"""Authenticated Streamable HTTP transport helpers for the MCP server."""

from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from mcp_identity.identity import (
    MCPIdentityError,
    get_http_shared_secret_from_environment,
    validate_bearer_secret,
    validate_http_shared_secret_configuration,
)

from .settings import MCPSettings

logger = logging.getLogger(__name__)


class SharedSecretAuthenticationMiddleware(BaseHTTPMiddleware):
    """Require the configured Bearer secret before handing an MCP request to the SDK."""

    def __init__(self, app: Any, *, shared_secret: str, path: str) -> None:
        super().__init__(app)
        self.shared_secret = shared_secret
        self.path = path

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.url.path != self.path:
            return await call_next(request)
        try:
            validate_bearer_secret(request.headers.get("authorization"), self.shared_secret)
        except MCPIdentityError:
            logger.warning("MCP HTTP authentication failed")
            return PlainTextResponse("Unauthorized", status_code=401)
        return await call_next(request)


def create_http_app(mcp: Any, settings: MCPSettings) -> Any:
    """Wrap the SDK Streamable HTTP app with the project's shared-secret check."""
    settings.validate_transport()
    shared_secret = validate_http_shared_secret_configuration(
        get_http_shared_secret_from_environment()
    )
    app = mcp.streamable_http_app()
    app.add_middleware(
        SharedSecretAuthenticationMiddleware,
        shared_secret=shared_secret,
        path=settings.http_path,
    )
    return app
