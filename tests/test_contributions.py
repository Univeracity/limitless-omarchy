from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from limitless_library.publication import _draft as validate_publication_draft

from limitless_omarchy import contributions as contribution_module
from limitless_omarchy import mcp_server
from limitless_omarchy.activity import activity_summary
from limitless_omarchy.adapter import query_local_catalog
from limitless_omarchy.contributions import (
    contribution_states,
    schedule_contribution_sync,
    sync_contributions,
    transition_contribution,
)
from limitless_omarchy.drafts import DraftError, list_drafts, load_draft, register_method
from limitless_omarchy.mcp_server import REGISTER_METHOD_TOOL_NAME, handle_message
from limitless_omarchy.settings import SettingsError, default_settings, load_settings, save_settings

POLICY_DIGEST = "sha256:" + "3" * 64


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    drafts = tmp_path / "drafts"
    catalog = tmp_path / "catalog"
    settings = tmp_path / "config" / "settings.json"
    drafts.mkdir()
    catalog.mkdir()
    return drafts, catalog, settings


def _settings(*, destination: str = "local", mode: str = "agent-mediated") -> dict[str, object]:
    return {
        "schemaVersion": "limitless.omarchy-owner-settings/0.1",
        "defaultDestination": destination,
        "contributionMode": mode,
        "materialPolicy": "methods-only",
        "publicPolicyDigest": POLICY_DIGEST if destination == "public" else None,
    }


def _register(drafts: Path, catalog: Path, settings: Path, *, name: str = "Lock-safe updates") -> dict[str, object]:
    return register_method(
        drafts,
        catalog,
        settings,
        {
            "name": name,
            "steps": ["Check lock state before replacing live files.", "Apply the update after unlock."],
            "sources": "https://example.com/upstream-issue",
        },
    )


def test_owner_settings_are_secure_and_public_is_bound_once(tmp_path: Path) -> None:
    _drafts, _catalog, settings = _paths(tmp_path)

    assert load_settings(settings) == default_settings()
    saved = save_settings(settings, _settings(destination="public", mode="automatic"))

    assert saved["publicPolicyDigest"] == POLICY_DIGEST
    assert stat.S_IMODE(settings.stat().st_mode) == 0o600
    invalid = _settings(destination="public")
    invalid["publicPolicyDigest"] = None
    with pytest.raises(SettingsError, match="verified policy"):
        save_settings(settings, invalid)


def test_minimal_registration_is_compact_idempotent_and_locally_useful(tmp_path: Path) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings())

    first = _register(drafts, catalog, settings)
    duplicate = _register(drafts, catalog, settings)

    assert first == {
        "schemaVersion": "limitless.method-registration-result/0.1",
        "status": "registered",
        "draftRef": first["draftRef"],
        "destination": "local",
    }
    assert duplicate == {**first, "status": "duplicate"}
    assert len(json.dumps(first, separators=(",", ":"))) < 180
    record = load_draft(drafts, str(first["draftRef"]))
    assert record["sourceReferences"] == ["https://example.com/upstream-issue"]
    assert record["method"]["verification"] == ["Confirm receiver-owned checks for the resulting change pass."]
    projection = next(catalog.glob("local-*/capsule.json"))
    capsule = json.loads(projection.read_text(encoding="utf-8"))
    assert capsule["offers"][0]["kind"] == "method"
    assert capsule["license"] == "LicenseRef-Limitless-Source-Free-Method"
    assert list_drafts(drafts)["items"][0]["status"] == "local"


def test_registration_retains_revision_provenance_and_retires_only_projection(tmp_path: Path) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings())
    first = _register(drafts, catalog, settings)
    second = register_method(
        drafts,
        catalog,
        settings,
        {
            "name": "Lock-safe updates",
            "steps": ["Wait for an unlocked compositor session.", "Replace files atomically."],
            "supersedes": first["draftRef"],
        },
    )

    assert load_draft(drafts, str(first["draftRef"]))["revision"] == 1
    assert load_draft(drafts, str(second["draftRef"]))["revision"] == 2
    assert len(list((drafts / "records").glob("*.json"))) == 2
    assert len(list(catalog.glob("local-*/capsule.json"))) == 1
    statuses = {item["draftRef"]: item["status"] for item in list_drafts(drafts)["items"]}
    assert statuses[first["draftRef"]] == "superseded"
    assert statuses[second["draftRef"]] == "local"


def test_superseded_content_is_not_reported_as_a_current_duplicate(tmp_path: Path) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings())
    first = _register(drafts, catalog, settings)
    second = register_method(
        drafts,
        catalog,
        settings,
        {
            "name": "Lock-safe updates",
            "steps": ["Wait until the session is unlocked.", "Swap one validated tree."],
            "supersedes": first["draftRef"],
        },
    )

    restored = _register(drafts, catalog, settings)

    assert restored["status"] == "registered"
    assert restored["draftRef"] not in {first["draftRef"], second["draftRef"]}
    assert len(list(catalog.glob("local-*/capsule.json"))) == 2


def test_tampered_immutable_record_is_rejected(tmp_path: Path) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings())
    registered = _register(drafts, catalog, settings)
    identifier = str(registered["draftRef"]).split(":", 1)[1]
    path = drafts / "records" / f"{identifier}.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["method"]["steps"] = ["Tampered after registration."]
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(DraftError, match="content digest"):
        load_draft(drafts, str(registered["draftRef"]))


def test_local_objective_selects_one_of_multiple_registered_methods(tmp_path: Path) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings())
    _register(drafts, catalog, settings)
    register_method(
        drafts,
        catalog,
        settings,
        {
            "name": "Reading focus layout",
            "steps": ["Hide low-value chrome.", "Keep the current article centered."],
        },
    )

    result = query_local_catalog(
        catalog,
        objective="Check lock state before replacing live files.",
    )

    assert result["disposition"] == "source-free-method"
    assert result["decision"]["selected"]["offer"]["method"]["summary"] == "Lock-safe updates"


def test_off_setting_makes_registration_a_no_write_noop(tmp_path: Path) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings(destination="off"))

    result = _register(drafts, catalog, settings)

    assert result["status"] == "disabled"
    assert result["draftRef"] is None
    assert not list((drafts / "records").glob("*.json")) if (drafts / "records").exists() else True


def test_public_sync_prepares_source_free_material_and_resumes_to_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings(destination="public", mode="automatic"))
    registered = _register(drafts, catalog, settings)
    calls: list[str] = []

    monkeypatch.setattr(
        contribution_module,
        "inspect_managed_service",
        lambda: {"publicationPolicy": {"digest": POLICY_DIGEST}},
    )

    def publication(**value: object) -> dict[str, object]:
        operation = str(value["operation"])
        calls.append(operation)
        if operation == "publish":
            draft_path = Path(value["draft_path"])
            document = validate_publication_draft(json.loads(draft_path.read_text(encoding="utf-8")))
            assert document["rights"] == {
                "license": "CC0-1.0",
                "allowedUses": ["derive-method"],
                "hasAuthority": True,
            }
            assert "https://example.com/upstream-issue" in (draft_path.parent / "method.md").read_text(encoding="utf-8")
            return {
                "submissionRef": "submission:" + "1" * 32,
                "admissionState": "pending",
                "releaseRef": None,
                "reasonCodes": [],
                "statePath": str(draft_path) + ".state.json",
            }
        return {
            "submissionRef": "submission:" + "1" * 32,
            "admissionState": "active",
            "releaseRef": {
                "releaseId": "release:" + "2" * 32,
                "releaseDigest": "sha256:" + "4" * 64,
                "lineageId": load_draft(drafts, str(registered["draftRef"]))["lineageId"],
                "version": "1.0.0",
            },
            "reasonCodes": [],
            "statePath": str(value["state_path"]),
        }

    monkeypatch.setattr(contribution_module, "manage_publication", publication)

    first = sync_contributions(drafts)
    second = sync_contributions(drafts)

    assert first == {
        "schemaVersion": "limitless.method-sharing-sync/0.1",
        "status": "complete",
        "processed": 1,
        "published": 0,
        "withdrawn": 0,
        "attention": 0,
        "retryable": 0,
    }
    assert second["published"] == 1
    assert calls == ["publish", "status"]
    assert contribution_states(drafts)[str(registered["draftRef"])]["state"] == "published"


def test_policy_drift_pauses_without_sending_content(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings(destination="public", mode="automatic"))
    registered = _register(drafts, catalog, settings)
    monkeypatch.setattr(
        contribution_module,
        "inspect_managed_service",
        lambda: {"publicationPolicy": {"digest": "sha256:" + "9" * 64}},
    )
    monkeypatch.setattr(
        contribution_module,
        "manage_publication",
        lambda **_value: pytest.fail("policy drift must stop before publication"),
    )

    result = sync_contributions(drafts)

    assert result["attention"] == 1
    state = contribution_states(drafts)[str(registered["draftRef"])]
    assert state["state"] == "policy-attention"
    assert not (drafts / "publication").exists()

    # A policy returning to the old digest is not a substitute for renewed
    # owner authorization after the pause.
    result = sync_contributions(drafts)
    assert result["processed"] == 0

    assert (
        transition_contribution(
            drafts,
            draft_ref=str(registered["draftRef"]),
            destination="public",
            public_policy_digest=POLICY_DIGEST,
        )["status"]
        == "queued"
    )


def test_status_retry_never_resubmits_an_existing_publication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings(destination="public", mode="automatic"))
    registered = _register(drafts, catalog, settings)
    calls: list[str] = []
    state_path = str(drafts / "remote-state.json")
    monkeypatch.setattr(
        contribution_module,
        "inspect_managed_service",
        lambda: {"publicationPolicy": {"digest": POLICY_DIGEST}},
    )

    def publication(**value: object) -> dict[str, object]:
        operation = str(value["operation"])
        calls.append(operation)
        if operation == "publish":
            return {
                "submissionRef": "submission:" + "1" * 32,
                "admissionState": "pending",
                "releaseRef": None,
                "reasonCodes": [],
                "statePath": state_path,
            }
        if calls.count("status") == 1:
            raise contribution_module.AdapterError("temporary status failure")
        return {
            "submissionRef": "submission:" + "1" * 32,
            "admissionState": "active",
            "releaseRef": {
                "releaseId": "release:" + "2" * 32,
                "releaseDigest": "sha256:" + "4" * 64,
                "lineageId": load_draft(drafts, str(registered["draftRef"]))["lineageId"],
                "version": "1.0.0",
            },
            "reasonCodes": [],
            "statePath": state_path,
        }

    monkeypatch.setattr(contribution_module, "manage_publication", publication)

    assert sync_contributions(drafts)["processed"] == 1
    assert sync_contributions(drafts)["retryable"] == 1
    assert sync_contributions(drafts)["published"] == 1
    assert calls == ["publish", "status", "status"]


def test_superseded_pending_release_resolves_before_revision_publication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings(destination="public", mode="automatic"))
    first = _register(drafts, catalog, settings)
    first_ref = str(first["draftRef"])
    release_ref = {
        "releaseId": "release:" + "2" * 32,
        "releaseDigest": "sha256:" + "4" * 64,
        "lineageId": load_draft(drafts, first_ref)["lineageId"],
        "version": "1.0.0",
    }
    calls: list[str] = []
    revision_documents: list[dict[str, object]] = []
    monkeypatch.setattr(
        contribution_module,
        "inspect_managed_service",
        lambda: {"publicationPolicy": {"digest": POLICY_DIGEST}},
    )

    def publication(**value: object) -> dict[str, object]:
        operation = str(value["operation"])
        calls.append(operation)
        if operation == "status":
            return {
                "submissionRef": "submission:" + "1" * 32,
                "admissionState": "active",
                "releaseRef": release_ref,
                "reasonCodes": [],
                "statePath": str(value["state_path"]),
            }
        draft_path = Path(value["draft_path"])
        document = json.loads(draft_path.read_text(encoding="utf-8"))
        if document["lineage"]["version"] == "1.0.1":
            revision_documents.append(document)
            admission = "active"
            published_release: dict[str, object] | None = {**release_ref, "version": "1.0.1"}
        else:
            admission = "pending"
            published_release = None
        return {
            "submissionRef": "submission:" + "1" * 32,
            "admissionState": admission,
            "releaseRef": published_release,
            "reasonCodes": [],
            "statePath": str(draft_path) + ".state.json",
        }

    monkeypatch.setattr(contribution_module, "manage_publication", publication)
    assert sync_contributions(drafts)["processed"] == 1
    second = register_method(
        drafts,
        catalog,
        settings,
        {
            "name": "Lock-safe updates",
            "steps": ["Wait until the session is unlocked.", "Swap one validated tree."],
            "supersedes": first_ref,
        },
    )

    result = sync_contributions(drafts)

    assert result["processed"] == 2
    assert calls == ["publish", "status", "publish"]
    assert revision_documents[0]["lineage"]["releaseClass"] == "revision"
    assert revision_documents[0]["lineage"]["parents"] == [release_ref]
    assert revision_documents[0]["lineage"]["supersedes"] == release_ref
    assert contribution_states(drafts)[str(second["draftRef"])]["state"] == "published"
    with pytest.raises(contribution_module.ContributionError, match="current method revision"):
        transition_contribution(
            drafts,
            draft_ref=first_ref,
            destination="local",
            public_policy_digest=None,
        )


def test_per_method_transition_queues_public_and_withdraws_before_local(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings())
    registered = _register(drafts, catalog, settings)
    reference = str(registered["draftRef"])
    assert (
        transition_contribution(
            drafts,
            draft_ref=reference,
            destination="public",
            public_policy_digest=POLICY_DIGEST,
        )["status"]
        == "queued"
    )
    monkeypatch.setattr(
        contribution_module,
        "inspect_managed_service",
        lambda: {"publicationPolicy": {"digest": POLICY_DIGEST}},
    )

    def publication(**value: object) -> dict[str, object]:
        path = value.get("draft_path") or value.get("state_path")
        return {
            "submissionRef": "submission:" + "1" * 32,
            "admissionState": "active" if value["operation"] != "revoke" else "revoked",
            "releaseRef": {
                "releaseId": "release:" + "2" * 32,
                "releaseDigest": "sha256:" + "4" * 64,
                "lineageId": load_draft(drafts, reference)["lineageId"],
                "version": "1.0.0",
            },
            "reasonCodes": [],
            "statePath": str(path) + (".state.json" if value["operation"] == "publish" else ""),
        }

    monkeypatch.setattr(contribution_module, "manage_publication", publication)
    assert sync_contributions(drafts)["published"] == 1
    moved = transition_contribution(
        drafts,
        draft_ref=reference,
        destination="local",
        public_policy_digest=None,
    )
    assert moved["status"] == "withdrawal-queued"
    result = sync_contributions(drafts)
    assert result["withdrawn"] == 1
    state = contribution_states(drafts)[reference]
    assert state["destination"] == "local"
    assert state["state"] == "local"


def test_scheduler_uses_only_fixed_local_arguments(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: list[object] = []

    class Process:
        def __init__(self, command: list[str], **options: object) -> None:
            captured.extend([command, options])

    monkeypatch.setattr(contribution_module.subprocess, "Popen", Process)

    assert schedule_contribution_sync(tmp_path / "drafts", activity_path=tmp_path / "activity.json")
    command = captured[0]
    assert isinstance(command, list)
    assert command[1:4] == ["-m", "limitless_omarchy.cli", "contribution-sync"]
    assert "Lock-safe updates" not in json.dumps(captured)
    assert captured[1]["start_new_session"] is True


def test_mcp_registration_requires_only_name_and_steps_and_returns_no_contents(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    drafts, catalog, settings = _paths(tmp_path)
    activity = tmp_path / "activity.json"
    save_settings(settings, _settings())
    monkeypatch.setattr(mcp_server, "schedule_contribution_sync", lambda *_args, **_kwargs: True)

    tools = handle_message(
        catalog,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        settings_path=settings,
        drafts_path=drafts,
        activity_path=activity,
    )
    assert tools is not None
    assert [item["name"] for item in tools["result"]["tools"]] == [
        "omarchy_query_before_customization",
        REGISTER_METHOD_TOOL_NAME,
    ]
    assert tools["result"]["tools"][0]["inputSchema"]["required"] == ["objective"]
    response = handle_message(
        catalog,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": REGISTER_METHOD_TOOL_NAME,
                "arguments": {"name": "Small method", "steps": "Do the smallest useful thing."},
            },
        },
        settings_path=settings,
        drafts_path=drafts,
        activity_path=activity,
    )

    assert response is not None
    result = response["result"]["structuredContent"]
    assert set(result) == {"schemaVersion", "status", "draftRef", "destination"}
    assert result["status"] == "registered"
    assert "Do the smallest" not in json.dumps(result)
    assert activity_summary(activity)["lifecycle"]["drafts"] == 1


def test_unsafe_draft_registry_is_rejected(tmp_path: Path) -> None:
    _drafts, catalog, settings = _paths(tmp_path)
    save_settings(settings, _settings())
    target = tmp_path / "elsewhere"
    target.mkdir()
    link = tmp_path / "draft-link"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(DraftError, match="non-symlink"):
        register_method(link, catalog, settings, {"name": "Unsafe", "steps": "Do not write."})
