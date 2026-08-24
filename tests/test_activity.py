from __future__ import annotations

import json
from pathlib import Path

from limitless_omarchy.activity import (
    SCHEMA_VERSION,
    activity_summary,
    record_agents,
    record_lifecycle,
    record_query,
    record_service,
)


def test_missing_activity_is_an_available_empty_projection(tmp_path: Path) -> None:
    summary = activity_summary(tmp_path / "activity.json")

    assert summary["available"] is True
    assert summary["privacy"] == "aggregate-only-local"
    assert summary["queries"]["total"] == 0
    assert summary["updatedAt"] is None


def test_query_counters_retain_no_result_material(tmp_path: Path) -> None:
    path = tmp_path / "private" / "activity.json"
    result = {
        "disposition": "source-free-method",
        "objective": "never persist this objective",
        "decision": {"selected": {"capsule": {"id": "capsule:private"}}},
    }

    assert record_query(path, result, channel="local")
    assert record_query(path, {"disposition": "abstain", "reason": "private-reason"}, channel="service")
    assert record_query(path, {"treatment": "exact-adoption", "selected": {"private": True}}, channel="general")

    raw = path.read_text(encoding="utf-8")
    stored = json.loads(raw)
    assert stored["schemaVersion"] == SCHEMA_VERSION
    assert stored["queries"] == {
        "total": 3,
        "local": 1,
        "service": 1,
        "general": 1,
        "exactComponents": 1,
        "sourceFreeMethods": 1,
        "abstentions": 1,
    }
    assert "objective" not in raw
    assert "capsule:private" not in raw
    assert "private-reason" not in raw
    assert path.stat().st_mode & 0o077 == 0


def test_unknown_query_outcome_is_not_mislabeled_as_an_abstention(tmp_path: Path) -> None:
    path = tmp_path / "activity.json"

    assert not record_query(path, {"decision": "unexpected"}, channel="service")
    assert not path.exists()


def test_inconsistent_query_totals_are_rejected_without_repair(tmp_path: Path) -> None:
    path = tmp_path / "activity.json"
    value = {
        "schemaVersion": SCHEMA_VERSION,
        "queries": {
            "total": 2,
            "local": 1,
            "service": 0,
            "general": 0,
            "exactComponents": 0,
            "sourceFreeMethods": 1,
            "abstentions": 0,
        },
        "lifecycle": {
            "drafts": 0,
            "reviews": 0,
            "installs": 0,
            "adoptions": 0,
            "publications": 0,
            "withdrawals": 0,
        },
        "agents": {"connected": 0, "attention": 0},
        "serviceConnected": False,
        "updatedAt": None,
    }
    original = json.dumps(value)
    path.write_text(original, encoding="utf-8")

    assert activity_summary(path)["available"] is False
    assert not record_query(path, {"disposition": "abstain"}, channel="local")
    assert path.read_text(encoding="utf-8") == original


def test_lifecycle_agent_and_service_projection(tmp_path: Path) -> None:
    path = tmp_path / "activity.json"

    assert record_lifecycle(path, "review")
    assert record_lifecycle(path, "install")
    assert record_lifecycle(path, "adoption")
    assert record_lifecycle(path, "publication")
    assert record_lifecycle(path, "withdrawal")
    assert record_agents(
        path,
        {
            "connections": [
                {"agent": "codex", "status": "connected"},
                {"agent": "claude", "status": "attention", "reason": "private"},
                {"agent": "grok", "status": "disconnected"},
            ]
        },
    )
    assert record_service(path, connected=True)

    summary = activity_summary(path)
    assert summary["lifecycle"] == {
        "drafts": 0,
        "reviews": 1,
        "installs": 1,
        "adoptions": 1,
        "publications": 1,
        "withdrawals": 1,
    }
    assert summary["agents"] == {"connected": 1, "attention": 1}
    assert summary["serviceConnected"] is True


def test_corrupt_or_symlinked_state_is_not_overwritten(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not-json", encoding="utf-8")

    assert not record_lifecycle(corrupt, "adoption")
    assert corrupt.read_text(encoding="utf-8") == "not-json"
    assert activity_summary(corrupt)["available"] is False

    target = tmp_path / "target.json"
    target.write_text("leave-me", encoding="utf-8")
    link = tmp_path / "activity.json"
    link.symlink_to(target)
    assert not record_query(link, {"disposition": "exact-component"}, channel="local")
    assert target.read_text(encoding="utf-8") == "leave-me"

    dangling = tmp_path / "dangling.json"
    dangling.symlink_to(tmp_path / "missing-target.json")
    assert not record_lifecycle(dangling, "review")
    assert dangling.is_symlink()
    assert not (tmp_path / "missing-target.json").exists()
