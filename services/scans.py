from services.supabase_client import require_db_client
from utils.helpers import now_iso


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


def get_scan(scan_id):
    client = require_db_client()
    response = client.table("scans").select("*").eq("id", scan_id).limit(1).execute()
    scans = response.data or []
    return normalize_scan(scans[0]) if scans else None


def upsert_scan(scan):
    client = require_db_client()
    client.table("scans").upsert(scan).execute()


def delete_scan(scan_id):
    client = require_db_client()
    client.table("scans").delete().eq("id", scan_id).execute()


def log_export(scan_id, user_id, export_format):
    client = require_db_client()
    try:
        client.table("exports").insert(
            {
                "scan_id": scan_id,
                "user_id": user_id,
                "format": export_format,
                "created_at": now_iso(),
            }
        ).execute()
    except Exception:
        pass


def log_translation(scan_id, user_id, source_lang, target_lang, text):
    client = require_db_client()
    try:
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
        pass
