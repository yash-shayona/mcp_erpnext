"""Frappe site bootstrap for the standalone MCP process."""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

import frappe

from .identity import resolve_frappe_user_for_runtime
from .settings import MCPSettings
from .transport_identity import RuntimeIdentity, get_http_runtime_identity


if TYPE_CHECKING:
	from mcp.server.fastmcp import Context


ResultT = TypeVar("ResultT")


def ensure_context(site: str | None = None, user: str | None = None) -> dict[str, str]:
	"""Connect the MCP process to one site and one resolved Frappe user.

	Service mode preserves the existing configured-service-user behavior. In
	LibreChat mode the execution user is resolved only from the authoritative
	LibreChat user ID mapping; an internal ``user`` override cannot bypass it.
	"""

	return _ensure_context(MCPSettings.from_environment(), site=site, user=user)


def execute_tool_with_context(
	context: Context, tool_name: str, operation: Callable[[], ResultT]
) -> ResultT | dict[str, object]:
	"""Execute one MCP tool with either persistent STDIO or scoped HTTP runtime state."""
	from .observability import execute_tool

	settings = MCPSettings.from_environment()
	runtime_identity = get_http_runtime_identity(context)
	if runtime_identity is None:
		return execute_tool(tool_name, lambda: _run_stdio_tool(settings, operation))
	return execute_tool(
		tool_name,
		lambda: _run_http_tool(settings, runtime_identity, operation),
	)


def _run_stdio_tool(settings: MCPSettings, operation: Callable[[], ResultT]) -> ResultT:
	_ensure_context(settings)
	return operation()


def _run_http_tool(
	settings: MCPSettings, runtime_identity: RuntimeIdentity, operation: Callable[[], ResultT]
) -> ResultT:
	if settings.transport != "streamable-http":
		raise RuntimeError("HTTP request context requires MCP_TRANSPORT=streamable-http.")
	with _http_runtime_scope():
		_ensure_context(settings, runtime_identity=runtime_identity)
		return operation()


@contextmanager
def _http_runtime_scope():
	"""Clear Frappe local state before and after each persistent HTTP tool call."""
	frappe.destroy()
	try:
		yield
	finally:
		frappe.destroy()


def _ensure_context(
	settings: MCPSettings,
	*,
	site: str | None = None,
	user: str | None = None,
	runtime_identity: RuntimeIdentity | None = None,
) -> dict[str, str]:
	"""Connect one Frappe runtime scope to the selected, resolved user."""
	if settings.backend != "direct":
		raise RuntimeError(
			"The REST backend is reserved for a future phase; use MCP_BACKEND=direct for the current server."
		)
	settings.validate_identity_mode(require_librechat_user_id=runtime_identity is None)
	if runtime_identity is not None and settings.identity_mode != "librechat":
		raise RuntimeError("Streamable HTTP requires MCP_IDENTITY_MODE=librechat.")

	configured_site = site or settings.frappe_site or getattr(frappe.local, "site", None)
	if not configured_site:
		raise RuntimeError("Set MCP_FRAPPE_SITE before starting the MCP server.")

	local_site = getattr(frappe.local, "site", None)
	local_initialised = getattr(frappe.local, "initialised", False)
	if not local_initialised or local_site != configured_site:
		if local_initialised:
			frappe.destroy()
		# Resolve the bench sites directory explicitly because Frappe's site
		# discovery is cwd-dependent (the launcher may start from either the
		# bench root or the sites directory).
		sites_path = os.environ.get("MCP_FRAPPE_SITES_PATH") or os.environ.get("FRAPPE_SITES_PATH")
		if not sites_path:
			sites_path = str(Path(__file__).resolve().parents[3] / "sites")

		# Frappe local state is ContextVar-backed. MCP may execute each tool in a
		# different async context, so each context needs its own session/database.
		frappe.init(site=configured_site, sites_path=sites_path, force=True)
		frappe.connect(set_admin_as_user=False)

	if settings.identity_mode == "service" and user:
		configured_user = user
	elif runtime_identity is None:
		configured_user = resolve_frappe_user_for_runtime(settings)
	else:
		configured_user = resolve_frappe_user_for_runtime(settings, runtime_identity)
	if configured_user:
		frappe.set_user(configured_user)

	current_user = getattr(frappe.session, "user", None)
	if not current_user or current_user in {"Guest", "guest"}:
		raise RuntimeError(
			"Set MCP_FRAPPE_USER to an authenticated Frappe service user before using Sales Order tools."
		)

	return {"site": configured_site, "user": current_user}
