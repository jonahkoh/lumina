from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/whatsapp_call_service/.env"),
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

    database_url: str = "postgresql+psycopg://lumina:lumina@postgres:5432/whatsapp_call_service"
    public_base_url: str = "http://localhost:8001"
    twilio_static_call_audio_url: str = ""
    service_timezone: str = "Asia/Singapore"
    worker_poll_interval_seconds: int = 10
    call_retry_limit: int = 3
    validate_twilio_signatures: bool = True

    @property
    def whatsapp_sender_phone_number(self) -> str:
        return self.twilio_whatsapp_from_phone_number or self.twilio_from_phone_number

@lru_cache
def get_settings() -> Settings:
    return Settings()
