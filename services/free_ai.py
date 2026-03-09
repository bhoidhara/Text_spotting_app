import io
import os

import requests
from gtts import gTTS


def translate_text(text: str, target_lang: str):
    base_url = os.getenv("LIBRETRANSLATE_URL", "https://libretranslate.de").rstrip("/")
    api_key = os.getenv("LIBRETRANSLATE_API_KEY")

    payload = {
        "q": text,
        "source": "auto",
        "target": target_lang,
        "format": "text",
    }
    if api_key:
        payload["api_key"] = api_key

    response = requests.post(f"{base_url}/translate", data=payload, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(response.text)

    data = response.json()
    translated = data.get("translatedText", "")
    detected = None
    detected_info = data.get("detectedLanguage") or {}
    if isinstance(detected_info, dict):
        detected = detected_info.get("language")

    return translated, detected


def synthesize_speech(text: str, language_code: str = "en") -> bytes:
    tts = gTTS(text=text, lang=language_code)
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    buffer.seek(0)
    return buffer.read()
