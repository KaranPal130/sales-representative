# AI-Powered Cold Calling Sales Representative

This project is an AI-powered cold-calling sales representative designed to autonomously contact leads, engage in intelligent conversations, and schedule meetings. It leverages cutting-edge AI and communication technologies to streamline the initial sales outreach process.

## Core Technologies

*   **Python 3.9+**
*   **Language Model (NLU & Conversation):** Google Gemini API
*   **Voice Synthesis (TTS):** ElevenLabs API
*   **Telephony & Call Handling:** Twilio API
*   **Meeting Scheduling:** Google Calendar API

## Planned Features

*   Autonomous outbound calling to a list of leads.
*   Real-time transcription of call audio.
*   Natural and persuasive conversation flow driven by Gemini.
*   Dynamic adaptation to conversation context and lead profile.
*   Entity extraction (objections, interest level, decision-maker status).
*   Automated meeting scheduling with proposed slots from a pre-defined calendar.
*   Integration with Google Calendar for sending invites.

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your_repository_url> # Replace with your actual repository URL
cd <your_repository_directory> # Replace with your actual directory name
```

### 2. Create a Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

### 3. Install Dependencies

Ensure your virtual environment is activated, then run:
```bash
pip install -r requirements.txt
```

### 4. Configure API Keys and Settings

This project requires API keys and credentials for several services. Configuration is handled via environment variables, which can be conveniently managed using a `.env` file for local development.

1.  **Copy the Example Configuration:**
    Copy the example environment file `config/example.env` to a new file named `.env` in the project root:
    ```bash
    cp config/example.env .env
    ```
    **Important:** The `.env` file contains sensitive credentials and is included in `.gitignore` to prevent accidental commits. Do **not** commit your actual `.env` file.

2.  **Edit `.env` and fill in your credentials:**

    *   **`ELEVENLABS_API_KEY`**: Your API key for ElevenLabs. Get this from your [ElevenLabs account](https://elevenlabs.io/).
    *   **`TWILIO_ACCOUNT_SID`**: Your Twilio Account SID. Found on your [Twilio Console dashboard](https://www.twilio.com/console).
    *   **`TWILIO_AUTH_TOKEN`**: Your Twilio Auth Token. Also on your [Twilio Console dashboard](https://www.twilio.com/console).
    *   **`TWILIO_PHONE_NUMBER`**: A Twilio phone number you own, in E.164 format (e.g., +1234567890). This number will be used to make outbound calls.
    *   **`GEMINI_API_KEY`**: Your API key for the Gemini API. Get this from [Google AI Studio](https://aistudio.google.com/app/apikey).
    *   **`GOOGLE_APPLICATION_CREDENTIALS`**: The **absolute path** to your Google Cloud service account JSON key file.
        *   **Setup for Google Calendar API:**
            1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
            2.  Create a new project or select an existing one.
            3.  Enable the "Google Calendar API" for your project (search for it in the API library).
            4.  Create a service account:
                *   Go to "IAM & Admin" > "Service Accounts".
                *   Click "Create Service Account".
                *   Give it a name (e.g., "calendar-automation-sa") and an optional description.
                *   Click "Create and Continue". You can skip granting specific roles to the service account here if you prefer to manage access by sharing the calendar directly.
                *   Click "Continue".
                *   Click "Done".
            5.  Create a key for the service account:
                *   Find your newly created service account in the list.
                *   Click on the three dots (Actions) next to it and select "Manage keys".
                *   Click "Add Key" > "Create new key".
                *   Choose "JSON" as the key type and click "Create". A JSON file will be downloaded to your computer.
            6.  **Store this JSON file securely** on your system (e.g., in a directory like `~/.config/gcloud/` or another location **outside** your project repository).
            7.  Set the `GOOGLE_APPLICATION_CREDENTIALS` variable in your `.env` file to the **absolute path** of this downloaded JSON file (e.g., `/Users/yourname/.config/gcloud/your-project-id-xxxxxxxxxxxx.json`).
            8.  **Share your Google Calendar(s):** The Google Calendar(s) that will be used for scheduling (e.g., the sales team's calendar) must be shared with the service account's email address (which you can find in the service account's details page in the Google Cloud Console). Grant it "Make changes to events" permission (or "See all event details" if only checking availability is needed by this account).

### 5. ngrok (for Local Development with Twilio)

To allow Twilio's servers to communicate with your local TwiML server during development, you'll need a tunneling service like [ngrok](https://ngrok.com/download).
Download and install ngrok, and make sure you can run it from your command line. You may also need to sign up for an ngrok account to enable longer-lived tunnel URLs or custom subdomains.

## Running the Application

Follow these steps to run the AI Cold Calling Sales Representative:

### 1. Start the TwiML Web Server

This server handles requests from Twilio, generates dynamic voice responses using AI, and manages the call flow.

Open a terminal, navigate to the project root, and run:
```bash
python src/twiml_server.py
```
You should see output indicating the server is running, typically on `http://0.0.0.0:5001/`. This server listens for incoming HTTP requests from Twilio.
The server will also clean up any temporary audio files from previous sessions in `static/temp_audio/` upon startup.

### 2. Expose Your Local Server with ngrok

Twilio needs a publicly accessible URL to send requests to your TwiML server. `ngrok` creates a secure tunnel to your local machine.

Open another terminal and run:
```bash
ngrok http 5001
```
(Replace `5001` if you changed the port in `src/twiml_server.py`).

`ngrok` will display a session status with "Forwarding" URLs. Copy the `https` URL (e.g., `https://xxxx-yyy-zzz.ngrok-free.app`). This is your public base URL.

**Tip:** For more stable testing, consider using a fixed ngrok domain (requires an ngrok account).

### 3. Configure Environment Variables (if not already done)

Ensure your `.env` file in the project root is correctly populated with all necessary API keys and your Twilio phone number as described in the "Setup Instructions".

You can optionally set the `NGROK_URL` environment variable to your ngrok forwarding URL from Step 2 to avoid typing it when running `main.py`.
Example (in your shell, or add to `.env` - though `main.py` doesn't auto-load it from `.env` for this specific var):
```bash
export NGROK_URL="https://your-ngrok-forwarding-url"
```

### 4. Initiate an Outbound Call

This script triggers an outbound call to a specified lead.

Open a new terminal, navigate to the project root, and run `src/main.py` with the required arguments:

```bash
python src/main.py --lead_id <LEAD_ID_FROM_LEADS.JSON> [--ngrok_url <YOUR_NGROK_URL>] [--call_phone_number <E.164_PHONE_NUMBER>]
```

**Arguments:**
*   `--lead_id` (Required): The ID of the lead to call (e.g., `lead_001` from `data/leads.json`).
*   `--ngrok_url` (Optional): Your public ngrok forwarding URL (e.g., `https://xxxx-yyy-zzz.ngrok-free.app`). If not provided here or as an `NGROK_URL` environment variable, the script will prompt you for it.
*   `--call_phone_number` (Optional): The phone number to call, in E.164 format (e.g., `+15551234567`). If not provided, the script will use the phone number associated with the `lead_id` from `data/leads.json`.

**Example:**
```bash
python src/main.py --lead_id lead_001 --ngrok_url https://your-ngrok-url.ngrok-free.app
```
Or, if `NGROK_URL` environment variable is set:
```bash
python src/main.py --lead_id lead_001
```

### Expected Behavior

*   The phone number associated with the lead (or the one you provided) will receive a call.
*   Upon answering, you should hear the AI's synthesized greeting.
*   You can speak, and the AI should respond based on your input.
*   Check the console output from `src/twiml_server.py` to see logs of incoming requests, transcriptions, AI responses, and generated TwiML.
*   Check the console output from `src/main.py` for call initiation status.

### Troubleshooting Tips
*   **No Call/Call Fails**:
    *   Verify your Twilio Account SID, Auth Token, and Phone Number in `.env`.
    *   Ensure your Twilio number is voice-enabled and has funds if it's a trial account.
    *   Check the Twilio Debugger logs in your Twilio console for errors related to the call.
    *   Confirm the `ngrok_url` is correct and the tunnel is active.
    *   Ensure `twiml_server.py` is running and accessible.
*   **Audio Issues/No AI Response**:
    *   Check ElevenLabs API key and Gemini API key in `.env`.
    *   Look for errors in the `twiml_server.py` console output, which might indicate issues with API calls to ElevenLabs/Gemini or file operations.
    *   Ensure the `static/temp_audio/` directory is writable by the server process.

## Project Structure

*   `src/`: Contains the core application logic.
    *   `api_clients/`: Modules for interacting with external APIs (ElevenLabs, Twilio, Google Calendar, Gemini).
    *   `conversation/`: (Planned) Logic for managing conversation flow.
    *   `scheduling/`: (Planned) Logic for handling meeting availability and booking.
    *   `main.py`: (Planned) The main entry point to run the application.
    *   `config_manager.py`: Handles loading of configuration and API keys.
*   `config/`: Configuration files and templates.
    *   `example.env`: Template for environment variables.
*   `tests/`: Unit and integration tests.
*   `requirements.txt`: Python package dependencies.
*   `.gitignore`: Specifies intentionally untracked files that Git should ignore.
*   `README.md`: This file.
```
