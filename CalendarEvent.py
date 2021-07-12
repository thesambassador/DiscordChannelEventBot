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
_subFieldCal = "Calendar"

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
		self.CachedEmbed = None

		
	def __lt__(self, other):
		return self.StartDateTime.__gt__(other.StartDateTime) #probably should just use lt and reverse

	def CreateEmbed(self) -> Embed:
		if(self.CachedEmbed != None):
			return self.CachedEmbed
		result = discord.Embed(title = self.Title, description = self.Description, url = self.CreationMessage.jump_url)
		result.add_field(name=_fieldHost, value = self.Host.mention)
		result.add_field(name=_fieldStartTime, value = self.StartDateTime.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")) #gross python. GROSS.
		result.add_field(name=_fieldLinks, value= f"[{_subFieldCal}]({self.GCalendarLink})")
		result.add_field(name=f"{_fieldRSVP} ({len(self.RSVPList)})", value = self.GetRSVPList(), inline=False)
		self.CachedEmbed = result
		return result
	
	async def UpdateMessage(self, msgString):
		noCommandMessage = msgString[7:]
		
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
			self.CachedEmbed = None
			await self.EventMessage.edit(embed=self.CreateEmbed())

	async def AddRSVP(self, user):
		print(self.RSVPList)
		if(user not in self.RSVPList):
			print("adding")
			self.RSVPList.append(user)
			await self.UpdateEmbed()
		

	async def RemoveRSVP(self, user):
		if(user in self.RSVPList):
			self.RSVPList.remove(user)
			await self.UpdateEmbed()

	async def UpdateEmbed(self):
		if(self.EventMessage != None):
			self.CachedEmbed = None
			await self.EventMessage.edit(embed=self.CreateEmbed())

	def GetRSVPList(self):
		if(len(self.RSVPList)==0):
			return "None"
		result = "".join([(x.mention + ",") for x in self.RSVPList])
		print("RSVPS: " + result)
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
	result.CachedEmbed = eventEmbed
	result.HasTextChannel = False #TODO: text channel nonsense
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
			rsvpMentions = field.value.split(',')
			for rsvp in rsvpMentions:
				userForRSVP = await GetUserFromMention(rsvp, calendar.Guild)
				if(userForRSVP != None):
					result.RSVPList.append(userForRSVP)
		elif(field.name == _fieldLinks):
			link = field.value[len(_subFieldCal)+3:-1]
			if(len(link) > 10): #10 is arbitrary idk
				print("link found, is:")
				print(link)
				eventID = GoogleCalendarHelper.GetEventIDFromLink(link)
				result.GCalendarData = calendar.GCalHelper.GetEvent(eventID)
				result.GCalendarLink = result.GCalendarData["htmlLink"]


	return result

#constructor from command (when creating events from a command)
async def CreateEventFromCommand(calendar, ctx, commandText):
	result = CalendarEvent()

	result.CalendarRef = calendar #ref to containing calendar
	result.CachedEmbed = None
	result.HasTextChannel = False
	result.TextChannel = None
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
