from logging import NullHandler
from os import name
from discord.channel import CategoryChannel, TextChannel
from discord.permissions import PermissionOverwrite
from GoogleCalendarHelper import GoogleCalendarHelper
import datetime
import discord
from discord.embeds import Embed
from dateutil.parser import parse
from discord.errors import Forbidden, HTTPException, NotFound
from discord.ext import commands
#from GuildCalendar import *

_fieldHost = "Host"
_fieldStartTime = "Start Time"
_fieldLinks = "Links"
_fieldRSVP = "RSVPs"
_fieldMaybes = "Maybes"
_subFieldCal = "Calendar"
_subFieldChannel = "Channel"

class CalendarEvent():

	def __init__(self) -> None:
		self.Title = ""
		self.Description = ""
		self.Host = None
		self.StartDateTime = None

		self.CalendarRef = None
		self.CreationMessage = None
		self.EventMessage = None
		self.GCalendarLink = None
		self.GCalendarData = None

		self.RSVPList = []
		self.MaybeList = []

		self.TextChannel = None
		
	def __lt__(self, other):
		return self.StartDateTime.__gt__(other.StartDateTime) #probably should just use lt and reverse

	def CreateEmbed(self) -> Embed:
		result = discord.Embed(title = self.Title, description = self.Description, url = self.CreationMessage.jump_url)
		result.add_field(name=_fieldHost, value = self.Host.mention)
		result.add_field(name=_fieldStartTime, value = self.StartDateTime.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")) #gross python. GROSS.

		#for links, we're gonna be crazy and allow multiple...
		linksText = f"[{_subFieldCal}]({self.GCalendarLink})\n"
		if(self.TextChannel != None):
			textChannelLink = GetLinkToChannel(self.TextChannel)
			linksText += f"[{_subFieldChannel}]({textChannelLink})"

		result.add_field(name=_fieldLinks, value = linksText)
		result.add_field(name=f"{_fieldRSVP} ({len(self.RSVPList)})", value = self.GetMentionList(self.RSVPList), inline=True)
		result.add_field(name=f"{_fieldMaybes} ({len(self.MaybeList)})", value = self.GetMentionList(self.MaybeList), inline=True)

		return result
	
	async def UpdateMessage(self, msgString):
		noCommandMessage = msgString[7:] #remove the command part of the message (the !event part)
		
		#determine if this is follows the strict syntax or if it's "loose"
		splitCommand = noCommandMessage.split("|")

		#strict definition:
		if(len(splitCommand) == 3):
			self.Title = splitCommand[0]
			self.StartDateTime = parse(splitCommand[1], fuzzy=True)
			self.Description = splitCommand[2]

		#loose definition
		else:
			self.StartDateTime = parse(noCommandMessage, fuzzy=True)
			self.Title = "Event"
			self.Description = noCommandMessage

		if(self.EventMessage != None):
			await self.EventMessage.edit(embed=self.CreateEmbed())

	async def CreateChannelForEvent(self, channelCategory : CategoryChannel):
		if(self.TextChannel == None):
			#figure out a name for the channel, use the event title up to 3 words
			maxWords = 3
			splitWords = self.Title.split()
			firstXWords = splitWords[:min(len(splitWords), 3)]
			firstXWords.insert(0, "event")
			possibleTitle = '-'.join(firstXWords)
			possibleTitle = possibleTitle.lower()

			#see if that channel name already exists (if yes figure out a new name)
			num = 1
			candidate = possibleTitle
			while(any(x.name == candidate for x in channelCategory.channels)):
				candidate = possibleTitle + str(num)
				num += 1
			possibleTitle = candidate
			print(f"trying to create channel with {possibleTitle}")

			#create the channel with overrides for all rsvped people
			overwrites = {}
			overwrites[channelCategory.guild.default_role] = discord.PermissionOverwrite(read_messages=False)
			for user in self.RSVPList:
				overwrites[user] = discord.PermissionOverwrite(read_messages=True)

			channel = await channelCategory.create_text_channel(possibleTitle, overwrites=overwrites)
			self.TextChannel = channel

			#post a message in the channel that @mentions all rsvped people
			channelEmbed = self.CreateEmbed()
			await channel.send(embed=channelEmbed)
			channelMessage = "This is a TEMPORARY channel to discuss the above event. This channel will be deleted when the event is archived or deleted. Only people who have RSVPed to the event can see this channel. "
			rsvpMentions = [channelMessage]
			for rsvp in self.RSVPList:
				rsvpMentions.append(rsvp.mention)
			
			messageToSend = " ".join(rsvpMentions)

			await channel.send(messageToSend)

			#add channel link to the event embed in the links section
			await self.UpdateEmbed()

			pass
		else:
			pass #channel already exists
		pass

	async def AddRSVP(self, user, isMaybe=False):
		toUse = self.RSVPList
		if(isMaybe):
			toUse = self.MaybeList
			#if they're switching to a maybe but are in the rsvp list, remove them
			if(user in self.RSVPList):
				self.RSVPList.remove(user)
		else:
			#if they're switching to RSVP but in the maybe list, remove them
			if(user in self.MaybeList):
				self.MaybeList.remove(user)

		if(user not in toUse):
			#print("adding")
			toUse.append(user)
			if(self.TextChannel != None):
				await self.TextChannel.set_permissions(user, overwrite = PermissionOverwrite(read_messages=True))
			await self.UpdateEmbed()
		

	async def RemoveRSVP(self, user):
		removed = False
		if(user in self.RSVPList):
			self.RSVPList.remove(user)
			removed = True
		
		if(user in self.MaybeList):
			self.MaybeList.remove(user)
			removed = True

		if(removed):
			if(self.TextChannel != None):
				await self.TextChannel.set_permissions(user, overwrite=None) #clears permissions on the channel
			await self.UpdateEmbed()

	async def UpdateEmbed(self):
		if(self.EventMessage != None):
			await self.EventMessage.edit(embed=self.CreateEmbed())

	async def DeleteTextChannel(self):
		if(self.TextChannel != None):
			await self.TextChannel.delete()
			self.TextChannel = None



	def GetMentionList(self, targetList):
		if(len(targetList)==0):
			return "None"
		result = " ".join([(x.mention) for x in targetList])
		#print("RSVPS: " + result)
		return result
	
	def GetSummaryString(self, includeDate = True):
		eventTitle = f"[{self.Title}]({self.EventMessage.jump_url}) "
		if(includeDate):
			eventTitle += "on "
		else:
			eventTitle += "at "

		eventTime = self.StartDateTime.strftime("%I:%M %p").replace(" 0", " ")
		if(includeDate):
			eventTime = self.StartDateTime.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")
		return eventTitle + eventTime
			

 #constructor from event message (when re-initializing events from messages)
async def CreateEventFromMessage(calendar, message) -> CalendarEvent:
	eventEmbed = message.embeds[0]

	result = CalendarEvent()

	result.CalendarRef = calendar
	result.TextChannel = None

	result.Title = eventEmbed.title
	result.Description = eventEmbed.description
	result.CreationMessage = await GetMessageFromURL(eventEmbed.url, message.guild)
	result.EventMessage = message
	result.RSVPList = []

	test = await GetUserFromMention("2357328573", calendar.Guild)
	print(test)
	
	for field in eventEmbed.fields:
		if(field.name == _fieldHost):
			#mention text, when in string form, looks like "<@#####>", so we need to strip out the brackets and @ to get the id itself
			hostName = field.value
			hostID = int(hostName[2:-1])
			result.Host = await message.guild.fetch_member(hostID)
		elif(field.name == _fieldStartTime):
			try:
				eventDate = parse(field.value)
				result.StartDateTime = eventDate
			except ValueError:
				print("invalid date, couldn't read")
				result.StartDateTime = datetime.datetime.now
		elif(field.name[:len(_fieldRSVP)] == _fieldRSVP):
			rsvpMentions = field.value.split(' ')
			for rsvp in rsvpMentions:
				userForRSVP = await GetUserFromMention(rsvp, calendar.Guild)
				if(userForRSVP != None):
					result.RSVPList.append(userForRSVP)

		elif(field.name[:len(_fieldMaybes)] == _fieldMaybes):
			maybeMentions = field.value.split(' ')
			for maybe in maybeMentions:
				userForMaybe = await GetUserFromMention(maybe, calendar.Guild)
				if(userForMaybe != None):
					result.MaybeList.append(userForMaybe)

		elif(field.name == _fieldLinks):
			textLinks = GetTextLinks(field.value)
			for textLink in textLinks:
				linkTitle = textLink[0]
				link = textLink[1]
				print(f"{linkTitle} link found, is {link}")
				if(linkTitle==_subFieldCal):
					eventID = GoogleCalendarHelper.GetEventIDFromLink(link)
					result.GCalendarData = calendar.GCalHelper.GetEvent(eventID)
					result.GCalendarLink = result.GCalendarData["htmlLink"]
				elif(linkTitle==_subFieldChannel):
					result.TextChannel = GetChannelFromURL(link, calendar.Guild)
					pass

	return result

#constructor from command (when creating events from a command)
async def CreateEventFromCommand(calendar, ctx, commandText):
	result = CalendarEvent()

	result.CalendarRef = calendar #ref to containing calendar
	result.EventMessage = None

	result.CreationMessage = ctx.message #message that created the event
	result.Host = ctx.author
	result.RSVPList = [] #this is a new event so no RSVPs yet?

	#determine if this is follows the strict syntax or if it's "loose"
	splitCommand = commandText.split("|")

	#strict definition:
	if(len(splitCommand) == 3):
		result.Title = splitCommand[0]
		result.StartDateTime = parse(splitCommand[1], fuzzy=True)
		result.Description = splitCommand[2]

	#loose definition
	else:
		result.StartDateTime = parse(commandText, fuzzy=True)
		result.Title = "Event"
		result.Description = commandText

	await result.AddRSVP(ctx.author)
	return result

async def GetUserFromMention(mention, guild):
	#mentions are format @<#######>, so we want to strip out the @ amd brackets
	try:
		userID = mention[2:-1]
		user = await guild.fetch_member(userID)
		return user
	except NotFound:
		return None
	except HTTPException:
		return None


async def GetMessageFromURL(url, guild):
	vals = url.split("/")
	try:
		channelID = int(vals[5])
		msgID = int(vals[6])

		channel = guild.get_channel(channelID)
		message = await channel.fetch_message(msgID)
		return message

	except ValueError:
		return 0

def GetChannelFromURL(url, guild):
	vals = url.split("/")
	try:
		channelID = int(vals[5])

		channel = guild.get_channel(channelID)

		return channel

	except ValueError:
		return 0


def GetTextLinks(input : str):
	result = []
	lines = input.split('\n')
	for line in lines:
		link = line[line.find("(")+1:line.find(")")]
		text = line[line.find("[")+1:line.find("]")]
		linkText = (text, link)
		result.append(linkText)
	return result

def GetLinkToChannel(channel : TextChannel):
	guildID = channel.guild.id
	channelID = channel.id
	return f"https://discord.com/channels/{guildID}/{channelID}/"
