import os
import re

from utils.helpers import safe_int

try:
    from PIL import ImageFilter, ImageOps
except Exception:
    ImageFilter = None
    ImageOps = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from langdetect import detect as detect_lang
except Exception:
    detect_lang = None

try:
    from spellchecker import SpellChecker
except Exception:
    SpellChecker = None


def preprocess_image(image):
    if ImageOps:
        image = ImageOps.grayscale(image)
    if ImageFilter:
        image = image.filter(ImageFilter.MedianFilter(size=3))
    return image


def ocr_image(image, lang="eng"):
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed.")

    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    processed = preprocess_image(image)
    text = pytesseract.image_to_string(processed, lang=lang)

    try:
        data = pytesseract.image_to_data(processed, lang=lang, output_type=pytesseract.Output.DICT)
    except Exception:
        data = {"text": [], "conf": []}

    conf_values = []
    low_conf_words = []
    for word, conf in zip(data.get("text", []), data.get("conf", [])):
        conf_value = safe_int(conf, -1)
        if conf_value >= 0:
            conf_values.append(conf_value)
            if conf_value < 60 and word.strip():
                low_conf_words.append(word.strip())

    avg_conf = round(sum(conf_values) / len(conf_values), 2) if conf_values else 0.0

    return text, avg_conf, low_conf_words


def clean_text(text):
    text = text.replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    cleaned_lines = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line.endswith("-") and idx + 1 < len(lines):
            line = line[:-1] + lines[idx + 1].lstrip()
            idx += 1
        cleaned_lines.append(line)
        idx += 1

    normalized = []
    previous_blank = False
    for line in cleaned_lines:
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            if not previous_blank:
                normalized.append("")
            previous_blank = True
            continue
        normalized.append(line)
        previous_blank = False

    return "\n".join(normalized).strip()


def auto_correct_text(text, language="en"):
    if not text.strip():
        return text
    if not language or not str(language).startswith("en"):
        return text
    if SpellChecker is None:
        return text

    spell = SpellChecker()

    def _replace(match):
        word = match.group(0)
        lower = word.lower()
        correction = spell.correction(lower)
        if not correction or correction == lower:
            return word
        try:
            if spell.word_frequency.frequency(lower) > 0:
                return word
            if spell.word_frequency.frequency(correction) == 0:
                return word
        except Exception:
            pass
        if word.isupper():
            return correction.upper()
        if word[0].isupper():
            return correction.capitalize()
        return correction

    return re.sub(r"[A-Za-z]{3,}", _replace, text)


def detect_intent(text):
    lowered = text.lower()
    lines = [line for line in text.split("\n") if line.strip()]

    if len(lines) <= 3 and len(text) < 160:
        return "quote"

    colon_lines = sum(1 for line in lines if ":" in line)
    if colon_lines >= 4:
        return "form"

    if any(word in lowered for word in ["chapter", "section", "table", "figure"]):
        return "document"

    if len(lines) >= 18:
        return "document"

    return "notes"


def student_pack(text):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    summary = " ".join(sentences[:3]).strip()

    key_points = []
    for line in text.split("\n"):
        line = line.strip("- ").strip()
        if line and line not in key_points:
            key_points.append(line)
        if len(key_points) >= 6:
            break

    mcqs = []
    if summary:
        first_sentence = summary.split(".")[0]
        mcqs.append({"q": "What is the main idea of the text?", "a": first_sentence})
    if key_points:
        mcqs.append({"q": "Which point best summarizes the notes?", "a": key_points[0]})

    return summary, key_points, mcqs


def detect_language(text):
    if not detect_lang or not text.strip():
        return "unknown"
    try:
        return detect_lang(text)
    except Exception:
        return "unknown"


def extract_actions(text):
    emails = list({match.group(0) for match in re.finditer(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", text)})
    urls = list({match.group(0) for match in re.finditer(r"https?://[^\s]+", text)})
    phones = list({match.group(0) for match in re.finditer(r"\b\+?\d[\d\s\-]{8,}\d\b", text)})

    address_words = [
        "street",
        "st",
        "road",
        "rd",
        "avenue",
        "ave",
        "lane",
        "ln",
        "boulevard",
        "blvd",
        "nagar",
        "sector",
        "colony",
        "area",
        "park",
        "phase",
        "society",
    ]
    addresses = []
    for line in text.split("\n"):
        lower_line = line.lower()
        if any(word in lower_line for word in address_words) and re.search(r"\d", line):
            addresses.append(line.strip())

    return {
        "emails": emails,
        "urls": urls,
        "phones": phones,
        "addresses": addresses,
    }
