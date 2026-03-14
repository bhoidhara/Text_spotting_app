import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, send_from_directory, url_for, request, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

from routes.auth_routes import register_auth_routes
from routes.history_routes import register_history_routes
from routes.scan_routes import register_scan_routes
from routes.settings_routes import register_settings_routes
from utils.helpers import ALLOWED_EXT_DEFAULT, safe_int

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change")
app.permanent_session_lifetime = timedelta(days=int(os.getenv("SESSION_DAYS", "30")))
app.config["APP_BUILD"] = os.getenv("APP_BUILD", "v64")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
max_upload_mb = safe_int(os.getenv("MAX_UPLOAD_MB"), 80)
soft_upload_mb = safe_int(os.getenv("SOFT_UPLOAD_MB"), 0)
app.config.update(
    UPLOAD_FOLDER=os.path.join(BASE_DIR, "uplaod"),
    DATA_DIR=os.path.join(BASE_DIR, "data"),
    DATA_PATH=os.path.join(BASE_DIR, "data", "scans.json"),
    ALLOWED_EXT=ALLOWED_EXT_DEFAULT,
    MAX_CONTENT_LENGTH=max_upload_mb * 1024 * 1024,
    MAX_UPLOAD_MB=max_upload_mb,
    SOFT_UPLOAD_MB=soft_upload_mb,
    MAX_PDF_PAGES=safe_int(os.getenv("MAX_PDF_PAGES"), 16),
    MAX_IMAGE_SIDE=safe_int(os.getenv("MAX_IMAGE_SIDE"), 4200),
)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["DATA_DIR"], exist_ok=True)


@app.route("/")
def index():
    return redirect(url_for("login"))


register_auth_routes(app)
try:
    register_scan_routes(app)
except Exception as exc:
    app.logger.exception("Failed to register scan routes: %s", exc)

    @app.route("/api/health")
    def api_health_fallback():
        return {"ok": False, "error": "OCR routes failed to load."}, 500
register_history_routes(app)
register_settings_routes(app)

@app.context_processor
def inject_build():
    return {"app_build": app.config.get("APP_BUILD", "v64")}


@app.route("/service-worker.js")
def service_worker():
    return send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    message = f"File too large. Max upload is {app.config.get('MAX_UPLOAD_MB', 12)} MB."
    if request and request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": message}), 413
    try:
        from flask import flash

        flash(message, "warn")
    except Exception:
        pass
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
