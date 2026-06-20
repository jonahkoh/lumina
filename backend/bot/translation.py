import requests
import logging
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.environ.get("API_KEY")
API_URL = os.environ.get("API_URL")
MODEL_NAME = os.environ.get("MODEL_NAME")

# Language mapping for the translation prompt
LANGUAGE_MAP = {
    "burmese": "Burmese",
    "english": "English",
    "indonesia": "Indonesian",
    "indonesian": "Indonesian",
    "khmer": "Khmer",
    "lao": "Lao",
    "malay": "Malay",
    "mandarin": "Mandarin Chinese",
    "tagalog": "Tagalog",
    "tamil": "Tamil",
    "thai": "Thai",
    "vietnamese": "Vietnamese"
}

def translate_text_sea_lion(text: str, target_language: str) -> Optional[str]:
    """
    Translate text to the target language using SEA-LION v4 API. 
    
    Args:
        text: The text to translate (typically English)
        target_language: Language code or name (e.g., 'zh', 'yue', 'Thai')
    
    Returns:
        Translated text string, or None if translation fails
    """
    # Get full language name for the prompt
    lang_name = LANGUAGE_MAP.get(target_language.lower(), target_language)
    
    # Create the system prompt for translation
    system_prompt = f"You are a translation assistant. Translate the user's message to {lang_name}. Output ONLY the translated text, no explanations, no quotation marks."
    
    # Format the user message as a translation request
    user_message = f"Translate this to {lang_name}: {text}"
    
    headers = {
        "Accept": "text/plain",
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_completion_tokens": 1024,  # Increased from 20 to handle longer translations
        "temperature": 0.2  # Lower temperature for more consistent translations
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        # Parse the response (based on OpenAI-compatible format)
        result = response.json()
        
        # Extract the translated text from the response
        # Expected format: {"choices": [{"message": {"content": "translated text"}}]}
        if "choices" in result and len(result["choices"]) > 0:
            translated = result["choices"][0]["message"]["content"].strip()
            
            # Basic validation: ensure we got something back
            if translated and len(translated) > 0:
                return translated
            else:
                logger.warning(f"Translation returned empty content for language {target_language}")
                return None
        else:
            logger.error(f"Unexpected API response format: {result}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"Translation request timed out for language {target_language}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Translation API request failed: {e}")
        return None
    except ValueError as e:  # JSON decode error
        logger.error(f"Failed to parse API response: {e}")
        return None

def simple_translate(text: str, target_lang: str) -> str:
    """
    Simple wrapper that returns original text if translation fails.
    Useful for graceful fallback in your WhatsApp bot.
    """
    translated = translate_text_sea_lion(text, target_lang)
    return translated if translated else text

### uncommment to test this out 
# msg = "hello auntie tan! you have an appointment at jurong polyclinic tomorrow morning at 10am. there will be someone taking you to the clinic and assisting you there, so we will contact you again tomorrow to inform you when the medical escort comes."
# result = translate_text_sea_lion(msg, "Mandarin Chinese")
# print(result)