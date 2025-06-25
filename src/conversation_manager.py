import logging

# Define Call States
CALL_STATE_GREETING = "GREETING"
CALL_STATE_QUALIFYING = "QUALIFYING"
CALL_STATE_PROPOSING_SLOTS = "PROPOSING_SLOTS"  # When AI is about to propose based on slots found
CALL_STATE_AWAITING_SLOT_CONFIRMATION = "AWAITING_SLOT_CONFIRMATION"  # After AI has proposed slots
CALL_STATE_ATTEMPTING_BOOKING = "ATTEMPTING_BOOKING"
CALL_STATE_ENDING = "ENDING"
CALL_STATE_ERROR = "ERROR"

MAX_CONVERSATION_TURNS = 12  # Max number of user-AI back-and-forths

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self):
        self.conversation_histories = {}  # Key: lead_id, Value: {"history": [], "state": ""}
        logger.info("ConversationManager initialized.")

    def initialize_conversation(self, lead_id: str):
        self.conversation_histories[lead_id] = {
            "history": [],
            "state": CALL_STATE_GREETING,
            "retry_count": 0  # Track speech recognition retries
        }
        logger.info(f"Initialized conversation for lead_id: {lead_id} to state {CALL_STATE_GREETING}")

    def get_conversation_data(self, lead_id: str) -> dict:
        # Returns a reference to the mutable dict.
        # If not found, initializes to avoid errors in subsequent calls for this lead_id.
        if lead_id not in self.conversation_histories:
            logger.warning(f"Conversation data not found for lead_id: {lead_id}. Initializing.")
            self.initialize_conversation(lead_id)
        return self.conversation_histories[lead_id]

    def _update_conversation_data(self, lead_id: str, history: list, state: str):
        # This method assumes lead_id already exists from get_conversation_data or initialize_conversation
        if lead_id in self.conversation_histories:
            self.conversation_histories[lead_id]["history"] = history
            self.conversation_histories[lead_id]["state"] = state
        else:
            # This case should ideally not be hit if initialize_conversation is always called first.
            logger.error(f"CRITICAL: Attempted to update non-initialized conversation for {lead_id}. Initializing now.")
            self.conversation_histories[lead_id] = {"history": history, "state": state}


    def add_turn_to_history(self, lead_id: str, user_input: str, ai_response: str):
        conv_data = self.get_conversation_data(lead_id)
        history = conv_data["history"]
        history.append({"user": user_input, "ai": ai_response})
        # State doesn't change here, only history. _update_conversation_data not strictly needed if history is mutated by ref.
        # However, explicitly calling it ensures consistency if we ever change get_conversation_data to return copies.
        self._update_conversation_data(lead_id, history, conv_data["state"])
        logger.debug(f"Added turn to history for {lead_id}. History length: {len(history)}")


    def get_formatted_history_for_prompt(self, lead_id: str) -> str:
        conv_data = self.get_conversation_data(lead_id)
        history = conv_data["history"]
        history_parts = []
        for turn in history:
            if turn.get("role") == "system" and turn.get("type") == "available_slots":
                slot_options_str = ", ".join([f"{idx}: \"{s_detail['repr_str']}\"" for idx, s_detail in enumerate(turn.get('slots_details', []))])
                history_parts.append(f"System: I have found these available slots, please propose them with their index: [{slot_options_str}]")
            else:
                if "user" in turn: history_parts.append(f"User: {turn['user']}")
                if "ai" in turn: history_parts.append(f"AI: {turn['ai']}")
        return "\n".join(history_parts)

    def get_current_state(self, lead_id: str) -> str:
        return self.get_conversation_data(lead_id)["state"]

    def set_state(self, lead_id: str, state: str):
        conv_data = self.get_conversation_data(lead_id) # Ensures lead_id entry exists
        history = conv_data["history"] # Preserve history
        self._update_conversation_data(lead_id, history, state)
        logger.info(f"Set state for lead {lead_id} to {state}")

    def add_system_message_to_history(self, lead_id: str, message_type: str, data: dict):
        conv_data = self.get_conversation_data(lead_id)
        history = conv_data["history"]
        history.append({"role": "system", "type": message_type, **data})
        self._update_conversation_data(lead_id, history, conv_data["state"])
        logger.debug(f"Added system message to history for {lead_id}: type {message_type}")


    def clear_conversation(self, lead_id: str):
        if lead_id in self.conversation_histories:
            del self.conversation_histories[lead_id]
            logger.info(f"Cleared conversation history and state for lead_id: {lead_id}")
        else:
            logger.debug(f"Attempted to clear non-existent conversation for lead_id: {lead_id}")

    def get_history_length(self, lead_id: str) -> int:
        # Check if lead_id exists to avoid KeyError if get_conversation_data initializes it
        if lead_id not in self.conversation_histories:
            return 0
        return len(self.get_conversation_data(lead_id)["history"])

    def get_full_history_for_lead(self, lead_id: str) -> list:
        """Returns the list of turn dictionaries for a given lead."""
        return self.get_conversation_data(lead_id)["history"]

    def get_retry_count(self, lead_id: str) -> int:
        """Get the current retry count for speech recognition issues."""
        conv_data = self.get_conversation_data(lead_id)
        return conv_data.get("retry_count", 0)
    
    def increment_retry_count(self, lead_id: str):
        """Increment the retry count for speech recognition issues."""
        conv_data = self.get_conversation_data(lead_id)
        current_retry = conv_data.get("retry_count", 0)
        conv_data["retry_count"] = current_retry + 1
        logger.debug(f"Incremented retry count for lead {lead_id} to {conv_data['retry_count']}")
    
    def reset_retry_count(self, lead_id: str):
        """Reset retry count when speech is successfully processed."""
        conv_data = self.get_conversation_data(lead_id)
        conv_data["retry_count"] = 0
        logger.debug(f"Reset retry count for lead {lead_id}")
