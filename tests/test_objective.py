from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import limitless_library
import pytest
from limitless_library.method_capture import register_method as capture_method
from limitless_library.objective_query import ObjectiveQueryError, load_query_record
from limitless_library.query_policy import default_query_policy, load_query_policy, save_query_policy
from limitless_library.service_connector import ServiceUnavailableError

from limitless_omarchy.drafts import register_method
from limitless_omarchy.objective import objective_engine, owner_query_policy_path, query_policy_result
from limitless_omarchy.settings import default_settings, save_settings

ROOT = Path(__file__).parents[1]


def shell_unavailable(argv):
    return subprocess.CompletedProcess(argv, 1, "", "")


def make_engine(tmp_path: Path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    settings = tmp_path / "settings.json"
    save_settings(settings, default_settings())
    drafts = tmp_path / "drafts"
    engine = objective_engine(
        catalog,
        settings_path=settings,
        drafts_path=drafts,
        method_store=tmp_path / "methods",
        runner=shell_unavailable,
    )
    return engine, catalog, settings, drafts


def method_input(**extra):
    return {
        "name": "Stable Wi-Fi selection",
        "summary": "Keep Wi-Fi rows stable during password entry.",
        "steps": ["Keep the selected network identity separate from changing list position."],
        "verify": ["Refresh the network list while entering a password and confirm the selected identity."],
        **extra,
    }


def test_old_native_registration_is_immediately_searchable_and_supersession_refreshes_same_engine(
    tmp_path: Path,
) -> None:
    engine, catalog, settings, drafts = make_engine(tmp_path)
    objective = {"objective": "Stable Wi-Fi selection during password entry"}
    assert engine.check(objective)["treatment"] == "abstain"
    first = register_method(drafts, catalog, settings, method_input())
    record = drafts / "records" / (first["draftRef"].split(":")[1] + ".json")
    original = record.read_bytes()
    view = engine.check(objective)
    assert view["origin"] == "local" and view["treatment"] == "source-free-method"
    assert view["selection"]["title"] == "Stable Wi-Fi selection"
    saved = load_query_record(settings.parent / "queries", view["queryRef"])
    assert "omarchy-plugin-schema-v1" in saved["receiver"]["constraints"]
    assert saved["receiver"]["toolchain"]["omarchyShell"] == "unavailable"
    assert view["assurance"]["outcome"] == "not-asserted"
    revised = register_method(
        drafts,
        catalog,
        settings,
        method_input(
            supersedes=first["draftRef"],
            steps=["Pin the network identity; ignore list reordering while accepting a password."],
        ),
    )
    after = engine.check(objective)
    assert after["selection"]["reference"] != view["selection"]["reference"]
    assert revised["draftRef"].split(":")[1].lower() in after["selection"]["reference"]
    assert record.read_bytes() == original


def test_native_path_also_finds_original_core_captures_without_copying_them(tmp_path: Path) -> None:
    engine, _, settings, _ = make_engine(tmp_path)
    method_store = tmp_path / "methods"
    capture_method(
        method_store,
        {
            "title": "Independent receiver adoption",
            "taskKind": "receiver-verification",
            "method": {
                "summary": "Observe receiver adoption independently.",
                "steps": [
                    {
                        "index": 1,
                        "instruction": "Observe the receiver directly.",
                        "check": "fact-present",
                        "expected": "Receiver evidence is present.",
                    }
                ],
                "constraints": [],
                "evaluation": ["Receiver evidence supports the result."],
                "limitations": [],
            },
            "observedOutcome": "Receiver checks passed.",
            "platform": "any",
        },
    )
    before = {str(path.relative_to(method_store)): path.read_bytes() for path in method_store.rglob("*.json")}
    view = engine.check({"objective": "Independent receiver adoption"})
    assert view["selection"]["reference"].startswith("offer:captured.")
    assert {str(path.relative_to(method_store)): path.read_bytes() for path in method_store.rglob("*.json")} == before
    assert not owner_query_policy_path(settings).exists()


def test_damaged_native_projection_is_not_served_from_a_warm_snapshot(tmp_path: Path) -> None:
    engine, catalog, settings, drafts = make_engine(tmp_path)
    register_method(drafts, catalog, settings, method_input())
    assert engine.check({"objective": "Stable Wi-Fi selection"})["treatment"] == "source-free-method"
    next(catalog.glob("*/capsule.json")).write_text("{}")
    after = engine.check({"objective": "Stable Wi-Fi selection"})
    assert after["treatment"] == "abstain" and after["coverage"]["local"] == "partial"


def test_query_consent_is_separate_reloadable_and_never_changes_old_settings(tmp_path: Path) -> None:
    engine, _, settings, _ = make_engine(tmp_path)
    original = settings.read_bytes()
    calls = []

    class UnavailableService:
        def build_query(self, **arguments):
            calls.append("build")
            return arguments

        def query(self, query):
            calls.append("post")
            raise ServiceUnavailableError("unavailable")

    engine._factory = lambda: UnavailableService()
    assert query_policy_result(settings)["executionMode"] == "local"
    assert engine.check({"objective": "Database transactions"})["coverage"]["service"] == "disabled"
    assert calls == []
    query_policy_result(settings, execution_mode="service")
    assert settings.read_bytes() == original
    assert engine.check({"objective": "Database transactions"})["coverage"]["service"] == "unavailable"
    assert calls == ["build", "post"]
    query_policy_result(settings, execution_mode="local")
    assert engine.check({"objective": "Database transactions"})["coverage"]["service"] == "disabled"
    assert calls == ["build", "post"] and settings.read_bytes() == original


def test_explicit_remote_receiver_does_not_inherit_native_host_facts(tmp_path: Path) -> None:
    engine, catalog, settings, drafts = make_engine(tmp_path)
    register_method(drafts, catalog, settings, method_input())
    policy = default_query_policy()
    policy["serviceReceiver"] = {
        "receiverId": "receiver:remote",
        "allowedUse": "derive-method",
        "interfaces": ["limitless.mcp/v1"],
        "execution": {"platform": "linux", "architecture": "x86_64", "runtime": "python", "version": "3.12"},
        "targets": [
            {
                "id": "target:remote",
                "platform": "windows",
                "architecture": "x86_64",
                "runtime": "any",
                "versionRange": "any",
                "interfaces": ["limitless.mcp/v1"],
            }
        ],
        "compatibilityMode": "all-targets",
        "selectedTarget": None,
    }
    save_query_policy(owner_query_policy_path(settings), policy)
    view = engine.check({"objective": "Stable Wi-Fi selection"})
    assert view["treatment"] == "abstain"
    saved = load_query_record(settings.parent / "queries", view["queryRef"])
    assert saved["receiver"] == {"constraints": ["windows"], "toolchain": {}}


@pytest.mark.parametrize("extra", [{"executionMode": "service"}, {"catalog": "/tmp/other"}, {"receiver": {}}])
def test_model_cannot_override_host_configuration(tmp_path: Path, extra: dict) -> None:
    engine, _, settings, _ = make_engine(tmp_path)
    with pytest.raises(ObjectiveQueryError):
        engine.check({"objective": "Stable Wi-Fi selection", **extra})
    assert not owner_query_policy_path(settings).exists()


def test_real_native_stdio_session_registers_then_checks_and_keeps_legacy_tools(tmp_path: Path) -> None:
    _, catalog, settings, drafts = make_engine(tmp_path)
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "native-objective-test", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "limitless_register_method", "arguments": method_input()},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "limitless_check", "arguments": {"objective": "Stable Wi-Fi selection"}},
        },
    ]
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(Path(limitless_library.__file__).parents[1])]),
    }
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "limitless_omarchy.mcp_server",
            "--catalog",
            str(catalog),
            "--settings-path",
            str(settings),
            "--drafts-path",
            str(drafts),
            "--method-store",
            str(tmp_path / "methods"),
        ],
        input="".join(json.dumps(message) + "\n" for message in messages),
        capture_output=True,
        text=True,
        check=True,
        env=environment,
    )
    responses = {value["id"]: value for value in map(json.loads, process.stdout.splitlines())}
    names = {tool["name"] for tool in responses[2]["result"]["tools"]}
    assert names == {
        "limitless_query_before_work",
        "omarchy_query_before_customization",
        "limitless_register_method",
        "limitless_check",
    }
    assert responses[3]["result"]["structuredContent"]["status"] == "registered"
    assert responses[4]["result"]["structuredContent"]["treatment"] == "source-free-method"
    assert load_query_policy(owner_query_policy_path(settings))["executionMode"] == "local"


def run_cli(arguments: list[str], payload: dict | None = None):
    environment = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR") if key in os.environ}
    environment["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(Path(limitless_library.__file__).parents[1])])
    process = subprocess.run(
        [sys.executable, "-m", "limitless_omarchy.cli", *arguments],
        input=None if payload is None else json.dumps(payload) + "\n",
        capture_output=True,
        text=True,
        check=True,
        env=environment,
    )
    return json.loads(process.stdout)


def test_cli_check_and_search_policy_preserve_legacy_settings_and_receiver_configuration(tmp_path: Path) -> None:
    _, catalog, settings, drafts = make_engine(tmp_path)
    register_method(drafts, catalog, settings, method_input())
    original = settings.read_bytes()
    result = run_cli(
        [
            "check",
            "--catalog",
            str(catalog),
            "--settings-path",
            str(settings),
            "--drafts-path",
            str(drafts),
            "--method-store",
            str(tmp_path / "methods"),
        ],
        {"objective": "Stable Wi-Fi selection"},
    )
    assert result["treatment"] == "source-free-method"
    policy = default_query_policy()
    policy["localReceiver"] = {"constraints": ["linux"], "toolchain": {"python": "3.12"}}
    save_query_policy(owner_query_policy_path(settings), policy)
    result = run_cli(
        ["query-policy-apply", "--settings-path", str(settings)],
        {
            "schemaVersion": "limitless.omarchy-query-policy-input/1.0",
            "executionMode": "service",
        },
    )
    assert result["saved"] and result["executionMode"] == "service"
    assert settings.read_bytes() == original
    saved = load_query_policy(owner_query_policy_path(settings))
    assert saved == {**policy, "executionMode": "service"}


def test_old_panel_state_wire_is_unchanged_and_new_overview_is_separately_versioned(tmp_path: Path) -> None:
    _, _, settings, drafts = make_engine(tmp_path)
    arguments = [
        "--settings-path",
        str(settings),
        "--drafts-path",
        str(drafts),
        "--state-dir",
        str(tmp_path / "agents"),
        "--activity-path",
        str(tmp_path / "activity.json"),
    ]
    old = run_cli(["panel-state", *arguments])
    assert old["schemaVersion"] == "limitless.omarchy-panel-state/0.1"
    assert set(old) == {"schemaVersion", "status", "settings", "drafts", "agents", "stats"}
    assert not owner_query_policy_path(settings).exists()
    new = run_cli(["panel-overview", *arguments])
    assert new["schemaVersion"] == "limitless.omarchy-panel-state/0.2"
    assert new["queryPolicy"]["executionMode"] == "local"
    assert set(new) == set(old) | {"queryPolicy"}
    assert not owner_query_policy_path(settings).exists()


def test_panel_and_agent_share_continuations_when_config_and_data_roots_differ(tmp_path: Path) -> None:
    config = tmp_path / "config"
    data = tmp_path / "data"
    config.mkdir(mode=0o700)
    data.mkdir(mode=0o700)
    catalog = data / "catalog"
    catalog.mkdir()
    settings = config / "settings.json"
    save_settings(settings, default_settings())
    drafts = data / "drafts"
    register_method(drafts, catalog, settings, method_input())
    agent = objective_engine(
        catalog, settings_path=settings, drafts_path=drafts, method_store=tmp_path / "methods", runner=shell_unavailable
    )
    view = agent.check({"objective": "Stable Wi-Fi selection"})
    assert load_query_record(data / "queries", view["queryRef"])["localMatch"] is not None
    assert not (config / "queries").exists()
