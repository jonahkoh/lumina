from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_conversation_engine, get_twilio_service
from app.models import MessageStatus, OutboundMessage, ScheduledCall, ScheduledCallStatus, TwilioEvent, utcnow
from app.schemas import WebhookAck
from app.services.conversation import ConversationEngine
from app.services.twilio_service import TwilioService

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio-webhooks"])


@router.post("/whatsapp", response_model=WebhookAck)
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
    twilio: TwilioService = Depends(get_twilio_service),
    conversation: ConversationEngine = Depends(get_conversation_engine),
) -> WebhookAck:
    form = dict(await request.form())
    await _validate_twilio_request(request, form, twilio)
    _record_event(db, "whatsapp_inbound", form.get("MessageSid") or f"{form.get('From')}:{form.get('SmsMessageSid')}", form)

    from_number = form.get("From", "")
    body = form.get("Body", "")
    reply = conversation.handle_message(db, from_number, body)
    result = twilio.send_whatsapp_message(from_number, reply)
    message = OutboundMessage(to_whatsapp=from_number, body=reply, twilio_sid=result.sid, status=MessageStatus.sent)
    db.add(message)
    db.commit()
    return WebhookAck()


@router.post("/voice/status", response_model=WebhookAck)
async def voice_status_webhook(
    request: Request,
    db: Session = Depends(get_db),
    twilio: TwilioService = Depends(get_twilio_service),
) -> WebhookAck:
    form = dict(await request.form())
    await _validate_twilio_request(request, form, twilio)
    _record_event(db, "voice_status", form.get("CallSid", ""), form)

    call_sid = form.get("CallSid")
    call_status = form.get("CallStatus")
    if call_sid:
        call = db.scalar(select(ScheduledCall).where(ScheduledCall.twilio_call_sid == call_sid))
        if call is not None:
            if call_status == "completed":
                call.status = ScheduledCallStatus.completed
                call.completed_at = utcnow()
            elif call_status in {"failed", "busy", "no-answer", "canceled"}:
                call.status = ScheduledCallStatus.failed
                call.last_error = call_status
            db.commit()
    return WebhookAck()


@router.post("/message/status", response_model=WebhookAck)
async def message_status_webhook(
    request: Request,
    db: Session = Depends(get_db),
    twilio: TwilioService = Depends(get_twilio_service),
) -> WebhookAck:
    form = dict(await request.form())
    await _validate_twilio_request(request, form, twilio)
    _record_event(db, "message_status", form.get("MessageSid", ""), form)

    message_sid = form.get("MessageSid")
    status_value = form.get("MessageStatus") or form.get("SmsStatus")
    if message_sid:
        message = db.scalar(select(OutboundMessage).where(OutboundMessage.twilio_sid == message_sid))
        if message is not None:
            if status_value in MessageStatus.__members__:
                message.status = MessageStatus(status_value)
            if form.get("ErrorCode"):
                message.status = MessageStatus.failed
                message.error_code = form.get("ErrorCode")
                message.error_message = form.get("ErrorMessage")
            db.commit()
    return WebhookAck()


async def _validate_twilio_request(request: Request, form: dict, twilio: TwilioService) -> None:
    if not await twilio.validate_request(request, form):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")


def _record_event(db: Session, event_type: str, event_key: str, payload: dict) -> None:
    if not event_key:
        event_key = f"{event_type}:{utcnow().isoformat()}"
    db.add(TwilioEvent(event_type=event_type, event_key=f"{event_type}:{event_key}", payload=payload))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
