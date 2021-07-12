from hashlib import new
from GoogleCalendarHelper import GoogleCalendarHelper
from discord import message
from CalendarEvent import *
import asyncio
import discord
import bisect
from datetime import datetime

class GuildCalendar():
	Emoji_Yes = '\u2705'
	Emoji_No = '\u274C'

	def __init__(self, guild) -> None:
		self.Guild = guild
		self.EventsDict = {} #for easily looking up events by the creation message id
		self.EventsList = [] #all events sorted by event start date
		self.NumLastEventsToTrack = 3 #how many events to show in the "newly created events" area
		self.LastEventsCreated = [] #last NumLastEventsToTrack events that have been created

		self.SummaryMessage = None
		self.GCalHelper = GoogleCalendarHelper()

		self.TaskQueue = asyncio.Queue()
		asyncio.create_task(self.EventChangeWorker(self.TaskQueue))

	async def EventChangeWorker(self, taskQueue : asyncio.Queue):
		while True:
			task = await taskQueue.get()
			await task()
			taskQueue.task_done()

	async def LoadCalendarFromEventsChannel(self):
		print(f"finding events channel for guild {self.Guild.name}")
		self.EventsChannel = next((x for x in self.Guild.channels if x.name == "events"))
		print(f'got events channel {self.EventsChannel.name}, getting messages')
		messages = await self.EventsChannel.history(limit=200).flatten()

		toRemove = []

		for message in messages:
			if(GuildCalendar.IsEventMessage(message)):
				try:
					newEvent = await CreateEventFromMessage(self, message)
					#since we already have the event in the channel, we don't need to do any posting
					await self.AddEvent(newEvent, False)
				except NotFound:
					print("linked message for this no longer exists, deleting event")
					toRemove.append(message)
			elif(GuildCalendar.IsSummaryMessage(message)):
				print("found summary message")
				self.SummaryMessage = message
				
		for msg in toRemove:
			await msg.delete()

		await self.UpdateSummary()

	async def HandleNewEventCommand(self, ctx, args):
		#lambda arguments don't get formed until they execute, so creating local vars in lambda scope is necessary
		self.TaskQueue.put_nowait(lambda ctx=ctx, args=args: self.NewEventCommand(ctx,args) ) 

	async def NewEventCommand(self, ctx, args):
		newEvent : CalendarEvent = await CreateEventFromCommand(self, ctx, args)
		await self.AddEvent(newEvent, True)

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
			#if the time changed, it may need to be removed and re-added
			if(oldDateTime != calEvent.StartDateTime):
				await self.DeleteEvent(calEvent)
				await self.AddEvent(calEvent, True)

			if(calEvent.EventMessage != None):
				calEvent.CachedEmbed = None
				await calEvent.EventMessage.edit(embed=calEvent.CreateEmbed())

	async def HandleMessageDelete(self, payload):
		self.TaskQueue.put_nowait(lambda payload=payload: self.MessageDelete(payload))

	async def MessageDelete(self, payload):
		if(payload.message_id in self.EventsDict):
			print("deleted message tied to event, deleting...")
			calEvent = self.EventsDict[payload.message_id]
			await self.DeleteEvent(calEvent)

	async def HandleReactAdd(self, payload):
		print("REACTION!")
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


	async def DeleteEvent(self, event : CalendarEvent):
		await event.EventMessage.delete()
		self.EventsList.remove(event)
		self.EventsDict.pop(event.CreationMessage.id)

		#delete google calendar thing
		if(event.GCalendarData != None):
			self.GCalHelper.DeleteEvent(event.GCalendarData['id'])
		
		await self.UpdateSummary()

	async def AddEvent(self, newEvent : CalendarEvent, shouldPost):
		#add to the events list sorted, and the events dictionary
		index = bisect.bisect(self.EventsList, newEvent)
		self.EventsList.insert(index, newEvent)
		self.EventsDict[newEvent.CreationMessage.id] = newEvent

		#update the LastEventsCreated array
		#TODO handle the lasteventscreated stuff

		#when creating from bot start, all the events currently exist already, so we don't want to do anything?
		#otherwise, gotta post stuff (and create the google calendar event?)
		if(shouldPost):
			newEvent.GCalendarData = self.GCalHelper.CreateEvent(newEvent.Title, newEvent.Description, newEvent.StartDateTime)
			newEvent.GCalendarLink = newEvent.GCalendarData['htmlLink']

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
			await(self.UpdateSummary())



	async def UpdateSummary(self, numTodayEvents = 10, numNewEvents = 3):
		summaryEmbed = discord.Embed(title = "Events Summary")
		
		#events happening today
		eventsTodayString = ""
		todayEvents = [x for x in self.EventsList if x.StartDateTime.date() == datetime.today().date()]
		todayEvents.sort(key=lambda x: x.StartDateTime, reverse=False)
		print(f"found {len(todayEvents)} today")
		if(len(todayEvents) < numTodayEvents):
			numTodayEvents = len(todayEvents)

		for i in range(numTodayEvents):
			eventString = todayEvents[i].GetSummaryString(False) + "\n"
			#print(eventString)
			eventsTodayString += eventString

		if(numTodayEvents == 0):
			eventsTodayString = "No events today"
		
		summaryEmbed.add_field(name="Today", value = eventsTodayString, inline = False)

		#newly added events
		if(len(self.EventsList) < numNewEvents):
			numNewEvents = len(self.EventsList)

		print(len(self.EventsList))
		newEvents = ""
		eventsByCreateDate = sorted(self.EventsList, key=lambda x: x.CreationMessage.created_at)
		eventsByCreateDate.reverse()
		for i in range(numNewEvents):
			eventString = eventsByCreateDate[i].GetSummaryString() + "\n"
			#print(eventString)
			newEvents += eventString	

		if(len(eventsByCreateDate) == 0):
			newEvents = "None"

		summaryEmbed.add_field(name = "Newly added", value = newEvents, inline=False)

		if(self.SummaryMessage != None):
			await self.SummaryMessage.delete()

		self.SummaryMessage = await self.EventsChannel.send(embed=summaryEmbed)
		
	
	def GetEventFromEventMessage(self, messageID):
		for event in self.EventsList:
			if(event.EventMessage != None and event.EventMessage.id == messageID):
				return event
		return None

	async def AddReactions(self, eventMessage):
		await eventMessage.add_reaction(self.Emoji_Yes)
		await eventMessage.add_reaction(self.Emoji_No)
		
	
	def IsSummaryMessage(message):
		sumString = "Events Summary"
		#should have an embed
		if(not len(message.embeds) == 1):
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
