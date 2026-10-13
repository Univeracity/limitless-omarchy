"""Thin Omarchy host configuration for the shared Library objective kernel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from limitless_library.catalog import LocalCatalog
from limitless_library.catalog_snapshot import CatalogSnapshot
from limitless_library.method_capture import CapturedMethodCatalog, default_method_store
from limitless_library.objective_query import ObjectiveQueryEngine
from limitless_library.query_policy import load_query_policy, resolve_receivers, save_query_policy

from .adapter import Runner, _default_runner, discover_profile


def owner_query_policy_path(settings_path: Path | None) -> Path:
    root = settings_path.parent if settings_path is not None else default_method_store().parent
    return root / "query-policy.json"


def query_policy_result(settings_path: Path, *, execution_mode: str | None = None) -> dict[str, Any]:
    """Change only query consent; retain the existing settings and receiver facts."""
    path = owner_query_policy_path(settings_path)
    policy = load_query_policy(path)
    if execution_mode is not None:
        policy = {**policy, "executionMode": execution_mode}
        save_query_policy(path, policy)
    return {
        "schemaVersion": "limitless.omarchy-query-policy-result/1.0",
        "saved": execution_mode is not None,
        "executionMode": policy["executionMode"],
        "allowExact": policy["allowExact"],
    }


def objective_engine(
    catalog: Path,
    *,
    settings_path: Path | None,
    drafts_path: Path | None,
    query_policy_path: Path | None = None,
    query_state: Path | None = None,
    method_store: Path | None = None,
    omarchy_release: str | None = None,
    runner: Runner = _default_runner,
) -> ObjectiveQueryEngine:
    policy_path = query_policy_path or owner_query_policy_path(settings_path)
    data_root = drafts_path.parent if drafts_path is not None else policy_path.parent
    source = CatalogSnapshot(catalog, lock_path=drafts_path / ".lock" if drafts_path is not None else None)

    def receivers(policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        local, service = resolve_receivers(policy)
        if policy["localReceiver"] is None and policy["serviceReceiver"] is None:
            # This native entry point targets the local desktop. An explicit
            # remote receiver always takes precedence over native host facts.
            profile = discover_profile(omarchy_release=omarchy_release, runner=runner)
            local = {"constraints": profile["constraints"], "toolchain": profile["toolchain"]}
        return local, service

    return ObjectiveQueryEngine(
        CapturedMethodCatalog(
            LocalCatalog.empty(catalog), method_store or default_method_store(), catalog_source=source.snapshot
        ),
        policy_path=policy_path,
        state_dir=query_state or data_root / "queries",
        receiver_resolver=receivers,
    )
