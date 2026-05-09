from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import ScheduledCall, ScheduledCallStatus
from app.schemas import ScheduleCallRequest, ScheduledCallResponse
from app.services.phone_numbers import PhoneNumberError
from app.services.scheduler import cancel_call, schedule_call

router = APIRouter(prefix="/api/v1/calls", tags=["calls"])


@router.post("/schedule", response_model=ScheduledCallResponse, status_code=status.HTTP_201_CREATED)
def create_scheduled_call(
    payload: ScheduleCallRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ScheduledCall:
    audio_url = str(payload.audio_url) if payload.audio_url is not None else settings.twilio_static_call_audio_url
    if not audio_url:
        raise HTTPException(status_code=422, detail="TWILIO_STATIC_CALL_AUDIO_URL is required when audio_url is omitted")

    try:
        return schedule_call(db, settings, payload.to, payload.scheduled_at, audio_url=audio_url)
    except PhoneNumberError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{call_id}", response_model=ScheduledCallResponse)
def get_scheduled_call(call_id: UUID, db: Session = Depends(get_db)) -> ScheduledCall:
    call = db.get(ScheduledCall, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Scheduled call not found")
    return call


@router.post("/{call_id}/cancel", response_model=ScheduledCallResponse)
def cancel_scheduled_call(call_id: UUID, db: Session = Depends(get_db)) -> ScheduledCall:
    call = cancel_call(db, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Scheduled call not found")
    if call.status != ScheduledCallStatus.cancelled:
        raise HTTPException(status_code=409, detail=f"Call is {call.status.value} and cannot be cancelled")
    return call
