import hashlib
import logging
from pathlib import Path

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


VOICE_ALIASES = {
    "english": "english_voice_id",
    "mandarin": "chinese_voice_id",
    "chinese": "chinese_voice_id",
    "cantonese": "chinese_voice_id",
    "hokkien": "chinese_voice_id",
    "indonesian": "indonesian_voice_id",
    "indonesia": "indonesian_voice_id",
    "malay": "malay_voice_id",
    "tagalog": "tagalog_voice_id",
    "tamil": "tamil_voice_id",
}

LANGUAGE_CODES = {
    "english": "en",
    "mandarin": "zh",
    "chinese": "zh",
    "cantonese": "zh",
    "hokkien": "zh",
    "indonesian": "id",
    "indonesia": "id",
    "malay": "ms",
    "tagalog": "fil",
    "tamil": "ta",
}


class AudioService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def text_to_speech(self, text: str, language: str | None) -> str | None:
        if not text:
            return None

        voice_id = self.voice_id_for_language(language)
        cache_path = self.cache_path(text, voice_id)
        if cache_path.exists():
            return self.public_url_for(cache_path)

        if not self.settings.elevenlabs_api_key:
            return None

        audio = self._generate_audio(text, voice_id, language)
        if audio is None and voice_id != self.settings.elevenlabs_fallback_voice_id:
            fallback_voice_id = self.settings.elevenlabs_fallback_voice_id
            logger.info("ElevenLabs retrying with fallback voice_id=%s", fallback_voice_id)
            voice_id = fallback_voice_id
            cache_path = self.cache_path(text, voice_id)
            if cache_path.exists():
                return self.public_url_for(cache_path)
            audio = self._generate_audio(text, voice_id, language)
        if audio is None:
            return None

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(audio)
        return self.public_url_for(cache_path)

    def voice_id_for_language(self, language: str | None) -> str:
        normalized = (language or "english").strip().lower() or "english"
        setting_name = VOICE_ALIASES.get(normalized, "english_voice_id")
        return getattr(self.settings, setting_name)

    def cache_path(self, text: str, voice_id: str) -> Path:
        digest = hashlib.sha256(f"{voice_id}\n{text}".encode("utf-8")).hexdigest()
        return self.cache_dir() / f"{digest}.mp3"

    def public_url_for(self, cache_path: Path) -> str:
        assets_dir = self.service_root() / "assets"
        relative = cache_path.relative_to(assets_dir).as_posix()
        return f"{self.settings.public_base_url.rstrip('/')}/assets/{relative}"

    def cache_dir(self) -> Path:
        configured = Path(self.settings.audio_cache_dir)
        if configured.is_absolute():
            return configured
        return self.service_root() / configured

    @staticmethod
    def service_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def _generate_audio(self, text: str, voice_id: str, language: str | None = None) -> bytes | None:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = {
            "text": text,
            "model_id": self.settings.elevenlabs_tts_model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        language_code = LANGUAGE_CODES.get((language or "english").strip().lower())
        if language_code:
            payload["language_code"] = language_code
        headers = {
            "xi-api-key": self.settings.elevenlabs_api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            logger.warning("ElevenLabs TTS generation failed: %s", exc)
            return None
