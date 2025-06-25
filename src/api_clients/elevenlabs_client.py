from config_manager import get_elevenlabs_api_key
from elevenlabs.client import ElevenLabs
import logging

logger = logging.getLogger(__name__)

class ElevenLabsClient:
    """
    Client for interacting with the ElevenLabs Text-to-Speech API.
    """
    def __init__(self):
        """
        Initializes the ElevenLabs client.
        Fetches the API key and instantiates the ElevenLabs SDK client.
        """
        try:
            api_key = get_elevenlabs_api_key()
            self.client = ElevenLabs(api_key=api_key)
        except ValueError as e:
            logger.error(f"Failed to initialize ElevenLabs client: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during ElevenLabs client initialization: {e}")
            raise

    def synthesize_speech(self, text: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM") -> bytes:
        """
        Synthesizes speech from the given text using the specified voice.

        Args:
            text: The text to synthesize.
            voice_id: The ID of the voice to use for synthesis. Defaults to "Rachel".

        Returns:
            A bytes object containing the audio data.

        Raises:
            elevenlabs.api.ApiException: If the API request fails.
            Exception: For other unexpected errors.
        """
        try:
            audio_stream = self.client.text_to_speech.convert(text=text, voice_id=voice_id)
            # Concatenate audio chunks
            audio_bytes = b"".join(chunk for chunk in audio_stream)
            return audio_bytes
        except Exception as e: # The SDK might raise various errors, catch generic Exception for now
            logger.error(f"ElevenLabs API error during speech synthesis: {e}")
            # Re-raising the SDK's error or a custom one. For now, re-raise.
            raise
