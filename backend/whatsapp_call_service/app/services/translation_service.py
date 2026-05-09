import hashlib
import logging
from collections import OrderedDict

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


LANGUAGE_MAP = {
    "burmese": "Burmese",
    "english": "English",
    "indonesia": "Indonesian",
    "indonesian": "Indonesian",
    "khmer": "Khmer",
    "lao": "Lao",
    "malay": "Malay",
    "mandarin": "Mandarin Chinese",
    "chinese": "Mandarin Chinese",
    "tagalog": "Tagalog",
    "tamil": "Tamil",
    "thai": "Thai",
    "vietnamese": "Vietnamese",
    "hokkien": "Hokkien",
    "cantonese": "Cantonese",
}


class TranslationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: OrderedDict[str, str] = OrderedDict()

    def translate(self, text: str, target_language: str | None) -> str:
        normalized_language = self.normalize_language(target_language)
        if not text or normalized_language == "english":
            return text

        key = self.cache_key(text, normalized_language)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        translated = self._translate_via_sea_lion(text, normalized_language) or text
        self._store(key, translated)
        return translated

    def translate_options(self, options: list[str], target_language: str | None) -> list[str]:
        return [self.translate(option, target_language) for option in options]

    @staticmethod
    def normalize_language(value: str | None) -> str:
        return (value or "english").strip().lower() or "english"

    @classmethod
    def cache_key(cls, text: str, target_language: str | None) -> str:
        language = cls.normalize_language(target_language)
        digest = hashlib.sha256(f"{language}\n{text}".encode("utf-8")).hexdigest()
        return f"{language}:{digest}"

    def _store(self, key: str, value: str) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self.settings.translation_cache_max_size:
            self._cache.popitem(last=False)

    def _translate_via_sea_lion(self, text: str, target_language: str) -> str | None:
        if not (
            self.settings.sea_lion_api_key
            and self.settings.sea_lion_api_url
            and self.settings.sea_lion_model_name
        ):
            return None

        language_name = LANGUAGE_MAP.get(target_language, target_language)
        payload = {
            "model": self.settings.sea_lion_model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a translation assistant. Translate the user's message to "
                        f"{language_name}. Output ONLY the translated text, no explanations, "
                        "no quotation marks."
                    ),
                },
                {"role": "user", "content": f"Translate this to {language_name}: {text}"},
            ],
            "max_completion_tokens": 1024,
            "temperature": 0.2,
        }
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.settings.sea_lion_api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(self.settings.sea_lion_api_url, headers=headers, json=payload)
                response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip() or None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("SEA-LION translation failed for %s: %s", target_language, exc)
            return None
