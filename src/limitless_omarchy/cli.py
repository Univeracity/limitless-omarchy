"""Command-line entry point for the local Omarchy integration."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from limitless_library.contracts import strict_json_loads

from .adapter import AdapterError, query_local_catalog, seal_local_capsule, status, validate_plugin
from .agent_connection import (
    AgentConnectionError,
    agent_connection_status,
    disconnect_agent_connections,
    reconcile_agent_connections,
)
from .mcp_server import serve
from .provider import serve_general_provider
from .service import (
    activate_managed_service,
    enable_managed_plugin,
    inspect_managed_service,
    install_managed_plugin_disabled,
    manage_publication,
    prepare_managed_plugin_review,
    query_managed_service,
    stage_managed_artifact,
)

MAX_SERVICE_INPUT_BYTES = 8 * 1024
_REASON_CODE = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _print(value: dict[str, Any]) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _service_query_input() -> tuple[str, str | None]:
    raw = sys.stdin.buffer.readline(MAX_SERVICE_INPUT_BYTES + 1)
    if not raw or len(raw) > MAX_SERVICE_INPUT_BYTES or not raw.endswith(b"\n"):
        raise AdapterError("service query input must be one bounded JSON line on stdin")
    try:
        value = strict_json_loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise AdapterError("service query input is invalid") from error
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "objective",
        "accessToken",
    }:
        raise AdapterError("service query input has an unsupported shape")
    if value["schemaVersion"] != "limitless.omarchy-service-query-input/0.1":
        raise AdapterError("service query input schemaVersion is invalid")
    objective = value["objective"]
    token = value["accessToken"]
    if not isinstance(objective, str) or not objective or len(objective) > 480:
        raise AdapterError("service query objective is invalid")
    if token is not None and (not isinstance(token, str) or len(token) > 4096):
        raise AdapterError("service access token is invalid")
    return objective, token


def _service_publication_input() -> dict[str, Any]:
    raw = sys.stdin.buffer.readline(MAX_SERVICE_INPUT_BYTES + 1)
    if not raw or len(raw) > MAX_SERVICE_INPUT_BYTES or not raw.endswith(b"\n"):
        raise AdapterError("publication input must be one bounded JSON line on stdin")
    try:
        value = strict_json_loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise AdapterError("publication input is invalid") from error
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "operation",
        "draftPath",
        "statePath",
        "acceptedPublicationPolicyDigest",
        "reasonCode",
    }:
        raise AdapterError("publication input has an unsupported shape")
    if value["schemaVersion"] != "limitless.omarchy-publication-input/0.1":
        raise AdapterError("publication input schemaVersion is invalid")
    operation = value["operation"]
    if operation not in {"publish", "status", "revoke"}:
        raise AdapterError("publication operation is invalid")
    paths: dict[str, Path | None] = {}
    for field in ("draftPath", "statePath"):
        configured = value[field]
        if configured is None:
            paths[field] = None
            continue
        if (
            not isinstance(configured, str)
            or not configured
            or len(configured) > 4096
            or "\x00" in configured
            or not Path(configured).is_absolute()
            or ".." in Path(configured).parts
        ):
            raise AdapterError("publication path is invalid")
        paths[field] = Path(configured)
    accepted_digest = value["acceptedPublicationPolicyDigest"]
    reason = value["reasonCode"]
    if accepted_digest is not None and (
        not isinstance(accepted_digest, str) or _DIGEST.fullmatch(accepted_digest) is None
    ):
        raise AdapterError("accepted publication policy digest is invalid")
    if reason is not None and (not isinstance(reason, str) or _REASON_CODE.fullmatch(reason) is None):
        raise AdapterError("publication withdrawal reason is invalid")
    if operation == "publish":
        valid = (
            paths["draftPath"] is not None
            and paths["statePath"] is None
            and reason is None
            and accepted_digest is not None
        )
    elif operation == "status":
        valid = (
            paths["draftPath"] is None and paths["statePath"] is not None and reason is None and accepted_digest is None
        )
    else:
        valid = (
            paths["draftPath"] is None
            and paths["statePath"] is not None
            and reason is not None
            and accepted_digest is None
        )
    if not valid:
        raise AdapterError("publication input is invalid")
    return {
        "operation": operation,
        "draft_path": paths["draftPath"],
        "state_path": paths["statePath"],
        "accepted_publication_policy_digest": accepted_digest,
        "reason_code": reason,
    }


def _service_artifact_stage_input() -> Path:
    raw = sys.stdin.buffer.readline(MAX_SERVICE_INPUT_BYTES + 1)
    if not raw or len(raw) > MAX_SERVICE_INPUT_BYTES or not raw.endswith(b"\n"):
        raise AdapterError("artifact stage input must be one bounded JSON line on stdin")
    try:
        value = strict_json_loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise AdapterError("artifact stage input is invalid") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "handoffStatePath"}
        or value.get("schemaVersion") != "limitless.omarchy-artifact-stage-input/0.1"
    ):
        raise AdapterError("artifact stage input has an unsupported shape")
    configured = value["handoffStatePath"]
    if (
        not isinstance(configured, str)
        or not configured
        or len(configured) > 4096
        or "\x00" in configured
        or not Path(configured).is_absolute()
        or ".." in Path(configured).parts
    ):
        raise AdapterError("artifact handoff state path is invalid")
    return Path(configured)


def _service_artifact_review_input() -> Path:
    raw = sys.stdin.buffer.readline(MAX_SERVICE_INPUT_BYTES + 1)
    if not raw or len(raw) > MAX_SERVICE_INPUT_BYTES or not raw.endswith(b"\n"):
        raise AdapterError("artifact review input must be one bounded JSON line on stdin")
    try:
        value = strict_json_loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise AdapterError("artifact review input is invalid") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "handoffStatePath"}
        or value.get("schemaVersion") != "limitless.omarchy-artifact-review-input/0.1"
    ):
        raise AdapterError("artifact review input has an unsupported shape")
    configured = value["handoffStatePath"]
    if (
        not isinstance(configured, str)
        or not configured
        or len(configured) > 4096
        or "\x00" in configured
        or not Path(configured).is_absolute()
        or ".." in Path(configured).parts
    ):
        raise AdapterError("artifact handoff state path is invalid")
    return Path(configured)


def _service_artifact_install_input() -> Path:
    raw = sys.stdin.buffer.readline(MAX_SERVICE_INPUT_BYTES + 1)
    if not raw or len(raw) > MAX_SERVICE_INPUT_BYTES or not raw.endswith(b"\n"):
        raise AdapterError("artifact installation input must be one bounded JSON line on stdin")
    try:
        value = strict_json_loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise AdapterError("artifact installation input is invalid") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "handoffStatePath"}
        or value.get("schemaVersion") != "limitless.omarchy-artifact-install-input/0.1"
    ):
        raise AdapterError("artifact installation input has an unsupported shape")
    configured = value["handoffStatePath"]
    if (
        not isinstance(configured, str)
        or not configured
        or len(configured) > 4096
        or "\x00" in configured
        or not Path(configured).is_absolute()
        or ".." in Path(configured).parts
    ):
        raise AdapterError("artifact handoff state path is invalid")
    return Path(configured)


def _service_artifact_enable_input() -> Path:
    raw = sys.stdin.buffer.readline(MAX_SERVICE_INPUT_BYTES + 1)
    if not raw or len(raw) > MAX_SERVICE_INPUT_BYTES or not raw.endswith(b"\n"):
        raise AdapterError("artifact enablement input must be one bounded JSON line on stdin")
    try:
        value = strict_json_loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise AdapterError("artifact enablement input is invalid") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "installationStatePath"}
        or value.get("schemaVersion") != "limitless.omarchy-artifact-enable-input/0.1"
    ):
        raise AdapterError("artifact enablement input has an unsupported shape")
    configured = value["installationStatePath"]
    if (
        not isinstance(configured, str)
        or not configured
        or len(configured) > 4096
        or "\x00" in configured
        or not Path(configured).is_absolute()
        or ".." in Path(configured).parts
    ):
        raise AdapterError("artifact installation state path is invalid")
    return Path(configured)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="show the minimal local Omarchy receiver profile")
    status_parser.add_argument("--omarchy-release", help="explicit receiver release for compatibility matching")

    query = subparsers.add_parser("query", help="query a local catalog before a customization")
    query.add_argument("--catalog", type=Path, required=True)
    query.add_argument("--omarchy-release", help="explicit receiver release for compatibility matching")
    query.add_argument("--task-kind", choices=["omarchy-customization"], default="omarchy-customization")
    query.add_argument("--requested-use", choices=["adopt", "instantiate"], default="adopt")
    query.add_argument("--tenant-scope", choices=["private"], default="private")

    seal = subparsers.add_parser("seal-capsule", help="seal an owner-provided local Work Capsule draft")
    seal.add_argument("--draft", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    seal.add_argument("--root", type=Path, help="exact-component root; defaults to the draft directory")

    validate = subparsers.add_parser("validate-plugin", help="run Omarchy's native plugin validator")
    validate.add_argument("plugin_dir", type=Path, nargs="?", default=Path("."))

    mcp = subparsers.add_parser("mcp", help="serve the local Omarchy-aware MCP tool over stdio")
    mcp.add_argument("--catalog", type=Path, required=True)
    mcp.add_argument("--omarchy-release", help="explicit receiver release for compatibility matching")

    provider = subparsers.add_parser(
        "provider",
        help="explicitly serve the generic local Limitless MCP tool over stdio",
    )
    provider.add_argument("--catalog", type=Path, required=True)

    agent_status = subparsers.add_parser(
        "agent-status",
        help="inspect the Omarchy-default agent and plugin-owned MCP connections",
    )
    agent_status.add_argument("--state-dir", type=Path, required=True)

    agent_reconcile = subparsers.add_parser(
        "agent-reconcile",
        help="connect Omarchy's default agent and selected additional agents to local MCP",
    )
    agent_reconcile.add_argument("--state-dir", type=Path, required=True)
    agent_reconcile.add_argument("--runtime-cli", type=Path, required=True)
    agent_reconcile.add_argument("--catalog", type=Path, required=True)
    agent_reconcile.add_argument("--additional-agent", action="append", default=[])

    agent_disconnect = subparsers.add_parser(
        "agent-disconnect",
        help="remove only plugin-owned local MCP connections",
    )
    agent_disconnect.add_argument("--state-dir", type=Path, required=True)

    subparsers.add_parser(
        "service-activate",
        help="enable the release-pinned official service after verifying its authority",
    )

    service_inspect = subparsers.add_parser(
        "service-inspect",
        help="verify the enabled official service without sending a task",
    )
    service_inspect.add_argument(
        "--profile",
        type=Path,
        help="advanced: inspect an explicit alternate service profile",
    )

    service_query = subparsers.add_parser(
        "service-query",
        help="send one explicit Omarchy request read from bounded stdin",
    )
    service_query.add_argument(
        "--profile",
        type=Path,
        help="advanced: query through an explicit alternate service profile",
    )
    service_query.add_argument("--omarchy-release")
    service_query.add_argument("--request-id")
    subparsers.add_parser(
        "service-publication",
        help="publish, inspect, or withdraw one explicitly selected contribution",
    )
    subparsers.add_parser(
        "service-artifact-stage",
        help="redeem one locally bound exact-artifact continuation into safe staging",
    )
    subparsers.add_parser(
        "service-artifact-review",
        help="materialize and natively validate one staged exact Omarchy bundle",
    )
    subparsers.add_parser(
        "service-artifact-install",
        help="install one reviewed exact Omarchy bundle while keeping it disabled",
    )
    subparsers.add_parser(
        "service-artifact-enable",
        help="explicitly enable one signed installation and capture observed use",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "status":
            _print(status(omarchy_release=args.omarchy_release))
        elif args.command == "query":
            _print(
                query_local_catalog(
                    args.catalog,
                    omarchy_release=args.omarchy_release,
                    task_kind=args.task_kind,
                    requested_use=args.requested_use,
                    tenant_scope=args.tenant_scope,
                )
            )
        elif args.command == "seal-capsule":
            _print(seal_local_capsule(args.draft, args.output, root=args.root))
        elif args.command == "validate-plugin":
            result = validate_plugin(args.plugin_dir)
            _print(result)
            if result["status"] != "valid":
                raise SystemExit(1)
        elif args.command == "mcp":
            serve(args.catalog, omarchy_release=args.omarchy_release)
        elif args.command == "provider":
            serve_general_provider(args.catalog)
        elif args.command == "agent-status":
            _print(agent_connection_status(args.state_dir))
        elif args.command == "agent-reconcile":
            _print(
                reconcile_agent_connections(
                    args.state_dir,
                    runtime_cli=args.runtime_cli,
                    catalog=args.catalog,
                    additional_agents=args.additional_agent,
                )
            )
        elif args.command == "agent-disconnect":
            _print(disconnect_agent_connections(args.state_dir))
        elif args.command == "service-activate":
            _print(activate_managed_service())
        elif args.command == "service-inspect":
            _print(inspect_managed_service(args.profile))
        elif args.command == "service-query":
            objective, access_token = _service_query_input()
            _print(
                query_managed_service(
                    args.profile,
                    objective=objective,
                    access_token=access_token,
                    omarchy_release=args.omarchy_release,
                    request_id=args.request_id,
                )
            )
        elif args.command == "service-publication":
            _print(manage_publication(**_service_publication_input()))
        elif args.command == "service-artifact-stage":
            _print(stage_managed_artifact(_service_artifact_stage_input()))
        elif args.command == "service-artifact-review":
            _print(prepare_managed_plugin_review(_service_artifact_review_input()))
        elif args.command == "service-artifact-install":
            _print(install_managed_plugin_disabled(_service_artifact_install_input()))
        elif args.command == "service-artifact-enable":
            _print(enable_managed_plugin(_service_artifact_enable_input()))
    except (AdapterError, AgentConnectionError) as error:
        print(f"limitless-omarchy: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
