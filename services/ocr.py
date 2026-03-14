import os
import re

from utils.helpers import safe_int

try:
    from PIL import ImageEnhance, ImageFilter, ImageOps, ImageStat
except Exception:
    ImageEnhance = None
    ImageFilter = None
    ImageOps = None
    ImageStat = None

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
    import easyocr
except Exception:
    easyocr = None

try:
    import cv2
except Exception:
    cv2 = None

try:
    import numpy as np
except Exception:
    np = None

try:
    from langdetect import detect as detect_lang
except Exception:
    detect_lang = None

try:
    from spellchecker import SpellChecker
except Exception:
    SpellChecker = None


def _ensure_tessdata_prefix():
    if os.getenv("TESSDATA_PREFIX"):
        return
    candidates = [
        "/usr/share/tesseract-ocr/5/tessdata",
        "/usr/share/tesseract-ocr/4.00/tessdata",
        "/usr/share/tesseract-ocr/tessdata",
        "/usr/share/tessdata",
    ]
    for path in candidates:
        if os.path.isdir(path):
            os.environ["TESSDATA_PREFIX"] = path
            break


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
    _ensure_tessdata_prefix()

    try:
        status["tesseract_version"] = str(pytesseract.get_tesseract_version())
    except Exception as exc:
        status["error"] = str(exc)

    return status


_EASY_READERS = {}


def _get_easy_reader(lang):
    if easyocr is None:
        return None
    lang_list = [token.strip() for token in str(lang or "eng").split("+") if token.strip()]
    lang_key = tuple(lang_list)
    reader = _EASY_READERS.get(lang_key)
    if reader:
        return reader
    try:
        reader = easyocr.Reader(lang_list, gpu=False, download_enabled=True, detector=True, recognizer=True)
        _EASY_READERS[lang_key] = reader
        return reader
    except Exception:
        return None


def _pil_to_cv(image):
    if np is None:
        return None
    try:
        rgb = image.convert("RGB")
        array = np.array(rgb)
        if cv2 is None:
            return array
        return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def _easyocr_image(image, lang="eng", max_side=1600):
    reader = _get_easy_reader(lang)
    if reader is None:
        raise RuntimeError("EasyOCR not available")
    try:
        if ImageOps and hasattr(ImageOps, "exif_transpose"):
            image = ImageOps.exif_transpose(image)
    except Exception:
        pass

    try:
        width, height = image.size
        scale = min(1.0, max_side / max(width, height))
        if scale < 1.0:
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            image = image.resize(new_size, resample=getattr(image, "LANCZOS", 1))
    except Exception:
        pass

    cv_img = _pil_to_cv(image)
    if cv_img is None:
        # fallback: use PIL image directly via numpy if available
        if np is None:
            raise RuntimeError("EasyOCR needs numpy")
        cv_img = np.array(image.convert("RGB"))
    results = reader.readtext(cv_img)
    texts = []
    for _, txt, prob in results:
        if prob is None or prob < 0.1:
            continue
        texts.append(txt)
    joined = " ".join(texts).strip()
    return joined


def preprocess_image(image):
    if ImageOps:
        image = ImageOps.grayscale(image)
    if ImageFilter:
        image = image.filter(ImageFilter.MedianFilter(size=3))
    return image


def _downscale_image(image, max_side):
    try:
        width, height = image.size
    except Exception:
        return image
    if not width or not height:
        return image
    scale = min(1.0, max_side / max(width, height))
    if scale >= 1.0:
        return image
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    try:
        resample = getattr(image, "LANCZOS", 1)
        return image.resize(new_size, resample=resample)
    except Exception:
        try:
            return image.resize(new_size)
        except Exception:
            return image


def _preprocess_variants(image, advanced=False):
    variants = []
    base = image
    if ImageOps:
        base = ImageOps.grayscale(base)
        variants.append(("grayscale", base))
        if advanced:
            try:
                variants.append(("autocontrast", ImageOps.autocontrast(base)))
            except Exception:
                pass
            try:
                variants.append(("equalize", ImageOps.equalize(base)))
            except Exception:
                pass
            try:
                if ImageStat:
                    mean = ImageStat.Stat(base).mean[0]
                    if mean < 90:
                        variants.append(("invert", ImageOps.invert(base)))
            except Exception:
                pass
    if ImageFilter:
        try:
            variants.append(("median", base.filter(ImageFilter.MedianFilter(size=3))))
        except Exception:
            pass
        if advanced:
            try:
                variants.append(("sharpen", base.filter(ImageFilter.UnsharpMask(radius=1, percent=160, threshold=2))))
            except Exception:
                pass
    if ImageEnhance:
        try:
            contrast_level = 1.5 if advanced else 1.25
            variants.append(("contrast", ImageEnhance.Contrast(base).enhance(contrast_level)))
        except Exception:
            pass
    if advanced:
        try:
            threshold = base.point(lambda p: 255 if p > 160 else 0)
            variants.append(("threshold", threshold))
        except Exception:
            pass
        try:
            width, height = base.size
            if width * height <= 1500000:
                upscaled = base.resize(
                    (width * 2, height * 2), resample=getattr(base, "LANCZOS", 1)
                )
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


def _run_tesseract(image, lang, config, timeout_s=20, collect_data=True):
    text = pytesseract.image_to_string(image, lang=lang, config=config, timeout=timeout_s)
    if not collect_data:
        return text, {"text": [], "conf": []}
    try:
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            config=config,
            output_type=pytesseract.Output.DICT,
            timeout=timeout_s,
        )
    except Exception:
        data = {"text": [], "conf": []}
    return text, data


def ocr_image(image, lang="eng", advanced=False, fast=False, rescue=False):
    use_easy_first = (
        os.getenv("USE_EASYOCR_FIRST", "1").lower() not in {"0", "false", "no"} or fast
    )
    if easyocr is not None and use_easy_first:
        try:
            easy_text = _easyocr_image(image, lang=lang, max_side=1500 if fast else 1800)
            if easy_text.strip():
                return easy_text, 0.0, [], []
        except Exception:
            pass

    status = tesseract_status()
    if not status.get("pytesseract_ok"):
        # If tesseract is unavailable but easyocr worked earlier, we would have returned.
        raise RuntimeError("pytesseract is not installed.")
    if status.get("error"):
        raise RuntimeError(f"Tesseract is not available: {status['error']}")

    if ImageOps and hasattr(ImageOps, "exif_transpose"):
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass

    if rescue:
        max_side = 2000
    else:
        max_side = 800 if fast else 1800 if advanced else 1500
    image = _downscale_image(image, max_side)

    if rescue:
        try:
            width, height = image.size
            max_dim = max(width, height)
            if max_dim and max_dim < 1300:
                scale = min(2.6, 2600 / max_dim)
                new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                image = image.resize(new_size, resample=getattr(image, "LANCZOS", 1))
        except Exception:
            pass
        variants = _preprocess_variants(image, advanced=True)
    else:
        variants = _preprocess_variants(image, advanced=advanced)
    if fast and not rescue:
        # Keep the fastest path for mobile auto-scan.
        variants = [("original", image)]
    last_exc = None
    best = {"score": -1, "text": "", "avg_conf": 0.0, "low_conf": [], "line_conf": []}
    configs = ["--oem 3 --psm 6"]
    if rescue:
        configs = [
            "--oem 3 --psm 6",
            "--oem 3 --psm 4",
            "--oem 3 --psm 11",
            "--oem 3 --psm 7",
            "--oem 3 --psm 13",
            "--oem 1 --psm 6",
            "--oem 1 --psm 4",
            "--oem 1 --psm 11",
            "--oem 1 --psm 7",
        ]
    elif advanced:
        configs = ["--oem 3 --psm 6", "--oem 3 --psm 4"]

    if rescue:
        timeout_s = 15
    else:
        timeout_s = 6 if fast else 18 if not advanced else 24
    collect_data = not fast or rescue

    for _, candidate in variants:
        for config in configs:
            try:
                text, data = _run_tesseract(
                    candidate, lang, config, timeout_s=timeout_s, collect_data=collect_data
                )
            except Exception as exc:
                if lang != "eng" and _needs_lang_fallback(exc):
                    try:
                        text, data = _run_tesseract(
                            candidate, "eng", config, timeout_s=timeout_s, collect_data=collect_data
                        )
                    except Exception as inner_exc:
                        last_exc = inner_exc
                        continue
                else:
                    last_exc = exc
                    continue

            avg_conf, low_conf_words, line_confidence = _summarize_data(data)
            text_clean = (text or "").strip()
            if not text_clean and line_confidence:
                text = "\n".join(item.get("text", "") for item in line_confidence).strip()
                text_clean = text
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
    def _unique(items):
        seen = set()
        output = []
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            output.append(item)
        return output

    emails = _unique([match.group(0) for match in re.finditer(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", text)])
    urls = _unique([match.group(0) for match in re.finditer(r"https?://[^\s]+", text)])
    phones = _unique([match.group(0) for match in re.finditer(r"\b\+?\d[\d\s\-]{8,}\d\b", text)])

    website_matches = re.findall(
        r"\b(?:www\.)?[a-zA-Z0-9-]+\.(?:com|in|org|net|io|co|gov|edu|me|app|dev|ai|xyz|info|biz|uk|us|ca|au|de|fr|jp|ru|cn|za|pk|bd|lk|sg|my|ae)\b",
        text,
    )
    websites = []
    for site in website_matches:
        if site.startswith("http"):
            websites.append(site)
        elif site.startswith("www."):
            websites.append(f"https://{site}")
        else:
            websites.append(f"https://{site}")
    websites = _unique(websites)

    instagram = _unique(
        [f"https://instagram.com/{m}" for m in re.findall(r"(?:instagram\.com/|insta\s*[:\-]?\s*@?)([A-Za-z0-9._]+)", text, re.I)]
    )
    facebook = _unique(
        [f"https://facebook.com/{m}" for m in re.findall(r"(?:facebook\.com/|fb\s*[:\-]?\s*@?)([A-Za-z0-9.\-]+)", text, re.I)]
    )
    twitter = _unique(
        [f"https://x.com/{m}" for m in re.findall(r"(?:twitter\.com/|x\.com/|twitter\s*[:\-]?\s*@)([A-Za-z0-9_]{1,30})", text, re.I)]
    )
    linkedin = _unique(
        [f"https://linkedin.com/{m[0]}/{m[1]}" for m in re.findall(r"linkedin\.com/(in|company)/([A-Za-z0-9-]+)", text, re.I)]
    )
    telegram = _unique(
        [f"https://t.me/{m}" for m in re.findall(r"(?:t\.me/|telegram\s*[:\-]?\s*@?)([A-Za-z0-9_]{3,32})", text, re.I)]
    )
    whatsapp = _unique(
        [f"https://wa.me/{m}" for m in re.findall(r"(?:wa\.me/|whatsapp\.com/send\?phone=|\bwhatsapp\b\s*[:\-]?\s*\+?)(\d{8,15})", text, re.I)]
    )

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
    addresses = _unique(addresses)

    # Merge website-only matches into urls for actions
    urls = _unique(urls + websites)

    return {
        "emails": emails,
        "urls": urls,
        "phones": phones,
        "addresses": addresses,
        "instagram": instagram,
        "facebook": facebook,
        "twitter": twitter,
        "linkedin": linkedin,
        "telegram": telegram,
        "whatsapp": whatsapp,
    }
