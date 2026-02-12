from pathlib import Path

from flask import Flask, redirect, url_for

from .config import Settings, load_settings
from .repository import FileRepository
from .routes import bp as main_bp
from .routes import start_cleanup_worker
from .service import FileService


def _read_home_page(settings: Settings) -> str:
    if settings.home_page_path.exists():
        return settings.home_page_path.read_text(encoding="utf-8")
    return "<h1>ClickHouse</h1><p>Fast open-source OLAP database.</p>"


def create_app(settings: Settings | None = None, app_dir: Path | None = None) -> Flask:
    cfg = settings or load_settings(app_dir=app_dir)
    repo = FileRepository(cfg.db_path)
    service = FileService(cfg, repo)
    service.ensure_storage()
    repo.init_db()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_content_length
    app.extensions["settings"] = cfg
    app.extensions["home_page"] = _read_home_page(cfg)
    app.extensions["file_service"] = service
    app.register_blueprint(main_bp)

    @app.errorhandler(404)
    def not_found(_: Exception):
        return redirect(url_for("main.index"), code=302)

    if cfg.enable_background_cleanup:
        app.extensions["cleanup_thread"] = start_cleanup_worker(service)

    return app
