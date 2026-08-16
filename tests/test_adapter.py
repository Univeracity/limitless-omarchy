from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from limitless_library.catalog import seal_capsule
from limitless_library.mcp_protocol import modern_metadata

from limitless_omarchy.adapter import (
    AdapterError,
    build_query,
    discover_profile,
    query_local_catalog,
    seal_local_capsule,
    status,
    validate_plugin,
)
from limitless_omarchy.mcp_server import TOOL_NAME, handle_message


def completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["omarchy-shell"], returncode, stdout, stderr)


def shell_available(_argv: object) -> subprocess.CompletedProcess[str]:
    return completed()


def shell_unavailable(_argv: object) -> subprocess.CompletedProcess[str]:
    return completed(1)


def sealed_catalog(tmp_path: Path) -> Path:
    source = Path(__file__).parents[1] / "examples" / "catalog" / "reading-focus-method" / "capsule.draft.json"
    draft = json.loads(source.read_text(encoding="utf-8"))
    capsule = seal_capsule(draft, source.parent)
    target = tmp_path / "catalog" / "reading-focus-method"
    target.mkdir(parents=True)
    (target / "capsule.json").write_text(json.dumps(capsule), encoding="utf-8")
    return target.parent


def test_profile_is_minimal_and_marks_shell_availability() -> None:
    profile = discover_profile(omarchy_release="2026.08", runner=shell_available)

    assert profile == {
        "schemaVersion": "limitless.omarchy-profile/0.1",
        "constraints": ["linux", "omarchy", "omarchy-plugin-schema-v1", "omarchy-shell-ipc"],
        "toolchain": {
            "omarchyPluginSchema": "1",
            "omarchyRelease": "2026.08",
            "omarchyShell": "available",
        },
    }


def test_profile_abstains_from_claiming_available_shell() -> None:
    profile = discover_profile(runner=shell_unavailable)

    assert "omarchy-shell-ipc" not in profile["constraints"]
    assert profile["toolchain"]["omarchyShell"] == "unavailable"


def test_build_query_is_generic_and_contains_no_task_text() -> None:
    request = build_query(
        discover_profile(runner=shell_available),
        evaluated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )

    assert request["schemaVersion"] == "limitless.query/0.1"
    assert request["taskKind"] == "omarchy-customization"
    assert request["tenantScope"] == "private"
    assert request["evaluatedAt"] == "2026-08-16T00:00:00Z"


def test_invalid_release_is_rejected() -> None:
    with pytest.raises(AdapterError):
        discover_profile(omarchy_release="../not-a-release", runner=shell_available)


def test_status_is_explicitly_local_only() -> None:
    result = status(runner=shell_available)

    assert result["mode"] == "local-only"
    assert result["service"] == {"connected": False, "reason": "service-not-configured"}


def test_query_returns_source_free_method_for_eligible_catalog(tmp_path: Path) -> None:
    result = query_local_catalog(
        sealed_catalog(tmp_path),
        runner=shell_available,
        evaluated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )

    assert result["mode"] == "local-only"
    assert result["disposition"] == "source-free-method"
    assert result["decision"]["treatment"] == "method-guided"


def test_bundled_catalog_is_sealed_and_queryable() -> None:
    catalog = Path(__file__).parents[1] / "examples" / "catalog"

    result = query_local_catalog(catalog, runner=shell_available, evaluated_at=datetime(2026, 8, 16, tzinfo=UTC))

    assert result["disposition"] == "source-free-method"
    assert result["decision"]["selected"]["capsule"]["id"] == "capsule:omarchy.reading-focus-method"


def test_query_fails_closed_for_unavailable_catalog(tmp_path: Path) -> None:
    result = query_local_catalog(tmp_path / "missing", runner=shell_available)

    assert result["disposition"] == "abstain"
    assert result["reason"] == "catalog-unavailable-or-ineligible"
    assert result["decision"] is None


@pytest.mark.parametrize(
    ("task_kind", "requested_use", "tenant_scope"),
    [
        ("other-work", "adopt", "private"),
        ("omarchy-customization", "replace", "private"),
        ("omarchy-customization", "adopt", "shared"),
    ],
)
def test_local_query_rejects_broader_task_or_scope(
    tmp_path: Path,
    task_kind: str,
    requested_use: str,
    tenant_scope: str,
) -> None:
    with pytest.raises(AdapterError):
        query_local_catalog(
            tmp_path,
            task_kind=task_kind,
            requested_use=requested_use,
            tenant_scope=tenant_scope,
            runner=shell_available,
        )


def test_owner_can_seal_a_local_capsule_without_overwriting(tmp_path: Path) -> None:
    draft = Path(__file__).parents[1] / "examples" / "catalog" / "reading-focus-method" / "capsule.draft.json"
    output = tmp_path / "private-capsule.json"

    sealed = seal_local_capsule(draft, output)

    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8")) == sealed
    assert sealed["capsuleDigest"].startswith("sha256:")
    with pytest.raises(AdapterError, match="refusing to overwrite immutable output"):
        seal_local_capsule(draft, output)


def test_native_validator_requires_available_directory() -> None:
    with pytest.raises(AdapterError):
        validate_plugin(Path("/definitely/not/a/plugin"), runner=shell_available)


def test_native_validator_reports_its_own_failure(tmp_path: Path) -> None:
    result = validate_plugin(tmp_path, runner=shell_unavailable)

    assert result["status"] == "invalid"


def test_mcp_derives_the_profile_and_returns_a_structured_method(tmp_path: Path) -> None:
    response = handle_message(
        sealed_catalog(tmp_path),
        {
            "jsonrpc": "2.0",
            "id": "query-1",
            "method": "tools/call",
            "params": {"name": TOOL_NAME, "arguments": {}},
        },
        runner=shell_available,
    )

    assert response is not None
    result = response["result"]["structuredContent"]
    assert result["disposition"] == "source-free-method"
    assert result["profile"]["toolchain"]["omarchyShell"] == "available"


def test_mcp_rejects_arbitrary_extra_task_data(tmp_path: Path) -> None:
    response = handle_message(
        sealed_catalog(tmp_path),
        {
            "jsonrpc": "2.0",
            "id": "query-2",
            "method": "tools/call",
            "params": {"name": TOOL_NAME, "arguments": {"prompt": "private request"}},
        },
        runner=shell_available,
    )

    assert response is not None
    assert response["result"]["isError"] is True


def test_mcp_rejects_free_text_in_a_bounded_field(tmp_path: Path) -> None:
    response = handle_message(
        sealed_catalog(tmp_path),
        {
            "jsonrpc": "2.0",
            "id": "query-3",
            "method": "tools/call",
            "params": {
                "name": TOOL_NAME,
                "arguments": {"tenantScope": "private work on a sensitive layout"},
            },
        },
        runner=shell_available,
    )

    assert response is not None
    assert response["result"]["isError"] is True


def test_mcp_supports_modern_stateless_tool_calls(tmp_path: Path) -> None:
    response = handle_message(
        sealed_catalog(tmp_path),
        {
            "jsonrpc": "2.0",
            "id": "query-4",
            "method": "tools/call",
            "params": {
                "name": TOOL_NAME,
                "arguments": {},
                "_meta": modern_metadata(client_name="test", client_version="1"),
            },
        },
        runner=shell_available,
    )

    assert response is not None
    assert response["result"]["resultType"] == "complete"
    assert response["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "limitless-omarchy"
