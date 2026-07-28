import json
import stat
import sys
import time
from io import BytesIO
from threading import Thread

from werkzeug.serving import make_server

from tmpshare.app import create_app
from tmpshare.cli import ClientConfig, load_client_config, main, save_client_config, upload_file
from tmpshare.config import Settings


def _build_settings(tmp_path, expire_seconds=60, unclaimed_expire_seconds=300, upload_token=None):
    app_dir = tmp_path
    data_dir = tmp_path / "data"
    files_dir = data_dir / "files"
    db_path = data_dir / "meta.db"
    home_page_path = tmp_path / "CLICKHOUSE_HOME.html"
    home_page_path.write_text("<h1>ClickHouse Home</h1>", encoding="utf-8")

    return Settings(
        app_dir=app_dir,
        data_dir=data_dir,
        files_dir=files_dir,
        db_path=db_path,
        home_page_path=home_page_path,
        expire_seconds=expire_seconds,
        unclaimed_expire_seconds=unclaimed_expire_seconds,
        cleanup_interval_seconds=1,
        max_content_length=10 * 1024 * 1024,
        enable_background_cleanup=False,
        upload_token=upload_token,
    )


def test_not_found_redirects_to_home(tmp_path):
    app = create_app(settings=_build_settings(tmp_path))
    client = app.test_client()

    resp = client.get("/not-found")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_upload_and_download_flow(tmp_path):
    app = create_app(settings=_build_settings(tmp_path))
    client = app.test_client()

    upload_resp = client.post(
        "/api/upload",
        data={"file": (BytesIO(b"hello"), "a.txt")},
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 200
    payload = upload_resp.get_json()
    assert payload is not None
    assert payload["download_url"].startswith("http://localhost/d/")

    token = payload["download_url"].rsplit("/", 1)[-1]
    download_resp = client.get(f"/d/{token}")
    assert download_resp.status_code == 200
    assert download_resp.data == b"hello"
    assert "attachment;" in download_resp.headers["Content-Disposition"]


def test_download_expires_after_first_download(tmp_path):
    app = create_app(settings=_build_settings(tmp_path, expire_seconds=1))
    client = app.test_client()

    upload_resp = client.post(
        "/api/upload",
        data={"file": (BytesIO(b"ttl"), "ttl.txt")},
        content_type="multipart/form-data",
    )
    token = upload_resp.get_json()["download_url"].rsplit("/", 1)[-1]

    first = client.get(f"/d/{token}")
    assert first.status_code == 200

    time.sleep(2)
    second = client.get(f"/d/{token}")
    assert second.status_code == 302
    assert second.headers["Location"].endswith("/")


def test_unclaimed_upload_expires(tmp_path, monkeypatch):
    app = create_app(settings=_build_settings(tmp_path, unclaimed_expire_seconds=10))
    client = app.test_client()
    service = app.extensions["file_service"]
    monkeypatch.setattr(service, "now_ts", lambda: 100)

    upload_resp = client.post(
        "/api/upload",
        data={"file": (BytesIO(b"unclaimed"), "unclaimed.txt")},
        content_type="multipart/form-data",
    )
    token = upload_resp.get_json()["download_url"].rsplit("/", 1)[-1]

    monkeypatch.setattr(service, "now_ts", lambda: 111)
    expired = client.get(f"/d/{token}")
    assert expired.status_code == 302
    assert service.repo.get_file(token) is None


def test_upload_token_is_optional_and_enforced_when_configured(tmp_path):
    app = create_app(settings=_build_settings(tmp_path, upload_token="test-token"))
    client = app.test_client()

    denied = client.post(
        "/api/upload",
        data={"file": (BytesIO(b"private"), "private.txt")},
        content_type="multipart/form-data",
    )
    assert denied.status_code == 401

    allowed = client.post(
        "/api/upload",
        headers={"Authorization": "Bearer test-token"},
        data={"file": (BytesIO(b"private"), "private.txt")},
        content_type="multipart/form-data",
    )
    assert allowed.status_code == 200


def test_cli_streaming_upload_uses_public_api(tmp_path):
    app = create_app(settings=_build_settings(tmp_path, upload_token="cli-token"))
    server = make_server("127.0.0.1", 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    source = tmp_path / "cli-example.txt"
    source.write_bytes(b"uploaded through cli")

    try:
        payload = upload_file(
            source,
            base_url=f"http://127.0.0.1:{server.server_port}",
            token="cli-token",
        )
        token = str(payload["download_url"]).rsplit("/", 1)[-1]
        response = app.test_client().get(f"/d/{token}")
        assert response.status_code == 200
        assert response.data == b"uploaded through cli"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_client_config_is_private_and_round_trips(tmp_path):
    config_path = tmp_path / "ishare" / "config.json"
    saved_path = save_client_config(
        ClientConfig(url="https://share.example.test/", upload_token="local-secret"),
        path=config_path,
    )

    assert saved_path == config_path
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(config_path.parent.stat().st_mode) == 0o700
    assert load_client_config(config_path) == ClientConfig(
        url="https://share.example.test",
        upload_token="local-secret",
    )
    assert json.loads(config_path.read_text(encoding="utf-8"))["upload_token"] == "local-secret"


def test_ishare_uses_saved_config_without_environment_variables(tmp_path, monkeypatch, capsys):
    app = create_app(settings=_build_settings(tmp_path, upload_token="saved-token"))
    server = make_server("127.0.0.1", 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    source = tmp_path / "saved-config.txt"
    source.write_bytes(b"saved configuration")
    config_home = tmp_path / "client-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.delenv("TMPSHARE_URL", raising=False)
    monkeypatch.delenv("TMPSHARE_UPLOAD_TOKEN", raising=False)
    save_client_config(
        ClientConfig(
            url=f"http://127.0.0.1:{server.server_port}",
            upload_token="saved-token",
        )
    )
    monkeypatch.setattr(sys, "argv", ["ishare", str(source)])

    try:
        assert main() == 0
        output = capsys.readouterr().out
        assert "http://127.0.0.1:" in output
        assert "saved-token" not in output
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_config_command_never_prints_token(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_client_config(ClientConfig(url="https://share.example.test", upload_token="hidden"))
    monkeypatch.setattr(sys, "argv", ["ishare", "config"])

    assert main() == 0
    output = capsys.readouterr().out
    assert "Upload token: configured" in output
    assert "hidden" not in output


def test_setup_prompts_for_token_and_saves_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("tmpshare.cli.getpass.getpass", lambda _: "prompt-token")
    monkeypatch.setattr(sys, "argv", ["ishare", "setup", "https://share.example.test/"])

    assert main() == 0
    config = load_client_config()
    assert config == ClientConfig(
        url="https://share.example.test",
        upload_token="prompt-token",
    )
    output = capsys.readouterr().out
    assert "Upload token: configured" in output
    assert "prompt-token" not in output
