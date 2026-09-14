"""Environment configuration shared by current and future MCP backends."""

from __future__ import annotations

import os
from ipaddress import ip_address
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit

from mcp_identity.identity import (
    get_http_shared_secret_from_environment,
    validate_http_shared_secret_configuration,
)


class ApprovalMode(StrEnum):
    """Server-controlled trust policy for final prepared-operation writes."""

    TRUSTED_HUMAN = "trusted_human"
    AGENT_DELEGATED = "agent_delegated"


class MCPProfile(StrEnum):
    """The domain-specific public MCP inventory served by one process."""

    SALES = "sales"
    PURCHASE = "purchase"


@dataclass(frozen=True)
class MCPSettings:
    """Process configuration; secrets are read from the environment only."""

    backend: str
    frappe_site: str | None
    frappe_user: str | None
    erpnext_base_url: str | None
    erpnext_api_key: str | None
    erpnext_api_secret: str | None
    rest_allow_insecure_http: bool = False
    transport: str = "stdio"
    http_host: str = "127.0.0.1"
    http_port: str = "8765"
    http_path: str = "/mcp"
    http_allowed_hosts: tuple[str, ...] = ("127.0.0.1:8765", "localhost:8765")
    approval_mode: ApprovalMode = ApprovalMode.AGENT_DELEGATED
    profile: MCPProfile = MCPProfile.SALES

    @classmethod
    def from_environment(cls) -> "MCPSettings":
        return cls(
            backend=os.environ.get("MCP_BACKEND", "direct").strip().lower(),
            frappe_site=os.environ.get("MCP_FRAPPE_SITE"),
            frappe_user=os.environ.get("MCP_FRAPPE_USER"),
            erpnext_base_url=os.environ.get("ERPNEXT_BASE_URL"),
            erpnext_api_key=os.environ.get("ERPNEXT_API_KEY"),
            erpnext_api_secret=os.environ.get("ERPNEXT_API_SECRET"),
            rest_allow_insecure_http=(
                os.environ.get("MCP_REST_ALLOW_INSECURE_HTTP", "").strip().lower()
                in {"1", "true", "yes"}
            ),
            transport=os.environ.get("MCP_TRANSPORT", "stdio").strip().lower(),
            http_host=os.environ.get("MCP_HTTP_HOST", "127.0.0.1").strip(),
            http_port=os.environ.get("MCP_HTTP_PORT", "8765").strip(),
            http_path=os.environ.get("MCP_HTTP_PATH", "/mcp").strip(),
            http_allowed_hosts=tuple(
                host.strip()
                for host in os.environ.get(
                    "MCP_HTTP_ALLOWED_HOSTS", "127.0.0.1:8765,localhost:8765"
                ).split(",")
                if host.strip()
            ),
            approval_mode=cls._approval_mode_from_environment(),
            profile=cls._profile_from_environment(),
        )

    @staticmethod
    def _approval_mode_from_environment() -> ApprovalMode:
        value = (
            os.environ.get("MCP_APPROVAL_MODE", ApprovalMode.AGENT_DELEGATED)
            .strip()
            .lower()
        )
        try:
            return ApprovalMode(value)
        except ValueError as error:
            raise RuntimeError(
                "MCP_APPROVAL_MODE must be either 'trusted_human' or 'agent_delegated'."
            ) from error

    @staticmethod
    def _profile_from_environment() -> MCPProfile:
        value = os.environ.get("MCP_PROFILE", MCPProfile.SALES).strip().lower()
        try:
            return MCPProfile(value)
        except ValueError as error:
            raise RuntimeError("MCP_PROFILE must be either 'sales' or 'purchase'.") from error

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
        if self.backend == "rest":
            self.rest_endpoint_url()
            if self.transport == "streamable-http":
                raise RuntimeError(
                    "MCP_BACKEND=rest currently supports only MCP_TRANSPORT=stdio because remote execution is bound to the configured ERPNext API user."
                )
        self.validate_transport()
        self.validate_approval_mode()
        self.validate_profile()

    def rest_endpoint_url(self) -> str:
        """Return the single approved remote bridge URL without exposing secrets."""
        if not self.erpnext_base_url:
            raise RuntimeError("ERPNEXT_BASE_URL is required for the REST backend.")
        parsed = urlsplit(self.erpnext_base_url)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.netloc
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise RuntimeError(
                "ERPNEXT_BASE_URL must be an absolute HTTP(S) origin without a path, credentials, query, or fragment."
            )
        if parsed.scheme == "http" and not self._allows_insecure_local_rest(parsed.hostname):
            raise RuntimeError(
                "ERPNEXT_BASE_URL must use HTTPS, except when MCP_REST_ALLOW_INSECURE_HTTP is enabled for a loopback-only local origin."
            )
        return urlunsplit(
            (parsed.scheme, parsed.netloc, "/api/method/mcp_erpnext.remote_api.execute_mcp_operation", "", "")
        )

    def _allows_insecure_local_rest(self, hostname: str) -> bool:
        """Allow explicit cleartext REST only for a local development origin."""
        if not self.rest_allow_insecure_http:
            return False
        normalized = hostname.rstrip(".").lower()
        if normalized == "localhost" or normalized.endswith(".localhost"):
            return True
        try:
            return ip_address(normalized).is_loopback
        except ValueError:
            return False

    def validate_approval_mode(self) -> None:
        """Reject an unsafe or unknown final-write approval policy."""
        try:
            ApprovalMode(self.approval_mode)
        except ValueError as error:
            raise RuntimeError(
                "MCP_APPROVAL_MODE must be either 'trusted_human' or 'agent_delegated'."
            ) from error

    def validate_profile(self) -> None:
        """Reject unknown inventories before any MCP server is exposed."""
        try:
            MCPProfile(self.profile)
        except ValueError as error:
            raise RuntimeError("MCP_PROFILE must be either 'sales' or 'purchase'.") from error

    def validate_transport(self) -> None:
        """Validate the selected MCP transport without exposing secret values."""
        if self.transport not in {"stdio", "streamable-http"}:
            raise RuntimeError(
                "MCP_TRANSPORT must be either 'stdio' or 'streamable-http'."
            )
        if self.transport == "stdio":
            return
        validate_http_shared_secret_configuration(get_http_shared_secret_from_environment())
        if not self.http_host:
            raise RuntimeError("MCP_HTTP_HOST is required for Streamable HTTP.")
        if (
            not self.http_path.startswith("/")
            or "?" in self.http_path
            or "#" in self.http_path
        ):
            raise RuntimeError(
                "MCP_HTTP_PATH must be an absolute path without a query or fragment."
            )
        if not self.http_allowed_hosts or any(
            "*" in host for host in self.http_allowed_hosts
        ):
            raise RuntimeError(
                "MCP_HTTP_ALLOWED_HOSTS must contain explicit, non-wildcard hosts."
            )
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
