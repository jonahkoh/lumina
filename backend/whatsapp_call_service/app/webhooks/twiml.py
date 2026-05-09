from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_twilio_service
from app.models import ScheduledCall
from app.services.twilio_service import TwilioService

router = APIRouter(prefix="/twiml", tags=["twiml"])


@router.post("/calls/{scheduled_call_id}")
def call_twiml(
    scheduled_call_id: UUID,
    db: Session = Depends(get_db),
    twilio: TwilioService = Depends(get_twilio_service),
) -> Response:
    call = db.get(ScheduledCall, scheduled_call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Scheduled call not found")
    return Response(content=twilio.build_play_twiml(call.audio_url), media_type="application/xml")
