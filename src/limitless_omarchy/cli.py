"""Command-line entry point for the local Omarchy integration."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from limitless_library.contracts import strict_json_loads

from .activity import activity_summary, record_agents, record_lifecycle, record_query, record_service
from .adapter import AdapterError, query_local_catalog, seal_local_capsule, status, validate_plugin
from .agent_connection import (
    AgentConnectionError,
    agent_connection_status,
    disconnect_agent_connections,
    reconcile_agent_connections,
)
from .contributions import (
    ContributionError,
    schedule_contribution_sync,
    sync_contributions,
    transition_contribution,
)
from .drafts import DraftError, list_drafts, register_method
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
from .settings import SettingsError, load_settings, save_settings, settings_result

MAX_SERVICE_INPUT_BYTES = 8 * 1024
_REASON_CODE = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_DRAFT_REF = re.compile(r"^draft:[0-9A-HJKMNP-TV-Z]{26}$")


def _bounded_json_input(label: str, *, maximum: int = MAX_SERVICE_INPUT_BYTES) -> Any:
    raw = sys.stdin.buffer.readline(maximum + 1)
    if not raw or len(raw) > maximum or not raw.endswith(b"\n"):
        raise AdapterError(f"{label} must be one bounded JSON line on stdin")
    try:
        return strict_json_loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise AdapterError(f"{label} is invalid") from error


def _print(value: dict[str, Any]) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _contribution_transition_input() -> dict[str, Any]:
    value = _bounded_json_input("method sharing transition")
    fields = {"schemaVersion", "draftRef", "destination", "publicPolicyDigest"}
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != "limitless.method-sharing-transition-input/0.1"
        or not isinstance(value.get("draftRef"), str)
        or _DRAFT_REF.fullmatch(value["draftRef"]) is None
        or value.get("destination") not in {"off", "local", "circle", "organization", "public"}
    ):
        raise AdapterError("method sharing transition has an unsupported shape")
    digest = value.get("publicPolicyDigest")
    if digest is not None and (not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None):
        raise AdapterError("method sharing policy digest is invalid")
    return value


def _activity_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--activity-path",
        type=Path,
        help="plugin-owned aggregate activity file; omitted for uncounted lower-level use",
    )


def _local_query_input() -> str:
    value = _bounded_json_input("local query input")
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "objective"}
        or value.get("schemaVersion") != "limitless.omarchy-local-query-input/0.1"
    ):
        raise AdapterError("local query input has an unsupported shape")
    objective = value.get("objective")
    if not isinstance(objective, str) or not objective.strip() or len(objective.strip()) > 480 or "\x00" in objective:
        raise AdapterError("local query objective is invalid")
    return objective.strip()


def _service_query_input() -> tuple[str, str | None]:
    value = _bounded_json_input("service query input")
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
    value = _bounded_json_input("publication input")
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
    value = _bounded_json_input("artifact stage input")
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
    value = _bounded_json_input("artifact review input")
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
    value = _bounded_json_input("artifact installation input")
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
    value = _bounded_json_input("artifact enablement input")
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
    panel_state = subparsers.add_parser("panel-state", help="load the complete local panel projection in one process")
    panel_state.add_argument("--state-dir", type=Path, required=True)
    panel_state.add_argument("--settings-path", type=Path, required=True)
    panel_state.add_argument("--drafts-path", type=Path, required=True)
    panel_state.add_argument("--activity-path", type=Path, required=True)
    panel_state.add_argument("--omarchy-release")

    query = subparsers.add_parser("query", help="query a local catalog before a customization")
    query.add_argument("--catalog", type=Path, required=True)
    query.add_argument("--omarchy-release", help="explicit receiver release for compatibility matching")
    query.add_argument("--task-kind", choices=["omarchy-customization"], default="omarchy-customization")
    query.add_argument("--requested-use", choices=["adopt", "instantiate"], default="adopt")
    query.add_argument("--tenant-scope", choices=["private"], default="private")
    _activity_argument(query)

    seal = subparsers.add_parser("seal-capsule", help="seal an owner-provided local Work Capsule draft")
    seal.add_argument("--draft", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    seal.add_argument("--root", type=Path, help="exact-component root; defaults to the draft directory")

    validate = subparsers.add_parser("validate-plugin", help="run Omarchy's native plugin validator")
    validate.add_argument("plugin_dir", type=Path, nargs="?", default=Path("."))

    mcp = subparsers.add_parser("mcp", help="serve the local Omarchy-aware MCP tool over stdio")
    mcp.add_argument("--catalog", type=Path, required=True)
    mcp.add_argument("--omarchy-release", help="explicit receiver release for compatibility matching")
    _activity_argument(mcp)
    mcp.add_argument("--settings-path", type=Path)
    mcp.add_argument("--drafts-path", type=Path)

    provider = subparsers.add_parser(
        "provider",
        help="explicitly serve the generic local Limitless MCP tool over stdio",
    )
    provider.add_argument("--catalog", type=Path, required=True)
    _activity_argument(provider)

    agent_status = subparsers.add_parser(
        "agent-status",
        help="inspect the Omarchy-default agent and plugin-owned MCP connections",
    )
    agent_status.add_argument("--state-dir", type=Path, required=True)
    _activity_argument(agent_status)

    agent_reconcile = subparsers.add_parser(
        "agent-reconcile",
        help="connect Omarchy's default agent and selected additional agents to local MCP",
    )
    agent_reconcile.add_argument("--state-dir", type=Path, required=True)
    agent_reconcile.add_argument("--runtime-cli", type=Path, required=True)
    agent_reconcile.add_argument("--catalog", type=Path, required=True)
    agent_reconcile.add_argument("--additional-agent", action="append", default=[])
    agent_reconcile.add_argument("--settings-path", type=Path)
    agent_reconcile.add_argument("--drafts-path", type=Path)
    _activity_argument(agent_reconcile)

    agent_disconnect = subparsers.add_parser(
        "agent-disconnect",
        help="remove only plugin-owned local MCP connections",
    )
    agent_disconnect.add_argument("--state-dir", type=Path, required=True)
    _activity_argument(agent_disconnect)

    service_activate = subparsers.add_parser(
        "service-activate",
        help="enable the release-pinned official service after verifying its authority",
    )
    service_activate.add_argument("--drafts-path", type=Path)
    _activity_argument(service_activate)

    service_inspect = subparsers.add_parser(
        "service-inspect",
        help="verify the enabled official service without sending a task",
    )
    service_inspect.add_argument(
        "--profile",
        type=Path,
        help="advanced: inspect an explicit alternate service profile",
    )
    _activity_argument(service_inspect)

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
    _activity_argument(service_query)
    service_publication = subparsers.add_parser(
        "service-publication",
        help="publish, inspect, or withdraw one explicitly selected contribution",
    )
    _activity_argument(service_publication)
    service_artifact_stage = subparsers.add_parser(
        "service-artifact-stage",
        help="redeem one locally bound exact-artifact continuation into safe staging",
    )
    _activity_argument(service_artifact_stage)
    service_artifact_review = subparsers.add_parser(
        "service-artifact-review",
        help="materialize and natively validate one staged exact Omarchy bundle",
    )
    _activity_argument(service_artifact_review)
    service_artifact_install = subparsers.add_parser(
        "service-artifact-install",
        help="install one reviewed exact Omarchy bundle while keeping it disabled",
    )
    _activity_argument(service_artifact_install)
    service_artifact_enable = subparsers.add_parser(
        "service-artifact-enable",
        help="explicitly enable one signed installation and capture observed use",
    )
    _activity_argument(service_artifact_enable)
    stats = subparsers.add_parser("stats", help="show private aggregate plugin activity")
    stats.add_argument("--activity-path", type=Path, required=True)
    settings_show = subparsers.add_parser("settings-show", help="show owner-controlled local settings")
    settings_show.add_argument("--settings-path", type=Path, required=True)
    settings_apply = subparsers.add_parser("settings-apply", help="validate and save owner-controlled local settings")
    settings_apply.add_argument("--settings-path", type=Path, required=True)
    draft_list = subparsers.add_parser("draft-list", help="list locally registered reusable-method candidates")
    draft_list.add_argument("--drafts-path", type=Path, required=True)
    draft_list.add_argument("--limit", type=int, default=12)
    register = subparsers.add_parser("register-method", help="register one concise reusable method from bounded stdin")
    register.add_argument("--drafts-path", type=Path, required=True)
    register.add_argument("--catalog", type=Path, required=True)
    register.add_argument("--settings-path", type=Path, required=True)
    _activity_argument(register)
    contribution_sync = subparsers.add_parser(
        "contribution-sync",
        help="advance queued sharing work without blocking method registration",
    )
    contribution_sync.add_argument("--drafts-path", type=Path, required=True)
    contribution_sync.add_argument("--limit", type=int, default=8)
    _activity_argument(contribution_sync)
    contribution_transition = subparsers.add_parser(
        "contribution-transition",
        help="move one registered method to an owner-selected sharing destination",
    )
    contribution_transition.add_argument("--drafts-path", type=Path, required=True)
    _activity_argument(contribution_transition)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "status":
            _print(status(omarchy_release=args.omarchy_release))
        elif args.command == "panel-state":
            schedule_contribution_sync(args.drafts_path, activity_path=args.activity_path)
            _print(
                {
                    "schemaVersion": "limitless.omarchy-panel-state/0.1",
                    "status": status(omarchy_release=args.omarchy_release),
                    "settings": settings_result(load_settings(args.settings_path), saved=False),
                    "drafts": list_drafts(args.drafts_path),
                    "agents": agent_connection_status(args.state_dir),
                    "stats": activity_summary(args.activity_path),
                }
            )
        elif args.command == "query":
            result = query_local_catalog(
                args.catalog,
                objective=_local_query_input(),
                omarchy_release=args.omarchy_release,
                task_kind=args.task_kind,
                requested_use=args.requested_use,
                tenant_scope=args.tenant_scope,
            )
            record_query(args.activity_path, result, channel="local")
            _print(result)
        elif args.command == "seal-capsule":
            _print(seal_local_capsule(args.draft, args.output, root=args.root))
        elif args.command == "validate-plugin":
            result = validate_plugin(args.plugin_dir)
            _print(result)
            if result["status"] != "valid":
                raise SystemExit(1)
        elif args.command == "mcp":
            serve(
                args.catalog,
                omarchy_release=args.omarchy_release,
                activity_path=args.activity_path,
                settings_path=args.settings_path,
                drafts_path=args.drafts_path,
            )
        elif args.command == "provider":
            serve_general_provider(args.catalog, activity_path=args.activity_path)
        elif args.command == "agent-status":
            result = agent_connection_status(args.state_dir)
            record_agents(args.activity_path, result)
            _print(result)
        elif args.command == "agent-reconcile":
            result = reconcile_agent_connections(
                args.state_dir,
                runtime_cli=args.runtime_cli,
                catalog=args.catalog,
                additional_agents=args.additional_agent,
                activity_path=args.activity_path,
                settings_path=args.settings_path,
                drafts_path=args.drafts_path,
            )
            record_agents(args.activity_path, result)
            _print(result)
        elif args.command == "agent-disconnect":
            result = disconnect_agent_connections(args.state_dir)
            record_agents(args.activity_path, result)
            _print(result)
        elif args.command == "service-activate":
            result = activate_managed_service()
            record_service(args.activity_path, connected=True)
            if args.drafts_path is not None:
                schedule_contribution_sync(args.drafts_path, activity_path=args.activity_path)
            _print(result)
        elif args.command == "service-inspect":
            result = inspect_managed_service(args.profile)
            record_service(args.activity_path, connected=True)
            _print(result)
        elif args.command == "service-query":
            objective, access_token = _service_query_input()
            result = query_managed_service(
                args.profile,
                objective=objective,
                access_token=access_token,
                omarchy_release=args.omarchy_release,
                request_id=args.request_id,
            )
            record_query(args.activity_path, result, channel="service")
            record_service(
                args.activity_path,
                connected=str(result.get("reason") or "") != "service-unavailable-local-still-available",
            )
            _print(result)
        elif args.command == "service-publication":
            publication = _service_publication_input()
            result = manage_publication(**publication)
            if publication["operation"] == "publish":
                record_lifecycle(args.activity_path, "publication")
            elif publication["operation"] == "revoke":
                record_lifecycle(args.activity_path, "withdrawal")
            _print(result)
        elif args.command == "service-artifact-stage":
            _print(stage_managed_artifact(_service_artifact_stage_input()))
        elif args.command == "service-artifact-review":
            result = prepare_managed_plugin_review(_service_artifact_review_input())
            record_lifecycle(args.activity_path, "review")
            _print(result)
        elif args.command == "service-artifact-install":
            result = install_managed_plugin_disabled(_service_artifact_install_input())
            record_lifecycle(args.activity_path, "install")
            _print(result)
        elif args.command == "service-artifact-enable":
            result = enable_managed_plugin(_service_artifact_enable_input())
            record_lifecycle(args.activity_path, "adoption")
            _print(result)
        elif args.command == "stats":
            _print(activity_summary(args.activity_path))
        elif args.command == "settings-show":
            _print(settings_result(load_settings(args.settings_path), saved=False))
        elif args.command == "settings-apply":
            value = _bounded_json_input("owner settings input")
            _print(settings_result(save_settings(args.settings_path, value), saved=True))
        elif args.command == "draft-list":
            _print(list_drafts(args.drafts_path, limit=args.limit))
        elif args.command == "register-method":
            result = register_method(
                args.drafts_path,
                args.catalog,
                args.settings_path,
                _bounded_json_input("method registration input"),
            )
            if result["status"] == "registered":
                record_lifecycle(args.activity_path, "draft")
            if result["destination"] == "public" and result["status"] != "disabled":
                schedule_contribution_sync(args.drafts_path, activity_path=args.activity_path)
            _print(result)
        elif args.command == "contribution-sync":
            result = sync_contributions(args.drafts_path, limit=args.limit)
            for _index in range(result["published"]):
                record_lifecycle(args.activity_path, "publication")
            for _index in range(result["withdrawn"]):
                record_lifecycle(args.activity_path, "withdrawal")
            _print(result)
        elif args.command == "contribution-transition":
            value = _contribution_transition_input()
            result = transition_contribution(
                args.drafts_path,
                draft_ref=value["draftRef"],
                destination=value["destination"],
                public_policy_digest=value["publicPolicyDigest"],
            )
            if result["status"] in {"queued", "withdrawal-queued"}:
                schedule_contribution_sync(args.drafts_path, activity_path=args.activity_path)
            _print(result)
    except (AdapterError, AgentConnectionError, ContributionError, DraftError, SettingsError) as error:
        print(f"limitless-omarchy: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
