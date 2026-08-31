"""Translate SDK request context into a transport-scoped LibreChat identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal


if TYPE_CHECKING:
	from mcp.server.fastmcp import Context


@dataclass(frozen=True)
class RuntimeIdentity:
	"""The non-model-visible identity supplied by an authenticated HTTP request."""

	source: Literal["librechat_http"]
	librechat_user_id: str | None
	librechat_user_email: str | None


def get_http_runtime_identity(context: Context) -> RuntimeIdentity | None:
	"""Read the current Streamable HTTP request identity without retaining the request."""
	request = context.request_context.request
	headers = getattr(request, "headers", None)
	if headers is None:
		return None
	return RuntimeIdentity(
		source="librechat_http",
		librechat_user_id=headers.get("x-librechat-user-id"),
		librechat_user_email=headers.get("x-librechat-user-email"),
	)
