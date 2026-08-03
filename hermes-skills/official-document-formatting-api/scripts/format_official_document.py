#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import zipfile


DEFAULT_BASE_URL = "http://127.0.0.1:10085/v1"
DEFAULT_MODEL = "official-document-formatting-agent"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def main() -> int:
    args = parse_args()
    document_url = validate_document_url(args.url)
    load_private_env()
    api_key = os.getenv("OFFICIAL_DOCUMENT_FORMATTING_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OFFICIAL_DOCUMENT_FORMATTING_API_KEY is required")
    base_url = (
        args.base_url
        or os.getenv("OFFICIAL_DOCUMENT_FORMATTING_BASE_URL", "").strip()
        or DEFAULT_BASE_URL
    ).rstrip("/")
    payload = {
        "model": args.model,
        "stream": False,
        "dry_run": args.dry_run,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "请按公司标准格式化这份公文，不得改写正文或表格内容。"},
                {"type": "file_url", "file_url": {"url": document_url}},
            ],
        }],
    }
    response = request_json(
        f"{base_url}/chat/completions", payload, api_key=api_key, timeout=args.timeout
    )
    message = extract_message(response)
    report = str(message.get("content", "")).strip()
    if args.dry_run:
        if message.get("file") is not None:
            raise SystemExit("dry-run response unexpectedly contained a file")
        print("STATUS=dry-run")
        print_report(report)
        return 0

    file_payload = message.get("file")
    if not isinstance(file_payload, dict):
        raise SystemExit("API response did not contain choices[0].message.file")
    content, filename, digest = validate_file_payload(file_payload)
    output = select_output_path(args, filename)
    write_atomic(output, content, force=args.force)
    print("STATUS=completed")
    print(f"OUTPUT_FILE={output.resolve()}")
    print(f"SHA256={digest}")
    print(f"SIZE={len(content)}")
    print_report(report)
    return 0


def load_private_env() -> None:
    configured = os.getenv("OFFICIAL_DOCUMENT_FORMATTING_ENV_FILE", "").strip()
    paths = [Path(configured).expanduser()] if configured else [
        Path(__file__).resolve().parents[1] / ".env.local",
        Path.home() / ".hermes" / "secrets" / "official-document-formatting-api.env",
    ]
    for path in paths:
        load_env_file(path)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise SystemExit(f"private environment file must have mode 600: {path}")
    allowed = {
        "OFFICIAL_DOCUMENT_FORMATTING_API_KEY",
        "OFFICIAL_DOCUMENT_FORMATTING_BASE_URL",
    }
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        if name in allowed:
            os.environ.setdefault(name, value.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Format one server-reachable DOC/DOCX URL through an OpenAI-compatible API."
    )
    parser.add_argument("--url", required=True, help="Server-reachable HTTP(S) DOC/DOCX URL")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path, help="Exact output DOCX path")
    destination.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / ".hermes" / "cache" / "official-document-formatting",
    )
    parser.add_argument("--base-url", help=f"OpenAI-compatible /v1 base URL; default: {DEFAULT_BASE_URL}")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Allow replacing an existing output")
    return parser.parse_args()


def validate_document_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("--url must be an HTTP(S) URL")
    if Path(urllib.parse.unquote(parsed.path)).suffix.lower() not in {".doc", ".docx"}:
        raise SystemExit("the URL path must end in .doc or .docx")
    return value


def request_json(url: str, payload: dict[str, Any], *, api_key: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = redact_urls(exc.read().decode("utf-8", errors="replace"))[:500]
        raise SystemExit(f"formatting API returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SystemExit(f"formatting API request failed: {type(exc).__name__}") from exc
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SystemExit("formatting API returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise SystemExit("formatting API returned a non-object JSON response")
    return value


def extract_message(response: dict[str, Any]) -> dict[str, Any]:
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SystemExit("API response did not contain choices[0].message") from exc
    if not isinstance(message, dict):
        raise SystemExit("API response message is invalid")
    return message


def validate_file_payload(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    if payload.get("status") != "completed" or payload.get("encoding") != "base64":
        raise SystemExit("API file payload is not a completed Base64 result")
    if payload.get("file_type") != "docx" or payload.get("mime_type") != DOCX_MIME:
        raise SystemExit("API file payload is not a DOCX")
    raw = payload.get("content_base64")
    if not isinstance(raw, str):
        raise SystemExit("API file payload has no Base64 content")
    try:
        content = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SystemExit("API file payload contains invalid Base64") from exc
    if payload.get("size") != len(content):
        raise SystemExit("API file size verification failed")
    digest = hashlib.sha256(content).hexdigest()
    if payload.get("sha256") != digest:
        raise SystemExit("API file SHA-256 verification failed")
    validate_docx(content)
    filename = Path(str(payload.get("filename", "formatted.docx"))).name
    if not filename.lower().endswith(".docx"):
        raise SystemExit("API output filename is not a DOCX")
    return content, filename, digest


def validate_docx(content: bytes) -> None:
    if not content.startswith(b"PK"):
        raise SystemExit("API output is not a ZIP-based DOCX")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                raise SystemExit("API output is missing required DOCX package members")
            if archive.testzip() is not None:
                raise SystemExit("API output DOCX ZIP integrity check failed")
    except zipfile.BadZipFile as exc:
        raise SystemExit("API output is not a valid DOCX ZIP") from exc


def select_output_path(args: argparse.Namespace, filename: str) -> Path:
    if args.output is not None:
        output = args.output.expanduser()
        if output.suffix.lower() != ".docx":
            raise SystemExit("--output must end in .docx")
        return output
    return args.output_dir.expanduser() / filename


def write_atomic(path: Path, content: bytes, *, force: bool) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise SystemExit(f"output already exists: {path}; use --force to replace it")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def redact_urls(value: str) -> str:
    return URL_RE.sub("<redacted-url>", value)


def print_report(report: str) -> None:
    print("REPORT_BEGIN")
    print(report)
    print("REPORT_END")


if __name__ == "__main__":
    raise SystemExit(main())
