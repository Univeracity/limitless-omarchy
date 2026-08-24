"""Low-tax, local registration of reusable source-free methods.

Agents submit only the method material they already produced.  Limitless adds
IDs, digests, local catalog projection, lineage, and sharing intent.  The tool
does not scan a workspace and registration remains useful when the managed
service is unavailable.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import secrets
import shutil
import stat
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from limitless_library.catalog import CatalogError, seal_capsule
from limitless_library.contracts import canonical_json_bytes, sha256_json

from .contributions import ContributionError, contribution_states, initialize_contribution
from .settings import CONTRIBUTION_MODES, DESTINATIONS, MATERIAL_POLICIES, SettingsError, load_settings

DRAFT_SCHEMA_VERSION = "limitless.local-method-draft/0.1"
DRAFT_RESULT_SCHEMA_VERSION = "limitless.method-registration-result/0.1"
DRAFT_LIST_SCHEMA_VERSION = "limitless.omarchy-draft-list/0.1"
MAX_DRAFT_BYTES = 64 * 1024
MAX_DRAFTS = 2_000
_DRAFT_REF = re.compile(r"^draft:([0-9A-HJKMNP-TV-Z]{26})$")
_LINEAGE_REF = re.compile(r"^lineage:[0-9A-HJKMNP-TV-Z]{26}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_TASK_KIND = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class DraftError(ValueError):
    """A local method candidate is unsafe or malformed."""


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ulid() -> str:
    value = ((time.time_ns() // 1_000_000) & ((1 << 48) - 1)) << 80
    value |= int.from_bytes(secrets.token_bytes(10), "big")
    encoded = ["0"] * 26
    for index in range(25, -1, -1):
        encoded[index] = _CROCKFORD[value & 31]
        value >>= 5
    return "".join(encoded)


def _directory(path: Path, label: str, *, create: bool = True) -> Path:
    selected = Path(path)
    if not selected.is_absolute() or ".." in selected.parts or selected.is_symlink():
        raise DraftError(f"{label} must be an absolute, normalized, non-symlink directory")
    if create:
        selected.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not selected.is_dir() or selected.is_symlink():
        raise DraftError(f"{label} is unavailable")
    return selected


def _text(value: Any, label: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise DraftError(f"{label} must be text")
    selected = " ".join(value.split())
    if not selected or len(selected) > maximum or "\x00" in selected:
        raise DraftError(f"{label} is empty or too long")
    return selected


def _text_list(value: Any, label: str, *, maximum_items: int, maximum_text: int) -> list[str]:
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or not 1 <= len(values) <= maximum_items:
        raise DraftError(f"{label} must contain between 1 and {maximum_items} items")
    selected = [_text(item, label, maximum=maximum_text) for item in values]
    if len(set(selected)) != len(selected):
        raise DraftError(f"{label} must not contain duplicates")
    return selected


def _optional_text_list(value: Any, label: str, *, maximum_items: int, maximum_text: int) -> list[str]:
    if value is None:
        return []
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or len(values) > maximum_items:
        raise DraftError(f"{label} contains too many items")
    selected = [_text(item, label, maximum=maximum_text) for item in values]
    if len(set(selected)) != len(selected):
        raise DraftError(f"{label} must not contain duplicates")
    return selected


def _slug(value: str) -> str:
    selected = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return selected[:60].rstrip("-") or "method"


def _record_path(registry: Path, draft_ref: str) -> Path:
    match = _DRAFT_REF.fullmatch(draft_ref)
    if match is None:
        raise DraftError("draft reference is invalid")
    return registry / "records" / f"{match.group(1)}.json"


def load_draft(registry_path: Path, draft_ref: str) -> dict[str, Any]:
    """Load one immutable method record by its opaque reference."""

    registry = _directory(registry_path, "draft registry")
    path = _record_path(registry, draft_ref)
    if not path.exists() or path.is_symlink():
        raise DraftError("draft record is unavailable")
    record = _read_record(path)
    if record.get("draftRef") != draft_ref:
        raise DraftError("draft record is misbound")
    return record


def _read_record(path: Path) -> dict[str, Any]:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or not 1 <= before.st_size <= MAX_DRAFT_BYTES:
        raise DraftError("draft record is not a bounded regular file")
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0))
    try:
        current = os.fstat(descriptor)
        if current.st_dev != before.st_dev or current.st_ino != before.st_ino or current.st_size != before.st_size:
            raise DraftError("draft record changed while being read")
        raw = os.read(descriptor, MAX_DRAFT_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(raw) != before.st_size or len(raw) > MAX_DRAFT_BYTES:
        raise DraftError("draft record changed or is oversized")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DraftError("draft record is invalid JSON") from error
    return _validate_record(value)


def _validate_record(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion",
        "draftRef",
        "lineageId",
        "revision",
        "supersedes",
        "title",
        "taskKind",
        "method",
        "sourceReferences",
        "requestedDestination",
        "contributionMode",
        "materialPolicy",
        "publicPolicyDigest",
        "contentDigest",
        "createdAt",
    }
    if not isinstance(value, dict) or set(value) != fields or value.get("schemaVersion") != DRAFT_SCHEMA_VERSION:
        raise DraftError("draft record has an unsupported shape")
    draft_ref = value.get("draftRef")
    if not isinstance(draft_ref, str) or _DRAFT_REF.fullmatch(draft_ref) is None:
        raise DraftError("draft record reference is invalid")
    if not isinstance(value.get("lineageId"), str) or _LINEAGE_REF.fullmatch(value["lineageId"]) is None:
        raise DraftError("draft record lineage is invalid")
    revision = value.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or not 1 <= revision <= 1_000_000:
        raise DraftError("draft record revision is invalid")
    supersedes = value.get("supersedes")
    if supersedes is not None and (not isinstance(supersedes, str) or _DRAFT_REF.fullmatch(supersedes) is None):
        raise DraftError("draft record supersession is invalid")
    if supersedes == draft_ref or (revision == 1) != (supersedes is None):
        raise DraftError("draft record revision lineage is inconsistent")
    title = _text(value.get("title"), "draft record title", maximum=160)
    task_kind = value.get("taskKind")
    if not isinstance(task_kind, str) or len(task_kind) > 100 or _TASK_KIND.fullmatch(task_kind) is None:
        raise DraftError("draft record task kind is invalid")
    method = value.get("method")
    if not isinstance(method, dict) or set(method) != {"summary", "steps", "verification"}:
        raise DraftError("draft record method has an unsupported shape")
    summary = _text(method.get("summary"), "draft record summary", maximum=1000)
    steps = _text_list(method.get("steps"), "draft record steps", maximum_items=20, maximum_text=1200)
    verification = _text_list(
        method.get("verification"), "draft record verification", maximum_items=12, maximum_text=1200
    )
    sources = _optional_text_list(
        value.get("sourceReferences"), "draft record source references", maximum_items=8, maximum_text=512
    )
    if value.get("requestedDestination") not in DESTINATIONS:
        raise DraftError("draft record destination is invalid")
    if value.get("contributionMode") not in CONTRIBUTION_MODES:
        raise DraftError("draft record contribution mode is invalid")
    if value.get("materialPolicy") not in MATERIAL_POLICIES:
        raise DraftError("draft record material policy is invalid")
    policy_digest = value.get("publicPolicyDigest")
    if policy_digest is not None and (not isinstance(policy_digest, str) or _DIGEST.fullmatch(policy_digest) is None):
        raise DraftError("draft record publication policy digest is invalid")
    if (value["requestedDestination"] == "public") != (policy_digest is not None):
        raise DraftError("draft record publication authorization is inconsistent")
    content = {
        "title": title,
        "taskKind": task_kind,
        "method": {"summary": summary, "steps": steps, "verification": verification},
        "sourceReferences": sources,
    }
    if value.get("contentDigest") != sha256_json(content):
        raise DraftError("draft record content digest is invalid")
    created_at = value.get("createdAt")
    if not isinstance(created_at, str) or _TIMESTAMP.fullmatch(created_at) is None:
        raise DraftError("draft record timestamp is invalid")
    return dict(value)


def _write_new(path: Path, value: dict[str, Any]) -> None:
    payload = canonical_json_bytes(value) + b"\n"
    if len(payload) > MAX_DRAFT_BYTES:
        raise DraftError("draft record is too large")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _records(registry: Path) -> list[dict[str, Any]]:
    root = registry / "records"
    if not root.exists():
        return []
    paths = sorted(root.glob("*.json"), reverse=True)
    if len(paths) > MAX_DRAFTS:
        raise DraftError("local draft registry exceeds its supported bound")
    records: list[dict[str, Any]] = []
    references: set[str] = set()
    for path in paths:
        if path.is_symlink():
            raise DraftError("draft registry contains a symbolic link")
        record = _read_record(path)
        match = _DRAFT_REF.fullmatch(str(record["draftRef"]))
        if match is None or path.name != match.group(1) + ".json" or record["draftRef"] in references:
            raise DraftError("draft registry contains a misbound record")
        references.add(record["draftRef"])
        records.append(record)
    return records


def _active_refs(records: list[dict[str, Any]]) -> set[str]:
    superseded = {str(item["supersedes"]) for item in records if item.get("supersedes") is not None}
    return {str(item["draftRef"]) for item in records if str(item["draftRef"]) not in superseded}


def _capsule(record: dict[str, Any]) -> dict[str, Any]:
    draft_ref = str(record["draftRef"])
    suffix = draft_ref.split(":", 1)[1].lower()
    task_kind = str(record["taskKind"])
    compatibility = (
        {"constraints": ["linux", "omarchy", "omarchy-plugin-schema-v1"], "toolchain": {"omarchyPluginSchema": ["1"]}}
        if task_kind == "omarchy-customization"
        else {"constraints": [], "toolchain": {}}
    )
    draft = {
        "schemaVersion": "limitless.capsule/0.1",
        "id": f"capsule:local.{_slug(str(record['title']))}.{suffix[:10]}",
        "version": f"0.1.{int(record['revision']) - 1}",
        "title": str(record["title"]),
        "license": "LicenseRef-Limitless-Source-Free-Method",
        "offers": [
            {
                "id": f"offer:local.{suffix.lower()}",
                "kind": "method",
                "priority": 500,
                "taskKind": task_kind,
                "compatibility": compatibility,
                "policy": {"allowedUses": ["adopt", "instantiate"], "tenantScopes": ["private"], "state": "active"},
                "files": None,
                "method": {
                    "summary": record["method"]["summary"],
                    "steps": record["method"]["steps"],
                    "verification": record["method"]["verification"],
                },
            }
        ],
    }
    try:
        return seal_capsule(draft, Path("."))
    except CatalogError as error:
        raise DraftError("registered method could not be projected into the local catalog") from error


def _project_catalog(catalog: Path, record: dict[str, Any]) -> None:
    suffix = str(record["draftRef"]).split(":", 1)[1]
    target = catalog / f"local-{suffix}"
    stage = catalog / f".local-{suffix}.{secrets.token_hex(6)}.tmp"
    stage.mkdir(mode=0o700)
    try:
        _write_new(stage / "capsule.json", _capsule(record))
        os.replace(stage, target)
    finally:
        if stage.exists() and not stage.is_symlink():
            shutil.rmtree(stage)


def _retire_projection(catalog: Path, draft_ref: str) -> None:
    match = _DRAFT_REF.fullmatch(draft_ref)
    if match is None:
        raise DraftError("superseded draft reference is invalid")
    target = catalog / f"local-{match.group(1)}"
    if not target.exists():
        return
    if target.is_symlink() or not target.is_dir() or target.parent != catalog:
        raise DraftError("superseded local projection is unsafe")
    shutil.rmtree(target)


def register_method(
    registry_path: Path,
    catalog_path: Path,
    settings_path: Path,
    value: Any,
) -> dict[str, Any]:
    """Register one method with an idempotent, compact agent-facing result."""

    if not isinstance(value, dict):
        raise DraftError("method registration arguments must be an object")
    permitted = {"name", "summary", "steps", "verify", "sources", "taskKind", "supersedes"}
    if not set(value).issubset(permitted):
        raise DraftError("method registration contains an unsupported field")
    name = _text(value.get("name"), "method name", maximum=160)
    summary = _text(value.get("summary", name), "method summary", maximum=1000)
    steps = _text_list(value.get("steps"), "method steps", maximum_items=20, maximum_text=1200)
    verification = _optional_text_list(
        value.get("verify"), "method verification", maximum_items=12, maximum_text=1200
    ) or ["Confirm receiver-owned checks for the resulting change pass."]
    sources = _optional_text_list(value.get("sources"), "source references", maximum_items=8, maximum_text=512)
    task_kind = value.get("taskKind", "omarchy-customization")
    if not isinstance(task_kind, str) or _TASK_KIND.fullmatch(task_kind) is None or len(task_kind) > 100:
        raise DraftError("method taskKind is invalid")
    supersedes = value.get("supersedes")
    if supersedes is not None and (not isinstance(supersedes, str) or _DRAFT_REF.fullmatch(supersedes) is None):
        raise DraftError("supersedes must be a valid draft reference")

    try:
        settings = load_settings(settings_path)
    except SettingsError as error:
        raise DraftError("owner settings are unavailable") from error
    destination = str(settings["defaultDestination"])
    if destination == "off":
        return {
            "schemaVersion": DRAFT_RESULT_SCHEMA_VERSION,
            "status": "disabled",
            "draftRef": None,
            "destination": "off",
        }

    registry = _directory(registry_path, "draft registry")
    records_dir = _directory(registry / "records", "draft record directory")
    catalog = _directory(catalog_path, "local catalog")
    lock_path = registry / ".lock"
    lock = os.open(
        lock_path,
        os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = _records(registry)
        prior: dict[str, Any] | None = None
        if supersedes is not None:
            prior = next((item for item in records if item.get("draftRef") == supersedes), None)
            if prior is None or supersedes not in _active_refs(records):
                raise DraftError("superseded draft is unavailable or no longer current")
        content = {
            "title": name,
            "taskKind": task_kind,
            "method": {"summary": summary, "steps": steps, "verification": verification},
            "sourceReferences": sources,
        }
        content_digest = sha256_json(content)
        active = _active_refs(records)
        duplicate = next(
            (
                item
                for item in records
                if item.get("contentDigest") == content_digest and item.get("draftRef") in active
            ),
            None,
        )
        if duplicate is not None:
            try:
                initialize_contribution(registry, duplicate)
            except ContributionError as error:
                raise DraftError("duplicate method sharing state is unavailable") from error
            return {
                "schemaVersion": DRAFT_RESULT_SCHEMA_VERSION,
                "status": "duplicate",
                "draftRef": duplicate["draftRef"],
                "destination": duplicate["requestedDestination"],
            }
        identifier = _ulid()
        draft_ref = "draft:" + identifier
        now = _utc_now()
        record = {
            "schemaVersion": DRAFT_SCHEMA_VERSION,
            "draftRef": draft_ref,
            "lineageId": prior["lineageId"] if prior is not None else "lineage:" + identifier,
            "revision": int(prior["revision"]) + 1 if prior is not None else 1,
            "supersedes": supersedes,
            "title": name,
            "taskKind": task_kind,
            "method": content["method"],
            "sourceReferences": sources,
            "requestedDestination": destination,
            "contributionMode": settings["contributionMode"],
            "materialPolicy": settings["materialPolicy"],
            "publicPolicyDigest": settings["publicPolicyDigest"],
            "contentDigest": content_digest,
            "createdAt": now,
        }
        _validate_record(record)
        record_path = records_dir / f"{identifier}.json"
        _write_new(record_path, record)
        try:
            _project_catalog(catalog, record)
            initialize_contribution(registry, record)
        except (ContributionError, DraftError, OSError) as error:
            _retire_projection(catalog, draft_ref)
            record_path.unlink(missing_ok=True)
            if isinstance(error, ContributionError):
                raise DraftError("method sharing state could not be initialized") from error
            raise
        if supersedes is not None:
            _retire_projection(catalog, supersedes)
        return {
            "schemaVersion": DRAFT_RESULT_SCHEMA_VERSION,
            "status": "registered",
            "draftRef": draft_ref,
            "destination": destination,
        }
    except OSError as error:
        raise DraftError("method could not be registered safely") from error
    finally:
        os.close(lock)


def list_drafts(registry_path: Path, *, limit: int = 12) -> dict[str, Any]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise DraftError("draft list limit is invalid")
    registry = _directory(registry_path, "draft registry")
    records = _records(registry)
    active = _active_refs(records)
    try:
        states = contribution_states(registry)
        for item in records:
            if item["draftRef"] not in states:
                states[item["draftRef"]] = initialize_contribution(registry, item)
    except ContributionError as error:
        raise DraftError("method sharing state is unavailable") from error
    items = [
        {
            "draftRef": item["draftRef"],
            "title": item["title"],
            "revision": item["revision"],
            "destination": states[item["draftRef"]]["destination"],
            "status": states[item["draftRef"]]["state"] if item["draftRef"] in active else "superseded",
            "createdAt": item["createdAt"],
        }
        for item in records[:limit]
    ]
    return {
        "schemaVersion": DRAFT_LIST_SCHEMA_VERSION,
        "total": len(records),
        "pending": sum(1 for item in records if item["draftRef"] in active),
        "items": items,
    }
