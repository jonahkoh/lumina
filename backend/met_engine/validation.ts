/**
 * MET Engine — Booking Validation (pure)
 */

import { BookingRequest, ValidationResult } from './types';

const SG_POSTAL_REGEX = /^\d{6}$/;
const ISO_DATETIME_REGEX = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

const VALID_TRANSPORT_MODES = ['driver_only', 'escort_only', 'both'];
const VALID_CITIZENSHIP = ['sg_citizen', 'sg_pr', 'foreigner'];

export function validateBookingRequest(req: BookingRequest): ValidationResult {
  const errors: string[] = [];

  if (!req.elderlyName?.trim()) errors.push('elderlyName is required');

  if (!req.pickup?.postalCode) {
    errors.push('pickup.postalCode is required');
  } else if (!SG_POSTAL_REGEX.test(req.pickup.postalCode)) {
    errors.push('pickup.postalCode must be 6 digits');
  }

  if (!req.appointmentDateTime) {
    errors.push('appointmentDateTime is required');
  } else if (!ISO_DATETIME_REGEX.test(req.appointmentDateTime)) {
    errors.push('appointmentDateTime must be ISO 8601 format');
  } else {
    const apptTime = new Date(req.appointmentDateTime);
    if (isNaN(apptTime.getTime())) {
      errors.push('appointmentDateTime is not a valid date');
    } else if (apptTime.getTime() < Date.now()) {
      errors.push('appointmentDateTime is in the past');
    }
  }

  if (!Array.isArray(req.mobilityFlags)) {
    errors.push('mobilityFlags must be an array');
  }

  if (!Array.isArray(req.preferredLanguages)) {
    errors.push('preferredLanguages must be an array');
  } else if (req.preferredLanguages.length === 0) {
    errors.push('at least one preferredLanguage required (use "english" as fallback)');
  }

  if (!req.transportMode) {
    errors.push('transportMode is required');
  } else if (!VALID_TRANSPORT_MODES.includes(req.transportMode)) {
    errors.push(`transportMode must be one of: ${VALID_TRANSPORT_MODES.join(', ')}`);
  }

  if (!req.citizenship) {
    errors.push('citizenship is required');
  } else if (!VALID_CITIZENSHIP.includes(req.citizenship)) {
    errors.push(`citizenship must be one of: ${VALID_CITIZENSHIP.join(', ')}`);
  }

  if (req.monthlyIncomeSGD === undefined || req.monthlyIncomeSGD === null) {
    errors.push('monthlyIncomeSGD is required (use 0 for no income)');
  } else if (typeof req.monthlyIncomeSGD !== 'number' || req.monthlyIncomeSGD < 0) {
    errors.push('monthlyIncomeSGD must be a non-negative number');
  }

  return { ok: errors.length === 0, errors };
}
