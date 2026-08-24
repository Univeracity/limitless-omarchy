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
from .agent_connection import agent_connection_status, disconnect_agent_connections, reconcile_agent_connections
from .mcp_server import handle_message
from .service import (
    build_service_receiver_context,
    inspect_managed_service,
    manage_publication,
    query_managed_service,
    stage_managed_artifact,
)
from .version import VERSION as __version__

__all__ = [
    "AdapterError",
    "__version__",
    "agent_connection_status",
    "build_query",
    "build_service_receiver_context",
    "disconnect_agent_connections",
    "discover_profile",
    "handle_message",
    "inspect_managed_service",
    "manage_publication",
    "query_local_catalog",
    "query_managed_service",
    "reconcile_agent_connections",
    "seal_local_capsule",
    "stage_managed_artifact",
    "status",
    "validate_plugin",
]
