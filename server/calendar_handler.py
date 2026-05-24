"""
calendar_handler.py — KIRA Phase 3
Handles OAuth2 with Google Calendar API.
Provides functions to read the schedule and add events.
"""
import os
import datetime
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

log = logging.getLogger("kira-server.calendar")

# We request full access to read and write events
SCOPES = ['https://www.googleapis.com/auth/calendar']

_base_dir = Path(__file__).parent
CREDENTIALS_FILE = _base_dir / "credentials.json"
TOKEN_FILE = _base_dir / "token.json"

def get_calendar_service():
    """Authenticates the user and returns the Google Calendar API service."""
    creds = None
    # token.json stores the user's access and refresh tokens, and is created automatically
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        
    # If there are no valid credentials available, pop up the browser login.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                log.error(f"Failed to refresh token: {e}. Deleting token.json to force re-login.")
                os.remove(TOKEN_FILE)
                return get_calendar_service()
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                log.error("credentials.json not found! Cannot use Calendar API.")
                return None
            log.info("Starting OAuth flow for Google Calendar...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        log.error(f"Failed to build calendar service: {e}")
        return None

def get_schedule(max_results=5) -> str:
    """Gets the upcoming events from the primary calendar and formats them for KIRA to speak."""
    service = get_calendar_service()
    if not service:
        return "I am not connected to your Google Calendar yet."

    try:
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            return "You have no upcoming events scheduled."

        schedule = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            
            # Simplify the date string for spoken audio (e.g. "Wednesday at 03:00 PM")
            try:
                dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                time_str = dt.strftime("%A at %I:%M %p")
            except ValueError:
                time_str = start

            summary = event.get('summary', 'Untitled Event')
            schedule.append(f"{summary} on {time_str}")
            
        return "Here is your schedule: " + ". ".join(schedule) + "."
    except Exception as e:
        log.error(f"Error fetching schedule: {e}")
        return "I encountered an error while trying to read your calendar."

def add_reminder(summary: str, hours_from_now: int = 1, duration_minutes: int = 60) -> str:
    """Adds a simple reminder event to the primary calendar."""
    service = get_calendar_service()
    if not service:
        return "I am not connected to your Google Calendar yet."

    try:
        start_dt = datetime.datetime.now().astimezone() + datetime.timedelta(hours=hours_from_now)
        end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

        event = {
            'summary': summary,
            'start': {
                'dateTime': start_dt.isoformat(),
            },
            'end': {
                'dateTime': end_dt.isoformat(),
            },
        }

        service.events().insert(calendarId='primary', body=event).execute()
        log.info(f"Added calendar event: {summary}")
        return f"Successfully added {summary} to your calendar."
    except Exception as e:
        log.error(f"Error adding reminder: {e}")
        return "I encountered an error while trying to add to your calendar."
