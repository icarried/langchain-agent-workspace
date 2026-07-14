"""Build a self-contained distribution archive for a workspace agent."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
AGENTS_ROOT = WORKSPACE_ROOT / "src" / "agents"
EXTERNAL_IMPORT_PATTERN = re.compile(
    r"^\s*(?:from|import)\s+src(?:\.|\s|$)", re.MULTILINE
)


def _load_manifest(agent_dir: Path) -> dict[str, Any]:
    manifest_path = agent_dir / "standalone_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"缺少独立打包清单: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _validate_agent(agent_dir: Path, manifest: dict[str, Any]) -> None:
    vendored_sources = set(manifest.get("workspace_files", {}))
    violations: list[str] = []
    for source_path in agent_dir.rglob("*.py"):
        if "standalone" in source_path.parts or "__pycache__" in source_path.parts:
            continue
        source = source_path.read_text(encoding="utf-8")
        if not EXTERNAL_IMPORT_PATTERN.search(source):
            continue
        imported_modules = re.findall(r"src\.agents\.([A-Za-z0-9_]+)", source)
        missing = [
            module
            for module in imported_modules
            if f"src/agents/{module}.py" not in vendored_sources
        ]
        if missing or not imported_modules:
            violations.append(str(source_path.relative_to(agent_dir)))
    if violations:
        joined = ", ".join(sorted(violations))
        raise ValueError(f"智能体仍依赖工作区 src 包，不能独立打包: {joined}")


def _toml_array(values: list[str]) -> str:
    return "[\n" + "".join(f"  {json.dumps(value)},\n" for value in values) + "]"


def _render_pyproject(manifest: dict[str, Any]) -> str:
    distribution = manifest["distribution_name"]
    package = manifest["package_name"]
    package_data = manifest.get("package_data", [])
    dependencies = manifest.get("dependencies", [])
    description = manifest.get("description", "Standalone workspace agent")
    return f'''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = {json.dumps(distribution)}
version = {json.dumps(manifest["version"])}
description = {json.dumps(description)}
readme = "README.md"
requires-python = {json.dumps(manifest.get("python_requires", ">=3.11"))}
dependencies = {_toml_array(dependencies)}

[project.scripts]
{manifest["console_script"]} = "{package}.cli:app"

[tool.setuptools]
package-dir = {{"" = "src"}}
include-package-data = true

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
{package} = {_toml_array(package_data)}
'''


def _copy_agent_source(agent_dir: Path, destination: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in {"__pycache__", "standalone"}}
        ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
        ignored.add("standalone_manifest.json")
        return ignored

    shutil.copytree(agent_dir, destination, ignore=ignore)


def _copy_standalone_files(agent_dir: Path, bundle_root: Path) -> None:
    standalone_dir = agent_dir / "standalone"
    if not standalone_dir.is_dir():
        raise FileNotFoundError(f"缺少独立发行模板目录: {standalone_dir}")
    for source_path in standalone_dir.iterdir():
        target_name = "README.md" if source_path.name == "README.md" else source_path.name
        target_path = bundle_root / target_name
        if source_path.is_dir():
            shutil.copytree(source_path, target_path)
        else:
            shutil.copy2(source_path, target_path)


def _copy_workspace_files(
    workspace_root: Path, bundle_root: Path, manifest: dict[str, Any]
) -> None:
    for source_name, destination_name in manifest.get("workspace_files", {}).items():
        source_path = (workspace_root / source_name).resolve()
        if not source_path.is_relative_to(workspace_root) or not source_path.is_file():
            raise FileNotFoundError(f"共享打包文件不存在或越界: {source_name}")
        destination_path = (bundle_root / destination_name).resolve()
        if not destination_path.is_relative_to(bundle_root):
            raise ValueError(f"共享打包目标越界: {destination_name}")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)


def _write_checksums(bundle_root: Path, manifest: dict[str, Any]) -> None:
    files: dict[str, str] = {}
    for file_path in sorted(path for path in bundle_root.rglob("*") if path.is_file()):
        relative_path = file_path.relative_to(bundle_root).as_posix()
        if relative_path == "MANIFEST.sha256.json":
            continue
        files[relative_path] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    checksum_manifest = {
        "distribution": manifest["distribution_name"],
        "version": manifest["version"],
        "algorithm": "sha256",
        "files": files,
    }
    output_path = bundle_root / "MANIFEST.sha256.json"
    output_path.write_text(
        json.dumps(checksum_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_bundle(
    agent: str,
    output_dir: str | Path,
    *,
    workspace_root: str | Path = WORKSPACE_ROOT,
) -> Path:
    """Build a standalone ZIP and return its path."""
    root = Path(workspace_root).resolve()
    agent_dir = root / "src" / "agents" / agent
    if not agent_dir.is_dir():
        raise FileNotFoundError(f"智能体目录不存在: {agent_dir}")

    manifest = _load_manifest(agent_dir)
    _validate_agent(agent_dir, manifest)
    package = manifest["package_name"]
    archive_stem = f"{manifest['distribution_name']}-{manifest['version']}"
    resolved_output_dir = Path(output_dir)
    if not resolved_output_dir.is_absolute():
        resolved_output_dir = root / resolved_output_dir
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = resolved_output_dir / f"{archive_stem}.zip"

    with tempfile.TemporaryDirectory(prefix="agent-package-", dir=resolved_output_dir) as temp_dir:
        bundle_root = Path(temp_dir) / archive_stem
        package_dir = bundle_root / "src" / package
        package_dir.parent.mkdir(parents=True)
        _copy_agent_source(agent_dir, package_dir)
        _copy_standalone_files(agent_dir, bundle_root)
        _copy_workspace_files(root, bundle_root, manifest)
        (bundle_root / "pyproject.toml").write_text(
            _render_pyproject(manifest), encoding="utf-8"
        )
        _write_checksums(bundle_root, manifest)

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(path for path in bundle_root.rglob("*") if path.is_file()):
                archive.write(file_path, file_path.relative_to(bundle_root.parent))

    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="打包可脱离工作区运行的智能体")
    parser.add_argument(
        "--agent", default="batch_resume_review_llm", help="src/agents 下的包名"
    )
    parser.add_argument("--output-dir", default="dist", help="ZIP 输出目录")
    args = parser.parse_args()
    archive_path = build_bundle(args.agent, args.output_dir)
    print(archive_path)


if __name__ == "__main__":
    main()
