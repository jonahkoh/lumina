import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_conversation_engine, get_twilio_service
from app.models import MessageStatus, OutboundMessage, ScheduledCall, ScheduledCallStatus, TwilioEvent, utcnow
from app.schemas import WebhookAck
from app.services.conversation import ConversationEngine, is_reset_command
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
    body = _normalized_inbound_body(form)
    reply = conversation.handle_message(
        db,
        from_number,
        body,
        media_url=form.get("MediaUrl0"),
        button_text=form.get("ButtonText"),
        button_payload=form.get("ButtonPayload") or form.get("Payload"),
    )
    for pre_message in reply.pre_messages:
        _send_whatsapp_reply(db, twilio, from_number, pre_message)
    if reply.pre_messages:
        await asyncio.sleep(1)
    _send_whatsapp_reply(
        db,
        twilio,
        from_number,
        reply.body,
        content_sid=reply.content_sid,
        content_variables=reply.content_variables,
    )
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
    _record_event(db, "voice_status", _voice_status_event_key(form), form)

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
                details = [call_status]
                if form.get("SipResponseCode"):
                    details.append(f"sip_response_code={form['SipResponseCode']}")
                if form.get("ErrorCode"):
                    details.append(f"error_code={form['ErrorCode']}")
                if form.get("ErrorMessage"):
                    details.append(form["ErrorMessage"])
                call.last_error = "; ".join(details)
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


def _voice_status_event_key(form: dict) -> str:
    call_sid = form.get("CallSid", "")
    sequence = form.get("SequenceNumber")
    status_value = form.get("CallStatus", "")
    if sequence is not None:
        return f"{call_sid}:{sequence}:{status_value}"
    return f"{call_sid}:{status_value}:{utcnow().isoformat()}"


def _send_whatsapp_reply(
    db: Session,
    twilio: TwilioService,
    to_whatsapp: str,
    body: str,
    content_sid: str | None = None,
    content_variables: dict[str, str] | None = None,
) -> OutboundMessage:
    message = OutboundMessage(to_whatsapp=to_whatsapp, body=body, status=MessageStatus.queued)
    db.add(message)
    try:
        result = twilio.send_whatsapp_template(
            to_whatsapp,
            body,
            content_sid=content_sid,
            content_variables=content_variables or {},
        )
        message.twilio_sid = result.sid
        message.status = MessageStatus.sent
    except Exception as exc:
        message.status = MessageStatus.failed
        message.error_message = str(exc)
    return message


def _normalized_inbound_body(form: dict) -> str:
    body = form.get("Body") or ""
    if is_reset_command(body):
        return body
    return (
        form.get("ButtonPayload")
        or form.get("Payload")
        or form.get("ButtonText")
        or form.get("Body")
        or ""
    )
