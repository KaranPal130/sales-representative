import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig # For explicit config typing
from google.api_core import exceptions as google_exceptions # For error handling

from config_manager import get_gemini_api_key

logger = logging.getLogger(__name__)

class ContentBlockedError(Exception):
    """Custom exception raised when content generation is blocked by safety settings or other reasons."""
    def __init__(self, message, prompt_feedback=None):
        super().__init__(message)
        self.prompt_feedback = prompt_feedback

class GeminiClient:
    """
    Client for interacting with the Google Gemini API.
    """
    def __init__(self, model_name: str = 'gemini-pro'):
        """
        Initializes the Gemini client.

        Args:
            model_name: The name of the Gemini model to use (e.g., 'gemini-pro').
        """
        try:
            api_key = get_gemini_api_key()
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Gemini client initialized successfully with model: {model_name}")
        except ValueError as e: # From get_gemini_api_key
            logger.error(f"Configuration error during Gemini client initialization: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise

    def generate_text(
        self,
        prompt: str,
        generation_config_dict: dict = None,
        safety_settings_dict: dict = None
    ) -> str:
        """
        Generates text using the Gemini model.

        Args:
            prompt: The text prompt to send to the model.
            generation_config_dict: Optional dictionary for generation configuration
                                    (e.g., {"temperature": 0.7, "max_output_tokens": 250}).
            safety_settings_dict: Optional dictionary for safety settings
                                 (e.g., {'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_LOW_AND_ABOVE'}).

        Returns:
            The generated text as a string.

        Raises:
            ContentBlockedError: If the content generation is blocked due to safety filters
                                 or other reasons indicated by prompt_feedback.
            google_exceptions.GoogleAPIError: For underlying API errors.
            Exception: For other unexpected errors during generation.
        """
        gen_config = None
        if generation_config_dict:
            try:
                gen_config = GenerationConfig(**generation_config_dict)
            except Exception as e:
                logger.warning(f"Invalid generation_config_dict: {generation_config_dict}. Error: {e}. Proceeding without it.")
                gen_config = None


        try:
            logger.debug(f"Generating text with Gemini. Prompt: '{prompt[:50]}...', Config: {generation_config_dict}, Safety: {safety_settings_dict}")
            response = self.model.generate_content(
                prompt,
                generation_config=gen_config,
                safety_settings=safety_settings_dict
            )

            # Check for blocking based on prompt_feedback
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason_message = f"Content generation blocked. Reason: {response.prompt_feedback.block_reason.name}."
                logger.error(block_reason_message + f" Details: {response.prompt_feedback}")
                raise ContentBlockedError(block_reason_message, prompt_feedback=response.prompt_feedback)

            # Try to access response.text, which is the primary way to get simple text output
            # The SDK documentation suggests that response.text should exist if generation was successful.
            # If response.text is not available or empty, and no block reason, it's an unusual state.
            if not response.parts: # If parts are empty, text might be missing.
                # Check if there was a finish_reason that might explain empty parts without explicit blocking
                finish_reason = response.candidates[0].finish_reason if response.candidates else None
                if finish_reason != genai.types.FinishReason.STOP: # STOP is normal
                     logger.warning(f"Gemini response has empty parts and finish reason is '{finish_reason}'. Prompt: '{prompt[:50]}...'")
                # If text is also empty/None
                if not hasattr(response, 'text') or not response.text:
                    logger.warning(f"Gemini response has no text and empty parts. Prompt: '{prompt[:50]}...'. This might be due to implicit safety filtering or an issue.")
                    # Depending on strictness, could raise an error here or return empty string.
                    # For now, let's return empty string if no explicit block.
                    return ""

            return response.text

        except ContentBlockedError: # Re-raise to be caught by the caller
            raise
        except (google_exceptions.GoogleAPIError, google_exceptions.RetryError) as e:
            logger.error(f"Gemini API error during text generation: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Gemini text generation: {e}")
            raise
