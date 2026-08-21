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
from .service import (
    build_service_receiver_context,
    inspect_managed_service,
    manage_publication,
    query_managed_service,
    stage_managed_artifact,
)

__all__ = [
    "AdapterError",
    "build_query",
    "build_service_receiver_context",
    "discover_profile",
    "handle_message",
    "inspect_managed_service",
    "manage_publication",
    "query_local_catalog",
    "query_managed_service",
    "seal_local_capsule",
    "stage_managed_artifact",
    "status",
    "validate_plugin",
]
