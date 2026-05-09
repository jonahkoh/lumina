# WhatsApp Call Service

FastAPI microservice for Twilio WhatsApp messaging and scheduled outbound Voice calls.

## Capabilities

- Send immediate WhatsApp messages through Twilio.
- Receive Twilio WhatsApp webhooks and guide users through scheduling a call.
- Persist contacts, conversation sessions, outbound messages, scheduled calls, and Twilio webhook events in Postgres.
- Run an API process and a separate worker process.
- Execute due calls with Twilio Voice and return TwiML that plays one configured static audio URL.

Twilio `<Play>` does not support MP4 audio directly. Configure `TWILIO_STATIC_CALL_AUDIO_URL` as a public MP3/WAV/AIFF/GSM/u-law URL.

## Local Run

From the repository root:

```powershell
docker compose up --build whatsapp-call-api whatsapp-call-worker postgres
```

The API listens on `http://localhost:8001`.

For local Twilio webhooks, expose the API with a tunnel and set:

```text
PUBLIC_BASE_URL=https://your-tunnel-host
TWILIO_STATIC_CALL_AUDIO_URL=https://your-tunnel-host/assets/appointment_test.mp3
```

Configure these Twilio webhook URLs:

- WhatsApp inbound: `POST {PUBLIC_BASE_URL}/webhooks/twilio/whatsapp`
- Message status callback: `POST {PUBLIC_BASE_URL}/webhooks/twilio/message/status`
- Voice status callback is attached when the worker creates calls.

## REST API

```http
POST /api/v1/messages/send
Content-Type: application/json

{
  "to": "+15551234567",
  "body": "Hello from Lumina"
}
```

```http
POST /api/v1/calls/schedule
Content-Type: application/json

{
  "to": "+15551234567",
  "scheduled_at": "2026-05-09T15:30:00+08:00"
}
```

If `audio_url` is omitted, the service uses `TWILIO_STATIC_CALL_AUDIO_URL`.

## WhatsApp Bot Flow

1. User sends `schedule call`.
2. Bot asks for the recipient phone number in E.164 format.
3. Bot asks for an ISO timestamp, for example `2026-05-09T15:30:00+08:00`.
4. User replies `YES`.
5. Worker creates the outbound Twilio Voice call when due.

Send `cancel` during the flow to stop, or after scheduling to cancel the latest pending call created by that WhatsApp user.

## Tests

```powershell
cd backend/whatsapp_call_service
python -m pytest
```
