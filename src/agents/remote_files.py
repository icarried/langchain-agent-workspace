from __future__ import annotations

import json
import os
import tempfile
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 30


@contextmanager
def materialize_sources(
    sources: list[str], *, allowed_suffixes: set[str], prefix: str = "agent-files-"
) -> Iterator[list[str]]:
    with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
        target_dir = Path(temporary)
        results: list[str] = []
        for index, source in enumerate(sources):
            if not is_http_url(source):
                results.append(source)
                continue
            filename = remote_filename(source)
            suffix = Path(filename).suffix.lower()
            if suffix not in allowed_suffixes:
                allowed = ", ".join(sorted(allowed_suffixes))
                raise ValueError(f"unsupported remote file extension {suffix or '<none>'}; expected {allowed}")
            target = target_dir / f"{index:03d}-{Path(filename).name}"
            download_remote_file(source, target)
            results.append(str(target))
        yield results


def download_remote_file(url: str, target: Path) -> None:
    _validate_remote_host(url)
    max_bytes = int(os.getenv("AGENT_FILE_MAX_BYTES", str(DEFAULT_MAX_BYTES)))
    timeout = float(os.getenv("AGENT_FILE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    transport_url, headers = apply_transport_override(url)
    headers["User-Agent"] = "agent-workspace/1.0"
    request = urllib.request.Request(transport_url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("remote file exceeds AGENT_FILE_MAX_BYTES")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("remote file exceeds AGENT_FILE_MAX_BYTES")
    target.write_bytes(data)


def apply_transport_override(url: str) -> tuple[str, dict[str, str]]:
    parsed = urllib.parse.urlparse(url)
    raw = os.getenv("AGENT_FILE_TRANSPORT_OVERRIDES", "").strip()
    if not raw:
        return url, {}
    overrides = json.loads(raw)
    replacement = overrides.get(parsed.netloc)
    if not replacement:
        return url, {}
    transport = urllib.parse.urlparse(replacement)
    if transport.scheme not in {"http", "https"} or not transport.netloc:
        raise ValueError("transport override must be an absolute HTTP(S) origin")
    mapped = parsed._replace(scheme=transport.scheme, netloc=transport.netloc)
    return urllib.parse.urlunparse(mapped), {"Host": parsed.netloc}


def remote_filename(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return Path(urllib.parse.unquote(parsed.path)).name or "download"


def is_http_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validate_remote_host(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("remote source must be an HTTP(S) URL without embedded credentials")
    allowed = {item.strip().lower() for item in os.getenv("AGENT_FILE_ALLOWED_HOSTS", "").split(",") if item.strip()}
    if allowed and parsed.hostname.lower() not in allowed and parsed.netloc.lower() not in allowed:
        raise ValueError(f"remote host is not allowed: {parsed.hostname}")
