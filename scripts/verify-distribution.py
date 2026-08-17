#!/usr/bin/env python3
"""Verify that an Omarchy plugin source distribution is actually usable."""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path

REQUIRED = {
    "LICENSE",
    "NOTICE",
    "README.md",
    "SECURITY.md",
    "MANIFEST.in",
    "manifest.json",
    "plugin/Panel.qml",
    "plugin/PanelContents.qml",
    "plugin/BarWidget.qml",
    "scripts/limitless-omarchy-runtime",
    "scripts/smoke-omarchy-panel",
    "scripts/verify-distribution.py",
    "docs/ARCHITECTURE.md",
    "docs/COMPATIBILITY.md",
    "docs/RUNTIME-SMOKE.md",
    "examples/catalog/reading-focus-method/capsule.json",
    "src/limitless_omarchy/adapter.py",
    "src/limitless_omarchy/mcp_server.py",
    "src/limitless_omarchy/provider.py",
}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-distribution.py PATH_TO_SDIST")
    archive_path = Path(sys.argv[1])
    with tarfile.open(archive_path, "r:gz") as archive:
        files = {
            Path(member.name).relative_to(Path(member.name).parts[0]).as_posix()
            for member in archive.getmembers()
            if member.isfile()
        }
    missing = sorted(REQUIRED - files)
    if missing:
        raise SystemExit(f"source distribution is missing required files: {', '.join(missing)}")
    print(f"source distribution contains {len(REQUIRED)} required integration files: {archive_path.name}")


if __name__ == "__main__":
    main()
