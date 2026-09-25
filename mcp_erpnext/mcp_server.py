"""MCP stdio entrypoint for safe ERPNext workflows."""

from __future__ import annotations

from .approvals import approvals
from .http_transport import create_http_app
from .instructions import get_mcp_instructions
from .settings import MCPSettings
from .tools import register_tools
from mcp_identity.identity import HTTPAuthMode, get_http_auth_mode_from_environment
from mcp_identity.oauth_resource_server import (
    FrappeOAuthTokenVerifier,
    validate_oauth_resource_server_startup,
)

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
    if (
        settings.transport == "streamable-http"
        and get_http_auth_mode_from_environment() is HTTPAuthMode.OAUTH
    ):
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
    settings.validate_quotation_validity_days()
    approvals.configure_approval_mode(settings.approval_mode)
    mcp = FastMCP(
        f"mcp_erpnext_{settings.profile.value}",
        instructions=get_mcp_instructions(settings.profile),
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
