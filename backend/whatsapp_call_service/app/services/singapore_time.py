import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


TIME_PATTERN = re.compile(r"^(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<period>am|pm)$", re.IGNORECASE)
DATE_TIME_PATTERN = re.compile(
    r"^(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})\s+"
    r"(?P<time>\d{1,2}(?::\d{2})?\s*(?:am|pm))$",
    re.IGNORECASE,
)
RELATIVE_TIME_PATTERN = re.compile(
    r"^(?P<relative>today|tomorrow)\s+(?P<time>\d{1,2}(?::\d{2})?\s*(?:am|pm))$",
    re.IGNORECASE,
)


class SingaporeTimeParseError(ValueError):
    pass


def parse_singapore_time(value: str, timezone_name: str = "Asia/Singapore", now: datetime | None = None) -> datetime:
    text = value.strip()
    tz = ZoneInfo(timezone_name)
    reference = now.astimezone(tz) if now and now.tzinfo else (now.replace(tzinfo=tz) if now else datetime.now(tz))

    relative_match = RELATIVE_TIME_PATTERN.fullmatch(text)
    if relative_match:
        day = reference.date()
        if relative_match.group("relative").lower() == "tomorrow":
            day += timedelta(days=1)
        hour, minute = _parse_time(relative_match.group("time"))
        return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)

    date_match = DATE_TIME_PATTERN.fullmatch(text)
    if date_match:
        month = MONTHS.get(date_match.group("month").lower())
        if month is None:
            raise SingaporeTimeParseError("Unknown month")
        hour, minute = _parse_time(date_match.group("time"))
        try:
            return datetime(
                int(date_match.group("year")),
                month,
                int(date_match.group("day")),
                hour,
                minute,
                tzinfo=tz,
            )
        except ValueError as exc:
            raise SingaporeTimeParseError(str(exc)) from exc

    raise SingaporeTimeParseError("Use examples like today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm.")


def _parse_time(value: str) -> tuple[int, int]:
    match = TIME_PATTERN.fullmatch(value.strip())
    if match is None:
        raise SingaporeTimeParseError("Invalid time")

    hour = int(match.group("hour"))
    minute = int(match.group("minute") or "0")
    period = match.group("period").lower()
    if hour < 1 or hour > 12 or minute > 59:
        raise SingaporeTimeParseError("Invalid time")
    if period == "am":
        hour = 0 if hour == 12 else hour
    else:
        hour = 12 if hour == 12 else hour + 12
    return hour, minute
