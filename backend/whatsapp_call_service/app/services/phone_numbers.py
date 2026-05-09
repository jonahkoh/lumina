import re


class PhoneNumberError(ValueError):
    pass


def normalize_e164(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("whatsapp:"):
        cleaned = cleaned.removeprefix("whatsapp:")

    cleaned = re.sub(r"[\s().-]", "", cleaned)
    if not cleaned.startswith("+"):
        raise PhoneNumberError("Phone number must be in E.164 format, for example +15551234567")

    if not re.fullmatch(r"\+[1-9]\d{7,14}", cleaned):
        raise PhoneNumberError("Phone number must include country code and 8 to 15 digits")

    return cleaned


def to_whatsapp_address(value: str) -> str:
    return f"whatsapp:{normalize_e164(value)}"
