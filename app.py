import os

from dotenv import load_dotenv
from flask import Flask, render_template

from routes.auth_routes import register_auth_routes
from routes.history_routes import register_history_routes
from routes.scan_routes import register_scan_routes
from utils.helpers import ALLOWED_EXT_DEFAULT

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change")

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
    return render_template("index.html")


register_auth_routes(app)
register_scan_routes(app)
register_history_routes(app)


if __name__ == "__main__":
    app.run(debug=True)
