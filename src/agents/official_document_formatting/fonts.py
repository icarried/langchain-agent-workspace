from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .schemas import FontInspection

REQUIRED_FONT_FAMILIES = (
    "方正小标宋简体",
    "黑体",
    "楷体_GB2312",
    "仿宋_GB2312",
)
FONT_ASSET_DIR = Path(__file__).with_name("fonts")


def inspect_required_fonts() -> FontInspection:
    fc_match = shutil.which("fc-match")
    if not fc_match:
        return FontInspection(
            available=(),
            missing=REQUIRED_FONT_FAMILIES,
            fontconfig_available=False,
        )

    available: list[str] = []
    missing: list[str] = []
    for family in REQUIRED_FONT_FAMILIES:
        try:
            completed = subprocess.run(
                [fc_match, "--format=%{family}", family],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            missing.append(family)
            continue
        matched_families = {
            value.strip().casefold()
            for value in completed.stdout.replace(",", "\n").splitlines()
            if value.strip()
        }
        if family.casefold() in matched_families:
            available.append(family)
        else:
            missing.append(family)
    return FontInspection(
        available=tuple(available),
        missing=tuple(missing),
        fontconfig_available=True,
    )

