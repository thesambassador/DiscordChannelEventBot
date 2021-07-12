Discord Channel Event Bot

Super basic event bot that I'm making to more specifically address the needs/wants of our channel. Other existing event bots weren't customizable enough... so I made this.

Features:
- All events and event data is stored in messages on the channel itself. Right now there's no other databse or anything else, so if the bot goes down it should be able to re-load all the existing events without issue.
- Events are sorted in the events channel in order of start date (the next upcoming events are the furthest down), so it's easy to see stuff that's coming up
- Event summary shows a condensed view of upcoming events
- Syncs with a google calendar

User Usage:
- Create events in any channel (can't post in events)
- Create events with a loose syntax like this (a date needs to be in there!):

!event chillin with the homies at 5pm on monday

- Create events with a strict syntax like this:

!event EventTitle | EventTime | EventDescription

- Edit events by editing your original message
- Delete events by deleting your original message
- Jump back to the original message from the Events channel
- RSVP to events by clicking the Checkmark react on the event. Remove yourself by reacting with the red X.

Dependencies (from pipreq):
oauthlib==3.1.1
google_auth_oauthlib==0.4.4
discord.py==1.7.3
discord==1.7.3
google_api_python_client==2.12.0
protobuf==3.17.3
python-dotenv==0.18.0
python_dateutil==2.8.1
