import os
import re

from utils.helpers import safe_int

try:
    from PIL import ImageEnhance, ImageFilter, ImageOps
except Exception:
    ImageEnhance = None
    ImageFilter = None
    ImageOps = None

try:
    from pillow_heif import register_heif_opener
except Exception:
    register_heif_opener = None

if register_heif_opener:
    try:
        register_heif_opener()
    except Exception:
        pass

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


def tesseract_status():
    status = {
        "pytesseract_ok": False,
        "tesseract_cmd": os.getenv("TESSERACT_CMD"),
        "tesseract_version": None,
        "error": None,
    }

    if pytesseract is None:
        status["error"] = "pytesseract is not installed."
        return status

    status["pytesseract_ok"] = True
    if status["tesseract_cmd"]:
        pytesseract.pytesseract.tesseract_cmd = status["tesseract_cmd"]

    try:
        status["tesseract_version"] = str(pytesseract.get_tesseract_version())
    except Exception as exc:
        status["error"] = str(exc)

    return status


def preprocess_image(image):
    if ImageOps:
        image = ImageOps.grayscale(image)
    if ImageFilter:
        image = image.filter(ImageFilter.MedianFilter(size=3))
    return image


def _preprocess_variants(image):
    variants = []
    base = image
    if ImageOps:
        base = ImageOps.grayscale(base)
        variants.append(("grayscale", base))
        try:
            variants.append(("autocontrast", ImageOps.autocontrast(base)))
        except Exception:
            pass
    if ImageFilter:
        try:
            variants.append(("median", base.filter(ImageFilter.MedianFilter(size=3))))
        except Exception:
            pass
        try:
            variants.append(("sharpen", base.filter(ImageFilter.UnsharpMask(radius=1, percent=160, threshold=2))))
        except Exception:
            pass
    if ImageEnhance:
        try:
            variants.append(("contrast", ImageEnhance.Contrast(base).enhance(1.8)))
        except Exception:
            pass
    try:
        threshold = base.point(lambda p: 255 if p > 160 else 0)
        variants.append(("threshold", threshold))
    except Exception:
        pass
    try:
        width, height = base.size
        upscaled = base.resize((width * 2, height * 2), resample=getattr(base, "LANCZOS", 1))
        variants.append(("upscale", upscaled))
    except Exception:
        pass
    variants.append(("original", image))
    return variants


def _summarize_data(data):
    conf_values = []
    low_conf_words = []
    line_confidence = []

    texts = data.get("text", []) or []
    confs = data.get("conf", []) or []
    line_nums = data.get("line_num", []) or []
    par_nums = data.get("par_num", []) or []
    block_nums = data.get("block_num", []) or []

    line_map = {}
    for idx, word in enumerate(texts):
        word = word.strip()
        if not word:
            continue
        conf_value = safe_int(confs[idx] if idx < len(confs) else -1, -1)
        if conf_value >= 0:
            conf_values.append(conf_value)
            if conf_value < 60:
                low_conf_words.append(word)
        key = (
            block_nums[idx] if idx < len(block_nums) else 0,
            par_nums[idx] if idx < len(par_nums) else 0,
            line_nums[idx] if idx < len(line_nums) else idx,
        )
        entry = line_map.setdefault(key, {"words": [], "conf": []})
        entry["words"].append(word)
        if conf_value >= 0:
            entry["conf"].append(conf_value)

    for key in sorted(line_map.keys()):
        entry = line_map[key]
        line_text = " ".join(entry["words"]).strip()
        if not line_text:
            continue
        avg_line_conf = round(sum(entry["conf"]) / len(entry["conf"]), 2) if entry["conf"] else 0.0
        line_confidence.append({"text": line_text, "conf": avg_line_conf})

    avg_conf = round(sum(conf_values) / len(conf_values), 2) if conf_values else 0.0

    return avg_conf, low_conf_words, line_confidence


def _needs_lang_fallback(exc):
    message = str(exc).lower()
    return "failed loading language" in message or "error opening data file" in message


def _run_tesseract(image, lang, config):
    text = pytesseract.image_to_string(image, lang=lang, config=config)
    try:
        data = pytesseract.image_to_data(
            image, lang=lang, config=config, output_type=pytesseract.Output.DICT
        )
    except Exception:
        data = {"text": [], "conf": []}
    return text, data


def ocr_image(image, lang="eng", advanced=False):
    status = tesseract_status()
    if not status.get("pytesseract_ok"):
        raise RuntimeError("pytesseract is not installed.")
    if status.get("error"):
        raise RuntimeError(f"Tesseract is not available: {status['error']}")

    variants = _preprocess_variants(image)
    last_exc = None
    best = {"score": -1, "text": "", "avg_conf": 0.0, "low_conf": [], "line_conf": []}
    configs = ["--oem 3 --psm 6"]
    if advanced:
        configs = [
            "--oem 3 --psm 6",
            "--oem 3 --psm 4",
            "--oem 3 --psm 11",
            "--oem 3 --psm 3",
        ]

    for _, candidate in variants:
        for config in configs:
            try:
                text, data = _run_tesseract(candidate, lang, config)
            except Exception as exc:
                if lang != "eng" and _needs_lang_fallback(exc):
                    try:
                        text, data = _run_tesseract(candidate, "eng", config)
                    except Exception as inner_exc:
                        last_exc = inner_exc
                        continue
                else:
                    last_exc = exc
                    continue

            avg_conf, low_conf_words, line_confidence = _summarize_data(data)
            text_clean = (text or "").strip()
            score = len(text_clean) + (avg_conf * 2)
            if score > best["score"]:
                best = {
                    "score": score,
                    "text": text,
                    "avg_conf": avg_conf,
                    "low_conf": low_conf_words,
                    "line_conf": line_confidence,
                }

    if best["score"] < 0:
        raise RuntimeError(f"OCR failed: {last_exc}") if last_exc else RuntimeError("OCR failed.")

    return best["text"], best["avg_conf"], best["low_conf"], best["line_conf"]


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
    buffer = []
    previous_blank = False
    bullet_re = re.compile(r"^(\d+\.|[-*•])\s+")

    for line in cleaned_lines:
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            if buffer:
                normalized.append(" ".join(buffer).strip())
                buffer = []
            if not previous_blank:
                normalized.append("")
            previous_blank = True
            continue

        if bullet_re.match(line):
            if buffer:
                normalized.append(" ".join(buffer).strip())
                buffer = []
            normalized.append(line)
            previous_blank = False
            continue

        buffer.append(line)
        previous_blank = False

    if buffer:
        normalized.append(" ".join(buffer).strip())

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
