from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.dependencies import get_twilio_service
from app.models import MessageStatus, OutboundMessage, TransportRole
from app.schemas import (
    MessageSendResponse,
    TransportBookingsResponse,
    TransportStatusEventResponse,
    TransportStatusUpdateRequest,
    TransportStatusUpdateResponse,
    TransportTripResetRequest,
)
from app.services.translation_service import TranslationService
from app.services.transporter import (
    TransporterConflict,
    TransporterError,
    get_transporter_bookings,
    reset_transport_trip,
    seed_demo_transport_trips,
    serialize_trip,
    update_transport_status,
)
from app.services.twilio_service import TwilioService

router = APIRouter(prefix="/api/v1/transporter", tags=["transporter"])


@router.get("/bookings", response_model=TransportBookingsResponse)
def transporter_bookings(
    resource_id: str = Query(..., min_length=1, max_length=64),
    role: TransportRole = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    seed_demo_transport_trips(db)
    pending, current = get_transporter_bookings(db, resource_id, role)
    return {
        "pending": [serialize_trip(trip) for trip in pending],
        "current": serialize_trip(current) if current else None,
    }


@router.post("/trips/{trip_id}/status", response_model=TransportStatusUpdateResponse)
def update_trip_status(
    trip_id: str,
    payload: TransportStatusUpdateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    twilio: TwilioService = Depends(get_twilio_service),
) -> dict:
    seed_demo_transport_trips(db)
    translation = TranslationService(settings)
    try:
        trip, event, message = update_transport_status(
            db,
            trip_id,
            payload.resource_id,
            payload.role,
            payload.status,
            twilio,
            translation,
        )
    except TransporterConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except TransporterError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {
        "trip": serialize_trip(trip),
        "event": event,
        "message": _message_response(message),
    }


@router.post("/trips/{trip_id}/reset", response_model=TransportBookingsResponse)
def reset_trip_status(
    trip_id: str,
    payload: TransportTripResetRequest,
    db: Session = Depends(get_db),
) -> dict:
    seed_demo_transport_trips(db)
    try:
        trip = reset_transport_trip(db, trip_id, payload.resource_id, payload.role)
    except TransporterError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    pending, current = get_transporter_bookings(db, payload.resource_id, payload.role)
    if current is None:
        current = trip
    return {
        "pending": [serialize_trip(trip) for trip in pending],
        "current": serialize_trip(current),
    }


def _message_response(message: OutboundMessage | None) -> MessageSendResponse | None:
    if message is None:
        return None
    return MessageSendResponse(
        id=message.id,
        to=message.to_whatsapp,
        body=message.body,
        status=message.status if message.status else MessageStatus.queued,
        twilio_sid=message.twilio_sid,
    )
