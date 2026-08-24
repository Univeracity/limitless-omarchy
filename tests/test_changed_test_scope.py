from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "changed_test_scope.py"
SPEC = importlib.util.spec_from_file_location("changed_test_scope", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
SCOPE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCOPE)


def plan(*paths: str) -> dict[str, object]:
    return SCOPE.plan_changes(paths)


def test_service_change_selects_adapter_tests_and_package_gate() -> None:
    result = plan("src/limitless_omarchy/service.py")

    assert result["mode"] == "targeted"
    assert result["tests"] == ["tests/test_adapter.py"]
    assert result["packageGateRequired"] is True
    assert result["omarchyContractRequired"] is False


def test_agent_connection_change_selects_its_focused_tests_and_package_gate() -> None:
    result = plan("src/limitless_omarchy/agent_connection.py")

    assert result["mode"] == "targeted"
    assert result["tests"] == ["tests/test_agent_connection.py"]
    assert result["packageGateRequired"] is True


def test_contribution_change_selects_its_focused_tests() -> None:
    result = plan("src/limitless_omarchy/contributions.py")

    assert result["mode"] == "targeted"
    assert result["tests"] == ["tests/test_contributions.py"]
    assert result["packageGateRequired"] is True


def test_mcp_change_selects_query_and_contribution_contracts() -> None:
    result = plan("src/limitless_omarchy/mcp_server.py")

    assert result["tests"] == ["tests/test_adapter.py", "tests/test_contributions.py"]


def test_qml_change_selects_plugin_and_visual_contracts() -> None:
    result = plan("plugin/PanelContents.qml")

    assert result["tests"] == ["tests/test_plugin_contract.py"]
    assert result["omarchyContractRequired"] is True
    assert result["visualGateRecommended"] is True


def test_catalog_move_and_preview_select_only_their_release_contracts() -> None:
    result = plan("examples/catalog/legacy.json", "catalog/current.json", "preview.png")

    assert result["mode"] == "targeted"
    assert result["tests"] == ["tests/test_adapter.py", "tests/test_plugin_contract.py"]
    assert result["packageGateRequired"] is True
    assert result["omarchyContractRequired"] is True
    assert result["visualGateRecommended"] is True


def test_visual_asset_selects_plugin_release_and_visual_contracts() -> None:
    result = plan("assets/univeracity-logo.png")

    assert result["mode"] == "targeted"
    assert result["tests"] == ["tests/test_plugin_contract.py"]
    assert result["packageGateRequired"] is True
    assert result["omarchyContractRequired"] is True
    assert result["visualGateRecommended"] is True


def test_documentation_change_does_not_run_product_tests() -> None:
    result = plan("docs/ARCHITECTURE.md")

    assert result["mode"] == "none"
    assert result["tests"] == []


def test_build_contract_change_fails_safe_to_full_suite() -> None:
    result = plan("pyproject.toml")

    assert result["mode"] == "full"
    assert result["tests"] == list(SCOPE.ALL_TESTS)
    assert result["packageGateRequired"] is True
    assert result["omarchyContractRequired"] is True


def test_runtime_bundle_change_selects_release_contract_without_expanding_unnecessarily() -> None:
    result = plan("runtime/requirements.lock")

    assert result["mode"] == "targeted"
    assert result["tests"] == ["tests/test_plugin_contract.py"]
    assert result["packageGateRequired"] is True
    assert result["omarchyContractRequired"] is True


def test_unknown_path_fails_safe_and_output_is_serializable() -> None:
    result = plan("operations/new-runtime.conf")

    assert result["mode"] == "full"
    json.dumps(result, sort_keys=True)
