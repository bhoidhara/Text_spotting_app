import os
import re
from datetime import datetime

ALLOWED_EXT_DEFAULT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
    ".heif",
    ".pdf",
    ".txt",
    ".docx",
    ".csv",
    ".rtf",
    ".json",
    ".xml",
}


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def allowed_file(filename, allowed_ext=None):
    if not filename:
        return False
    _, ext = os.path.splitext(filename.lower())
    allowed_ext = allowed_ext or ALLOWED_EXT_DEFAULT
    return ext in allowed_ext


def safe_slug(value, default="user"):
    if not value:
        return default
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(value))
