"""Owner-controlled, local-first settings for the Omarchy integration.

The verified service profile describes what the service is allowed to do.  This
file describes what this owner wants the plugin and its connected agents to do.
Keeping those documents separate prevents a UI preference from becoming a
trust assertion.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import secrets
import stat
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "limitless.omarchy-owner-settings/0.1"
MAX_SETTINGS_BYTES = 16 * 1024
DESTINATIONS = frozenset({"off", "local", "circle", "organization", "public"})
CONTRIBUTION_MODES = frozenset({"manual", "agent-mediated", "automatic"})
MATERIAL_POLICIES = frozenset({"methods-only", "methods-and-exact"})
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class SettingsError(ValueError):
    """Owner settings are malformed or cannot be stored safely."""


def default_settings() -> dict[str, Any]:
    """Return conservative defaults that still let useful local work accrue."""

    return {
        "schemaVersion": SCHEMA_VERSION,
        "defaultDestination": "local",
        "contributionMode": "agent-mediated",
        "materialPolicy": "methods-only",
        "publicPolicyDigest": None,
    }


def validate_settings(value: Any) -> dict[str, Any]:
    expected = set(default_settings())
    if not isinstance(value, dict) or set(value) != expected or value.get("schemaVersion") != SCHEMA_VERSION:
        raise SettingsError("owner settings have an unsupported shape")
    destination = value.get("defaultDestination")
    mode = value.get("contributionMode")
    material = value.get("materialPolicy")
    policy_digest = value.get("publicPolicyDigest")
    if destination not in DESTINATIONS:
        raise SettingsError("default contribution destination is invalid")
    if mode not in CONTRIBUTION_MODES:
        raise SettingsError("contribution mode is invalid")
    if material not in MATERIAL_POLICIES:
        raise SettingsError("reusable material policy is invalid")
    if policy_digest is not None and (not isinstance(policy_digest, str) or _DIGEST.fullmatch(policy_digest) is None):
        raise SettingsError("public policy digest is invalid")
    if destination == "public":
        if policy_digest is None:
            raise SettingsError("public sharing requires a verified policy authorization")
    elif policy_digest is not None:
        raise SettingsError("public policy authorization is only valid for public sharing")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "defaultDestination": destination,
        "contributionMode": mode,
        "materialPolicy": material,
        "publicPolicyDigest": policy_digest,
    }


def _require_path(path: Path) -> Path:
    selected = Path(path)
    if not selected.is_absolute() or ".." in selected.parts or selected.is_symlink():
        raise SettingsError("settings path must be absolute, normalized, and not a symbolic link")
    return selected


def _read_bounded(path: Path) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SETTINGS_BYTES:
        raise SettingsError("settings file is not a bounded regular file")
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        current = os.fstat(descriptor)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_dev != before.st_dev
            or current.st_ino != before.st_ino
            or current.st_size != before.st_size
        ):
            raise SettingsError("settings file changed while being read")
        payload = bytearray()
        while len(payload) <= MAX_SETTINGS_BYTES:
            chunk = os.read(descriptor, MAX_SETTINGS_BYTES + 1 - len(payload))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) != current.st_size or len(payload) > MAX_SETTINGS_BYTES:
            raise SettingsError("settings file changed or is oversized")
        return bytes(payload)
    finally:
        os.close(descriptor)


def load_settings(path: Path) -> dict[str, Any]:
    """Load saved settings, returning safe defaults before the first save."""

    selected = _require_path(path)
    if not selected.exists():
        return default_settings()
    try:
        raw = _read_bounded(selected)
        return validate_settings(json.loads(raw.decode("utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SettingsError("owner settings are unavailable or invalid") from error


def save_settings(path: Path, value: Any) -> dict[str, Any]:
    """Validate and atomically replace one owner settings document."""

    selected = _require_path(path)
    checked = validate_settings(value)
    try:
        selected.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if selected.parent.is_symlink() or not selected.parent.is_dir():
            raise SettingsError("settings parent must be a real directory")
        lock_path = selected.with_name(selected.name + ".lock")
        lock = os.open(
            lock_path,
            os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            if not stat.S_ISREG(os.fstat(lock).st_mode):
                raise SettingsError("settings lock is not a regular file")
            fcntl.flock(lock, fcntl.LOCK_EX)
            payload = (json.dumps(checked, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
            temporary = selected.parent / f".{selected.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp"
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                os.write(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            try:
                os.replace(temporary, selected)
                os.chmod(selected, 0o600, follow_symlinks=False)
                directory = os.open(selected.parent, os.O_RDONLY | os.O_CLOEXEC)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                temporary.unlink(missing_ok=True)
        finally:
            os.close(lock)
        return checked
    except SettingsError:
        raise
    except OSError as error:
        raise SettingsError("owner settings could not be saved safely") from error


def settings_result(settings: dict[str, Any], *, saved: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "limitless.omarchy-settings-result/0.1",
        "saved": saved,
        "settings": validate_settings(settings),
    }
