"""Environment configuration shared by current and future MCP backends."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .observability import MCPIdentityConfigurationError


@dataclass(frozen=True)
class MCPSettings:
	"""Process configuration; secrets are read from the environment only."""

	backend: str
	frappe_site: str | None
	frappe_user: str | None
	identity_mode: str
	librechat_user_id: str | None
	librechat_user_email: str | None
	erpnext_base_url: str | None
	erpnext_api_key: str | None
	erpnext_api_secret: str | None
	transport: str = "stdio"
	http_host: str = "127.0.0.1"
	http_port: str = "8765"
	http_path: str = "/mcp"
	http_shared_secret: str | None = None
	http_allowed_hosts: tuple[str, ...] = ("127.0.0.1:8765", "localhost:8765")

	@classmethod
	def from_environment(cls) -> "MCPSettings":
		return cls(
			backend=os.environ.get("MCP_BACKEND", "direct").strip().lower(),
			frappe_site=os.environ.get("MCP_FRAPPE_SITE"),
			frappe_user=os.environ.get("MCP_FRAPPE_USER"),
			identity_mode=os.environ.get("MCP_IDENTITY_MODE", "service").strip().lower(),
			librechat_user_id=os.environ.get("MCP_LIBRECHAT_USER_ID"),
			librechat_user_email=os.environ.get("MCP_LIBRECHAT_USER_EMAIL"),
			erpnext_base_url=os.environ.get("ERPNEXT_BASE_URL"),
			erpnext_api_key=os.environ.get("ERPNEXT_API_KEY"),
			erpnext_api_secret=os.environ.get("ERPNEXT_API_SECRET"),
			transport=os.environ.get("MCP_TRANSPORT", "stdio").strip().lower(),
			http_host=os.environ.get("MCP_HTTP_HOST", "127.0.0.1").strip(),
			http_port=os.environ.get("MCP_HTTP_PORT", "8765").strip(),
			http_path=os.environ.get("MCP_HTTP_PATH", "/mcp").strip(),
			http_shared_secret=os.environ.get("MCP_HTTP_SHARED_SECRET"),
			http_allowed_hosts=tuple(
				host.strip()
				for host in os.environ.get(
					"MCP_HTTP_ALLOWED_HOSTS", "127.0.0.1:8765,localhost:8765"
				).split(",")
				if host.strip()
			),
		)

	def validate(self) -> None:
		"""Validate only the selected backend's required configuration."""
		if self.backend not in {"direct", "rest"}:
			raise RuntimeError("MCP_BACKEND must be either 'direct' or 'rest'.")
		if self.backend == "direct" and not self.frappe_site:
			raise RuntimeError("MCP_FRAPPE_SITE is required for the direct backend.")
		if self.backend == "rest" and not all(
			(self.erpnext_base_url, self.erpnext_api_key, self.erpnext_api_secret)
		):
			raise RuntimeError(
				"ERPNEXT_BASE_URL, ERPNEXT_API_KEY, and ERPNEXT_API_SECRET are required for the REST backend."
			)
		self.validate_transport()
		self.validate_identity_mode(require_librechat_user_id=self.transport == "stdio")

	def validate_identity_mode(self, *, require_librechat_user_id: bool = True) -> None:
		"""Validate identity settings without constraining an internal site override."""
		if self.identity_mode not in {"service", "librechat"}:
			raise MCPIdentityConfigurationError()
		if (
			require_librechat_user_id
			and self.identity_mode == "librechat"
			and not (self.librechat_user_id or "").strip()
		):
			raise MCPIdentityConfigurationError()

	def validate_transport(self) -> None:
		"""Validate the selected MCP transport without exposing secret values."""
		if self.transport not in {"stdio", "streamable-http"}:
			raise RuntimeError("MCP_TRANSPORT must be either 'stdio' or 'streamable-http'.")
		if self.transport == "stdio":
			return
		if self.identity_mode != "librechat":
			raise MCPIdentityConfigurationError()
		if not self.http_shared_secret or len(self.http_shared_secret) < 32:
			raise RuntimeError("MCP_HTTP_SHARED_SECRET must be at least 32 characters for Streamable HTTP.")
		if not self.http_host:
			raise RuntimeError("MCP_HTTP_HOST is required for Streamable HTTP.")
		if not self.http_path.startswith("/") or "?" in self.http_path or "#" in self.http_path:
			raise RuntimeError("MCP_HTTP_PATH must be an absolute path without a query or fragment.")
		if not self.http_allowed_hosts or any("*" in host for host in self.http_allowed_hosts):
			raise RuntimeError("MCP_HTTP_ALLOWED_HOSTS must contain explicit, non-wildcard hosts.")
		self.http_port_number()

	def http_port_number(self) -> int:
		"""Return the validated Streamable HTTP port."""
		try:
			port = int(self.http_port)
		except (TypeError, ValueError) as error:
			raise RuntimeError("MCP_HTTP_PORT must be a valid integer port.") from error
		if not 1 <= port <= 65535:
			raise RuntimeError("MCP_HTTP_PORT must be between 1 and 65535.")
		return port
