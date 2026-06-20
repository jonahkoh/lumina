import json
import logging
import platform
import re
import subprocess
import tempfile
from typing import Any
from pathlib import Path

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


OCR_FIELDS = {
    "patient_name",
    "appointment_time",
    "appointment_location",
    "clinic",
    "department",
    "doctor",
}


class OCRService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_error: str | None = None

    def parse_healthhub_screenshot(self, image_url: str) -> dict[str, str | None]:
        self.last_error = None
        if not image_url:
            return {}
        if not (
            self.settings.sea_lion_api_key
            and self.settings.sea_lion_api_url
            and self.settings.sea_lion_vision_model_name
        ):
            logger.info("ocr skipped reason=missing_sea_lion_vision_config")
            self.last_error = "missing_config"
            return self._parse_with_windows_ocr(image_url)

        api_url = self.settings.sea_lion_api_url.strip().strip('"').strip("'")
        if api_url and not api_url.startswith(("http://", "https://")):
            api_url = f"https://{api_url}"

        payload = {
            "model": self.settings.sea_lion_vision_model_name,
            "messages": [
                {
                    "role": "system",
                    "content": self.settings.healthhub_ocr_prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract HealthHub appointment booking details as strict JSON only.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                },
            ],
            "temperature": 0,
            "max_completion_tokens": 800,
        }
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.settings.sea_lion_api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(api_url, headers=headers, json=payload)
                response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            parsed = self._normalize_payload(self._parse_json_content(content))
            if any(parsed.values()):
                return parsed
            return self._parse_with_windows_ocr(image_url)
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            self.last_error = f"http_{status_code}"
            logger.warning("HealthHub OCR failed status=%s response=%s", status_code, exc.response.text[:500])
            return self._parse_with_windows_ocr(image_url)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            self.last_error = exc.__class__.__name__
            logger.warning("HealthHub OCR failed: %s", exc)
            return self._parse_with_windows_ocr(image_url)

    @staticmethod
    def _parse_json_content(content: str) -> dict[str, Any]:
        raw = content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            raw = match.group(0)
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, str | None]:
        normalized: dict[str, str | None] = {}
        for field in OCR_FIELDS:
            value = payload.get(field)
            if value is None:
                normalized[field] = None
            elif isinstance(value, list):
                normalized[field] = ", ".join(str(item).strip() for item in value if str(item).strip()) or None
            else:
                text = str(value).strip()
                normalized[field] = text or None
        return normalized

    def _parse_with_windows_ocr(self, image_url: str) -> dict[str, str | None]:
        if platform.system() != "Windows":
            return {}
        try:
            image_path = self._download_image(image_url)
            lines = _run_windows_ocr(image_path)
            parsed = _parse_healthhub_appointment_lines(lines)
            if any(parsed.values()):
                logger.info("ocr fallback=windows_ocr fields=%s", sorted(k for k, v in parsed.items() if v))
                self.last_error = None
                return parsed
        except Exception as exc:
            logger.warning("Windows OCR fallback failed: %s", exc)
            self.last_error = self.last_error or exc.__class__.__name__
        return {}

    def _download_image(self, image_url: str) -> Path:
        suffix = ".jpg"
        temp_file = tempfile.NamedTemporaryFile(prefix="carekaki_ocr_", suffix=suffix, delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()

        auth = None
        if "api.twilio.com" in image_url and self.settings.twilio_account_sid and self.settings.twilio_auth_token:
            auth = (self.settings.twilio_account_sid, self.settings.twilio_auth_token)

        with httpx.Client(timeout=30, follow_redirects=True, auth=auth) as client:
            response = client.get(image_url)
            response.raise_for_status()
        temp_path.write_bytes(response.content)
        return temp_path


def _run_windows_ocr(image_path: Path) -> list[str]:
    script = r'''
param([string]$Path)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($Operation, [Type]$ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($Operation))
  $netTask.Wait() | Out-Null
  $netTask.Result
}
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$bitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert($bitmap, [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied)
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
if ($null -eq $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$result.Lines | ForEach-Object { $_.Text }
'''
    script_path = Path(tempfile.gettempdir()) / "carekaki_windows_ocr.ps1"
    script_path.write_text(script, encoding="utf-8")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), str(image_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "PowerShell OCR failed")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _parse_healthhub_appointment_lines(lines: list[str]) -> dict[str, str | None]:
    parsed: dict[str, str | None] = {field: None for field in OCR_FIELDS}
    cleaned = [re.sub(r"\s+", " ", line).strip() for line in lines if line.strip()]
    joined = " ".join(cleaned)

    date_match = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d{2})\b", joined)
    if not date_match:
        for index in range(len(cleaned) - 2):
            if cleaned[index].isdigit() and re.fullmatch(r"[A-Za-z]{3,9}", cleaned[index + 1]) and re.fullmatch(r"20\d{2}", cleaned[index + 2]):
                date_match = re.match(r"(.+)", f"{cleaned[index]} {cleaned[index + 1]} {cleaned[index + 2]}")
                break

    time_index = None
    time_value = None
    for index, line in enumerate(cleaned):
        match = re.search(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*,?\s*(\d{1,2}:\d{2}\s*(?:AM|PM))\b", line, re.IGNORECASE)
        if match:
            time_index = index
            time_value = match.group(1).replace(" ", "")
            break

    if date_match and time_value:
        if hasattr(date_match, "group") and date_match.lastindex and date_match.lastindex >= 3:
            parsed["appointment_time"] = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)} {time_value.lower()}"
        else:
            parsed["appointment_time"] = f"{date_match.group(0)} {time_value.lower()}"

    location = None
    for line in cleaned:
        if re.search(r"\b(?:polyclinic|hospital|clinic|medical centre|medical center|healthcare)\b", line, re.IGNORECASE):
            location = line
            break
    if not location and time_index is not None:
        for candidate in reversed(cleaned[:time_index]):
            if candidate.lower() not in {"appointments", "upcoming", "missed", "open"} and not re.fullmatch(r"\d{1,4}|[A-Za-z]{3,9}", candidate):
                location = candidate
                break
    parsed["appointment_location"] = location
    parsed["clinic"] = location

    if time_index is not None and time_index + 1 < len(cleaned):
        department = cleaned[time_index + 1]
        if department.lower() not in {"switch v", "open", "nuhs", "cancel", "reschedule"}:
            parsed["department"] = department

    return parsed
