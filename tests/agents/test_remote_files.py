from pathlib import Path

import pytest

from src.agents.remote_files import apply_transport_override, materialize_sources


class FakeResponse:
    headers = {"Content-Length": "4"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size):
        return b"data"


def test_materialize_downloads_and_cleans_remote_file(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())
    materialized = None
    with materialize_sources(["https://files.example/test.docx?signature=abc"], allowed_suffixes={".docx"}) as paths:
        materialized = Path(paths[0])
        assert materialized.read_bytes() == b"data"
    assert materialized is not None and not materialized.exists()


def test_allowed_hosts_and_suffixes_are_enforced(monkeypatch):
    monkeypatch.setenv("AGENT_FILE_ALLOWED_HOSTS", "files.example")
    with pytest.raises(ValueError, match="not allowed"):
        with materialize_sources(["https://evil.example/test.pdf"], allowed_suffixes={".pdf"}):
            pass
    with pytest.raises(ValueError, match="unsupported remote file extension"):
        with materialize_sources(["https://files.example/test.exe"], allowed_suffixes={".pdf"}):
            pass


def test_transport_override_preserves_query_and_signed_host(monkeypatch):
    monkeypatch.setenv(
        "AGENT_FILE_TRANSPORT_OVERRIDES",
        '{"signed.example:9000":"http://minio:9000"}',
    )
    url, headers = apply_transport_override(
        "https://signed.example:9000/bucket/file.pdf?X-Amz-Signature=abc&x-id=GetObject"
    )
    assert url == "http://minio:9000/bucket/file.pdf?X-Amz-Signature=abc&x-id=GetObject"
    assert headers == {"Host": "signed.example:9000"}
