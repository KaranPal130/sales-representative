import os
from dotenv import load_dotenv
from datetime import datetime # Ensure datetime is imported

load_dotenv() # Load .env file if it exists

def get_elevenlabs_api_key():
    """Retrieves the ElevenLabs API key from environment variables."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY environment variable not set.")
    return api_key

import json # Added
import logging # Added, if not already present for other tests

logger = logging.getLogger(__name__) # Added, if not already present

# Determine the absolute path to the project root more robustly
# __file__ is the path to config_manager.py (e.g. /app/src/config_manager.py)
# os.path.dirname(__file__) is /app/src/
# os.path.dirname(os.path.dirname(__file__)) is /app/ (project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_company_profile(filepath: str = "config/company_profile.json") -> dict:
    """
    Loads the company profile from a JSON file.

    Args:
        filepath: The path to the JSON file containing the company profile,
                  relative to the project root.

    Returns:
        A dictionary containing the company profile data.

    Raises:
        FileNotFoundError: If the specified filepath does not exist.
        ValueError: If the JSON data is malformed.
    """
    absolute_filepath = os.path.join(PROJECT_ROOT, filepath)
    logger.debug(f"Attempting to load company profile from: {absolute_filepath}")
    try:
        with open(absolute_filepath, 'r') as f:
            profile_data = json.load(f)
        logger.info(f"Company profile loaded successfully from {absolute_filepath}")
        return profile_data
    except FileNotFoundError:
        logger.error(f"Company profile file not found: {absolute_filepath}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {absolute_filepath}: {e}")
        raise ValueError(f"Invalid JSON format in {absolute_filepath}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading company profile from {absolute_filepath}: {e}")
        raise

if __name__ == '__main__':
    # Example of how to test the functions (requires .env file or environment variables to be set)
    logging.basicConfig(level=logging.DEBUG) # Use DEBUG to see file path logs

    print("--- Testing API Key Getters ---")
    try:
        print(f"ElevenLabs API Key: {get_elevenlabs_api_key()}")
    except ValueError as e:
        print(e)
    try:
        print(f"Twilio Account SID: {get_twilio_account_sid()}")
    except ValueError as e:
        print(e)
    # Add other getters here if needed for quick testing

    print("\n--- Testing Company Profile Loader ---")
    try:
        company_profile = get_company_profile()
        if company_profile:
            print(f"Company Name from profile: {company_profile.get('company_name')}")
            print(f"Product Name from profile: {company_profile.get('product_name')}")
        else:
            print("Company profile was not loaded (None or empty).")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading company profile: {e}")
    except Exception as e: # Catch-all for other unexpected errors during testing
        print(f"An unexpected error occurred during company profile test: {e}")

    print("\n--- Testing Scheduling Parameters Loader ---")
    try:
        scheduling_params = get_scheduling_parameters()
        if scheduling_params:
            print(f"Calendar ID from scheduling_params: {scheduling_params.get('calendar_id')}")
            print(f"Meeting duration: {scheduling_params.get('meeting_duration_minutes')} minutes")
            print(f"Timezone: {scheduling_params.get('timezone')}")
        else:
            print("Scheduling parameters were not loaded or are empty.")
    except Exception as e:
        print(f"Error loading scheduling parameters: {e}")


def get_scheduling_parameters() -> dict:
    """
    Retrieves scheduling parameters from the company profile.

    Returns:
        A dictionary containing scheduling parameters. Returns an empty dict
        if parameters are not found or are invalid.
    """
    profile = get_company_profile() # This already handles file loading errors
    params = profile.get("scheduling_parameters")
    if not params or not isinstance(params, dict):
        logger.error("Scheduling parameters not found or not in correct dict format in company_profile.json")
        return {}

    # Convert time strings to datetime.time objects
    time_format = '%H:%M'
    try:
        if 'business_hours_start' in params:
            params['business_hours_start'] = datetime.strptime(params['business_hours_start'], time_format).time()
        if 'business_hours_end' in params:
            params['business_hours_end'] = datetime.strptime(params['business_hours_end'], time_format).time()
    except (ValueError, TypeError) as e:
        logger.error(f"Error converting business hours to time objects: {e}. Check format in company_profile.json.")
        # Decide how to handle: return partially processed, return {}, or raise.
        # For now, let's return what we have, but log the error. User should validate.
        # Or, to be safer, return {} if essential time conversions fail:
        # return {}

    # Basic validation example (can be expanded)
    required_keys = ["calendar_id", "meeting_duration_minutes", "timezone", "business_hours_start", "business_hours_end"]
    missing_keys = [key for key in required_keys if key not in params]
    if missing_keys:
        logger.error(f"Missing essential scheduling parameters: {', '.join(missing_keys)}")
        # Depending on strictness, could return {} or raise error.
        # For now, returning potentially incomplete params if some essentials are missing.
        # Or, return {} :
        # return {}

    logger.debug(f"Scheduling parameters loaded: {params}")
    return params

def get_twilio_account_sid():
    """Retrieves the Twilio Account SID from environment variables."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    if not account_sid:
        raise ValueError("TWILIO_ACCOUNT_SID environment variable not set.")
    return account_sid

def get_twilio_auth_token():
    """Retrieves the Twilio Auth Token from environment variables."""
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not auth_token:
        raise ValueError("TWILIO_AUTH_TOKEN environment variable not set.")
    return auth_token

def get_twilio_phone_number():
    """Retrieves the Twilio Phone Number from environment variables."""
    phone_number = os.getenv("TWILIO_PHONE_NUMBER")
    if not phone_number:
        raise ValueError("TWILIO_PHONE_NUMBER environment variable not set.")
    return phone_number

def get_google_application_credentials():
    """Retrieves the Google Application Credentials path from environment variables."""
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
    return credentials_path

def get_google_api_key():
    """Retrieves the Google API key from environment variables."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    return api_key

def get_gemini_api_key():
    """Retrieves the Gemini API key from environment variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    return api_key

# Ensure logger is available if this is the first time it's used in this file.
# This might be redundant if already defined above.
if 'logger' not in globals():
    logger = logging.getLogger(__name__)
