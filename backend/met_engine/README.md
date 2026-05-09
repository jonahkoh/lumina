# MET Engine

Stateless orchestration logic for CareKaki MET.

## Files

```
types.ts          Domain + Kafka payload types
validation.ts     validateBookingRequest (pure)
eligibility.ts    computeSubsidy + applySubsidy (pure)
bot-webhook.ts    notifyBot — POST to bot service
orchestrator.ts   start, stop, 3 caller fns, 3 Kafka subscribers
index.ts          Public API
data/
  aic-subsidy-rules.json
```

## Public API

```typescript
import {
  start, stop,
  handleBookingRequest,
  handleCaregiverConfirm,
  handleCaregiverCancel,
  validateBookingRequest,
  computeSubsidy,
  applySubsidy,
} from 'carekaki-met-engine';
```

## Usage

```typescript
import { start, stop, handleBookingRequest } from 'carekaki-met-engine';

await start();   // connect kafkajs, subscribe to topics, run consumer

const result = await handleBookingRequest(payload);
// { ok: true, tripId: 'trip_xxxxxxxx' }

process.on('SIGTERM', async () => { await stop(); process.exit(0); });
```

## Flow

```
Caller invokes:                Engine publishes:        Engine consumes:
─────────────────              ─────────────────        ────────────────
handleBookingRequest    →      trip.requested
                                                        ← job.offered    → POST bot
                                                        ← trip.no_match  → POST bot

handleCaregiverConfirm  →      trip.book
                                                        ← trip.confirmed → POST bot

handleCaregiverCancel   →      trip.cancelled           (also POST bot directly)
```

`trip.book` carries only `{tripId}` — Transport already has the offer details
from the `job.offered` it published earlier.

## Env vars

```
KAFKA_BROKERS              comma-separated broker URLs
KAFKA_CLIENT_ID            any unique string
KAFKA_GROUP_ID             consumer group
KAFKA_SSL                  default true
KAFKA_SASL_MECHANISM       plain | scram-sha-256 | scram-sha-512 (optional)
KAFKA_SASL_USERNAME        if SASL set
KAFKA_SASL_PASSWORD        if SASL set
BOT_WEBHOOK_URL            where to POST caregiver notifications
BOT_WEBHOOK_SECRET         optional; sent as X-Webhook-Secret
```

## Booking payload

```typescript
{
  elderlyName: string;
  pickup: { postalCode: string; address?, lat?, lng? };
  appointmentDateTime: string;
  mobilityFlags: MobilityFlag[];
  preferredLanguages: Dialect[];
  transportMode: 'driver_only' | 'escort_only' | 'both';
  citizenship: 'sg_citizen' | 'sg_pr' | 'foreigner';
  monthlyIncomeSGD: number;     // PCHI
}
```

## Subsidy computation

For each booking, before publishing, computes:

```typescript
{
  baseSubsidyRate: 0.80,
  interimRebateSGD: 6,
  interimRebateValid: true,
  serviceTier: 'basic_escort_transport',
  ...
}
```

Attached to `trip.requested` so Transport can filter and price.

Worked example: Auntie Tan, SG citizen, PCHI $800, base cost $90 →
**$12 final** (80% subsidy + $6 rebate).
