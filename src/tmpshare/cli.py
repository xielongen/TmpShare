import argparse
import http.client
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit


def _upload_target(base_url: str) -> tuple[type[http.client.HTTPConnection], str, str]:
    parsed = urlsplit(base_url.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("server URL must start with http:// or https://")
    if parsed.query or parsed.fragment:
        raise ValueError("server URL cannot contain a query or fragment")

    connection_type: type[http.client.HTTPConnection]
    connection_type = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    endpoint = f"{parsed.path.rstrip('/')}/api/upload" or "/api/upload"
    return connection_type, host, endpoint


def upload_file(
    file_path: Path,
    *,
    base_url: str,
    token: str | None = None,
    timeout: int = 120,
) -> dict[str, object]:
    if not file_path.is_file():
        raise ValueError(f"file does not exist: {file_path}")

    connection_type, host, endpoint = _upload_target(base_url)
    boundary = f"----tmpshare-{secrets.token_hex(16)}"
    safe_name = file_path.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    encoded_name = quote(file_path.name, safe="")
    prefix = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; '
        f"filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}\r\n"
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    suffix = f"\r\n--{boundary}--\r\n".encode()

    connection = connection_type(host, timeout=timeout)
    try:
        connection.putrequest("POST", endpoint)
        connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        content_length = len(prefix) + file_path.stat().st_size + len(suffix)
        connection.putheader("Content-Length", str(content_length))
        if token:
            connection.putheader("Authorization", f"Bearer {token}")
        connection.endheaders()
        connection.send(prefix)
        with file_path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                connection.send(chunk)
        connection.send(suffix)

        response = connection.getresponse()
        body = response.read()
        if not 200 <= response.status < 300:
            detail = body.decode("utf-8", errors="replace")
            raise RuntimeError(f"upload failed with HTTP {response.status}: {detail}")
        payload = json.loads(body)
        if not isinstance(payload, dict) or "download_url" not in payload:
            raise RuntimeError("server returned an invalid upload response")
        return payload
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="Upload a file to a TmpShare server and print its temporary download link.",
    )
    parser.add_argument("file", type=Path, help="file to upload")
    parser.add_argument(
        "--url",
        default=os.getenv("TMPSHARE_URL") or "http://127.0.0.1:8080",
        help="TmpShare base URL (env: TMPSHARE_URL)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("TMPSHARE_UPLOAD_TOKEN"),
        help="optional upload token (env: TMPSHARE_UPLOAD_TOKEN)",
    )
    parser.add_argument("--timeout", type=int, default=120, help="request timeout in seconds")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        payload = upload_file(
            args.file.expanduser().resolve(),
            base_url=args.url,
            token=args.token,
            timeout=args.timeout,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"tmpshare: {exc}", file=sys.stderr)
        return 1

    print(payload["download_url"])
    download_command = payload.get("curl_download")
    if download_command:
        print(download_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
