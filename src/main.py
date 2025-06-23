"""
This script serves as the main entry point for initiating an AI-powered sales call.

It takes a lead_id and an ngrok URL (for TwiML webhook access) as input,
loads lead data, constructs the initial TwiML URL for the call, and then uses
the TwilioClient to place an outbound call to the specified lead.

The script handles:
- Command-line argument parsing for lead_id, ngrok_url, and an optional override phone number.
- Loading lead data from data/leads.json.
- Retrieving ngrok URL from arguments, environment variable (NGROK_URL), or user input.
- Constructing the TwiML URL pointing to the /call/start endpoint of the running
  TwiML server (src/twiml_server.py), passing the lead_id.
- Initializing the TwilioClient and making the call.
- Logging key steps and errors.
"""
import argparse
import logging
import os
import sys

# Assuming this script is run from the project root, or PYTHONPATH is set.
# If running `python src/main.py` from root, these imports should work.
from src.api_clients.twilio_client import TwilioClient
from src.lead_manager import load_leads, get_lead_by_id, Lead

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

def main():
    """
    Main function to parse arguments, load data, and initiate the sales call.
    """
    parser = argparse.ArgumentParser(description="Initiate an AI-powered sales call.")
    parser.add_argument("--lead_id", required=True, help="The ID of the lead to call.")
    parser.add_argument("--ngrok_url", help="The ngrok base URL (e.g., https://xxxx.ngrok.io). Overrides NGROK_URL env var.")
    parser.add_argument(
        "--call_phone_number",
        help="The phone number to call. Overrides the phone number from the lead's data. Must be in E.164 format."
    )

    args = parser.parse_args()

    # Get Ngrok URL
    ngrok_url = args.ngrok_url
    if not ngrok_url:
        ngrok_url = os.getenv('NGROK_URL')

    if not ngrok_url:
        try:
            # Simple input prompt if not found in args or env
            print("NGROK_URL not found in arguments or environment variables.")
            ngrok_url = input("Please enter your ngrok base URL (e.g., https://xxxx.ngrok.io): ").strip()
            if not ngrok_url: # User pressed enter without typing anything
                 logging.warning("No ngrok URL provided by user.")
        except KeyboardInterrupt:
            logging.info("User cancelled input. Exiting.")
            sys.exit(0)
        except EOFError: # Handle if input stream is closed (e.g. in a script)
            logging.warning("No input received for ngrok URL (EOF). Exiting.")
            sys.exit(1)

    if not ngrok_url or not (ngrok_url.startswith('http://') or ngrok_url.startswith('https://')):
        logging.error(
            "Invalid or missing ngrok URL. It must start with 'http://' or 'https://'. "
            "Please provide it via --ngrok_url argument, NGROK_URL environment variable, or user input."
        )
        sys.exit(1)

    ngrok_url = ngrok_url.rstrip('/') # Normalize to prevent double slashes

    # Load leads
    try:
        # Assuming leads.json is in data/ relative to project root.
        # If main.py is in src/, and data/ is at root, path needs adjustment if load_leads doesn't handle it.
        # load_leads default is "data/leads.json", which assumes it's called from project root.
        # If running `python src/main.py`, current working dir is project root, so "data/leads.json" is fine.
        leads = load_leads()
        if not leads:
            logging.error("No leads found. Check 'data/leads.json' or its loading mechanism.")
            sys.exit(1)
    except FileNotFoundError:
        logging.error("Lead file 'data/leads.json' not found. Ensure it exists in the 'data' directory at the project root.")
        sys.exit(1)
    except ValueError as e: # Handles JSON decode errors from load_leads
        logging.error(f"Error parsing leads.json: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to load leads due to an unexpected error: {e}")
        sys.exit(1)

    # Get specific lead
    lead_to_call = get_lead_by_id(args.lead_id, leads)
    if not lead_to_call:
        logging.error(f"Lead with ID '{args.lead_id}' not found in the loaded leads.")
        sys.exit(1)

    # Determine target phone number
    target_phone_number = args.call_phone_number if args.call_phone_number else lead_to_call.phone_number
    if not target_phone_number:
        logging.error(f"No phone number specified for lead '{args.lead_id}' (either in lead data or via --call_phone_number).")
        sys.exit(1)

    logging.info(f"Preparing to call lead: {lead_to_call.name} (ID: {lead_to_call.id}) at {target_phone_number}")

    # Construct TwiML URL
    # The /call/start endpoint in twiml_server.py expects lead_id as a URL parameter.
    initial_twiml_url = f"{ngrok_url}/call/start?lead_id={lead_to_call.id}"
    logging.info(f"Using TwiML URL: {initial_twiml_url}")

    # Initialize TwilioClient and initiate call
    try:
        twilio_client = TwilioClient() # Assumes TWILIO_ACCOUNT_SID, AUTH_TOKEN, PHONE_NUMBER are in env or .env
        logging.info(f"Initiating call to {target_phone_number} via Twilio...")
        call_sid = twilio_client.initiate_call(
            to_phone_number=target_phone_number,
            twiml_url=initial_twiml_url
        )
        logging.info(f"Call initiated successfully. Call SID: {call_sid}")
        print(f"Call placed. SID: {call_sid}. Check Twilio console for status.")
        print(f"Ensure your TwiML server (src/twiml_server.py) is running and accessible via: {ngrok_url}")

    except ValueError as ve: # Catch config errors from TwilioClient init (e.g., missing env vars)
        logging.error(f"Configuration error for Twilio client: {ve}")
        print(f"Error: {ve}. Please ensure your Twilio environment variables (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER) are correctly set in your .env file or environment.")
        sys.exit(1)
    except Exception as e: # Catch other exceptions like TwilioRestException for invalid numbers etc.
        logging.error(f"Failed to initiate call: {e}")
        print(f"Error making call: {e}")
        sys.exit(1)

if __name__ == '__main__':
    # This allows the script to be run with `python src/main.py --lead_id ...`
    # Make sure your .env file is in the root of the project, NOT in the src/ directory.
    # The load_dotenv() in config_manager.py (called by other clients) should handle it.
    main()
