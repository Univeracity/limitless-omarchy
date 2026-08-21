from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import limitless_library
import pytest
from limitless_library.catalog import seal_capsule
from limitless_library.contracts import load_json
from limitless_library.mcp_protocol import modern_metadata
from limitless_library.mcp_server import TOOL_NAME as GENERAL_TOOL_NAME
from limitless_library.service_connector import ServiceConnectorError, ServiceUnavailableError

from limitless_omarchy import service as service_module
from limitless_omarchy.adapter import (
    AdapterError,
    build_query,
    discover_profile,
    query_local_catalog,
    seal_local_capsule,
    status,
    validate_plugin,
)
from limitless_omarchy.cli import _service_query_input
from limitless_omarchy.mcp_server import TOOL_NAME, handle_message
from limitless_omarchy.provider import general_provider_command
from limitless_omarchy.service import (
    activate_managed_service,
    build_service_receiver_context,
    inspect_managed_service,
    query_managed_service,
)

ROOT = Path(__file__).parents[1]
GENERAL_ASSETS = Path(limitless_library.__file__).with_name("demo_assets")
GENERAL_CATALOG = GENERAL_ASSETS / "catalog"
GENERAL_REQUEST = GENERAL_ASSETS / "requests" / "exact-python.json"


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


def service_profile(tmp_path: Path) -> Path:
    path = tmp_path / "service-profile.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "limitless.service-profile/1.1",
                "apiBaseUrl": "https://api.example.com",
                "serviceId": "service:example",
                "rootKey": {
                    "keyId": "root:example",
                    "algorithm": "ed25519",
                    "publicKey": "A" * 43,
                },
                "acceptedPolicyDigest": "sha256:" + "1" * 64,
                "executionMode": "service",
                "defaultAudience": "private",
                "historyMode": "local-only",
                "requestedAudiences": ["public"],
            }
        ),
        encoding="utf-8",
    )
    return path


class FakeServiceConnector:
    def __init__(self, profile: object) -> None:
        self.profile = profile
        self.last_query: dict[str, object] | None = None

    def inspect(self) -> object:
        return SimpleNamespace(
            discovery={
                "dataUsePolicy": {
                    "url": "https://example.com/policy",
                    "digest": "sha256:" + "1" * 64,
                },
                "resultVersions": ["limitless.service-query-result/1.1"],
                "expiresAt": "2026-08-21T00:00:00Z",
            }
        )

    def build_query(self, **values: object) -> dict[str, object]:
        return {
            **values,
            "queryDigest": "sha256:" + "2" * 64,
        }

    def query(self, query: dict[str, object]) -> dict[str, object]:
        self.last_query = query
        return {
            "treatment": "source-free-method",
            "selection": {
                "title": "Reviewed focus method",
                "summary": "Reduce visual noise while preserving navigation.",
                "method": {"summary": "Apply the reviewed focus sequence."},
            },
        }


class UnavailableServiceConnector(FakeServiceConnector):
    def query(self, query: dict[str, object]) -> dict[str, object]:
        self.last_query = query
        raise ServiceUnavailableError("unavailable")


class InvalidAuthorityConnector(FakeServiceConnector):
    def inspect(self) -> object:
        raise ServiceConnectorError("invalid authority")


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


def test_service_receiver_context_is_minimal_and_target_aware() -> None:
    context = build_service_receiver_context(discover_profile(omarchy_release="4.2", runner=shell_available))

    assert context["receiverId"] == "receiver:omarchy-desktop"
    assert context["interfaces"] == ["omarchy.plugin/v1"]
    assert context["targets"][0]["runtime"] == "omarchy"
    assert context["targets"][0]["versionRange"] == "==4.2"
    assert "plugins" not in json.dumps(context).lower()


def test_service_inspection_verifies_profile_without_a_query(tmp_path: Path) -> None:
    result = inspect_managed_service(
        service_profile(tmp_path),
        connector_factory=FakeServiceConnector,
    )

    assert result["mode"] == "managed-service-ready"
    assert result["service"]["serviceId"] == "service:example"
    assert result["policy"]["digest"] == "sha256:" + "1" * 64


def test_service_activation_is_one_action_and_persists_no_credential(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile = load_json(service_profile(tmp_path))
    monkeypatch.setattr(
        service_module,
        "activate_official_service",
        lambda: {
            "profile": profile,
            "activatedAt": "2026-08-20T22:00:00Z",
        },
    )

    result = activate_managed_service()

    assert result["mode"] == "managed-service-ready"
    assert result["service"]["defaultAudience"] == "private"
    assert result["service"]["authenticated"] is False


def test_managed_query_returns_verified_shape_without_echoing_sensitive_input(tmp_path: Path) -> None:
    result = query_managed_service(
        service_profile(tmp_path),
        objective="Find a reviewed focus customization.",
        access_token="test-access-token-value",
        omarchy_release="4.2",
        request_id="request:omarchy-test",
        runner=shell_available,
        connector_factory=FakeServiceConnector,
    )

    encoded = json.dumps(result)
    assert result["mode"] == "managed-service"
    assert result["disposition"] == "source-free-method"
    assert result["decision"]["selection"]["title"] == "Reviewed focus method"
    assert "Find a reviewed" not in encoded
    assert "test-access-token-value" not in encoded
    assert result["service"]["authenticated"] is True


def test_managed_unavailability_abstains_without_disabling_local_reuse(tmp_path: Path) -> None:
    result = query_managed_service(
        service_profile(tmp_path),
        objective="Find a reviewed focus customization.",
        request_id="request:omarchy-test",
        runner=shell_available,
        connector_factory=UnavailableServiceConnector,
    )

    assert result["disposition"] == "abstain"
    assert result["reason"] == "service-unavailable-local-still-available"
    assert result["decision"] is None


def test_service_authority_failure_is_not_reclassified_as_an_abstention(tmp_path: Path) -> None:
    with pytest.raises(AdapterError, match="authority verification failed"):
        inspect_managed_service(
            service_profile(tmp_path),
            connector_factory=InvalidAuthorityConnector,
        )


def test_service_cli_reads_objective_and_token_only_from_bounded_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schemaVersion": "limitless.omarchy-service-query-input/0.1",
        "objective": "Find a reviewed focus customization.",
        "accessToken": "test-access-token-value",
    }
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(buffer=BytesIO((json.dumps(payload) + "\n").encode("utf-8"))),
    )

    assert _service_query_input() == (
        "Find a reviewed focus customization.",
        "test-access-token-value",
    )


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


def test_general_provider_reuses_the_core_server_with_the_current_interpreter(tmp_path: Path) -> None:
    catalog = tmp_path / "general-catalog"

    assert general_provider_command(catalog) == [
        sys.executable,
        "-m",
        "limitless_library.mcp_server",
        "--catalog",
        str(catalog),
    ]


def test_general_provider_is_explicit_and_exposes_only_the_generic_tool() -> None:
    request = load_json(GENERAL_REQUEST)
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {"_meta": modern_metadata(client_name="test", client_version="1")},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": GENERAL_TOOL_NAME,
                "arguments": request,
                "_meta": modern_metadata(client_name="test", client_version="1"),
            },
        },
    ]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(Path(limitless_library.__file__).parents[1])])
    completed_process = subprocess.run(
        [
            sys.executable,
            "-m",
            "limitless_omarchy.cli",
            "provider",
            "--catalog",
            str(GENERAL_CATALOG),
        ],
        input="".join(json.dumps(message) + "\n" for message in messages),
        capture_output=True,
        check=True,
        encoding="utf-8",
        env=environment,
    )
    responses = [json.loads(line) for line in completed_process.stdout.splitlines()]

    assert [tool["name"] for tool in responses[0]["result"]["tools"]] == [GENERAL_TOOL_NAME]
    assert responses[1]["result"]["structuredContent"]["decision"] == "reuse"
