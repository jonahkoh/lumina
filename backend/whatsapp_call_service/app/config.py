from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env", "backend/whatsapp_call_service/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    twilio_account_sid: str = Field(default="", validation_alias=AliasChoices("TWILIO_ACCOUNT_SID", "ACCOUNT_SID"))
    twilio_auth_token: str = Field(default="", validation_alias=AliasChoices("TWILIO_AUTH_TOKEN", "AUTH_TOKEN"))
    twilio_from_phone_number: str = Field(
        default="", validation_alias=AliasChoices("TWILIO_FROM_PHONE_NUMBER", "FROM_PHONE_NUMBER")
    )
    twilio_whatsapp_from_phone_number: str = Field(
        default="",
        validation_alias=AliasChoices("TWILIO_WHATSAPP_FROM_PHONE_NUMBER", "WHATSAPP_FROM_PHONE_NUMBER"),
    )

    database_url: str = "sqlite:///./local_whatsapp_call_service.db"
    public_base_url: str = "http://localhost:8002"
    twilio_static_call_audio_url: str = ""
    service_timezone: str = "Asia/Singapore"
    worker_poll_interval_seconds: int = 10
    call_retry_limit: int = 3
    validate_twilio_signatures: bool = True
    twilio_role_menu_content_sid: str = ""
    twilio_yes_no_content_sid: str = ""
    twilio_mobility_menu_content_sid: str = ""
    sea_lion_api_key: str = Field(default="", validation_alias=AliasChoices("SEA_LION_API_KEY", "API_KEY"))
    sea_lion_api_url: str = Field(default="", validation_alias=AliasChoices("SEA_LION_API_URL", "API_URL"))
    sea_lion_model_name: str = Field(default="", validation_alias=AliasChoices("SEA_LION_MODEL_NAME", "MODEL_NAME"))
    sea_lion_vision_model_name: str = "aisingapore/Qwen-SEA-LION-v4-8B-VL"
    healthhub_ocr_prompt: str = (
        "You are an expert OCR and data extraction assistant for Singapore healthcare apps. "
        "Extract only appointment booking details from the HealthHub screenshot into JSON: "
        "patient_name, appointment_time, appointment_location, clinic, department, doctor. "
        "Use appointment_location for the clinic, hospital, department, or address where the appointment happens. "
        "If a field is not visible, use null. Do not include NRIC or other sensitive identifiers."
    )
    translation_cache_max_size: int = 1024
    elevenlabs_api_key: str = Field(default="", validation_alias=AliasChoices("ELEVENLABS_API_KEY", "ELEVEN_API_KEY"))
    elevenlabs_tts_model_id: str = "eleven_multilingual_v2"
    elevenlabs_fallback_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    audio_cache_dir: str = "assets/audio_cache"
    english_voice_id: str = "FXMPPfJPpDj0GSwJ6ASO"
    chinese_voice_id: str = "M0TrFmFeBJS9H4xzdk8Z"
    indonesian_voice_id: str = "BSiuHWDgVlCBuGpext0k"
    malay_voice_id: str = "GRrjXNxBiQvkZ37pgMw0"
    tagalog_voice_id: str = "OPouXJLzlYeaXfgM6Q7O"
    tamil_voice_id: str = "5klqvwuBHYwcS99jLmDR"

    @property
    def whatsapp_sender_phone_number(self) -> str:
        return self.twilio_whatsapp_from_phone_number or self.twilio_from_phone_number

@lru_cache
def get_settings() -> Settings:
    return Settings()
