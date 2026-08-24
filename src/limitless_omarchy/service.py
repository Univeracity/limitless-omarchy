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
import shutil
import stat
import subprocess  # nosec B404
import time
from base64 import urlsafe_b64decode
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from limitless_library.contracts import (
    ContractError,
    canonical_json_bytes,
    load_json,
    sha256_bytes,
    sha256_file,
    strict_json_loads,
    write_new_bytes,
)
from limitless_library.exact_file_bundle import (
    EXACT_FILE_BUNDLE_SCHEMA_VERSION,
    MAX_EXACT_FILE_BUNDLE_BYTES,
    ExactFileBundle,
    ExactFileBundleError,
    parse_exact_file_bundle,
)
from limitless_library.official_service import (
    OfficialServiceActivationError,
    OfficialServiceNotConfiguredError,
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

from .adapter import AdapterError, Runner, _default_runner, discover_profile, validate_plugin

ConnectorFactory = Callable[[ServiceProfile], ServiceConnector]

_NUMERIC_RELEASE = re.compile(r"^[0-9]+(?:\.[0-9]+){0,3}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REASON_CODE = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")
_WHOLE_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_USAGE_UPGRADE_URL = "https://limitlesslibrary.com/#contact"
_HANDOFF_STATE_SCHEMA_VERSION = "limitless.omarchy-artifact-handoff-state/0.1"
_RECEIVER_INSTALLATION_SCHEMA_VERSION = "limitless.omarchy-receiver-installation/0.1"
_RECEIVER_ADOPTION_SCHEMA_VERSION = "limitless.omarchy-receiver-adoption/0.1"
_MAX_HANDOFF_STATE_BYTES = 64 * 1024
_MAX_RECEIVER_STATE_BYTES = 256 * 1024
_EXACT_BUNDLE_MEDIA_TYPE = "application/vnd.limitless.exact-file-bundle+json"
_PLUGIN_ID = re.compile(r"^(?!omarchy\.)[a-z0-9][a-z0-9._-]{1,126}[a-z0-9]$")
_PLUGIN_KINDS = frozenset({"bar", "bar-widget", "menu", "overlay", "panel", "service"})
_SUMMONABLE_PLUGIN_KINDS = frozenset({"menu", "overlay", "panel"})


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
    """Enable and verify the release-pinned service from one explicit UI action."""

    try:
        state = activate_official_service()
        ServiceProfile.from_json(state["profile"])
        connector = activated_service_connector()
        result = _service_status(connector, connector.inspect())
    except OfficialServiceUnavailableError:
        return {
            "schemaVersion": "limitless.omarchy-service-status/0.1",
            "mode": "service-unavailable",
            "reason": "service-unavailable-local-still-available",
        }
    except ServiceUnavailableError:
        return {
            "schemaVersion": "limitless.omarchy-service-status/0.1",
            "mode": "service-unavailable",
            "reason": "service-unavailable-local-still-available",
        }
    except (OfficialServiceActivationError, ServiceConnectorError, OSError, ValueError) as error:
        raise AdapterError("official service activation failed") from error
    return {**result, "activatedAt": state["activatedAt"]}


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

    if profile_path is None and connector_factory is ServiceConnector:
        try:
            connector = activated_service_connector()
        except OfficialServiceNotConfiguredError:
            return {
                "schemaVersion": "limitless.omarchy-service-status/0.1",
                "mode": "service-not-enabled",
                "reason": "service-not-enabled",
            }
        except (
            OfficialServiceActivationError,
            ServiceIdentityError,
            OSError,
            ValueError,
        ) as error:
            raise AdapterError("service profile or credential is invalid") from error
    else:
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
    usage: dict[str, str] | None = None,
) -> dict[str, Any]:
    if usage is not None:
        disposition = "abstain"
        reason = "free-usage-exceeded"
    elif unavailable:
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
    result = {
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
    if usage is not None:
        result["usage"] = usage
    return result


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
    except ServiceUnavailableError as error:
        reset_at = getattr(error, "reset_at", None)
        upgrade_url = getattr(error, "upgrade_url", None)
        usage = None
        if (
            isinstance(reset_at, str)
            and _WHOLE_SECOND.fullmatch(reset_at) is not None
            and upgrade_url == _USAGE_UPGRADE_URL
        ):
            usage = {"resetAt": reset_at, "upgradeUrl": upgrade_url}
        return _managed_result(
            connector=connector,
            local_profile=local_profile,
            query=query,
            decision=None,
            unavailable=usage is None,
            usage=usage,
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


def _private_review_root(environ: Mapping[str, str] | None = None) -> Path:
    root = _handoff_root(environ).parent / "receiver-reviews"
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or os.name == "posix"
            and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700)
        ):
            raise AdapterError("the managed receiver review directory is unsafe")
    except AdapterError:
        raise
    except OSError as error:
        raise AdapterError("the managed receiver review directory is unavailable") from error
    return root.resolve(strict=True)


def _review_inventory(bundle: ExactFileBundle, root: Path) -> list[dict[str, Any]]:
    expected = {item.path: item for item in bundle.files}
    actual: set[str] = set()
    try:
        root_info = root.lstat()
        if (
            stat.S_ISLNK(root_info.st_mode)
            or not stat.S_ISDIR(root_info.st_mode)
            or os.name == "posix"
            and (root_info.st_uid != os.geteuid() or stat.S_IMODE(root_info.st_mode) != 0o700)
        ):
            raise AdapterError("the managed receiver review tree is unsafe")
        for directory, directories, files in os.walk(root, followlinks=False):
            current = Path(directory)
            for name in directories:
                info = (current / name).lstat()
                if (
                    stat.S_ISLNK(info.st_mode)
                    or not stat.S_ISDIR(info.st_mode)
                    or os.name == "posix"
                    and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700)
                ):
                    raise AdapterError("the managed receiver review tree is unsafe")
            for name in files:
                path = current / name
                relative = path.relative_to(root).as_posix()
                item = expected.get(relative)
                if item is None:
                    raise AdapterError("the managed receiver review tree differs from its bundle")
                descriptor = -1
                try:
                    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
                    info = os.fstat(descriptor)
                    hasher = sha256()
                    total = 0
                    while True:
                        chunk = os.read(descriptor, 128 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > item.byte_length:
                            raise AdapterError("the managed receiver review tree differs from its bundle")
                        hasher.update(chunk)
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or os.name == "posix"
                        and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != int(item.mode, 8))
                        or total != item.byte_length
                        or os.fstat(descriptor).st_size != item.byte_length
                        or "sha256:" + hasher.hexdigest() != item.content_digest
                    ):
                        raise AdapterError("the managed receiver review tree differs from its bundle")
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                actual.add(relative)
    except AdapterError:
        raise
    except OSError as error:
        raise AdapterError("the managed receiver review tree is unavailable") from error
    if actual != set(expected):
        raise AdapterError("the managed receiver review tree differs from its bundle")
    return [
        {
            "path": item.path,
            "mode": item.mode,
            "byteLength": item.byte_length,
            "contentDigest": item.content_digest,
        }
        for item in bundle.files
    ]


def _materialize_review_bundle(
    bundle: ExactFileBundle,
    *,
    digest: str,
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, list[dict[str, Any]]]:
    root = _private_review_root(environ)
    destination = root / digest.removeprefix("sha256:")
    created = False
    try:
        if destination.exists() or destination.is_symlink():
            inventory = _review_inventory(bundle, destination)
            return destination.resolve(strict=True), inventory
        destination.mkdir(mode=0o700)
        created = True
        for item in bundle.files:
            path = destination.joinpath(*item.path.split("/"))
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            for parent in path.parents:
                if parent == destination.parent:
                    break
                parent.chmod(0o700)
            write_new_bytes(path, item.data, mode=int(item.mode, 8))
        inventory = _review_inventory(bundle, destination)
        return destination.resolve(strict=True), inventory
    except (AdapterError, ContractError, OSError, ValueError) as error:
        if created:
            shutil.rmtree(destination, ignore_errors=True)
        if isinstance(error, AdapterError):
            raise
        raise AdapterError("managed exact bundle could not be materialized safely") from error


def _read_private_staged_bundle(path: Path, *, digest: str, byte_length: int) -> bytes:
    """Read one staged bundle through a no-follow descriptor and reverify it."""

    if (
        not isinstance(byte_length, int)
        or isinstance(byte_length, bool)
        or not 1 <= byte_length <= MAX_EXACT_FILE_BUNDLE_BYTES
    ):
        raise AdapterError("the staged exact bundle length is invalid")
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or os.name == "posix"
            and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600)
            or info.st_size != byte_length
        ):
            raise AdapterError("the staged exact bundle is unsafe")
        chunks: list[bytes] = []
        remaining = byte_length
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise AdapterError("the staged exact bundle changed while reading")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1) or os.fstat(descriptor).st_size != byte_length:
            raise AdapterError("the staged exact bundle changed while reading")
        payload = b"".join(chunks)
        if sha256_bytes(payload) != digest:
            raise AdapterError("the staged exact bundle digest is invalid")
        return payload
    except AdapterError:
        raise
    except OSError as error:
        raise AdapterError("the staged exact bundle is unavailable") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


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
                or isinstance(immutable.get("byteLength"), int)
                and info.st_size != immutable["byteLength"]
            ):
                raise AdapterError("the existing managed artifact staging file is unsafe")
            staged = {
                "schemaVersion": (
                    "limitless.staged-service-artifact/1.1"
                    if immutable.get("format") == EXACT_FILE_BUNDLE_SCHEMA_VERSION
                    and immutable.get("mediaType") == _EXACT_BUNDLE_MEDIA_TYPE
                    else "limitless.staged-service-artifact/1.0"
                ),
                "decisionRef": result["decisionRef"],
                "capabilityId": result["selection"]["capabilityId"],
                "revision": immutable["revision"],
                "digest": immutable["digest"],
                "byteLength": info.st_size,
                "path": str(destination),
                "nextAction": result["nextAction"],
                **(
                    {
                        "format": immutable["format"],
                        "mediaType": immutable["mediaType"],
                    }
                    if immutable.get("format") == EXACT_FILE_BUNDLE_SCHEMA_VERSION
                    and immutable.get("mediaType") == _EXACT_BUNDLE_MEDIA_TYPE
                    else {}
                ),
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
        **(
            {
                "format": staged["format"],
                "mediaType": staged["mediaType"],
            }
            if staged.get("schemaVersion") == "limitless.staged-service-artifact/1.1"
            else {}
        ),
    }


def prepare_managed_plugin_review(
    state_path: Path,
    *,
    runner: Runner = _default_runner,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Stage, materialize, and natively validate one exact Omarchy bundle.

    This is the explicit receiver adapter. It never invokes Omarchy's add,
    enable, disable, or remove operations; installation remains a separate
    owner-controlled native action after review.
    """

    staged = stage_managed_artifact(state_path, environ=environ)
    if staged.get("format") != EXACT_FILE_BUNDLE_SCHEMA_VERSION or staged.get("mediaType") != _EXACT_BUNDLE_MEDIA_TYPE:
        raise AdapterError("managed artifact is not an exact file bundle")
    bundle_path = Path(staged["path"])
    try:
        payload = _read_private_staged_bundle(
            bundle_path,
            digest=staged["digest"],
            byte_length=staged["byteLength"],
        )
        bundle = parse_exact_file_bundle(payload)
        review_path, inventory = _materialize_review_bundle(
            bundle,
            digest=staged["digest"],
            environ=environ,
        )
        native_validation = validate_plugin(review_path, runner=runner)
    except AdapterError:
        raise
    except (ExactFileBundleError, OSError, ValueError) as error:
        raise AdapterError("managed exact bundle review failed closed") from error
    return {
        "schemaVersion": "limitless.omarchy-artifact-review-result/0.1",
        "decisionRef": staged["decisionRef"],
        "capabilityId": staged["capabilityId"],
        "revision": staged["revision"],
        "digest": staged["digest"],
        "bundlePath": staged["path"],
        "reviewPath": str(review_path),
        "files": inventory,
        "nativeValidation": native_validation,
        "installationDisposition": "not-installed",
        "nativeInstallationRequired": True,
    }


def _bundle_plugin_manifest(bundle: ExactFileBundle) -> dict[str, Any]:
    manifests = [item for item in bundle.files if item.path == "manifest.json"]
    if len(manifests) != 1:
        raise AdapterError("managed Omarchy bundle must contain one root manifest")
    try:
        manifest = strict_json_loads(manifests[0].data.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise AdapterError("managed Omarchy bundle manifest is invalid") from error
    if not isinstance(manifest, dict):
        raise AdapterError("managed Omarchy bundle manifest is invalid")
    plugin_id = manifest.get("id")
    kinds = manifest.get("kinds")
    if (
        manifest.get("schemaVersion") != 1
        or not isinstance(plugin_id, str)
        or _PLUGIN_ID.fullmatch(plugin_id) is None
        or not isinstance(kinds, list)
        or not kinds
        or len(kinds) != len(set(kinds))
        or not all(isinstance(kind, str) and kind in _PLUGIN_KINDS for kind in kinds)
        or not isinstance(manifest.get("entryPoints"), dict)
    ):
        raise AdapterError("managed Omarchy bundle manifest is outside the receiver contract")
    return {"id": plugin_id, "kinds": sorted(kinds)}


def _private_receiver_root(
    name: str,
    environ: Mapping[str, str] | None = None,
) -> Path:
    if name not in {"receiver-adoptions", "receiver-installations"}:
        raise AdapterError("receiver state kind is invalid")
    root = _handoff_root(environ).parent / name
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or os.name == "posix"
            and info.st_uid != os.geteuid()
        ):
            raise AdapterError("the managed receiver state directory is unsafe")
        if os.name == "posix" and stat.S_IMODE(info.st_mode) != 0o700:
            root.chmod(0o700)
            if stat.S_IMODE(root.lstat().st_mode) != 0o700:
                raise AdapterError("the managed receiver state directory is unsafe")
    except AdapterError:
        raise
    except OSError as error:
        raise AdapterError("the managed receiver state directory is unavailable") from error
    return root.resolve(strict=True)


def _omarchy_plugins_root(environ: Mapping[str, str] | None = None) -> Path:
    environment = os.environ if environ is None else environ
    home = environment.get("HOME")
    if not home:
        raise AdapterError("the Omarchy user configuration directory is unavailable")
    configured = Path(home)
    if not configured.is_absolute() or ".." in configured.parts:
        raise AdapterError("the Omarchy user configuration directory is invalid")
    root = configured / ".config" / "omarchy" / "plugins"
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        resolved = root.resolve(strict=True)
        info = resolved.lstat()
        if not stat.S_ISDIR(info.st_mode) or os.name == "posix" and info.st_uid != os.geteuid():
            raise AdapterError("the Omarchy plugin directory is unsafe")
    except AdapterError:
        raise
    except OSError as error:
        raise AdapterError("the Omarchy plugin directory is unavailable") from error
    return resolved


def _value_references_plugin(value: Any, plugin_id: str) -> bool:
    if isinstance(value, str):
        return value == plugin_id
    if isinstance(value, list):
        return any(_value_references_plugin(item, plugin_id) for item in value)
    if isinstance(value, dict):
        return any(_value_references_plugin(item, plugin_id) for item in value.values())
    return False


def _shell_config_references_plugin(
    plugin_id: str,
    environ: Mapping[str, str] | None = None,
) -> bool:
    environment = os.environ if environ is None else environ
    home = environment.get("HOME")
    if not home:
        raise AdapterError("the Omarchy shell configuration is unavailable")
    path = Path(home) / ".config" / "omarchy" / "shell.json"
    if not path.exists():
        return False
    descriptor = -1
    try:
        info = path.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)
            or os.name == "posix"
            and info.st_uid != os.geteuid()
            or not 1 <= info.st_size <= 1024 * 1024
        ):
            raise AdapterError("the Omarchy shell configuration is unsafe")
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        encoded = os.read(descriptor, info.st_size + 1)
        if len(encoded) != info.st_size or os.fstat(descriptor).st_size != info.st_size:
            raise AdapterError("the Omarchy shell configuration changed during read")
        value = strict_json_loads(encoded.decode("utf-8"))
    except AdapterError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise AdapterError("the Omarchy shell configuration is invalid") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(value, dict) or value.get("version") != 1:
        raise AdapterError("the Omarchy shell configuration version is unsupported")
    return _value_references_plugin(value, plugin_id)


def _run_receiver_command(
    runner: Runner,
    argv: tuple[str, ...],
    *,
    failure: str,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = runner(argv)
    except (OSError, subprocess.SubprocessError) as error:
        raise AdapterError(failure) from error
    if completed.returncode != 0:
        raise AdapterError(failure)
    return completed


def _attempt_receiver_command(runner: Runner, argv: tuple[str, ...]) -> bool:
    """Attempt rollback-only native work without masking the primary failure."""

    try:
        return runner(argv).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _native_plugin_record(
    plugin_id: str,
    *,
    runner: Runner,
    attempts: int = 1,
) -> dict[str, Any] | None:
    for attempt in range(attempts):
        completed = _run_receiver_command(
            runner,
            ("omarchy", "plugin", "list", "--json"),
            failure="Omarchy's native plugin inventory is unavailable",
        )
        try:
            value = strict_json_loads(completed.stdout)
        except (UnicodeError, ValueError) as error:
            raise AdapterError("Omarchy's native plugin inventory is invalid") from error
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise AdapterError("Omarchy's native plugin inventory is invalid")
        selected = [item for item in value if item.get("id") == plugin_id]
        if len(selected) > 1:
            raise AdapterError("Omarchy's native plugin inventory is ambiguous")
        if selected:
            record = selected[0]
            if (
                not isinstance(record.get("enabled"), bool)
                or record.get("firstParty") is not False
                or not isinstance(record.get("kinds"), list)
                or not all(isinstance(kind, str) for kind in record["kinds"])
            ):
                raise AdapterError("Omarchy's native plugin inventory is invalid")
            return record
        if attempt + 1 < attempts:
            time.sleep(0.05)
    return None


def _materialize_installed_bundle(
    bundle: ExactFileBundle,
    destination: Path,
) -> list[dict[str, Any]]:
    created = False
    try:
        if destination.exists() or destination.is_symlink():
            raise AdapterError("the Omarchy plugin id is already installed")
        destination.mkdir(mode=0o700)
        created = True
        for item in bundle.files:
            path = destination.joinpath(*item.path.split("/"))
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            write_new_bytes(path, item.data, mode=int(item.mode, 8))
        return _review_inventory(bundle, destination)
    except (AdapterError, ContractError, OSError, ValueError) as error:
        if created:
            shutil.rmtree(destination, ignore_errors=True)
        if isinstance(error, AdapterError):
            raise
        raise AdapterError("managed Omarchy plugin could not be installed safely") from error


def _signed_receiver_record(
    payload: dict[str, Any],
    *,
    signer: InstallationSigner,
) -> dict[str, Any]:
    return {
        **payload,
        "signature": {
            "algorithm": "ed25519",
            "keyId": signer.key_id,
            "value": signer.sign(canonical_json_bytes(payload)),
        },
    }


def _write_receiver_record(
    root: Path,
    filename: str,
    payload: dict[str, Any],
    *,
    signer: InstallationSigner,
) -> tuple[Path, dict[str, Any]]:
    state = _signed_receiver_record(payload, signer=signer)
    encoded = canonical_json_bytes(state) + b"\n"
    if len(encoded) > _MAX_RECEIVER_STATE_BYTES:
        raise AdapterError("managed receiver state exceeds its local limit")
    path = root / filename
    try:
        write_new_bytes(path, encoded, mode=0o600)
    except (ContractError, OSError, ValueError) as error:
        raise AdapterError("managed receiver state could not be saved safely") from error
    return path.resolve(strict=True), state


def _load_receiver_record(
    path: Path,
    *,
    root: Path,
    schema_version: str,
    signer: InstallationSigner,
) -> tuple[Path, dict[str, Any]]:
    selected = Path(path)
    if (
        not selected.is_absolute()
        or selected.parent.resolve(strict=False) != root
        or re.fullmatch(r"[0-9a-f]{64}\.json", selected.name) is None
    ):
        raise AdapterError("managed receiver state path is invalid")
    descriptor = -1
    try:
        before = selected.lstat()
        if (
            stat.S_ISLNK(before.st_mode)
            or not stat.S_ISREG(before.st_mode)
            or os.name == "posix"
            and (before.st_uid != os.geteuid() or stat.S_IMODE(before.st_mode) != 0o600)
            or not 1 <= before.st_size <= _MAX_RECEIVER_STATE_BYTES
        ):
            raise AdapterError("managed receiver state is unsafe")
        descriptor = os.open(selected, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        encoded = os.read(descriptor, before.st_size + 1)
        if len(encoded) != before.st_size or os.fstat(descriptor).st_size != before.st_size:
            raise AdapterError("managed receiver state changed during read")
        state = strict_json_loads(encoded.decode("utf-8"))
    except AdapterError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise AdapterError("managed receiver state is invalid") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(state, dict) or state.get("schemaVersion") != schema_version:
        raise AdapterError("managed receiver state has an unsupported shape")
    signature = state.get("signature")
    if (
        not isinstance(signature, dict)
        or set(signature) != {"algorithm", "keyId", "value"}
        or signature.get("algorithm") != "ed25519"
        or signature.get("keyId") != signer.key_id
        or not isinstance(signature.get("value"), str)
        or _SIGNATURE.fullmatch(signature["value"]) is None
    ):
        raise AdapterError("managed receiver state is unbound")
    payload = {key: value for key, value in state.items() if key != "signature"}
    try:
        Ed25519PublicKey.from_public_bytes(signer.public_bytes()).verify(
            urlsafe_b64decode(signature["value"] + "=="),
            canonical_json_bytes(payload),
        )
    except (InvalidSignature, TypeError, ValueError) as error:
        raise AdapterError("managed receiver state signature is invalid") from error
    return selected.resolve(strict=True), state


def _utc_timestamp(occurred_at: datetime | None = None) -> str:
    timestamp = occurred_at or datetime.now(tz=UTC)
    if timestamp.tzinfo is None:
        raise AdapterError("receiver event time must include an offset")
    return timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _installation_result(path: Path, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "limitless.omarchy-artifact-install-result/0.1",
        "decisionRef": state["decisionRef"],
        "capabilityId": state["capabilityId"],
        "revision": state["revision"],
        "digest": state["bundleDigest"],
        "pluginId": state["pluginId"],
        "pluginKinds": state["pluginKinds"],
        "installPath": state["installPath"],
        "installationStatePath": str(path),
        "installationDisposition": "installed-disabled",
        "enabled": False,
        "nextAction": "explicit-owner-enablement",
    }


def install_managed_plugin_disabled(
    state_path: Path,
    *,
    runner: Runner = _default_runner,
    environ: Mapping[str, str] | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Install reviewed exact bytes while proving Omarchy still marks them disabled."""

    reviewed = prepare_managed_plugin_review(state_path, runner=runner, environ=environ)
    if reviewed["nativeValidation"].get("status") != "valid":
        raise AdapterError("managed Omarchy plugin did not pass native validation")
    try:
        payload = _read_private_staged_bundle(
            Path(reviewed["bundlePath"]),
            digest=reviewed["digest"],
            byte_length=Path(reviewed["bundlePath"]).stat().st_size,
        )
        bundle = parse_exact_file_bundle(payload)
    except (ExactFileBundleError, OSError, ValueError) as error:
        raise AdapterError("managed exact bundle installation failed closed") from error
    manifest = _bundle_plugin_manifest(bundle)
    plugin_id = manifest["id"]
    plugins_root = _omarchy_plugins_root(environ)
    destination = plugins_root / plugin_id
    receiver_root = _private_receiver_root("receiver-installations", environ)
    filename = reviewed["digest"].removeprefix("sha256:") + ".json"
    installation_path = receiver_root / filename
    try:
        connector = activated_service_connector()
        signer, publisher = installation_publisher_authority(service_id=connector.profile.service_id)
    except (
        ContractError,
        OfficialServiceActivationError,
        ServiceIdentityError,
        OSError,
        ValueError,
    ) as error:
        raise AdapterError("managed receiver authority is unavailable") from error

    if installation_path.exists():
        selected, state = _load_receiver_record(
            installation_path,
            root=receiver_root,
            schema_version=_RECEIVER_INSTALLATION_SCHEMA_VERSION,
            signer=signer,
        )
        if (
            state.get("serviceId") != connector.profile.service_id
            or state.get("publisher")
            != {key: publisher[key] for key in ("publisherId", "authorityId", "keyId", "generation")}
            or state.get("bundleDigest") != reviewed["digest"]
            or state.get("pluginId") != plugin_id
            or state.get("installPath") != str(destination)
            or state.get("pluginKinds") != manifest["kinds"]
        ):
            raise AdapterError("managed receiver installation state conflicts with the exact bundle")
        _review_inventory(bundle, destination)
        record = _native_plugin_record(plugin_id, runner=runner)
        if record is None or record["enabled"] is not False or _shell_config_references_plugin(plugin_id, environ):
            raise AdapterError("the managed Omarchy plugin is no longer installed disabled")
        return _installation_result(selected, state)

    if destination.exists() or destination.is_symlink():
        raise AdapterError("the Omarchy plugin id is already installed")
    if _shell_config_references_plugin(plugin_id, environ):
        raise AdapterError("the Omarchy plugin id is already enabled in shell configuration")

    created = False
    try:
        inventory = _materialize_installed_bundle(bundle, destination)
        created = True
        _run_receiver_command(
            runner,
            ("omarchy-shell", "shell", "rescanPlugins"),
            failure="Omarchy could not discover the installed plugin",
        )
        record = _native_plugin_record(plugin_id, runner=runner, attempts=40)
        if (
            record is None
            or record["enabled"] is not False
            or sorted(record["kinds"]) != manifest["kinds"]
            or _shell_config_references_plugin(plugin_id, environ)
        ):
            raise AdapterError("Omarchy did not confirm a disabled exact installation")
        payload = {
            "schemaVersion": _RECEIVER_INSTALLATION_SCHEMA_VERSION,
            "serviceId": connector.profile.service_id,
            "publisher": {key: publisher[key] for key in ("publisherId", "authorityId", "keyId", "generation")},
            "decisionRef": reviewed["decisionRef"],
            "capabilityId": reviewed["capabilityId"],
            "revision": reviewed["revision"],
            "bundleDigest": reviewed["digest"],
            "pluginId": plugin_id,
            "pluginKinds": manifest["kinds"],
            "installPath": str(destination),
            "inventoryDigest": sha256_bytes(canonical_json_bytes(inventory)),
            "installedAt": _utc_timestamp(occurred_at),
            "installationDisposition": "installed-disabled",
        }
        selected, state = _write_receiver_record(
            receiver_root,
            filename,
            payload,
            signer=signer,
        )
        return _installation_result(selected, state)
    except (AdapterError, ServiceIdentityError):
        if created:
            _attempt_receiver_command(runner, ("omarchy", "plugin", "disable", plugin_id))
            shutil.rmtree(destination, ignore_errors=True)
            _attempt_receiver_command(runner, ("omarchy-shell", "shell", "rescanPlugins"))
        raise


def _adoption_result(path: Path, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "limitless.omarchy-artifact-adoption-result/0.1",
        "decisionRef": state["decisionRef"],
        "capabilityId": state["capabilityId"],
        "revision": state["revision"],
        "digest": state["bundleDigest"],
        "pluginId": state["pluginId"],
        "installPath": state["installPath"],
        "adoptionReceiptPath": str(path),
        "installationDisposition": "enabled",
        "enabled": True,
        "observedInvocation": state["observedInvocation"],
    }


def enable_managed_plugin(
    installation_state_path: Path,
    *,
    runner: Runner = _default_runner,
    environ: Mapping[str, str] | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Explicitly enable one signed installation and bind adoption to native evidence."""

    receiver_root = _private_receiver_root("receiver-installations", environ)
    adoption_root = _private_receiver_root("receiver-adoptions", environ)
    try:
        connector = activated_service_connector()
        signer, publisher = installation_publisher_authority(service_id=connector.profile.service_id)
    except (
        ContractError,
        OfficialServiceActivationError,
        ServiceIdentityError,
        OSError,
        ValueError,
    ) as error:
        raise AdapterError("managed receiver authority is unavailable") from error
    selected_installation, installation = _load_receiver_record(
        installation_state_path,
        root=receiver_root,
        schema_version=_RECEIVER_INSTALLATION_SCHEMA_VERSION,
        signer=signer,
    )
    expected_publisher = {key: publisher[key] for key in ("publisherId", "authorityId", "keyId", "generation")}
    plugin_id = installation.get("pluginId")
    kinds = installation.get("pluginKinds")
    install_path = installation.get("installPath")
    digest = installation.get("bundleDigest")
    if (
        installation.get("serviceId") != connector.profile.service_id
        or installation.get("publisher") != expected_publisher
        or not isinstance(plugin_id, str)
        or _PLUGIN_ID.fullmatch(plugin_id) is None
        or not isinstance(kinds, list)
        or not kinds
        or "bar" in kinds
        or not all(isinstance(kind, str) and kind in _PLUGIN_KINDS for kind in kinds)
        or not isinstance(install_path, str)
        or not Path(install_path).is_absolute()
        or not isinstance(digest, str)
        or _DIGEST.fullmatch(digest) is None
    ):
        raise AdapterError("managed receiver installation state is invalid")
    expected_install_path = _omarchy_plugins_root(environ) / plugin_id
    if Path(install_path) != expected_install_path:
        raise AdapterError("managed receiver installation path is invalid")
    staged_bundle_path = _private_staging_root(environ) / (digest.removeprefix("sha256:") + ".bin")
    try:
        bundle_payload = _read_private_staged_bundle(
            staged_bundle_path,
            digest=digest,
            byte_length=staged_bundle_path.stat().st_size,
        )
        bundle = parse_exact_file_bundle(bundle_payload)
        manifest = _bundle_plugin_manifest(bundle)
        inventory = _review_inventory(bundle, expected_install_path)
    except (ExactFileBundleError, OSError, ValueError) as error:
        raise AdapterError("managed receiver installation no longer matches its exact bundle") from error
    if (
        manifest["id"] != plugin_id
        or manifest["kinds"] != sorted(kinds)
        or installation.get("inventoryDigest") != sha256_bytes(canonical_json_bytes(inventory))
    ):
        raise AdapterError("managed receiver installation no longer matches its exact bundle")

    adoption_path = adoption_root / (digest.removeprefix("sha256:") + ".json")
    if adoption_path.exists():
        selected, state = _load_receiver_record(
            adoption_path,
            root=adoption_root,
            schema_version=_RECEIVER_ADOPTION_SCHEMA_VERSION,
            signer=signer,
        )
        record = _native_plugin_record(plugin_id, runner=runner)
        if (
            state.get("installationStateDigest") != sha256_file(selected_installation)
            or state.get("pluginId") != plugin_id
            or record is None
            or record["enabled"] is not True
        ):
            raise AdapterError("managed receiver adoption state is no longer valid")
        return _adoption_result(selected, state)

    record = _native_plugin_record(plugin_id, runner=runner)
    if record is None or record["enabled"] is not False or sorted(record["kinds"]) != sorted(kinds):
        raise AdapterError("managed Omarchy plugin is not awaiting explicit enablement")
    if _shell_config_references_plugin(plugin_id, environ):
        raise AdapterError("managed Omarchy plugin enablement state is ambiguous")
    native_validation = validate_plugin(expected_install_path, runner=runner)
    if native_validation["status"] != "valid":
        raise AdapterError("installed Omarchy plugin no longer passes native validation")

    enabled = False
    try:
        _run_receiver_command(
            runner,
            ("omarchy", "plugin", "enable", plugin_id),
            failure="Omarchy did not enable the reviewed plugin",
        )
        enabled = True
        record = _native_plugin_record(plugin_id, runner=runner, attempts=40)
        if record is None or record["enabled"] is not True or sorted(record["kinds"]) != sorted(kinds):
            raise AdapterError("Omarchy did not confirm reviewed plugin enablement")
        if not _shell_config_references_plugin(plugin_id, environ):
            raise AdapterError("Omarchy did not persist reviewed plugin enablement")

        if _SUMMONABLE_PLUGIN_KINDS.intersection(kinds):
            observed = _run_receiver_command(
                runner,
                ("omarchy-shell", "shell", "summon", plugin_id, "{}"),
                failure="Omarchy did not confirm reviewed plugin invocation",
            )
            if observed.stdout.strip() != "ok":
                raise AdapterError("Omarchy did not confirm reviewed plugin invocation")
            evidence_kind = "omarchy-shell-summon"
        else:
            evidence_kind = "omarchy-shell-enabled-runtime"

        evidence = {
            "observed": True,
            "kind": evidence_kind,
            "pluginId": plugin_id,
            "nativeRecordDigest": sha256_bytes(canonical_json_bytes(record)),
        }
        payload = {
            "schemaVersion": _RECEIVER_ADOPTION_SCHEMA_VERSION,
            "serviceId": connector.profile.service_id,
            "publisher": expected_publisher,
            "decisionRef": installation["decisionRef"],
            "capabilityId": installation["capabilityId"],
            "revision": installation["revision"],
            "bundleDigest": digest,
            "pluginId": plugin_id,
            "installPath": install_path,
            "installationStateDigest": sha256_file(selected_installation),
            "enabledAt": _utc_timestamp(occurred_at),
            "installationDisposition": "enabled",
            "observedInvocation": evidence,
        }
        selected, state = _write_receiver_record(
            adoption_root,
            adoption_path.name,
            payload,
            signer=signer,
        )
        return _adoption_result(selected, state)
    except (AdapterError, ServiceIdentityError):
        if enabled:
            _attempt_receiver_command(runner, ("omarchy", "plugin", "disable", plugin_id))
        raise


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
