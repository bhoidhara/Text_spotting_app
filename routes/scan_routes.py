import io
import os
from uuid import uuid4

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)

from services.ocr import clean_text, detect_intent, detect_language, extract_actions, ocr_image, student_pack
from services.scans import get_scan, list_scans, log_export, log_translation, upsert_scan
from services.storage import download_from_storage, upload_to_storage
from services.supabase_client import supabase_storage_client
from utils.auth import get_user_id, require_login
from utils.helpers import allowed_file, now_iso, safe_int, safe_slug
from werkzeug.utils import secure_filename

try:
    from PIL import Image
except Exception:
    Image = None


def register_scan_routes(app):
    @app.route("/dashboard")
    def dashboard():
        if not require_login():
            return redirect(url_for("login"))

        user_id = get_user_id()
        scans = list_scans(user_id)
        recent_scans = scans[:5]
        tags = sorted({tag for scan in scans for tag in scan.get("tags", [])})

        return render_template(
            "dashboard.html",
            recent_scans=recent_scans,
            tags=tags,
            user_email=session.get("user_email"),
        )

    @app.route("/upload", methods=["POST"])
    def upload():
        if not require_login():
            return redirect(url_for("login"))

        files = request.files.getlist("images")
        if not files or all(file.filename == "" for file in files):
            flash("Please select at least one image.", "warn")
            return redirect(url_for("dashboard"))

        lang = request.form.get("lang", "eng")
        cleanup = request.form.get("cleanup") == "on"
        detect_intent_flag = request.form.get("detect_intent") == "on"
        student_mode = request.form.get("student_mode") == "on"
        privacy_mode = request.form.get("privacy_mode") == "on"

        crop_x = request.form.get("crop_x")
        crop_y = request.form.get("crop_y")
        crop_w = request.form.get("crop_w")
        crop_h = request.form.get("crop_h")

        crop_box = None
        if crop_x and crop_y and crop_w and crop_h:
            crop_box = (
                safe_int(crop_x),
                safe_int(crop_y),
                safe_int(crop_x) + safe_int(crop_w),
                safe_int(crop_y) + safe_int(crop_h),
            )

        if Image is None:
            flash("Pillow is not installed. OCR cannot run.", "warn")
            return redirect(url_for("dashboard"))

        combined_text = []
        combined_conf = []
        combined_low_conf = []
        image_paths = []
        scan_id = str(uuid4())
        user_id = get_user_id()
        safe_user = safe_slug(user_id)
        store_local = os.getenv("STORE_LOCAL_UPLOADS", "true").lower() not in {"false", "0", "no"}
        storage_enabled = supabase_storage_client() is not None
        upload_root = current_app.config["UPLOAD_FOLDER"]

        for index, file in enumerate(files, start=1):
            if not file or not allowed_file(file.filename, current_app.config["ALLOWED_EXT"]):
                continue

            filename = f"{uuid4().hex}_{secure_filename(file.filename)}"
            local_dir = os.path.join(upload_root, safe_user, scan_id)
            os.makedirs(local_dir, exist_ok=True)
            local_rel_path = os.path.join(safe_user, scan_id, filename)
            file_path = os.path.join(upload_root, local_rel_path)
            file.save(file_path)

            try:
                image = Image.open(file_path)
            except Exception:
                continue

            if crop_box:
                try:
                    image = image.crop(crop_box)
                except Exception:
                    pass

            try:
                page_text, avg_conf, low_conf = ocr_image(image, lang=lang)
            except Exception as exc:
                flash(f"OCR failed on {file.filename}: {exc}", "warn")
                continue

            page_block = f"--- Page {index} ---\n{page_text.strip()}"
            combined_text.append(page_block.strip())
            combined_conf.append(avg_conf)
            combined_low_conf.extend(low_conf)

            storage_path = local_rel_path.replace("\\", "/")
            upload_ok = False
            if not privacy_mode and storage_enabled:
                upload_ok = upload_to_storage(file_path, storage_path) is not None

            if not privacy_mode:
                image_paths.append(storage_path)

            if privacy_mode or (not store_local and upload_ok):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        if not combined_text:
            flash("No valid images were processed.", "warn")
            return redirect(url_for("dashboard"))

        extracted_text = "\n\n".join(combined_text).strip()
        cleaned_text = clean_text(extracted_text) if cleanup else extracted_text
        intent = detect_intent(cleaned_text if detect_intent_flag else extracted_text) if detect_intent_flag else "auto"
        language = detect_language(cleaned_text)

        summary = ""
        key_points = []
        mcqs = []
        if student_mode:
            summary, key_points, mcqs = student_pack(cleaned_text)

        confidence_avg = round(sum(combined_conf) / len(combined_conf), 2) if combined_conf else 0.0

        scan = {
            "id": scan_id,
            "user_id": user_id,
            "image_paths": image_paths,
            "extracted_text": extracted_text,
            "cleaned_text": cleaned_text,
            "language": language,
            "intent": intent,
            "confidence_avg": confidence_avg,
            "low_confidence_words": combined_low_conf[:50],
            "summary": summary,
            "key_points": key_points,
            "mcqs": mcqs,
            "tags": [],
            "is_private": privacy_mode,
            "created_at": now_iso(),
        }

        upsert_scan(scan)
        flash("OCR complete.", "success")
        return redirect(url_for("result", scan_id=scan_id))

    @app.route("/result/<scan_id>")
    def result(scan_id):
        if not require_login():
            return redirect(url_for("login"))

        scan = get_scan(scan_id)
        if not scan:
            flash("Scan not found.", "warn")
            return redirect(url_for("dashboard"))

        actions = extract_actions(scan.get("cleaned_text") or scan.get("extracted_text", ""))

        return render_template(
            "result.html",
            scan=scan,
            actions=actions,
        )

    @app.route("/result/<scan_id>/save", methods=["POST"])
    def save_result(scan_id):
        if not require_login():
            return redirect(url_for("login"))

        scan = get_scan(scan_id)
        if not scan:
            flash("Scan not found.", "warn")
            return redirect(url_for("dashboard"))

        cleaned_text = request.form.get("cleaned_text", "").strip()
        tags = [tag.strip() for tag in request.form.get("tags", "").split(",") if tag.strip()]

        scan["cleaned_text"] = cleaned_text
        scan["tags"] = tags
        scan["updated_at"] = now_iso()

        upsert_scan(scan)
        flash("Saved successfully.", "success")
        return redirect(url_for("result", scan_id=scan_id))

    @app.route("/result/<scan_id>/export", methods=["POST"])
    def export_result(scan_id):
        if not require_login():
            return redirect(url_for("login"))

        scan = get_scan(scan_id)
        if not scan:
            flash("Scan not found.", "warn")
            return redirect(url_for("dashboard"))

        export_format = request.form.get("export_format", "txt")
        content = scan.get("cleaned_text") or scan.get("extracted_text", "")

        if export_format == "txt":
            buffer = io.BytesIO(content.encode("utf-8"))
            filename = f"visiontext_{scan_id}.txt"
            log_export(scan_id, scan.get("user_id"), "txt")
            return send_file(buffer, as_attachment=True, download_name=filename, mimetype="text/plain")

        if export_format == "pdf":
            try:
                from fpdf import FPDF

                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                for line in content.split("\n"):
                    pdf.multi_cell(0, 8, line)
                pdf_bytes = pdf.output(dest="S").encode("latin-1")
                buffer = io.BytesIO(pdf_bytes)
                filename = f"visiontext_{scan_id}.pdf"
                log_export(scan_id, scan.get("user_id"), "pdf")
                return send_file(
                    buffer, as_attachment=True, download_name=filename, mimetype="application/pdf"
                )
            except Exception:
                flash("PDF export needs fpdf2 installed.", "warn")
                return redirect(url_for("result", scan_id=scan_id))

        if export_format == "docx":
            try:
                from docx import Document

                doc = Document()
                for line in content.split("\n"):
                    doc.add_paragraph(line)
                buffer = io.BytesIO()
                doc.save(buffer)
                buffer.seek(0)
                filename = f"visiontext_{scan_id}.docx"
                log_export(scan_id, scan.get("user_id"), "docx")
                return send_file(
                    buffer,
                    as_attachment=True,
                    download_name=filename,
                    mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            except Exception:
                flash("DOCX export needs python-docx installed.", "warn")
                return redirect(url_for("result", scan_id=scan_id))

        flash("Unsupported export format.", "warn")
        return redirect(url_for("result", scan_id=scan_id))

    @app.route("/result/<scan_id>/translate", methods=["POST"])
    def translate_result(scan_id):
        if not require_login():
            return redirect(url_for("login"))

        scan = get_scan(scan_id)
        if not scan:
            flash("Scan not found.", "warn")
            return redirect(url_for("dashboard"))

        target_lang = request.form.get("target_lang", "en")
        scan["translation"] = {
            "target": target_lang,
            "text": scan.get("cleaned_text") or scan.get("extracted_text", ""),
            "created_at": now_iso(),
        }
        upsert_scan(scan)
        log_translation(scan_id, scan.get("user_id"), scan.get("language"), target_lang, scan["translation"]["text"])
        flash("Translation is in demo mode.", "warn")
        return redirect(url_for("result", scan_id=scan_id))

    @app.route("/result/<scan_id>/tts", methods=["POST"])
    def tts_result(scan_id):
        if not require_login():
            return redirect(url_for("login"))

        flash("Text-to-speech is not configured yet.", "warn")
        return redirect(url_for("result", scan_id=scan_id))

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        local_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(local_path):
            return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

        data, content_type = download_from_storage(filename)
        if data is not None:
            return send_file(io.BytesIO(data), mimetype=content_type)

        return abort(404)
