from logging import NullHandler
from os import name
from discord import channel
from discord.channel import CategoryChannel, TextChannel
from discord.permissions import PermissionOverwrite
from discord.threads import Thread
from GoogleCalendarHelper import GoogleCalendarHelper
import datetime
import discord
import re
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
		self.EventMessage : discord.Message = None
		self.GCalendarLink = None
		self.GCalendarData = None

		self.RSVPList = []
		self.MaybeList = []

		self.EventThread : discord.Thread = None
		self.Thread = None
		
	def __lt__(self, other):
		return self.StartDateTime.__gt__(other.StartDateTime) #probably should just use lt and reverse

	def CreateEmbed(self) -> Embed:
		result = discord.Embed(title = self.Title, description = self.Description, url = self.CreationMessage.jump_url)
		result.add_field(name=_fieldHost, value = GetSanitizedNicknameLink(self.Host))
		result.add_field(name=_fieldStartTime, value = self.StartDateTime.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")) #gross python. GROSS.

		#for links, we're gonna be crazy and allow multiple...
		linksText = f"[{_subFieldCal}]({self.GCalendarLink})\n"
		if(self.EventThread != None):
			textChannelLink = GetLinkToChannel(self.EventThread)
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

	async def CreateThreadForEvent(self):
		if(self.EventThread == None):
			
			#figure out a name for the thread, use the event title up to 3 words (joined with -)
			maxWords = 3
			splitWords = self.Title.split()
			firstXWords = splitWords[:min(len(splitWords), 3)]
			possibleTitle = '-'.join(firstXWords)
			possibleTitle = possibleTitle.lower()

			#create the thread
			self.EventThread = await self.EventMessage.create_thread(name=possibleTitle)

			allUsers = self.RSVPList + self.MaybeList
			#add all rsvped people to the thread
			mentionList = ", ".join([x.mention for x in allUsers])
			message = f"Event thread created for {self.Title} {mentionList}"

			await self.EventThread.send(content=message)
		else:
			pass #thread already exists
		

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
			if(self.EventThread != None):
				await self.EventThread.add_user(user)
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
			if(self.EventThread != None):
				await self.EventThread.remove_user(user)
			await self.UpdateEmbed()

	async def UpdateEmbed(self):
		if(self.EventMessage != None):
			await self.EventMessage.edit(embed=self.CreateEmbed())

	async def DeleteTextChannel(self):
		if(self.EventThread != None):
			await self.EventThread.delete()
			self.EventThread = None

	def GetManualMention(self, user:discord.User):
		return f"<@{user.id}>"

	def GetMentionList(self, targetList):
		if(len(targetList)==0):
			return "None"
		
		userLinkList = []
		for user in targetList:
			userLink = GetSanitizedNicknameLink(user)
			userLinkList.append(userLink)

		result = ", ".join(userLinkList)
		#print("RSVPS: " + result)
		return result
	
	def GetSummaryString(self, includeDate = True):
		eventTitle = f"[{self.Title}]({self.EventMessage.jump_url}) "
		if(includeDate):
			eventTitle += "on "
		else:
			#no space here to correctly strip out leading zeros
			eventTitle += "at"

		#have space before %I so that we can correctly strip out leading 0s
		eventTime = self.StartDateTime.strftime(" %I:%M %p").replace(" 0", " ")
		if(includeDate):
			eventTime = self.StartDateTime.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")
		return eventTitle + eventTime
			
def GetUserIDsFromRSVPList(rsvpString):
	result = []
	#legacy, old way was with mentions, but ran into problems with user caching on some people's machines
	if(rsvpString[0]=="<"):
		rsvpMentions = rsvpString.split(' ')
		for rsvp in rsvpMentions:
			if(rsvp != "None"):
				userForRSVP = GetUserIDFromMention(rsvp)
				if(userForRSVP != None):
					result.append(userForRSVP)
	else:
		#new way is a list of the format (nickname)[userid] (separated by spaces, but some nicknames can have spaces)
		pattern = r"\[(.+?)\]\((.+?)\)"
		#this returns a list of tuples where the 2nd tuple element is the userid
		rsvps = re.findall(pattern, rsvpString)
		for rsvpTuple in rsvps:
			idString = rsvpTuple[1]
			#new method to have http in there... christ. strip out the http
			if(idString[0]=="h"):
				idString = idString[7:]
				
			id = int(idString)
			result.append(id)
	return result

#don't allow [] or () in nicknames
def GetSanitizedNicknameLink(user : discord.Member):
	nickname = user.display_name
	id = user.id
	
	santizedNickname = re.sub('[\[\]\(\)]', '', nickname)
	return f"[{santizedNickname}](http://{id})"

 #constructor from event message (when re-initializing events from messages)
async def CreateEventFromMessage(calendar, message:discord.Message) -> CalendarEvent:
	eventEmbed = message.embeds[0]

	result = CalendarEvent()

	result.CalendarRef = calendar
	result.EventThread = None

	result.Title = eventEmbed.title
	result.Description = eventEmbed.description
	result.CreationMessage = await GetMessageFromURL(eventEmbed.url, message.guild)
	result.EventMessage = message
	result.RSVPList = []

	print(f"Reading event {result.Title}")
	#see if the message has a thread and save it
	#seems like right now, the only way to get the thread is to look at ALL the threads
	#and check the referenced messageid on the first message in that thread
	for thread in message.channel.threads:
		messages = await thread.history(limit=1, oldest_first=True).flatten()
		if(messages[0].reference.message_id == message.id):
			result.EventThread = thread
			print("Found thread")
			break
	
	
	
	for field in eventEmbed.fields:
		if(field.name == _fieldHost):
			hostName = field.value
			#legacy
			if(hostName[0]=="<"):
				result.Host = await GetUserFromMention(hostName, calendar.Guild)
				#mention text, when in string form, looks like "<@#####>", so we need to strip out the brackets and @ to get the id itself
			else:
				#should just be 1 value
				hostIDList = GetUserIDsFromRSVPList(hostName)
				hostID = hostIDList[0]
				result.Host = await calendar.Guild.fetch_member(hostID)
				print(f"got host {result.Host.display_name}")
			
		elif(field.name == _fieldStartTime):
			try:
				eventDate = parse(field.value)
				result.StartDateTime = eventDate
			except ValueError:
				print("invalid date, couldn't read")
				result.StartDateTime = datetime.datetime.now
		elif(field.name[:len(_fieldRSVP)] == _fieldRSVP):
			rsvpMentions = GetUserIDsFromRSVPList(field.value)
			print(f"Got {len(rsvpMentions)} RSVPs")
			for rsvp in rsvpMentions:
				userForRSVP = await calendar.Guild.fetch_member(rsvp)
				if(userForRSVP != None):
					result.RSVPList.append(userForRSVP)

		elif(field.name[:len(_fieldMaybes)] == _fieldMaybes):
			maybeMentions = GetUserIDsFromRSVPList(field.value)
			print(f"Got {len(rsvpMentions)} maybes")
			for maybe in maybeMentions:
				userForMaybe = await calendar.Guild.fetch_member(maybe)
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
					result.EventThread = GetChannelFromURL(link, calendar.Guild)
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
	#changed to be >= 3 instead of 3, in case they put | in their descriptions
	if(len(splitCommand) >= 3):
		result.Title = splitCommand[0]
		result.StartDateTime = parse(splitCommand[1], fuzzy=True)
		result.Description = splitCommand[2]

	#loose definition
	else:
		parseResult = parse(commandText, fuzzy_with_tokens=True)
		result.StartDateTime = parseResult[0]
		result.Title = parseResult[1][0]
		result.Description = commandText

	await result.AddRSVP(ctx.author)
	return result

async def GetUserFromMention(mention, guild):
	#print(f"mention: {mention}")
	#mentions are format @<#######> OR <@!#####>, so we want to strip out the @ amd brackets
	try:
		userID = -1
		if(mention[2] == "!"):
			userID = int(mention[3:-1])
		else:
			userID = int(mention[2:-1])

		user = await guild.fetch_member(userID)
		return user
	except NotFound:
		return None
	except HTTPException:
		return None

def GetUserIDFromMention(mention):
	try:
		userID = -1
		if(mention[2] == "!"):
			userID = int(mention[3:-1])
		else:
			userID = int(mention[2:-1])
		return userID
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
