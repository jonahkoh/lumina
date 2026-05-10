from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_twilio_service
from app.models import MessageStatus, OutboundMessage
from app.schemas import MessageSendRequest, MessageSendResponse
from app.services.phone_numbers import PhoneNumberError, to_whatsapp_address
from app.services.twilio_service import TwilioService

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])


@router.post("/send", response_model=MessageSendResponse, status_code=status.HTTP_201_CREATED)
def send_message(
    payload: MessageSendRequest,
    db: Session = Depends(get_db),
    twilio: TwilioService = Depends(get_twilio_service),
) -> OutboundMessage:
    try:
        to_address = to_whatsapp_address(payload.to)
    except PhoneNumberError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    message = OutboundMessage(to_whatsapp=to_address, body=payload.body, status=MessageStatus.queued)
    db.add(message)
    db.commit()
    db.refresh(message)

    try:
        result = twilio.send_whatsapp_message(payload.to, payload.body)
        message.twilio_sid = result.sid
        message.status = MessageStatus.sent
    except Exception as exc:
        message.status = MessageStatus.failed
        message.error_message = str(exc)
    db.commit()
    db.refresh(message)
    return message
