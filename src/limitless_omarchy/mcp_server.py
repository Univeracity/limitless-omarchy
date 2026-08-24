"""Bounded local MCP adapter for Omarchy query-before-customization."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from limitless_library.contracts import strict_json_loads
from limitless_library.mcp_protocol import McpToolCallError, McpToolDispatcher, McpToolSession, jsonrpc_error

from .activity import record_lifecycle, record_query
from .adapter import Runner, _default_runner, query_local_catalog
from .contributions import ContributionError, schedule_contribution_sync
from .drafts import DraftError, register_method
from .settings import SettingsError, load_settings

SERVER_NAME = "limitless-omarchy"
SERVER_VERSION = "0.1.0a0"
TOOL_NAME = "omarchy_query_before_customization"
REGISTER_METHOD_TOOL_NAME = "limitless_register_method"
MAX_REQUEST_BYTES = 1024 * 1024
TASK_KINDS = frozenset({"omarchy-customization"})
REQUESTED_USES = frozenset({"adopt", "instantiate"})
TENANT_SCOPES = frozenset({"private"})
INSTRUCTIONS = "Before material Omarchy customization, query this local tool with the intended change."


def _tool() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "title": "Query before Omarchy customization",
        "description": "Select one locally eligible component or source-free method, or safely abstain.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["objective"],
            "properties": {
                "objective": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 480,
                    "description": "A concise description of the change already in context.",
                },
                "taskKind": {
                    "type": "string",
                    "enum": sorted(TASK_KINDS),
                    "default": "omarchy-customization",
                },
                "requestedUse": {"type": "string", "enum": sorted(REQUESTED_USES), "default": "adopt"},
                "tenantScope": {"type": "string", "enum": sorted(TENANT_SCOPES), "default": "private"},
                "omarchyRelease": {
                    "type": "string",
                    "pattern": "^[A-Za-z0-9][A-Za-z0-9._+-]{0,99}$",
                },
            },
        },
        "outputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["schemaVersion", "mode", "disposition", "reason", "profile", "request", "decision"],
            "properties": {
                "schemaVersion": {"const": "limitless.omarchy-result/0.1"},
                "mode": {"const": "local-only"},
                "disposition": {"enum": ["exact-component", "source-free-method", "abstain"]},
                "reason": {"type": "string"},
                "profile": {"type": "object"},
                "request": {"type": "object"},
                "decision": {"oneOf": [{"type": "object"}, {"type": "null"}]},
            },
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    }


def _register_method_tool() -> dict[str, Any]:
    compact_text_or_list = {
        "oneOf": [
            {"type": "string", "minLength": 1, "maxLength": 1200},
            {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1, "maxLength": 1200},
            },
        ]
    }
    return {
        "name": REGISTER_METHOD_TOOL_NAME,
        "title": "Register a reusable method",
        "description": "Save one concise method locally; optional references preserve where the idea came from.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "steps"],
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 160},
                "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
                "steps": compact_text_or_list,
                "verify": {
                    "oneOf": [
                        {"type": "string", "minLength": 1, "maxLength": 1200},
                        {
                            "type": "array",
                            "maxItems": 12,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1, "maxLength": 1200},
                        },
                    ]
                },
                "sources": {
                    "oneOf": [
                        {"type": "string", "minLength": 1, "maxLength": 512},
                        {
                            "type": "array",
                            "maxItems": 8,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1, "maxLength": 512},
                        },
                    ]
                },
                "taskKind": {
                    "type": "string",
                    "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$",
                    "default": "omarchy-customization",
                },
                "supersedes": {"type": "string", "pattern": "^draft:[0-9A-HJKMNP-TV-Z]{26}$"},
            },
        },
        "outputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["schemaVersion", "status", "draftRef", "destination"],
            "properties": {
                "schemaVersion": {"const": "limitless.method-registration-result/0.1"},
                "status": {"enum": ["registered", "duplicate", "disabled"]},
                "draftRef": {
                    "oneOf": [
                        {"type": "string", "pattern": "^draft:[0-9A-HJKMNP-TV-Z]{26}$"},
                        {"type": "null"},
                    ]
                },
                "destination": {"enum": ["off", "local", "circle", "organization", "public"]},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def _instructions(settings_path: Path | None) -> str:
    suffix = " It derives a minimal receiver profile and returns one component, method, or abstention."
    if settings_path is None:
        return INSTRUCTIONS + suffix
    try:
        settings = load_settings(settings_path)
    except SettingsError:
        return INSTRUCTIONS + suffix + " Method registration is unavailable until owner settings can be read."
    mode = settings["contributionMode"]
    destination = settings["defaultDestination"]
    if destination == "off":
        registration = " Method registration is disabled by the owner."
    elif mode == "manual":
        registration = " Register a method only when the user explicitly asks."
    elif mode == "automatic":
        registration = (
            " Register a reusable method when it is created; the saved owner policy controls its destination."
        )
    else:
        registration = " Register a concise method when it is likely to save meaningful future work."
    return INSTRUCTIONS + suffix + registration


def _argument(value: dict[str, Any], key: str, default: str, *, maximum: int = 200) -> str:
    candidate = value.get(key, default)
    if not isinstance(candidate, str) or not candidate or len(candidate) > maximum:
        raise McpToolCallError(f"{key} must be a non-empty string no longer than {maximum} characters")
    return candidate


def _enum_argument(value: dict[str, Any], key: str, default: str, permitted: frozenset[str]) -> str:
    candidate = _argument(value, key, default)
    if candidate not in permitted:
        allowed = ", ".join(sorted(permitted))
        raise McpToolCallError(f"{key} must be one of: {allowed}")
    return candidate


def _dispatcher(
    catalog: Path,
    *,
    omarchy_release: str | None,
    runner: Runner,
    activity_path: Path | None = None,
    settings_path: Path | None = None,
    drafts_path: Path | None = None,
) -> McpToolDispatcher:
    def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == REGISTER_METHOD_TOOL_NAME:
            if settings_path is None or drafts_path is None:
                raise McpToolCallError("method registration is not configured")
            try:
                result = register_method(drafts_path, catalog, settings_path, arguments)
                if result["status"] == "registered":
                    record_lifecycle(activity_path, "draft")
                if result["destination"] == "public" and result["status"] != "disabled":
                    schedule_contribution_sync(drafts_path, activity_path=activity_path)
                return result
            except (ContributionError, DraftError) as error:
                raise McpToolCallError(str(error)) from error
        if name != TOOL_NAME:
            raise McpToolCallError("tool is not available")
        permitted = {"objective", "taskKind", "requestedUse", "tenantScope", "omarchyRelease"}
        if not set(arguments).issubset(permitted):
            raise McpToolCallError("tool arguments contain an unsupported field")
        release = _argument(arguments, "omarchyRelease", omarchy_release or "unknown", maximum=100)
        try:
            result = query_local_catalog(
                catalog,
                objective=_argument(arguments, "objective", "", maximum=480),
                omarchy_release=release,
                task_kind=_enum_argument(arguments, "taskKind", "omarchy-customization", TASK_KINDS),
                requested_use=_enum_argument(arguments, "requestedUse", "adopt", REQUESTED_USES),
                tenant_scope=_enum_argument(arguments, "tenantScope", "private", TENANT_SCOPES),
                runner=runner,
            )
            record_query(activity_path, result, channel="local")
            if drafts_path is not None:
                try:
                    schedule_contribution_sync(drafts_path, activity_path=activity_path)
                except ContributionError:
                    pass
            return result
        except ValueError as error:
            raise McpToolCallError(str(error)) from error

    return McpToolDispatcher(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        instructions=_instructions(settings_path),
        tools=[_tool(), _register_method_tool()],
        call_tool=call_tool,
        cache_scope="private",
    )


def handle_message(
    catalog: Path,
    message: dict[str, Any],
    *,
    omarchy_release: str | None = None,
    runner: Runner = _default_runner,
    activity_path: Path | None = None,
    settings_path: Path | None = None,
    drafts_path: Path | None = None,
) -> dict[str, Any] | None:
    """Handle one stateless MCP message for embedding and tests."""

    return _dispatcher(
        catalog,
        omarchy_release=omarchy_release,
        runner=runner,
        activity_path=activity_path,
        settings_path=settings_path,
        drafts_path=drafts_path,
    ).handle(message)


def _bounded_lines(stream: Any) -> Iterator[tuple[str | None, str | None]]:
    while True:
        raw = stream.readline(MAX_REQUEST_BYTES + 1)
        if not raw:
            return
        if len(raw) > MAX_REQUEST_BYTES or (len(raw) == MAX_REQUEST_BYTES and not raw.endswith(b"\n")):
            while raw and not raw.endswith(b"\n"):
                raw = stream.readline(MAX_REQUEST_BYTES + 1)
            yield None, f"MCP request exceeds {MAX_REQUEST_BYTES} bytes"
            continue
        try:
            yield raw.decode("utf-8"), None
        except UnicodeDecodeError:
            yield None, "MCP request is not UTF-8 JSON"


def serve(
    catalog: Path,
    *,
    omarchy_release: str | None = None,
    activity_path: Path | None = None,
    settings_path: Path | None = None,
    drafts_path: Path | None = None,
) -> None:
    """Run the local stdio MCP server."""

    session = McpToolSession(
        _dispatcher(
            catalog,
            omarchy_release=omarchy_release,
            runner=_default_runner,
            activity_path=activity_path,
            settings_path=settings_path,
            drafts_path=drafts_path,
        )
    )
    for line, framing_error in _bounded_lines(sys.stdin.buffer):
        if framing_error:
            response = jsonrpc_error(None, -32700, framing_error)
        else:
            try:
                message = strict_json_loads(line)
                if not isinstance(message, dict):
                    raise TypeError("JSON-RPC message must be an object")
                response = session.handle(message)
            except (TypeError, ValueError) as error:
                response = jsonrpc_error(None, -32700, str(error))
        if response is not None:
            print(json.dumps(response, sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--omarchy-release")
    parser.add_argument("--activity-path", type=Path)
    parser.add_argument("--settings-path", type=Path)
    parser.add_argument("--drafts-path", type=Path)
    args = parser.parse_args()
    serve(
        args.catalog,
        omarchy_release=args.omarchy_release,
        activity_path=args.activity_path,
        settings_path=args.settings_path,
        drafts_path=args.drafts_path,
    )


if __name__ == "__main__":
    main()
