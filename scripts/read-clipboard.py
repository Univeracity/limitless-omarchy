#!/usr/bin/env python3
"""Read an explicitly requested Wayland text selection with fixed limits."""

from __future__ import annotations

import argparse
import json
import os
import resource
import selectors
import shutil
import signal

# The clipboard reader runs with fixed argv in a separate, bounded process.
import subprocess  # nosec B404
import time
from collections.abc import Sequence

MAX_BYTES = 2048
MAX_CHARACTERS = 480
DEADLINE_SECONDS = 2.0
_cancelled = False


class ClipboardError(Exception):
    pass


def _cancel(_signal: int, _frame: object) -> None:
    global _cancelled
    _cancelled = True


def _process_limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (64 * 1024 * 1024, 64 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))


def read_bounded(command: Sequence[str], *, deadline_seconds: float = DEADLINE_SECONDS) -> bytes:
    watchdog = shutil.which("timeout")
    if watchdog is None:
        raise ClipboardError("Paste requires GNU coreutils; typing remains available.")
    deadline = time.monotonic() + deadline_seconds
    process = subprocess.Popen(  # nosec B603
        # This independent deadline survives controller SIGKILL or shell
        # teardown. The controller also limits bytes and handles cancellation.
        [watchdog, "--signal=KILL", str(deadline_seconds), *command],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "LANG", "LC_ALL"}
        },
    )
    data = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if _cancelled:
                    raise ClipboardError("Clipboard read canceled.")
                if remaining <= 0:
                    raise ClipboardError("Clipboard did not finish within two seconds.")
                if not selector.select(min(remaining, 0.1)):
                    continue
                chunk = os.read(process.stdout.fileno(), MAX_BYTES + 1 - len(data))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ClipboardError("Clipboard text exceeds the 2 KiB paste limit.")
        try:
            code = process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            raise ClipboardError("Clipboard did not finish within two seconds.") from exc
        if code in {124, 137, -signal.SIGKILL}:
            raise ClipboardError("Clipboard did not finish within two seconds.")
        if code != 0:
            raise ClipboardError("No readable text selection is available.")
        return bytes(data)
    finally:
        # Kill the transfer's session, including a producer helper that keeps
        # stdout open. No transfer survives a rejected or canceled read.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.stdout.close()
        process.wait()


def decode_text(data: bytes) -> str:
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ClipboardError("Clipboard text is not valid UTF-8.") from exc
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = text.replace("\u2028", " ").replace("\u2029", " ")
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ClipboardError("Clipboard text contains unsupported control characters.")
    if len(text) > MAX_CHARACTERS:
        raise ClipboardError("Text can contain at most 480 characters.")
    return text


def main() -> None:
    # Bound this standalone, single-threaded controller and its child through
    # inherited limits, without running Python between fork and exec.
    _process_limits()
    signal.signal(signal.SIGTERM, _cancel)
    signal.signal(signal.SIGINT, _cancel)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", choices=("clipboard", "primary"), default="clipboard")
    args = parser.parse_args()
    try:
        executable = shutil.which("wl-paste")
        if executable is None:
            raise ClipboardError("Paste requires wl-clipboard; typing remains available.")
        command = [executable, "--no-newline", "--type", "text"]
        if args.selection == "primary":
            command.append("--primary")
        result = {"ok": True, "text": decode_text(read_bounded(command))}
    except (ClipboardError, OSError, subprocess.SubprocessError) as error:
        # Emit fixed diagnostics, never stderr from another application.
        result = {"ok": False, "error": str(error) if isinstance(error, ClipboardError) else "Clipboard read failed."}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
