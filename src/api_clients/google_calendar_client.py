import os
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from src.config_manager import get_google_application_credentials
import logging

logger = logging.getLogger(__name__)

class GoogleCalendarClient:
    """
    Client for interacting with the Google Calendar API using service account credentials.

    To use this client:
    1.  Ensure the `GOOGLE_APPLICATION_CREDENTIALS` environment variable is set to the
        path of your service account's JSON key file.
    2.  The service account must have been granted permissions to access the target
        Google Calendar. This usually involves sharing the calendar with the service
        account's email address with appropriate permissions (e.g., "Make changes to events"
        for scheduling, "See all event details" or "See only free/busy" for availability).
    """
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self):
        """
        Initializes the Google Calendar service client.
        - Fetches the service account credentials path from `config_manager`.
        - Creates credentials using the service account file and defined SCOPES.
        - Builds the Google Calendar API service object.
        """
        try:
            credentials_path = get_google_application_credentials()
            if not os.path.exists(credentials_path):
                raise ValueError(f"Google credentials file not found at: {credentials_path}")

            creds = ServiceAccountCredentials.from_service_account_file(
                credentials_path, scopes=self.SCOPES
            )
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Google Calendar client initialized successfully.")
        except ValueError as e:
            logger.error(f"Configuration error during Google Calendar client initialization: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar client: {e}")
            raise

    def get_calendar_availability(
        self,
        calendar_id: str = 'primary',
        time_min_dt: datetime = None,
        time_max_dt: datetime = None
    ) -> list:
        """
        Fetches the busy time slots from a specified Google Calendar within a given time range.

        Args:
            calendar_id: The ID of the calendar to check. Defaults to 'primary'.
            time_min_dt: The start of the time range (datetime object). Defaults to now (UTC).
            time_max_dt: The end of the time range (datetime object). Defaults to 7 days from now (UTC).

        Returns:
            A list of busy slots, where each slot is a dictionary {'start': iso_time_str, 'end': iso_time_str}.
            Returns an empty list if no busy times are found or if the calendar has no information.

        Raises:
            googleapiclient.errors.HttpError: If the API request fails.
        """
        if time_min_dt is None:
            time_min_dt = datetime.now(timezone.utc)
        if time_max_dt is None:
            time_max_dt = time_min_dt + timedelta(days=7)

        # Ensure datetime objects are timezone-aware (UTC for consistency)
        if time_min_dt.tzinfo is None:
            time_min_dt = time_min_dt.replace(tzinfo=timezone.utc)
        if time_max_dt.tzinfo is None:
            time_max_dt = time_max_dt.replace(tzinfo=timezone.utc)

        time_min_iso = time_min_dt.isoformat()
        time_max_iso = time_max_dt.isoformat()

        freebusy_query_body = {
            "timeMin": time_min_iso,
            "timeMax": time_max_iso,
            "timeZone": "UTC",
            "items": [{"id": calendar_id}]
        }

        try:
            logger.debug(f"Querying freeBusy for calendar '{calendar_id}' from {time_min_iso} to {time_max_iso}")
            freebusy_result = self.service.freebusy().query(body=freebusy_query_body).execute()

            calendar_busy_times = freebusy_result.get('calendars', {}).get(calendar_id, {}).get('busy', [])
            logger.info(f"Found {len(calendar_busy_times)} busy slots for calendar '{calendar_id}'.")
            return calendar_busy_times
        except Exception as e: # Catches HttpError and other potential errors
            logger.error(f"Error fetching free/busy for calendar '{calendar_id}': {e}")
            raise

    def schedule_meeting(
        self,
        summary: str,
        start_datetime: datetime,
        end_datetime: datetime,
        attendees: list[str],
        description: str = None,
        calendar_id: str = 'primary',
        timezone_str: str = 'UTC' # Renamed from timezone to avoid conflict with datetime.timezone
    ) -> dict:
        """
        Schedules a meeting (creates an event) in the specified Google Calendar.

        Args:
            summary: The title of the event.
            start_datetime: The start time of the event (datetime object).
            end_datetime: The end time of the event (datetime object).
            attendees: A list of email addresses of attendees.
            description: A description of the event (optional).
            calendar_id: The ID of the calendar to create the event in. Defaults to 'primary'.
            timezone_str: The timezone for the event start and end times (e.g., 'America/New_York'). Defaults to 'UTC'.

        Returns:
            A dictionary representing the created event.

        Raises:
            googleapiclient.errors.HttpError: If the API request fails.
        """
        # Ensure datetime objects are timezone-aware if not already
        if start_datetime.tzinfo is None:
            start_datetime = start_datetime.replace(tzinfo=timezone.utc) # Default to UTC if naive
        if end_datetime.tzinfo is None:
            end_datetime = end_datetime.replace(tzinfo=timezone.utc) # Default to UTC if naive

        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_datetime.isoformat(), 'timeZone': timezone_str},
            'end': {'dateTime': end_datetime.isoformat(), 'timeZone': timezone_str},
            'attendees': [{'email': email} for email in attendees],
            'reminders': {'useDefault': True}, # Default reminders
        }

        try:
            logger.info(f"Scheduling meeting '{summary}' in calendar '{calendar_id}' from {start_datetime} to {end_datetime}")
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event,
                sendUpdates='all' # Notify attendees
            ).execute()
            logger.info(f"Meeting '{summary}' scheduled successfully. Event ID: {created_event.get('id')}")
            return created_event
        except Exception as e: # Catches HttpError and other potential errors
            logger.error(f"Error scheduling meeting '{summary}' in calendar '{calendar_id}': {e}")
            raise
