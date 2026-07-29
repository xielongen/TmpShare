CREATE TABLE IF NOT EXISTS files (
    token TEXT PRIMARY KEY,
    object_key TEXT NOT NULL UNIQUE,
    download_name TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    first_download_at INTEGER,
    expire_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_files_expire_at
    ON files(expire_at)
    WHERE expire_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_files_unclaimed
    ON files(created_at)
    WHERE first_download_at IS NULL;
