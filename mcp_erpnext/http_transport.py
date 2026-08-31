"""Authenticated Streamable HTTP transport helpers for the MCP server."""

from __future__ import annotations

import hmac
import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

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
		if not _has_valid_bearer_secret(request.headers.get("authorization"), self.shared_secret):
			logger.warning("MCP HTTP authentication failed")
			return PlainTextResponse("Unauthorized", status_code=401)
		return await call_next(request)


def _has_valid_bearer_secret(authorization: str | None, shared_secret: str) -> bool:
	"""Validate only a complete Bearer value without exposing either secret."""
	if not authorization or not authorization.startswith("Bearer "):
		return False
	presented_secret = authorization.removeprefix("Bearer ")
	return bool(presented_secret) and hmac.compare_digest(presented_secret, shared_secret)


def create_http_app(mcp: Any, settings: MCPSettings) -> Any:
	"""Wrap the SDK Streamable HTTP app with the project's shared-secret check."""
	settings.validate_transport()
	app = mcp.streamable_http_app()
	app.add_middleware(
		SharedSecretAuthenticationMiddleware,
		shared_secret=settings.http_shared_secret or "",
		path=settings.http_path,
	)
	return app
