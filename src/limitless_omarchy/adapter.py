"""Local, fail-closed adapter primitives for the Omarchy integration."""

from __future__ import annotations

import re
import subprocess  # nosec B404
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AdapterError(ValueError):
    """The adapter cannot make a bounded, local decision."""


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]

_RELEASE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,99}$")
_TASK_KIND = "omarchy-customization"
_REQUESTED_USES = frozenset({"adopt", "instantiate"})
_TENANT_SCOPE = "private"


def _default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    # The argument vector is passed directly; shell expansion is never enabled.
    return subprocess.run(  # nosec B603
        list(argv), capture_output=True, check=False, text=True, timeout=3
    )


def _shell_available(runner: Runner) -> bool:
    try:
        completed = runner(("omarchy-shell", "shell", "ping"))
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _release(value: str | None) -> str:
    if value is None or value == "":
        return "unknown"
    if not _RELEASE.fullmatch(value):
        raise AdapterError("Omarchy release must be a short, plain release identifier")
    return value


def _local_query_inputs(task_kind: str, requested_use: str, tenant_scope: str) -> None:
    """Keep the companion focused on private Omarchy reuse.

    The generic Library supports broader callers. This integration must not
    become a permissive transport for arbitrary task descriptions or scopes.
    """

    if task_kind != _TASK_KIND:
        raise AdapterError(f"task_kind must be {_TASK_KIND!r}")
    if requested_use not in _REQUESTED_USES:
        allowed = ", ".join(sorted(_REQUESTED_USES))
        raise AdapterError(f"requested_use must be one of: {allowed}")
    if tenant_scope != _TENANT_SCOPE:
        raise AdapterError(f"tenant_scope must be {_TENANT_SCOPE!r}")


def discover_profile(*, omarchy_release: str | None = None, runner: Runner = _default_runner) -> dict[str, Any]:
    """Return the minimum receiver material relevant to a reuse decision.

    This intentionally does not read a home directory, shell configuration,
    installed plugin list, or agent history. A caller may state a release
    explicitly when it is material to compatibility.
    """

    shell_state = "available" if _shell_available(runner) else "unavailable"
    constraints = ["omarchy", "omarchy-plugin-schema-v1"]
    if sys.platform.startswith("linux"):
        constraints.append("linux")
    if shell_state == "available":
        constraints.append("omarchy-shell-ipc")
    return {
        "schemaVersion": "limitless.omarchy-profile/0.1",
        "constraints": sorted(constraints),
        "toolchain": {
            "omarchyPluginSchema": "1",
            "omarchyRelease": _release(omarchy_release),
            "omarchyShell": shell_state,
        },
    }


def build_query(
    profile: dict[str, Any],
    *,
    task_kind: str = "omarchy-customization",
    requested_use: str = "adopt",
    tenant_scope: str = "private",
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the generic Library query without carrying arbitrary task text."""

    timestamp = evaluated_at or datetime.now(tz=UTC)
    if timestamp.tzinfo is None:
        raise AdapterError("evaluated_at must include an offset")
    constraints = profile.get("constraints")
    toolchain = profile.get("toolchain")
    if not isinstance(constraints, list) or not all(isinstance(item, str) for item in constraints):
        raise AdapterError("profile constraints are invalid")
    if not isinstance(toolchain, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in toolchain.items()
    ):
        raise AdapterError("profile toolchain is invalid")
    return {
        "schemaVersion": "limitless.query/0.1",
        "taskKind": task_kind,
        "receiver": {"constraints": constraints, "toolchain": toolchain},
        "requestedUse": requested_use,
        "tenantScope": tenant_scope,
        "evaluatedAt": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }


def status(*, omarchy_release: str | None = None, runner: Runner = _default_runner) -> dict[str, Any]:
    """State the local-only posture without contacting a service."""

    return {
        "schemaVersion": "limitless.omarchy-status/0.1",
        "mode": "local-only",
        "service": {"connected": False, "reason": "service-not-configured"},
        "profile": discover_profile(omarchy_release=omarchy_release, runner=runner),
    }


def _abstention(profile: dict[str, Any], request: dict[str, Any] | None, reason: str) -> dict[str, Any]:
    return {
        "schemaVersion": "limitless.omarchy-result/0.1",
        "mode": "local-only",
        "disposition": "abstain",
        "reason": reason,
        "profile": profile,
        "request": request,
        "decision": None,
    }


def query_local_catalog(
    catalog: Path,
    *,
    omarchy_release: str | None = None,
    task_kind: str = "omarchy-customization",
    requested_use: str = "adopt",
    tenant_scope: str = "private",
    runner: Runner = _default_runner,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Query a local catalog, returning a non-disclosing abstention on failure."""

    _local_query_inputs(task_kind, requested_use, tenant_scope)
    profile = discover_profile(omarchy_release=omarchy_release, runner=runner)
    request = build_query(
        profile,
        task_kind=task_kind,
        requested_use=requested_use,
        tenant_scope=tenant_scope,
        evaluated_at=evaluated_at,
    )
    try:
        from limitless_library.catalog import CatalogError, LocalCatalog
    except ImportError:
        return _abstention(profile, request, "library-unavailable")
    try:
        decision = LocalCatalog(Path(catalog)).query(request)
    except (CatalogError, OSError, ValueError):
        return _abstention(profile, request, "catalog-unavailable-or-ineligible")
    treatment = decision["treatment"]
    disposition = {
        "exact-adoption": "exact-component",
        "method-guided": "source-free-method",
        "abstain": "abstain",
    }.get(treatment)
    if disposition is None:
        return _abstention(profile, request, "unsupported-decision")
    return {
        "schemaVersion": "limitless.omarchy-result/0.1",
        "mode": "local-only",
        "disposition": disposition,
        "reason": decision["reason"],
        "profile": profile,
        "request": request,
        "decision": decision,
    }


def seal_local_capsule(draft_path: Path, output_path: Path, *, root: Path | None = None) -> dict[str, Any]:
    """Seal an owner-provided Omarchy capsule draft without publishing it.

    The generic Library owns the schema, digest, and no-overwrite write path.
    This integration only supplies the ergonomic default that a draft's
    directory is its exact-component root.
    """

    source = Path(draft_path)
    capsule_root = Path(root) if root is not None else source.parent
    try:
        from limitless_library.catalog import CatalogError, seal_capsule
        from limitless_library.contracts import ContractError, load_json, write_new_json
    except ImportError as error:
        raise AdapterError("Limitless Library is unavailable") from error
    try:
        sealed = seal_capsule(load_json(source), capsule_root)
        write_new_json(Path(output_path), sealed)
    except (CatalogError, ContractError, OSError) as error:
        raise AdapterError(str(error)) from error
    return sealed


def validate_plugin(plugin_dir: Path, *, runner: Runner = _default_runner) -> dict[str, Any]:
    """Ask Omarchy's native validator to inspect an explicit plugin directory."""

    target = Path(plugin_dir)
    if not target.is_dir():
        raise AdapterError("plugin directory is unavailable")
    try:
        completed = runner(("omarchy", "plugin", "validate", str(target)))
    except (OSError, subprocess.SubprocessError) as error:
        raise AdapterError("Omarchy plugin validator is unavailable") from error
    return {
        "schemaVersion": "limitless.omarchy-native-validation/0.1",
        "target": str(target),
        "status": "valid" if completed.returncode == 0 else "invalid",
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
