import os

from flask import current_app, flash, redirect, render_template, request, session, url_for

from services.supabase_client import supabase_anon, supabase_service
from utils.helpers import now_iso


def register_auth_routes(app):
    def _auth_error_message(exc, fallback):
        message = ""
        if hasattr(exc, "message"):
            message = str(exc.message)
        elif getattr(exc, "args", None):
            message = str(exc.args[0])
        else:
            message = str(exc)
        lowered = message.lower()
        if "email not confirmed" in lowered:
            return "Email not confirmed. Check your inbox or disable email confirmations in Supabase."
        if "invalid login credentials" in lowered:
            return "Invalid email or password."
        if "user already registered" in lowered or "already registered" in lowered:
            return "User already exists. Please login."
        if "password" in lowered and "at least" in lowered:
            return "Password must be at least 6 characters."
        return fallback

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not email or not password:
                flash("Email and password are required.", "warn")
                return render_template("login.html")

            client = supabase_anon()
            if not client:
                flash("Supabase is not configured.", "warn")
                return render_template("login.html")
            try:
                auth = client.auth.sign_in_with_password({"email": email, "password": password})
                user_id = getattr(auth.user, "id", None) or email
                session["user_id"] = str(user_id)
                session["user_email"] = email
                session["supabase_user"] = True
                session.permanent = True
                return redirect(url_for("dashboard"))
            except Exception as exc:
                current_app.logger.exception("Login failed")
                flash(_auth_error_message(exc, "Login failed. Check your credentials."), "warn")
                return render_template("login.html")

        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not email or not password:
                flash("Email and password are required.", "warn")
                return render_template("signup.html")

            client = supabase_anon()
            if not client:
                flash("Supabase is not configured.", "warn")
                return render_template("signup.html")
            try:
                auth = client.auth.sign_up({"email": email, "password": password})
                user_id = getattr(auth.user, "id", None) or email
                session["user_id"] = str(user_id)
                session["user_email"] = email
                session["supabase_user"] = True
                session.permanent = True
                service = supabase_service()
                if service and getattr(auth, "user", None):
                    try:
                        service.table("profiles").upsert(
                            {"id": str(user_id), "email": email, "created_at": now_iso()}
                        ).execute()
                    except Exception:
                        pass
                flash("Signup complete. Please verify your email if required.", "success")
                return redirect(url_for("dashboard"))
            except Exception as exc:
                current_app.logger.exception("Signup failed")
                flash(_auth_error_message(exc, "Signup failed. Try again."), "warn")
                return render_template("signup.html")

        return render_template("signup.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Logged out.", "success")
        return redirect(url_for("index"))

    @app.route("/auth/google")
    def auth_google():
        client = supabase_anon()
        if not client:
            flash("Supabase is not configured for Google Sign-In.", "warn")
            return redirect(url_for("login"))

        redirect_to = url_for("auth_callback", _external=True)
        try:
            response = client.auth.sign_in_with_oauth(
                {"provider": "google", "options": {"redirect_to": redirect_to}}
            )
            oauth_url = getattr(response, "url", None) or response.get("url")
            if oauth_url:
                return redirect(oauth_url)
        except Exception:
            pass

        supabase_url = os.getenv("SUPABASE_URL", "").strip()
        if supabase_url:
            fallback_url = (
                f"{supabase_url}/auth/v1/authorize?provider=google&redirect_to={redirect_to}"
            )
            return redirect(fallback_url)

        flash("Google Sign-In could not be started.", "warn")
        return redirect(url_for("login"))

    @app.route("/auth/callback")
    def auth_callback():
        code = request.args.get("code")
        if not code:
            flash("Missing auth code from provider.", "warn")
            return redirect(url_for("login"))

        client = supabase_anon()
        if not client:
            flash("Supabase is not configured.", "warn")
            return redirect(url_for("login"))

        session_data = None
        try:
            session_data = client.auth.exchange_code_for_session(code)
        except TypeError:
            try:
                session_data = client.auth.exchange_code_for_session({"auth_code": code})
            except Exception:
                session_data = None
        except Exception:
            session_data = None

        user = None
        if session_data:
            if isinstance(session_data, dict):
                user = session_data.get("user")
            else:
                user = getattr(session_data, "user", None)

        if not user:
            try:
                user = client.auth.get_user().user
            except Exception:
                user = None

        if not user:
            flash("Google Sign-In failed.", "warn")
            return redirect(url_for("login"))

        user_id = getattr(user, "id", None) or user.get("id")
        email = getattr(user, "email", None) or user.get("email", "")

        session["user_id"] = str(user_id)
        session["user_email"] = email or "google-user"
        session["supabase_user"] = True
        session.permanent = True

        service = supabase_service()
        if service and user_id:
            try:
                service.table("profiles").upsert(
                    {"id": str(user_id), "email": email, "created_at": now_iso()}
                ).execute()
            except Exception:
                pass

        return redirect(url_for("dashboard"))
