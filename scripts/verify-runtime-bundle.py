#!/usr/bin/env python3
"""Verify the release-pinned runtime bundle without third-party imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

SCHEMA = "limitless.omarchy-runtime-bundle/0.1"
LOCK_PATTERN = re.compile(
    r"[A-Za-z0-9_.-]+==[^\s\\]+(?:\s+--hash=sha256:[0-9a-f]{64})+",
)


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _safe_file(root: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        raise TypeError("bundle paths must be strings")
    logical = PurePosixPath(relative)
    if logical.is_absolute() or ".." in logical.parts or not logical.parts:
        raise ValueError(f"unsafe bundle path: {relative!r}")
    path = root.joinpath(*logical.parts)
    current = root
    for part in logical.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"bundle path must not traverse a symbolic link: {relative}")
    if not path.is_file():
        raise ValueError(f"bundle file is missing: {relative}")
    return path


def _verify_digest(path: Path, expected: object) -> None:
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError(f"invalid SHA-256 declaration for {path.name}")
    observed = _digest(path)
    if observed != expected:
        raise ValueError(f"SHA-256 mismatch for {path.name}: expected {expected}, observed {observed}")


def _logical_requirements(text: str) -> list[str]:
    logical: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pending = f"{pending} {line}".strip()
        if pending.endswith("\\"):
            pending = pending[:-1].strip()
            continue
        logical.append(pending)
        pending = ""
    if pending:
        raise ValueError("requirements lock ends in an incomplete continuation")
    return logical


def _verify_lock(path: Path) -> None:
    requirements = _logical_requirements(path.read_text(encoding="utf-8"))
    if not requirements:
        raise ValueError("requirements lock is empty")
    for requirement in requirements:
        if not LOCK_PATTERN.fullmatch(requirement):
            raise ValueError(f"unlocked or unsupported requirement: {requirement}")


def _normal_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _wheel_metadata(path: Path) -> tuple[str, str, list[str]]:
    with zipfile.ZipFile(path) as wheel:
        for name in wheel.namelist():
            logical = PurePosixPath(name)
            if logical.is_absolute() or ".." in logical.parts:
                raise ValueError(f"unsafe member in {path.name}: {name}")
        metadata_names = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError(f"wheel must contain exactly one METADATA file: {path.name}")
        metadata = BytesParser().parsebytes(wheel.read(metadata_names[0]))
    return metadata["Name"], metadata["Version"], metadata.get_all("Requires-Dist", [])


def _verify_plugin_sources(root: Path, wheel_path: Path) -> None:
    source_root = root / "src" / "limitless_omarchy"
    expected = {
        path.relative_to(source_root).as_posix(): path.read_bytes()
        for path in source_root.rglob("*.py")
        if path.is_file() and not path.is_symlink()
    }
    with zipfile.ZipFile(wheel_path) as wheel:
        prefix = "limitless_omarchy/"
        observed = {
            name.removeprefix(prefix): wheel.read(name)
            for name in wheel.namelist()
            if name.startswith(prefix) and name.endswith(".py")
        }
    if observed.keys() != expected.keys():
        raise ValueError("plugin wheel Python file set does not match the release source")
    mismatches = sorted(name for name in expected if observed[name] != expected[name])
    if mismatches:
        raise ValueError(f"plugin wheel does not match release source: {', '.join(mismatches)}")


def verify(root: Path) -> list[Path]:
    root = root.resolve(strict=True)
    manifest_path = _safe_file(root, "runtime/bundle.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported runtime bundle schema")

    requirements = manifest.get("requirements")
    if not isinstance(requirements, dict):
        raise TypeError("runtime bundle requirements declaration is missing")
    lock_path = _safe_file(root, requirements.get("path"))
    _verify_digest(lock_path, requirements.get("sha256"))
    _verify_lock(lock_path)

    packages = manifest.get("packages")
    if not isinstance(packages, list) or len(packages) != 2:
        raise ValueError("runtime bundle must declare the core and adapter wheels")
    wheel_paths: list[Path] = []
    seen: set[str] = set()
    for package in packages:
        if not isinstance(package, dict):
            raise TypeError("runtime package declarations must be objects")
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise TypeError("runtime package name and version must be strings")
        normalized = _normal_name(name)
        if normalized in seen:
            raise ValueError(f"duplicate runtime package: {name}")
        seen.add(normalized)
        wheel_path = _safe_file(root, package.get("path"))
        if wheel_path.suffix != ".whl":
            raise ValueError(f"runtime package is not a wheel: {wheel_path.name}")
        _verify_digest(wheel_path, package.get("sha256"))
        wheel_name, wheel_version, dependencies = _wheel_metadata(wheel_path)
        if _normal_name(wheel_name) != normalized or wheel_version != version:
            raise ValueError(f"wheel identity mismatch for {wheel_path.name}")
        if normalized == "limitless-omarchy":
            unconditional = [item for item in dependencies if "; extra ==" not in item]
            if unconditional:
                raise ValueError("adapter wheel must not trigger dependency resolution")
            _verify_plugin_sources(root, wheel_path)
        wheel_paths.append(wheel_path)

    if seen != {"limitless-library", "limitless-omarchy"}:
        raise ValueError("runtime bundle package set is not recognized")
    return wheel_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--print-wheel-paths0", action="store_true")
    arguments = parser.parse_args()
    try:
        wheels = verify(arguments.root)
    except (OSError, TypeError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        print(f"runtime bundle verification failed: {error}", file=sys.stderr)
        return 2
    if arguments.print_wheel_paths0:
        sys.stdout.buffer.write(b"\0".join(str(path).encode() for path in wheels) + b"\0")
    else:
        print(f"verified runtime bundle: {len(wheels)} wheels and one hash-locked dependency graph")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
