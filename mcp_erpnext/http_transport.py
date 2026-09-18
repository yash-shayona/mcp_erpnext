"""Streamable HTTP transport assembly for the MCP server."""

from __future__ import annotations

from typing import Any

from mcp_identity.identity import (
    HTTPAuthMode,
    get_http_auth_mode_from_environment,
    get_http_shared_secret_from_environment,
    validate_http_auth_configuration,
)
from mcp_identity.http import add_trusted_header_authentication

from .settings import MCPSettings


def create_http_app(mcp: Any, settings: MCPSettings) -> Any:
    """Build the SDK app and delegate authentication assembly to mcp_identity."""
    settings.validate_transport()
    mode = validate_http_auth_configuration()
    if mode is HTTPAuthMode.OAUTH:
        # FastMCP already supplies bearer authentication, scope enforcement,
        # challenges, and protected-resource metadata for this mode.
        return mcp.streamable_http_app()
    shared_secret = get_http_shared_secret_from_environment()
    if shared_secret is None:  # The validator above guarantees this invariant.
        raise RuntimeError("Trusted-header authentication is not configured.")
    app = mcp.streamable_http_app()
    return add_trusted_header_authentication(
        app,
        shared_secret=shared_secret,
        path=settings.http_path,
    )
