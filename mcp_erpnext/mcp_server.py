"""MCP stdio entrypoint for safe ERPNext workflows."""

from __future__ import annotations

from .approvals import approvals
from .http_transport import create_http_app
from .settings import MCPSettings
from .tools import register_tools
from mcp_identity.identity import HTTPAuthMode, get_http_auth_mode_from_environment
from mcp_identity.oauth_resource_server import (
    FrappeOAuthTokenVerifier,
    validate_oauth_resource_server_startup,
)

SALES_RESPONSE_PRECISION_INSTRUCTION = """\
RESPONSE PRECISION POLICY: Answer only the information the user asked for.
Do not dump unrelated fields or internal tool metadata. For a Sales Order
status, date, or total request, return only that value (and currency for a
total). For a request for Sales Order IDs without requested columns, return
only IDs. For counts, totals, and averages, return the computed result without
listing source records. Ask only when a missing distinction materially changes
the answer.
"""

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:  # pragma: no cover - exercised only before dependency installation
    FastMCP = None  # type: ignore[assignment,misc]
    TransportSecuritySettings = None  # type: ignore[assignment,misc]


def create_mcp(settings: MCPSettings | None = None):
    """Build one selected profile registry for either supported MCP transport."""
    if FastMCP is None or TransportSecuritySettings is None:
        return None
    settings = settings or MCPSettings.from_environment()
    auth = None
    token_verifier = None
    if settings.transport == "streamable-http" and get_http_auth_mode_from_environment() is HTTPAuthMode.OAUTH:
        from mcp.server.auth.settings import AuthSettings

        oauth_settings = validate_oauth_resource_server_startup()
        auth = AuthSettings(
            issuer_url=oauth_settings.issuer_url,
            resource_server_url=oauth_settings.resource_server_url,
            required_scopes=list(oauth_settings.required_scopes),
        )
        token_verifier = FrappeOAuthTokenVerifier(oauth_settings)
    settings.validate_approval_mode()
    settings.validate_profile()
    approvals.configure_approval_mode(settings.approval_mode)
    mcp = FastMCP(
        f"mcp_erpnext_{settings.profile.value}",
        instructions=(
            SALES_RESPONSE_PRECISION_INSTRUCTION
            if settings.profile.value == "sales"
            else None
        ),
        host=settings.http_host,
        port=settings.http_port_number(),
        streamable_http_path=settings.http_path,
        auth=auth,
        token_verifier=token_verifier,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(settings.http_allowed_hosts),
        ),
    )
    register_tools(mcp, settings.profile)
    return mcp


mcp = create_mcp()


def main() -> None:
    """Run the configured local MCP transport."""
    if mcp is None:
        raise RuntimeError(
            "Install the mcp_erpnext app dependencies before starting the MCP server."
        )
    settings = MCPSettings.from_environment()
    settings.validate()
    if settings.transport == "stdio":
        mcp.run(transport="stdio")
        return

    import uvicorn

    uvicorn.run(
        create_http_app(mcp, settings),
        host=settings.http_host,
        port=settings.http_port_number(),
    )


if __name__ == "__main__":
    main()
