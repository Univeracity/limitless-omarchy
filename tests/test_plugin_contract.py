from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def test_manifest_is_a_valid_third_party_panel_contract() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["schemaVersion"] == 1
    assert manifest["id"] == "univeracity.limitless-library"
    assert not manifest["id"].startswith("omarchy.")
    assert manifest["kinds"] == ["panel"]
    entry_point = ROOT / manifest["entryPoints"]["panel"]
    assert entry_point.is_file()
    assert not entry_point.is_symlink()


def test_package_pins_a_public_limitless_library_revision() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "limitless-library @ git+https://github.com/univeracity/limitlesslibrary.git@" in project
    assert "3cc4839f87202422541a6aaa57a97d635f87f409" in project


def test_cli_keeps_local_queries_bounded_to_omarchy_private_reuse() -> None:
    cli = (ROOT / "src" / "limitless_omarchy" / "cli.py").read_text(encoding="utf-8")

    assert 'choices=["omarchy-customization"]' in cli
    assert 'choices=["adopt", "instantiate"]' in cli
    assert 'choices=["private"]' in cli


def test_panel_exposes_host_lifecycle_and_uses_local_companion() -> None:
    panel = (ROOT / "plugin" / "Panel.qml").read_text(encoding="utf-8")

    assert "function open(payloadJson)" in panel
    assert "function close()" in panel
    assert '["limitless-omarchy", "status"]' in panel
    assert '["limitless-omarchy", "query", "--catalog", catalogPath]' in panel
    assert "WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive" in panel
    assert "selectionReference" in panel
    assert "method.summary" in panel
    assert "service-not-configured" not in panel
    assert "omarchy plugin enable" not in panel


def test_runtime_smoke_harness_is_syntax_valid_and_non_mutating() -> None:
    script = ROOT / "scripts" / "smoke-omarchy-panel"
    text = script.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(script)], check=True)
    assert "omarchy plugin validate" in text
    assert "omarchy plugin add" not in text
    assert "omarchy plugin enable" not in text
    assert "omarchy plugin remove" not in text


def _mock_command(directory: Path, name: str, source: str) -> None:
    path = directory / name
    path.write_text(source, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.mark.parametrize("summon", [False, True])
def test_runtime_smoke_harness_only_summons_when_explicit(tmp_path: Path, summon: bool) -> None:
    if shutil.which("jq") is None:
        pytest.skip("jq is required by the real Omarchy smoke harness")

    commands = tmp_path / "commands"
    commands.mkdir()
    log = tmp_path / "commands.log"
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    _mock_command(
        commands,
        "omarchy",
        """#!/bin/sh
printf 'omarchy %s\\n' "$*" >> "$SMOKE_LOG"
if [ "$1" = plugin ] && [ "$2" = validate ]; then exit 0; fi
if [ "$1" = plugin ] && [ "$2" = list ]; then printf '%s\\n' '[{"id":"univeracity.limitless-library"}]'; exit 0; fi
exit 99
""",
    )
    _mock_command(
        commands,
        "omarchy-shell",
        """#!/bin/sh
printf 'omarchy-shell %s\\n' "$*" >> "$SMOKE_LOG"
""",
    )
    _mock_command(
        commands,
        "limitless-omarchy",
        """#!/bin/sh
printf 'limitless-omarchy %s\\n' "$*" >> "$SMOKE_LOG"
printf '%s\\n' '{"mode":"local-only","disposition":"source-free-method"}'
""",
    )
    environment = {
        **os.environ,
        "PATH": f"{commands}:{os.environ['PATH']}",
        "SMOKE_LOG": str(log),
    }
    command = [str(ROOT / "scripts" / "smoke-omarchy-panel"), "--catalog", str(catalog)]
    if summon:
        command.append("--summon")

    completed = subprocess.run(command, check=False, capture_output=True, text=True, env=environment)

    assert completed.returncode == 0, completed.stderr
    observed = log.read_text(encoding="utf-8")
    assert "omarchy plugin validate" in observed
    assert "limitless-omarchy query --catalog" in observed
    if summon:
        assert "omarchy plugin list --json" in observed
        assert "omarchy-shell shell summon univeracity.limitless-library" in observed
    else:
        assert "omarchy plugin list" not in observed
        assert "omarchy-shell" not in observed
    assert " plugin add" not in observed
    assert " plugin enable" not in observed
    assert " plugin update" not in observed
    assert " plugin remove" not in observed


def test_distribution_verifier_rejects_missing_plugin_assets(tmp_path: Path) -> None:
    archive = tmp_path / "incomplete.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        source = tmp_path / "README.md"
        source.write_text("placeholder", encoding="utf-8")
        output.add(source, arcname="limitless_omarchy-0.1.0a0/README.md")

    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify-distribution.py"), str(archive)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "plugin/Panel.qml" in completed.stderr
