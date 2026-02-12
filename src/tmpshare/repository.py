import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileRecord:
    file_id: str
    stored_name: str
    original_name: str
    download_name: str
    created_at: int
    first_download_at: int | None
    expire_at: int | None


class FileRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._conn() as conn:
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

    def insert_file(
        self,
        *,
        file_id: str,
        stored_name: str,
        original_name: str,
        download_name: str,
        created_at: int,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO files (
                    id, stored_name, original_name, download_name, created_at,
                    first_download_at, expire_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL)
                """,
                (file_id, stored_name, original_name, download_name, created_at),
            )
            conn.commit()

    def get_file(self, file_id: str) -> FileRecord | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if not row:
            return None
        return self._from_row(row)

    def set_first_download(self, file_id: str, first_download_at: int, expire_at: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE files SET first_download_at = ?, expire_at = ? WHERE id = ?",
                (first_download_at, expire_at, file_id),
            )
            conn.commit()

    def delete_file(self, file_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
            conn.commit()

    def list_expired(self, now_ts: int) -> list[FileRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM files WHERE expire_at IS NOT NULL AND expire_at <= ?",
                (now_ts,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> FileRecord:
        return FileRecord(
            file_id=row["id"],
            stored_name=row["stored_name"],
            original_name=row["original_name"],
            download_name=row["download_name"],
            created_at=row["created_at"],
            first_download_at=row["first_download_at"],
            expire_at=row["expire_at"],
        )
