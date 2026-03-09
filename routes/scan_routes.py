import io
import os
from uuid import uuid4

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)

from services.ocr import (
    auto_correct_text,
    clean_text,
    detect_intent,
    detect_language,
    extract_actions,
    ocr_image,
    student_pack,
)
from services.scans import delete_scan as delete_scan_record, get_scan, list_scans, log_export, log_translation, upsert_scan
from services.storage import delete_from_storage, download_from_storage, upload_to_storage
from services.supabase_client import require_storage_client
from utils.auth import get_user_id, require_login
from utils.helpers import allowed_file, now_iso, safe_int, safe_slug
from werkzeug.utils import secure_filename

try:
    from PIL import Image
except Exception:
    Image = None


def register_scan_routes(app):
    def _api_user_id():
        return request.headers.get("X-User-Id") or session.get("user_id")

    def _build_crop_box():
        crop_x = request.form.get("crop_x")
        crop_y = request.form.get("crop_y")
        crop_w = request.form.get("crop_w")
        crop_h = request.form.get("crop_h")
        if crop_x and crop_y and crop_w and crop_h:
            return (
                safe_int(crop_x),
                safe_int(crop_y),
                safe_int(crop_x) + safe_int(crop_w),
                safe_int(crop_y) + safe_int(crop_h),
            )
        return None

    def _process_upload(files, user_id, use_flash=True):
        if not files or all(file.filename == "" for file in files):
            return None, [], "Please select at least one image."

        if Image is None:
            return None, [], "Pillow is not installed. OCR cannot run."

        lang = request.form.get("lang", "eng")
        cleanup = request.form.get("cleanup") == "on"
        autocorrect = request.form.get("autocorrect") == "on"
        detect_intent_flag = request.form.get("detect_intent") == "on"
        student_mode = request.form.get("student_mode") == "on"
        privacy_mode = request.form.get("privacy_mode") == "on"
        crop_box = _build_crop_box()

        combined_text = []
        combined_conf = []
        combined_low_conf = []
        image_paths = []
        scan_id = str(uuid4())
        safe_user = safe_slug(user_id)
        store_local = os.getenv("STORE_LOCAL_UPLOADS", "false").lower() not in {"false", "0", "no"}
        upload_root = current_app.config["UPLOAD_FOLDER"]
        warnings = []

        if not privacy_mode:
            try:
                require_storage_client()
            except Exception:
                return None, warnings, "Storage is not configured."


        for index, file in enumerate(files, start=1):
            if not file or not allowed_file(file.filename, current_app.config["ALLOWED_EXT"]):
                warnings.append(f"Skipped unsupported file: {file.filename}")
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
                warnings.append(f"Failed to open {file.filename}")
                continue

            if crop_box:
                try:
                    image = image.crop(crop_box)
                except Exception:
                    pass

            try:
                page_text, avg_conf, low_conf = ocr_image(image, lang=lang)
            except Exception as exc:
                warnings.append(f"OCR failed on {file.filename}: {exc}")
                continue

            page_block = f"--- Page {index} ---\n{page_text.strip()}"
            combined_text.append(page_block.strip())
            combined_conf.append(avg_conf)
            combined_low_conf.extend(low_conf)

            storage_path = local_rel_path.replace("\\", "/")
            upload_ok = False
            if not privacy_mode:
                try:
                    upload_ok = upload_to_storage(file_path, storage_path) is not None
                except Exception as exc:
                    return None, warnings, f"Storage upload failed: {exc}"

            if not privacy_mode:
                image_paths.append(storage_path)

            if not privacy_mode and not upload_ok:
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                return None, warnings, "Storage upload failed."

            if privacy_mode or not store_local:
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        if not combined_text:
            return None, warnings, "No valid images were processed."

        extracted_text = "\n\n".join(combined_text).strip()
        cleaned_text = clean_text(extracted_text) if cleanup else extracted_text
        intent = detect_intent(cleaned_text if detect_intent_flag else extracted_text) if detect_intent_flag else "auto"
        language = detect_language(cleaned_text)
        if autocorrect:
            cleaned_text = auto_correct_text(cleaned_text, language)

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

        try:
            upsert_scan(scan)
        except Exception as exc:
            return None, warnings, f"Database save failed: {exc}"
        if use_flash:
            for warn in warnings:
                flash(warn, "warn")
        return scan, warnings, None

    @app.route("/dashboard")
    def dashboard():
        if not require_login():
            return redirect(url_for("login"))

        user_id = get_user_id()
        try:
            scans = list_scans(user_id)
        except Exception as exc:
            flash(f"Database error: {exc}", "warn")
            scans = []
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

        user_id = get_user_id()
        scan, warnings, error = _process_upload(request.files.getlist("images"), user_id, use_flash=True)
        if error:
            flash(error, "warn")
            return redirect(url_for("dashboard"))

        flash("OCR complete.", "success")
        return redirect(url_for("result", scan_id=scan["id"]))

    @app.route("/api/health")
    def api_health():
        return jsonify({"ok": True})

    @app.route("/api/scans", methods=["GET"])
    def api_scans():
        user_id = _api_user_id()
        if not user_id:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        try:
            scans = list_scans(user_id)
            return jsonify({"ok": True, "data": scans})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/scans", methods=["POST"])
    def api_upload():
        user_id = _api_user_id()
        if not user_id:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        scan, warnings, error = _process_upload(request.files.getlist("images"), user_id, use_flash=False)
        if error:
            return jsonify({"ok": False, "error": error, "warnings": warnings}), 400
        return jsonify({"ok": True, "data": scan, "warnings": warnings})

    @app.route("/api/scans/<scan_id>", methods=["GET"])
    def api_scan(scan_id):
        user_id = _api_user_id()
        if not user_id:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        try:
            scan = get_scan(scan_id)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        if not scan:
            return jsonify({"ok": False, "error": "Scan not found"}), 404
        if scan.get("user_id") != user_id:
            return jsonify({"ok": False, "error": "Forbidden"}), 403
        return jsonify({"ok": True, "data": scan})

    @app.route("/api/scans/<scan_id>", methods=["PATCH"])
    def api_scan_update(scan_id):
        user_id = _api_user_id()
        if not user_id:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        try:
            scan = get_scan(scan_id)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        if not scan:
            return jsonify({"ok": False, "error": "Scan not found"}), 404
        if scan.get("user_id") != user_id:
            return jsonify({"ok": False, "error": "Forbidden"}), 403

        payload = request.get_json(silent=True) or {}
        cleaned_text = (payload.get("cleaned_text") or scan.get("cleaned_text") or "").strip()
        tags = payload.get("tags") or scan.get("tags") or []
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

        scan["cleaned_text"] = cleaned_text
        scan["tags"] = tags
        scan["updated_at"] = now_iso()
        try:
            upsert_scan(scan)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        return jsonify({"ok": True, "data": scan})

    @app.route("/api/scans/<scan_id>", methods=["DELETE"])
    def api_scan_delete(scan_id):
        user_id = _api_user_id()
        if not user_id:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        try:
            scan = get_scan(scan_id)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        if not scan:
            return jsonify({"ok": False, "error": "Scan not found"}), 404
        if scan.get("user_id") != user_id:
            return jsonify({"ok": False, "error": "Forbidden"}), 403

        image_paths = scan.get("image_paths", [])
        for path in image_paths:
            local_path = os.path.join(current_app.config["UPLOAD_FOLDER"], path)
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass
        try:
            delete_from_storage(image_paths)
        except Exception:
            pass
        try:
            delete_scan_record(scan_id)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        return jsonify({"ok": True})

    @app.route("/result/<scan_id>")
    def result(scan_id):
        if not require_login():
            return redirect(url_for("login"))

        try:
            scan = get_scan(scan_id)
        except Exception as exc:
            flash(f"Database error: {exc}", "warn")
            return redirect(url_for("dashboard"))
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

        try:
            scan = get_scan(scan_id)
        except Exception as exc:
            flash(f"Database error: {exc}", "warn")
            return redirect(url_for("dashboard"))
        if not scan:
            flash("Scan not found.", "warn")
            return redirect(url_for("dashboard"))

        cleaned_text = request.form.get("cleaned_text", "").strip()
        tags = [tag.strip() for tag in request.form.get("tags", "").split(",") if tag.strip()]

        scan["cleaned_text"] = cleaned_text
        scan["tags"] = tags
        scan["updated_at"] = now_iso()

        try:
            upsert_scan(scan)
        except Exception as exc:
            flash(f"Save failed: {exc}", "warn")
            return redirect(url_for("result", scan_id=scan_id))
        flash("Saved successfully.", "success")
        return redirect(url_for("result", scan_id=scan_id))

    @app.route("/result/<scan_id>/export", methods=["POST"])
    def export_result(scan_id):
        if not require_login():
            return redirect(url_for("login"))

        try:
            scan = get_scan(scan_id)
        except Exception as exc:
            flash(f"Database error: {exc}", "warn")
            return redirect(url_for("dashboard"))
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

        try:
            scan = get_scan(scan_id)
        except Exception as exc:
            flash(f"Database error: {exc}", "warn")
            return redirect(url_for("dashboard"))
        if not scan:
            flash("Scan not found.", "warn")
            return redirect(url_for("dashboard"))

        target_lang = request.form.get("target_lang", "en")
        source_text = scan.get("cleaned_text") or scan.get("extracted_text", "")
        try:
            from services.free_ai import translate_text

            translated, source_lang = translate_text(source_text, target_lang)
            scan["translation"] = {
                "target": target_lang,
                "source": source_lang,
                "text": translated,
                "created_at": now_iso(),
            }
            upsert_scan(scan)
            log_translation(scan_id, scan.get("user_id"), source_lang, target_lang, translated)
            flash("Translation complete.", "success")
        except Exception as exc:
            flash(f"Translation failed: {exc}", "warn")
        return redirect(url_for("result", scan_id=scan_id))

    @app.route("/result/<scan_id>/tts", methods=["POST"])
    def tts_result(scan_id):
        if not require_login():
            return redirect(url_for("login"))
        try:
            scan = get_scan(scan_id)
        except Exception as exc:
            flash(f"Database error: {exc}", "warn")
            return redirect(url_for("dashboard"))
        if not scan:
            flash("Scan not found.", "warn")
            return redirect(url_for("dashboard"))

        text = scan.get("cleaned_text") or scan.get("extracted_text", "")
        if not text:
            flash("No text available for audio.", "warn")
            return redirect(url_for("result", scan_id=scan_id))

        lang_map = {
            "en": "en",
            "hi": "hi",
            "gu": "gu",
        }
        language_code = lang_map.get((scan.get("language") or "en")[:2], "en")
        speed = request.form.get("tts_speed", "normal")
        slow = speed == "slow"
        try:
            from services.free_ai import synthesize_speech

            audio_bytes = synthesize_speech(text[:4000], language_code=language_code, slow=slow)
            audio_name = f"audio_{scan_id}.mp3"
            storage_path = f"audio/{scan.get('user_id')}/{audio_name}"
            temp_path = os.path.join(current_app.config["UPLOAD_FOLDER"], storage_path)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            with open(temp_path, "wb") as handle:
                handle.write(audio_bytes)
            upload_to_storage(temp_path, storage_path)
            try:
                os.remove(temp_path)
            except Exception:
                pass

            scan["audio_path"] = storage_path
            scan["audio_updated_at"] = now_iso()
            upsert_scan(scan)
            flash("Audio generated.", "success")
        except Exception as exc:
            flash(f"TTS failed: {exc}", "warn")
        return redirect(url_for("result", scan_id=scan_id))

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        local_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(local_path):
            return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

        try:
            data, content_type = download_from_storage(filename)
            if data is not None:
                return send_file(io.BytesIO(data), mimetype=content_type)
        except Exception:
            pass

        return abort(404)
