import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_dir: Path
    data_dir: Path
    files_dir: Path
    db_path: Path
    home_page_path: Path
    expire_seconds: int
    cleanup_interval_seconds: int
    max_content_length: int
    enable_background_cleanup: bool


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_settings(app_dir: Path | None = None) -> Settings:
    resolved_app_dir = (app_dir or Path(__file__).resolve().parents[2]).resolve()
    data_dir = Path(os.getenv("TMPSHARE_DATA_DIR", str(resolved_app_dir / "data"))).resolve()
    files_dir = (data_dir / "files").resolve()
    db_path = Path(os.getenv("TMPSHARE_DB_PATH", str(data_dir / "meta.db"))).resolve()
    home_page_path = Path(
        os.getenv("TMPSHARE_HOME_PAGE_PATH", str(resolved_app_dir / "CLICKHOUSE_HOME.html"))
    ).resolve()

    return Settings(
        app_dir=resolved_app_dir,
        data_dir=data_dir,
        files_dir=files_dir,
        db_path=db_path,
        home_page_path=home_page_path,
        expire_seconds=max(_int_env("TMPSHARE_EXPIRE_SECONDS", 60), 1),
        cleanup_interval_seconds=max(_int_env("TMPSHARE_CLEANUP_INTERVAL_SECONDS", 15), 1),
        max_content_length=max(_int_env("TMPSHARE_MAX_CONTENT_LENGTH", 100 * 1024 * 1024), 1),
        enable_background_cleanup=os.getenv("TMPSHARE_ENABLE_BG_CLEANUP", "true").lower()
        in {"1", "true", "yes", "on"},
    )
