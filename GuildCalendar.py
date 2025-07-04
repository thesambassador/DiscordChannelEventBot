from hashlib import new
from SamDiscordUtilities import *
from dateutil.parser import ParserError
#from discord.components import C
from discord.enums import ChannelType, MessageType
from discord.threads import Thread
from GoogleCalendarHelper import GoogleCalendarHelper
from discord import message
import discord
from CalendarEvent import *
import asyncio
import discord
import bisect
import sys
import traceback
from datetime import datetime
from datetime import timedelta
import EventBotViews
from EventBotViews import EventViewActive
from EventBotViews import EventModal
from EventBotViews import DeleteModal

class GuildCalendar():
	Emoji_Yes = '\u2705'
	Emoji_No = '\u274C'
	Emoji_Maybe = '\u2754'
	Emoji_TextChannel = '\u2328'


	def __init__(self, guild) -> None:
		self.Guild = guild
		self.EventsDict = {} #for easily looking up events by the creation message id
		self.EventsList = [] #all events sorted by event start date
		self.ArchivedEventsList = []
		self.NumLastEventsToTrack = 3 #how many events to show in the "newly created events" area

		self.EventsChannel = None
		self.ArchiveChannel = None

		self.EventsMention : discord.Role = None #the role that this calendar should use when new events are created
		self.SummaryMessage : discord.Message = None
		self.LastArchiveDateTime : datetime.datetime = datetime.now()
		self.GCalHelper = GoogleCalendarHelper(guild.id)

		self.TaskQueue = asyncio.Queue()
		asyncio.create_task(self.EventChangeWorker(self.TaskQueue))

	async def EventChangeWorker(self, taskQueue : asyncio.Queue):
		while True:
			task = await taskQueue.get()
			try:
				await task()
			except: #catch all exceptions in here so that they don't make the worker break?
				traceback.print_exc()
			taskQueue.task_done()

	async def LoadCalendarFromEventsChannel(self):
		eventChannelName = "events" #todo: change this to a config value
		archiveChannelName = "eventarchive"

		print(f"finding events channel for guild {self.Guild.name}")
		self.EventsChannel = next((x for x in self.Guild.channels if x.name == eventChannelName))
		print(f'got events channel {self.EventsChannel.name}, getting messages')
		#messages = await self.EventsChannel.history(limit=200).flatten()  I guess flatten might  not work any more?
		messages = [message async for message in self.EventsChannel.history(limit=200)]

		print(f"finding archive channel for guild {self.Guild.name}")
		self.ArchiveChannel = next((x for x in self.Guild.channels if x.name == archiveChannelName))


		toRemove = []

		for message in messages:
			if(GuildCalendar.IsEventMessage(message)):
				try:
					newEvent = await CreateEventFromMessage(self, message)
					#if the event message has reactions, it's in the "old" format and we need to update
					if(len(message.reactions) > 0):
						print("Old style event, gotta update")
						await message.edit(view = EventViewActive())
						await message.clear_reactions()

					#going to tell it to just create the thread here for all of them to fix the events that didn't get threads
					await newEvent.CreateThreadForEvent()
					
					#since we already have the event in the channel, we don't need to do any posting
					await self.AddEvent(newEvent, False)
				except NotFound:
					print("linked message for this no longer exists, deleting event")
					toRemove.append(message)
			elif(GuildCalendar.IsSummaryMessage(message)):
				print("found summary message")
				#check for the role mention in the last embed of the summary
				numEmbeds = len(message.embeds)
				print(f"Found {numEmbeds} embeds")
				lastEmbed = message.embeds[numEmbeds-1]
				roleMentions = get_role_mentions_in_string(lastEmbed.description, message.guild)
				if(len(roleMentions) > 0):
					print(f"got role {roleMentions[0]}")
					self.EventsMention = roleMentions[0]
				
				self.SummaryMessage = message
				

				
		for msg in toRemove:
			await msg.delete()

		await self.UpdateSummary()
	
	#old non-slash commmand method
	async def HandleNewEventCommand(self, ctx, args):
		#lambda arguments don't get formed until they execute, so creating local vars in lambda scope is necessary
		self.TaskQueue.put_nowait(lambda ctx=ctx, args=args: self.NewEventCommand(ctx,args) ) 

	#new slash command method
	async def HandleNewEventSlashCommand(self, interaction : discord.Interaction, title : str, date : str, starttime : str, description : str):
		await interaction.response.defer()
		self.TaskQueue.put_nowait(lambda i=interaction: self.NewEventSlashCommand(i, title, date, starttime, description))
	
	async def NewEventSlashCommand(self, interaction : discord.Interaction, title : str, date : str, starttime : str, description : str):
		#try to create the new event from the command
		try:
			newEvent : CalendarEvent = CreateEventFromSlashCommand(self, interaction, title, date, starttime, description)
			print(newEvent.StartDateTime)
			if(newEvent.StartDateTime < datetime.now()):
				print("date is in past")
				await interaction.followup.send(content="The date you put was in the past, re-check the date and try again. On PC, hitting the up arrow should re-populate the slash command with what you put in!", ephemeral=True)
				await self.PostResponseMessage(newEvent, 3)
			else:
				#if we were successful in parsing the command into an event, post it to the events channel
				await self.AddEvent(newEvent, True)
				response = f"[New Event - {newEvent.Title}]({newEvent.EventMessage.jump_url})"
				await interaction.followup.send(content=response)

		except ParserError:
			await interaction.followup.send(content="Something went wrong when parsing the date, check the input and try again. On PC, hitting the up arrow should re-populate the slash command with what you put in!", ephemeral=True)


	#for handling the event response drop down options
	async def HandleEventDropDownInteraction(self, interaction : discord.Interaction, selectedValue):
		reactedEvent = self.GetEventFromEventMessage(interaction.message.id)
		isAdmin = interaction.permissions.send_messages
		isHost = interaction.user == reactedEvent.Host
		canEdit = isAdmin or isHost

		if(selectedValue == EventBotViews.stringGoing):
			await reactedEvent.AddRSVP(interaction)
			
		elif(selectedValue == EventBotViews.stringMaybe):
			await reactedEvent.AddRSVP(interaction, True)
			
		elif(selectedValue == EventBotViews.stringNo):
			await reactedEvent.RemoveRSVP(interaction)

		elif(selectedValue == EventBotViews.stringEdit):
			if(canEdit):
				await interaction.response.send_modal(EventModal(reactedEvent))
			else:
				await interaction.response.send_message("You are not the creator of the event, so you cannot edit it", ephemeral=True)
		elif(selectedValue == EventBotViews.stringDelete):
			if(canEdit):
				await interaction.response.send_modal(DeleteModal(reactedEvent))
			else:
				await interaction.response.send_message("You are not the creator of the event, so you cannot delete it", ephemeral=True)
		else:
			await interaction.response.defer()

	#for handling when they hit the "submit" button on the edit event modal
	async def HandleEditEventSubmit(self, interaction : discord.Interaction, title : str, date : str, starttime : str, description : str):
		event = self.GetEventFromEventMessage(interaction.message.id)
		await event.EditEvent(interaction, title, date, starttime, description)
		

	#this should only happen once they've already typed in delete, so just do it
	async def HandleDeleteEventSubmit(self, interaction : discord.Interaction):
		event = self.GetEventFromEventMessage(interaction.message.id)
		await self.DeleteEvent(event)
		await interaction.response.send_message("Event deleted", ephemeral=True, delete_after=30)


	#OLD METHOD NOT USED
	async def NewEventCommand(self, ctx, args):
		print("new event!")
		errorMessage = ""
		#try to create the new event from the command
		try:
			newEvent : CalendarEvent = CreateEventFromCommand(self, ctx, args)
			print(newEvent.StartDateTime)
			if(newEvent.StartDateTime < datetime.now()):
				print("date is in past")
				await self.PostResponseMessage(newEvent, 3)
			else:
				#if we were successful in parsing the command into an event, post it to the events channel
				await self.AddEvent(newEvent, True)
				
				await self.PostResponseMessage(newEvent)

		except ParserError:
			nullEvent = CalendarEvent()
			nullEvent.CreationMessage = ctx.message
			await self.PostResponseMessage(nullEvent, 2)
		
		# except:
		# 	nullEvent = CalendarEvent()
		# 	nullEvent.CreationMessage = ctx.message
		# 	await self.PostResponseMessage(nullEvent, 1)

	async def PostResponseMessage(self, calEvent : CalendarEvent, errorCode = 0):
		pass
		#TODO this whole thing is gross and i'll fix it properly lol
		# createMessage : discord.Message = calEvent.CreationMessage
		# createChannel : TextChannel = createMessage.channel
		# #no error
		# if(errorCode == 0):
		# 	responseMessage = f"[Successfully created your event, click here to see it in the events channel]({calEvent.EventMessage.jump_url})"
		# 	responseEmbed = discord.Embed(description = responseMessage)
		# 	await createChannel.send(embed=responseEmbed, reference=createMessage, delete_after=120)

		# elif(errorCode == 1):
		# 	errorMessage = "Something went wrong when parsing your message, try again?"
		# 	await createChannel.send(content=errorMessage, reference=createMessage, delete_after=120)
		# elif(errorCode == 2):
		# 	errorMessage = "Couldn't determine a date for your event, make sure that your event has a date and time in it"
		# 	await createChannel.send(content=errorMessage, reference=None, delete_after=120)
		# elif(errorCode == 3):
		# 	dateString = calEvent.StartDateTime.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")
		# 	errorMessage = f"Looks like your selected date, {dateString}, might be in the past? Unfortunately, nobody on this server can time travel, try again"
		# 	await createChannel.send(content=errorMessage, reference=createMessage, delete_after=120)

	async def HandleSetupCommand(self, interaction : discord.Interaction, eventMention : discord.Role):
		self.EventsMention = eventMention
		await interaction.response.send_message("Set settings", ephemeral=True)

	async def HandleMessageEdit(self, payload):
		self.TaskQueue.put_nowait(lambda payload=payload: self.MessageEdit(payload))

	async def MessageEdit(self, payload):
		if(payload.message_id in self.EventsDict):
			print("editted message tied to event, editing...")
			chan = self.Guild.get_channel(payload.channel_id)
			msg = await chan.fetch_message(payload.message_id)
			print(f"new message contents {msg.content}")
			calEvent = self.EventsDict[payload.message_id]

			oldDateTime = calEvent.StartDateTime
			await calEvent.UpdateMessage(msg.content)
			#not sure why this was my logic, commenting for now #if the time changed, it may need to be removed and re-added
			# if(oldDateTime != calEvent.StartDateTime):
			# 	await self.DeleteEvent(calEvent)
			# 	await self.AddEvent(calEvent, True)

			#update summary
			await self.UpdateSummary()

			if(calEvent.EventMessage != None):
				await calEvent.EventMessage.edit(embed=calEvent.CreateEmbed())

	async def HandleMessageDelete(self, payload):
		self.TaskQueue.put_nowait(lambda payload=payload: self.MessageDelete(payload))

	async def MessageDelete(self, payload):
		if(payload.message_id in self.EventsDict):
			print("deleted message tied to event, deleting...")
			calEvent = self.EventsDict[payload.message_id]
			await self.DeleteEvent(calEvent)

	async def HandleReactAdd(self, payload):
		#print("REACTION!")
		reactedEvent = self.GetEventFromEventMessage(payload.message_id)
		if(reactedEvent != None):
			print(f"reacted to event {reactedEvent.Title}")
			user = await self.Guild.fetch_member(payload.user_id)

			if(str(payload.emoji) == self.Emoji_Yes):
				print("yes")
				await reactedEvent.AddRSVP(user)
				await reactedEvent.EventMessage.remove_reaction(self.Emoji_Yes, user)

			elif(str(payload.emoji) == self.Emoji_No):
				print("no")
				await reactedEvent.RemoveRSVP(user)
				await reactedEvent.EventMessage.remove_reaction(self.Emoji_No, user)

			elif(str(payload.emoji) == self.Emoji_Maybe):
				await reactedEvent.AddRSVP(user, True)
				await reactedEvent.EventMessage.remove_reaction(self.Emoji_Maybe, user)

			elif(str(payload.emoji) == self.Emoji_TextChannel):
				if(user.id == reactedEvent.Host.id):
					await reactedEvent.CreateThreadForEvent()
				else:
					#changing this to allow anybody to do this?
					await reactedEvent.CreateThreadForEvent()

				await(reactedEvent.EventMessage.remove_reaction(self.Emoji_TextChannel, user))
			else:
				pass
				#temporarily doing this to test something
				#await reactedEvent.EventMessage.remove_reaction(payload.emoji, user)


	async def DeleteEvent(self, event : CalendarEvent):
		await event.EventMessage.delete()
		self.EventsList.remove(event)
		#self.EventsDict.pop(event.CreationMessage.id) NO LONGER NEEDED

		#delete google calendar thing
		if(event.GCalendarData != None):
			self.GCalHelper.DeleteEvent(event.GCalendarData['id'])
		await event.DeleteTextChannel()
		
		await self.UpdateSummary()

	#Adds a CalendarEvent to the events list and dict. 
	# If shouldPost is true, it also creates a google calendar entry for it,
	#posts the event to the events channel, and updates the events summary
	async def AddEvent(self, newEvent : CalendarEvent, shouldPost, reorderEvents = False):
		#add to the events list sorted, and the events dictionary
		index = bisect.bisect(self.EventsList, newEvent)
		self.EventsList.insert(index, newEvent)
		#self.EventsDict[newEvent.CreationMessage.id] = newEvent NO LONGER NEEDED

		#update the LastEventsCreated array
		#TODO handle the lasteventscreated stuff

		#when creating from bot start, all the events currently exist already, so we don't want to do anything?
		#otherwise, gotta post stuff (and create the google calendar event?)
		if(shouldPost):
			newEvent.GCalendarData = self.GCalHelper.CreateEvent(newEvent.Title, newEvent.Description, newEvent.StartDateTime)
			newEvent.GCalendarLink = newEvent.GCalendarData['htmlLink']
			
			#if we want to reorder the events page to be in order of date, we do so here
			#going to not do this any more though since we can't move threads between messages, and the summary should be enough to keep track of stuff
			if(reorderEvents):
				#add a new message for the last event in the list (might be a duplicate for now)
				lastEmbed = self.EventsList[-1].CreateEmbed()
				newMessage = await self.EventsChannel.send(embed=lastEmbed)
				await self.AddReactions(newMessage)

				#slide down any events happening sooner
				forwardEventMessage = self.EventsList[-1].EventMessage #
				for i in range(len(self.EventsList) - 2, index-1, -1):
					await forwardEventMessage.edit(embed=self.EventsList[i].CreateEmbed())
					saveCurrent = self.EventsList[i].EventMessage
					self.EventsList[i].EventMessage = forwardEventMessage
					forwardEventMessage = saveCurrent
			
				self.EventsList[-1].EventMessage = newMessage
			else:
				newEmbed = newEvent.CreateEmbed()
				content = ""
				if(self.EventsMention != None):
					content = self.EventsMention.mention
				newMessage = await self.EventsChannel.send(content=content, embed=newEmbed, view = EventViewActive())
				#await self.AddReactions(newMessage) no longer need to add reactions
				newEvent.EventMessage = newMessage
				await newEvent.CreateThreadForEvent()
				await(self.UpdateSummary())
			

		

	#note that embed fields seem to have a limit of 1024 characters per field
	#whole embed might have an overall character limit of 6000
	async def UpdateSummary(self, numTodayEvents = 10, numWeekEvents = 10, numFutureEvents = 10):
		summaryEmbeds = []
		
		#events happening today
		eventsTodayString = ""
		todayEvents = [x for x in self.EventsList if x.StartDateTime.date() == datetime.today().date()]
		todayEvents.sort(key=lambda x: x.StartDateTime, reverse=False)
		print(f"found {len(todayEvents)} today")

		todayEmbed = self.CreateSummaryEmbedFromList(todayEvents, "Events Today", numTodayEvents, "No events today", False)
		summaryEmbeds.append(todayEmbed)

		#events this week
		thisWeekEvents = [x for x in self.EventsList 
						if x.StartDateTime.date() <= (datetime.today().date() + timedelta(days=7)) and
						x.StartDateTime.date() >= (datetime.today().date() + timedelta(days=1))]
		thisWeekEvents.sort(key=lambda x: x.StartDateTime, reverse=False)
		
		thisWeekEmbed = self.CreateSummaryEmbedFromList(thisWeekEvents, "Events This Week", numWeekEvents, "No events later this week")
		summaryEmbeds.append(thisWeekEmbed)

		#events further out than the week
		futureEvents = [x for x in self.EventsList
						if x not in thisWeekEvents and
						x not in todayEvents]
		futureEvents.sort(key=lambda x: x.StartDateTime, reverse=False)

		futureEventsEmbed = self.CreateSummaryEmbedFromList(futureEvents, "In More Than A Week", numFutureEvents, "None")
		summaryEmbeds.append(futureEventsEmbed)
		

		
		
		#newlyAddedEmbed = self.CreateSummaryEmbedFromList(eventsByCreateDate, "Newly Created Events", numNewEvents, "No events added so far")
		#summaryEmbeds.append(newlyAddedEmbed)

		#add event usage FAQ link
		usageEmbed = discord.Embed()
		description = "[Click here to find out how to use this channel!](https://github.com/thesambassador/DiscordChannelEventBot/wiki/User-Usage)\n"
		description += f"Problems or suggestions? Message <@116783246599127044>\n"
		if(self.EventsMention != None):
			description += f"Get the {self.EventsMention.mention} role from the Channels & Roles to get notified on new events!"
		usageEmbed.description = description
		

		summaryEmbeds.append(usageEmbed)

		#check if the summary is currently the LAST message in the channel. 
		#if yes, just edit that message
		messages = [message async for message in self.EventsChannel.history(limit=1, oldest_first=False)]

		if(len(messages) > 0 and GuildCalendar.IsSummaryMessage(messages[0])):
			print("summary is last, just editting")
			self.SummaryMessage = messages[0]
			await self.SummaryMessage.edit(embeds=summaryEmbeds)

		#if no, delete that message and re-post
		#delete the existing summary set if it exists
		else:
			if(self.SummaryMessage != None):
				await self.SummaryMessage.delete()
				self.SummaryMessage = None
			#post the new one with the embed sets
			self.SummaryMessage = await self.EventsChannel.send(embeds=summaryEmbeds)

	#embeds can be a max of 6000 characters including title and probably other stuff...
	#probably should handle that at some point just in case but not now TODO
	#since we're limiting number of events per "section" this should be OK?
	def CreateSummaryEmbedFromList(self, eventList, embedTitle, numEvents, zeroLengthString, includeDate = True):
		maxEmbedDescriptionLength = 5800

		if(numEvents > len(eventList)):
			numEvents = len(eventList)

		summaryEmbed = discord.Embed(title = embedTitle)

		if(numEvents == 0):
			summaryEmbed.description = zeroLengthString
		else:
			summaryStrings = []
			for i in range(numEvents):
				summaryStrings.append(eventList[i].GetSummaryString(includeDate))

			summaryString = '\n'.join(summaryStrings)

			summaryEmbed.description = summaryString
		
		return summaryEmbed
	
	#called both when the bot joins a thread AND when the thread is created!
	async def HandleThreadJoined(self, thread:Thread):
		self.TaskQueue.put_nowait(lambda thread=thread: self.ThreadJoined(thread))

	async def ThreadJoined(self, thread:Thread):
		#print("thread joined")
		pass

	#threads probably generally won't be deleted but... ya know
	async def HandleThreadDeleted(self, thread:Thread):
		self.TaskQueue.put_nowait(lambda thread=thread: self.ThreadDeleted(thread))	

	async def ThreadDeleted(self, thread:Thread):
		pass

	async def HandleThreadUpdated(self, before:Thread, after:Thread):
		self.TaskQueue.put_nowait(lambda before=before, after=after: self.ThreadUpdated(before,after))

	async def ThreadUpdated(self, before:Thread, after:Thread):
		print(f"Threadupdated: {before.id}, {after.id}")
		event = self.GetEventForThread(after)
		if(event == None): 
			print("not an event thread")
			return

		#update the event thread to the newly updated one so archived is updated
		event.EventThread = after

		if(before.archived and not after.archived):
			print("thread unarchived")
			await event.UpdateThreadMentionMessage()
		elif(not before.archived and after.archived):
			print("thread archived")
		else:
			print("some other update")
		

	def GetEventForThread(self, thread:Thread) -> CalendarEvent:
		for event in self.EventsList:
			print("event")
			if(event.EventThread != None):
				print(f"  checking thread id {event.EventThread.id}")
				if(event.EventThread.id == thread.id):
					return event
		return None

	async def HandleNewMessage(self, message:message.Message):
		self.TaskQueue.put_nowait(lambda message=message: self.NewMessage(message))

	#we want to suppress discord's annoying "added x user to thread" and "started a thread" messages
	#edit - seems like we can't delete the thread "x user added to thread" message, so I'll just add users another way
	async def NewMessage(self, message:message.Message):
		#print(f"--MESSAGE TYPE: {message.type}, CHANNELTYPE: {message.channel.type}")
		#check to see if the message is in the events channel first
		if(self.IsEventThreadCreatedMessage(message)):
			await message.delete()
		#otherwise, check and see if it's in a thread that's in the events channel (apparently you can't delete these so commenting this out)
		# elif(self.IsEventThreadMessage(message)):
		# 	if(message.type == discord.MessageType.recipient_add or message.type == discord.MessageType.recipient_remove):
		# 		await message.channel.delete_messages([message])

	def IsEventThreadCreatedMessage(self, message:message.Message):
		return ((message.channel.id == self.EventsChannel.id) and (message.type == discord.MessageType.thread_created))
		
	def IsEventThreadMessage(self, message:message.Message):
		if(message.channel.type == discord.ChannelType.public_thread):
			if(message.channel.parent.id == self.EventsChannel.id):
				#print("event thread message!")
				return True

			return False

	def GetEventFromEventMessage(self, messageID) -> CalendarEvent:
		for event in self.EventsList:
			if(event.EventMessage != None and event.EventMessage.id == messageID):
				return event
		return None

	async def AddReactions(self, eventMessage):
		await eventMessage.add_reaction(self.Emoji_Yes)
		await eventMessage.add_reaction(self.Emoji_Maybe)
		await eventMessage.add_reaction(self.Emoji_No)
		await eventMessage.add_reaction(self.Emoji_TextChannel)
		
	async def HandleArchiveOld(self):
		self.TaskQueue.put_nowait(lambda: self.ArchiveOld())

	async def ArchiveOld(self):
		oldnessBuffer = 8 #amount of hours that the event stays in the event channel even after it's started
		print("Starting archiving...")
		now = datetime.now()
		oldnessBufferDelta = timedelta(hours=oldnessBuffer)
		toArchive = []

		for event in self.EventsList:
			if(event.StartDateTime + oldnessBufferDelta < now):
				toArchive.append(event)

		numArchived = len(toArchive)
		print(f"found {numArchived} events need to be archived")

		for oldEvent in toArchive:
			#post the event in the archive channel
			archiveMessage = await self.ArchiveChannel.send(embed = oldEvent.CreateEmbed())

			#delete the event in the events channel
			await oldEvent.EventMessage.delete()
			await oldEvent.DeleteTextChannel()

			oldEvent.EventMessage = archiveMessage
			oldEvent.IsArchived = True

			self.EventsList.remove(oldEvent)
			#self.EventsDict.pop(oldEvent.CreationMessage.id)

			self.ArchivedEventsList.append(oldEvent)

		shouldArchive = numArchived > 0
		#if it's a new day, we should update the summary to make sure that "today" is accurate
		if(self.LastArchiveDateTime.date() != datetime.now().date()):
			shouldArchive = True

		#have it update the summary
		if(shouldArchive):
			await self.UpdateSummary()

		print("Done archiving")
		self.LastArchiveDateTime = datetime.now()
	
	def IsSummaryMessage(message):
		sumString = "Events Today"
		#should have an embed
		if(not len(message.embeds) == 4):
			return False
		
		if(message.embeds[0].title != sumString):
			return False

		return True

	#figure out if the message fits the format for an "event" message
	def IsEventMessage(message):
		#should have an embed
		if(not len(message.embeds) == 1):
			return False
		
		fieldNames = [x.name for x in message.embeds[0].fields]
		expectedFields = ["Host", "Start Time"]
		for field in expectedFields:
			if(field not in fieldNames):
				return False

		return True


async def CreateCalendarForGuild(guild) -> GuildCalendar:
	print(f"Reading calendar for {guild.name}")
	result = GuildCalendar(guild)
	await result.LoadCalendarFromEventsChannel()
	return result
