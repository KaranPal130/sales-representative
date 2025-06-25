"""
A simple Flask server to provide TwiML instructions for Twilio calls.
This server will need to be publicly accessible (e.g., via ngrok) for Twilio to reach it.
"""
import os
import uuid
import logging
import re
from flask import Flask, request, url_for, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from datetime import datetime as dt, timedelta, time
import pytz

from api_clients.elevenlabs_client import ElevenLabsClient
from api_clients.gemini_client import GeminiClient, ContentBlockedError
from api_clients.google_calendar_client import GoogleCalendarClient
from lead_manager import get_lead_by_id, Lead
from config_manager import get_company_profile, get_scheduling_parameters
from scheduling_logic import find_available_slots, format_slot_for_proposal
from conversation_manager import (
    ConversationManager,
    CALL_STATE_GREETING, CALL_STATE_QUALIFYING, CALL_STATE_PROPOSING_SLOTS,
    CALL_STATE_AWAITING_SLOT_CONFIRMATION, CALL_STATE_ATTEMPTING_BOOKING,
    CALL_STATE_ENDING, CALL_STATE_ERROR, MAX_CONVERSATION_TURNS
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# Global instance of ConversationManager
conv_manager = ConversationManager()

def _cleanup_directory_contents(directory_path):
    logging.info(f"Starting cleanup for directory: {directory_path}")
    if os.path.exists(directory_path):
        for filename in os.listdir(directory_path):
            if filename == '.gitkeep':
                logging.debug(f"Skipping '.gitkeep' file in {directory_path}")
                continue
            file_path = os.path.join(directory_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    logging.info(f"Deleted temporary file: {file_path}")
            except Exception as e:
                logging.error(f"Failed to delete {file_path}. Reason: {e}")
    else:
        logging.info(f"Directory '{directory_path}' not found, no cleanup needed.")
    logging.info(f"Cleanup process completed for directory: {directory_path}")

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'))

@app.route('/')
def home():
    logging.info("Root path '/' accessed.")
    return "TwiML Server is running!"

@app.route('/call/start', methods=['POST'])
def start_call_twiml():
    logging.info(f"Received request at /call/start. Form data: {request.form}")
    lead_id = request.values.get('lead_id')

    if not lead_id:
        logging.error("lead_id missing from request to /call/start.")
        return Response("Mandatory parameter 'lead_id' is missing.", status=400, mimetype='text/plain')

    conv_manager.initialize_conversation(lead_id)

    logging.info(f"Processing call for lead_id: {lead_id}")
    try:
        lead = get_lead_by_id(lead_id)
        profile = get_company_profile()
        if not lead or not profile:
            logging.error(f"Lead or company profile not found for lead_id {lead_id}.")
            conv_manager.set_state(lead_id, CALL_STATE_ERROR)
            return Response("Server error: Essential data missing.", status=500, mimetype='text/plain')
    except Exception as e:
        logging.error(f"Error fetching lead/profile for {lead_id}: {e}")
        conv_manager.set_state(lead_id, CALL_STATE_ERROR)
        return Response("Server error: Could not retrieve data.", status=500, mimetype='text/plain')

    greeting_text = (
        f"Hello {lead.name}. My name is Alex, and I'm calling from {profile.get('company_name', 'our company')}. "
        f"We're introducing {profile.get('product_name', 'our new product')}, {profile.get('product_description', '')}. "
        f"Is this a good time to talk briefly?"
    )
    logging.info(f"Generated greeting text for lead {lead_id}: \"{greeting_text}\"")

    try:
        eleven_labs_client = ElevenLabsClient()
        audio_bytes = eleven_labs_client.synthesize_speech(greeting_text)
        if not audio_bytes: raise ValueError("ElevenLabs returned no audio bytes.")
    except Exception as e:
        logging.error(f"ElevenLabs synthesis failed for lead {lead_id}: {e}")
        conv_manager.set_state(lead_id, CALL_STATE_ERROR)
        return Response("Server error during speech synthesis.", status=500, mimetype='text/plain')

    audio_filename = f"greeting_{lead_id}_{uuid.uuid4()}.mp3"
    temp_audio_dir = os.path.join(app.static_folder, 'temp_audio')
    if not os.path.exists(temp_audio_dir): os.makedirs(temp_audio_dir)
    audio_save_path = os.path.join(temp_audio_dir, audio_filename)

    try:
        with open(audio_save_path, 'wb') as f: f.write(audio_bytes)
        logging.info(f"Saved greeting audio for lead {lead_id} to: {audio_save_path}")
    except IOError as e:
        logging.error(f"Failed to save greeting audio for {lead_id}: {e}")
        conv_manager.set_state(lead_id, CALL_STATE_ERROR)
        return Response("Server error: Could not save audio.", status=500, mimetype='text/plain')

    response_twiml = VoiceResponse()
    try:
        audio_url = url_for('static', filename=f'temp_audio/{audio_filename}', _external=True)
    except RuntimeError as e:
        logging.error(f"url_for failed for greeting audio (SERVER_NAME?): {e}")
        conv_manager.set_state(lead_id, CALL_STATE_ERROR)
        return Response("Server config error for URL generation.", status=500, mimetype='text/plain')

    response_twiml.play(audio_url)
    gather = Gather(input='speech', action=url_for('handle_speech_input', lead_id=lead.id, _external=True), method='POST', speechTimeout='auto', timeout=5)
    response_twiml.append(gather)
    response_twiml.say("We didn't receive any input. Goodbye.")
    response_twiml.hangup()

    # Implicitly, the first response from user will move state from GREETING to QUALIFYING in handle_speech_input
    return Response(str(response_twiml), mimetype='text/xml')


@app.route('/call/handle_response', methods=['POST'])
def handle_speech_input():
    lead_id = request.values.get('lead_id')
    transcribed_text = request.values.get('SpeechResult', '').strip()

    if not lead_id:
        logging.error("Critical: lead_id missing in /call/handle_response.")
        error_response = VoiceResponse()
        error_response.say("I'm sorry, there was an issue processing your call. Goodbye.")
        error_response.hangup()
        return Response(str(error_response), mimetype='text/xml')

    current_state = conv_manager.get_current_state(lead_id)
    logging.info(f"Handling speech for lead_id: {lead_id}. Current State: {current_state}. Transcription: '{transcribed_text}'")

    if conv_manager.get_history_length(lead_id) >= MAX_CONVERSATION_TURNS:
        logging.warning(f"Max conversation turns ({MAX_CONVERSATION_TURNS}) reached for lead {lead_id}. Ending call.")
        text_for_tts = "Thank you for your time today. We've covered quite a bit. A team member will follow up if necessary. Goodbye."
        conv_manager.clear_conversation(lead_id)
        response_twiml = VoiceResponse()
        response_twiml.say(text_for_tts)
        response_twiml.hangup()
        return Response(str(response_twiml), mimetype='text/xml')

    if current_state == CALL_STATE_GREETING: # First interaction after greeting
        current_state = CALL_STATE_QUALIFYING
        conv_manager.set_state(lead_id, current_state)
        logging.info(f"Transitioned state for lead {lead_id} to: {current_state}")

    try:
        lead = get_lead_by_id(lead_id)
        company_profile = get_company_profile()
        sched_params = get_scheduling_parameters()
        if not lead or not company_profile or not sched_params or not all(k in sched_params for k in ['business_hours_start', 'business_hours_end', 'timezone']):
            logging.error(f"Essential data missing for lead {lead_id}.")
            conv_manager.set_state(lead_id, CALL_STATE_ERROR)
            # ... (error TwiML)
            error_response = VoiceResponse()
            error_response.say("Server error: Essential configuration data missing. Goodbye.")
            error_response.hangup()
            return Response(str(error_response), mimetype='text/xml')

    except Exception as e:
        logging.error(f"Error fetching data for {lead_id}: {e}")
        conv_manager.set_state(lead_id, CALL_STATE_ERROR)
        # ... (error TwiML)
        error_response = VoiceResponse()
        error_response.say("An unexpected server error occurred while fetching data. Goodbye.")
        error_response.hangup()
        return Response(str(error_response), mimetype='text/xml')

    if not transcribed_text and current_state != CALL_STATE_GREETING :
        logging.info(f"Empty transcription for lead {lead_id} in state {current_state}. Re-prompting.")
        # ... (re-prompt TwiML)
        response_twiml = VoiceResponse()
        response_twiml.say("Sorry, I didn't quite catch that.")
        gather = Gather(input='speech', action=url_for('handle_speech_input', lead_id=lead.id, _external=True), method='POST', speechTimeout='auto', timeout=5)
        gather.say("Could you please say that again?")
        response_twiml.append(gather)
        response_twiml.say("Still no input. Goodbye.")
        response_twiml.hangup()
        return Response(str(response_twiml), mimetype='text/xml')

    history_context = conv_manager.get_formatted_history_for_prompt(lead_id)
    current_state_for_prompt = conv_manager.get_current_state(lead_id) # Get potentially updated state

    prompt = (
        f"{history_context}"
        f"You are Alex, an AI sales representative for {company_profile.get('company_name', 'SalesBot AI Solutions')}. "
        f"Your product is {company_profile.get('product_name', 'AutoCaller X')}: {company_profile.get('product_description', 'it helps businesses achieve great results by automating initial outreach and scheduling qualified meetings.')}. "
        f"Key selling points include: {', '.join(company_profile.get('key_selling_points', ['saves time', 'improves qualification']))}. "
        f"Your current goal is: {company_profile.get('conversation_goal', 'to determine if the lead is a good fit for our product and to schedule a 15-minute discovery call with a senior sales representative if there is clear interest.')}. "
        f"Maintain a friendly, professional, and helpful tone. Your responses should be concise, typically 1-2 sentences, maximum 3. "
        f"You are talking to {lead.name} from {lead.company_name}. "
        f"Current conversation state: {current_state_for_prompt}.\n"
        f"The client just said: '{transcribed_text}'.\n\n"
        f"**Your Task (align with current state):**\n"
        f"Your behavior should align with the current conversation state: '{current_state_for_prompt}'.\n"
        f"If state is GREETING/QUALIFYING, focus on introduction, rapport, and understanding needs. Transition to PROPOSING_SLOTS if strong interest is shown.\n"
        f"If state is AWAITING_SLOT_CONFIRMATION, your main goal is to get a clear choice for the proposed slots or handle objections to them.\n"
        f"1. Acknowledge any specific questions or points the user made if appropriate.\n"
        f"2. If the user asks a direct question, answer concisely from provided info. If unknown, defer to a specialist for a follow-up.\n"
        f"3. Listen for objections. Address briefly if a simple counter is obvious from product info. Do not argue. Otherwise, acknowledge.\n"
        f"4. Gauge interest. Positive questions are good signs.\n"
        f"5. Steer conversation to your goal. If strong interest in a demo/meeting, or if they ask to book (and state is QUALIFYING), first confirm (e.g., 'Great, I can help with that!'), then end your response with the exact phrase `[PROPOSE_MEETING_SLOTS]`.\n"
        f"6. If the client shows clear/strong disinterest (e.g., 'not interested', 'stop calling', 'remove me from your list'), respond politely and end your response with 'GOODBYE_HANGUP'.\n"
        f"7. **Proposing Meeting Slots**: If state is `PROPOSING_SLOTS` (or if history includes 'System: I have found these available slots...'), your primary goal for this turn is to propose these exact slots to the user. Example: 'Great! I found a few times: option 0 is [slot A string], option 1 is [slot B string]. Does one of those options work for you?'. If no slots available from history, inform the user and suggest manual follow-up.\n"
        f"8. **Handling Response to Slot Proposal**: If state is `AWAITING_SLOT_CONFIRMATION` and the user responds to proposed slots, try to understand their choice. If they confirm a specific slot by its number/index or by repeating enough details, acknowledge it (e.g., 'Excellent, Tuesday at 2 PM is confirmed.'), and then include `[MEETING_CONFIRMED_SLOT_INDEX: {{{{index_0_based}}}}]` (replace `{{{{index_0_based}}}}` with the chosen numeric index). If they say none work or ask for other times, acknowledge this (e.g., 'Okay, I understand. I'll make a note for our team to find some alternative times for you.'). If ambiguous, ask for clarification.\n"
        f"9. Otherwise (if not covered by above, e.g. general chat in QUALIFYING state), continue conversation naturally. Do NOT use special keywords unless criteria are met.\n\n"
        f"Generate your response now."
    )
    logging.info(f"Full Gemini Prompt for lead {lead_id}:\n{prompt}")

    gemini_response_text = "I'm sorry, I'm having trouble thinking of a response right now. Could you try again?"
    try:
        gemini_client = GeminiClient()
        gemini_response_text = gemini_client.generate_text(prompt)
        if not gemini_response_text:
             logging.warning(f"Gemini returned empty response for {lead_id}. Using fallback.")
             gemini_response_text = "I'm not sure how to respond to that. Could you say it again?"
    except ContentBlockedError as e:
        logging.error(f"Gemini content blocked for {lead_id}: {e}")
        gemini_response_text = "I'm sorry, I can't discuss that. Is there anything else about our product I can help with? GOODBYE_HANGUP"
        conv_manager.set_state(lead_id, CALL_STATE_ENDING)
    except Exception as e:
        logging.error(f"Gemini failed for {lead_id}: {e}")
        conv_manager.set_state(lead_id, CALL_STATE_ERROR)
        response_twiml = VoiceResponse()
        response_twiml.say("I'm having trouble processing that. Please try again later. Goodbye.")
        response_twiml.hangup()
        return Response(str(response_twiml), mimetype='text/xml')

    conv_manager.add_turn_to_history(lead_id, transcribed_text, gemini_response_text)

    text_for_tts = gemini_response_text
    meeting_scheduled_successfully = False

    if "[PROPOSE_MEETING_SLOTS]" in gemini_response_text:
        text_for_tts = gemini_response_text.replace("[PROPOSE_MEETING_SLOTS]", "").strip()
        if not text_for_tts: text_for_tts = "Great! Let me check some available times for us."
        logging.info(f"Meeting proposal triggered for lead {lead_id}. Current state: {current_state_for_prompt}")
        conv_manager.set_state(lead_id, CALL_STATE_PROPOSING_SLOTS)
        try:
            gcal_client = GoogleCalendarClient()
            target_tz = pytz.timezone(sched_params['timezone'])
            start_check = dt.now(target_tz)
            end_check = start_check + timedelta(days=sched_params['days_to_check_availability'])
            busy_slots = gcal_client.get_calendar_availability( calendar_id=sched_params['calendar_id'], time_min_dt=start_check.astimezone(pytz.utc), time_max_dt=end_check.astimezone(pytz.utc) )
            available_slot_starts = find_available_slots(
                busy_slots=busy_slots, start_date=start_check, end_date=end_check,
                business_hours_start=sched_params['business_hours_start'], business_hours_end=sched_params['business_hours_end'],
                business_days=sched_params['business_days'], meeting_duration_minutes=sched_params['meeting_duration_minutes'],
                slots_to_propose=sched_params['slots_to_propose'], target_timezone_str=sched_params['timezone']
            )
            if available_slot_starts:
                detailed_slots_for_history = [{"id": i, "datetime_iso": s.isoformat(), "repr_str": format_slot_for_proposal(s, sched_params['timezone'])} for i, s in enumerate(available_slot_starts)]
                logging.info(f"Found available slots for {lead_id}: {detailed_slots_for_history}")
                conv_manager.add_system_message_to_history(lead_id, "available_slots", {"slots_details": detailed_slots_for_history})
                conv_manager.set_state(lead_id, CALL_STATE_AWAITING_SLOT_CONFIRMATION)
            else:
                logging.warning(f"No slots found for lead {lead_id}. Modifying AI response.")
                text_for_tts = "It looks like our calendar is quite full at the moment. I'll make a note for our team to reach out to you personally to find a suitable time. Thanks!"
                gemini_response_text += " GOODBYE_HANGUP"
                conv_manager.set_state(lead_id, CALL_STATE_ENDING)
        except Exception as e:
            logging.error(f"Error during slot finding for {lead_id}: {e}")
            text_for_tts = "I had an issue checking the calendar. Our team will follow up with you. Thanks."
            gemini_response_text += " GOODBYE_HANGUP"
            conv_manager.set_state(lead_id, CALL_STATE_ENDING)

    elif "[MEETING_CONFIRMED_SLOT_INDEX:" in gemini_response_text:
        conv_manager.set_state(lead_id, CALL_STATE_ATTEMPTING_BOOKING)
        confirmed_index_match = re.search(r"\[MEETING_CONFIRMED_SLOT_INDEX:(\s*\d+\s*)\]", gemini_response_text)
        if confirmed_index_match:
            try:
                confirmed_index = int(confirmed_index_match.group(1).strip())
                retrieved_slots_details = None
                # Use conv_manager to get the full history list for this lead
                full_history_list = conv_manager.get_full_history_for_lead(lead_id)
                for hist_item in reversed(full_history_list):
                    if hist_item.get("role") == "system" and hist_item.get("type") == "available_slots":
                        retrieved_slots_details = hist_item.get("slots_details")
                        break

                if retrieved_slots_details and 0 <= confirmed_index < len(retrieved_slots_details):
                    chosen_slot_detail = retrieved_slots_details[confirmed_index]
                    chosen_slot_dt = dt.fromisoformat(chosen_slot_detail['datetime_iso'])
                    meeting_duration = timedelta(minutes=sched_params['meeting_duration_minutes'])
                    end_slot_dt = chosen_slot_dt + meeting_duration
                    lead_email_str = getattr(lead, 'email', None)
                    if not lead_email_str and isinstance(lead.custom_notes, str) and '@' in lead.custom_notes:
                         email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', lead.custom_notes)
                         if email_match: lead_email_str = email_match.group(0)

                    attendees = [sched_params.get('sales_representative_email')] if sched_params.get('sales_representative_email') else []
                    if lead_email_str: attendees.append(lead_email_str)
                    else: logging.warning(f"No email found for lead {lead_id}, cannot invite to meeting.")

                    if not attendees or (len(attendees) == 1 and not lead_email_str and sched_params.get('sales_representative_email') in attendees):
                        logging.error(f"Not enough distinct attendee emails to schedule for lead {lead_id}.")
                        text_for_tts = gemini_response_text.replace(confirmed_index_match.group(0), "").strip() + " I have that time noted, but I'll need a team member to finalize the calendar invite with you as I couldn't confirm your email."
                    else:
                        gcal_client = GoogleCalendarClient()
                        event_summary = f"Sales Call: {company_profile.get('company_name', 'Our Company')} / {lead.name}"
                        event_desc = f"Scheduled sales call with {lead.name}. Lead ID: {lead_id}."
                        gcal_client.schedule_meeting(summary=event_summary, description=event_desc, start_datetime=chosen_slot_dt, end_datetime=end_slot_dt, attendees=attendees, timezone_str=sched_params['timezone'], calendar_id=sched_params['calendar_id'])
                        meeting_scheduled_successfully = True
                        text_for_tts = gemini_response_text.replace(confirmed_index_match.group(0), "").strip() + " Great! I've scheduled that for you. You should receive an invitation shortly."
                        logging.info(f"Successfully scheduled meeting for lead {lead_id} at {chosen_slot_detail['repr_str']}.")
                else:
                    logging.error(f"Invalid slot index or details not found for lead {lead_id}, index {confirmed_index}")
                    text_for_tts = "I had a slight mix-up with that confirmation. A team member will reach out to finalize."
            except ValueError:
                logging.error(f"Could not parse slot index from: {gemini_response_text}")
                text_for_tts = "There was an issue confirming that time. Let's try again or a team member can assist."
            except Exception as e:
                logging.error(f"Error scheduling GCal meeting for {lead_id}: {e}")
                text_for_tts = gemini_response_text.replace(confirmed_index_match.group(0), "").strip() + " I noted your choice, but encountered an issue sending the calendar invite. Our team will follow up to confirm everything with you."

            gemini_response_text += " GOODBYE_HANGUP"
            conv_manager.set_state(lead_id, CALL_STATE_ENDING)
        else:
            logging.error(f"Regex failed to parse index from: {gemini_response_text}")
            text_for_tts = "I couldn't quite confirm that selection. A team member will reach out."
            gemini_response_text += " GOODBYE_HANGUP"
            conv_manager.set_state(lead_id, CALL_STATE_ENDING)

    final_tts_text = text_for_tts.replace("GOODBYE_HANGUP", "").strip()
    if not final_tts_text:
        final_tts_text = "Okay. Goodbye." if "GOODBYE_HANGUP" in text_for_tts else "I'm not sure how to respond."

    try:
        eleven_labs_client = ElevenLabsClient()
        ai_audio_bytes = eleven_labs_client.synthesize_speech(final_tts_text)
        if not ai_audio_bytes: raise ValueError("ElevenLabs returned no audio bytes for AI response.")
    except Exception as e:
        logging.error(f"ElevenLabs synthesis failed for AI response (lead {lead_id}): {e}")
        response_twiml = VoiceResponse()
        response_twiml.say("I'm having trouble with my voice response. Please try again later. Goodbye.")
        response_twiml.hangup()
        return Response(str(response_twiml), mimetype='text/xml')

    ai_audio_filename = f"response_{lead_id}_{uuid.uuid4()}.mp3"
    temp_audio_dir = os.path.join(app.static_folder, 'temp_audio')
    if not os.path.exists(temp_audio_dir): os.makedirs(temp_audio_dir)
    ai_audio_save_path = os.path.join(temp_audio_dir, ai_audio_filename)

    try:
        with open(ai_audio_save_path, 'wb') as f: f.write(ai_audio_bytes)
    except IOError as e:
        logging.error(f"Failed to save AI audio for {lead_id}: {e}")
        response_twiml = VoiceResponse()
        response_twiml.say("I encountered a system issue. Goodbye.")
        response_twiml.hangup()
        return Response(str(response_twiml), mimetype='text/xml')

    response_twiml = VoiceResponse()
    try:
        ai_audio_url = url_for('static', filename=f'temp_audio/{ai_audio_filename}', _external=True)
    except RuntimeError as e:
        logging.error(f"url_for failed for AI audio (SERVER_NAME?): {e}")
        return Response("Server config error for URL gen.", status=500, mimetype='text/plain')

    response_twiml.play(ai_audio_url)

    current_state_for_saving = conv_manager.get_current_state(lead_id) # Get latest state before saving

    if "GOODBYE_HANGUP" in gemini_response_text or meeting_scheduled_successfully or current_state_for_saving == CALL_STATE_ENDING:
        logging.info(f"Call ending for lead {lead_id}. State: {current_state_for_saving}, Hangup keyword: {'GOODBYE_HANGUP' in gemini_response_text}, Scheduled: {meeting_scheduled_successfully}")
        conv_manager.clear_conversation(lead_id)
        response_twiml.hangup()
    else:
        # Ensure state is saved if it was changed (e.g. to AWAITING_SLOT_CONFIRMATION)
        # conv_manager.set_state(lead_id, current_state_for_saving) # Already done by specific set_state calls
        logging.info(f"Continuing conversation with {lead_id}. Current state: {current_state_for_saving}. Re-gathering.")
        gather = Gather(input='speech', action=url_for('handle_speech_input', lead_id=lead_id, _external=True), method='POST', speechTimeout='auto', timeout=5)
        response_twiml.append(gather)
        response_twiml.say("Sorry, I didn't catch that. Could you say it again?")
        response_twiml.hangup()

    logging.info(f"Final TwiML for {lead_id}: {str(response_twiml)}")
    return Response(str(response_twiml), mimetype='text/xml')

if __name__ == '__main__':
    logging.info("Performing pre-startup cleanup of temporary audio files...")
    temp_audio_full_path = os.path.join(app.static_folder, 'temp_audio')
    _cleanup_directory_contents(temp_audio_full_path)

    logging.info("Starting TwiML Flask server...")
    app.run(debug=True, port=5001, host='0.0.0.0')
