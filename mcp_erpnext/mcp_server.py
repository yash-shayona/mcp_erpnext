"""MCP stdio entrypoint for safe ERPNext workflows."""

from __future__ import annotations

from .http_transport import create_http_app
from .settings import MCPSettings
from .tools import register_tools

try:
	from mcp.server.fastmcp import FastMCP
	from mcp.server.transport_security import TransportSecuritySettings
except ImportError:  # pragma: no cover - exercised only before dependency installation
	FastMCP = None  # type: ignore[assignment,misc]
	TransportSecuritySettings = None  # type: ignore[assignment,misc]


def create_mcp(settings: MCPSettings | None = None):
	"""Build one shared tool registry for either supported MCP transport."""
	if FastMCP is None or TransportSecuritySettings is None:
		return None
	settings = settings or MCPSettings.from_environment()
	mcp = FastMCP(
		"mcp_erpnext",
		host=settings.http_host,
		port=settings.http_port_number(),
		streamable_http_path=settings.http_path,
		transport_security=TransportSecuritySettings(
			enable_dns_rebinding_protection=True,
			allowed_hosts=list(settings.http_allowed_hosts),
		),
	)
	register_tools(mcp)
	return mcp


mcp = create_mcp()



def main() -> None:
	"""Run the configured local MCP transport."""
	if mcp is None:
		raise RuntimeError("Install the mcp_erpnext app dependencies before starting the MCP server.")
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
