import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request, send_file, url_for


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"
DB_PATH = DATA_DIR / "meta.db"
HOME_PAGE_PATH = BASE_DIR / "CLICKHOUSE_HOME.html"

DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)


def now_ts() -> int:
    return int(time.time())


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                stored_name TEXT NOT NULL,
                original_name TEXT NOT NULL,
                download_name TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                first_download_at INTEGER,
                expire_at INTEGER
            )
            """
        )
        conn.commit()


def read_home_page() -> str:
    if HOME_PAGE_PATH.exists():
        return HOME_PAGE_PATH.read_text(encoding="utf-8")
    return "<h1>ClickHouse</h1><p>Fast open-source OLAP database.</p>"


HOME_PAGE = read_home_page()
app = Flask(__name__)


def cleanup_expired() -> int:
    removed = 0
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, stored_name FROM files WHERE expire_at IS NOT NULL AND expire_at <= ?",
            (now_ts(),),
        ).fetchall()
        for row in rows:
            file_path = FILES_DIR / row["stored_name"]
            if file_path.exists():
                file_path.unlink()
            conn.execute("DELETE FROM files WHERE id = ?", (row["id"],))
            removed += 1
        conn.commit()
    return removed


def background_cleaner() -> None:
    while True:
        try:
            cleanup_expired()
        except Exception:
            pass
        time.sleep(15)


@app.route("/", methods=["GET"])
def index() -> Response:
    return Response(HOME_PAGE, status=200, mimetype="text/html")


@app.route("/api/upload", methods=["POST"])
def upload() -> Response:
    cleanup_expired()
    if "file" not in request.files:
        return jsonify({"error": "missing file field, use multipart key 'file'"}), 400

    upload_file = request.files["file"]
    if not upload_file or not upload_file.filename:
        return jsonify({"error": "empty file"}), 400

    ext = Path(upload_file.filename).suffix
    file_id = secrets.token_urlsafe(24)
    download_name = f"{secrets.token_hex(8)}{ext}" if ext else secrets.token_hex(8)
    stored_name = f"{file_id}.bin"
    save_path = FILES_DIR / stored_name
    upload_file.save(save_path)

    created_at = now_ts()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO files (id, stored_name, original_name, download_name, created_at, first_download_at, expire_at)
            VALUES (?, ?, ?, ?, ?, NULL, NULL)
            """,
            (file_id, stored_name, upload_file.filename, download_name, created_at),
        )
        conn.commit()

    base = request.host_url.rstrip("/")
    download_url = f"{base}/d/{file_id}"
    return jsonify(
        {
            "message": "upload ok",
            "uploaded_at": iso_now(),
            "download_url": download_url,
            "download_filename": download_name,
            "expires_rule": "First successful download starts a 60-second expiry timer.",
            "curl_download": f"curl -L '{download_url}' -o '{download_name}'",
        }
    )


@app.route("/d/<file_id>", methods=["GET"])
def download(file_id: str) -> Response:
    cleanup_expired()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if not row:
            return redirect(url_for("index"), code=302)

        current = now_ts()
        if row["expire_at"] is not None and row["expire_at"] <= current:
            file_path = FILES_DIR / row["stored_name"]
            if file_path.exists():
                file_path.unlink()
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
            conn.commit()
            return redirect(url_for("index"), code=302)

        if row["first_download_at"] is None:
            expire_at = current + 60
            conn.execute(
                "UPDATE files SET first_download_at = ?, expire_at = ? WHERE id = ?",
                (current, expire_at, file_id),
            )
            conn.commit()

    file_path = FILES_DIR / row["stored_name"]
    if not file_path.exists():
        return redirect(url_for("index"), code=302)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=row["download_name"],
    )


@app.errorhandler(404)
def not_found(_: Exception) -> Response:
    return redirect(url_for("index"), code=302)


init_db()
t = threading.Thread(target=background_cleaner, daemon=True)
t.start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
