/**
 * MET Engine — Public API
 *
 * Usage:
 *
 *   import {
 *     start, stop,
 *     handleBookingRequest,
 *     handleCaregiverConfirm,
 *     handleCaregiverCancel,
 *   } from 'carekaki-met-engine';
 *
 *   await start();
 *   const r = await handleBookingRequest(payload);
 *   ...
 *   await stop();   // SIGTERM handler
 */

export {
  start,
  stop,
  handleBookingRequest,
  handleCaregiverConfirm,
  handleCaregiverCancel,
  type BookingResult,
} from './orchestrator';

// Pure functions, importable independently
export { validateBookingRequest } from './validation';
export { computeSubsidy, applySubsidy } from './eligibility';

// Types
export * from './types';
