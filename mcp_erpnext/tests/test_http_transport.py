from __future__ import annotations

import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mcp_identity.identity import get_http_identity_inputs
from mcp_erpnext.http_transport import create_http_app
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.settings import MCPSettings


SECRET = "this-is-a-development-only-secret-with-32-chars"


def _settings(**overrides) -> MCPSettings:
	values = {
		"backend": "direct",
		"frappe_site": "test.localhost",
		"frappe_user": "Administrator",
		"erpnext_base_url": None,
		"erpnext_api_key": None,
		"erpnext_api_secret": None,
		"transport": "streamable-http",
	}
	values.update(overrides)
	return MCPSettings(**values)


class TransportSettingsTests(unittest.TestCase):
	@patch.dict(
		os.environ,
		{"MCP_BACKEND": "direct", "MCP_FRAPPE_SITE": "test.localhost"},
		clear=True,
	)
	def test_missing_transport_defaults_to_stdio(self):
		self.assertEqual(MCPSettings.from_environment().transport, "stdio")

	def test_explicit_stdio_preserves_service_user_development_mode(self):
		_settings(transport="stdio").validate_transport()

	@patch.dict(os.environ, {"MCP_HTTP_AUTH_MODE": "oauth"}, clear=True)
	def test_stdio_does_not_validate_http_auth_mode(self):
		_settings(transport="stdio").validate_transport()

	def test_invalid_transport_fails_deterministically(self):
		with self.assertRaisesRegex(RuntimeError, "MCP_TRANSPORT"):
			_settings(transport="sse").validate_transport()

	def test_http_rejects_missing_or_short_secret(self):
		for secret in (None, "too-short"):
			with self.subTest(secret=secret), patch.dict(
				os.environ, {"MCP_HTTP_SHARED_SECRET": secret} if secret else {}, clear=True
			):
				with self.assertRaisesRegex(Exception, "MCP_HTTP_SHARED_SECRET"):
					_settings().validate_transport()

	@patch.dict(os.environ, {"MCP_HTTP_AUTH_MODE": "oauth"}, clear=True)
	def test_http_oauth_mode_requires_oauth_configuration(self):
		with self.assertRaisesRegex(Exception, "MCP_OAUTH_ISSUER_URL"):
			_settings().validate_transport()

	@patch.dict(os.environ, {"MCP_HTTP_SHARED_SECRET": SECRET}, clear=True)
	def test_http_rejects_invalid_port_and_wildcard_host(self):
		with self.assertRaisesRegex(RuntimeError, "MCP_HTTP_PORT"):
			_settings(http_port="invalid").validate_transport()
		with self.assertRaisesRegex(RuntimeError, "MCP_HTTP_ALLOWED_HOSTS"):
			_settings(http_allowed_hosts=("*:8765",)).validate_transport()


class HTTPAppAssemblyTests(unittest.TestCase):
	@patch.dict(
		os.environ,
		{
			"MCP_HTTP_AUTH_MODE": "oauth",
			"MCP_FRAPPE_SITE": "test.localhost",
			"MCP_OAUTH_ISSUER_URL": "https://erp.example.com",
			"MCP_OAUTH_RESOURCE_SERVER_URL": "https://mcp.example.com/mcp",
			"MCP_OAUTH_REQUIRED_SCOPES": "mcp:access",
			"MCP_OAUTH_FRAPPE_CLIENT_ID": "client-a",
		},
		clear=True,
	)
	@patch("mcp_erpnext.mcp_server.FrappeOAuthTokenVerifier")
	@patch("mcp_erpnext.mcp_server.validate_oauth_resource_server_startup")
	def test_oauth_uses_sdk_auth_and_metadata_routes(self, startup, verifier):
		startup.return_value = SimpleNamespace(
			issuer_url="https://erp.example.com",
			resource_server_url="https://mcp.example.com/mcp",
			required_scopes=("mcp:access",),
		)
		mcp = create_mcp(_settings())
		self.assertEqual(str(mcp.settings.auth.resource_server_url), "https://mcp.example.com/mcp")
		self.assertEqual(mcp.settings.auth.required_scopes, ["mcp:access"])
		self.assertTrue(mcp._token_verifier is verifier.return_value)
		app = create_http_app(mcp, _settings())
		self.assertTrue(any("oauth-protected-resource" in route.path for route in app.routes))
		verifier.assert_called_once_with(startup.return_value)

	@patch.dict(os.environ, {"MCP_HTTP_SHARED_SECRET": SECRET}, clear=True)
	@patch("mcp_erpnext.http_transport.add_trusted_header_authentication")
	def test_http_authentication_is_supplied_by_mcp_identity(self, add_authentication):
		app = Mock()
		mcp = Mock()
		mcp.streamable_http_app.return_value = app
		add_authentication.return_value = app

		self.assertIs(create_http_app(mcp, _settings()), app)
		add_authentication.assert_called_once_with(
			app, shared_secret=SECRET, path="/mcp"
		)


class RequestIdentityTests(unittest.TestCase):
	def test_http_identity_uses_only_generic_headers(self):
		identity = get_http_identity_inputs(
			{"authorization": f"Bearer {SECRET}", "x-mcp-user-email": "sales@example.com"}
		)
		self.assertEqual(identity.authorization, f"Bearer {SECRET}")
		self.assertEqual(identity.user_email, "sales@example.com")

	def test_email_only_http_request_is_not_authenticated(self):
		identity = get_http_identity_inputs({"x-mcp-user-email": "sales@example.com"})
		self.assertIsNone(identity.authorization)


class ToolSchemaTests(unittest.TestCase):
	def test_context_and_identity_fields_are_not_model_visible(self):
		async def list_tools():
			return await create_mcp(_settings()).list_tools()

		for tool in asyncio.run(list_tools()):
			with self.subTest(tool=tool.name):
				properties = tool.inputSchema.get("properties", {})
				self.assertNotIn("ctx", properties)
				self.assertFalse({"frappe_user", "run_as", "role", "user_email"} & properties.keys())
