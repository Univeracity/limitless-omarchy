from __future__ import annotations

import importlib.util
import io
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("wheel_inventory", ROOT / "scripts/inventory-release-wheel.py")
assert SPEC is not None and SPEC.loader is not None
INVENTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INVENTORY)
WHEEL = ROOT / "runtime/wheels/limitless_omarchy-0.2.2-py3-none-any.whl"
INFO = "limitless_omarchy-0.2.2.dist-info/"
COMMIT = "c2e303ba63024ee4e1c4cbc595488fa9dfef7170"


@pytest.fixture(scope="module")
def baseline():
    archive_bytes = subprocess.check_output(["git", "-C", str(ROOT), "archive", COMMIT])
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        source = {member.name: archive.extractfile(member).read() for member in archive.getmembers() if member.isfile()}
    with zipfile.ZipFile(WHEEL) as wheel:
        metadata = {name: wheel.read(INFO + name) for name in ("METADATA", "entry_points.txt", "top_level.txt")}
    return source, metadata


def changed_wheel(path: Path, *, changes: dict[str, bytes] | None = None, omit: str | None = None) -> Path:
    changes = changes or {}
    with zipfile.ZipFile(WHEEL) as original, zipfile.ZipFile(path, "w") as changed:
        for member in original.infolist():
            if member.filename != omit:
                changed.writestr(member, changes.get(member.filename, original.read(member.filename)))
        for name, data in changes.items():
            if name not in original.namelist():
                changed.writestr(name, data)
    return path


def verify(path: Path, baseline):
    source, metadata = baseline
    return INVENTORY.verify_contents(path, source, metadata, backend_version="83.0.0")


def test_existing_wheel_has_a_complete_source_and_generation_mapping(baseline) -> None:
    files = verify(WHEEL, baseline)
    assert len(files) == 19
    assert {file["sourceMapping"]["kind"] for file in files} == {
        "exact-source",
        "exact-regenerated-metadata",
        "checked-backend-format",
        "complete-archive-record",
    }
    assert all(file["installationScheme"] == "purelib" for file in files)


@pytest.mark.parametrize("path", ["unexpected.pth", "limitless_omarchy-0.2.2.data/scripts/unexpected"])
def test_extra_installed_file_outside_the_package_is_rejected(tmp_path: Path, baseline, path: str) -> None:
    changed = changed_wheel(tmp_path / "extra.whl", changes={path: b"unexpected payload\n"})
    with pytest.raises(ValueError, match="complete wheel file set"):
        verify(changed, baseline)


@pytest.mark.parametrize(
    "path", [INFO + "METADATA", INFO + "entry_points.txt", INFO + "WHEEL", INFO + "licenses/NOTICE"]
)
def test_changed_installed_metadata_or_license_is_rejected(tmp_path: Path, baseline, path: str) -> None:
    changed = changed_wheel(tmp_path / "changed.whl", changes={path: b"changed metadata\n"})
    with pytest.raises(ValueError, match="differs from its source"):
        verify(changed, baseline)


def test_missing_metadata_and_duplicate_member_are_rejected(tmp_path: Path, baseline) -> None:
    changed = changed_wheel(tmp_path / "missing.whl", omit=INFO + "entry_points.txt")
    with pytest.raises(ValueError, match="complete wheel file set"):
        verify(changed, baseline)
    changed = changed_wheel(tmp_path / "duplicate.whl")
    with zipfile.ZipFile(changed, "a") as wheel, pytest.warns(UserWarning, match="Duplicate name"):
        wheel.writestr(INFO + "entry_points.txt", b"changed\n")
    with pytest.raises(ValueError, match="duplicate member"):
        verify(changed, baseline)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "hash", "size", "self-entry"])
def test_record_must_bind_every_actual_member(tmp_path: Path, baseline, mutation: str) -> None:
    with zipfile.ZipFile(WHEEL) as original:
        lines = original.read(INFO + "RECORD").decode().splitlines()
    if mutation == "missing":
        lines = lines[1:]
    elif mutation == "duplicate":
        lines.append(lines[0])
    elif mutation == "hash":
        fields = lines[0].split(",")
        fields[1] = "sha256=" + "A" * 43
        lines[0] = ",".join(fields)
    elif mutation == "size":
        fields = lines[0].split(",")
        fields[2] = "0"
        lines[0] = ",".join(fields)
    else:
        lines[-1] = INFO + "RECORD,sha256=wrong,1"
    changed = changed_wheel(tmp_path / "record.whl", changes={INFO + "RECORD": ("\n".join(lines) + "\n").encode()})
    with pytest.raises(ValueError, match="RECORD"):
        verify(changed, baseline)
