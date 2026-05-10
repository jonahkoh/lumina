from fastapi import Depends

from app.config import Settings, get_settings
from app.services.conversation import ConversationEngine
from app.services.twilio_service import TwilioService


def get_twilio_service(settings: Settings = Depends(get_settings)) -> TwilioService:
    return TwilioService(settings)


def get_conversation_engine(settings: Settings = Depends(get_settings)) -> ConversationEngine:
    return ConversationEngine(settings)
