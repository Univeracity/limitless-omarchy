from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("receipt", [None, b'{"old":"bundle"}\n'])
@pytest.mark.parametrize("action", ["status", "panel-state", "query", "service-query"])
def test_old_runtime_requests_update_without_invoking_it(tmp_path: Path, receipt: bytes | None, action: str) -> None:
    data = tmp_path / "data"
    runtime_root = data / "limitless-omarchy"
    binary = runtime_root / "runtime" / "bin" / "limitless-omarchy"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    binary.chmod(0o755)
    if receipt is not None:
        (runtime_root / "installed-bundle.json").write_bytes(receipt)
    local_method = runtime_root / "catalog" / "local-owned" / "capsule.json"
    local_method.parent.mkdir(parents=True)
    local_method.write_bytes(b"owner-local fixture\n")

    result = subprocess.run(
        [str(ROOT / "scripts" / "limitless-omarchy-runtime"), action, "--plugin-root", str(ROOT)],
        input="{}\n",
        env={**os.environ, "XDG_DATA_HOME": str(data)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["service"]["reason"] == "local-runtime-update-required"
    assert local_method.read_bytes() == b"owner-local fixture\n"


def test_matching_installed_bundle_runs_the_existing_runtime(tmp_path: Path) -> None:
    data = tmp_path / "data"
    runtime_root = data / "limitless-omarchy"
    binary = runtime_root / "runtime" / "bin" / "limitless-omarchy"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nprintf '%s\\n' '{\"mode\":\"local-only\"}'\n", encoding="utf-8")
    binary.chmod(0o755)
    (runtime_root / "installed-bundle.json").write_bytes((ROOT / "runtime" / "bundle.json").read_bytes())
    result = subprocess.run(
        [str(ROOT / "scripts" / "limitless-omarchy-runtime"), "status", "--plugin-root", str(ROOT)],
        env={**os.environ, "XDG_DATA_HOME": str(data)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {"mode": "local-only"}
