import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, send_from_directory, url_for

from routes.auth_routes import register_auth_routes
from routes.history_routes import register_history_routes
from routes.scan_routes import register_scan_routes
from utils.helpers import ALLOWED_EXT_DEFAULT

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change")
app.permanent_session_lifetime = timedelta(days=int(os.getenv("SESSION_DAYS", "30")))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config.update(
    UPLOAD_FOLDER=os.path.join(BASE_DIR, "uplaod"),
    DATA_DIR=os.path.join(BASE_DIR, "data"),
    DATA_PATH=os.path.join(BASE_DIR, "data", "scans.json"),
    ALLOWED_EXT=ALLOWED_EXT_DEFAULT,
)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["DATA_DIR"], exist_ok=True)


@app.route("/")
def index():
    return redirect(url_for("login"))


register_auth_routes(app)
register_scan_routes(app)
register_history_routes(app)


@app.route("/service-worker.js")
def service_worker():
    return send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")


if __name__ == "__main__":
    app.run(debug=True)
