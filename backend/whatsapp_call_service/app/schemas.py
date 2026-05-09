from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models import MessageStatus, ScheduledCallStatus


class MessageSendRequest(BaseModel):
    to: str = Field(..., examples=["+15551234567", "whatsapp:+15551234567"])
    body: str = Field(..., min_length=1, max_length=1600)


class MessageSendResponse(BaseModel):
    id: UUID
    to: str
    body: str
    status: MessageStatus
    twilio_sid: str | None = None


class ScheduleCallRequest(BaseModel):
    to: str = Field(..., examples=["+15551234567"])
    scheduled_at: datetime
    audio_url: HttpUrl | None = None


class ScheduledCallResponse(BaseModel):
    id: UUID
    to_phone_number: str
    scheduled_at: datetime
    audio_url: str
    status: ScheduledCallStatus
    twilio_call_sid: str | None = None
    retry_count: int
    last_error: str | None = None

    model_config = {"from_attributes": True}


class WebhookAck(BaseModel):
    ok: bool = True
