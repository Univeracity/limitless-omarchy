"""Explicit managed-service adapter for the Omarchy panel.

Local reuse never imports or calls this module.  The panel reaches it only
after an owner explicitly enables, inspects, or queries the optional service.
"""

from __future__ import annotations

import platform
import re
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any

from limitless_library.contracts import ContractError, load_json
from limitless_library.official_service import (
    OfficialServiceActivationError,
    OfficialServiceUnavailableError,
    activate_official_service,
    activated_service_profile,
)
from limitless_library.service_connector import (
    ServiceConnector,
    ServiceConnectorError,
    ServiceProfile,
    ServiceUnavailableError,
    VerifiedService,
)

from .adapter import AdapterError, Runner, _default_runner, discover_profile

ConnectorFactory = Callable[[ServiceProfile], ServiceConnector]

_NUMERIC_RELEASE = re.compile(r"^[0-9]+(?:\.[0-9]+){0,3}$")


def _service_connector(
    profile_path: Path | None,
    *,
    access_token: str | None,
    connector_factory: ConnectorFactory,
) -> ServiceConnector:
    try:
        if profile_path is None:
            profile = activated_service_profile(access_token=access_token or None)
        else:
            if not profile_path.is_absolute() or not profile_path.is_file():
                raise AdapterError(
                    "service profile must be an absolute path to a readable file"
                )
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


def _managed_result(
    *,
    connector: ServiceConnector,
    local_profile: dict[str, Any],
    query: dict[str, Any],
    decision: dict[str, Any] | None,
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
        "decision": decision,
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
    return _managed_result(
        connector=connector,
        local_profile=local_profile,
        query=query,
        decision=decision,
    )
