from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models import ContactRole, MessageStatus, MobilityLevel, ScheduledCallStatus


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
    message_text: str | None = Field(default=None, min_length=1, max_length=1600)
    appointment_location: str | None = Field(default=None, min_length=1, max_length=1000)
    language: str = "english"


class ScheduledCallResponse(BaseModel):
    id: UUID
    to_phone_number: str
    scheduled_at: datetime
    audio_url: str
    message_text: str | None = None
    appointment_location: str | None = None
    language: str
    status: ScheduledCallStatus
    twilio_call_sid: str | None = None
    retry_count: int
    last_error: str | None = None

    model_config = {"from_attributes": True}


class WebhookAck(BaseModel):
    ok: bool = True


class ContactResponse(BaseModel):
    id: UUID
    phone_number: str
    whatsapp_address: str
    display_name: str | None = None
    role: ContactRole | None = None

    model_config = {"from_attributes": True}


class CaregiverProfileCreate(BaseModel):
    contact_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    phone_number: str
    preferred_language: str = "english"
    notes: str | None = None


class CaregiverProfileResponse(BaseModel):
    id: UUID
    contact_id: UUID
    name: str
    phone_number: str
    preferred_language: str
    notes: str | None = None

    model_config = {"from_attributes": True}


class ElderlyProfileCreate(BaseModel):
    contact_id: UUID | None = None
    created_by_contact_id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=255)
    phone_number: str
    pickup_address: str = Field(..., min_length=1)
    postal_code: str = Field(..., min_length=6, max_length=6)
    preferred_language: str = "english"
    mobility_level: MobilityLevel = MobilityLevel.need_transport
    notes: str | None = None


class ElderlyProfileResponse(BaseModel):
    id: UUID
    contact_id: UUID | None = None
    created_by_contact_id: UUID | None = None
    name: str
    phone_number: str
    pickup_address: str
    postal_code: str
    preferred_language: str
    mobility_level: MobilityLevel
    notes: str | None = None

    model_config = {"from_attributes": True}


class CaregiverElderlyLinkCreate(BaseModel):
    caregiver_profile_id: UUID
    elderly_profile_id: UUID
    relationship: str = Field(..., min_length=1, max_length=64)


class CaregiverElderlyLinkResponse(BaseModel):
    id: UUID
    caregiver_profile_id: UUID
    elderly_profile_id: UUID
    relationship: str

    model_config = {"from_attributes": True}


class ContactProfileResponse(BaseModel):
    contact: ContactResponse
    caregiver: CaregiverProfileResponse | None = None
    elderly: ElderlyProfileResponse | None = None
    linked_elderly: list[ElderlyProfileResponse] = Field(default_factory=list)
