from __future__ import print_function
import datetime
import os.path
import os
import base64
import urllib.parse
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from oauth2client import service_account
from oauthlib.oauth2.rfc6749.clients import base

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarHelper():
    def __init__(self, guildID) -> None:
        creds = None
        saFile = 'sa_file.json'
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            print("getting credentials from service file")
            creds = service_account.ServiceAccountCredentials.from_json_keyfile_name(saFile, SCOPES)
            print("gotem?")

            # if creds and creds.expired and creds.refresh_token:
            #     creds.refresh(Request())
            # else:
            #     flow = InstalledAppFlow.from_client_secrets_file(
            #         'credentials.json', SCOPES)
            #     creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        self.service = build('calendar', 'v3', credentials=creds)
        self.calendarID = self.GetCalendarIDForGuild(guildID)
        self.calendarActive = True
        if(self.calendarID == None):
            self.calendarActive = False
        self.timeZone = os.getenv('GOOGLE_CALENDAR_TIMEZONE', 'America/Chicago')

    def CreateEvent(self, eventName, eventDescription, startTime, endTime=None):
        if(not self.calendarActive): return
        if(endTime == None):
            endTime = startTime + datetime.timedelta(hours=1)

        event = {
            'summary': eventName,
            'description': eventDescription,
            'start': {
                'dateTime': startTime.isoformat(), 
                'timeZone' : 'America/Chicago'
            },
            'end':{
                'dateTime': endTime.isoformat(),
                'timeZone' : 'America/Chicago'
            }
        }

        newEvent = self.service.events().insert(calendarId=self.calendarID, body=event).execute()
        print("calendar event created\n" + str(newEvent))
        #print(newEvent.htmlLink)
        return newEvent

    def UpdateEvent(self, eventID, newName, newDescripion, newStart, newEnd=None):
        if(not self.calendarActive): return
        if(newEnd == None):
            endTime = newEnd + datetime.timedelta(hours=1)
        event = self.service.events().get(calendarId=self.calendarID, eventId=eventID).execute()

        event['summary'] = newName
        event['description'] = newDescripion
        event['start']['dateTime'] = newStart.isoformat()
        event['end']['dateTime'] = newEnd.isoformat()

        updated_event = self.service.events().update(calendarId=self.calendarID, eventId=event['id'], body=event).execute()
        return updated_event

    def DeleteEvent(self, eventID):
        if(not self.calendarActive): return
        self.service.events().delete(calendarId=self.calendarID, eventId=eventID).execute()
        
    def GetEvent(self, eventID):
        if(not self.calendarActive): return
        event = self.service.events().get(calendarId = self.calendarID, eventId=eventID).execute()
        return event

    def GetEventIDFromLink(linkString):
        parsedURL = urllib.parse.urlparse(linkString)
        params = urllib.parse.parse_qs(parsedURL.query)

        eid = params['eid'][0]
        print(eid)
        print(len(eid))
        
        decoded = base64.urlsafe_b64decode(eid + '=====') #the == adds padding to allow it to decode? python 3 ignores extra padding
        strDecoded = decoded.decode('ascii').split(' ')
        return strDecoded[0]

    def GetCalendarIDForGuild(self, guildID):
        filename = "GuildGoogleCalenderIDs"
        calIDLookup = open(filename, "r")

        for line in calIDLookup:
            x = line.split()
            if(len(x) != 2): continue
            
            try:
                lineGuildID = int(x[0])
                calid = x[1]
                if(lineGuildID == guildID):
                    print(f"Found {calid} for guild {lineGuildID}")
                    return calid
            except:
                continue
        calIDLookup.close()

