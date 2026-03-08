from flask import flash, session


def get_user_id():
    return session.get("user_id")


def require_login():
    if not get_user_id():
        flash("Please log in to continue.", "warn")
        return False
    return True
