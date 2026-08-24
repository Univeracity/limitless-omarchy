"""Private aggregate activity counters for the Omarchy panel.

The activity file is presentation state, not lifecycle evidence. It deliberately
stores no objectives, prompts, paths, identifiers, capsule metadata, or result
content. Failure to update it must never break the operation being counted.
"""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import stat
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "limitless.omarchy-activity/0.1"
SUMMARY_SCHEMA_VERSION = "limitless.omarchy-stats/0.1"
MAX_ACTIVITY_BYTES = 32 * 1024


class ActivityError(ValueError):
    """The local aggregate activity state is unavailable or invalid."""


def _empty() -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "queries": {
            "total": 0,
            "local": 0,
            "service": 0,
            "general": 0,
            "exactComponents": 0,
            "sourceFreeMethods": 0,
            "abstentions": 0,
        },
        "lifecycle": {
            "drafts": 0,
            "reviews": 0,
            "installs": 0,
            "adoptions": 0,
            "publications": 0,
            "withdrawals": 0,
        },
        "agents": {"connected": 0, "attention": 0},
        "serviceConnected": False,
        "updatedAt": None,
    }


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validated(value: Any) -> dict[str, Any]:
    expected = _empty()
    if (
        isinstance(value, dict)
        and value.get("schemaVersion") == SCHEMA_VERSION
        and isinstance(value.get("lifecycle"), dict)
        and "drafts" not in value["lifecycle"]
        and set(value["lifecycle"]) == set(expected["lifecycle"]) - {"drafts"}
    ):
        value = {**value, "lifecycle": {"drafts": 0, **value["lifecycle"]}}
    if not isinstance(value, dict) or set(value) != set(expected) or value.get("schemaVersion") != SCHEMA_VERSION:
        raise ActivityError("activity state has an unsupported shape")
    for section in ("queries", "lifecycle", "agents"):
        candidate = value.get(section)
        if not isinstance(candidate, dict) or set(candidate) != set(expected[section]):
            raise ActivityError(f"activity {section} has an unsupported shape")
        if not all(_nonnegative_int(item) for item in candidate.values()):
            raise ActivityError(f"activity {section} contains an invalid counter")
    if not isinstance(value.get("serviceConnected"), bool):
        raise ActivityError("activity service state is invalid")
    queries = value["queries"]
    if queries["total"] != queries["local"] + queries["service"] + queries["general"] or queries["total"] != (
        queries["exactComponents"] + queries["sourceFreeMethods"] + queries["abstentions"]
    ):
        raise ActivityError("activity query counters are inconsistent")
    updated = value.get("updatedAt")
    if updated is not None and (not isinstance(updated, str) or len(updated) > 40):
        raise ActivityError("activity timestamp is invalid")
    return value


def _prepare_parent(path: Path) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise ActivityError("activity path must be absolute and normalized")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ActivityError("activity parent must be a real directory")


def _read(path: Path) -> dict[str, Any]:
    if not path.is_absolute() or ".." in path.parts:
        raise ActivityError("activity path must be absolute and normalized")
    try:
        path_metadata = path.lstat()
    except FileNotFoundError:
        return _empty()
    if not stat.S_ISREG(path_metadata.st_mode) or path_metadata.st_size > MAX_ACTIVITY_BYTES:
        raise ActivityError("activity state is not a bounded regular file")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_ACTIVITY_BYTES:
            raise ActivityError("activity state is not a bounded regular file")
        raw = b""
        while len(raw) <= MAX_ACTIVITY_BYTES:
            part = os.read(descriptor, MAX_ACTIVITY_BYTES + 1 - len(raw))
            if not part:
                break
            raw += part
    finally:
        os.close(descriptor)
    if not raw or len(raw) > MAX_ACTIVITY_BYTES:
        raise ActivityError("activity state is empty or oversized")
    try:
        return _validated(json.loads(raw.decode("utf-8")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ActivityError("activity state is invalid JSON") from error


def _write(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(_validated(value), separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    temporary = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.replace(temporary, path)
        os.chmod(path, 0o600, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def _update(path: Path | None, mutate: Callable[[dict[str, Any]], None]) -> bool:
    if path is None:
        return False
    target = Path(path)
    try:
        _prepare_parent(target)
        lock_path = target.with_name(target.name + ".lock")
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        lock = os.open(lock_path, flags, 0o600)
        try:
            lock_metadata = os.fstat(lock)
            if not stat.S_ISREG(lock_metadata.st_mode):
                raise ActivityError("activity lock is not a regular file")
            fcntl.flock(lock, fcntl.LOCK_EX)
            value = _read(target)
            mutate(value)
            value["updatedAt"] = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
            _write(target, value)
        finally:
            os.close(lock)
        return True
    except (ActivityError, OSError, ValueError):
        return False


def record_query(path: Path | None, result: dict[str, Any], *, channel: str) -> bool:
    """Count one projected query result without retaining any result material."""

    if channel not in {"local", "service", "general"}:
        return False
    disposition = str(result.get("disposition") or "")
    if not disposition:
        disposition = {
            "exact-adoption": "exact-component",
            "method-guided": "source-free-method",
            "abstain": "abstain",
        }.get(str(result.get("treatment") or ""), "")
    if disposition not in {"exact-component", "source-free-method", "abstain"}:
        return False

    def mutate(value: dict[str, Any]) -> None:
        queries = value["queries"]
        queries["total"] += 1
        queries[channel] += 1
        if disposition == "exact-component":
            queries["exactComponents"] += 1
        elif disposition == "source-free-method":
            queries["sourceFreeMethods"] += 1
        elif disposition == "abstain":
            queries["abstentions"] += 1

    return _update(path, mutate)


def record_agents(path: Path | None, result: dict[str, Any]) -> bool:
    """Project current connection counts from a status or reconciliation result."""

    connections = result.get("connections")
    if not isinstance(connections, list):
        connections = result.get("results")
    if not isinstance(connections, list):
        return False
    connected = 0
    attention = 0
    for item in connections:
        if not isinstance(item, dict):
            continue
        status_value = str(item.get("status") or "")
        if status_value == "connected":
            connected += 1
        elif status_value != "disconnected":
            attention += 1

    def mutate(value: dict[str, Any]) -> None:
        value["agents"]["connected"] = connected
        value["agents"]["attention"] = attention

    return _update(path, mutate)


def record_service(path: Path | None, *, connected: bool) -> bool:
    return _update(path, lambda value: value.__setitem__("serviceConnected", connected))


def record_lifecycle(path: Path | None, event: str) -> bool:
    keys = {
        "draft": "drafts",
        "review": "reviews",
        "install": "installs",
        "adoption": "adoptions",
        "publication": "publications",
        "withdrawal": "withdrawals",
    }
    key = keys.get(event)
    if key is None:
        return False

    def mutate(value: dict[str, Any]) -> None:
        value["lifecycle"][key] += 1

    return _update(path, mutate)


def activity_summary(path: Path) -> dict[str, Any]:
    """Return the bounded UI projection; never expose the backing file path."""

    try:
        value = _read(Path(path))
        available = True
    except (ActivityError, OSError, ValueError):
        value = _empty()
        available = False
    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "available": available,
        "privacy": "aggregate-only-local",
        "queries": value["queries"],
        "lifecycle": value["lifecycle"],
        "agents": value["agents"],
        "serviceConnected": value["serviceConnected"],
        "updatedAt": value["updatedAt"],
    }
