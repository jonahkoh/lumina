from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    MessageStatus,
    OutboundMessage,
    TransportRole,
    TransportTrip,
    TransportTripStatus,
    TransportTripStatusEvent,
    utcnow,
)
from app.services.translation_service import TranslationService
from app.services.twilio_service import TwilioResult, TwilioService


STATUS_FLOW = [
    TransportTripStatus.arriving_soon,
    TransportTripStatus.arrived_pickup,
    TransportTripStatus.picked_up_client,
    TransportTripStatus.arrived_appointment,
    TransportTripStatus.appointment_finished,
    TransportTripStatus.sending_home,
    TransportTripStatus.reached_home,
]

ACTIVE_STATUSES = {TransportTripStatus.upcoming, *STATUS_FLOW}


class TransporterError(ValueError):
    pass


class TransporterConflict(TransporterError):
    pass


def get_transporter_bookings(db: Session, resource_id: str, role: TransportRole) -> tuple[list[TransportTrip], TransportTrip | None]:
    field = TransportTrip.driver_id if role == TransportRole.driver else TransportTrip.escort_id
    trips = list(db.scalars(select(TransportTrip).where(field == resource_id).order_by(TransportTrip.pickup_time.asc())))
    pending = [trip for trip in trips if trip.status == TransportTripStatus.pending]
    current = next((trip for trip in trips if trip.status in ACTIVE_STATUSES), None)
    return pending, current


def update_transport_status(
    db: Session,
    trip_id: str,
    resource_id: str,
    role: TransportRole,
    status: TransportTripStatus,
    twilio: TwilioService,
    translation: TranslationService,
) -> tuple[TransportTrip, TransportTripStatusEvent, OutboundMessage | None]:
    trip = db.get(TransportTrip, trip_id)
    if trip is None:
        raise TransporterError("Transport trip not found")
    _ensure_assigned(trip, resource_id, role)
    _ensure_next_status(trip.status, status)

    event = TransportTripStatusEvent(trip_id=trip.id, resource_id=resource_id, role=role, status=status)
    trip.status = status
    trip.status_updated_at = utcnow()
    db.add(event)
    db.commit()
    db.refresh(trip)
    db.refresh(event)

    message = _send_caregiver_update(db, trip, status, twilio, translation)
    db.commit()
    if message is not None:
        db.refresh(message)
    return trip, event, message


def reset_transport_trip(
    db: Session,
    trip_id: str,
    resource_id: str,
    role: TransportRole,
) -> TransportTrip:
    trip = db.get(TransportTrip, trip_id)
    if trip is None:
        raise TransporterError("Transport trip not found")
    _ensure_assigned(trip, resource_id, role)

    trip.status = TransportTripStatus.upcoming
    trip.status_updated_at = None
    trip.status_events.clear()
    db.commit()
    db.refresh(trip)
    return trip


def serialize_trip(trip: TransportTrip) -> dict:
    return {
        "id": trip.id,
        "elderly": trip.elderly_name,
        "age": trip.elderly_age,
        "accessibility": trip.accessibility,
        "pickup": {
            "time": trip.pickup_time,
            "date": trip.pickup_date,
            "location": trip.pickup_location,
        },
        "appointment": {
            "time": trip.appointment_time,
            "location": trip.appointment_location,
            "clinic": trip.appointment_type,
        },
        "returnTime": trip.return_time,
        "driverId": trip.driver_id,
        "escortId": trip.escort_id,
        "caregiver": trip.caregiver_name,
        "caregiverPhone": trip.caregiver_phone,
        "subsidy": trip.subsidy,
        "notes": trip.notes,
        "status": trip.status.value,
        "statusHistory": [
            {
                "id": str(event.id),
                "status": event.status.value,
                "resourceId": event.resource_id,
                "role": event.role.value,
                "createdAt": event.created_at.isoformat(),
            }
            for event in trip.status_events
        ],
    }


def seed_demo_transport_trips(db: Session) -> None:
    demo_trips = [
        TransportTrip(
            id="p1",
            elderly_name="Mdm Tan Soo Kheng",
            elderly_age=84,
            accessibility="wheelchair",
            pickup_time="09:00",
            pickup_date="Tue, 12 May",
            pickup_location="Blk 167 Toa Payoh Lor 1",
            appointment_time="10:00",
            appointment_location="Tan Tock Seng Hospital",
            appointment_type="Cardiology",
            return_time="12:30",
            driver_id="d1",
            escort_id="e1",
            caregiver_name="Ms Tan Li Yuan",
            caregiver_phone="+6598268686",
            caregiver_whatsapp="whatsapp:+6598268686",
            caregiver_language="english",
            subsidy="PG - 75% subsidy",
            status=TransportTripStatus.pending,
        ),
        TransportTrip(
            id="t2",
            elderly_name="Mr Goh Tian Seng",
            elderly_age=76,
            accessibility="ambulant",
            pickup_time="09:30",
            pickup_date="Today",
            pickup_location="Blk 456 Ang Mo Kio Ave 10",
            appointment_time="10:30",
            appointment_location="National University Hospital",
            appointment_type="Cardiology",
            return_time="12:30",
            driver_id="d2",
            escort_id="e2",
            caregiver_name="Ms Goh Mei Ling",
            caregiver_phone="+6598268686",
            caregiver_whatsapp="whatsapp:+6598268686",
            caregiver_language="english",
            subsidy="PG - 75% subsidy",
            status=TransportTripStatus.upcoming,
        ),
        TransportTrip(
            id="t1",
            elderly_name="Mdm Lim Choo Neo",
            elderly_age=82,
            accessibility="wheelchair",
            pickup_time="09:30",
            pickup_date="Today",
            pickup_location="Blk 123 Toa Payoh Lor 1",
            appointment_time="10:15",
            appointment_location="Singapore General Hospital",
            appointment_type="Geriatric Clinic",
            return_time="12:00",
            driver_id="d1",
            escort_id="e1",
            caregiver_name="Mr Lim Boon Heng",
            caregiver_phone="+6598268686",
            caregiver_whatsapp="whatsapp:+6598268686",
            caregiver_language="english",
            subsidy="SMF - 50% subsidy",
            status=TransportTripStatus.upcoming,
        ),
    ]
    for trip in demo_trips:
        if db.get(TransportTrip, trip.id) is None:
            db.add(trip)
    db.commit()


def _ensure_assigned(trip: TransportTrip, resource_id: str, role: TransportRole) -> None:
    assigned = trip.driver_id if role == TransportRole.driver else trip.escort_id
    if assigned != resource_id:
        raise TransporterError("This resource is not assigned to the trip")


def _ensure_next_status(current: TransportTripStatus, requested: TransportTripStatus) -> None:
    if requested not in STATUS_FLOW:
        raise TransporterConflict("Unsupported transport journey status")
    if current == TransportTripStatus.pending:
        raise TransporterConflict("Accept the trip before updating journey status")
    next_status = STATUS_FLOW[0] if current == TransportTripStatus.upcoming else _next_after(current)
    if requested != next_status:
        raise TransporterConflict(f"Next valid status is {next_status.value}")


def _next_after(current: TransportTripStatus) -> TransportTripStatus:
    try:
        index = STATUS_FLOW.index(current)
    except ValueError as exc:
        raise TransporterConflict("Trip is not active") from exc
    if index >= len(STATUS_FLOW) - 1:
        raise TransporterConflict("Trip journey is already complete")
    return STATUS_FLOW[index + 1]


def _send_caregiver_update(
    db: Session,
    trip: TransportTrip,
    status: TransportTripStatus,
    twilio: TwilioService,
    translation: TranslationService,
) -> OutboundMessage | None:
    if not trip.caregiver_whatsapp:
        return None
    body = _status_message(trip, status)
    localized = translation.translate(body, trip.caregiver_language)
    message = OutboundMessage(to_whatsapp=trip.caregiver_whatsapp, body=localized, status=MessageStatus.queued)
    db.add(message)
    db.flush()
    try:
        result: TwilioResult = twilio.send_whatsapp_message(trip.caregiver_whatsapp, localized)
        message.twilio_sid = result.sid
        message.status = MessageStatus.sent
    except Exception as exc:
        message.status = MessageStatus.failed
        message.error_message = str(exc)
    return message


def _status_message(trip: TransportTrip, status: TransportTripStatus) -> str:
    name = trip.elderly_name
    messages = {
        TransportTripStatus.arriving_soon: f"Transport is arriving in about 10 minutes for {name}.",
        TransportTripStatus.arrived_pickup: "Transport has arrived at the pickup point.",
        TransportTripStatus.picked_up_client: f"{name} has been picked up and is on the way.",
        TransportTripStatus.arrived_appointment: f"{name} has reached the appointment location.",
        TransportTripStatus.appointment_finished: "The appointment is finished. They are heading home.",
        TransportTripStatus.sending_home: f"{name} is on the way home.",
        TransportTripStatus.reached_home: f"{name} has reached home.",
    }
    return messages[status]
