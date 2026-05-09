from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CaregiverElderlyLink, CaregiverProfile, Contact, ElderlyProfile
from app.schemas import (
    CaregiverElderlyLinkCreate,
    CaregiverElderlyLinkResponse,
    CaregiverProfileCreate,
    CaregiverProfileResponse,
    ContactProfileResponse,
    ContactResponse,
    ElderlyProfileCreate,
    ElderlyProfileResponse,
)
from app.services.phone_numbers import PhoneNumberError, normalize_e164

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.get("/contacts/by-phone/{phone:path}", response_model=ContactProfileResponse)
def get_contact_by_phone(phone: str, db: Session = Depends(get_db)) -> ContactProfileResponse:
    try:
        normalized_phone = normalize_e164(phone)
    except PhoneNumberError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    contact = db.scalar(select(Contact).where(Contact.phone_number == normalized_phone))
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _profile_response(db, contact)


@router.get("/contacts/{contact_id}", response_model=ContactProfileResponse)
def get_contact(contact_id: UUID, db: Session = Depends(get_db)) -> ContactProfileResponse:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _profile_response(db, contact)


@router.post("/caregivers", response_model=CaregiverProfileResponse, status_code=status.HTTP_201_CREATED)
def create_caregiver_profile(payload: CaregiverProfileCreate, db: Session = Depends(get_db)) -> CaregiverProfile:
    if db.get(Contact, payload.contact_id) is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    profile = CaregiverProfile(
        contact_id=payload.contact_id,
        name=payload.name.strip(),
        phone_number=_normalize_phone_or_422(payload.phone_number),
        preferred_language=payload.preferred_language.strip().lower(),
        notes=payload.notes,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/elderly", response_model=ElderlyProfileResponse, status_code=status.HTTP_201_CREATED)
def create_elderly_profile(payload: ElderlyProfileCreate, db: Session = Depends(get_db)) -> ElderlyProfile:
    if payload.contact_id and db.get(Contact, payload.contact_id) is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    if payload.created_by_contact_id and db.get(Contact, payload.created_by_contact_id) is None:
        raise HTTPException(status_code=404, detail="Creator contact not found")

    profile = ElderlyProfile(
        contact_id=payload.contact_id,
        created_by_contact_id=payload.created_by_contact_id,
        name=payload.name.strip(),
        phone_number=_normalize_phone_or_422(payload.phone_number),
        pickup_address=payload.pickup_address.strip(),
        postal_code=_validate_postal_code(payload.postal_code),
        preferred_language=payload.preferred_language.strip().lower(),
        mobility_level=payload.mobility_level,
        notes=payload.notes,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/links", response_model=CaregiverElderlyLinkResponse, status_code=status.HTTP_201_CREATED)
def create_profile_link(payload: CaregiverElderlyLinkCreate, db: Session = Depends(get_db)) -> CaregiverElderlyLink:
    if db.get(CaregiverProfile, payload.caregiver_profile_id) is None:
        raise HTTPException(status_code=404, detail="Caregiver profile not found")
    if db.get(ElderlyProfile, payload.elderly_profile_id) is None:
        raise HTTPException(status_code=404, detail="Elderly profile not found")

    link = CaregiverElderlyLink(
        caregiver_profile_id=payload.caregiver_profile_id,
        elderly_profile_id=payload.elderly_profile_id,
        relationship=payload.relationship.strip().lower(),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.get("/caregivers/{caregiver_id}/elderly", response_model=list[ElderlyProfileResponse])
def list_caregiver_elderly(caregiver_id: UUID, db: Session = Depends(get_db)) -> list[ElderlyProfile]:
    if db.get(CaregiverProfile, caregiver_id) is None:
        raise HTTPException(status_code=404, detail="Caregiver profile not found")
    statement = (
        select(ElderlyProfile)
        .join(CaregiverElderlyLink, CaregiverElderlyLink.elderly_profile_id == ElderlyProfile.id)
        .where(CaregiverElderlyLink.caregiver_profile_id == caregiver_id)
        .order_by(ElderlyProfile.created_at.desc())
    )
    return list(db.scalars(statement))


def _profile_response(db: Session, contact: Contact) -> ContactProfileResponse:
    caregiver = db.scalar(select(CaregiverProfile).where(CaregiverProfile.contact_id == contact.id))
    elderly = db.scalar(select(ElderlyProfile).where(ElderlyProfile.contact_id == contact.id))
    linked_elderly: list[ElderlyProfile] = []
    if caregiver is not None:
        linked_elderly = list_caregiver_elderly(caregiver.id, db)
    return ContactProfileResponse(
        contact=ContactResponse.model_validate(contact),
        caregiver=CaregiverProfileResponse.model_validate(caregiver) if caregiver else None,
        elderly=ElderlyProfileResponse.model_validate(elderly) if elderly else None,
        linked_elderly=[ElderlyProfileResponse.model_validate(profile) for profile in linked_elderly],
    )


def _validate_postal_code(value: str) -> str:
    postal_code = value.strip()
    if len(postal_code) != 6 or not postal_code.isdigit():
        raise HTTPException(status_code=422, detail="Postal code must be 6 digits")
    return postal_code


def _normalize_phone_or_422(value: str) -> str:
    try:
        return normalize_e164(value)
    except PhoneNumberError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
