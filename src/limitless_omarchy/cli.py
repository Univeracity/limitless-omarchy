"""Command-line entry point for the local Omarchy integration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adapter import AdapterError, query_local_catalog, seal_local_capsule, status, validate_plugin
from .mcp_server import serve


def _print(value: dict[str, Any]) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="show the minimal local Omarchy receiver profile")
    status_parser.add_argument("--omarchy-release", help="explicit receiver release for compatibility matching")

    query = subparsers.add_parser("query", help="query a local catalog before a customization")
    query.add_argument("--catalog", type=Path, required=True)
    query.add_argument("--omarchy-release", help="explicit receiver release for compatibility matching")
    query.add_argument("--task-kind", choices=["omarchy-customization"], default="omarchy-customization")
    query.add_argument("--requested-use", choices=["adopt", "instantiate"], default="adopt")
    query.add_argument("--tenant-scope", choices=["private"], default="private")

    seal = subparsers.add_parser("seal-capsule", help="seal an owner-provided local Work Capsule draft")
    seal.add_argument("--draft", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    seal.add_argument("--root", type=Path, help="exact-component root; defaults to the draft directory")

    validate = subparsers.add_parser("validate-plugin", help="run Omarchy's native plugin validator")
    validate.add_argument("plugin_dir", type=Path, nargs="?", default=Path("."))

    mcp = subparsers.add_parser("mcp", help="serve the local Omarchy-aware MCP tool over stdio")
    mcp.add_argument("--catalog", type=Path, required=True)
    mcp.add_argument("--omarchy-release", help="explicit receiver release for compatibility matching")
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "status":
            _print(status(omarchy_release=args.omarchy_release))
        elif args.command == "query":
            _print(
                query_local_catalog(
                    args.catalog,
                    omarchy_release=args.omarchy_release,
                    task_kind=args.task_kind,
                    requested_use=args.requested_use,
                    tenant_scope=args.tenant_scope,
                )
            )
        elif args.command == "seal-capsule":
            _print(seal_local_capsule(args.draft, args.output, root=args.root))
        elif args.command == "validate-plugin":
            result = validate_plugin(args.plugin_dir)
            _print(result)
            if result["status"] != "valid":
                raise SystemExit(1)
        elif args.command == "mcp":
            serve(args.catalog, omarchy_release=args.omarchy_release)
    except AdapterError as error:
        print(f"limitless-omarchy: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
