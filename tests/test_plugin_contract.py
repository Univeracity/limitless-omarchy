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
    assert manifest["license"] == "Apache-2.0"
    assert manifest["kinds"] == ["panel", "bar-widget"]
    entry_point = ROOT / manifest["entryPoints"]["panel"]
    assert entry_point.is_file()
    assert not entry_point.is_symlink()
    widget = ROOT / manifest["entryPoints"]["barWidget"]
    assert widget.is_file()
    assert manifest["barWidget"]["defaultSection"] == "right"


def test_marketplace_submission_materials_are_complete() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    submission = (ROOT / "docs" / "MARKETPLACE-SUBMISSION.md").read_text(encoding="utf-8")
    baseline = ROOT / "scripts" / "verify-marketplace-baseline.mjs"
    preview = (ROOT / "preview.png").read_bytes()
    limitless_logo = (ROOT / "assets" / "limitless-library-logo.png").read_bytes()
    univeracity_logo = (ROOT / "assets" / "univeracity-logo.png").read_bytes()

    assert "omarchy plugin remove univeracity.limitless-library" in readme
    assert "Marketplace verification" in readme
    assert "review-required" in submission
    assert "package-manager" in submission
    assert "approved-and-verified" in submission
    assert baseline.is_file()
    assert preview.startswith(b"\x89PNG\r\n\x1a\n")
    assert limitless_logo.startswith(b"\x89PNG\r\n\x1a\n")
    assert univeracity_logo.startswith(b"\x89PNG\r\n\x1a\n")


def test_package_pins_a_public_limitless_library_revision() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "limitless-library @ git+https://github.com/univeracity/limitlesslibrary.git@" in project
    assert "bbd8d312151e01503c85bce40ebbb3fa22aee66d" in project


def test_cli_keeps_local_queries_bounded_to_omarchy_private_reuse() -> None:
    cli = (ROOT / "src" / "limitless_omarchy" / "cli.py").read_text(encoding="utf-8")

    assert 'choices=["omarchy-customization"]' in cli
    assert 'choices=["adopt", "instantiate"]' in cli
    assert 'choices=["private"]' in cli


def test_panel_exposes_host_lifecycle_and_uses_panel_owned_local_runtime() -> None:
    panel = (ROOT / "plugin" / "Panel.qml").read_text(encoding="utf-8")
    contents = (ROOT / "plugin" / "PanelContents.qml").read_text(encoding="utf-8")

    assert "function open(payloadJson)" in panel
    assert 'payload.section || "library"' in panel
    assert '"library", "agents", "service", "stats", "about"' in panel
    assert "function close()" in panel
    assert '"/scripts/limitless-omarchy-runtime"' in panel
    assert "function installRuntime()" in panel
    assert "function refreshAgentStatus()" in panel
    assert "function reconcileAgents()" in panel
    assert "function disconnectAgents()" in panel
    assert "function queryCatalog()" in panel
    assert "limitless.omarchy-local-query-input/0.1" in panel
    assert "function queryExample()" not in panel
    assert "function refreshStats()" in panel
    assert "function activateService()" in panel
    assert "function inspectService()" in panel
    assert "function queryService()" in panel
    assert "function stageServiceArtifact()" in panel
    assert "function prepareServiceArtifactReview()" in panel
    assert "function installServiceArtifactDisabled()" in panel
    assert "function enableServiceArtifact()" in panel
    assert "function openPublicationPolicy()" in panel
    assert "function transitionDraft(" in panel
    assert "function saveSettings()" in panel
    assert "stdinEnabled: true" in panel
    assert "command.write(root.pendingInput" in panel
    assert "command.running = false" in panel
    assert 'root.serviceObjective = ""' in panel
    assert "PanelContents" in panel
    assert "Flickable" in contents
    assert "implicitHeight: 680" in contents
    assert "TextInput" in contents
    assert 'text: "Library"' in contents
    assert 'text: "Agents"' in contents
    assert 'text: "Service"' in contents
    assert 'text: "Stats"' in contents
    assert 'text: "?"' in contents
    assert 'tooltipText: "About Limitless Library"' in contents
    assert 'root.panel.selectSection("about")' in contents
    assert "WELCOME TO THE LIMITLESS LIBRARY" in contents
    assert "WHY LIMITLESS" not in contents
    assert "WHY IT EXISTS" not in contents
    assert "WHERE IT CAME FROM" not in contents
    assert "THE LONG VIEW" in contents
    assert "As the Limitless Library grows, valuable work compounds across" in contents
    assert "Why reuse needs more than just search." in contents
    assert "Omarchy: the revolution will be customized." in contents
    assert "a Univeracity project" in contents
    assert 'source: Qt.resolvedUrl("../assets/limitless-library-logo.png")' in contents
    assert 'source: Qt.resolvedUrl("../assets/univeracity-logo.png")' in contents
    assert "© 2026 Limitless Library · Apache-2.0" in contents
    assert "function openOfficialUrl(url)" in panel
    assert "Qt.openUrlExternally(target)" in panel
    assert "https://limitlesslibrary.com" in panel + contents
    assert "property bool serviceUsageExceeded: false" in panel
    assert 'value.reason === "free-usage-exceeded"' in panel
    assert '"Free usage exceeded. Resets: "' in panel
    assert '"https://limitlesslibrary.com/#contact"' in panel
    assert 'text: "Upgrade or request more usage ↗"' in contents
    assert "root.panel.openUsageUpgrade()" in contents
    assert "https://univeracity.com" in panel + contents
    assert "https://github.com/Univeracity/limitless-omarchy" in panel + contents
    assert "Omarchy-specific queries" in contents
    assert "General queries" in contents
    assert "Only aggregate counters are stored locally" in contents
    assert "A wheel was left peacefully un-reinvented." in contents
    assert "activeSection" in panel + contents
    assert "PanelHero" in contents
    assert "PanelSectionHeader" in contents
    assert "ScrollBar.vertical" in contents
    assert "included example" not in (panel + contents).lower()
    assert "See what Limitless has been doing in the background." in contents
    assert "Looks like reuse showed up to work. Nice." in contents
    assert 'text: statTile.loading ? "◒" : statTile.value' in contents
    assert "running: statTile.loading" in contents
    assert "onRunningChanged: if (!running) statValue.rotation = 0" in contents
    assert "function heroMeta(fallback)" in contents
    assert 'root.panel.operation === "stats"' in contents
    assert "Checking for reusable work" not in contents
    assert "Component.onCompleted: Qt.callLater(function() { root.refresh() })" in panel
    assert 'completedOperation === "panel-state" && root.runtimeReady' in panel
    assert 'root.operation === "status") root.applyResult(root.commandOutput)' in panel
    assert "Agent connection" in contents
    assert "Optional additional agents" in contents
    assert "Apply selected agent connections" in contents
    assert "agentReportNeeded" in panel + contents
    assert "Disconnect plugin-owned agent connections" in contents
    assert "Connect to Limitless Library service" in contents
    assert "Local reuse is available. Opt in for service discovery." in contents
    assert "Local reuse is available. Checking service discovery." in contents
    assert "Local reuse and service discovery are available." in contents
    assert "Inspect trust boundary" in contents
    assert "Query Limitless Library service" in contents
    assert "Prepare verified plugin review" in contents
    assert "Install reviewed plugin disabled" in contents
    assert "Enable reviewed plugin" in contents
    assert "Library settings" in contents
    assert "DEFAULT SHARING" in contents
    assert "CONTRIBUTION MODE" in contents
    assert "Methods + exact sources" in contents
    assert "What are you about to make or change?" in contents
    assert "PUBLIC AND SHARED REUSE" in contents
    assert "View verified publication policy" in contents
    assert "MOVE AVAILABILITY" in contents
    assert "/absolute/path" not in contents
    assert "LOCAL CATALOG FOLDER" not in contents
    assert "profile file, or API key" in contents
    assert "serviceProfilePath" not in panel + contents
    assert "serviceAccessToken" not in panel + contents
    assert "standing authorization" in contents
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
    assert "stage_runtime_source" in text
    assert 'pip install \\\n      --disable-pip-version-check --no-input --upgrade "$plugin_root"' not in text
    assert 'pip install \\\n    --disable-pip-version-check --no-input "$plugin_root"' not in text
    assert "service-inspect" in text
    assert "service-query" in text
    assert "service-activate" in text
    assert "service-publication" in text
    assert "service-artifact-stage" in text
    assert "service-artifact-review" in text
    assert "service-artifact-install" in text
    assert "service-artifact-enable" in text
    assert "agent-status" in text
    assert "agent-reconcile" in text
    assert "agent-disconnect" in text
    assert "--objective" not in text
    assert "LIMITLESS_SERVICE_TOKEN" not in text


def test_panel_runtime_builds_from_an_xdg_snapshot_without_mutating_the_watched_plugin_tree(tmp_path: Path) -> None:
    runtime = ROOT / "scripts" / "limitless-omarchy-runtime"
    data_home = tmp_path / "xdg-data"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    pip_source_log = tmp_path / "pip-source.txt"
    fake_python = fake_bin / "python3"
    fake_python.write_text(
        """#!/bin/bash
set -euo pipefail
if [[ ${1:-} == "-m" && ${2:-} == "venv" ]]; then
  runtime=$3
  mkdir -p "$runtime/bin"
  cp "$0" "$runtime/bin/python"
  cat >"$runtime/bin/limitless-omarchy" <<'CLI'
#!/bin/bash
printf '%s\n' '{"schemaVersion":"limitless.omarchy-agent-connection/0.1","status":"configured"}'
CLI
  chmod +x "$runtime/bin/python" "$runtime/bin/limitless-omarchy"
  exit 0
fi
printf '%s\n' "${@: -1}" >"$PIP_SOURCE_LOG"
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    before = sorted(path.relative_to(ROOT) for path in ROOT.rglob("*") if path.is_file())
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "XDG_DATA_HOME": str(data_home),
        "PIP_SOURCE_LOG": str(pip_source_log),
    }

    completed = subprocess.run(
        [str(runtime), "setup", "--plugin-root", str(ROOT)],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    pip_source = Path(pip_source_log.read_text(encoding="utf-8").strip())
    assert pip_source.parent.parent == data_home / "limitless-omarchy"
    assert pip_source.name == "package"
    assert not pip_source.exists()
    assert json.loads(completed.stdout)["status"] == "configured"
    assert sorted(path.relative_to(ROOT) for path in ROOT.rglob("*") if path.is_file()) == before


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
        "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
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

    assert captured_arguments.read_text(encoding="utf-8").strip() == (
        f"service-publication --activity-path {data_home / 'limitless-omarchy' / 'activity.json'}"
    )
    assert json.loads(captured_input.read_text(encoding="utf-8")) == payload
    assert "/home/user/reviewed" not in captured_arguments.read_text(encoding="utf-8")
    assert json.loads(completed.stdout)["operation"] == "publish"


def test_panel_runtime_reconciles_the_default_and_optional_agents_through_its_owned_cli(tmp_path: Path) -> None:
    runtime = ROOT / "scripts" / "limitless-omarchy-runtime"
    data_home = tmp_path / "xdg-data"
    runtime_bin = data_home / "limitless-omarchy" / "runtime" / "bin"
    runtime_bin.mkdir(parents=True)
    captured_arguments = tmp_path / "arguments.txt"
    _mock_command(
        runtime_bin,
        "limitless-omarchy",
        """#!/bin/sh
printf '%s\\n' "$*" > "$CAPTURED_ARGUMENTS"
printf '%s\\n' '{"schemaVersion":"limitless.omarchy-agent-connection-report/0.1","results":[]}'
""",
    )
    environment = {
        **os.environ,
        "XDG_DATA_HOME": str(data_home),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
        "CAPTURED_ARGUMENTS": str(captured_arguments),
    }

    completed = subprocess.run(
        [
            str(runtime),
            "agent-reconcile",
            "--plugin-root",
            str(ROOT),
            "--additional-agent",
            "claude",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    arguments = captured_arguments.read_text(encoding="utf-8").strip().split()
    assert arguments[:7] == [
        "agent-reconcile",
        "--state-dir",
        str(data_home / "limitless-omarchy" / "agent-connection"),
        "--runtime-cli",
        str(runtime_bin / "limitless-omarchy"),
        "--catalog",
        str(data_home / "limitless-omarchy" / "catalog"),
    ]
    assert arguments[7:] == [
        "--settings-path",
        str(tmp_path / "xdg-config" / "limitless-omarchy" / "settings.json"),
        "--drafts-path",
        str(data_home / "limitless-omarchy" / "drafts"),
        "--activity-path",
        str(data_home / "limitless-omarchy" / "activity.json"),
        "--additional-agent",
        "claude",
    ]
    assert json.loads(completed.stdout)["schemaVersion"] == "limitless.omarchy-agent-connection-report/0.1"


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
    assert '"/preview.png"' in harness
    assert '"/agents.png"' in harness
    assert '"/stats.png"' in harness
    assert '"/about.png"' in harness
    assert '"/service-top.png"' in harness
    assert '"/quota.png"' in harness
    assert '"/library-settings.png"' in harness
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
