from __future__ import annotations

import hashlib
import mimetypes
import re
import uuid
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from src.agents.openai_compatible_inputs import AttachmentReference
from src.agents.remote_files import is_http_url, read_remote_file, remote_filename

from .document_loader import SUPPORTED_EXTENSIONS
from .schemas import SavedDocument
from .schemas import ProgressCallback, ProgressEvent
from .settings import DepartmentKnowledgeBaseSettings


@dataclass(frozen=True, slots=True)
class PreparedDocument:
    filename: str
    data: bytes
    sha256: str


def prepare_sources(
    sources: list[str | AttachmentReference],
    settings: DepartmentKnowledgeBaseSettings,
    *,
    progress: ProgressCallback | None = None,
) -> list[PreparedDocument]:
    if len(sources) > settings.max_files_per_request:
        raise ValueError(
            f"too many files; maximum is {settings.max_files_per_request}"
        )
    prepared: list[PreparedDocument] = []
    seen: dict[str, str] = {}
    for index, raw_source in enumerate(sources, start=1):
        source = (
            raw_source
            if isinstance(raw_source, AttachmentReference)
            else AttachmentReference(url=raw_source, source_kind="legacy")
        )
        location = source.url
        display_name = source.filename or remote_filename(location)
        if progress:
            progress(
                ProgressEvent(
                    "download",
                    f"正在下载并校验第 {index}/{len(sources)} 个附件：{display_name}",
                )
            )
        if is_http_url(location):
            data, content_type = read_remote_file(location)
            filename = source.filename or remote_filename(location)
        else:
            if not settings.allow_local_files:
                raise ValueError("local file paths are disabled; use an HTTP(S) attachment URL")
            path = Path(location).resolve()
            if not path.is_file():
                raise ValueError(f"local attachment does not exist: {path.name}")
            data = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or ""
            filename = path.name
        filename = _safe_filename(filename, content_type)
        digest = hashlib.sha256(data).hexdigest()
        previous = seen.get(filename.casefold())
        if previous == digest:
            continue
        if previous is not None:
            raise ValueError(
                f"multiple attachments resolve to the same filename {filename!r}; "
                "rename one file before saving"
            )
        seen[filename.casefold()] = digest
        prepared.append(
            PreparedDocument(filename=filename, data=data, sha256=digest)
        )
        if progress:
            progress(
                ProgressEvent(
                    "download",
                    f"第 {index}/{len(sources)} 个附件下载并校验完成：{filename}",
                )
            )
    return prepared


def persist_documents(
    documents_dir: Path,
    documents: list[PreparedDocument],
) -> list[SavedDocument]:
    documents_dir.mkdir(parents=True, exist_ok=True)
    results: list[SavedDocument] = []
    for document in documents:
        target = documents_dir / document.filename
        unchanged = target.exists() and _sha256_file(target) == document.sha256
        if not unchanged:
            temporary = documents_dir / f".{uuid.uuid4().hex}.uploading"
            temporary.write_bytes(document.data)
            temporary.replace(target)
        results.append(
            SavedDocument(
                filename=target.name,
                sha256=document.sha256,
                size_bytes=len(document.data),
                unchanged=unchanged,
            )
        )
    return results


def describe_documents(
    documents_dir: Path,
    documents: list[PreparedDocument],
) -> list[SavedDocument]:
    return [
        SavedDocument(
            filename=document.filename,
            sha256=document.sha256,
            size_bytes=len(document.data),
            unchanged=(
                (target := documents_dir / document.filename).exists()
                and _sha256_file(target) == document.sha256
            ),
        )
        for document in documents
    ]


def _safe_filename(filename: str, content_type: str) -> str:
    normalized = unicodedata.normalize("NFC", filename)
    name = Path(normalized.replace("\\", "/")).name.strip()
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed == ".jpe":
            guessed = ".jpg"
        if guessed in SUPPORTED_EXTENSIONS:
            name = f"{Path(name).stem or 'document'}{guessed}"
            suffix = guessed
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"unsupported attachment extension {suffix or '<none>'}; expected {allowed}"
        )
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(name).stem).strip(" .")
    if not stem:
        stem = "document"
    return f"{stem[:120]}{suffix}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()
