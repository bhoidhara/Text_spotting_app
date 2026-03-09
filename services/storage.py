import mimetypes

from services.supabase_client import require_storage_client, storage_bucket


def upload_to_storage(local_path, remote_path):
    client = require_storage_client()
    bucket = storage_bucket()
    content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    try:
        with open(local_path, "rb") as handle:
            payload = handle.read()
        client.storage.from_(bucket).upload(remote_path, payload, {"content-type": content_type, "upsert": True})
        return remote_path
    except Exception:
        return None


def download_from_storage(remote_path):
    client = require_storage_client()
    bucket = storage_bucket()
    try:
        data = client.storage.from_(bucket).download(remote_path)
    except Exception:
        return None, None
    content_type = mimetypes.guess_type(remote_path)[0] or "application/octet-stream"
    return data, content_type


def delete_from_storage(paths):
    if not paths:
        return
    client = require_storage_client()
    bucket = storage_bucket()
    try:
        client.storage.from_(bucket).remove(paths)
    except Exception:
        pass
