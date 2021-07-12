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
from oauthlib.oauth2.rfc6749.clients import base

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarHelper():
    def __init__(self) -> None:
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        self.service = build('calendar', 'v3', credentials=creds)
        self.calendarID = os.getenv('GOOGLE_CALENDAR_ID')
        self.timeZone = os.getenv('GOOGLE_CALENDAR_TIMEZONE', 'America/Chicago')

    def CreateEvent(self, eventName, eventDescription, startTime, endTime=None):
        
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
        self.service.events().delete(calendarId=self.calendarID, eventId=eventID).execute()
        
    def GetEvent(self, eventID):
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