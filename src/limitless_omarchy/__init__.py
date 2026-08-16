"""Limitless Library integration surface for Omarchy."""

from .adapter import (
    AdapterError,
    build_query,
    discover_profile,
    query_local_catalog,
    seal_local_capsule,
    status,
    validate_plugin,
)
from .mcp_server import handle_message

__all__ = [
    "AdapterError",
    "build_query",
    "discover_profile",
    "handle_message",
    "query_local_catalog",
    "seal_local_capsule",
    "status",
    "validate_plugin",
]
