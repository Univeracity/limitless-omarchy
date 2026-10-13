"""Omarchy policy and presentation over the shared immutable draft kernel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from limitless_library.method_drafts import (
    DRAFT_RESULT_SCHEMA_VERSION,
    DRAFT_SCHEMA_VERSION,
    MAX_DRAFT_BYTES,
    MAX_DRAFTS,
    DraftError,
    _active_refs,
    _directory,
    _records,
    draft_capsule,
    load_draft,
    register_draft,
)

from .contributions import ContributionError, contribution_states, initialize_contribution
from .settings import SettingsError, load_settings

DRAFT_LIST_SCHEMA_VERSION = "limitless.omarchy-draft-list/0.1"
__all__ = [
    "DRAFT_RESULT_SCHEMA_VERSION",
    "DRAFT_SCHEMA_VERSION",
    "MAX_DRAFTS",
    "MAX_DRAFT_BYTES",
    "DraftError",
    "list_drafts",
    "load_draft",
    "register_method",
]


def _capsule(record: dict[str, Any]) -> dict[str, Any]:
    compatibility = (
        {"constraints": ["linux", "omarchy", "omarchy-plugin-schema-v1"], "toolchain": {"omarchyPluginSchema": ["1"]}}
        if record["taskKind"] == "omarchy-customization"
        else {"constraints": [], "toolchain": {}}
    )
    return draft_capsule(record, compatibility=compatibility)


def register_method(registry_path: Path, catalog_path: Path, settings_path: Path, value: Any) -> dict[str, Any]:
    try:
        settings = load_settings(settings_path)
    except SettingsError as error:
        raise DraftError("owner settings are unavailable") from error
    policy = {
        key: settings[key] for key in ("defaultDestination", "contributionMode", "materialPolicy", "publicPolicyDigest")
    }
    return register_draft(
        registry_path,
        catalog_path,
        value,
        policy=policy,
        default_task_kind="omarchy-customization",
        projector=_capsule,
        initialize=initialize_contribution,
    )


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
