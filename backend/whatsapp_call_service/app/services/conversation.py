from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Contact, ConversationSession, ConversationState, ScheduledCall, ScheduledCallStatus
from app.services.phone_numbers import PhoneNumberError, normalize_e164, to_whatsapp_address
from app.services.scheduler import schedule_call


class ConversationEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def handle_message(self, db: Session, from_whatsapp: str, body: str) -> str:
        contact = self._get_or_create_contact(db, from_whatsapp)
        session = self._get_or_create_session(db, contact)
        text = body.strip()
        lowered = text.lower()

        if lowered in {"help", "menu"}:
            return "Send 'schedule call' to schedule a call, or 'cancel' to cancel your latest pending call."

        if lowered in {"cancel", "stop"} and session.state != ConversationState.idle:
            session.state = ConversationState.idle
            session.data = {}
            db.commit()
            return "Cancelled the scheduling flow."

        if lowered.startswith("cancel"):
            return self._cancel_latest(db, contact)

        if lowered in {"schedule call", "schedule", "call"}:
            session.state = ConversationState.awaiting_recipient
            session.data = {}
            db.commit()
            return "Who should I call? Reply with the phone number in E.164 format, for example +15551234567."

        if session.state == ConversationState.awaiting_recipient:
            try:
                recipient = normalize_e164(text)
            except PhoneNumberError as exc:
                return str(exc)
            session.data = {"recipient": recipient}
            session.state = ConversationState.awaiting_time
            db.commit()
            return "When should I call? Reply with an ISO time like 2026-05-09T15:30:00+08:00."

        if session.state == ConversationState.awaiting_time:
            try:
                scheduled_at = datetime.fromisoformat(text)
            except ValueError:
                return "I could not parse that time. Use ISO format, for example 2026-05-09T15:30:00+08:00."
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=ZoneInfo(self.settings.service_timezone))
            session.data = {**session.data, "scheduled_at": scheduled_at.isoformat()}
            session.state = ConversationState.awaiting_confirmation
            db.commit()
            return (
                f"Confirm scheduled call to {session.data['recipient']} at {scheduled_at.isoformat()}? "
                "Reply YES to confirm or CANCEL to stop."
            )

        if session.state == ConversationState.awaiting_confirmation:
            if lowered in {"yes", "y", "confirm"}:
                scheduled_at = datetime.fromisoformat(session.data["scheduled_at"])
                call = schedule_call(
                    db,
                    self.settings,
                    session.data["recipient"],
                    scheduled_at,
                    requested_by_whatsapp=contact.whatsapp_address,
                )
                session.state = ConversationState.idle
                session.data = {}
                db.commit()
                return f"Scheduled call {call.id} for {call.scheduled_at.isoformat()}."
            if lowered in {"no", "n", "cancel"}:
                session.state = ConversationState.idle
                session.data = {}
                db.commit()
                return "Cancelled the scheduling flow."
            return "Reply YES to confirm or CANCEL to stop."

        return "I can help schedule calls. Send 'schedule call' to start."

    def _get_or_create_contact(self, db: Session, from_whatsapp: str) -> Contact:
        whatsapp_address = to_whatsapp_address(from_whatsapp)
        phone_number = normalize_e164(whatsapp_address)
        contact = db.scalar(select(Contact).where(Contact.whatsapp_address == whatsapp_address))
        if contact is not None:
            return contact
        contact = Contact(phone_number=phone_number, whatsapp_address=whatsapp_address)
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    def _get_or_create_session(self, db: Session, contact: Contact) -> ConversationSession:
        session = db.scalar(select(ConversationSession).where(ConversationSession.contact_id == contact.id))
        if session is not None:
            return session
        session = ConversationSession(contact_id=contact.id)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def _cancel_latest(self, db: Session, contact: Contact) -> str:
        call = db.scalar(
            select(ScheduledCall)
            .where(ScheduledCall.requested_by_whatsapp == contact.whatsapp_address)
            .where(ScheduledCall.status == ScheduledCallStatus.pending)
            .order_by(ScheduledCall.scheduled_at.desc())
        )
        if call is None:
            return "You do not have any pending calls to cancel."
        call.status = ScheduledCallStatus.cancelled
        db.commit()
        return f"Cancelled scheduled call {call.id}."
