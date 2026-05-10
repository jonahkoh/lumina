# WhatsApp Call Service

FastAPI microservice for Twilio WhatsApp messaging and scheduled outbound Voice calls.

## Capabilities

- Collect CareKaki caregiver and elderly profiles through WhatsApp.
- Assume the WhatsApp user is a caregiver booking escort or transport for an elderly person.
- Send immediate WhatsApp messages through Twilio.
- Receive Twilio WhatsApp webhooks and guide users through scheduling a call.
- Persist contacts, caregiver profiles, elderly profiles, caregiver-elderly links, conversation sessions, outbound messages, scheduled calls, and Twilio webhook events in a local SQLite database.
- Run an API process and a separate worker process.
- Execute due calls with Twilio Voice and return TwiML that plays one configured static audio URL or a generated ElevenLabs audio clip.
- Translate chatbot messages, scheduled WhatsApp reminders, and outbound call text with SEA-LION when a user has a non-English preferred language.
- Parse HealthHub screenshots with SEA-LION vision to prefill appointment time and place during booking.
- Cache common translations and generated audio clips to reduce repeat SEA-LION and ElevenLabs calls.

Twilio `<Play>` does not support MP4 audio directly. Configure `TWILIO_STATIC_CALL_AUDIO_URL` as a public MP3/WAV/AIFF/GSM/u-law URL.

## Local Run

From the repository root:

```powershell
cd backend/whatsapp_call_service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

The API listens on `http://localhost:8002` and uses `local_whatsapp_call_service.db` by default.

To run the call worker in a second terminal:

```powershell
cd backend/whatsapp_call_service
python -m app.worker
```

For local Twilio webhooks, expose the API with a tunnel and set:

```text
PUBLIC_BASE_URL=https://your-tunnel-host
TWILIO_STATIC_CALL_AUDIO_URL=https://your-tunnel-host/assets/appointment_test.mp3
```

Optional translation and audio settings:

```text
SEA_LION_API_KEY=...
SEA_LION_API_URL=...
SEA_LION_MODEL_NAME=...
SEA_LION_VISION_MODEL_NAME=Qwen-SEA-LION-v4-8B-VL
ELEVENLABS_API_KEY=...
AUDIO_CACHE_DIR=assets/audio_cache
```

The service also accepts the existing `API_KEY`, `API_URL`, and `MODEL_NAME` environment variable names used by `backend/bot/translation.py`.

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
  "scheduled_at": "2026-05-09T15:30:00+08:00",
  "appointment_location": "Singapore General Hospital"
}
```

If `audio_url` is omitted, the service uses `TWILIO_STATIC_CALL_AUDIO_URL`.

## CareKaki WhatsApp Profile Flow

New users are asked:

```text
What language should we use with you?
1. English
2. Mandarin
3. Malay
4. Tamil
```

Caregiver path:

1. Save the WhatsApp sender number as the caregiver phone.
2. Ask caregiver name and relationship to the elderly person.
3. Ask elderly name and elderly phone number.
4. Ask pickup address, postal code, preferred language/dialect, mobility level, and optional notes.
5. Save caregiver profile, elderly profile, and caregiver-elderly link.
6. Immediately ask for the appointment date/time and destination to book escort or transport.

After registration, normal messages start appointment booking. Caregivers are asked to choose one of their saved elderly profiles before the appointment date/time and destination are collected.

Mobility options are:

```text
Mobility level?
1. Need transport
2. Need escort
3. Need both
```

Existing commands:

- `profile`: show saved profile.
- `add elderly`: caregivers can add another elderly profile.
- `edit profile`: explains how to restart profile entry.
- `schedule`: start the existing call scheduling flow.
- `/reset`: remove your saved bot profile data, conversation state, and pending reminder calls, then start again.

If a caregiver sends a HealthHub screenshot during appointment booking, the bot attempts OCR extraction for the appointment time and place. It does not create or update elderly profiles from OCR. If multiple elderly profiles exist, the caregiver chooses the profile first, then the screenshot is used to prefill the booking confirmation.

WhatsApp button templates are optional. Configure Content SIDs if available; numbered text fallback always works.

## Appointment Booking Flow

1. User sends `book` or completes a new elderly profile.
2. Bot asks for the recipient phone number, for example `+6591234567`.
3. Bot asks for a Singapore time, for example `today 3pm`, `tomorrow 9:30am`, or `9 May 2026 3:30pm`.
4. Bot asks where the appointment is, for example the clinic or hospital name and address.
5. Bot asks for the appointment type, for example `non-fasting lab`, `cardiology review`, or `eye clinic`.
6. Bot asks whether support is `Escort`, `Driver`, or `Both escort and driver`.
7. User replies `YES`.
8. Worker sends a localized WhatsApp reminder and creates the caregiver reminder call. For local testing, the actual call is scheduled 30 seconds after confirmation while the WhatsApp copy still says the reminder is 2 hours before the appointment.

Instead of typing steps 3 to 5 manually, the caregiver can upload a HealthHub appointment screenshot after choosing the elderly profile. SEA-LION vision or the local Windows OCR fallback extracts the appointment time, place, and appointment type when those fields are visible.

Send `cancel` during the flow to stop, or after scheduling to cancel the latest pending call created by that WhatsApp user.

## Profile API

- `GET /api/v1/profiles/contacts/by-phone/{phone}`
- `GET /api/v1/profiles/contacts/{contact_id}`
- `POST /api/v1/profiles/caregivers`
- `POST /api/v1/profiles/elderly`
- `POST /api/v1/profiles/links`
- `GET /api/v1/profiles/caregivers/{caregiver_id}/elderly`

## Tests

```powershell
cd backend/whatsapp_call_service
python -m pytest
```
