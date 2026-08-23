"""Best-effort, ownership-aware MCP connection for Omarchy's agent choices.

The Omarchy plugin must make its selected default agent useful without
rewriting the rest of a user's agent configuration. This module uses a
supported client's documented MCP surface, records only the entries it created,
and verifies their exact command before it updates or removes anything.

An unavailable client, an unsupported client, or a configuration collision is
reported locally per target.  It never prevents another selected client from
being connected.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404
import tempfile
import tomllib
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AgentConnectionError(ValueError):
    """The local agent-connection request is malformed."""


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]

_SERVER_NAME = "limitless-omarchy"
_STATE_SCHEMA = "limitless.omarchy-agent-connection-state/0.1"
_REPORT_SCHEMA = "limitless.omarchy-agent-connection-report/0.1"
_STATUS_SCHEMA = "limitless.omarchy-agent-connection-status/0.1"

# This mirrors Omarchy's current default-agent chooser.  It is intentionally a
# closed list: a stray value in the host defaults file must not become a command
# or a configuration path supplied to an agent client.
_AGENTS: dict[str, str] = {
    "agy": "Antigravity",
    "claude": "Claude Code",
    "codex": "Codex",
    "copilot": "GitHub Copilot",
    "crush": "Crush",
    "grok": "Grok",
    "omp": "Oh My Pi",
    "opencode": "OpenCode",
    "pi": "Pi",
}

# Each of these adapters has a documented MCP configuration surface.  Agy's
# standalone profile predates its native MCP management commands, so its
# adapter writes only the exact, documented entry and verifies it afterwards.
# Other Omarchy agent choices remain visible in the panel and receive an
# explicit report rather than a guessed configuration-file edit.
_SUPPORTED_MCP_AGENTS = frozenset({"agy", "claude", "codex", "grok"})


def _default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603
        list(argv),
        capture_output=True,
        check=False,
        text=True,
        timeout=8,
    )


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured) if configured and Path(configured).is_absolute() else Path.home() / ".config"


def _require_directory(path: Path, *, label: str, create: bool) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute() or candidate.is_symlink():
        raise AgentConnectionError(f"{label} must be an absolute, non-symlink directory")
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
    if not candidate.is_dir():
        raise AgentConnectionError(f"{label} is unavailable")
    return candidate


def _require_regular_file(path: Path, *, label: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute() or candidate.is_symlink() or not candidate.is_file():
        raise AgentConnectionError(f"{label} must be an absolute, non-symlink regular file")
    return candidate


def _default_agent(config_home: Path) -> tuple[str | None, str | None]:
    path = Path(config_home) / "omarchy" / "defaults" / "agent"
    if path.is_symlink() or not path.is_file():
        return None, "default-agent-not-set"
    try:
        value = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, UnicodeError, IndexError):
        return None, "default-agent-unreadable"
    if value not in _AGENTS:
        return None, "default-agent-unsupported"
    return value, None


def _normalize_additional(values: Iterable[str], default_agent: str | None) -> tuple[list[str], list[dict[str, str]]]:
    selected: list[str] = []
    results: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, str) or value not in _AGENTS:
            results.append({"agent": str(value), "status": "skipped", "reason": "unknown-agent"})
            continue
        if value == default_agent or value in selected:
            continue
        selected.append(value)
    return selected, results


def _descriptor(runtime_cli: Path, catalog: Path) -> dict[str, Any]:
    return {
        "command": str(runtime_cli),
        "args": ["mcp", "--catalog", str(catalog)],
    }


def _codex_current(*, runner: Runner) -> tuple[str, dict[str, Any] | None, str | None]:
    try:
        completed = runner(("codex", "mcp", "get", "--json", _SERVER_NAME))
    except (OSError, subprocess.SubprocessError):
        return "unknown", None, "agent-client-unavailable"
    if completed.returncode != 0:
        text = f"{completed.stdout}\n{completed.stderr}"
        if "No MCP server named" in text:
            return "absent", None, None
        return "unknown", None, "agent-configuration-unavailable"
    try:
        value = json.loads(completed.stdout)
        transport = value["transport"]
        if value.get("name") != _SERVER_NAME or transport.get("type") != "stdio":
            return "present", {"unrecognized": True}, None
        command = transport.get("command")
        args = transport.get("args")
        if (
            not isinstance(command, str)
            or not isinstance(args, list)
            or not all(isinstance(item, str) for item in args)
        ):
            return "present", {"unrecognized": True}, None
        return "present", {"command": command, "args": args}, None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return "unknown", None, "agent-configuration-unreadable"


def _claude_current(*, home: Path) -> tuple[str, dict[str, Any] | None, str | None]:
    path = home / ".claude.json"
    if not path.exists():
        return "absent", None, None
    if path.is_symlink() or not path.is_file():
        return "unknown", None, "agent-configuration-unreadable"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        servers = value.get("mcpServers", {})
        if not isinstance(servers, dict):
            return "unknown", None, "agent-configuration-unreadable"
        entry = servers.get(_SERVER_NAME)
        if entry is None:
            return "absent", None, None
        if not isinstance(entry, dict) or entry.get("type") != "stdio":
            return "present", {"unrecognized": True}, None
        command = entry.get("command")
        args = entry.get("args")
        if (
            not isinstance(command, str)
            or not isinstance(args, list)
            or not all(isinstance(item, str) for item in args)
        ):
            return "present", {"unrecognized": True}, None
        return "present", {"command": command, "args": args}, None
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return "unknown", None, "agent-configuration-unreadable"


def _grok_current(*, home: Path) -> tuple[str, dict[str, Any] | None, str | None]:
    path = home / ".grok" / "config.toml"
    if not path.exists():
        return "absent", None, None
    if path.is_symlink() or not path.is_file():
        return "unknown", None, "agent-configuration-unreadable"
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
        servers = value.get("mcp_servers", {})
        if not isinstance(servers, dict):
            return "unknown", None, "agent-configuration-unreadable"
        entry = servers.get(_SERVER_NAME)
        if entry is None:
            return "absent", None, None
        if not isinstance(entry, dict):
            return "present", {"unrecognized": True}, None
        command = entry.get("command")
        args = entry.get("args")
        if (
            not isinstance(command, str)
            or not isinstance(args, list)
            or not all(isinstance(item, str) for item in args)
        ):
            return "present", {"unrecognized": True}, None
        return "present", {"command": command, "args": args}, None
    except (OSError, UnicodeError, ValueError, tomllib.TOMLDecodeError):
        return "unknown", None, "agent-configuration-unreadable"


def _agy_config_path(home: Path) -> Path:
    """Return the active Agy global profile without guessing over a migration.

    Current Antigravity CLI installations use ``.gemini/config``.  Older
    pre-migration installs, including Agy 1.0.x, keep their active profile in
    ``.gemini/antigravity``.  Prefer the current path whenever it exists; a
    later migration then cannot revive an obsolete profile by accident.
    """

    modern = home / ".gemini" / "config" / "mcp_config.json"
    legacy = home / ".gemini" / "antigravity" / "mcp_config.json"
    if modern.exists() or (modern.parent / ".migrated").exists():
        return modern
    if legacy.exists():
        return legacy
    return modern


def _agy_profile(*, home: Path) -> tuple[Path, dict[str, Any] | None, str | None]:
    """Load Agy's profile without exposing or rewriting unrelated fields."""

    path = _agy_config_path(home)
    if not path.exists():
        return path, {"mcpServers": {}}, None
    if path.is_symlink() or not path.is_file():
        return path, None, "agent-configuration-unreadable"
    try:
        raw = path.read_text(encoding="utf-8")
        # Agy 1.1.x treats a zero-byte modern profile as an empty server set.
        # Non-empty profiles remain strict JSON and fail without mutation.
        if not raw.strip():
            return path, {"mcpServers": {}}, None
        value = json.loads(raw)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return path, None, "agent-configuration-unreadable"
    if not isinstance(value, dict):
        return path, None, "agent-configuration-unreadable"
    servers = value.get("mcpServers", {})
    if not isinstance(servers, dict):
        return path, None, "agent-configuration-unreadable"
    return path, value, None


def _agy_current(*, home: Path) -> tuple[str, dict[str, Any] | None, str | None]:
    _path, profile, reason = _agy_profile(home=home)
    if profile is None:
        return "unknown", None, reason
    entry = profile["mcpServers"].get(_SERVER_NAME)
    if entry is None:
        return "absent", None, None
    if not isinstance(entry, dict):
        return "present", {"unrecognized": True}, None
    command = entry.get("command")
    args = entry.get("args")
    if not isinstance(command, str) or not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        return "present", {"unrecognized": True}, None
    return "present", {"command": command, "args": args}, None


def _agy_add(*, home: Path, descriptor: dict[str, Any]) -> tuple[bool, str | None]:
    path, profile, reason = _agy_profile(home=home)
    if profile is None:
        return False, reason
    if path.parent.exists() and (path.parent.is_symlink() or not path.parent.is_dir()):
        return False, "agent-configuration-unreadable"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        servers = profile.setdefault("mcpServers", {})
        if not isinstance(servers, dict) or _SERVER_NAME in servers:
            return False, "agent-configuration-unreadable"
        servers[_SERVER_NAME] = descriptor
        _write_json(path, profile)
    except OSError:
        return False, "agent-configuration-unavailable"
    return True, None


def _agy_remove(*, home: Path, descriptor: dict[str, Any]) -> tuple[bool, str | None]:
    path, profile, reason = _agy_profile(home=home)
    if profile is None:
        return False, reason
    servers = profile.get("mcpServers")
    if not isinstance(servers, dict) or servers.get(_SERVER_NAME) != descriptor:
        return False, "plugin-entry-modified"
    try:
        del servers[_SERVER_NAME]
        _write_json(path, profile)
    except OSError:
        return False, "agent-configuration-unavailable"
    return True, None


def _current(agent: str, *, home: Path, runner: Runner) -> tuple[str, dict[str, Any] | None, str | None]:
    if agent == "agy":
        return _agy_current(home=home)
    if agent == "codex":
        return _codex_current(runner=runner)
    if agent == "claude":
        return _claude_current(home=home)
    if agent == "grok":
        return _grok_current(home=home)
    return "unknown", None, "mcp-configuration-not-yet-supported"


def _add_command(agent: str, descriptor: dict[str, Any]) -> tuple[str, ...]:
    command = descriptor["command"]
    arguments = descriptor["args"]
    if agent == "codex":
        return ("codex", "mcp", "add", _SERVER_NAME, "--", command, *arguments)
    if agent == "claude":
        return ("claude", "mcp", "add", "--scope", "user", _SERVER_NAME, "--", command, *arguments)
    if agent == "grok":
        return ("grok", "mcp", "add", "--scope", "user", _SERVER_NAME, "--", command, *arguments)
    raise AgentConnectionError("the selected agent does not have a verified MCP adapter")


def _remove_command(agent: str) -> tuple[str, ...]:
    if agent == "codex":
        return ("codex", "mcp", "remove", _SERVER_NAME)
    if agent == "claude":
        return ("claude", "mcp", "remove", "--scope", "user", _SERVER_NAME)
    if agent == "grok":
        return ("grok", "mcp", "remove", "--scope", "user", _SERVER_NAME)
    raise AgentConnectionError("the selected agent does not have a verified MCP adapter")


def _invoke(argv: Sequence[str], *, runner: Runner) -> tuple[bool, str | None]:
    try:
        completed = runner(argv)
    except (OSError, subprocess.SubprocessError):
        return False, "agent-client-unavailable"
    if completed.returncode == 0:
        return True, None
    return False, "agent-client-command-failed"


def _read_state(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {"managed": {}, "additionalAgents": []}, None
    if path.is_symlink() or not path.is_file():
        return {"managed": {}, "additionalAgents": []}, "connection-state-unreadable"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        managed = value.get("managed")
        additional = value.get("additionalAgents")
        if (
            value.get("schemaVersion") != _STATE_SCHEMA
            or not isinstance(managed, dict)
            or not isinstance(additional, list)
        ):
            raise ValueError("unexpected state")
        return {"managed": managed, "additionalAgents": additional}, None
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return {"managed": {}, "additionalAgents": []}, "connection-state-unreadable"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    parent = path.parent
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        try:
            Path(temporary).unlink(missing_ok=True)
        except OSError:
            pass


def _record(agent: str, descriptor: dict[str, Any]) -> dict[str, Any]:
    return {"agent": agent, "server": _SERVER_NAME, "descriptor": descriptor}


def _previous_descriptor(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    descriptor = value.get("descriptor")
    if not isinstance(descriptor, dict):
        return None
    command = descriptor.get("command")
    arguments = descriptor.get("args")
    if (
        not isinstance(command, str)
        or not isinstance(arguments, list)
        or not all(isinstance(item, str) for item in arguments)
    ):
        return None
    return {"command": command, "args": arguments}


def _connect_one(
    agent: str,
    *,
    descriptor: dict[str, Any],
    previous: object,
    home: Path,
    runner: Runner,
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    if agent not in _SUPPORTED_MCP_AGENTS:
        return None, {"agent": agent, "status": "skipped", "reason": "mcp-configuration-not-yet-supported"}
    state, current, reason = _current(agent, home=home, runner=runner)
    previous_descriptor = _previous_descriptor(previous)
    if state == "unknown":
        return previous if isinstance(previous, dict) else None, {
            "agent": agent,
            "status": "skipped",
            "reason": reason or "agent-configuration-unavailable",
        }
    if state == "present":
        if current == descriptor and previous_descriptor == descriptor:
            return previous if isinstance(previous, dict) else _record(agent, descriptor), {
                "agent": agent,
                "status": "connected",
                "reason": "already-configured",
            }
        return previous if isinstance(previous, dict) else None, {
            "agent": agent,
            "status": "skipped",
            "reason": "plugin-entry-modified" if previous_descriptor is not None else "existing-unmanaged-entry",
        }
    # The entry is absent. A prior record means the user or their agent removed
    # our exact entry; an explicit reconcile is permitted to repair it.
    if agent == "agy":
        added, failure = _agy_add(home=home, descriptor=descriptor)
    else:
        added, failure = _invoke(_add_command(agent, descriptor), runner=runner)
    if not added:
        return previous if isinstance(previous, dict) else None, {
            "agent": agent,
            "status": "failed",
            "reason": failure or "agent-client-command-failed",
        }
    state, current, reason = _current(agent, home=home, runner=runner)
    if state == "present" and current == descriptor:
        return _record(agent, descriptor), {"agent": agent, "status": "connected", "reason": "configured"}
    return previous if isinstance(previous, dict) else None, {
        "agent": agent,
        "status": "failed",
        "reason": reason or "configuration-verification-failed",
    }


def _disconnect_one(
    agent: str,
    *,
    previous: object,
    home: Path,
    runner: Runner,
) -> tuple[bool, dict[str, str]]:
    descriptor = _previous_descriptor(previous)
    if descriptor is None:
        return True, {"agent": agent, "status": "skipped", "reason": "connection-state-unreadable"}
    state, current, reason = _current(agent, home=home, runner=runner)
    if state == "absent":
        return True, {"agent": agent, "status": "disconnected", "reason": "already-absent"}
    if state != "present" or current != descriptor:
        return False, {"agent": agent, "status": "skipped", "reason": reason or "plugin-entry-modified"}
    if agent == "agy":
        removed, failure = _agy_remove(home=home, descriptor=descriptor)
    else:
        removed, failure = _invoke(_remove_command(agent), runner=runner)
    if not removed:
        return False, {"agent": agent, "status": "failed", "reason": failure or "agent-client-command-failed"}
    state, _current_value, reason = _current(agent, home=home, runner=runner)
    if state == "absent":
        return True, {"agent": agent, "status": "disconnected", "reason": "removed"}
    return False, {"agent": agent, "status": "failed", "reason": reason or "configuration-verification-failed"}


def _report(
    *,
    action: str,
    default_agent: str | None,
    additional_agents: list[str],
    results: list[dict[str, str]],
    report_path: Path,
) -> dict[str, Any]:
    return {
        "schemaVersion": _REPORT_SCHEMA,
        "action": action,
        "defaultAgent": default_agent,
        "additionalAgents": additional_agents,
        "generatedAt": _utc_now(),
        "reportPath": str(report_path),
        "results": results,
    }


def agent_connection_status(
    state_dir: Path,
    *,
    config_home: Path | None = None,
    home: Path | None = None,
    runner: Runner = _default_runner,
) -> dict[str, Any]:
    """Return a read-only view of host-default and plugin-owned connections."""

    configured_directory = Path(state_dir)
    if not configured_directory.is_absolute() or configured_directory.is_symlink():
        raise AgentConnectionError("agent state directory must be an absolute, non-symlink directory")
    directory = (
        _require_directory(configured_directory, label="agent state directory", create=False)
        if configured_directory.exists()
        else configured_directory
    )
    state_path = directory / "connection-state.json"
    state, state_error = _read_state(state_path)
    resolved_home = Path(home) if home is not None else Path.home()
    default_agent, default_reason = _default_agent(Path(config_home) if config_home is not None else _config_home())
    additional, ignored = _normalize_additional(state["additionalAgents"], default_agent)
    requested = [agent for agent in [default_agent, *additional] if agent is not None]
    results = list(ignored)
    for agent in requested:
        previous = state["managed"].get(agent)
        if agent not in _SUPPORTED_MCP_AGENTS:
            results.append({"agent": agent, "status": "available", "reason": "mcp-configuration-not-yet-supported"})
            continue
        current_state, current, reason = _current(agent, home=resolved_home, runner=runner)
        previous_descriptor = _previous_descriptor(previous)
        if current_state == "present" and current == previous_descriptor and previous_descriptor is not None:
            results.append({"agent": agent, "status": "connected", "reason": "configured"})
        elif current_state == "absent":
            results.append({"agent": agent, "status": "not-connected", "reason": "entry-absent"})
        else:
            results.append({"agent": agent, "status": "attention", "reason": reason or "plugin-entry-modified"})
    return {
        "schemaVersion": _STATUS_SCHEMA,
        "defaultAgent": default_agent,
        "defaultAgentReason": default_reason,
        "additionalAgents": additional,
        "availableAgents": [
            {
                "id": identifier,
                "label": label,
                "mcpSetup": "supported" if identifier in _SUPPORTED_MCP_AGENTS else "not-yet-supported",
            }
            for identifier, label in _AGENTS.items()
        ],
        "connections": results,
        "reportPath": str(directory / "connection-report.json"),
        "stateReason": state_error,
    }


def reconcile_agent_connections(
    state_dir: Path,
    *,
    runtime_cli: Path,
    catalog: Path,
    additional_agents: Iterable[str] = (),
    config_home: Path | None = None,
    home: Path | None = None,
    runner: Runner = _default_runner,
) -> dict[str, Any]:
    """Connect Omarchy's default agent and chosen additional agents independently."""

    directory = _require_directory(Path(state_dir), label="agent state directory", create=True)
    executable = _require_regular_file(Path(runtime_cli), label="runtime CLI")
    source_catalog = _require_directory(Path(catalog), label="local catalog", create=False)
    resolved_home = Path(home) if home is not None else Path.home()
    default_agent, default_reason = _default_agent(Path(config_home) if config_home is not None else _config_home())
    additional, results = _normalize_additional(additional_agents, default_agent)
    report_path = directory / "connection-report.json"
    state_path = directory / "connection-state.json"
    state, state_error = _read_state(state_path)
    if state_error is not None:
        results.append({"agent": "state", "status": "attention", "reason": state_error})
    if default_agent is None:
        results.append({"agent": "default", "status": "skipped", "reason": default_reason or "default-agent-not-set"})
    targets = [agent for agent in [default_agent, *additional] if agent is not None]
    descriptor = _descriptor(executable, source_catalog)
    managed: dict[str, Any] = dict(state["managed"])
    for agent in targets:
        record, result = _connect_one(
            agent,
            descriptor=descriptor,
            previous=managed.get(agent),
            home=resolved_home,
            runner=runner,
        )
        results.append(result)
        if record is not None:
            managed[agent] = record
    for agent in sorted(set(managed) - set(targets)):
        removed, result = _disconnect_one(agent, previous=managed[agent], home=resolved_home, runner=runner)
        results.append(result)
        if removed:
            managed.pop(agent, None)
    next_state = {
        "schemaVersion": _STATE_SCHEMA,
        "updatedAt": _utc_now(),
        "managed": managed,
        "additionalAgents": additional,
    }
    _write_json(state_path, next_state)
    report = _report(
        action="reconcile",
        default_agent=default_agent,
        additional_agents=additional,
        results=results,
        report_path=report_path,
    )
    _write_json(report_path, report)
    return report


def disconnect_agent_connections(
    state_dir: Path,
    *,
    home: Path | None = None,
    runner: Runner = _default_runner,
) -> dict[str, Any]:
    """Remove only exact MCP entries previously recorded as plugin-owned."""

    directory = _require_directory(Path(state_dir), label="agent state directory", create=True)
    resolved_home = Path(home) if home is not None else Path.home()
    state_path = directory / "connection-state.json"
    report_path = directory / "connection-report.json"
    state, state_error = _read_state(state_path)
    results: list[dict[str, str]] = []
    if state_error is not None:
        results.append({"agent": "state", "status": "attention", "reason": state_error})
    managed = dict(state["managed"])
    for agent in sorted(managed):
        removed, result = _disconnect_one(agent, previous=managed[agent], home=resolved_home, runner=runner)
        results.append(result)
        if removed:
            managed.pop(agent, None)
    next_state = {
        "schemaVersion": _STATE_SCHEMA,
        "updatedAt": _utc_now(),
        "managed": managed,
        "additionalAgents": [],
    }
    _write_json(state_path, next_state)
    report = _report(
        action="disconnect",
        default_agent=None,
        additional_agents=[],
        results=results,
        report_path=report_path,
    )
    _write_json(report_path, report)
    return report
