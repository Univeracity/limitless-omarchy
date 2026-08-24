"""Durable, low-friction sharing state for agent-registered methods.

Registration is always a fast local write.  Public transfer happens in a
detached best-effort worker and is resumable; service failure never turns the
agent tool call into a failure.  Mutable sharing state stays separate from the
immutable method record so destination changes do not rewrite provenance.
"""

from __future__ import annotations

import fcntl
import json
import os
import platform
import re
import secrets
import stat

# The only subprocess below executes this fixed local interpreter/module with
# validated absolute data paths and never invokes a shell.
import subprocess  # nosec B404
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from limitless_library.contracts import canonical_json_bytes

from .adapter import AdapterError
from .service import inspect_managed_service, manage_publication

STATE_SCHEMA_VERSION = "limitless.method-sharing-state/0.1"
SYNC_RESULT_SCHEMA_VERSION = "limitless.method-sharing-sync/0.1"
TRANSITION_RESULT_SCHEMA_VERSION = "limitless.method-sharing-transition/0.1"
MAX_STATE_BYTES = 64 * 1024
MAX_STATES = 2_000
_DRAFT_REF = re.compile(r"^draft:([0-9A-HJKMNP-TV-Z]{26})$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_DESTINATIONS = frozenset({"off", "local", "circle", "organization", "public"})
_PUBLIC_RETRY_STATES = frozenset({"queued", "retryable"})
_REMOTE_PENDING_STATES = frozenset({"submitted", "retryable", "withdrawal-queued"})


class ContributionError(ValueError):
    """A contribution transition or durable sharing state is invalid."""


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _directory(path: Path, label: str) -> Path:
    selected = Path(path)
    if not selected.is_absolute() or ".." in selected.parts or selected.is_symlink():
        raise ContributionError(f"{label} must be an absolute, normalized, non-symlink directory")
    selected.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not selected.is_dir() or selected.is_symlink():
        raise ContributionError(f"{label} is unavailable")
    return selected


def _suffix(draft_ref: str) -> str:
    if not isinstance(draft_ref, str):
        raise ContributionError("draft reference is invalid")
    match = _DRAFT_REF.fullmatch(draft_ref)
    if match is None:
        raise ContributionError("draft reference is invalid")
    return match.group(1)


def _state_path(registry: Path, draft_ref: str) -> Path:
    return registry / "states" / f"{_suffix(draft_ref)}.json"


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or not 1 <= before.st_size <= MAX_STATE_BYTES:
        raise ContributionError(f"{label} is not a bounded regular file")
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0))
    try:
        current = os.fstat(descriptor)
        if current.st_dev != before.st_dev or current.st_ino != before.st_ino or current.st_size != before.st_size:
            raise ContributionError(f"{label} changed while being read")
        payload = os.read(descriptor, MAX_STATE_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(payload) != before.st_size or len(payload) > MAX_STATE_BYTES:
        raise ContributionError(f"{label} changed or is oversized")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContributionError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict):
        raise ContributionError(f"{label} has an unsupported shape")
    return value


def _validate_state(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion",
        "draftRef",
        "destination",
        "state",
        "reason",
        "policyDigest",
        "submissionRef",
        "releaseRef",
        "publicationStatePath",
        "attempts",
        "updatedAt",
    }
    if not isinstance(value, dict) or set(value) != fields or value.get("schemaVersion") != STATE_SCHEMA_VERSION:
        raise ContributionError("method sharing state has an unsupported shape")
    _suffix(value.get("draftRef"))
    if value.get("destination") not in _DESTINATIONS:
        raise ContributionError("method sharing destination is invalid")
    if not isinstance(value.get("state"), str) or not value["state"] or len(value["state"]) > 64:
        raise ContributionError("method sharing disposition is invalid")
    for field in ("reason", "submissionRef", "publicationStatePath"):
        selected = value.get(field)
        if selected is not None and (not isinstance(selected, str) or not selected or len(selected) > 4096):
            raise ContributionError(f"method sharing {field} is invalid")
    digest = value.get("policyDigest")
    if digest is not None and (not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None):
        raise ContributionError("method sharing policy digest is invalid")
    if value.get("releaseRef") is not None and not isinstance(value["releaseRef"], dict):
        raise ContributionError("method sharing release reference is invalid")
    attempts = value.get("attempts")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or not 0 <= attempts <= 1_000_000:
        raise ContributionError("method sharing attempt count is invalid")
    if not isinstance(value.get("updatedAt"), str) or len(value["updatedAt"]) != 20:
        raise ContributionError("method sharing timestamp is invalid")
    return dict(value)


def _replace_json(path: Path, value: dict[str, Any]) -> None:
    payload = canonical_json_bytes(value) + b"\n"
    if len(payload) > MAX_STATE_BYTES:
        raise ContributionError("method sharing state is too large")
    temporary = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp"
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
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_CLOEXEC)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _initial_disposition(destination: str) -> tuple[str, str | None]:
    if destination == "off":
        return "disabled", None
    if destination == "local":
        return "local", None
    if destination in {"circle", "organization"}:
        return "waiting-account", "account-scope-required"
    return "queued", None


def initialize_contribution(registry_path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Create the mutable sharing projection for one immutable method record."""

    registry = _directory(registry_path, "draft registry")
    _directory(registry / "states", "method sharing state directory")
    destination = record.get("requestedDestination")
    if destination not in _DESTINATIONS:
        raise ContributionError("registered method destination is invalid")
    state_path = _state_path(registry, str(record.get("draftRef")))
    if state_path.exists():
        return _validate_state(_read_json(state_path, label="method sharing state"))
    disposition, reason = _initial_disposition(destination)
    value = {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "draftRef": record["draftRef"],
        "destination": destination,
        "state": disposition,
        "reason": reason,
        "policyDigest": record.get("publicPolicyDigest"),
        "submissionRef": None,
        "releaseRef": None,
        "publicationStatePath": None,
        "attempts": 0,
        "updatedAt": _utc_now(),
    }
    _replace_json(state_path, _validate_state(value))
    return value


def contribution_states(registry_path: Path) -> dict[str, dict[str, Any]]:
    registry = _directory(registry_path, "draft registry")
    root = _directory(registry / "states", "method sharing state directory")
    paths = sorted(root.glob("*.json"))
    if len(paths) > MAX_STATES:
        raise ContributionError("method sharing registry exceeds its supported bound")
    result: dict[str, dict[str, Any]] = {}
    for path in paths:
        if path.is_symlink():
            raise ContributionError("method sharing registry contains a symbolic link")
        state = _validate_state(_read_json(path, label="method sharing state"))
        if path.name != _suffix(state["draftRef"]) + ".json" or state["draftRef"] in result:
            raise ContributionError("method sharing state is misbound")
        result[state["draftRef"]] = state
    return result


def transition_contribution(
    registry_path: Path,
    *,
    draft_ref: str,
    destination: str,
    public_policy_digest: str | None,
) -> dict[str, Any]:
    """Apply one explicit per-method destination override without rewriting it.

    The registry lock prevents a revision from superseding the selected method
    between the active-revision check and the state change. The sharing lock
    prevents the background worker from overwriting the owner's transition.
    """

    registry = _directory(registry_path, "draft registry")
    flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try:
        registry_lock = os.open(registry / ".lock", flags, 0o600)
        try:
            sharing_lock = os.open(registry / ".sharing.lock", flags, 0o600)
            try:
                fcntl.flock(registry_lock, fcntl.LOCK_EX)
                fcntl.flock(sharing_lock, fcntl.LOCK_EX)
                return _transition_contribution_locked(
                    registry,
                    draft_ref=draft_ref,
                    destination=destination,
                    public_policy_digest=public_policy_digest,
                )
            finally:
                os.close(sharing_lock)
        finally:
            os.close(registry_lock)
    except OSError as error:
        raise ContributionError("method sharing transition could not be stored safely") from error


def _transition_contribution_locked(
    registry_path: Path,
    *,
    draft_ref: str,
    destination: str,
    public_policy_digest: str | None,
) -> dict[str, Any]:
    """Apply a validated transition while both method-state locks are held."""

    from .drafts import _active_refs, _records, load_draft  # avoid a module import cycle

    if destination not in _DESTINATIONS:
        raise ContributionError("method sharing destination is invalid")
    if destination == "public":
        if not isinstance(public_policy_digest, str) or _DIGEST.fullmatch(public_policy_digest) is None:
            raise ContributionError("public sharing requires the current verified policy digest")
    elif public_policy_digest is not None:
        raise ContributionError("a public policy digest is valid only for public sharing")
    registry = _directory(registry_path, "draft registry")
    record = load_draft(registry, draft_ref)
    if draft_ref not in _active_refs(_records(registry)):
        raise ContributionError("only the current method revision can change sharing destination")
    path = _state_path(registry, draft_ref)
    state = (
        _validate_state(_read_json(path, label="method sharing state"))
        if path.exists()
        else initialize_contribution(registry, record)
    )
    if (
        destination == state["destination"]
        and (destination != "public" or public_policy_digest == state["policyDigest"])
        and state["state"] not in {"attention", "policy-attention"}
    ):
        disposition = "unchanged"
    elif destination == "public":
        if state["destination"] == "public" and state["state"] == "published":
            disposition = "unchanged"
        elif state["publicationStatePath"] is not None:
            raise ContributionError("a previously submitted method must be revised before it can be published again")
        else:
            state = _updated(
                state,
                destination="public",
                state="queued",
                reason=None,
                policyDigest=public_policy_digest,
                submissionRef=None,
                releaseRef=None,
                publicationStatePath=None,
            )
            _replace_json(path, state)
            disposition = "queued"
    elif (
        state["destination"] == "public"
        and state["publicationStatePath"] is not None
        and state["state"]
        in {
            "submitted",
            "published",
            "retryable",
        }
    ):
        state = _updated(
            state,
            destination=destination,
            state="withdrawal-queued",
            reason=f"move-to:{destination}",
        )
        _replace_json(path, state)
        disposition = "withdrawal-queued"
    else:
        target_state, reason = _initial_disposition(destination)
        state = _updated(
            state,
            destination=destination,
            state=target_state,
            reason=reason,
            policyDigest=None,
            submissionRef=None,
            releaseRef=None,
            publicationStatePath=None,
        )
        _replace_json(path, state)
        disposition = target_state
    return {
        "schemaVersion": TRANSITION_RESULT_SCHEMA_VERSION,
        "draftRef": draft_ref,
        "destination": state["destination"],
        "status": disposition,
    }


def _public_method_text(record: dict[str, Any]) -> str:
    method = record["method"]
    lines = [f"# {record['title']}", "", str(method["summary"]), "", "## Steps", ""]
    lines.extend(f"{index}. {step}" for index, step in enumerate(method["steps"], start=1))
    lines.extend(["", "## Verification", ""])
    lines.extend(f"- {item}" for item in method["verification"])
    public_sources = sorted(source for source in record.get("sourceReferences", []) if source.startswith("https://"))
    if public_sources:
        lines.extend(["", "## Public source references", ""])
        lines.extend(f"- {source}" for source in public_sources)
    return "\n".join(lines) + "\n"


def _publication_material(
    registry: Path,
    record: dict[str, Any],
    *,
    parent_release: dict[str, Any] | None,
) -> Path:
    suffix = _suffix(record["draftRef"])
    root = _directory(registry / "publication", "method publication directory")
    target = root / suffix
    if target.exists() and (target.is_symlink() or not target.is_dir()):
        raise ContributionError("method publication material is unsafe")
    target.mkdir(mode=0o700, exist_ok=True)
    method_path = target / "method.md"
    publication_path = target / "publication.json"
    interfaces = ["omarchy.plugin/v1"] if record["taskKind"] == "omarchy-customization" else ["limitless.mcp/v1"]
    supported = {
        "platform": "linux" if record["taskKind"] == "omarchy-customization" else "any",
        "architecture": "any",
        "runtime": "omarchy" if record["taskKind"] == "omarchy-customization" else "any",
        "versionRange": "any",
        "interfaces": interfaces,
    }
    parents = [] if parent_release is None else [parent_release]
    publication = {
        "schemaVersion": "limitless.publication-draft/1.0",
        "candidate": {
            "title": record["title"][:120],
            "summary": record["method"]["summary"][:480],
            "treatment": "source-free-method",
            "capabilities": sorted({record["taskKind"], *interfaces}),
        },
        "lineage": {
            "lineageId": record["lineageId"],
            "version": f"1.0.{int(record['revision']) - 1}",
            "releaseClass": "initial" if parent_release is None else "revision",
            "parents": parents,
            "supersedes": parent_release,
        },
        "objects": [{"role": "method", "path": "method.md"}],
        "compatibility": {"supportedTargets": [supported], "verifiedTargets": []},
        "buildContext": {
            "platform": platform.system().lower() or "unknown",
            "architecture": platform.machine().lower() or "unknown",
            "runtime": "limitless-omarchy",
            "version": "0.1.0",
            "interfaces": interfaces,
        },
        "evidenceDigests": [record["contentDigest"]],
        "rights": {"license": "CC0-1.0", "allowedUses": ["derive-method"], "hasAuthority": True},
    }
    method_payload = _public_method_text(record).encode("utf-8")
    publication_payload = canonical_json_bytes(publication) + b"\n"
    for path, payload in ((method_path, method_payload), (publication_path, publication_payload)):
        if path.exists():
            before = path.read_bytes()
            if before != payload:
                raise ContributionError("prepared publication material differs from immutable method record")
            continue
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
    return publication_path


def _prior_release(record: dict[str, Any], states: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    prior_ref = record.get("supersedes")
    if prior_ref is None:
        return None
    prior = states.get(prior_ref)
    release = None if prior is None else prior.get("releaseRef")
    return dict(release) if isinstance(release, dict) else None


def _updated(current: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return _validate_state({**current, **changes, "updatedAt": _utc_now()})


def sync_contributions(registry_path: Path, *, limit: int = 8) -> dict[str, Any]:
    """Advance queued public work without exposing its contents to the caller."""

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 32:
        raise ContributionError("contribution sync limit is invalid")
    from .drafts import _active_refs, _records  # avoid a module import cycle

    registry = _directory(registry_path, "draft registry")
    lock_path = registry / ".sharing.lock"
    lock = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    processed = 0
    published = 0
    withdrawn = 0
    attention = 0
    retryable = 0
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        return {
            "schemaVersion": SYNC_RESULT_SCHEMA_VERSION,
            "status": "already-running",
            "processed": 0,
            "published": 0,
            "withdrawn": 0,
            "attention": 0,
            "retryable": 0,
        }
    try:
        records = _records(registry)
        active = _active_refs(records)
        states = contribution_states(registry)
        by_ref = {record["draftRef"]: record for record in records}
        unresolved = [
            draft_ref
            for draft_ref, state in states.items()
            if draft_ref in by_ref
            and state["publicationStatePath"] is not None
            and state["state"] in _REMOTE_PENDING_STATES
        ]
        work = sorted(unresolved) + [draft_ref for draft_ref in sorted(active) if draft_ref not in unresolved]
        for draft_ref in work:
            if processed >= limit:
                break
            record = by_ref[draft_ref]
            state = states.get(draft_ref) or initialize_contribution(registry, record)
            states[draft_ref] = state
            if state["state"] == "withdrawal-queued":
                processed += 1
                try:
                    result = manage_publication(
                        operation="revoke",
                        draft_path=None,
                        state_path=Path(state["publicationStatePath"]),
                        accepted_publication_policy_digest=None,
                        reason_code="publisher-scope-change",
                    )
                    target_state, target_reason = _initial_disposition(state["destination"])
                    state = _updated(
                        state,
                        state=target_state,
                        reason=target_reason,
                        policyDigest=None,
                        releaseRef=result.get("releaseRef"),
                        attempts=state["attempts"] + 1,
                    )
                    withdrawn += 1
                except (AdapterError, OSError):
                    state = _updated(
                        state,
                        state="withdrawal-queued",
                        reason="service-unavailable",
                        attempts=state["attempts"] + 1,
                    )
                    retryable += 1
                _replace_json(_state_path(registry, draft_ref), state)
                states[draft_ref] = state
                continue
            if state["publicationStatePath"] is not None and state["state"] in {"submitted", "retryable"}:
                processed += 1
                try:
                    result = manage_publication(
                        operation="status",
                        draft_path=None,
                        state_path=Path(state["publicationStatePath"]),
                        accepted_publication_policy_digest=None,
                        reason_code=None,
                    )
                    admission = result["admissionState"]
                    if admission == "active":
                        disposition = "published"
                        published += 1
                    elif admission in {"rejected", "revoked"}:
                        disposition = admission
                        attention += 1
                    else:
                        disposition = "submitted"
                    state = _updated(
                        state,
                        state=disposition,
                        reason=",".join(result.get("reasonCodes", [])) or None,
                        releaseRef=result.get("releaseRef"),
                        attempts=state["attempts"] + 1,
                    )
                except (AdapterError, OSError):
                    state = _updated(
                        state,
                        state="retryable",
                        reason="service-unavailable",
                        attempts=state["attempts"] + 1,
                    )
                    retryable += 1
                _replace_json(_state_path(registry, draft_ref), state)
                states[draft_ref] = state
                continue
            if draft_ref not in active:
                continue
            if state["destination"] != "public":
                continue
            if state["state"] not in _PUBLIC_RETRY_STATES:
                continue
            prior_ref = record.get("supersedes")
            prior_state = states.get(prior_ref) if isinstance(prior_ref, str) else None
            if (
                prior_state is not None
                and prior_state["publicationStatePath"] is not None
                and prior_state["state"] in _REMOTE_PENDING_STATES
            ):
                continue
            processed += 1
            digest = state.get("policyDigest")
            try:
                inspected = inspect_managed_service()
                advertised = (inspected.get("publicationPolicy") or {}).get("digest")
                if digest is None or advertised != digest:
                    state = _updated(state, state="policy-attention", reason="publication-policy-changed")
                    attention += 1
                else:
                    draft_path = _publication_material(
                        registry,
                        record,
                        parent_release=_prior_release(record, states),
                    )
                    result = manage_publication(
                        operation="publish",
                        draft_path=draft_path,
                        state_path=None,
                        accepted_publication_policy_digest=digest,
                        reason_code=None,
                    )
                    state = _updated(
                        state,
                        state="published" if result["admissionState"] == "active" else "submitted",
                        reason=",".join(result.get("reasonCodes", [])) or None,
                        submissionRef=result.get("submissionRef"),
                        releaseRef=result.get("releaseRef"),
                        publicationStatePath=result.get("statePath"),
                        attempts=state["attempts"] + 1,
                    )
                    if state["state"] == "published":
                        published += 1
            except ContributionError:
                state = _updated(
                    state,
                    state="attention",
                    reason="local-preparation-error",
                    attempts=state["attempts"] + 1,
                )
                attention += 1
            except (AdapterError, OSError):
                state = _updated(
                    state,
                    state="retryable",
                    reason="service-unavailable",
                    attempts=state["attempts"] + 1,
                )
                retryable += 1
            _replace_json(_state_path(registry, draft_ref), state)
            states[draft_ref] = state
        return {
            "schemaVersion": SYNC_RESULT_SCHEMA_VERSION,
            "status": "complete",
            "processed": processed,
            "published": published,
            "withdrawn": withdrawn,
            "attention": attention,
            "retryable": retryable,
        }
    finally:
        os.close(lock)


def schedule_contribution_sync(registry_path: Path, *, activity_path: Path | None = None) -> bool:
    """Launch one detached best-effort worker; registration never waits for it."""

    registry = Path(registry_path)
    if not registry.is_absolute() or ".." in registry.parts:
        raise ContributionError("draft registry path is invalid")
    command = [sys.executable, "-m", "limitless_omarchy.cli", "contribution-sync", "--drafts-path", str(registry)]
    if activity_path is not None:
        selected = Path(activity_path)
        if not selected.is_absolute() or ".." in selected.parts:
            raise ContributionError("activity path is invalid")
        command.extend(["--activity-path", str(selected)])
    try:
        subprocess.Popen(  # nosec B603
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except OSError:
        return False
    return True
