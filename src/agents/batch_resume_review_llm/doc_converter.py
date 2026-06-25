from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def convert_doc_to_docx(data: bytes, *, source: str) -> bytes:
    """Convert a legacy Word .doc file to DOCX without running document macros."""
    with tempfile.TemporaryDirectory(prefix="batch-resume-doc-") as temp_dir:
        directory = Path(temp_dir)
        input_path = directory / "input.doc"
        output_path = directory / "input.docx"
        input_path.write_bytes(data)

        errors: list[str] = []
        if shutil.which("soffice"):
            try:
                _convert_with_libreoffice(input_path, directory)
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                errors.append(f"LibreOffice: {exc}")
        if not output_path.exists():
            try:
                _convert_with_word(input_path, output_path)
            except (ImportError, OSError, RuntimeError) as exc:
                errors.append(f"Microsoft Word: {exc}")

        if not output_path.exists():
            detail = "; ".join(errors) or "no converter is installed"
            raise ValueError(
                f"cannot convert legacy DOC resume '{source}': {detail}. "
                "Install LibreOffice, or Microsoft Word with pywin32 on Windows."
            )
        return output_path.read_bytes()


def _convert_with_libreoffice(input_path: Path, output_dir: Path) -> None:
    command = [
        str(shutil.which("soffice")),
        "--headless",
        "--convert-to",
        "docx",
        "--outdir",
        str(output_dir),
        str(input_path),
    ]
    completed = subprocess.run(  # noqa: S603 - executable path comes from shutil.which.
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ValueError(detail or f"conversion exited with {completed.returncode}")


def _convert_with_word(input_path: Path, output_path: Path) -> None:
    try:
        import win32com.client
    except ImportError as exc:
        raise ImportError("pywin32 is unavailable") from exc

    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        document = word.Documents.Open(
            str(input_path.resolve()),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
        )
        document.SaveAs2(str(output_path.resolve()), FileFormat=16)
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        if document is not None:
            document.Close(False)
        if word is not None:
            word.Quit()
