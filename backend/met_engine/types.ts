/**
 * MET Engine — Types
 *
 * Engine is stateless. Trip Status Service is the source of truth.
 */

// =============================================================================
// DOMAIN
// =============================================================================

export type MobilityFlag =
  | 'walker'
  | 'wheelchair'
  | 'stretcher'
  | 'bedridden'
  | 'visually_impaired'
  | 'hearing_impaired'
  | 'cognitive_impairment';

export type Dialect =
  | 'hokkien'
  | 'teochew'
  | 'cantonese'
  | 'mandarin'
  | 'malay'
  | 'tamil'
  | 'english';

export type TransportMode = 'driver_only' | 'escort_only' | 'both';
export type Citizenship = 'sg_citizen' | 'sg_pr' | 'foreigner';

export interface Location {
  postalCode: string;
  address?: string;
  lat?: number;
  lng?: number;
}

// =============================================================================
// BOOKING (8 fields)
// =============================================================================

export interface BookingRequest {
  elderlyName: string;
  pickup: Location;
  appointmentDateTime: string;
  mobilityFlags: MobilityFlag[];
  preferredLanguages: Dialect[];
  transportMode: TransportMode;
  citizenship: Citizenship;
  monthlyIncomeSGD: number;
}

export interface ValidationResult {
  ok: boolean;
  errors: string[];
}

// =============================================================================
// SUBSIDY
// =============================================================================

export type ServiceTier =
  | 'transport_only'
  | 'basic_escort_transport'
  | 'accompanied_escort_transport';

export interface SubsidyComputation {
  citizenship: Citizenship;
  monthlyIncomeSGD: number;
  serviceTier: ServiceTier;
  baseSubsidyRate: number;
  interimRebateSGD: number;
  interimRebateValid: boolean;
  interimRebateExclusionReason?: string;
  computedAt: string;
}

// =============================================================================
// KAFKA EVENT ENVELOPE
// =============================================================================

export type KafkaTopic =
  | 'trip.requested'
  | 'trip.book'
  | 'trip.cancelled'
  | 'job.offered'
  | 'trip.confirmed'
  | 'trip.no_match';

export interface KafkaEvent<T = unknown> {
  topic: KafkaTopic;
  key: string;
  payload: T;
  publishedAt: string;
  version: number;
}

// =============================================================================
// PAYLOADS — Engine publishes
// =============================================================================

export interface TripRequestedPayload {
  tripId: string;
  elderlyName: string;
  pickup: Location;
  appointmentDateTime: string;
  mobilityFlags: MobilityFlag[];
  preferredLanguages: Dialect[];
  transportMode: TransportMode;
  subsidy: SubsidyComputation;
  requestedAt: string;
}

/** Engine sends just tripId. Transport already has the offer details. */
export interface TripBookPayload {
  tripId: string;
  bookedAt: string;
}

export interface TripCancelledPayload {
  tripId: string;
  cancelledBy: 'caregiver' | 'system';
  reason?: string;
  cancelledAt: string;
}

// =============================================================================
// PAYLOADS — Engine consumes
// =============================================================================

export interface JobOfferedPayload {
  tripId: string;
  driverId: string;
  driverName: string;
  escortId: string;
  escortName: string;
  vehicleType: string;
  estimatedPriceSGD: number;
  finalPriceSGD: number;
  pickupETA: string;
  appointmentDateTime: string;
  ngoId: string;
  ngoName: string;
}

export interface TripConfirmedPayload {
  tripId: string;
  driverId: string;
  escortId: string;
  finalPriceSGD: number;
  pickupETA: string;
  appointmentDateTime: string;
  confirmedAt: string;
}

export interface TripNoMatchPayload {
  tripId: string;
  reason: string;
  retriesAttempted: number;
}

// =============================================================================
// BOT NOTIFICATIONS (outbound HTTP)
// =============================================================================

export type NotificationType =
  | 'matching_started'
  | 'recommendation_ready'
  | 'no_match_available'
  | 'trip_confirmed'
  | 'booking_cancelled';

export interface BotNotificationPayload {
  tripId: string;
  type: NotificationType;
  message: string;
  data?: Record<string, unknown>;
  sentAt: string;
}
