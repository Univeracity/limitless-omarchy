"""Explicit managed-service adapter for the Omarchy panel.

Local reuse never imports or calls this module.  The panel reaches it only
after an owner explicitly enables, inspects, or queries the optional service.
"""

from __future__ import annotations

import copy
import os
import platform
import re
import secrets
import stat
from base64 import urlsafe_b64decode
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from limitless_library.contracts import (
    ContractError,
    canonical_json_bytes,
    load_json,
    sha256_file,
    strict_json_loads,
    write_new_bytes,
)
from limitless_library.official_service import (
    OfficialServiceActivationError,
    OfficialServiceUnavailableError,
    activate_official_service,
    activated_service_connector,
    activated_service_profile,
)
from limitless_library.publication import (
    PublicationError,
    publication_status,
    publish_draft,
    revoke_publication,
)
from limitless_library.service_connector import (
    ServiceConnector,
    ServiceConnectorError,
    ServiceProfile,
    ServiceUnavailableError,
    VerifiedService,
)
from limitless_library.service_identity import (
    InstallationSigner,
    ServiceIdentityError,
    installation_publisher_authority,
)

from .adapter import AdapterError, Runner, _default_runner, discover_profile

ConnectorFactory = Callable[[ServiceProfile], ServiceConnector]

_NUMERIC_RELEASE = re.compile(r"^[0-9]+(?:\.[0-9]+){0,3}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REASON_CODE = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")
_HANDOFF_STATE_SCHEMA_VERSION = "limitless.omarchy-artifact-handoff-state/0.1"
_MAX_HANDOFF_STATE_BYTES = 64 * 1024


def _service_connector(
    profile_path: Path | None,
    *,
    access_token: str | None,
    connector_factory: ConnectorFactory,
) -> ServiceConnector:
    try:
        if profile_path is None and not access_token and connector_factory is ServiceConnector:
            return activated_service_connector()
        if profile_path is None:
            profile = activated_service_profile(access_token=access_token or None)
        else:
            if not profile_path.is_absolute() or not profile_path.is_file():
                raise AdapterError("service profile must be an absolute path to a readable file")
            profile = ServiceProfile.from_json(
                load_json(profile_path),
                access_token=access_token or None,
            )
        return connector_factory(profile)
    except AdapterError:
        raise
    except (
        ContractError,
        OfficialServiceActivationError,
        OSError,
        ValueError,
    ) as error:
        raise AdapterError("service profile or credential is invalid") from error


def activate_managed_service() -> dict[str, Any]:
    """Enable the release-pinned official service from one explicit UI action."""

    try:
        state = activate_official_service()
        profile = ServiceProfile.from_json(state["profile"])
    except OfficialServiceUnavailableError:
        return {
            "schemaVersion": "limitless.omarchy-service-status/0.1",
            "mode": "service-unavailable",
            "reason": "service-unavailable-local-still-available",
        }
    except (OfficialServiceActivationError, OSError, ValueError) as error:
        raise AdapterError("official service activation failed") from error
    return {
        "schemaVersion": "limitless.omarchy-service-status/0.1",
        "mode": "managed-service-ready",
        "service": profile.public_summary(),
        "policy": {"digest": profile.accepted_policy_digest},
        "activatedAt": state["activatedAt"],
    }


def _service_status(
    connector: ServiceConnector,
    verified: VerifiedService,
) -> dict[str, Any]:
    discovery = verified.discovery
    return {
        "schemaVersion": "limitless.omarchy-service-status/0.1",
        "mode": "managed-service-ready",
        "service": connector.profile.public_summary(),
        "policy": discovery["dataUsePolicy"],
        "publicationPolicy": discovery.get("publicationPolicy"),
        "resultVersions": discovery["resultVersions"],
        "expiresAt": discovery["expiresAt"],
    }


def inspect_managed_service(
    profile_path: Path | None = None,
    *,
    connector_factory: ConnectorFactory = ServiceConnector,
) -> dict[str, Any]:
    """Verify one explicitly supplied profile without sending a task query."""

    connector = _service_connector(
        profile_path,
        access_token=None,
        connector_factory=connector_factory,
    )
    try:
        return _service_status(connector, connector.inspect())
    except ServiceUnavailableError:
        return {
            "schemaVersion": "limitless.omarchy-service-status/0.1",
            "mode": "service-unavailable",
            "service": connector.profile.public_summary(),
            "reason": "service-unavailable-local-still-available",
        }
    except ServiceConnectorError as error:
        raise AdapterError("service profile or authority verification failed") from error


def build_service_receiver_context(
    omarchy_profile: dict[str, Any],
) -> dict[str, Any]:
    """Translate the minimal local profile into the public service contract."""

    toolchain = omarchy_profile.get("toolchain")
    if not isinstance(toolchain, dict):
        raise AdapterError("Omarchy profile toolchain is invalid")
    release = toolchain.get("omarchyRelease")
    if not isinstance(release, str) or not release:
        raise AdapterError("Omarchy profile release is invalid")
    version_range = f"=={release}" if _NUMERIC_RELEASE.fullmatch(release) else "any"
    architecture = platform.machine().lower() or "unknown"
    host = platform.system().lower() or "unknown"
    interfaces = ["omarchy.plugin/v1"]
    target = {
        "id": "target:omarchy-current-device",
        "platform": host,
        "architecture": architecture,
        "runtime": "omarchy",
        "versionRange": version_range,
        "interfaces": interfaces,
    }
    return {
        "receiverId": "receiver:omarchy-desktop",
        "allowedUse": "install-plugin",
        "interfaces": interfaces,
        "execution": {
            "platform": host,
            "architecture": architecture,
            "runtime": "python",
            "version": platform.python_version(),
        },
        "targets": [target],
        "compatibilityMode": "one-target",
        "selectedTarget": target["id"],
    }


def _handoff_root(environ: Mapping[str, str] | None = None) -> Path:
    environment = os.environ if environ is None else environ
    configured = environment.get("XDG_STATE_HOME")
    if configured:
        root = Path(configured)
    else:
        home = environment.get("HOME")
        if not home:
            raise AdapterError("a per-user state directory is unavailable")
        root = Path(home) / ".local" / "state"
    if not root.is_absolute() or ".." in root.parts:
        raise AdapterError("the per-user state directory is invalid")
    return root / "limitless-omarchy" / "artifact-handoffs"


def _private_handoff_root(environ: Mapping[str, str] | None = None) -> Path:
    root = _handoff_root(environ)
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or os.name == "posix"
            and info.st_uid != os.geteuid()
        ):
            raise AdapterError("the artifact handoff directory is unsafe")
        if os.name == "posix" and stat.S_IMODE(info.st_mode) != 0o700:
            root.chmod(0o700)
            if stat.S_IMODE(root.lstat().st_mode) != 0o700:
                raise AdapterError("the artifact handoff directory is unsafe")
    except AdapterError:
        raise
    except OSError as error:
        raise AdapterError("the artifact handoff directory is unavailable") from error
    return root.resolve(strict=True)


def _project_service_selection(decision: dict[str, Any] | None) -> dict[str, Any] | None:
    if decision is None or decision["treatment"] == "abstention":
        return None
    selected = decision["selection"]
    projected = {
        key: copy.deepcopy(selected[key])
        for key in (
            "capabilityId",
            "title",
            "summary",
            "compatibility",
            "provenance",
            "allowedUses",
            "confidence",
            "rationale",
            "supplyAuthorityId",
            "cardDigest",
            "method",
        )
        if key in selected
    }
    immutable = selected.get("immutable")
    if isinstance(immutable, dict):
        projected["immutable"] = {
            key: copy.deepcopy(immutable[key]) for key in ("kind", "digest", "revision") if key in immutable
        }
    return projected


def _write_handoff_state(
    *,
    connector: ServiceConnector,
    result: dict[str, Any],
    signer: InstallationSigner,
    publisher: dict[str, Any],
    environ: Mapping[str, str] | None = None,
) -> Path:
    root = _private_handoff_root(environ)
    digest = result.get("resultDigest")
    if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
        raise AdapterError("managed artifact continuation is invalid")
    payload = {
        "schemaVersion": _HANDOFF_STATE_SCHEMA_VERSION,
        "serviceId": connector.profile.service_id,
        "publisher": {key: publisher[key] for key in ("publisherId", "authorityId", "keyId", "generation")},
        "requestDigest": result["requestDigest"],
        "result": result,
    }
    state = {
        **payload,
        "signature": {
            "algorithm": "ed25519",
            "keyId": signer.key_id,
            "value": signer.sign(canonical_json_bytes(payload)),
        },
    }
    path = root / f"{digest.removeprefix('sha256:')}.json"
    encoded = canonical_json_bytes(state) + b"\n"
    if len(encoded) > _MAX_HANDOFF_STATE_BYTES:
        raise AdapterError("managed artifact continuation exceeds its local limit")
    if path.exists():
        selected, saved = _load_handoff_state(
            path,
            connector=connector,
            signer=signer,
            publisher=publisher,
            environ=environ,
        )
        if saved != state:
            raise AdapterError("managed artifact continuation conflicts with existing state")
        return selected
    try:
        write_new_bytes(path, encoded, mode=0o600)
    except (ContractError, OSError, ValueError) as error:
        raise AdapterError("managed artifact continuation could not be saved safely") from error
    return path


def _load_handoff_state(
    path: Path,
    *,
    connector: ServiceConnector,
    signer: InstallationSigner,
    publisher: dict[str, Any],
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    root = _private_handoff_root(environ)
    selected = Path(path)
    if (
        not selected.is_absolute()
        or selected.parent.resolve(strict=False) != root
        or re.fullmatch(r"[0-9a-f]{64}\.json", selected.name) is None
    ):
        raise AdapterError("managed artifact continuation path is invalid")
    descriptor: int | None = None
    try:
        before = selected.lstat()
        if (
            stat.S_ISLNK(before.st_mode)
            or not stat.S_ISREG(before.st_mode)
            or os.name == "posix"
            and before.st_uid != os.geteuid()
            or os.name == "posix"
            and stat.S_IMODE(before.st_mode) != 0o600
            or not 1 <= before.st_size <= _MAX_HANDOFF_STATE_BYTES
        ):
            raise AdapterError("managed artifact continuation is unsafe")
        descriptor = os.open(
            selected,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        current = os.fstat(descriptor)
        encoded = bytearray()
        while len(encoded) <= _MAX_HANDOFF_STATE_BYTES:
            chunk = os.read(
                descriptor,
                min(64 * 1024, _MAX_HANDOFF_STATE_BYTES + 1 - len(encoded)),
            )
            if not chunk:
                break
            encoded.extend(chunk)
        after = os.fstat(descriptor)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_size != before.st_size
            or current.st_dev != before.st_dev
            or current.st_ino != before.st_ino
            or after.st_size != current.st_size
            or len(encoded) != current.st_size
        ):
            raise AdapterError("managed artifact continuation changed during read")
        state = strict_json_loads(bytes(encoded).decode("utf-8"))
    except AdapterError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise AdapterError("managed artifact continuation is invalid") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if not isinstance(state, dict) or set(state) != {
        "schemaVersion",
        "serviceId",
        "publisher",
        "requestDigest",
        "result",
        "signature",
    }:
        raise AdapterError("managed artifact continuation has an unsupported shape")
    expected_publisher = {key: publisher[key] for key in ("publisherId", "authorityId", "keyId", "generation")}
    signature = state["signature"]
    payload = {key: state[key] for key in state if key != "signature"}
    result_digest = state["result"].get("resultDigest") if isinstance(state["result"], dict) else None
    if (
        state["schemaVersion"] != _HANDOFF_STATE_SCHEMA_VERSION
        or state["serviceId"] != connector.profile.service_id
        or state["publisher"] != expected_publisher
        or not isinstance(state["result"], dict)
        or state["requestDigest"] != state["result"].get("requestDigest")
        or not isinstance(result_digest, str)
        or _DIGEST.fullmatch(result_digest) is None
        or selected.name != result_digest.removeprefix("sha256:") + ".json"
        or not isinstance(signature, dict)
        or set(signature) != {"algorithm", "keyId", "value"}
        or signature["algorithm"] != "ed25519"
        or signature["keyId"] != signer.key_id
        or not isinstance(signature["value"], str)
        or _SIGNATURE.fullmatch(signature["value"]) is None
    ):
        raise AdapterError("managed artifact continuation is unbound")
    try:
        Ed25519PublicKey.from_public_bytes(signer.public_bytes()).verify(
            urlsafe_b64decode(signature["value"] + "=="),
            canonical_json_bytes(payload),
        )
    except (InvalidSignature, TypeError, ValueError) as error:
        raise AdapterError("managed artifact continuation signature is invalid") from error
    return selected.resolve(strict=True), state


def _managed_result(
    *,
    connector: ServiceConnector,
    local_profile: dict[str, Any],
    query: dict[str, Any],
    decision: dict[str, Any] | None,
    handoff_state_path: Path | None = None,
    unavailable: bool = False,
) -> dict[str, Any]:
    if unavailable:
        disposition = "abstain"
        reason = "service-unavailable-local-still-available"
    elif decision is None:
        raise AdapterError("managed service returned no decision")
    elif decision["treatment"] == "abstention":
        disposition = "abstain"
        reason = decision["selection"]["reason"]
    else:
        disposition = decision["treatment"]
        reason = "verified-service-selection"
    return {
        "schemaVersion": "limitless.omarchy-service-result/0.1",
        "mode": "managed-service",
        "disposition": disposition,
        "reason": reason,
        "profile": local_profile,
        "service": connector.profile.public_summary(),
        "requestDigest": query["queryDigest"],
        "selection": _project_service_selection(decision),
        "handoffStatePath": None if handoff_state_path is None else str(handoff_state_path),
    }


def query_managed_service(
    profile_path: Path | None = None,
    *,
    objective: str,
    access_token: str | None = None,
    omarchy_release: str | None = None,
    request_id: str | None = None,
    runner: Runner = _default_runner,
    connector_factory: ConnectorFactory = ServiceConnector,
) -> dict[str, Any]:
    """Issue one owner-authorized query and return only verified service data."""

    connector = _service_connector(
        profile_path,
        access_token=access_token,
        connector_factory=connector_factory,
    )
    local_profile = discover_profile(
        omarchy_release=omarchy_release,
        runner=runner,
    )
    try:
        query = connector.build_query(
            request_id=request_id or f"request:omarchy-{secrets.token_hex(16)}",
            objective=objective,
            receiver_context=build_service_receiver_context(local_profile),
        )
        decision = connector.query(query)
    except ServiceUnavailableError:
        return _managed_result(
            connector=connector,
            local_profile=local_profile,
            query=query,
            decision=None,
            unavailable=True,
        )
    except (ServiceConnectorError, ValueError) as error:
        raise AdapterError("managed service query verification failed") from error
    handoff_state = None
    if (
        profile_path is None
        and access_token is None
        and connector_factory is ServiceConnector
        and decision["treatment"] == "exact-component"
        and isinstance(decision["selection"].get("immutable"), dict)
        and decision["selection"]["immutable"].get("kind") == "artifact"
    ):
        try:
            signer, publisher = installation_publisher_authority(
                service_id=connector.profile.service_id,
            )
            handoff_state = _write_handoff_state(
                connector=connector,
                result=decision,
                signer=signer,
                publisher=publisher,
            )
        except (AdapterError, ServiceIdentityError, OSError, ValueError) as error:
            raise AdapterError("managed artifact continuation could not be bound locally") from error
    return _managed_result(
        connector=connector,
        local_profile=local_profile,
        query=query,
        decision=decision,
        handoff_state_path=handoff_state,
    )


def _private_staging_root(environ: Mapping[str, str] | None = None) -> Path:
    root = _handoff_root(environ).parent / "staged-artifacts"
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or os.name == "posix"
            and info.st_uid != os.geteuid()
        ):
            raise AdapterError("the managed artifact staging directory is unsafe")
        if os.name == "posix" and stat.S_IMODE(info.st_mode) != 0o700:
            root.chmod(0o700)
            if stat.S_IMODE(root.lstat().st_mode) != 0o700:
                raise AdapterError("the managed artifact staging directory is unsafe")
    except AdapterError:
        raise
    except OSError as error:
        raise AdapterError("the managed artifact staging directory is unavailable") from error
    return root.resolve(strict=True)


def stage_managed_artifact(
    state_path: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Redeem one locally signed continuation into digest-verified staging."""

    try:
        connector = activated_service_connector()
        signer, publisher = installation_publisher_authority(
            service_id=connector.profile.service_id,
        )
        selected_state, state = _load_handoff_state(
            state_path,
            connector=connector,
            signer=signer,
            publisher=publisher,
            environ=environ,
        )
        result = state["result"]
        immutable = result.get("selection", {}).get("immutable")
        if (
            result.get("treatment") != "exact-component"
            or not isinstance(immutable, dict)
            or immutable.get("kind") != "artifact"
            or not isinstance(immutable.get("digest"), str)
            or _DIGEST.fullmatch(immutable["digest"]) is None
        ):
            raise AdapterError("managed artifact continuation has no exact artifact")
        destination = _private_staging_root(environ) / (immutable["digest"].removeprefix("sha256:") + ".bin")
        if destination.exists() or destination.is_symlink():
            info = destination.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISREG(info.st_mode)
                or os.name == "posix"
                and info.st_uid != os.geteuid()
                or os.name == "posix"
                and stat.S_IMODE(info.st_mode) != 0o600
                or sha256_file(destination) != immutable["digest"]
            ):
                raise AdapterError("the existing managed artifact staging file is unsafe")
            staged = {
                "schemaVersion": "limitless.staged-service-artifact/1.0",
                "decisionRef": result["decisionRef"],
                "capabilityId": result["selection"]["capabilityId"],
                "revision": immutable["revision"],
                "digest": immutable["digest"],
                "byteLength": info.st_size,
                "path": str(destination),
                "nextAction": result["nextAction"],
            }
        else:
            staged = connector.fetch_selected_artifact_continuation(
                result=result,
                expected_request_digest=state["requestDigest"],
                destination=destination,
            )
    except AdapterError:
        raise
    except (
        ContractError,
        OfficialServiceActivationError,
        ServiceConnectorError,
        ServiceIdentityError,
        OSError,
        ValueError,
    ) as error:
        raise AdapterError("managed artifact could not be staged safely") from error
    return {
        "schemaVersion": "limitless.omarchy-artifact-stage-result/0.1",
        "decisionRef": staged["decisionRef"],
        "capabilityId": staged["capabilityId"],
        "revision": staged["revision"],
        "digest": staged["digest"],
        "byteLength": staged["byteLength"],
        "path": staged["path"],
        "nextAction": staged["nextAction"],
        "handoffStatePath": str(selected_state),
        "nativeInstallationRequired": True,
    }


def manage_publication(
    *,
    operation: str,
    draft_path: Path | None,
    state_path: Path | None,
    accepted_publication_policy_digest: str | None,
    reason_code: str | None,
) -> dict[str, Any]:
    """Run one explicit publisher action through anonymous installation authority."""

    if operation not in {"publish", "status", "revoke"}:
        raise AdapterError("publication operation is invalid")
    for selected in (draft_path, state_path):
        if selected is not None and (
            not isinstance(selected, Path) or not selected.is_absolute() or ".." in selected.parts
        ):
            raise AdapterError("publication path is invalid")
    if operation == "publish":
        if (
            draft_path is None
            or state_path is not None
            or reason_code is not None
            or not isinstance(accepted_publication_policy_digest, str)
            or _DIGEST.fullmatch(accepted_publication_policy_digest) is None
        ):
            raise AdapterError("publication input is invalid")
    elif (
        draft_path is not None
        or state_path is None
        or accepted_publication_policy_digest is not None
        or operation == "status"
        and reason_code is not None
    ):
        raise AdapterError("publication input is invalid")
    if operation == "revoke" and (not isinstance(reason_code, str) or _REASON_CODE.fullmatch(reason_code) is None):
        raise AdapterError("publication withdrawal reason is invalid")

    try:
        connector = activated_service_connector()
        signer, publisher = installation_publisher_authority(
            service_id=connector.profile.service_id,
        )
        if operation == "publish":
            result = publish_draft(
                connector,
                draft_path=draft_path,
                state_path=None,
                signer=signer,
                publisher=publisher,
                accepted_publication_policy_digest=accepted_publication_policy_digest,
            )
        elif operation == "status":
            result = publication_status(
                connector,
                state_path=state_path,
                signer=signer,
                publisher=publisher,
            )
        else:
            result = revoke_publication(
                connector,
                state_path=state_path,
                signer=signer,
                publisher=publisher,
                reason_code=reason_code,
            )
    except (
        OfficialServiceActivationError,
        PublicationError,
        ServiceConnectorError,
        ServiceIdentityError,
        OSError,
        ValueError,
    ) as error:
        raise AdapterError("managed publication could not be completed safely") from error

    return {
        "schemaVersion": "limitless.omarchy-publication-result/0.1",
        "operation": operation,
        "submissionRef": result["submissionRef"],
        "admissionState": result["admissionState"],
        "releaseRef": result.get("releaseRef"),
        "reasonCodes": result.get("reasonCodes", []),
        "uploadedObjectCount": len(result.get("uploadedObjects", [])),
        "statePath": result["statePath"],
    }
