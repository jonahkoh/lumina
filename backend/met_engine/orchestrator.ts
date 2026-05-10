/**
 * MET Engine — Orchestrator
 *
 * Stateless. Uses kafkajs directly. No local state, no audit log.
 *
 * Caller-invoked (your gateway / bot router calls these):
 *   handleBookingRequest(req)
 *   handleCaregiverConfirm(tripId)
 *   handleCaregiverCancel(tripId)
 *
 * Kafka subscribers (auto-dispatched from consumer.run):
 *   on job.offered      → POST to bot
 *   on trip.no_match    → POST to bot
 *   on trip.confirmed   → POST to bot
 *
 * Lifecycle:
 *   await start()    — connect, subscribe, run consumer
 *   await stop()     — graceful shutdown for SIGTERM
 */

import { randomUUID } from 'crypto';
import { Kafka, Producer, Consumer, SASLOptions, logLevel } from 'kafkajs';

import {
  BookingRequest,
  KafkaTopic,
  KafkaEvent,
  TripRequestedPayload,
  TripBookPayload,
  TripCancelledPayload,
  JobOfferedPayload,
  TripConfirmedPayload,
  TripNoMatchPayload,
} from './types';
import { validateBookingRequest } from './validation';
import { computeSubsidy } from './eligibility';
import { notifyBot } from './bot-webhook';

// =============================================================================
// KAFKAJS SETUP (module-level)
// =============================================================================

let producer: Producer | null = null;
let consumer: Consumer | null = null;

function getRequired(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

function buildSasl(): SASLOptions | undefined {
  const mechanism = process.env.KAFKA_SASL_MECHANISM as
    | 'plain'
    | 'scram-sha-256'
    | 'scram-sha-512'
    | undefined;
  if (!mechanism) return undefined;
  return {
    mechanism,
    username: getRequired('KAFKA_SASL_USERNAME'),
    password: getRequired('KAFKA_SASL_PASSWORD'),
  };
}

const SUBSCRIBED_TOPICS: KafkaTopic[] = [
  'job.offered',
  'trip.no_match',
  'trip.confirmed',
];

export async function start(): Promise<void> {
  const kafka = new Kafka({
    clientId: getRequired('KAFKA_CLIENT_ID'),
    brokers: getRequired('KAFKA_BROKERS').split(',').map(s => s.trim()),
    ssl: process.env.KAFKA_SSL !== 'false',
    sasl: buildSasl(),
    logLevel: logLevel.WARN,
  });

  producer = kafka.producer({ allowAutoTopicCreation: false });
  consumer = kafka.consumer({ groupId: getRequired('KAFKA_GROUP_ID') });

  await producer.connect();
  await consumer.connect();

  for (const topic of SUBSCRIBED_TOPICS) {
    await consumer.subscribe({ topic, fromBeginning: false });
  }

  await consumer.run({
    eachMessage: async ({ topic, message }) => {
      if (!message.value) return;
      try {
        const event = JSON.parse(message.value.toString()) as KafkaEvent;
        switch (topic as KafkaTopic) {
          case 'job.offered':
            await onJobOffered(event as KafkaEvent<JobOfferedPayload>);
            break;
          case 'trip.no_match':
            await onTripNoMatch(event as KafkaEvent<TripNoMatchPayload>);
            break;
          case 'trip.confirmed':
            await onTripConfirmed(event as KafkaEvent<TripConfirmedPayload>);
            break;
        }
      } catch (err) {
        console.error(`[MET-ENGINE] handler error on ${topic}:`, err);
      }
    },
  });
}

export async function stop(): Promise<void> {
  await consumer?.disconnect();
  await producer?.disconnect();
  consumer = null;
  producer = null;
}

async function publish<T>(topic: KafkaTopic, key: string, payload: T): Promise<void> {
  if (!producer) throw new Error('start() the engine first');
  const event: KafkaEvent<T> = {
    topic,
    key,
    payload,
    publishedAt: new Date().toISOString(),
    version: 1,
  };
  await producer.send({
    topic,
    messages: [{ key, value: JSON.stringify(event) }],
  });
}

// =============================================================================
// CALLER-INVOKED
// =============================================================================

export interface BookingResult {
  ok: boolean;
  tripId?: string;
  errors?: string[];
}

export async function handleBookingRequest(
  request: BookingRequest
): Promise<BookingResult> {
  const validation = validateBookingRequest(request);
  if (!validation.ok) {
    return { ok: false, errors: validation.errors };
  }

  const subsidy = computeSubsidy({
    citizenship: request.citizenship,
    monthlyIncomeSGD: request.monthlyIncomeSGD,
    transportMode: request.transportMode,
  });

  const tripId = `trip_${randomUUID().slice(0, 8)}`;

  await notifyBot({
    tripId,
    type: 'matching_started',
    message:
      `Got it! Searching for the right escort and transport for ` +
      `${request.elderlyName}'s appointment. Booking ref: ${tripId}`,
    data: {
      elderlyName: request.elderlyName,
      subsidyRate: subsidy.baseSubsidyRate,
      interimRebateSGD: subsidy.interimRebateValid ? subsidy.interimRebateSGD : 0,
    },
    sentAt: new Date().toISOString(),
  });

  const payload: TripRequestedPayload = {
    tripId,
    elderlyName: request.elderlyName,
    pickup: request.pickup,
    appointmentDateTime: request.appointmentDateTime,
    mobilityFlags: request.mobilityFlags,
    preferredLanguages: request.preferredLanguages,
    transportMode: request.transportMode,
    subsidy,
    requestedAt: new Date().toISOString(),
  };

  await publish('trip.requested', tripId, payload);
  return { ok: true, tripId };
}

export async function handleCaregiverConfirm(tripId: string): Promise<{ ok: boolean }> {
  const payload: TripBookPayload = {
    tripId,
    bookedAt: new Date().toISOString(),
  };
  await publish('trip.book', tripId, payload);
  return { ok: true };
}

export async function handleCaregiverCancel(tripId: string): Promise<{ ok: boolean }> {
  const payload: TripCancelledPayload = {
    tripId,
    cancelledBy: 'caregiver',
    cancelledAt: new Date().toISOString(),
  };
  await publish('trip.cancelled', tripId, payload);

  await notifyBot({
    tripId,
    type: 'booking_cancelled',
    message: `Booking ${tripId} cancelled.`,
    sentAt: new Date().toISOString(),
  });

  return { ok: true };
}

// =============================================================================
// SUBSCRIBERS
// =============================================================================

async function onJobOffered(event: KafkaEvent<JobOfferedPayload>): Promise<void> {
  const p = event.payload;
  await notifyBot({
    tripId: p.tripId,
    type: 'recommendation_ready',
    message:
      `We found a match!\n\n` +
      `Driver: ${p.driverName}\n` +
      `Escort: ${p.escortName}\n` +
      `Vehicle: ${p.vehicleType}\n` +
      `ETA: ${new Date(p.pickupETA).toLocaleTimeString('en-SG')}\n` +
      `Final price (after subsidy): S$${p.finalPriceSGD.toFixed(2)}\n` +
      `Provider: ${p.ngoName}\n\n` +
      `Reply CONFIRM to accept or CANCEL to decline. Booking ref: ${p.tripId}`,
    data: {
      driverId: p.driverId,
      driverName: p.driverName,
      escortId: p.escortId,
      escortName: p.escortName,
      vehicleType: p.vehicleType,
      estimatedPriceSGD: p.estimatedPriceSGD,
      finalPriceSGD: p.finalPriceSGD,
      pickupETA: p.pickupETA,
      ngoId: p.ngoId,
      ngoName: p.ngoName,
    },
    sentAt: new Date().toISOString(),
  });
}

async function onTripNoMatch(event: KafkaEvent<TripNoMatchPayload>): Promise<void> {
  const p = event.payload;
  await notifyBot({
    tripId: p.tripId,
    type: 'no_match_available',
    message:
      `Sorry — we couldn't find an available escort and transport right now. ` +
      `Try a different appointment time. Booking ref: ${p.tripId}`,
    data: { reason: p.reason, retriesAttempted: p.retriesAttempted },
    sentAt: new Date().toISOString(),
  });
}

async function onTripConfirmed(event: KafkaEvent<TripConfirmedPayload>): Promise<void> {
  const p = event.payload;
  await notifyBot({
    tripId: p.tripId,
    type: 'trip_confirmed',
    message:
      `✅ Booking confirmed!\n\n` +
      `Pickup ETA: ${new Date(p.pickupETA).toLocaleTimeString('en-SG')}\n` +
      `Final price: S$${p.finalPriceSGD.toFixed(2)}`,
    data: {
      driverId: p.driverId,
      escortId: p.escortId,
      finalPriceSGD: p.finalPriceSGD,
      pickupETA: p.pickupETA,
      appointmentDateTime: p.appointmentDateTime,
    },
    sentAt: new Date().toISOString(),
  });
}
