from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
import re
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    CaregiverElderlyLink,
    CaregiverProfile,
    Contact,
    ContactRole,
    ConversationSession,
    ConversationState,
    ElderlyProfile,
    MobilityLevel,
    OutboundMessage,
    ScheduledCall,
    ScheduledCallStatus,
)
from app.services.phone_numbers import PhoneNumberError, normalize_e164, to_whatsapp_address
from app.services.ocr_service import OCRService
from app.services.scheduler import schedule_call
from app.services.singapore_time import SingaporeTimeParseError, parse_singapore_time
from app.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WhatsAppReply:
    body: str
    content_sid: str | None = None
    content_variables: dict[str, str] = field(default_factory=dict)
    language_override: str | None = None


class ConversationEngine:
    def __init__(
        self,
        settings: Settings,
        translation: TranslationService | None = None,
        ocr: OCRService | None = None,
    ) -> None:
        self.settings = settings
        self.translation = translation or TranslationService(settings)
        self.ocr = ocr or OCRService(settings)

    def handle_message(
        self,
        db: Session,
        from_whatsapp: str,
        body: str,
        media_url: str | None = None,
        button_text: str | None = None,
        button_payload: str | None = None,
    ) -> WhatsAppReply:
        reply = self._handle_message_english(db, from_whatsapp, body, media_url, button_text, button_payload)
        contact = self._get_or_create_contact(db, from_whatsapp)
        session = self._get_or_create_session(db, contact)
        return self._localize_reply(db, contact, session, reply)

    def _handle_message_english(
        self,
        db: Session,
        from_whatsapp: str,
        body: str,
        media_url: str | None = None,
        button_text: str | None = None,
        button_payload: str | None = None,
    ) -> WhatsAppReply:
        contact = self._get_or_create_contact(db, from_whatsapp)
        session = self._get_or_create_session(db, contact)
        body_text = _normalize_command(body)
        text = body_text if is_reset_command(body_text) else _normalize_command(button_payload or button_text or body)
        lowered = text.lower()
        logger.info(
            "conversation inbound from=%s state=%s role=%s command=%s",
            contact.whatsapp_address,
            session.state.value,
            contact.role.value if contact.role else None,
            lowered[:32],
        )

        if media_url:
            return self._handle_ocr_upload(db, contact, session, media_url)

        if is_reset_command(lowered):
            previous_language = self._preferred_language(db, contact, session)
            logger.info("conversation reset from=%s previous_language=%s", contact.whatsapp_address, previous_language)
            self._reset_contact_data(db, contact, session)
            reset_session = self._get_or_create_session(db, contact)
            reset_session.state = ConversationState.awaiting_role
            reset_session.data = {"awaiting_start_language": True}
            db.commit()
            return WhatsAppReply(
                "Reset complete. I removed your saved bot profile data and conversation.",
                language_override=previous_language,
            )

        if lowered in {"restart profile", "reset profile"}:
            contact.role = None
            contact.display_name = None
            session.state = ConversationState.awaiting_role
            session.data = {}
            db.commit()
            return self._language_prompt()

        if contact.role is None or session.state == ConversationState.awaiting_role:
            if session.data.get("awaiting_start_language"):
                language = _parse_start_language(text)
                if language is None:
                    db.commit()
                    return self._language_prompt(prefix="Please choose a language option.", language_override="english")
                session.state = ConversationState.awaiting_role
                session.data = {"start_language": language}
                contact.language_preference = language
                db.commit()
                return self._start_caregiver_onboarding(db, contact, session)
            if not session.data.get("start_language"):
                session.state = ConversationState.awaiting_role
                session.data = {"awaiting_start_language": True}
                db.commit()
                return self._language_prompt(language_override="english")
            return self._start_caregiver_onboarding(db, contact, session)

        if lowered in {"help", "menu"}:
            return WhatsAppReply(self._menu_text(contact))

        if lowered == "profile":
            return WhatsAppReply(self._profile_summary(db, contact))

        if lowered == "edit profile":
            return WhatsAppReply(
                "Profile editing is available by re-entering your profile. Send 'restart profile' to start again, "
                "or 'add elderly' if you are adding another elderly person."
            )

        if lowered == "add elderly":
            return self._start_add_elderly(db, contact, session)

        if lowered in {"cancel", "stop"} and session.state != ConversationState.idle:
            session.state = ConversationState.idle
            session.data = {}
            db.commit()
            return WhatsAppReply("Cancelled the current flow.")

        profile_reply = self._handle_profile_state(db, contact, session, text, lowered)
        if profile_reply:
            return profile_reply

        schedule_reply = self._handle_existing_schedule_flow(db, contact, session, text, lowered)
        if schedule_reply:
            return schedule_reply

        return self._start_booking_flow(db, contact, session)

    def _localize_reply(
        self, db: Session, contact: Contact, session: ConversationSession, reply: WhatsAppReply
    ) -> WhatsAppReply:
        language = reply.language_override or self._preferred_language(db, contact, session)
        logger.info("conversation localize from=%s language=%s", contact.whatsapp_address, language)
        if self.translation.normalize_language(language) == "english":
            return reply

        localized_body = self._localize_body(reply.body, language)
        return WhatsAppReply(
            body=localized_body,
            content_sid=None,
            content_variables=reply.content_variables,
            language_override=reply.language_override,
        )

    def _localize_body(self, body: str, language: str) -> str:
        lines = []
        for line in body.splitlines():
            option_match = re.match(r"^(\s*\d+\.\s+)(.+)$", line)
            if option_match:
                lines.append(f"{option_match.group(1)}{self.translation.translate(option_match.group(2), language)}")
            else:
                lines.append(self.translation.translate(line, language))
        return "\n".join(lines)

    def _preferred_language(self, db: Session, contact: Contact, session: ConversationSession) -> str:
        for key in ("caregiver_language", "start_language"):
            if session.data.get(key):
                return session.data[key]

        if contact.role == ContactRole.caregiver:
            caregiver = db.scalar(select(CaregiverProfile).where(CaregiverProfile.contact_id == contact.id))
            if caregiver is not None:
                return caregiver.preferred_language

        if contact.language_preference:
            return contact.language_preference

        elderly = db.scalar(select(ElderlyProfile).where(ElderlyProfile.contact_id == contact.id))
        if elderly is not None:
            return elderly.preferred_language
        return "english"

    def _start_caregiver_onboarding(
        self, db: Session, contact: Contact, session: ConversationSession
    ) -> WhatsAppReply:
        contact.role = ContactRole.caregiver
        start_language = session.data.get("start_language", "english")
        contact.language_preference = start_language
        session.data = {"flow": "caregiver", "caregiver_language": start_language}
        session.state = ConversationState.awaiting_caregiver_name
        db.commit()
        return WhatsAppReply("Welcome to CareKaki. I will help you book escort or transport for an elderly person.\nWhat is your name?")

    def _handle_profile_state(
        self, db: Session, contact: Contact, session: ConversationSession, text: str, lowered: str
    ) -> WhatsAppReply | None:
        if session.state == ConversationState.awaiting_caregiver_name:
            if not text:
                return WhatsAppReply("Please tell me your name.")
            session.data = {**session.data, "caregiver_name": text}
            session.state = ConversationState.awaiting_relationship
            db.commit()
            return WhatsAppReply("What is your relationship to the elderly person? For example child, spouse, helper, neighbour, or volunteer.")

        if session.state == ConversationState.awaiting_caregiver_language:
            session.data = {**session.data, "caregiver_language": _normalize_language(text)}
            session.state = ConversationState.awaiting_relationship
            db.commit()
            return WhatsAppReply("What is your relationship to the elderly person? For example child, spouse, helper, neighbour, or volunteer.")

        if session.state == ConversationState.awaiting_relationship:
            if not text:
                return WhatsAppReply("Please tell me your relationship to the elderly person.")
            session.data = {**session.data, "relationship": text.lower()}
            session.state = ConversationState.awaiting_elderly_name
            db.commit()
            return WhatsAppReply("What is the elderly person's full name?")

        if session.state == ConversationState.awaiting_elderly_name:
            if not text:
                return WhatsAppReply("Please tell me the elderly person's full name.")
            session.data = {**session.data, "elderly_name": text}
            session.state = ConversationState.awaiting_elderly_phone
            db.commit()
            return WhatsAppReply("What is the elderly person's phone number? For example +6591234567.")

        if session.state == ConversationState.awaiting_elderly_phone:
            try:
                elderly_phone = normalize_e164(text)
            except PhoneNumberError as exc:
                return WhatsAppReply(str(exc))
            session.data = {**session.data, "elderly_phone": elderly_phone}
            session.state = ConversationState.awaiting_pickup_address
            db.commit()
            return WhatsAppReply("What is the pickup address?")

        if session.state == ConversationState.awaiting_pickup_address:
            if not text:
                return WhatsAppReply("Please provide the pickup address.")
            session.data = {**session.data, "pickup_address": text}
            session.state = ConversationState.awaiting_postal_code
            db.commit()
            return WhatsAppReply("What is the 6-digit postal code?")

        if session.state == ConversationState.awaiting_postal_code:
            if not _is_postal_code(text):
                return WhatsAppReply("Postal code must be 6 digits. Please try again.")
            session.data = {**session.data, "postal_code": text}
            if session.data.get("elderly_language"):
                session.state = ConversationState.awaiting_mobility
                db.commit()
                return self._mobility_prompt()
            session.state = ConversationState.awaiting_elderly_language
            db.commit()
            return WhatsAppReply("What language or dialect does the elderly person prefer? For example English, Mandarin, Malay, Tamil, Hokkien, or Cantonese.")

        if session.state == ConversationState.awaiting_elderly_language:
            session.data = {**session.data, "elderly_language": _normalize_language(text)}
            session.state = ConversationState.awaiting_mobility
            db.commit()
            return self._mobility_prompt()

        if session.state == ConversationState.awaiting_mobility:
            mobility = _parse_mobility(lowered)
            if mobility is None:
                return self._mobility_prompt(prefix="Please choose a valid mobility option.")
            session.data = {**session.data, "mobility_level": mobility.value}
            session.state = ConversationState.awaiting_notes
            db.commit()
            return WhatsAppReply("Any optional notes? For example hearing difficulty, dementia, lift access, or 'skip'.")

        if session.state == ConversationState.awaiting_notes:
            notes = None if lowered in {"skip", "none", "no", "n/a", "na"} else text
            session.data = {**session.data, "notes": notes}
            session.state = ConversationState.awaiting_profile_confirmation
            db.commit()
            return WhatsAppReply(self._pending_profile_summary(contact, session.data))

        if session.state == ConversationState.awaiting_profile_confirmation:
            if lowered in {"yes", "y", "confirm", "1"}:
                booking_data = self._persist_profile_flow(db, contact, session)
                session.state = ConversationState.awaiting_time
                session.data = booking_data
                db.commit()
                return WhatsAppReply(
                    f"Profile saved. Book escort or transport for {booking_data['booking_elderly_name']}.\n"
                    "What date and time is the appointment? Reply in Singapore time, for example today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm."
                )
            if lowered in {"edit", "2"}:
                session.state = ConversationState.awaiting_role
                session.data = {}
                db.commit()
                return WhatsAppReply("Let's re-enter the profile details.")
            return WhatsAppReply("Reply YES to save this profile, or EDIT to restart.")

        return None

    def _handle_ocr_upload(
        self, db: Session, contact: Contact, session: ConversationSession, media_url: str
    ) -> WhatsAppReply:
        if contact.role is None or session.data.get("awaiting_start_language"):
            session.state = ConversationState.awaiting_role
            session.data = {"awaiting_start_language": True}
            db.commit()
            return self._language_prompt(
                prefix="Please choose a language before uploading a HealthHub screenshot.",
                language_override="english",
            )

        caregiver = self._caregiver_profile(db, contact)
        if caregiver is None:
            if session.data.get("caregiver_name"):
                caregiver = self._upsert_caregiver_profile(
                    db,
                    contact,
                    {
                        "caregiver_name": session.data.get("caregiver_name"),
                        "caregiver_language": session.data.get("caregiver_language")
                        or self._preferred_language(db, contact, session),
                    },
                )
                db.commit()
            else:
                session.state = ConversationState.awaiting_caregiver_name
                session.data = {"flow": "caregiver", "caregiver_language": self._preferred_language(db, contact, session)}
                db.commit()
                return WhatsAppReply("Please save your caregiver profile first. What is your name?")

        if caregiver is None:
            session.state = ConversationState.awaiting_caregiver_name
            session.data = {"flow": "caregiver", "caregiver_language": self._preferred_language(db, contact, session)}
            db.commit()
            return WhatsAppReply("Please save your caregiver profile first. What is your name?")

        if not session.data.get("recipient"):
            options = self._caregiver_elderly_options(db, caregiver)
            if not options:
                return WhatsAppReply("Please add an elderly profile first, then upload the HealthHub appointment screenshot.")
            if len(options) > 1:
                session.state = ConversationState.awaiting_elderly_selection
                session.data = {
                    "booking_options": options,
                    "caregiver_language": caregiver.preferred_language,
                    "pending_ocr_image_url": media_url,
                }
                db.commit()
                return WhatsAppReply(
                    self._elderly_selection_text(
                        options,
                        prefix="I received the HealthHub screenshot. Choose the elderly profile first.",
                    )
                )
            option = options[0]
            session.data = {
                **session.data,
                "recipient": option["phone_number"],
                "elderly_language": option.get("preferred_language") or "english",
                "booking_elderly_name": option["name"],
                "caregiver_language": caregiver.preferred_language,
            }

        extracted = self.ocr.parse_healthhub_screenshot(media_url)
        if not any(extracted.values()):
            if getattr(self.ocr, "last_error", None) in {"http_401", "missing_config"}:
                return WhatsAppReply(
                    "I could not read the screenshot because the OCR service is not configured correctly right now. "
                    "Please type the appointment date and time manually."
                )
            return WhatsAppReply(
                "I could not extract appointment details from that image. Please type the appointment date and time manually."
            )

        appointment_time_text = extracted.get("appointment_time")
        appointment_location = _ocr_appointment_location(extracted)
        scheduled_at = _parse_ocr_appointment_time(appointment_time_text, self.settings.service_timezone)

        session.data = {
            **session.data,
            "ocr_image_url": media_url,
            "ocr_extracted": extracted,
        }

        if scheduled_at is not None:
            session.data = {**session.data, "scheduled_at": scheduled_at.isoformat()}
            if appointment_location:
                session.data = {**session.data, "appointment_location": appointment_location}
                session.state = ConversationState.awaiting_confirmation
                db.commit()
                return WhatsAppReply(self._appointment_confirmation_text(session.data, scheduled_at, appointment_location))
            session.state = ConversationState.awaiting_appointment_location
            db.commit()
            return WhatsAppReply(
                "I found the appointment time as "
                f"{_format_singapore_datetime(scheduled_at)}.\n"
                "Where is the appointment? Reply with the clinic or hospital name and address."
            )

        if appointment_location:
            session.data = {**session.data, "appointment_location": appointment_location}
            session.state = ConversationState.awaiting_time
            db.commit()
            return WhatsAppReply(
                f"I found the appointment place as {appointment_location}.\n"
                "Please type the appointment date and time in Singapore time, for example today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm."
            )

        session.state = ConversationState.awaiting_time
        db.commit()
        return WhatsAppReply(
            "I could not find the appointment date and place in that image. Please type the appointment date and time in Singapore time."
        )

    def _handle_existing_schedule_flow(
        self, db: Session, contact: Contact, session: ConversationSession, text: str, lowered: str
    ) -> WhatsAppReply | None:
        if lowered.startswith("cancel"):
            return WhatsAppReply(self._cancel_latest(db, contact))

        if lowered in {"schedule call", "schedule", "call", "book", "book appointment", "appointment"}:
            return self._start_booking_flow(db, contact, session)

        if session.state == ConversationState.awaiting_elderly_selection:
            selected = _parse_numbered_choice(text, len(session.data.get("booking_options", [])))
            if selected is None:
                return WhatsAppReply(self._elderly_selection_text(session.data.get("booking_options", []), prefix="Please choose a valid elderly profile."))
            option = session.data["booking_options"][selected - 1]
            pending_ocr_image_url = session.data.get("pending_ocr_image_url")
            session.data = {
                **session.data,
                "recipient": option["phone_number"],
                "elderly_language": option.get("preferred_language") or "english",
                "booking_elderly_name": option["name"],
            }
            session.state = ConversationState.awaiting_time
            db.commit()
            if pending_ocr_image_url:
                return self._handle_ocr_upload(db, contact, session, pending_ocr_image_url)
            return WhatsAppReply(
                f"Book an appointment for {option['name']}.\nWhen is the appointment date? Reply in Singapore time, for example today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm."
            )

        if session.state == ConversationState.awaiting_recipient:
            try:
                recipient = normalize_e164(text)
            except PhoneNumberError as exc:
                return WhatsAppReply(str(exc))
            session.data = {"recipient": recipient}
            session.state = ConversationState.awaiting_time
            db.commit()
            return WhatsAppReply(
                "When is the appointment date? Reply in Singapore time, for example today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm."
            )

        if session.state == ConversationState.awaiting_time:
            try:
                scheduled_at = parse_singapore_time(text, self.settings.service_timezone)
            except SingaporeTimeParseError:
                return WhatsAppReply(
                    "I could not parse that time. Use Singapore time examples like today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm."
                )
            session.data = {**session.data, "scheduled_at": scheduled_at.isoformat()}
            session.state = ConversationState.awaiting_appointment_location
            db.commit()
            return WhatsAppReply("Where is the appointment? Reply with the clinic or hospital name and address.")

        if session.state == ConversationState.awaiting_appointment_location:
            if not text:
                return WhatsAppReply("Please tell me where the appointment is.")
            session.data = {**session.data, "appointment_location": text}
            session.state = ConversationState.awaiting_confirmation
            db.commit()
            scheduled_at = datetime.fromisoformat(session.data["scheduled_at"])
            return WhatsAppReply(self._appointment_confirmation_text(session.data, scheduled_at, text), content_sid=self.settings.twilio_yes_no_content_sid or None)

        if session.state == ConversationState.awaiting_confirmation:
            if lowered in {"yes", "y", "confirm", "1"}:
                if not session.data.get("appointment_location"):
                    session.state = ConversationState.awaiting_appointment_location
                    db.commit()
                    return WhatsAppReply("Where is the appointment? Reply with the clinic or hospital name and address.")
                scheduled_at = datetime.fromisoformat(session.data["scheduled_at"])
                reminder_at = scheduled_at - timedelta(hours=2)
                call = schedule_call(
                    db,
                    self.settings,
                    contact.phone_number,
                    reminder_at,
                    requested_by_whatsapp=contact.whatsapp_address,
                    message_text=(
                        "Hello from CareKaki. The elderly person has an appointment today at "
                        f"{_format_singapore_datetime(scheduled_at)} at {session.data.get('appointment_location')}. "
                        "Please prepare escort or transport support."
                    ),
                    appointment_location=session.data.get("appointment_location"),
                    language=self._preferred_language(db, contact, session),
                )
                session.state = ConversationState.idle
                session.data = {}
                db.commit()
                return WhatsAppReply(
                    f"Appointment confirmed for {_format_singapore_datetime(scheduled_at)} at {call.appointment_location}. "
                    f"We will call the caregiver at {_format_singapore_datetime(call.scheduled_at)}."
                )
            if lowered in {"no", "n", "cancel", "2"}:
                session.state = ConversationState.idle
                session.data = {}
                db.commit()
                return WhatsAppReply("Cancelled the scheduling flow.")
            if not session.data.get("appointment_location"):
                session.data = {**session.data, "appointment_location": text}
                db.commit()
                scheduled_at = datetime.fromisoformat(session.data["scheduled_at"])
                return WhatsAppReply(self._appointment_confirmation_text(session.data, scheduled_at, text), content_sid=self.settings.twilio_yes_no_content_sid or None)
            return WhatsAppReply("Reply YES to confirm or CANCEL to stop.")

        return None

    def _persist_profile_flow(self, db: Session, contact: Contact, session: ConversationSession) -> dict[str, str]:
        data = session.data
        if data.get("flow") in {"caregiver", "add_elderly"}:
            caregiver = self._upsert_caregiver_profile(db, contact, data)
            elderly = ElderlyProfile(
                created_by_contact_id=contact.id,
                name=data["elderly_name"],
                phone_number=data["elderly_phone"],
                pickup_address=data["pickup_address"],
                postal_code=data["postal_code"],
                preferred_language=data["elderly_language"],
                mobility_level=MobilityLevel(data["mobility_level"]),
                notes=data.get("notes"),
            )
            db.add(elderly)
            db.flush()
            db.add(
                CaregiverElderlyLink(
                    caregiver_profile_id=caregiver.id,
                    elderly_profile_id=elderly.id,
                    relationship=data.get("relationship", "caregiver"),
                )
            )
            return {
                "recipient": elderly.phone_number,
                "caregiver_language": caregiver.preferred_language,
                "elderly_language": elderly.preferred_language,
                "booking_elderly_name": elderly.name,
            }

        contact.display_name = data["elderly_name"]
        elderly = ElderlyProfile(
            contact_id=contact.id,
            created_by_contact_id=contact.id,
            name=data["elderly_name"],
            phone_number=contact.phone_number,
            pickup_address=data["pickup_address"],
            postal_code=data["postal_code"],
            preferred_language=data["elderly_language"],
            mobility_level=MobilityLevel(data["mobility_level"]),
            notes=data.get("notes"),
        )
        db.add(elderly)
        db.flush()
        return {
            "recipient": elderly.phone_number,
            "elderly_language": elderly.preferred_language,
            "booking_elderly_name": elderly.name,
        }

    def _upsert_caregiver_profile(self, db: Session, contact: Contact, data: dict) -> CaregiverProfile:
        caregiver = db.scalar(select(CaregiverProfile).where(CaregiverProfile.contact_id == contact.id))
        if caregiver is None:
            caregiver = CaregiverProfile(
                contact_id=contact.id,
                name=data.get("caregiver_name") or contact.display_name or "Caregiver",
                phone_number=contact.phone_number,
                preferred_language=data.get("caregiver_language", "english"),
            )
            db.add(caregiver)
            db.flush()
        else:
            caregiver.name = data.get("caregiver_name") or caregiver.name
            caregiver.preferred_language = data.get("caregiver_language") or caregiver.preferred_language
        contact.language_preference = caregiver.preferred_language
        contact.display_name = caregiver.name
        return caregiver

    def _caregiver_profile(self, db: Session, contact: Contact) -> CaregiverProfile | None:
        return db.scalar(select(CaregiverProfile).where(CaregiverProfile.contact_id == contact.id))

    def _start_add_elderly(self, db: Session, contact: Contact, session: ConversationSession) -> WhatsAppReply:
        if contact.role != ContactRole.caregiver:
            return WhatsAppReply("Only caregiver accounts can add another elderly profile.")
        caregiver = db.scalar(select(CaregiverProfile).where(CaregiverProfile.contact_id == contact.id))
        if caregiver is None:
            session.state = ConversationState.awaiting_caregiver_name
            session.data = {"flow": "caregiver"}
            db.commit()
            return WhatsAppReply("Let's save your caregiver profile first. What is your name?")
        session.state = ConversationState.awaiting_elderly_name
        session.data = {
            "flow": "add_elderly",
            "caregiver_language": caregiver.preferred_language,
            "caregiver_name": caregiver.name,
            "relationship": "caregiver",
        }
        db.commit()
        return WhatsAppReply("What is the elderly person's full name?")

    def _start_booking_flow(self, db: Session, contact: Contact, session: ConversationSession) -> WhatsAppReply:
        if contact.role == ContactRole.caregiver:
            caregiver = db.scalar(select(CaregiverProfile).where(CaregiverProfile.contact_id == contact.id))
            if caregiver is None:
                session.state = ConversationState.awaiting_caregiver_name
                session.data = {"flow": "caregiver"}
                db.commit()
                return WhatsAppReply("Let's save your caregiver profile first. What is your name?")

            elderly_profiles = (
                db.scalars(
                    select(ElderlyProfile)
                    .join(CaregiverElderlyLink, CaregiverElderlyLink.elderly_profile_id == ElderlyProfile.id)
                    .where(CaregiverElderlyLink.caregiver_profile_id == caregiver.id)
                    .order_by(ElderlyProfile.created_at.asc())
                )
                .all()
            )
            if not elderly_profiles:
                return WhatsAppReply("Book an appointment. No elderly profiles saved yet. Send 'add elderly' first.")

            options = [_elderly_booking_option(profile) for profile in elderly_profiles]
            session.state = ConversationState.awaiting_elderly_selection
            session.data = {"booking_options": options, "caregiver_language": caregiver.preferred_language}
            db.commit()
            return WhatsAppReply(self._elderly_selection_text(options))

        session.state = ConversationState.awaiting_caregiver_name
        session.data = {"flow": "caregiver", "caregiver_language": self._preferred_language(db, contact, session)}
        db.commit()
        return WhatsAppReply("Let's save your caregiver profile first. What is your name?")

    def _caregiver_elderly_options(self, db: Session, caregiver: CaregiverProfile) -> list[dict[str, str]]:
        elderly_profiles = (
            db.scalars(
                select(ElderlyProfile)
                .join(CaregiverElderlyLink, CaregiverElderlyLink.elderly_profile_id == ElderlyProfile.id)
                .where(CaregiverElderlyLink.caregiver_profile_id == caregiver.id)
                .order_by(ElderlyProfile.created_at.asc())
            )
            .all()
        )
        return [_elderly_booking_option(profile) for profile in elderly_profiles]

    def _appointment_confirmation_text(self, data: dict, scheduled_at: datetime, appointment_location: str) -> str:
        reminder_at = scheduled_at - timedelta(hours=2)
        return (
            "Confirm appointment for "
            f"{data.get('booking_elderly_name', data['recipient'])} at {_format_singapore_datetime(scheduled_at)}. "
            f"Appointment place: {appointment_location}. "
            f"We will call the caregiver 2 hours before at {_format_singapore_datetime(reminder_at)} to remind them that the elderly person has an appointment today. "
            "Reply YES to confirm or CANCEL to stop."
        )

    def _elderly_selection_text(self, options: list[dict], prefix: str | None = None) -> str:
        lines = ["Book an appointment. Choose the elderly profile:"]
        if prefix:
            lines.insert(0, prefix)
        for index, option in enumerate(options, start=1):
            lines.append(f"{index}. {option['name']} ({option['phone_number']})")
        return "\n".join(lines)

    def _profile_summary(self, db: Session, contact: Contact) -> str:
        if contact.role == ContactRole.caregiver:
            caregiver = db.scalar(select(CaregiverProfile).where(CaregiverProfile.contact_id == contact.id))
            if caregiver is None:
                return "Caregiver profile is not complete. Send 'restart profile' to complete it."
            elderly_profiles = (
                db.scalars(
                    select(ElderlyProfile)
                    .join(CaregiverElderlyLink, CaregiverElderlyLink.elderly_profile_id == ElderlyProfile.id)
                    .where(CaregiverElderlyLink.caregiver_profile_id == caregiver.id)
                    .order_by(ElderlyProfile.created_at.desc())
                )
                .all()
            )
            lines = [f"Caregiver: {caregiver.name}", f"Phone: {caregiver.phone_number}", f"Language: {caregiver.preferred_language}"]
            if not elderly_profiles:
                lines.append("No elderly profiles saved yet.")
            for profile in elderly_profiles:
                lines.append(
                    f"Elderly: {profile.name}, {profile.phone_number}, {profile.postal_code}, {profile.mobility_level.value}"
                )
                if profile.appointment_time_text:
                    lines.append(f"Appointment: {profile.appointment_time_text}")
                if profile.transport_mode_preference:
                    lines.append(f"Transport: {profile.transport_mode_preference}")
            return "\n".join(lines)

        elderly = db.scalar(select(ElderlyProfile).where(ElderlyProfile.contact_id == contact.id))
        if elderly is None:
            return "Elderly profile is not complete. Send 'restart profile' to complete it."
        return (
            f"Elderly: {elderly.name}\n"
            f"Phone: {elderly.phone_number}\n"
            f"Pickup: {elderly.pickup_address} {elderly.postal_code}\n"
            f"Language: {elderly.preferred_language}\n"
            f"Mobility: {elderly.mobility_level.value}\n"
            f"Dialects: {elderly.dialects or '-'}\n"
            f"Transport: {elderly.transport_mode_preference or '-'}\n"
            f"Appointment: {elderly.appointment_time_text or '-'}"
        )

    def _pending_profile_summary(self, contact: Contact, data: dict) -> str:
        lines = ["Please confirm this profile:"]
        if data.get("flow") in {"caregiver", "add_elderly"}:
            lines.extend(
                [
                    f"Caregiver: {data.get('caregiver_name')}",
                    f"Caregiver phone: {contact.phone_number}",
                    f"Relationship: {data.get('relationship')}",
                ]
            )
        lines.extend(
            [
                f"Elderly: {data.get('elderly_name')}",
                f"Elderly phone: {data.get('elderly_phone')}",
                f"Pickup: {data.get('pickup_address')} {data.get('postal_code')}",
                f"Language/dialect: {data.get('elderly_language')}",
                f"Mobility: {data.get('mobility_level')}",
                f"Notes: {data.get('notes') or '-'}",
                "Reply YES to save, or EDIT to restart.",
            ]
        )
        return "\n".join(lines)

    def _role_prompt(self, prefix: str | None = None) -> WhatsAppReply:
        body = "Welcome to CareKaki. Who are you?\n1. I am a caregiver booking for someone\n2. I am the elderly person"
        if prefix:
            body = f"{prefix}\n{body}"
        return WhatsAppReply(body, content_sid=self.settings.twilio_role_menu_content_sid or None)

    def _language_prompt(self, prefix: str | None = None, language_override: str | None = None) -> WhatsAppReply:
        body = "What language should we use with you?\n1. English\n2. Mandarin\n3. Malay\n4. Tamil"
        if prefix:
            body = f"{prefix}\n{body}"
        return WhatsAppReply(body, language_override=language_override)

    def _mobility_prompt(self, prefix: str | None = None) -> WhatsAppReply:
        body = "Mobility level?\n1. Need transport\n2. Need escort\n3. Need both"
        if prefix:
            body = f"{prefix}\n{body}"
        return WhatsAppReply(body, content_sid=self.settings.twilio_mobility_menu_content_sid or None)

    def _menu_text(self, contact: Contact) -> str:
        if contact.role == ContactRole.caregiver:
            return "Send 'profile' to view saved profiles, 'add elderly' to add another elderly person, or 'book' to book escort or transport."
        return "Send 'profile' to view your saved profile or 'book' to book escort or transport."

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

    def _reset_contact_data(self, db: Session, contact: Contact, session: ConversationSession) -> None:
        caregiver = db.scalar(select(CaregiverProfile).where(CaregiverProfile.contact_id == contact.id))
        if caregiver is not None:
            db.execute(
                delete(CaregiverElderlyLink).where(CaregiverElderlyLink.caregiver_profile_id == caregiver.id)
            )
            db.delete(caregiver)

        elderly_profiles = list(
            db.scalars(
                select(ElderlyProfile).where(
                    (ElderlyProfile.contact_id == contact.id)
                    | (ElderlyProfile.created_by_contact_id == contact.id)
                )
            )
        )
        elderly_ids = [profile.id for profile in elderly_profiles]
        if elderly_ids:
            db.execute(delete(CaregiverElderlyLink).where(CaregiverElderlyLink.elderly_profile_id.in_(elderly_ids)))
            for elderly in elderly_profiles:
                db.delete(elderly)

        db.execute(
            delete(ScheduledCall)
            .where(ScheduledCall.requested_by_whatsapp == contact.whatsapp_address)
            .where(ScheduledCall.status == ScheduledCallStatus.pending)
        )
        db.execute(delete(OutboundMessage).where(OutboundMessage.to_whatsapp == contact.whatsapp_address))
        db.delete(session)
        contact.role = None
        contact.display_name = None
        contact.language_preference = "english"
        db.commit()


def _normalize_command(value: str | None) -> str:
    normalized = (value or "").replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    return normalized.strip()


def _is_reset_command(value: str) -> bool:
    normalized = value.strip().lower().replace("\uff0f", "/")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized in {"/reset", "/ reset", "reset"}


def is_reset_command(value: str | None) -> bool:
    return _is_reset_command(_normalize_command(value))


def _normalize_language(value: str) -> str:
    normalized = value.strip().lower()
    return {
        "1": "english",
        "2": "mandarin",
        "3": "malay",
        "4": "tamil",
        "chinese": "mandarin",
    }.get(normalized, normalized or "english")


def _parse_start_language(value: str) -> str | None:
    normalized = value.strip().lower()
    return {
        "1": "english",
        "english": "english",
        "eng": "english",
        "2": "mandarin",
        "mandarin": "mandarin",
        "chinese": "mandarin",
        "中文": "mandarin",
        "华语": "mandarin",
        "3": "malay",
        "malay": "malay",
        "melayu": "malay",
        "4": "tamil",
        "tamil": "tamil",
        "தமிழ்": "tamil",
    }.get(normalized)


def _parse_numbered_choice(value: str, max_choice: int) -> int | None:
    if not value.strip().isdigit():
        return None
    selected = int(value.strip())
    if selected < 1 or selected > max_choice:
        return None
    return selected


def _elderly_booking_option(profile: ElderlyProfile) -> dict[str, str]:
    return {
        "id": str(profile.id),
        "name": profile.name,
        "phone_number": profile.phone_number,
        "preferred_language": profile.preferred_language,
    }


def _parse_mobility(value: str) -> MobilityLevel | None:
    normalized = value.strip().lower().replace("-", " ").replace("_", " ")
    return {
        "1": MobilityLevel.need_transport,
        "need transport": MobilityLevel.need_transport,
        "transport": MobilityLevel.need_transport,
        "2": MobilityLevel.need_escort,
        "need escort": MobilityLevel.need_escort,
        "escort": MobilityLevel.need_escort,
        "3": MobilityLevel.need_both,
        "need both": MobilityLevel.need_both,
        "both": MobilityLevel.need_both,
        "transport and escort": MobilityLevel.need_both,
        "escort and transport": MobilityLevel.need_both,
        "independent": MobilityLevel.independent,
        "walking aid": MobilityLevel.walking_aid,
        "walker": MobilityLevel.walking_aid,
        "cane": MobilityLevel.walking_aid,
        "wheelchair": MobilityLevel.wheelchair,
        "needs escort support": MobilityLevel.escort_support,
        "escort support": MobilityLevel.escort_support,
    }.get(normalized)


def _ocr_appointment_location(extracted: dict) -> str | None:
    location_parts = []
    for key in ("appointment_location", "clinic", "department"):
        value = (extracted.get(key) or "").strip()
        if value and value not in location_parts:
            location_parts.append(value)
    return ", ".join(location_parts) or None


def _parse_ocr_appointment_time(value: str | None, timezone_name: str) -> datetime | None:
    if not value:
        return None

    normalized = re.sub(r"\s+", " ", value.replace(",", " ")).strip()
    normalized = re.sub(r"\b([AP])\.?M\.?\b", lambda match: match.group(1).lower() + "m", normalized, flags=re.IGNORECASE)
    candidates = [normalized]

    date_first = re.search(
        r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4}).*?(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if date_first:
        candidates.append(
            f"{date_first.group(1)} {date_first.group(2)} {date_first.group(3)} {date_first.group(4)}"
        )

    month_first = re.search(
        r"\b([A-Za-z]{3,9})\s+(\d{1,2})\s+(\d{4}).*?(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if month_first:
        candidates.append(
            f"{month_first.group(2)} {month_first.group(1)} {month_first.group(3)} {month_first.group(4)}"
        )

    for candidate in candidates:
        try:
            return parse_singapore_time(candidate, timezone_name)
        except SingaporeTimeParseError:
            continue
    return None


def _is_postal_code(value: str) -> bool:
    postal_code = value.strip()
    return len(postal_code) == 6 and postal_code.isdigit()


def _format_singapore_datetime(value: datetime) -> str:
    source_time = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    singapore_time = source_time.astimezone(ZoneInfo("Asia/Singapore"))
    period = "am" if singapore_time.hour < 12 else "pm"
    hour = singapore_time.hour % 12 or 12
    return f"{singapore_time.day} {singapore_time:%b %Y} {hour}:{singapore_time.minute:02d}{period}"
