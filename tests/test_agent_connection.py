from __future__ import annotations

import json
import subprocess
from pathlib import Path

from limitless_omarchy.agent_connection import (
    agent_connection_status,
    disconnect_agent_connections,
    reconcile_agent_connections,
)


def _default_agent(config_home: Path, agent: str) -> None:
    path = config_home / "omarchy" / "defaults" / "agent"
    path.parent.mkdir(parents=True)
    path.write_text(f"{agent}\n", encoding="utf-8")


def _runtime(tmp_path: Path) -> tuple[Path, Path, Path]:
    runtime_cli = tmp_path / "runtime" / "bin" / "limitless-omarchy"
    runtime_cli.parent.mkdir(parents=True)
    runtime_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    state = tmp_path / "state"
    return runtime_cli, catalog, state


class FakeCodex:
    def __init__(self) -> None:
        self.descriptor: dict[str, object] | None = None
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: object) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)  # type: ignore[arg-type]
        self.calls.append(command)
        if command[:4] == ("codex", "mcp", "get", "--json"):
            if self.descriptor is None:
                return subprocess.CompletedProcess(command, 1, "", "No MCP server named 'limitless-omarchy' found.")
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "name": "limitless-omarchy",
                        "transport": {"type": "stdio", **self.descriptor},
                    }
                ),
                "",
            )
        if command[:4] == ("codex", "mcp", "add", "limitless-omarchy"):
            delimiter = command.index("--")
            self.descriptor = {"command": command[delimiter + 1], "args": list(command[delimiter + 2 :])}
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:4] == ("codex", "mcp", "remove", "limitless-omarchy"):
            self.descriptor = None
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "unexpected command")


def test_reconcile_connects_the_omarchy_default_and_disconnects_only_its_entry(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    home = tmp_path / "home"
    home.mkdir()
    _default_agent(config_home, "codex")
    runtime_cli, catalog, state = _runtime(tmp_path)
    codex = FakeCodex()

    report = reconcile_agent_connections(
        state,
        runtime_cli=runtime_cli,
        catalog=catalog,
        config_home=config_home,
        home=home,
        runner=codex,
    )

    assert report["defaultAgent"] == "codex"
    assert report["results"][-1] == {"agent": "codex", "status": "connected", "reason": "configured"}
    assert codex.descriptor == {"command": str(runtime_cli), "args": ["mcp", "--catalog", str(catalog)]}
    state_value = json.loads((state / "connection-state.json").read_text(encoding="utf-8"))
    assert set(state_value["managed"]) == {"codex"}

    disconnected = disconnect_agent_connections(state, home=home, runner=codex)

    assert disconnected["results"] == [{"agent": "codex", "status": "disconnected", "reason": "removed"}]
    assert codex.descriptor is None
    state_value = json.loads((state / "connection-state.json").read_text(encoding="utf-8"))
    assert state_value["managed"] == {}


def test_reconcile_keeps_an_unmanaged_same_name_entry_untouched(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    home = tmp_path / "home"
    home.mkdir()
    _default_agent(config_home, "codex")
    runtime_cli, catalog, state = _runtime(tmp_path)
    codex = FakeCodex()
    codex.descriptor = {"command": "/owner/server", "args": ["--owner"]}

    report = reconcile_agent_connections(
        state,
        runtime_cli=runtime_cli,
        catalog=catalog,
        config_home=config_home,
        home=home,
        runner=codex,
    )

    assert report["results"][-1] == {"agent": "codex", "status": "skipped", "reason": "existing-unmanaged-entry"}
    assert codex.descriptor == {"command": "/owner/server", "args": ["--owner"]}
    assert not any(call[:4] == ("codex", "mcp", "add", "limitless-omarchy") for call in codex.calls)


def test_reconcile_is_best_effort_when_an_extra_agent_is_not_yet_supported(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    home = tmp_path / "home"
    home.mkdir()
    _default_agent(config_home, "codex")
    runtime_cli, catalog, state = _runtime(tmp_path)
    codex = FakeCodex()

    report = reconcile_agent_connections(
        state,
        runtime_cli=runtime_cli,
        catalog=catalog,
        additional_agents=["omp", "not-an-agent"],
        config_home=config_home,
        home=home,
        runner=codex,
    )

    assert {tuple(item.items()) for item in report["results"]} >= {
        tuple({"agent": "codex", "status": "connected", "reason": "configured"}.items()),
        tuple({"agent": "omp", "status": "skipped", "reason": "mcp-configuration-not-yet-supported"}.items()),
        tuple({"agent": "not-an-agent", "status": "skipped", "reason": "unknown-agent"}.items()),
    }
    assert json.loads((state / "connection-state.json").read_text(encoding="utf-8"))["additionalAgents"] == ["omp"]


def test_status_reads_the_current_omarchy_default_without_mutating_it(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    home = tmp_path / "home"
    home.mkdir()
    _default_agent(config_home, "agy")
    state = tmp_path / "state"

    result = agent_connection_status(state, config_home=config_home, home=home, runner=FakeCodex())

    assert result["defaultAgent"] == "agy"
    assert result["connections"] == [{"agent": "agy", "status": "not-connected", "reason": "entry-absent"}]
    assert not state.exists()


def test_reconcile_configures_legacy_agy_profile_and_preserves_other_servers(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    home = tmp_path / "home"
    profile = home / ".gemini" / "antigravity" / "mcp_config.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        json.dumps(
            {
                "mcpServers": {"unrelated": {"command": "/owner/server", "args": ["--owner"]}},
                "unrelatedSetting": {"keep": True},
            }
        ),
        encoding="utf-8",
    )
    _default_agent(config_home, "agy")
    runtime_cli, catalog, state = _runtime(tmp_path)

    report = reconcile_agent_connections(
        state,
        runtime_cli=runtime_cli,
        catalog=catalog,
        config_home=config_home,
        home=home,
    )

    assert report["results"][-1] == {"agent": "agy", "status": "connected", "reason": "configured"}
    configured = json.loads(profile.read_text(encoding="utf-8"))
    assert configured["unrelatedSetting"] == {"keep": True}
    assert configured["mcpServers"]["unrelated"] == {"command": "/owner/server", "args": ["--owner"]}
    assert configured["mcpServers"]["limitless-omarchy"] == {
        "command": str(runtime_cli),
        "args": ["mcp", "--catalog", str(catalog)],
    }

    disconnected = disconnect_agent_connections(state, home=home)

    assert disconnected["results"] == [{"agent": "agy", "status": "disconnected", "reason": "removed"}]
    cleaned = json.loads(profile.read_text(encoding="utf-8"))
    assert "limitless-omarchy" not in cleaned["mcpServers"]
    assert cleaned["mcpServers"]["unrelated"] == {"command": "/owner/server", "args": ["--owner"]}


def test_reconcile_accepts_the_empty_modern_agy_profile(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    home = tmp_path / "home"
    profile = home / ".gemini" / "config" / "mcp_config.json"
    profile.parent.mkdir(parents=True)
    profile.touch()
    _default_agent(config_home, "agy")
    runtime_cli, catalog, state = _runtime(tmp_path)

    report = reconcile_agent_connections(
        state,
        runtime_cli=runtime_cli,
        catalog=catalog,
        config_home=config_home,
        home=home,
    )

    assert report["results"][-1] == {"agent": "agy", "status": "connected", "reason": "configured"}
    assert json.loads(profile.read_text(encoding="utf-8"))["mcpServers"]["limitless-omarchy"] == {
        "command": str(runtime_cli),
        "args": ["mcp", "--catalog", str(catalog)],
    }


def test_reconcile_respects_an_unmanaged_agy_entry(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    home = tmp_path / "home"
    profile = home / ".gemini" / "config" / "mcp_config.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        json.dumps({"mcpServers": {"limitless-omarchy": {"command": "/owner/server", "args": ["--owner"]}}}),
        encoding="utf-8",
    )
    _default_agent(config_home, "agy")
    runtime_cli, catalog, state = _runtime(tmp_path)

    report = reconcile_agent_connections(
        state,
        runtime_cli=runtime_cli,
        catalog=catalog,
        config_home=config_home,
        home=home,
    )

    assert report["results"][-1] == {"agent": "agy", "status": "skipped", "reason": "existing-unmanaged-entry"}
    assert json.loads(profile.read_text(encoding="utf-8"))["mcpServers"]["limitless-omarchy"] == {
        "command": "/owner/server",
        "args": ["--owner"],
    }
