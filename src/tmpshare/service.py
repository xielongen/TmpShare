import secrets
import time
from pathlib import Path
from typing import BinaryIO

from .config import Settings
from .repository import FileRecord, FileRepository


class FileService:
    def __init__(self, settings: Settings, repo: FileRepository) -> None:
        self.settings = settings
        self.repo = repo

    @staticmethod
    def now_ts() -> int:
        return int(time.time())

    def ensure_storage(self) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.files_dir.mkdir(parents=True, exist_ok=True)

    def cleanup_expired(self) -> int:
        removed = 0
        expired = self.repo.list_expired(self.now_ts())
        for item in expired:
            file_path = self.settings.files_dir / item.stored_name
            if file_path.exists():
                file_path.unlink()
            self.repo.delete_file(item.file_id)
            removed += 1
        return removed

    def create_upload(
        self,
        *,
        original_name: str,
        file_stream: BinaryIO,
    ) -> tuple[str, str]:
        ext = Path(original_name).suffix
        file_id = secrets.token_urlsafe(24)
        download_name = f"{secrets.token_hex(8)}{ext}" if ext else secrets.token_hex(8)
        stored_name = f"{file_id}.bin"
        save_path = self.settings.files_dir / stored_name

        with save_path.open("wb") as f:
            f.write(file_stream.read())

        self.repo.insert_file(
            file_id=file_id,
            stored_name=stored_name,
            original_name=original_name,
            download_name=download_name,
            created_at=self.now_ts(),
        )
        return file_id, download_name

    def resolve_download(self, file_id: str) -> tuple[str, FileRecord | None]:
        record = self.repo.get_file(file_id)
        if not record:
            return "not_found", None

        now_value = self.now_ts()
        if record.expire_at is not None and record.expire_at <= now_value:
            file_path = self.settings.files_dir / record.stored_name
            if file_path.exists():
                file_path.unlink()
            self.repo.delete_file(record.file_id)
            return "expired", None

        if record.first_download_at is None:
            self.repo.set_first_download(
                file_id=record.file_id,
                first_download_at=now_value,
                expire_at=now_value + self.settings.expire_seconds,
            )
            record = self.repo.get_file(file_id)
            if not record:
                return "not_found", None

        file_path = self.settings.files_dir / record.stored_name
        if not file_path.exists():
            self.repo.delete_file(record.file_id)
            return "not_found", None

        return "ok", record
