"""Explicit handoff to the generic local Limitless MCP provider.

The Omarchy-specific MCP surface deliberately accepts only a narrow desktop
customization request.  A user who wants this installation to also provide
the standard, general-purpose local Limitless tool opts in by invoking this
module's provider command instead.  The generic provider is implemented by
Limitless Library; this adapter does not fork its protocol or policy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NoReturn

from limitless_library.catalog import CatalogError, LocalCatalog
from limitless_library.contracts import strict_json_loads
from limitless_library.mcp_protocol import McpToolSession, jsonrpc_error
from limitless_library.mcp_server import _bounded_lines, _dispatcher

from .activity import record_query


def general_provider_command(catalog: Path, activity_path: Path | None = None) -> list[str]:
    """Return the replacement-process command for the generic local provider."""

    command = [sys.executable, "-m", "limitless_omarchy.provider", "--catalog", str(catalog)]
    if activity_path is not None:
        command.extend(["--activity-path", str(activity_path)])
    return command


def serve_general_provider(catalog: Path, *, activity_path: Path | None = None) -> NoReturn:
    """Serve the generic local Library protocol with aggregate observation.

    The pinned Library still owns the dispatcher, session rules, schemas, and
    bounded framing. This adapter wraps only the catalog query callback so the
    Omarchy UI can count outcomes without retaining requests or results.
    """

    try:
        registry = LocalCatalog(Path(catalog))
    except CatalogError as error:
        print(f"cannot load catalog: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    original_query = registry.query

    def counted_query(request: dict[str, object]) -> dict[str, object]:
        result = original_query(request)
        record_query(activity_path, result, channel="general")
        return result

    registry.query = counted_query  # type: ignore[method-assign]
    # These helpers are private to the exact Library revision pinned by this
    # package. Reusing them avoids forking either MCP generation.
    session = McpToolSession(_dispatcher(registry))
    for line, framing_error in _bounded_lines(sys.stdin.buffer):
        if framing_error:
            response = jsonrpc_error(None, -32700, framing_error)
        else:
            try:
                message = strict_json_loads(line)
                if not isinstance(message, dict):
                    raise TypeError("JSON-RPC message must be an object")
                response = session.handle(message)
            except (TypeError, ValueError, CatalogError) as error:
                response = jsonrpc_error(None, -32700, str(error))
        if response is not None:
            print(json.dumps(response, sort_keys=True), flush=True)

    raise SystemExit(0)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--activity-path", type=Path)
    args = parser.parse_args()
    serve_general_provider(args.catalog, activity_path=args.activity_path)


if __name__ == "__main__":
    main()
