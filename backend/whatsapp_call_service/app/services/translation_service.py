import hashlib
import logging
import re
from collections import OrderedDict

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


LANGUAGE_MAP = {
    "burmese": "Burmese",
    "english": "English",
    "indonesia": "Indonesian",
    "indonesian": "Indonesian",
    "khmer": "Khmer",
    "lao": "Lao",
    "malay": "Malay",
    "mandarin": "Mandarin Chinese",
    "chinese": "Mandarin Chinese",
    "tagalog": "Tagalog",
    "tamil": "Tamil",
    "thai": "Thai",
    "vietnamese": "Vietnamese",
    "hokkien": "Hokkien",
    "cantonese": "Cantonese",
}


STATIC_TRANSLATIONS = {
    "mandarin": {
        "Welcome to CareKaki. I will help you book escort or transport for an elderly person.": "欢迎使用 CareKaki。我会帮您为长者预约陪诊或交通服务。",
        "What is your name?": "请问您叫什么名字？",
        "What is your relationship to the elderly person? For example child, spouse, helper, neighbour, or volunteer.": "请问您和长者是什么关系？例如子女、配偶、帮佣、邻居或义工。",
        "What is the elderly person's full name?": "请问长者的全名是什么？",
        "Please tell me the elderly person's full name.": "请告诉我长者的全名。",
        "What is the elderly person's phone number? For example +6591234567.": "请问长者的电话号码是多少？例如 +6591234567。",
        "What is the pickup address?": "请问接送地址是什么？",
        "Please provide the pickup address.": "请提供接送地址。",
        "What is the 6-digit postal code?": "请问 6 位邮政编码是什么？",
        "Postal code must be 6 digits. Please try again.": "邮政编码必须是 6 位数字。请再试一次。",
        "What language or dialect does the elderly person prefer? For example English, Mandarin, Malay, Tamil, Hokkien, or Cantonese.": "长者偏好使用什么语言或方言？例如英语、华语、马来语、淡米尔语、福建话或广东话。",
        "Mobility level?": "行动能力需求？",
        "Need transport": "需要交通",
        "Need escort": "需要陪诊",
        "Need both": "两者都需要",
        "Please choose a valid mobility option.": "请选择有效的行动能力选项。",
        "Any optional notes? For example hearing difficulty, dementia, lift access, or 'skip'.": "有其他备注吗？例如听力困难、失智、电梯通行，或回复“skip”跳过。",
        "Please confirm this profile:": "请确认以下资料：",
        "Reply YES to save, or EDIT to restart.": "回复 YES 保存，或回复 EDIT 重新填写。",
        "Reply YES to save this profile, or EDIT to restart.": "回复 YES 保存此资料，或回复 EDIT 重新填写。",
        "Where is the appointment? Reply with the clinic or hospital name and address.": "预约地点在哪里？请回复诊所或医院名称和地址。",
        "Please tell me where the appointment is.": "请告诉我预约地点。",
        "Reply YES to confirm or CANCEL to stop.": "回复 YES 确认，或回复 CANCEL 停止。",
        "Cancelled the current flow.": "已取消当前流程。",
        "Cancelled the scheduling flow.": "已取消预约流程。",
        "What date and time is the appointment? Reply in Singapore time, for example today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm.": "预约日期和时间是什么？请用新加坡时间回复，例如 today 3pm、tomorrow 9:30am，或 9 May 2026 3:30pm。",
        "When is the appointment date? Reply in Singapore time, for example today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm.": "预约日期是什么时候？请用新加坡时间回复，例如 today 3pm、tomorrow 9:30am，或 9 May 2026 3:30pm。",
    },
    "malay": {
        "Welcome to CareKaki. I will help you book escort or transport for an elderly person.": "Selamat datang ke CareKaki. Saya akan membantu anda menempah pengiring atau pengangkutan untuk warga emas.",
        "What is your name?": "Siapakah nama anda?",
        "What is your relationship to the elderly person? For example child, spouse, helper, neighbour, or volunteer.": "Apakah hubungan anda dengan warga emas itu? Contohnya anak, pasangan, pembantu, jiran, atau sukarelawan.",
        "What is the elderly person's full name?": "Apakah nama penuh warga emas itu?",
        "What is the elderly person's phone number? For example +6591234567.": "Apakah nombor telefon warga emas itu? Contohnya +6591234567.",
        "What is the pickup address?": "Apakah alamat pengambilan?",
        "What is the 6-digit postal code?": "Apakah poskod 6 digit?",
        "What language or dialect does the elderly person prefer? For example English, Mandarin, Malay, Tamil, Hokkien, or Cantonese.": "Apakah bahasa atau dialek pilihan warga emas itu? Contohnya Inggeris, Mandarin, Melayu, Tamil, Hokkien, atau Kantonis.",
        "Mobility level?": "Tahap mobiliti?",
        "Need transport": "Perlu pengangkutan",
        "Need escort": "Perlu pengiring",
        "Need both": "Perlu kedua-duanya",
        "Any optional notes? For example hearing difficulty, dementia, lift access, or 'skip'.": "Ada nota tambahan? Contohnya masalah pendengaran, demensia, akses lif, atau 'skip'.",
        "Where is the appointment? Reply with the clinic or hospital name and address.": "Di manakah janji temu itu? Balas dengan nama dan alamat klinik atau hospital.",
    },
    "tamil": {
        "Welcome to CareKaki. I will help you book escort or transport for an elderly person.": "CareKaki-க்கு வரவேற்கிறோம். முதியவருக்கான துணை அல்லது போக்குவரத்தை பதிவு செய்ய நான் உதவுவேன்.",
        "What is your name?": "உங்கள் பெயர் என்ன?",
        "What is the elderly person's full name?": "முதியவரின் முழுப் பெயர் என்ன?",
        "What is the elderly person's phone number? For example +6591234567.": "முதியவரின் தொலைபேசி எண் என்ன? உதாரணம் +6591234567.",
        "What is the pickup address?": "அழைத்துச் செல்ல வேண்டிய முகவரி என்ன?",
        "What is the 6-digit postal code?": "6 இலக்க அஞ்சல் குறியீடு என்ன?",
        "Mobility level?": "நடமாட்ட உதவி தேவை?",
        "Need transport": "போக்குவரத்து தேவை",
        "Need escort": "துணை தேவை",
        "Need both": "இரண்டும் தேவை",
        "Where is the appointment? Reply with the clinic or hospital name and address.": "சந்திப்பு எங்கு உள்ளது? மருத்துவமனை அல்லது கிளினிக் பெயர் மற்றும் முகவரியை அனுப்பவும்.",
    },
}


STATIC_TEMPLATE_TRANSLATIONS = {
    "mandarin": [
        (r"Profile saved\. Book escort or transport for (.+)\.", "资料已保存。为 {0} 预约陪诊或交通服务。"),
        (r"Book an appointment for (.+)\.", "为 {0} 预约。"),
        (r"Confirm appointment for (.+) at (.+)\. Appointment place: (.+)\. We will call the caregiver 2 hours before at (.+) to remind them that the elderly person has an appointment today\. Reply YES to confirm or CANCEL to stop\.", "请确认 {0} 在 {1} 的预约。预约地点：{2}。我们会在 {3}，也就是预约前 2 小时，打电话提醒照护者长者今天有预约。回复 YES 确认，或回复 CANCEL 停止。"),
        (r"Appointment confirmed for (.+) at (.+)\. We will call the caregiver at (.+)\.", "已确认 {0} 在 {1} 的预约。我们会在 {2} 打电话给照护者。"),
        (r"Caregiver: (.+)", "照护者：{0}"),
        (r"Caregiver phone: (.+)", "照护者电话：{0}"),
        (r"Relationship: (.+)", "关系：{0}"),
        (r"Elderly: (.+)", "长者：{0}"),
        (r"Elderly phone: (.+)", "长者电话：{0}"),
        (r"Pickup: (.+)", "接送地址：{0}"),
        (r"Language/dialect: (.+)", "语言/方言：{0}"),
        (r"Mobility: (.+)", "行动需求：{0}"),
        (r"Notes: (.+)", "备注：{0}"),
    ],
    "malay": [
        (r"Profile saved\. Book escort or transport for (.+)\.", "Profil disimpan. Tempah pengiring atau pengangkutan untuk {0}."),
        (r"Book an appointment for (.+)\.", "Tempah janji temu untuk {0}."),
    ],
    "tamil": [
        (r"Profile saved\. Book escort or transport for (.+)\.", "சுயவிவரம் சேமிக்கப்பட்டது. {0} அவர்களுக்கு துணை அல்லது போக்குவரத்தை பதிவு செய்யுங்கள்."),
        (r"Book an appointment for (.+)\.", "{0} அவர்களுக்கு சந்திப்பை பதிவு செய்யுங்கள்."),
    ],
}


EXTRA_STATIC_TRANSLATIONS = {
    "mandarin": {
        "Reset complete. I removed your saved bot profile data and conversation.": "\u91cd\u7f6e\u5b8c\u6210\u3002\u6211\u5df2\u5220\u9664\u60a8\u4fdd\u5b58\u7684\u673a\u5668\u4eba\u8d44\u6599\u548c\u5bf9\u8bdd\u3002",
        "What language should we use with you?": "\u8bf7\u95ee\u60a8\u60f3\u7528\u4ec0\u4e48\u8bed\u8a00\uff1f",
        "English": "\u82f1\u8bed",
        "Mandarin": "\u534e\u8bed",
        "Malay": "\u9a6c\u6765\u8bed",
        "Tamil": "\u6de1\u7c73\u5c14\u8bed",
    },
    "malay": {
        "Reset complete. I removed your saved bot profile data and conversation.": "Tetapan semula selesai. Saya telah memadam data profil bot dan perbualan anda yang disimpan.",
        "What language should we use with you?": "Bahasa apakah yang patut kami gunakan dengan anda?",
        "English": "Bahasa Inggeris",
        "Mandarin": "Mandarin",
        "Malay": "Bahasa Melayu",
        "Tamil": "Tamil",
        "Please choose a language option.": "Sila pilih pilihan bahasa.",
        "Please choose a valid mobility option.": "Sila pilih pilihan mobiliti yang sah.",
        "Please confirm this profile:": "Sila sahkan profil ini:",
        "Reply YES to save, or EDIT to restart.": "Balas YES untuk simpan, atau EDIT untuk mula semula.",
        "Reply YES to save this profile, or EDIT to restart.": "Balas YES untuk simpan profil ini, atau EDIT untuk mula semula.",
        "Please tell me where the appointment is.": "Sila beritahu saya di mana janji temu itu.",
        "Reply YES to confirm or CANCEL to stop.": "Balas YES untuk sahkan atau CANCEL untuk berhenti.",
        "Cancelled the current flow.": "Aliran semasa telah dibatalkan.",
        "Cancelled the scheduling flow.": "Aliran penjadualan telah dibatalkan.",
        "What date and time is the appointment? Reply in Singapore time, for example today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm.": "Apakah tarikh dan masa janji temu? Balas dalam masa Singapura, contohnya today 3pm, tomorrow 9:30am, atau 9 May 2026 3:30pm.",
        "When is the appointment date? Reply in Singapore time, for example today 3pm, tomorrow 9:30am, or 9 May 2026 3:30pm.": "Bilakah tarikh janji temu? Balas dalam masa Singapura, contohnya today 3pm, tomorrow 9:30am, atau 9 May 2026 3:30pm.",
    },
    "tamil": {
        "Reset complete. I removed your saved bot profile data and conversation.": "\u0bae\u0bc0\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0b9f\u0bbf\u0ba8\u0bcd\u0ba4\u0ba4\u0bc1. \u0b9a\u0bc7\u0bae\u0bbf\u0ba4\u0bcd\u0ba4 \u0baa\u0bca\u0b9f\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bc8\u0baf\u0bbe\u0b9f\u0bb2\u0bcd \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba9.",
        "What language should we use with you?": "\u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b8e\u0ba8\u0bcd\u0ba4 \u0bae\u0bca\u0bb4\u0bbf\u0baf\u0bc8 \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4 \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd?",
        "English": "\u0b86\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bae\u0bcd",
        "Mandarin": "\u0bae\u0bbe\u0ba3\u0bcd\u0b9f\u0bb0\u0bbf\u0ba9\u0bcd",
        "Malay": "\u0bae\u0bb2\u0bbe\u0baf\u0bcd",
        "Tamil": "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd",
    },
}


EXTRA_STATIC_TEMPLATE_TRANSLATIONS = {
    "malay": [
        (r"Confirm appointment for (.+) at (.+)\. Appointment place: (.+)\. We will call the caregiver 2 hours before at (.+) to remind them that the elderly person has an appointment today\. Reply YES to confirm or CANCEL to stop\.", "Sahkan janji temu untuk {0} pada {1}. Tempat janji temu: {2}. Kami akan menghubungi penjaga 2 jam sebelum pada {3} untuk mengingatkan bahawa warga emas mempunyai janji temu hari ini. Balas YES untuk sahkan atau CANCEL untuk berhenti."),
        (r"Appointment confirmed for (.+) at (.+)\. We will call the caregiver at (.+)\.", "Janji temu untuk {0} pada {1} telah disahkan. Kami akan menghubungi penjaga pada {2}."),
        (r"Caregiver: (.+)", "Penjaga: {0}"),
        (r"Caregiver phone: (.+)", "Telefon penjaga: {0}"),
        (r"Relationship: (.+)", "Hubungan: {0}"),
        (r"Elderly: (.+)", "Warga emas: {0}"),
        (r"Elderly phone: (.+)", "Telefon warga emas: {0}"),
        (r"Pickup: (.+)", "Alamat pengambilan: {0}"),
        (r"Language/dialect: (.+)", "Bahasa/dialek: {0}"),
        (r"Mobility: (.+)", "Mobiliti: {0}"),
        (r"Notes: (.+)", "Nota: {0}"),
    ],
}


class TranslationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: OrderedDict[str, str] = OrderedDict()

    def translate(self, text: str, target_language: str | None) -> str:
        normalized_language = self.normalize_language(target_language)
        if not text or normalized_language == "english":
            return text

        key = self.cache_key(text, normalized_language)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            logger.info("translation cache_hit language=%s chars=%d", normalized_language, len(text))
            return cached

        translated = self._translate_static(text, normalized_language)
        if translated:
            logger.info("translation static language=%s chars=%d", normalized_language, len(text))
        else:
            translated = self._translate_via_sea_lion(text, normalized_language)
            if translated:
                logger.info("translation sea_lion language=%s chars=%d", normalized_language, len(text))
            else:
                logger.info("translation fallback_english language=%s chars=%d", normalized_language, len(text))
                translated = text
        self._store(key, translated)
        return translated

    def translate_options(self, options: list[str], target_language: str | None) -> list[str]:
        return [self.translate(option, target_language) for option in options]

    @staticmethod
    def normalize_language(value: str | None) -> str:
        return (value or "english").strip().lower() or "english"

    @classmethod
    def cache_key(cls, text: str, target_language: str | None) -> str:
        language = cls.normalize_language(target_language)
        digest = hashlib.sha256(f"{language}\n{text}".encode("utf-8")).hexdigest()
        return f"{language}:{digest}"

    def _store(self, key: str, value: str) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self.settings.translation_cache_max_size:
            self._cache.popitem(last=False)

    @staticmethod
    def _translate_static(text: str, target_language: str) -> str | None:
        exact = EXTRA_STATIC_TRANSLATIONS.get(target_language, {}).get(text)
        if exact:
            return exact
        exact = STATIC_TRANSLATIONS.get(target_language, {}).get(text)
        if exact:
            return exact
        for pattern, replacement in EXTRA_STATIC_TEMPLATE_TRANSLATIONS.get(target_language, []):
            match = re.fullmatch(pattern, text)
            if match:
                return replacement.format(*match.groups())
        for pattern, replacement in STATIC_TEMPLATE_TRANSLATIONS.get(target_language, []):
            match = re.fullmatch(pattern, text)
            if match:
                return replacement.format(*match.groups())
        return None

    def _translate_via_sea_lion(self, text: str, target_language: str) -> str | None:
        if not (
            self.settings.sea_lion_api_key
            and self.settings.sea_lion_api_url
            and self.settings.sea_lion_model_name
        ):
            return None

        language_name = LANGUAGE_MAP.get(target_language, target_language)
        api_url = self.settings.sea_lion_api_url.strip().strip('"').strip("'")
        if api_url and not api_url.startswith(("http://", "https://")):
            api_url = f"https://{api_url}"

        payload = {
            "model": self.settings.sea_lion_model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a translation assistant. Translate the user's message to "
                        f"{language_name}. Output ONLY the translated text, no explanations, "
                        "no quotation marks."
                    ),
                },
                {"role": "user", "content": f"Translate this to {language_name}: {text}"},
            ],
            "max_completion_tokens": 1024,
            "temperature": 0.2,
        }
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.settings.sea_lion_api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(api_url, headers=headers, json=payload)
                response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip() or None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("SEA-LION translation failed for %s: %s", target_language, exc)
            return None
