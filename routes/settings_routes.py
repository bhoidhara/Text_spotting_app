from flask import flash, redirect, render_template, request, session, url_for

from services.supabase_client import supabase_db_client
from utils.auth import get_user_id, require_login


DEFAULT_SETTINGS = {
    "theme": "dark",
    "notifications": True,
    "autosave": True,
    "feedback_category": "General",
    "feedback_rating": 5,
    "feedback_text": "",
}


def _load_settings():
    stored = session.get("app_settings")
    if not isinstance(stored, dict):
        stored = {}
    settings = DEFAULT_SETTINGS.copy()
    settings.update({k: v for k, v in stored.items() if k in settings})
    return settings


def _store_settings(settings):
    session["app_settings"] = settings


DEFAULT_PROFILE = {
    "full_name": "",
    "username": "",
    "phone": "",
    "bio": "",
}


def _load_profile():
    stored = session.get("profile_draft")
    if not isinstance(stored, dict):
        stored = {}
    profile = DEFAULT_PROFILE.copy()
    profile.update({k: v for k, v in stored.items() if k in profile})
    return profile


def register_settings_routes(app):
    @app.route("/camera")
    def camera():
        if not require_login():
            return redirect(url_for("login"))
        return render_template("camera.html")

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if not require_login():
            return redirect(url_for("login"))

        settings_data = _load_settings()
        if request.method == "POST":
            settings_data["theme"] = "dark" if request.form.get("theme_dark") == "on" else "light"
            settings_data["notifications"] = request.form.get("notifications") == "on"
            settings_data["autosave"] = request.form.get("autosave") == "on"

            settings_data["feedback_category"] = request.form.get(
                "feedback_category", settings_data["feedback_category"]
            )
            rating = request.form.get("feedback_rating")
            if rating and rating.isdigit():
                settings_data["feedback_rating"] = int(rating)
            feedback_text = request.form.get("feedback_text", "").strip()
            settings_data["feedback_text"] = "" if feedback_text else settings_data.get("feedback_text", "")

            _store_settings(settings_data)

            if feedback_text:
                flash("Feedback submitted. Thank you!", "success")
            else:
                flash("Settings updated.", "success")
            return redirect(url_for("settings"))

        return render_template("settings.html", settings=settings_data)

    @app.route("/profile", methods=["GET", "POST"])
    def profile():
        if not require_login():
            return redirect(url_for("login"))

        user_id = get_user_id()
        email = session.get("user_email", "")
        profile_data = _load_profile()

        client = supabase_db_client()
        if client and user_id:
            try:
                response = client.table("profiles").select("full_name, email").eq("id", user_id).execute()
                if response and response.data:
                    db_profile = response.data[0]
                    profile_data["full_name"] = profile_data["full_name"] or db_profile.get(
                        "full_name", ""
                    )
                    email = db_profile.get("email") or email
            except Exception:
                pass

        if request.method == "POST":
            profile_data["full_name"] = request.form.get("full_name", "").strip()
            profile_data["username"] = request.form.get("username", "").strip()
            profile_data["phone"] = request.form.get("phone", "").strip()
            profile_data["bio"] = request.form.get("bio", "").strip()
            session["profile_draft"] = profile_data

            if client and user_id:
                try:
                    client.table("profiles").upsert(
                        {"id": str(user_id), "email": email, "full_name": profile_data["full_name"]}
                    ).execute()
                except Exception:
                    pass

            flash("Profile updated.", "success")
            return redirect(url_for("profile"))

        return render_template("profile.html", profile=profile_data, user_email=email)
