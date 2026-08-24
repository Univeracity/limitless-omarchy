from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import limitless_library
import pytest
from limitless_library.catalog import seal_capsule
from limitless_library.contracts import load_json, write_new_bytes
from limitless_library.exact_file_bundle import build_exact_file_bundle
from limitless_library.mcp_protocol import modern_metadata
from limitless_library.mcp_server import TOOL_NAME as GENERAL_TOOL_NAME
from limitless_library.service_connector import (
    ServiceConnectorError,
    ServiceProfile,
    ServiceUnavailableError,
)
from limitless_library.service_identity import InstallationSigner

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
from limitless_omarchy.cli import (
    _local_query_input,
    _service_artifact_enable_input,
    _service_artifact_install_input,
    _service_artifact_review_input,
    _service_artifact_stage_input,
    _service_publication_input,
    _service_query_input,
)
from limitless_omarchy.mcp_server import TOOL_NAME, handle_message
from limitless_omarchy.provider import general_provider_command
from limitless_omarchy.service import (
    activate_managed_service,
    build_service_receiver_context,
    enable_managed_plugin,
    inspect_managed_service,
    install_managed_plugin_disabled,
    manage_publication,
    prepare_managed_plugin_review,
    query_managed_service,
    stage_managed_artifact,
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
    source = Path(__file__).parents[1] / "catalog" / "reading-focus-method" / "capsule.draft.json"
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
                "publicationPolicy": {
                    "url": "https://example.com/publication-policy",
                    "revision": "publication-2026-08",
                    "digest": "sha256:" + "3" * 64,
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


class UsageExceededError(ServiceUnavailableError):
    def __init__(self) -> None:
        super().__init__("free usage exceeded")
        self.reset_at = "2026-08-24T00:00:00Z"
        self.upgrade_url = "https://limitlesslibrary.com/#contact"


class UsageExceededServiceConnector(FakeServiceConnector):
    def query(self, query: dict[str, object]) -> dict[str, object]:
        self.last_query = query
        raise UsageExceededError


class InvalidAuthorityConnector(FakeServiceConnector):
    def inspect(self) -> object:
        raise ServiceConnectorError("invalid authority")


class ArtifactContinuationConnector(FakeServiceConnector):
    artifact = build_exact_file_bundle(
        {
            "manifest.json": (
                b'{"schemaVersion":1,"id":"example.reviewed-plugin",'
                b'"name":"Reviewed plugin","version":"1.0.0","kinds":["panel"],'
                b'"entryPoints":{"panel":"plugin.qml"}}\n'
            ),
            "plugin.qml": b"import QtQuick\nItem {}\n",
        }
    )

    def fetch_selected_artifact_continuation(
        self,
        *,
        result: dict[str, object],
        expected_request_digest: str,
        destination: Path,
    ) -> dict[str, object]:
        assert result["requestDigest"] == expected_request_digest
        write_new_bytes(destination, self.artifact)
        immutable = result["selection"]["immutable"]  # type: ignore[index]
        return {
            "schemaVersion": "limitless.staged-service-artifact/1.1",
            "decisionRef": result["decisionRef"],
            "capabilityId": result["selection"]["capabilityId"],  # type: ignore[index]
            "revision": immutable["revision"],
            "digest": immutable["digest"],
            "byteLength": len(self.artifact),
            "format": "limitless.exact-file-bundle/1.0",
            "mediaType": "application/vnd.limitless.exact-file-bundle+json",
            "path": str(destination),
            "nextAction": result["nextAction"],
        }


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


def test_build_query_can_remain_generic_when_no_local_objective_is_supplied() -> None:
    request = build_query(
        discover_profile(runner=shell_available),
        evaluated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )

    assert request["schemaVersion"] == "limitless.query/0.1"
    assert request["taskKind"] == "omarchy-customization"
    assert request["tenantScope"] == "private"
    assert request["evaluatedAt"] == "2026-08-16T00:00:00Z"
    assert "objective" not in request


def test_build_query_binds_one_short_local_objective() -> None:
    request = build_query(
        discover_profile(runner=shell_available),
        objective="  Keep Wi-Fi rows still during password entry.  ",
        evaluated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )

    assert request["objective"] == "Keep Wi-Fi rows still during password entry."


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
    assert result["publicationPolicy"]["digest"] == "sha256:" + "3" * 64


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
    connector = FakeServiceConnector(ServiceProfile.from_json(profile))
    monkeypatch.setattr(service_module, "activated_service_connector", lambda: connector)

    result = activate_managed_service()

    assert result["mode"] == "managed-service-ready"
    assert result["service"]["defaultAudience"] == "private"
    assert result["service"]["authenticated"] is False
    assert result["publicationPolicy"]["digest"] == "sha256:" + "3" * 64


def test_ordinary_service_path_uses_automatic_anonymous_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    connector = FakeServiceConnector(
        ServiceProfile.from_json(
            {
                "schemaVersion": "limitless.service-profile/1.1",
                "apiBaseUrl": "https://service.example",
                "serviceId": "service:example",
                "rootKey": {
                    "keyId": "root:example",
                    "algorithm": "ed25519",
                    "publicKey": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                },
                "acceptedPolicyDigest": "sha256:" + "1" * 64,
                "executionMode": "service",
                "defaultAudience": "private",
                "historyMode": "local-only",
                "requestedAudiences": ["public"],
            }
        )
    )
    monkeypatch.setattr(
        service_module,
        "activated_service_connector",
        lambda: calls.append("automatic-session") or connector,
    )

    result = inspect_managed_service()

    assert calls == ["automatic-session"]
    assert result["mode"] == "managed-service-ready"


def test_service_inspection_distinguishes_not_enabled_from_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def not_enabled() -> object:
        raise service_module.OfficialServiceNotConfiguredError("not enabled")

    monkeypatch.setattr(service_module, "activated_service_connector", not_enabled)

    result = inspect_managed_service()

    assert result == {
        "schemaVersion": "limitless.omarchy-service-status/0.1",
        "mode": "service-not-enabled",
        "reason": "service-not-enabled",
    }


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
    assert result["selection"]["title"] == "Reviewed focus method"
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
    assert result["selection"] is None


def test_managed_usage_limit_preserves_local_reuse_and_exposes_only_safe_upgrade_details(
    tmp_path: Path,
) -> None:
    result = query_managed_service(
        service_profile(tmp_path),
        objective="Find a reviewed focus customization.",
        request_id="request:omarchy-test",
        runner=shell_available,
        connector_factory=UsageExceededServiceConnector,
    )

    encoded = json.dumps(result)
    assert result["disposition"] == "abstain"
    assert result["reason"] == "free-usage-exceeded"
    assert result["selection"] is None
    assert result["usage"] == {
        "resetAt": "2026-08-24T00:00:00Z",
        "upgradeUrl": "https://limitlesslibrary.com/#contact",
    }
    assert "Find a reviewed" not in encoded


def test_exact_result_projects_no_delivery_secret_and_stages_from_signed_local_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile = ServiceProfile.from_json(load_json(service_profile(tmp_path)))
    connector = ArtifactContinuationConnector(profile)
    signer = InstallationSigner.generate()
    publisher = {
        "publisherId": "installation:" + "1" * 32,
        "authorityId": "installation-space:" + "2" * 32,
        "keyId": signer.key_id,
        "generation": 1,
    }
    artifact_digest = "sha256:" + sha256(connector.artifact).hexdigest()
    request_digest = "sha256:" + "3" * 64
    decision = {
        "schemaVersion": "limitless.service-query-result/1.4",
        "requestDigest": request_digest,
        "decisionRef": "decision:omarchy-artifact-test",
        "treatment": "exact-component",
        "selection": {
            "capabilityId": "capability:omarchy-artifact-test",
            "title": "Reviewed exact plugin",
            "summary": "An exact plugin bundle for receiver review.",
            "immutable": {
                "kind": "artifact",
                "revision": "1.0.0",
                "digest": artifact_digest,
                "byteLength": len(connector.artifact),
                "format": "limitless.exact-file-bundle/1.0",
                "mediaType": "application/vnd.limitless.exact-file-bundle+json",
                "uri": "https://objects.example.test/v1/artifact",
                "authorization": {
                    "header": "Limitless-Capability",
                    "value": "A" * 43,
                },
            },
        },
        "nextAction": {
            "kind": "handoff-native-add",
            "instruction": "Review before native installation.",
            "checks": [
                {
                    "id": "interface",
                    "predicate": "interface-subset",
                    "expected": "omarchy.plugin/v1",
                }
            ],
            "localReuseAvailable": True,
            "handoff": "omarchy-native-add",
        },
        "resultDigest": "sha256:" + "4" * 64,
    }
    environment = {
        "HOME": str(tmp_path / "home"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
    }
    state = service_module._write_handoff_state(
        connector=connector,
        result=decision,
        signer=signer,
        publisher=publisher,
        environ=environment,
    )
    projected = service_module._managed_result(
        connector=connector,
        local_profile=discover_profile(omarchy_release="4.2", runner=shell_available),
        query={"queryDigest": request_digest},
        decision=decision,
        handoff_state_path=state,
    )
    monkeypatch.setattr(service_module, "activated_service_connector", lambda: connector)
    monkeypatch.setattr(
        service_module,
        "installation_publisher_authority",
        lambda *, service_id: (signer, publisher),
    )

    staged = stage_managed_artifact(state, environ=environment)

    assert state.stat().st_mode & 0o777 == 0o600
    assert projected["handoffStatePath"] == str(state)
    assert "authorization" not in json.dumps(projected)
    assert "A" * 43 not in json.dumps(projected)
    assert "objects.example.test" not in json.dumps(projected)
    assert staged["nativeInstallationRequired"] is True
    assert staged["format"] == "limitless.exact-file-bundle/1.0"
    assert Path(staged["path"]).read_bytes() == connector.artifact
    assert Path(staged["path"]).stat().st_mode & 0o777 == 0o600
    assert stage_managed_artifact(state, environ=environment) == staged

    commands: list[tuple[str, ...]] = []

    def native_validator(argv: object) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)  # type: ignore[arg-type]
        commands.append(command)
        return completed(stdout="plugin valid")

    reviewed = prepare_managed_plugin_review(
        state,
        environ=environment,
        runner=native_validator,
    )
    review_path = Path(reviewed["reviewPath"])
    assert reviewed["installationDisposition"] == "not-installed"
    assert reviewed["nativeValidation"]["status"] == "valid"
    assert [item["path"] for item in reviewed["files"]] == ["manifest.json", "plugin.qml"]
    assert (review_path / "manifest.json").is_file()
    assert commands == [("omarchy", "plugin", "validate", str(review_path))]
    assert not any(operation in " ".join(commands[0]) for operation in (" add ", " enable ", " remove "))

    class ReceiverRuntime:
        def __init__(self) -> None:
            self.enabled = False
            self.commands: list[tuple[str, ...]] = []

        def __call__(self, argv: object) -> subprocess.CompletedProcess[str]:
            command = tuple(argv)  # type: ignore[arg-type]
            self.commands.append(command)
            if command[:3] == ("omarchy", "plugin", "validate"):
                return completed(stdout="plugin valid")
            if command == ("omarchy-shell", "shell", "rescanPlugins"):
                return completed(stdout="ok")
            if command == ("omarchy", "plugin", "list", "--json"):
                installed = Path(environment["HOME"]) / ".config/omarchy/plugins/example.reviewed-plugin"
                records = []
                if installed.is_dir():
                    records.append(
                        {
                            "id": "example.reviewed-plugin",
                            "name": "Reviewed plugin",
                            "kinds": ["panel"],
                            "enabled": self.enabled,
                            "active": False,
                            "canDisable": True,
                            "firstParty": False,
                            "clonedFrom": "",
                        }
                    )
                return completed(stdout=json.dumps(records))
            if command == ("omarchy", "plugin", "enable", "example.reviewed-plugin"):
                self.enabled = True
                config = Path(environment["HOME"]) / ".config/omarchy/shell.json"
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_text(
                    json.dumps({"version": 1, "plugins": [{"id": "example.reviewed-plugin"}]}),
                    encoding="utf-8",
                )
                return completed(stdout="Enabled example.reviewed-plugin")
            if command == ("omarchy", "plugin", "disable", "example.reviewed-plugin"):
                self.enabled = False
                return completed(stdout="Disabled example.reviewed-plugin")
            if command == (
                "omarchy-shell",
                "shell",
                "summon",
                "example.reviewed-plugin",
                "{}",
            ):
                return completed(stdout="ok")
            return completed(returncode=99, stderr="unexpected receiver command")

    receiver = ReceiverRuntime()
    installed = install_managed_plugin_disabled(
        state,
        environ=environment,
        runner=receiver,
        occurred_at=datetime(2026, 8, 22, 12, tzinfo=UTC),
    )
    assert installed["installationDisposition"] == "installed-disabled"
    assert installed["enabled"] is False
    assert Path(installed["installPath"], "plugin.qml").read_bytes() == b"import QtQuick\nItem {}\n"
    assert Path(installed["installationStatePath"]).stat().st_mode & 0o777 == 0o600
    assert (
        install_managed_plugin_disabled(
            state,
            environ=environment,
            runner=receiver,
            occurred_at=datetime(2026, 8, 22, 12, tzinfo=UTC),
        )
        == installed
    )

    adopted = enable_managed_plugin(
        Path(installed["installationStatePath"]),
        environ=environment,
        runner=receiver,
        occurred_at=datetime(2026, 8, 22, 12, 1, tzinfo=UTC),
    )
    assert adopted["installationDisposition"] == "enabled"
    assert adopted["observedInvocation"] == {
        "observed": True,
        "kind": "omarchy-shell-summon",
        "pluginId": "example.reviewed-plugin",
        "nativeRecordDigest": adopted["observedInvocation"]["nativeRecordDigest"],
    }
    assert adopted["observedInvocation"]["nativeRecordDigest"].startswith("sha256:")
    assert Path(adopted["adoptionReceiptPath"]).stat().st_mode & 0o777 == 0o600
    assert (
        enable_managed_plugin(
            Path(installed["installationStatePath"]),
            environ=environment,
            runner=receiver,
        )
        == adopted
    )
    assert ("omarchy", "plugin", "enable", "example.reviewed-plugin") in receiver.commands
    assert (
        "omarchy-shell",
        "shell",
        "summon",
        "example.reviewed-plugin",
        "{}",
    ) in receiver.commands
    installed_plugin = Path(installed["installPath"], "plugin.qml")
    installed_plugin.write_text("substituted\n", encoding="utf-8")
    installed_plugin.chmod(0o644)
    with pytest.raises(AdapterError, match="no longer matches its exact bundle"):
        enable_managed_plugin(
            Path(installed["installationStatePath"]),
            environ=environment,
            runner=receiver,
        )
    installed_plugin.write_bytes(b"import QtQuick\nItem {}\n")
    installed_plugin.chmod(0o644)

    plugin_path = review_path / "plugin.qml"
    plugin_path.unlink()
    plugin_path.symlink_to(Path(environment["HOME"]) / "outside.qml")
    with pytest.raises(AdapterError, match="review tree"):
        prepare_managed_plugin_review(
            state,
            environ=environment,
            runner=native_validator,
        )

    renamed = state.with_name("5" * 64 + ".json")
    write_new_bytes(renamed, state.read_bytes())
    with pytest.raises(AdapterError, match="continuation is unbound"):
        stage_managed_artifact(renamed, environ=environment)

    tampered = json.loads(state.read_text(encoding="utf-8"))
    tampered["result"]["selection"]["title"] = "Substituted plugin"
    state.write_text(json.dumps(tampered), encoding="utf-8")
    state.chmod(0o600)
    with pytest.raises(AdapterError, match="signature is invalid"):
        stage_managed_artifact(state, environ=environment)


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


def test_local_cli_reads_only_one_short_objective_from_bounded_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schemaVersion": "limitless.omarchy-local-query-input/0.1",
        "objective": "Keep Wi-Fi rows still during password entry.",
    }
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(buffer=BytesIO((json.dumps(payload) + "\n").encode("utf-8"))),
    )

    assert _local_query_input() == "Keep Wi-Fi rows still during password entry."


@pytest.mark.parametrize(
    ("operation", "draft", "state", "accepted_digest", "reason"),
    [
        ("publish", "/tmp/reviewed-publication.json", None, "sha256:" + "3" * 64, None),
        ("status", None, "/tmp/reviewed-publication.json.state.json", None, None),
        (
            "revoke",
            None,
            "/tmp/reviewed-publication.json.state.json",
            None,
            "publisher-withdrawal",
        ),
    ],
)
def test_service_publication_cli_accepts_only_explicit_bounded_paths(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    draft: str | None,
    state: str | None,
    accepted_digest: str | None,
    reason: str | None,
) -> None:
    payload = {
        "schemaVersion": "limitless.omarchy-publication-input/0.1",
        "operation": operation,
        "draftPath": draft,
        "statePath": state,
        "acceptedPublicationPolicyDigest": accepted_digest,
        "reasonCode": reason,
    }
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(buffer=BytesIO((json.dumps(payload) + "\n").encode("utf-8"))),
    )

    result = _service_publication_input()

    assert result["operation"] == operation
    assert result["draft_path"] == (None if draft is None else Path(draft))
    assert result["state_path"] == (None if state is None else Path(state))
    assert result["accepted_publication_policy_digest"] == accepted_digest
    assert result["reason_code"] == reason


def test_service_publication_cli_rejects_relative_or_unaccepted_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schemaVersion": "limitless.omarchy-publication-input/0.1",
        "operation": "publish",
        "draftPath": "publication.json",
        "statePath": None,
        "acceptedPublicationPolicyDigest": None,
        "reasonCode": None,
    }
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(buffer=BytesIO((json.dumps(payload) + "\n").encode("utf-8"))),
    )

    with pytest.raises(AdapterError, match="path is invalid"):
        _service_publication_input()


def test_service_artifact_stage_cli_accepts_only_one_absolute_state_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schemaVersion": "limitless.omarchy-artifact-stage-input/0.1",
        "handoffStatePath": "/home/user/.local/state/limitless-omarchy/artifact-handoffs/" + "4" * 64 + ".json",
    }
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(buffer=BytesIO((json.dumps(payload) + "\n").encode("utf-8"))),
    )

    assert _service_artifact_stage_input() == Path(payload["handoffStatePath"])


def test_service_artifact_review_cli_accepts_only_one_absolute_state_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schemaVersion": "limitless.omarchy-artifact-review-input/0.1",
        "handoffStatePath": "/home/user/.local/state/limitless-omarchy/artifact-handoffs/" + "4" * 64 + ".json",
    }
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(buffer=BytesIO((json.dumps(payload) + "\n").encode("utf-8"))),
    )

    assert _service_artifact_review_input() == Path(payload["handoffStatePath"])


def test_service_artifact_install_cli_accepts_only_one_absolute_handoff_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schemaVersion": "limitless.omarchy-artifact-install-input/0.1",
        "handoffStatePath": "/home/user/.local/state/limitless-omarchy/artifact-handoffs/" + "4" * 64 + ".json",
    }
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(buffer=BytesIO((json.dumps(payload) + "\n").encode("utf-8"))),
    )

    assert _service_artifact_install_input() == Path(payload["handoffStatePath"])


def test_service_artifact_enable_cli_accepts_only_one_absolute_installation_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schemaVersion": "limitless.omarchy-artifact-enable-input/0.1",
        "installationStatePath": "/home/user/.local/state/limitless-omarchy/receiver-installations/"
        + "4" * 64
        + ".json",
    }
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(buffer=BytesIO((json.dumps(payload) + "\n").encode("utf-8"))),
    )

    assert _service_artifact_enable_input() == Path(payload["installationStatePath"])


def test_managed_publication_uses_current_anonymous_authority_and_projects_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    connector = SimpleNamespace(profile=SimpleNamespace(service_id="service:example"))
    signer = object()
    publisher = {"publisherId": "installation:example"}
    draft = tmp_path / "publication.json"
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(service_module, "activated_service_connector", lambda: connector)
    monkeypatch.setattr(
        service_module,
        "installation_publisher_authority",
        lambda *, service_id: (signer, publisher),
    )
    monkeypatch.setattr(
        service_module,
        "publish_draft",
        lambda selected, **values: (
            calls.append({"connector": selected, **values})
            or {
                "submissionRef": "public-submission:example",
                "admissionState": "pending",
                "uploadedObjects": [{"digest": "sha256:" + "1" * 64}],
                "statePath": str(draft) + ".state.json",
            }
        ),
    )

    result = manage_publication(
        operation="publish",
        draft_path=draft,
        state_path=None,
        accepted_publication_policy_digest="sha256:" + "3" * 64,
        reason_code=None,
    )

    assert calls[0]["connector"] is connector
    assert calls[0]["signer"] is signer
    assert calls[0]["publisher"] is publisher
    assert calls[0]["draft_path"] == draft
    assert calls[0]["accepted_publication_policy_digest"] == "sha256:" + "3" * 64
    assert result == {
        "schemaVersion": "limitless.omarchy-publication-result/0.1",
        "operation": "publish",
        "submissionRef": "public-submission:example",
        "admissionState": "pending",
        "releaseRef": None,
        "reasonCodes": [],
        "uploadedObjectCount": 1,
        "statePath": str(draft) + ".state.json",
    }


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
    catalog = Path(__file__).parents[1] / "catalog"

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
    draft = Path(__file__).parents[1] / "catalog" / "reading-focus-method" / "capsule.draft.json"
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
            "params": {"name": TOOL_NAME, "arguments": {"objective": "Create a portable greeting."}},
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
            "params": {
                "name": TOOL_NAME,
                "arguments": {"objective": "Create a portable greeting.", "prompt": "private request"},
            },
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
                "arguments": {
                    "objective": "Create a portable greeting.",
                    "tenantScope": "private work on a sensitive layout",
                },
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
                "arguments": {"objective": "Create a portable greeting."},
                "_meta": modern_metadata(client_name="test", client_version="1"),
            },
        },
        runner=shell_available,
    )

    assert response is not None
    assert response["result"]["resultType"] == "complete"
    assert response["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "limitless-omarchy"


def test_configured_mcp_exposes_general_limitless_reuse_and_counts_it(tmp_path: Path) -> None:
    activity = tmp_path / "activity.json"
    response = handle_message(
        GENERAL_CATALOG,
        {
            "jsonrpc": "2.0",
            "id": "general-query",
            "method": "tools/call",
            "params": {
                "name": GENERAL_TOOL_NAME,
                "arguments": load_json(GENERAL_REQUEST),
                "_meta": modern_metadata(client_name="test", client_version="1"),
            },
        },
        activity_path=activity,
    )

    assert response is not None
    assert response["result"]["structuredContent"]["decision"] == "reuse"
    assert json.loads(activity.read_text(encoding="utf-8"))["queries"]["general"] == 1


def test_general_provider_wraps_the_core_server_with_the_current_interpreter(tmp_path: Path) -> None:
    catalog = tmp_path / "general-catalog"
    activity = tmp_path / "activity.json"

    assert general_provider_command(catalog, activity) == [
        sys.executable,
        "-m",
        "limitless_omarchy.provider",
        "--catalog",
        str(catalog),
        "--activity-path",
        str(activity),
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


def test_general_provider_counts_only_the_aggregate_outcome(tmp_path: Path) -> None:
    request = load_json(GENERAL_REQUEST)
    activity = tmp_path / "activity.json"
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": GENERAL_TOOL_NAME,
            "arguments": request,
            "_meta": modern_metadata(client_name="test", client_version="1"),
        },
    }
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
            "--activity-path",
            str(activity),
        ],
        input=json.dumps(message) + "\n",
        capture_output=True,
        check=True,
        encoding="utf-8",
        env=environment,
    )

    assert json.loads(completed_process.stdout)["result"]["structuredContent"]["decision"] == "reuse"
    stored = json.loads(activity.read_text(encoding="utf-8"))
    assert stored["queries"]["total"] == 1
    assert stored["queries"]["general"] == 1
    assert stored["queries"]["local"] == 0
    assert stored["queries"]["service"] == 0
    serialized = activity.read_text(encoding="utf-8")
    assert request["taskKind"] not in serialized
    assert request["evaluatedAt"] not in serialized
