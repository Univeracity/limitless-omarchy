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
    ".github/scripts/changed_test_scope.py",
    "manifest.json",
    "preview.png",
    "assets/limitless-library-logo.png",
    "assets/univeracity-logo.png",
    "plugin/Panel.qml",
    "plugin/PanelContents.qml",
    "plugin/BarWidget.qml",
    "scripts/limitless-omarchy-runtime",
    "scripts/smoke-omarchy-panel",
    "scripts/verify-distribution.py",
    "scripts/verify-runtime-bundle.py",
    "scripts/verify-marketplace-baseline.mjs",
    "runtime/README.md",
    "runtime/bundle.json",
    "runtime/requirements.in",
    "runtime/requirements.lock",
    "runtime/wheels/limitless_library-0.1.0a0-py3-none-any.whl",
    "runtime/wheels/limitless_omarchy-0.1.1-py3-none-any.whl",
    "docs/ARCHITECTURE.md",
    "docs/COMPATIBILITY.md",
    "docs/RUNTIME-SMOKE.md",
    "docs/MARKETPLACE-SUBMISSION.md",
    "catalog/reading-focus-method/capsule.json",
    "src/limitless_omarchy/__init__.py",
    "src/limitless_omarchy/adapter.py",
    "src/limitless_omarchy/activity.py",
    "src/limitless_omarchy/agent_connection.py",
    "src/limitless_omarchy/cli.py",
    "src/limitless_omarchy/contributions.py",
    "src/limitless_omarchy/drafts.py",
    "src/limitless_omarchy/mcp_server.py",
    "src/limitless_omarchy/provider.py",
    "src/limitless_omarchy/service.py",
    "src/limitless_omarchy/settings.py",
    "src/limitless_omarchy/version.py",
    "tests/runtime/visual.qml",
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
