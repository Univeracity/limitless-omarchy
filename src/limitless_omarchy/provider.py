"""Explicit handoff to the generic local Limitless MCP provider.

The Omarchy-specific MCP surface deliberately accepts only a narrow desktop
customization request.  A user who wants this installation to also provide
the standard, general-purpose local Limitless tool opts in by invoking this
module's provider command instead.  The generic provider is implemented by
Limitless Library; this adapter does not fork its protocol or policy.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NoReturn


def general_provider_command(catalog: Path) -> list[str]:
    """Return the replacement-process command for the generic local provider."""

    return [sys.executable, "-m", "limitless_library.mcp_server", "--catalog", str(catalog)]


def serve_general_provider(catalog: Path) -> NoReturn:
    """Replace this process with the generic, local-only Library MCP server.

    Replacing rather than proxying the process preserves the core server's
    bounded stdio framing and avoids a second MCP implementation here.
    """

    command = general_provider_command(catalog)
    # The command fixes the current interpreter and module and never uses a shell.
    os.execv(command[0], command)  # nosec B606
    raise AssertionError("os.execv unexpectedly returned")
