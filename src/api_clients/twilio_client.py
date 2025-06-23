from twilio.rest import Client
from src.config_manager import get_twilio_account_sid, get_twilio_auth_token, get_twilio_phone_number
import logging

logger = logging.getLogger(__name__)

class TwilioClient:
    """
    Client for interacting with the Twilio API to make calls.
    """
    def __init__(self):
        """
        Initializes the Twilio client.
        Fetches Twilio credentials and phone number from config_manager
        and instantiates the Twilio SDK client.
        """
        try:
            account_sid = get_twilio_account_sid()
            auth_token = get_twilio_auth_token()
            self.twilio_phone_number = get_twilio_phone_number()
            self.client = Client(account_sid, auth_token)
        except ValueError as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during Twilio client initialization: {e}")
            raise

    def initiate_call(self, to_phone_number: str, twiml_url: str) -> str:
        """
        Initiates a call to the given phone number using the specified TwiML URL.

        Args:
            to_phone_number: The phone number to call.
            twiml_url: The URL that provides TwiML instructions for the call.

        Returns:
            The SID of the initiated call.

        Raises:
            TwilioRestException: If the Twilio API call fails (e.g., invalid number).
            Exception: For other unexpected errors.
        """
        try:
            call = self.client.calls.create(
                to=to_phone_number,
                from_=self.twilio_phone_number,
                url=twiml_url
            )
            logger.info(f"Call initiated to {to_phone_number}, SID: {call.sid}")
            return call.sid
        except Exception as e: # Catches TwilioRestException and other potential errors
            logger.error(f"Failed to initiate call to {to_phone_number}: {e}")
            raise
