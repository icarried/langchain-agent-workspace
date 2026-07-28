from __future__ import annotations

import io
import mimetypes
from dataclasses import dataclass
from typing import Protocol

from .departments import Department
from .settings import DepartmentKnowledgeBaseSettings
from .storage import PreparedDocument


@dataclass(frozen=True, slots=True)
class ObjectLocation:
    bucket: str
    object_key: str


class DepartmentObjectStore(Protocol):
    def archive(
        self,
        department: Department,
        documents: list[PreparedDocument],
    ) -> list[ObjectLocation]: ...


class MinioDepartmentObjectStore:
    """Archive immutable originals in one private bucket per department."""

    def __init__(self, settings: DepartmentKnowledgeBaseSettings) -> None:
        if not settings.minio_access_key or not settings.minio_secret_key:
            raise RuntimeError(
                "department MinIO credentials are not configured; set "
                "DEPARTMENT_KB_MINIO_ACCESS_KEY and DEPARTMENT_KB_MINIO_SECRET_KEY"
            )
        if "://" in settings.minio_endpoint:
            raise ValueError(
                "DEPARTMENT_KB_MINIO_ENDPOINT must be host:port without a URL scheme"
            )
        if len(settings.minio_access_key) < 3 or len(settings.minio_secret_key) < 8:
            raise ValueError(
                "department MinIO access key must have at least 3 characters and "
                "secret key at least 8 characters"
            )
        from minio import Minio

        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def archive(
        self,
        department: Department,
        documents: list[PreparedDocument],
    ) -> list[ObjectLocation]:
        bucket = f"department-kb-{department.knowledge_id}"
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
        locations: list[ObjectLocation] = []
        for document in documents:
            object_key = (
                f"sha256/{document.sha256[:2]}/{document.sha256}/"
                f"{document.filename}"
            )
            try:
                self.client.stat_object(bucket, object_key)
            except Exception as exc:
                if not _is_missing_object(exc):
                    raise
                self.client.put_object(
                    bucket,
                    object_key,
                    io.BytesIO(document.data),
                    length=len(document.data),
                    content_type=(
                        mimetypes.guess_type(document.filename)[0]
                        or "application/octet-stream"
                    ),
                    metadata={"sha256": document.sha256},
                )
            locations.append(ObjectLocation(bucket=bucket, object_key=object_key))
        return locations


def _is_missing_object(exc: Exception) -> bool:
    code = getattr(exc, "code", "")
    return code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"} or "not found" in str(
        exc
    ).lower()
