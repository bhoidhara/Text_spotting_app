import os

from flask import current_app, flash, redirect, render_template, request, url_for

from services.scans import delete_scan as delete_scan_record, get_scan, list_scans
from services.storage import delete_from_storage
from utils.auth import get_user_id, require_login


def register_history_routes(app):
    @app.route("/history")
    def history():
        if not require_login():
            return redirect(url_for("login"))

        query = request.args.get("q", "").strip().lower()
        tag_filter = request.args.get("tag", "").strip().lower()

        scans = list_scans(get_user_id())

        if query:
            scans = [
                scan
                for scan in scans
                if query in (scan.get("cleaned_text") or "").lower()
                or query in (scan.get("extracted_text") or "").lower()
            ]

        if tag_filter:
            scans = [scan for scan in scans if tag_filter in [tag.lower() for tag in scan.get("tags", [])]]

        tags = sorted({tag for scan in list_scans(get_user_id()) for tag in scan.get("tags", [])})

        return render_template("history.html", scans=scans, tags=tags, query=query, tag_filter=tag_filter)

    @app.route("/history/<scan_id>/delete", methods=["POST"])
    def delete_scan(scan_id):
        if not require_login():
            return redirect(url_for("login"))

        scan = get_scan(scan_id)
        if scan:
            image_paths = scan.get("image_paths", [])
            for path in image_paths:
                local_path = os.path.join(current_app.config["UPLOAD_FOLDER"], path)
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except Exception:
                        pass
            delete_from_storage(image_paths)

        delete_scan_record(scan_id)
        flash("Scan deleted.", "success")
        return redirect(url_for("history"))
