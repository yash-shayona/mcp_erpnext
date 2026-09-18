"""Frappe site bootstrap for the standalone MCP process."""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

import frappe
from mcp_identity.identity import (
    HTTPAuthMode,
    HTTPIdentityInputs,
    MCPAuthenticationMissingError,
    get_http_identity_inputs,
    get_http_shared_secret_from_environment,
    resolve_configured_frappe_user,
    resolve_frappe_user_from_http,
    validate_http_auth_configuration,
    get_http_auth_mode_from_environment,
)

from .settings import MCPSettings
from .rest_client import ERPNextRestClient

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context


ResultT = TypeVar("ResultT")


def ensure_context(site: str | None = None, user: str | None = None) -> dict[str, str]:
    """Connect the MCP process to one site and one resolved Frappe user.

    Stdio preserves the existing configured-service-user development behavior.
    HTTP tools always resolve their execution user from the authenticated
    request and never use this process-level value as a fallback.
    """

    return _ensure_context(MCPSettings.from_environment(), site=site, user=user)


def execute_tool_with_context(
    context: Context,
    tool_name: str,
    operation: Callable[[], ResultT],
    *,
    rest_arguments: dict[str, object] | None = None,
) -> ResultT | dict[str, object]:
    """Execute one MCP tool with either persistent STDIO or scoped HTTP runtime state."""
    from .observability import execute_tool

    settings = MCPSettings.from_environment()
    if settings.backend == "rest":
        if rest_arguments is None:
            return execute_tool(
                tool_name,
                lambda: (_ for _ in ()).throw(
                    RuntimeError("The REST operation payload is unavailable.")
                ),
            )
        return execute_tool(
            tool_name,
            lambda: ERPNextRestClient(settings).execute(
                operation=tool_name,
                profile=settings.profile.value,
                arguments=rest_arguments,
            ),
        )
    if settings.transport == "stdio":
        return execute_tool(tool_name, lambda: _run_stdio_tool(settings, operation))
    if settings.transport == "streamable-http":
        return execute_tool(
            tool_name,
            lambda: _run_configured_http_tool(settings, context, operation),
        )
    return execute_tool(
        tool_name,
        lambda: (_ for _ in ()).throw(
            RuntimeError("MCP_TRANSPORT must be either 'stdio' or 'streamable-http'.")
        ),
    )


def _run_stdio_tool(settings: MCPSettings, operation: Callable[[], ResultT]) -> ResultT:
    _ensure_context(settings)
    return operation()


def _run_http_tool(
    settings: MCPSettings,
    runtime_identity: HTTPIdentityInputs | None,
    operation: Callable[[], ResultT],
    *,
    oauth_user: str | None = None,
) -> ResultT:
    if settings.transport != "streamable-http":
        raise RuntimeError(
            "HTTP request context requires MCP_TRANSPORT=streamable-http."
        )
    with _http_runtime_scope():
        _ensure_context(settings, runtime_identity=runtime_identity, oauth_user=oauth_user)
        return operation()


def _run_configured_http_tool(
    settings: MCPSettings,
    context: Context,
    operation: Callable[[], ResultT],
) -> ResultT:
    """Validate the configured HTTP strategy before reading request identity."""
    mode = validate_http_auth_configuration()
    if mode is HTTPAuthMode.OAUTH:
        from mcp.server.auth.middleware.auth_context import get_access_token

        access_token = get_access_token()
        subject = getattr(access_token, "subject", None) if access_token else None
        if not subject:
            raise MCPAuthenticationMissingError()
        return _run_http_tool(settings, None, operation, oauth_user=str(subject))
    return _run_http_tool(settings, _require_http_runtime_identity(context), operation)


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
    runtime_identity: HTTPIdentityInputs | None = None,
    oauth_user: str | None = None,
) -> dict[str, str]:
    """Connect one Frappe runtime scope to the selected, resolved user."""
    if settings.backend != "direct":
        raise RuntimeError(
            "The REST backend is reserved for a future phase; use MCP_BACKEND=direct for the current server."
        )
    configured_site = (
        site or settings.frappe_site or getattr(frappe.local, "site", None)
    )
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
        sites_path = os.environ.get("MCP_FRAPPE_SITES_PATH") or os.environ.get(
            "FRAPPE_SITES_PATH"
        )
        if not sites_path:
            sites_path = str(Path(__file__).resolve().parents[3] / "sites")

        # Frappe local state is ContextVar-backed. MCP may execute each tool in a
        # different async context, so each context needs its own session/database.
        frappe.init(site=configured_site, sites_path=sites_path, force=True)
        frappe.connect(set_admin_as_user=False)

    if oauth_user is not None:
        configured_user = oauth_user
    elif runtime_identity is None:
        configured_user = resolve_configured_frappe_user(user or settings.frappe_user)
    else:
        validate_http_auth_configuration()
        shared_secret = get_http_shared_secret_from_environment()
        if shared_secret is None:  # The validator above guarantees this invariant.
            raise RuntimeError("Trusted-header authentication is not configured.")
        configured_user = resolve_frappe_user_from_http(
            runtime_identity, shared_secret=shared_secret
        )
    frappe.set_user(configured_user)

    current_user = getattr(frappe.session, "user", None)
    if not current_user or current_user in {"Guest", "guest"}:
        raise RuntimeError("The verified Frappe user could not be applied.")

    return {"site": configured_site, "user": current_user}


def _get_http_runtime_identity(context: Context) -> HTTPIdentityInputs | None:
    """Copy generic headers from one SDK request without retaining the request."""
    request_context = getattr(context, "request_context", None)
    request = getattr(request_context, "request", None)
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    return get_http_identity_inputs(headers)


def _require_http_runtime_identity(context: Context) -> HTTPIdentityInputs:
    """Fail closed when an HTTP process has no request authentication context."""
    identity = _get_http_runtime_identity(context)
    if identity is None:
        raise MCPAuthenticationMissingError()
    return identity
