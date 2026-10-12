from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "read-clipboard.py"
SPEC = importlib.util.spec_from_file_location("read_clipboard", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
CLIPBOARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIPBOARD)


def test_normal_text_and_unicode_round_trip() -> None:
    value = CLIPBOARD.read_bounded([sys.executable, "-c", "print('café 😀', end='')"])
    assert CLIPBOARD.decode_text(value) == "café 😀"
    assert CLIPBOARD.decode_text(b"first\r\nsecond\tthird") == "first second third"


def test_fast_unlimited_producer_is_rejected_without_collecting_its_output() -> None:
    started = time.monotonic()
    with pytest.raises(CLIPBOARD.ClipboardError, match="2 KiB"):
        CLIPBOARD.read_bounded([sys.executable, "-c", "import os\nwhile True: os.write(1, b'x'*4096)"])
    assert time.monotonic() - started < 2


def test_exact_byte_limit_is_read_without_truncation() -> None:
    assert CLIPBOARD.read_bounded([sys.executable, "-c", "import os; os.write(1,b'x'*2048)"]) == b"x" * 2048


@pytest.mark.parametrize(
    "source", ["import time; time.sleep(30)", "import os,time\nwhile True:\n os.write(1,b'x'); time.sleep(.02)"]
)
def test_silent_and_dribbling_producers_share_one_total_deadline(source: str) -> None:
    started = time.monotonic()
    with pytest.raises(CLIPBOARD.ClipboardError, match="two seconds"):
        CLIPBOARD.read_bounded([sys.executable, "-c", source], deadline_seconds=0.2)
    assert 0.15 < time.monotonic() - started < 1


def test_eof_does_not_allow_a_process_to_outlive_the_deadline() -> None:
    with pytest.raises(CLIPBOARD.ClipboardError, match="two seconds"):
        CLIPBOARD.read_bounded(
            [sys.executable, "-c", "import os,time; os.close(1); time.sleep(30)"], deadline_seconds=0.2
        )


@pytest.mark.parametrize(
    "data,message", [(b"\xff", "UTF-8"), (b"a\0b", "control"), (b"x" * 481, "480"), (b"x\x1bb", "control")]
)
def test_invalid_or_oversized_objectives_are_rejected(data: bytes, message: str) -> None:
    with pytest.raises(CLIPBOARD.ClipboardError, match=message):
        CLIPBOARD.decode_text(data)


def _provider(tmp_path: Path, body: str) -> Path:
    executable = tmp_path / "wl-paste"
    executable.write_text(f"#!{sys.executable}\n{body}\n")
    executable.chmod(0o700)
    return executable


def test_primary_selection_and_failures_use_fixed_diagnostics(tmp_path: Path) -> None:
    _provider(tmp_path, "import sys; print('primary' if '--primary' in sys.argv else 'clipboard', end='')")
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--selection", "primary"], env=env, check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == {"ok": True, "text": "primary"}
    _provider(tmp_path, "import sys; print('private-provider-diagnostic',file=sys.stderr); sys.exit(1)")
    result = subprocess.run([sys.executable, str(SCRIPT)], env=env, check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == {"ok": False, "error": "No readable text selection is available."}
    assert "private-provider-diagnostic" not in result.stdout + result.stderr


def test_cancellation_terminates_the_reader_and_its_transfer(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid"
    _provider(tmp_path, f"import os,time; open({str(pid_file)!r},'w').write(str(os.getpid())); time.sleep(30)")
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT)],
        env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 2
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert pid_file.exists()
        child = int(pid_file.read_text())
        process.terminate()
        stdout, stderr = process.communicate(timeout=1)
        assert json.loads(stdout) == {"ok": False, "error": "Clipboard read canceled."}
        assert stderr == ""
        status = Path(f"/proc/{child}/stat")
        # The watchdog and transfer are killed together. A transfer waiting
        # for init to reap it is stopped, even while its zombie PID exists.
        assert not status.exists() or status.read_text().split()[2] == "Z"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_independent_deadline_survives_controller_sigkill(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid"
    _provider(
        tmp_path,
        f"import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); open({str(pid_file)!r},'w').write(str(os.getpid())); time.sleep(30)",
    )
    process = subprocess.Popen(
        [sys.executable, "-I", str(SCRIPT)],
        env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 1
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert pid_file.exists()
        child = int(pid_file.read_text())
        process.kill()
        process.wait(timeout=1)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status = Path(f"/proc/{child}/stat")
            if not status.exists() or status.read_text().split()[2] == "Z":
                break
            time.sleep(0.02)
        else:
            pytest.fail("Transfer survived the independent total deadline after controller SIGKILL.")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
