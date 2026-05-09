from dataclasses import dataclass
import json
from typing import Any

from fastapi import Request
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from app.config import Settings
from app.services.phone_numbers import normalize_e164, to_whatsapp_address


@dataclass(frozen=True)
class TwilioResult:
    sid: str
    status: str | None = None


class TwilioService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        return self._client

    def send_whatsapp_message(self, to: str, body: str) -> TwilioResult:
        return self._send_whatsapp(to=to, body=body)

    def send_whatsapp_template(
        self,
        to: str,
        body_fallback: str,
        content_sid: str | None = None,
        content_variables: dict[str, Any] | None = None,
    ) -> TwilioResult:
        return self._send_whatsapp(
            to=to,
            body=body_fallback,
            content_sid=content_sid,
            content_variables=content_variables,
        )

    def _send_whatsapp(
        self,
        to: str,
        body: str,
        content_sid: str | None = None,
        content_variables: dict[str, Any] | None = None,
    ) -> TwilioResult:
        kwargs: dict[str, Any] = {
            "from_": to_whatsapp_address(self.settings.whatsapp_sender_phone_number),
            "to": to_whatsapp_address(to),
            "status_callback": f"{self.settings.public_base_url.rstrip('/')}/webhooks/twilio/message/status",
        }
        if content_sid:
            kwargs["content_sid"] = content_sid
            if content_variables:
                kwargs["content_variables"] = json.dumps(content_variables)
        else:
            kwargs["body"] = body

        message = self.client.messages.create(
            **kwargs,
        )
        return TwilioResult(sid=message.sid, status=getattr(message, "status", None))

    def create_outbound_call(self, to: str, scheduled_call_id: str) -> TwilioResult:
        base_url = self.settings.public_base_url.rstrip("/")
        call = self.client.calls.create(
            to=normalize_e164(to),
            from_=normalize_e164(self.settings.twilio_from_phone_number),
            url=f"{base_url}/twiml/calls/{scheduled_call_id}",
            method="POST",
            status_callback=f"{base_url}/webhooks/twilio/voice/status",
            status_callback_method="POST",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )
        return TwilioResult(sid=call.sid, status=getattr(call, "status", None))

    def build_play_twiml(self, audio_url: str) -> str:
        response = VoiceResponse()
        response.play(audio_url)
        return str(response)

    async def validate_request(self, request: Request, form: dict[str, Any]) -> bool:
        if not self.settings.validate_twilio_signatures:
            return True

        signature = request.headers.get("X-Twilio-Signature", "")
        validator = RequestValidator(self.settings.twilio_auth_token)
        return validator.validate(str(request.url), form, signature)
