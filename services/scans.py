import json
import os
import threading

from services.supabase_client import require_db_client
from utils.helpers import now_iso

# Local fallback is now optional and disabled by default to keep the app fully dynamic.
# Set FORCE_SUPABASE_ONLY=false if you want the old offline/local mode.
_LOCK = threading.Lock()
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOCAL_PATH = os.getenv(
    "LOCAL_SCANS_PATH",
    os.path.join(_BASE_DIR, "data", "scans.json"),
)


def _supabase_ready():
    url = os.getenv("SUPABASE_URL")
    anon = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
    service = os.getenv("SUPABASE_SERVICE_KEY")
    return bool(url and (anon or service))


def _supabase_only():
    forced = os.getenv("FORCE_SUPABASE_ONLY")
    if forced is None:
        # Default to local fallback when Supabase credentials are missing.
        return _supabase_ready()
    return forced.lower() not in {"false", "0", "no"}


def _load_local():
    try:
        with _LOCK:
            if not os.path.exists(_LOCAL_PATH):
                return []
            with open(_LOCAL_PATH, "r", encoding="utf-8") as handle:
                return json.load(handle) or []
    except Exception:
        return []


def _save_local(scans):
    os.makedirs(os.path.dirname(_LOCAL_PATH), exist_ok=True)
    with _LOCK:
        with open(_LOCAL_PATH, "w", encoding="utf-8") as handle:
            json.dump(scans, handle, ensure_ascii=False, indent=2)


def normalize_scan(scan):
    if not scan:
        return None
    if isinstance(scan.get("tags"), str):
        scan["tags"] = [tag.strip() for tag in scan.get("tags", "").split(",") if tag.strip()]
    scan.setdefault("tags", [])
    scan.setdefault("image_paths", [])
    scan.setdefault("low_confidence_words", [])
    scan.setdefault("key_points", [])
    scan.setdefault("mcqs", [])
    scan.setdefault("confidence_avg", 0.0)
    scan.setdefault("intent", "auto")
    scan.setdefault("language", "unknown")
    scan.setdefault("extracted_text", "")
    scan.setdefault("cleaned_text", scan.get("extracted_text", ""))
    scan.setdefault("summary", "")
    return scan


def list_scans(user_id):
    try:
        client = require_db_client()
        response = (
            client.table("scans")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        scans = response.data or []
        return [normalize_scan(scan) for scan in scans]
    except Exception:
        if _supabase_only():
            raise
        # Fallback to local JSON store (only when FORCE_SUPABASE_ONLY=false)
        scans = [s for s in _load_local() if s.get("user_id") == user_id]
        # newest first
        scans = sorted(scans, key=lambda x: x.get("created_at", ""), reverse=True)
        return [normalize_scan(scan) for scan in scans]


def get_scan(scan_id):
    try:
        client = require_db_client()
        response = client.table("scans").select("*").eq("id", scan_id).limit(1).execute()
        scans = response.data or []
        return normalize_scan(scans[0]) if scans else None
    except Exception:
        if _supabase_only():
            raise
        for scan in _load_local():
            if scan.get("id") == scan_id:
                return normalize_scan(scan)
        return None


def upsert_scan(scan):
    try:
        client = require_db_client()
        client.table("scans").upsert(scan).execute()
        return
    except Exception:
        if _supabase_only():
            raise
        scans = _load_local()
        updated = False
        for idx, existing in enumerate(scans):
            if existing.get("id") == scan.get("id"):
                scans[idx] = scan
                updated = True
                break
        if not updated:
            scans.append(scan)
        _save_local(scans)


def delete_scan(scan_id):
    try:
        client = require_db_client()
        client.table("scans").delete().eq("id", scan_id).execute()
        return
    except Exception:
        if _supabase_only():
            raise
        scans = [s for s in _load_local() if s.get("id") != scan_id]
        _save_local(scans)


def log_export(scan_id, user_id, export_format):
    try:
        client = require_db_client()
        client.table("exports").insert(
            {
                "scan_id": scan_id,
                "user_id": user_id,
                "format": export_format,
                "created_at": now_iso(),
            }
        ).execute()
    except Exception:
        # ignore in local mode
        if _supabase_only():
            raise
        return


def log_translation(scan_id, user_id, source_lang, target_lang, text):
    try:
        client = require_db_client()
        client.table("translations").insert(
            {
                "scan_id": scan_id,
                "user_id": user_id,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "text": text,
                "created_at": now_iso(),
            }
        ).execute()
    except Exception:
        # ignore in local mode
        if _supabase_only():
            raise
        return
