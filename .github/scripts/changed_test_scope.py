#!/usr/bin/env python3
"""Plan and optionally run the smallest safe test scope for changed files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath

ALL_TESTS = (
    "tests/test_adapter.py",
    "tests/test_agent_connection.py",
    "tests/test_changed_test_scope.py",
    "tests/test_plugin_contract.py",
)
DOC_PREFIXES = ("docs/",)
FULL_PATHS = {
    ".github/workflows/ci.yml",
    "MANIFEST.in",
    "pyproject.toml",
    "scripts/verify-distribution.py",
}


def _git_paths(root: Path, arguments: Sequence[str]) -> list[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [part.decode("utf-8") for part in result.stdout.split(b"\0") if part]


def changed_paths(root: Path, *, base: str | None, head: str | None) -> list[str]:
    if base:
        return sorted(set(_git_paths(root, ["diff", "--name-only", "-z", f"{base}...{head or 'HEAD'}"])))
    paths: set[str] = set()
    paths.update(_git_paths(root, ["diff", "--name-only", "-z"]))
    paths.update(_git_paths(root, ["diff", "--cached", "--name-only", "-z"]))
    paths.update(_git_paths(root, ["ls-files", "--others", "--exclude-standard", "-z"]))
    return sorted(paths)


def plan_changes(paths: Iterable[str]) -> dict[str, object]:
    normalized = sorted({PurePosixPath(path).as_posix().removeprefix("./") for path in paths if path})
    tests: set[str] = set()
    reasons: list[str] = []
    full = False
    package_gate = False
    omarchy_contract = False
    visual_gate = False

    for raw in normalized:
        path = PurePosixPath(raw)
        if raw in FULL_PATHS:
            full = True
            package_gate = True
            omarchy_contract = True
            reasons.append(f"shared build or CI contract changed: {raw}")
        elif raw == ".github/scripts/changed_test_scope.py":
            tests.add("tests/test_changed_test_scope.py")
            reasons.append("test-scope planner changed")
        elif raw.startswith(("plugin/", "tests/runtime/")):
            tests.add("tests/test_plugin_contract.py")
            package_gate = True
            omarchy_contract = True
            visual_gate = path.suffix == ".qml"
            reasons.append(f"Omarchy UI contract changed: {raw}")
        elif raw == "manifest.json":
            tests.add("tests/test_plugin_contract.py")
            package_gate = True
            omarchy_contract = True
            reasons.append("plugin manifest changed")
        elif raw == "scripts/limitless-omarchy-runtime" or raw == "scripts/smoke-omarchy-panel":
            tests.add("tests/test_plugin_contract.py")
            package_gate = True
            reasons.append(f"panel runtime changed: {raw}")
        elif raw == "src/limitless_omarchy/agent_connection.py":
            tests.add("tests/test_agent_connection.py")
            package_gate = True
            reasons.append("agent connection adapter changed")
        elif raw.startswith("src/limitless_omarchy/") and path.suffix == ".py":
            tests.add("tests/test_adapter.py")
            package_gate = True
            reasons.append(f"Python adapter changed: {raw}")
        elif raw.startswith("examples/"):
            tests.add("tests/test_adapter.py")
            package_gate = True
            reasons.append(f"bundled example changed: {raw}")
        elif raw in ALL_TESTS:
            tests.add(raw)
            reasons.append(f"test changed: {raw}")
        elif raw == "README.md" or raw == "SECURITY.md" or raw.startswith(DOC_PREFIXES):
            reasons.append(f"documentation-only change: {raw}")
        elif raw in {".gitignore", ".gitattributes", "LICENSE", "NOTICE"}:
            reasons.append(f"repository metadata changed: {raw}")
        else:
            full = True
            package_gate = True
            omarchy_contract = True
            reasons.append(f"unclassified change requires fail-safe full coverage: {raw}")

    selected = list(ALL_TESTS) if full else sorted(tests)
    return {
        "schemaVersion": "limitless.omarchy-changed-test-scope.v1",
        "changedPaths": normalized,
        "mode": "full" if full else "targeted" if selected else "none",
        "reasons": sorted(set(reasons)),
        "tests": selected,
        "packageGateRequired": package_gate,
        "omarchyContractRequired": omarchy_contract,
        "visualGateRecommended": visual_gate,
    }


def run_plan(root: Path, plan: dict[str, object]) -> None:
    tests = [str(path) for path in plan["tests"]]
    if tests:
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *tests],
            cwd=root,
            check=True,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--run", action="store_true")
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    paths = arguments.path or changed_paths(root, base=arguments.base, head=arguments.head)
    plan = plan_changes(paths)
    print(json.dumps(plan, indent=2, sort_keys=True))
    if arguments.run:
        run_plan(root, plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
