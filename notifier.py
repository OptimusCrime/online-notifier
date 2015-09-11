#!/usr/bin/env python
# -*- coding: utf-8 -*-

from config import *

import json
import sys
import time
import urllib2

from daemon import runner
from datetime import date, datetime
from twilio.rest import TwilioRestClient

# Storing all the events
STORAGE = []

# Limit for sending SMS
SMS_TIMEOUT = 60 * 60

# Fix utf8
reload(sys)
sys.setdefaultencoding('utf8')

class Event():
    
    def __init__(self):
        # Information attributes from the API
        self.id = None
        self.title = None
        self.url = None
        self.date = None
        self.type = None
        self.reg_open = None
        
        # Other attributes
        self.notified = False


class Notifier():
    
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path =  '/tmp/notifier.pid'
        self.pidfile_timeout = 5
    
    
    def fetch_data(self):
        # Get the current date for the api call
        now_date = str(date.today().year) + '-' + (str(date.today().month) if date.today().month > 9 else ('0' + str(date.today().month))) + '-' + (str(date.today().day) if date.today().day > 9 else ('0' + str(date.today().day)))
        
        # Get the content from the api
        api_stream = urllib2.urlopen('https://online.ntnu.no/api/v0/events/?event_end__gte=' + now_date + '&order_by=event_start&limit=99&format=json');
        api_response = api_stream.read();
        api_parsed = json.loads(api_response)

        # Loop all events
        for api_event in api_parsed['events']:
            # Check if event has signup
            if 'attendance_event' in api_event and api_event['attendance_event'] is not None:
                # Check if this event has already been added to the storage
                new_event = None
                for cached_event in STORAGE:
                    # Match on id
                    if cached_event.id == api_event['id']:
                        # This event exists, just use the old object
                        new_event = cached_event
                        break
                
                # Check if we should initialize a new Event object
                if new_event is None:
                    new_event = Event()
                
                # Update/Set the various data
                new_event.id = api_event['id']
                new_event.title = api_event['title']
                new_event.url = api_event['absolute_url']
                new_event.date = api_event['event_start']
                new_event.type = api_event['event_type']
                new_event.reg_open = api_event['attendance_event']['registration_start']
                
                # Add to storage list if not already present
                if new_event not in STORAGE:
                    STORAGE.append(new_event)
    
    
    def check_status(self):
        # Loop all the events stored
        for event in STORAGE:
            # Only evaluate events that are not yet notified
            if event.notified is False:
                # Parse to datetime (hello ugly hax)
                reg_open_split = event.reg_open.split('T')
                reg_open_date = map(int, reg_open_split[0].split('-'))
                reg_open_time = map(int, reg_open_split[1].split(':'))
                reg_open_datetime = datetime(reg_open_date[0], reg_open_date[1], reg_open_date[2], reg_open_time[0], reg_open_time[1], reg_open_time[2])
                
                # Check if in past
                if reg_open_datetime > datetime.now():
                    # Get the number of seconds until the registration opens
                    seconds_until_open = (reg_open_datetime - datetime.now()).total_seconds()
                    
                    if seconds_until_open <= SMS_TIMEOUT:
                        self.notify(event)
    
    
    def notify(self, event):
        # New instance of Twilio Rest Client
        client = TwilioRestClient(account=ACCOUNT_SID, token=ACCOUNT_TOKEN)
        
        # Send the SMS
        client.messages.create(
            body='Påmelding til ' + event.title + ' åpner om en time!',
            to=NUMBER_TO,
            from_=NUMBER_FROM,
        )
        
        # Set the event to notified to avoid multiple messages
        event.notified = True
        
        # Kill instance of Twilio
        del client
    
    
    def run(self):
        # Do this as long as the daemon is running
        while True:
            # Fetch the data from the API
            self.fetch_data()
            
            # Check if we should send any notifications this iteration
            self.check_status()

            # Daemon timeout
            time.sleep(60)


# Run the daemon
notifier = Notifier()
daemon_runner = runner.DaemonRunner(notifier)
daemon_runner.do_action()