"""
MET Engine — domain enums.

Field names and enum values mirror the trip_audit source of truth exactly:
  - provider_id / provider_name  (not ngo_id / ngo_name)
  - TripType: DRIVER_ONLY, ESCORT_ONLY, COMBINED
  - AuditOutcome: COMPLETED, NO_MATCH, CANCELLED
  - Kafka topics: trip.* namespace  (not job.*)
"""
import enum


class TripType(str, enum.Enum):
    DRIVER_ONLY = "DRIVER_ONLY"
    ESCORT_ONLY = "ESCORT_ONLY"
    COMBINED = "COMBINED"


class AuditOutcome(str, enum.Enum):
    COMPLETED = "COMPLETED"
    NO_MATCH = "NO_MATCH"
    CANCELLED = "CANCELLED"


class MobilityFlag(str, enum.Enum):
    walker = "walker"
    wheelchair = "wheelchair"
    stretcher = "stretcher"
    bedridden = "bedridden"
    visually_impaired = "visually_impaired"
    hearing_impaired = "hearing_impaired"
    cognitive_impairment = "cognitive_impairment"


class TransportMode(str, enum.Enum):
    driver_only = "driver_only"
    escort_only = "escort_only"
    both = "both"
