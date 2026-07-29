import argparse
import getpass
import http.client
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

DEFAULT_URL = "https://ishare.xie-longen.workers.dev"


@dataclass(frozen=True)
class ClientConfig:
    url: str = DEFAULT_URL
    upload_token: str | None = None


def client_config_path() -> Path:
    config_home = os.getenv("XDG_CONFIG_HOME")
    base_dir = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return base_dir / "ishare" / "config.json"


def load_client_config(path: Path | None = None) -> ClientConfig:
    config_path = path or client_config_path()
    if not config_path.exists():
        return ClientConfig()

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read client config {config_path}: {exc}") from exc

    url = payload.get("url") if isinstance(payload, dict) else None
    token = payload.get("upload_token") if isinstance(payload, dict) else None
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"client config {config_path} has an invalid URL")
    if token is not None and not isinstance(token, str):
        raise ValueError(f"client config {config_path} has an invalid upload token")
    _upload_target(url)
    return ClientConfig(url=url.rstrip("/"), upload_token=token or None)


def save_client_config(config: ClientConfig, path: Path | None = None) -> Path:
    _upload_target(config.url)
    config_path = path or client_config_path()
    config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    config_path.parent.chmod(0o700)
    temporary_path = config_path.with_name(f".{config_path.name}.{os.urandom(4).hex()}.tmp")
    payload = {"url": config.url.rstrip("/"), "upload_token": config.upload_token or None}

    try:
        descriptor = os.open(
            temporary_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            stat.S_IRUSR | stat.S_IWUSR,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(payload, destination, ensure_ascii=False, indent=2)
            destination.write("\n")
        os.replace(temporary_path, config_path)
        config_path.chmod(0o600)
    finally:
        temporary_path.unlink(missing_ok=True)
    return config_path


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
    encoded_name = quote(file_path.name, safe="")

    connection = connection_type(host, timeout=timeout)
    try:
        connection.putrequest("POST", endpoint)
        connection.putheader("Content-Type", "application/octet-stream")
        connection.putheader("Content-Length", str(file_path.stat().st_size))
        connection.putheader("X-File-Name", encoded_name)
        if token:
            connection.putheader("Authorization", f"Bearer {token}")
        connection.endheaders()
        with file_path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                connection.send(chunk)

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


def _parser(config: ClientConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="Upload a file to a TmpShare server and print its temporary download link.",
    )
    parser.add_argument("file", type=Path, help="file to upload")
    parser.add_argument(
        "--url",
        default=os.getenv("TMPSHARE_URL") or config.url,
        help="override the saved TmpShare URL",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("TMPSHARE_UPLOAD_TOKEN") or config.upload_token,
        help="override the saved upload token",
    )
    parser.add_argument("--timeout", type=int, default=120, help="request timeout in seconds")
    return parser


def _setup(argv: list[str]) -> int:
    current = load_client_config()
    parser = argparse.ArgumentParser(
        prog=f"{Path(sys.argv[0]).name} setup",
        description="Save the server URL and upload token for future uploads.",
    )
    parser.add_argument("url", nargs="?", default=current.url, help="TmpShare base URL")
    token_group = parser.add_mutually_exclusive_group()
    token_group.add_argument("--token", help="upload token (prefer the hidden prompt)")
    token_group.add_argument(
        "--token-file",
        type=Path,
        help="read the upload token from a file instead of exposing it on the command line",
    )
    token_group.add_argument(
        "--no-token",
        action="store_true",
        help="save a configuration for a server without upload authentication",
    )
    args = parser.parse_args(argv)

    if args.no_token:
        token = None
    elif args.token_file is not None:
        try:
            token = args.token_file.read_text(encoding="utf-8").strip() or None
        except OSError as exc:
            print(f"{Path(sys.argv[0]).name}: cannot read token file: {exc}", file=sys.stderr)
            return 1
    elif args.token is not None:
        token = args.token.strip() or None
    elif sys.stdin.isatty():
        token = getpass.getpass("Upload token (hidden; leave empty if disabled): ").strip() or None
    else:
        print(
            f"{Path(sys.argv[0]).name}: use --token or --no-token in a non-interactive shell",
            file=sys.stderr,
        )
        return 2

    try:
        saved_path = save_client_config(ClientConfig(url=args.url, upload_token=token))
    except (OSError, ValueError) as exc:
        print(f"{Path(sys.argv[0]).name}: {exc}", file=sys.stderr)
        return 1

    print(f"Saved server configuration to {saved_path}")
    print(f"URL: {args.url.rstrip('/')}")
    print(f"Upload token: {'configured' if token else 'not configured'}")
    return 0


def _show_config() -> int:
    try:
        config = load_client_config()
    except ValueError as exc:
        print(f"{Path(sys.argv[0]).name}: {exc}", file=sys.stderr)
        return 1
    print(f"Config file: {client_config_path()}")
    print(f"URL: {config.url}")
    print(f"Upload token: {'configured' if config.upload_token else 'not configured'}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "setup":
        return _setup(argv[1:])
    if argv and argv[0] == "config":
        if len(argv) != 1:
            print(f"usage: {Path(sys.argv[0]).name} config", file=sys.stderr)
            return 2
        return _show_config()

    try:
        config = load_client_config()
        args = _parser(config).parse_args(argv)
        payload = upload_file(
            args.file.expanduser().resolve(),
            base_url=args.url,
            token=args.token,
            timeout=args.timeout,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"{Path(sys.argv[0]).name}: {exc}", file=sys.stderr)
        return 1

    print(payload["download_url"])
    download_command = payload.get("curl_download")
    if download_command:
        print(download_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
