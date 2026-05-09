from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ScheduledCall, ScheduledCallStatus, utcnow
from app.services.audio_service import AudioService
from app.services.phone_numbers import normalize_e164
from app.services.translation_service import TranslationService
from app.services.twilio_service import TwilioService


def schedule_call(
    db: Session,
    settings: Settings,
    to: str,
    scheduled_at: datetime,
    audio_url: str | None = None,
    requested_by_whatsapp: str | None = None,
    message_text: str | None = None,
    appointment_location: str | None = None,
    language: str = "english",
) -> ScheduledCall:
    call = ScheduledCall(
        to_phone_number=normalize_e164(to),
        requested_by_whatsapp=requested_by_whatsapp,
        scheduled_at=_as_utc(scheduled_at),
        audio_url=audio_url or settings.twilio_static_call_audio_url,
        message_text=message_text,
        appointment_location=appointment_location,
        language=(language or "english").strip().lower() or "english",
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def get_due_calls(db: Session, now: datetime | None = None, limit: int = 50) -> list[ScheduledCall]:
    due_at = now or utcnow()
    statement = (
        select(ScheduledCall)
        .where(ScheduledCall.status == ScheduledCallStatus.pending)
        .where(ScheduledCall.scheduled_at <= due_at)
        .order_by(ScheduledCall.scheduled_at.asc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def cancel_call(db: Session, call_id: UUID) -> ScheduledCall | None:
    call = db.get(ScheduledCall, call_id)
    if call is None:
        return None
    if call.status == ScheduledCallStatus.pending:
        call.status = ScheduledCallStatus.cancelled
        call.cancelled_at = utcnow()
        db.commit()
        db.refresh(call)
    return call


def execute_due_call(
    db: Session,
    settings: Settings,
    twilio: TwilioService,
    call: ScheduledCall,
    translation: TranslationService | None = None,
    audio: AudioService | None = None,
) -> None:
    try:
        call.status = ScheduledCallStatus.in_progress
        db.commit()
        _prepare_call_audio(settings, call, translation, audio)
        db.commit()
        result = twilio.create_outbound_call(call.to_phone_number, str(call.id))
        call.twilio_call_sid = result.sid
        db.commit()
    except Exception as exc:  # pragma: no cover - guarded by worker tests with fake Twilio
        call.retry_count += 1
        call.last_error = str(exc)
        call.status = (
            ScheduledCallStatus.failed
            if call.retry_count >= settings.call_retry_limit
            else ScheduledCallStatus.pending
        )
        db.commit()


def _prepare_call_audio(
    settings: Settings,
    call: ScheduledCall,
    translation: TranslationService | None = None,
    audio: AudioService | None = None,
) -> None:
    if not call.message_text:
        return

    translation_service = translation or TranslationService(settings)
    audio_service = audio or AudioService(settings)
    localized_text = translation_service.translate(call.message_text, call.language)
    generated_url = audio_service.text_to_speech(localized_text, call.language)
    if generated_url:
        call.audio_url = generated_url


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
