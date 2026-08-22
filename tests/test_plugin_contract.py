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
    assert manifest["kinds"] == ["panel", "bar-widget"]
    entry_point = ROOT / manifest["entryPoints"]["panel"]
    assert entry_point.is_file()
    assert not entry_point.is_symlink()
    widget = ROOT / manifest["entryPoints"]["barWidget"]
    assert widget.is_file()
    assert manifest["barWidget"]["defaultSection"] == "right"


def test_package_pins_a_public_limitless_library_revision() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "limitless-library @ git+https://github.com/univeracity/limitlesslibrary.git@" in project
    assert "7aece03bfbf68eb558e602de3bb50205593d8b52" in project


def test_cli_keeps_local_queries_bounded_to_omarchy_private_reuse() -> None:
    cli = (ROOT / "src" / "limitless_omarchy" / "cli.py").read_text(encoding="utf-8")

    assert 'choices=["omarchy-customization"]' in cli
    assert 'choices=["adopt", "instantiate"]' in cli
    assert 'choices=["private"]' in cli


def test_panel_exposes_host_lifecycle_and_uses_panel_owned_local_runtime() -> None:
    panel = (ROOT / "plugin" / "Panel.qml").read_text(encoding="utf-8")
    contents = (ROOT / "plugin" / "PanelContents.qml").read_text(encoding="utf-8")

    assert "function open(payloadJson)" in panel
    assert "function close()" in panel
    assert '"/scripts/limitless-omarchy-runtime"' in panel
    assert "function installRuntime()" in panel
    assert "function queryCatalog()" in panel
    assert "function queryExample()" in panel
    assert "function activateService()" in panel
    assert "function inspectService()" in panel
    assert "function queryService()" in panel
    assert "function stageServiceArtifact()" in panel
    assert "function prepareServiceArtifactReview()" in panel
    assert "function installServiceArtifactDisabled()" in panel
    assert "function enableServiceArtifact()" in panel
    assert "function publishContribution()" in panel
    assert "function inspectPublication()" in panel
    assert "function withdrawPublication()" in panel
    assert "function runPublication(" in panel
    assert "function openPublicationPolicy()" in panel
    assert "stdinEnabled: true" in panel
    assert "command.write(root.pendingInput" in panel
    assert 'root.serviceObjective = ""' in panel
    assert "PanelContents" in panel
    assert "Flickable" in contents
    assert "Math.min(content.implicitHeight + 40, 680)" in contents
    assert "TextInput" in contents
    assert "Try included example" in contents
    assert "Use Limitless service (optional)" in contents
    assert "Enable official service" in contents
    assert "Inspect trust boundary" in contents
    assert "Query managed service" in contents
    assert "Prepare verified plugin review" in contents
    assert "Install reviewed plugin disabled" in contents
    assert "Enable reviewed plugin" in contents
    assert "Share a reviewed contribution (optional)" in contents
    assert "Limitless does not scan the workspace" in contents
    assert "Open verified public publication policy" in contents
    assert "Publish explicitly selected draft" in contents
    assert "Check contribution status" in contents
    assert "Confirm withdrawal" in contents
    assert "profile file, or API key" in contents
    assert "serviceProfilePath" not in panel + contents
    assert "serviceAccessToken" not in panel + contents
    assert "authorization" not in panel + contents
    assert "WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive" in panel
    assert "selectionReference" in panel
    assert "method.summary" in panel
    assert "service-not-configured" not in panel
    assert "omarchy plugin enable" not in panel


def test_bar_widget_opens_the_panel_through_omarchy() -> None:
    widget = (ROOT / "plugin" / "BarWidget.qml").read_text(encoding="utf-8")

    assert 'moduleName: "univeracity.limitless-library"' in widget
    assert "WidgetButton" in widget
    assert "omarchy-shell shell toggle univeracity.limitless-library" in widget


def test_panel_runtime_is_syntax_valid_and_never_targets_system_python() -> None:
    runtime = ROOT / "scripts" / "limitless-omarchy-runtime"
    text = runtime.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(runtime)], check=True)
    assert "XDG_DATA_HOME" in text
    assert '"$runtime/bin/python" -m pip' in text
    assert "pip install --user" not in text
    assert "sudo" not in text
    assert '"$python_command" -m venv "$runtime"' in text
    assert 'mv -- "$stage/venv" "$runtime"' not in text
    assert "service-inspect" in text
    assert "service-query" in text
    assert "service-activate" in text
    assert "service-publication" in text
    assert "service-artifact-stage" in text
    assert "service-artifact-review" in text
    assert "service-artifact-install" in text
    assert "service-artifact-enable" in text
    assert "--objective" not in text
    assert "LIMITLESS_SERVICE_TOKEN" not in text


def test_panel_runtime_reports_setup_required_without_writing_to_the_system_python(tmp_path: Path) -> None:
    runtime = ROOT / "scripts" / "limitless-omarchy-runtime"
    environment = {**os.environ, "XDG_DATA_HOME": str(tmp_path / "xdg-data")}

    completed = subprocess.run(
        [str(runtime), "status", "--plugin-root", str(ROOT)],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert json.loads(completed.stdout) == {
        "schemaVersion": "limitless.omarchy-status/0.1",
        "mode": "setup-required",
        "service": {"connected": False, "reason": "local-runtime-not-installed"},
    }
    assert not (tmp_path / "xdg-data").exists()


def test_panel_runtime_forwards_publication_only_over_stdin(tmp_path: Path) -> None:
    runtime = ROOT / "scripts" / "limitless-omarchy-runtime"
    data_home = tmp_path / "xdg-data"
    runtime_bin = data_home / "limitless-omarchy" / "runtime" / "bin"
    runtime_bin.mkdir(parents=True)
    captured_arguments = tmp_path / "arguments.txt"
    captured_input = tmp_path / "input.json"
    _mock_command(
        runtime_bin,
        "limitless-omarchy",
        """#!/bin/sh
printf '%s\n' "$*" > "$CAPTURED_ARGUMENTS"
IFS= read -r line
printf '%s\n' "$line" > "$CAPTURED_INPUT"
printf '%s\n' '{"schemaVersion":"limitless.omarchy-publication-result/0.1","operation":"publish"}'
""",
    )
    payload = {
        "schemaVersion": "limitless.omarchy-publication-input/0.1",
        "operation": "publish",
        "draftPath": "/home/user/reviewed/publication.json",
        "statePath": None,
        "acceptedPublicationPolicyDigest": "sha256:" + "3" * 64,
        "reasonCode": None,
    }
    environment = {
        **os.environ,
        "XDG_DATA_HOME": str(data_home),
        "CAPTURED_ARGUMENTS": str(captured_arguments),
        "CAPTURED_INPUT": str(captured_input),
    }

    completed = subprocess.run(
        [str(runtime), "service-publication", "--plugin-root", str(ROOT)],
        input=json.dumps(payload) + "\n",
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert captured_arguments.read_text(encoding="utf-8").strip() == "service-publication"
    assert json.loads(captured_input.read_text(encoding="utf-8")) == payload
    assert "/home/user/reviewed" not in captured_arguments.read_text(encoding="utf-8")
    assert json.loads(completed.stdout)["operation"] == "publish"


def test_runtime_smoke_harness_is_syntax_valid_and_non_mutating() -> None:
    script = ROOT / "scripts" / "smoke-omarchy-panel"
    text = script.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(script)], check=True)
    assert "omarchy plugin validate" in text
    assert "omarchy plugin add" not in text
    assert "omarchy plugin enable" not in text
    assert "omarchy plugin remove" not in text


def test_visual_harness_renders_the_production_scroll_surface() -> None:
    harness = (ROOT / "tests" / "runtime" / "visual.qml").read_text(encoding="utf-8")

    assert "source: root.panelContentsPath" in harness
    assert '"/service-top.png"' in harness
    assert '"/service-bottom.png"' in harness
    assert "scroll.contentY = Math.max(0, scroll.contentHeight - scroll.height)" in harness


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
