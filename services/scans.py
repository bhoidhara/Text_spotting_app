import json
import os

from flask import current_app

from services.supabase_client import supabase_db_client
from utils.helpers import now_iso


def _load_store():
    data_path = current_app.config["DATA_PATH"]
    if not os.path.exists(data_path):
        return {"scans": []}
    try:
        with open(data_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {"scans": []}


def _save_store(store):
    data_path = current_app.config["DATA_PATH"]
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(store, handle, ensure_ascii=True, indent=2)


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
    client = supabase_db_client()
    if client:
        try:
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
            pass

    store = _load_store()
    scans = [scan for scan in store.get("scans", []) if scan.get("user_id") == user_id]
    scans.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return scans


def get_scan(scan_id):
    client = supabase_db_client()
    if client:
        try:
            response = client.table("scans").select("*").eq("id", scan_id).limit(1).execute()
            scans = response.data or []
            return normalize_scan(scans[0]) if scans else None
        except Exception:
            pass

    store = _load_store()
    for scan in store.get("scans", []):
        if scan.get("id") == scan_id:
            return scan
    return None


def upsert_scan(scan):
    client = supabase_db_client()
    if client:
        try:
            client.table("scans").upsert(scan).execute()
            return
        except Exception:
            pass

    store = _load_store()
    scans = store.get("scans", [])
    scans = [item for item in scans if item.get("id") != scan.get("id")]
    scans.insert(0, scan)
    store["scans"] = scans
    _save_store(store)


def delete_scan(scan_id):
    client = supabase_db_client()
    if client:
        try:
            client.table("scans").delete().eq("id", scan_id).execute()
            return
        except Exception:
            pass

    store = _load_store()
    store["scans"] = [scan for scan in store.get("scans", []) if scan.get("id") != scan_id]
    _save_store(store)


def log_export(scan_id, user_id, export_format):
    client = supabase_db_client()
    if not client:
        return
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
    client = supabase_db_client()
    if not client:
        return
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
