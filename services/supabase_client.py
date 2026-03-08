import os

from dotenv import load_dotenv
from flask import session

load_dotenv()

_SUPABASE = {"init": False, "anon": None, "service": None}


def _looks_placeholder(value):
    lowered = (value or "").lower()
    return not value or "xxxx" in lowered or "placeholder" in lowered or "your_" in lowered


def _init_supabase():
    if _SUPABASE["init"]:
        return
    _SUPABASE["init"] = True

    url = os.getenv("SUPABASE_URL", "").strip()
    anon_key = (os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    service_key = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()

    if not url:
        return

    try:
        from supabase import create_client
    except Exception:
        return

    if anon_key and not _looks_placeholder(anon_key):
        try:
            _SUPABASE["anon"] = create_client(url, anon_key)
        except Exception:
            _SUPABASE["anon"] = None

    if service_key and not _looks_placeholder(service_key):
        try:
            _SUPABASE["service"] = create_client(url, service_key)
        except Exception:
            _SUPABASE["service"] = None


def supabase_anon():
    _init_supabase()
    return _SUPABASE.get("anon")


def supabase_service():
    _init_supabase()
    return _SUPABASE.get("service")


def _supabase_blocked():
    return session.get("supabase_user") is False


def supabase_db_client():
    if _supabase_blocked():
        return None
    if os.getenv("SUPABASE_USE_DB", "true").lower() in {"false", "0", "no"}:
        return None
    return supabase_service() or supabase_anon()


def supabase_storage_client():
    if _supabase_blocked():
        return None
    if os.getenv("SUPABASE_USE_STORAGE", "true").lower() in {"false", "0", "no"}:
        return None
    return supabase_service() or supabase_anon()


def storage_bucket():
    return os.getenv("SUPABASE_BUCKET", "uploads")
