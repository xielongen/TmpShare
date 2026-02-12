import threading
import time
from datetime import datetime, timezone

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    request,
    send_file,
    url_for,
)

from .service import FileService

bp = Blueprint("main", __name__)


def _service() -> FileService:
    return current_app.extensions["file_service"]


def _home_html() -> str:
    return current_app.extensions["home_page"]


@bp.route("/", methods=["GET"])
def index() -> Response:
    return Response(_home_html(), status=200, mimetype="text/html")


@bp.route("/api/upload", methods=["POST"])
def upload() -> Response:
    svc = _service()
    svc.cleanup_expired()

    if "file" not in request.files:
        return jsonify({"error": "missing file field, use multipart key 'file'"}), 400

    upload_file = request.files["file"]
    if not upload_file or not upload_file.filename:
        return jsonify({"error": "empty file"}), 400

    file_id, download_name = svc.create_upload(
        original_name=upload_file.filename,
        file_stream=upload_file.stream,
    )

    base = request.host_url.rstrip("/")
    download_url = f"{base}/d/{file_id}"
    expires_rule = (
        "First successful download starts a "
        f"{svc.settings.expire_seconds}-second expiry timer."
    )
    return jsonify(
        {
            "message": "upload ok",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "download_url": download_url,
            "download_filename": download_name,
            "expires_rule": expires_rule,
            "curl_download": f"curl -L '{download_url}' -o '{download_name}'",
        }
    )


@bp.route("/d/<file_id>", methods=["GET"])
def download(file_id: str) -> Response:
    svc = _service()
    svc.cleanup_expired()

    status, record = svc.resolve_download(file_id)
    if status != "ok" or not record:
        return redirect(url_for("main.index"), code=302)

    file_path = svc.settings.files_dir / record.stored_name
    return send_file(file_path, as_attachment=True, download_name=record.download_name)


def start_cleanup_worker(service: FileService) -> threading.Thread:
    def runner() -> None:
        while True:
            try:
                service.cleanup_expired()
            except Exception:
                pass
            time.sleep(service.settings.cleanup_interval_seconds)

    thread = threading.Thread(target=runner, daemon=True, name="tmpshare-cleaner")
    thread.start()
    return thread
