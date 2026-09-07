from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from mcp_identity.identity import get_http_identity_inputs
from mcp_erpnext.http_transport import SharedSecretAuthenticationMiddleware
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.settings import MCPSettings
from starlette.requests import Request
from starlette.responses import Response


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

	@patch.dict(os.environ, {"MCP_HTTP_SHARED_SECRET": SECRET}, clear=True)
	def test_http_rejects_invalid_port_and_wildcard_host(self):
		with self.assertRaisesRegex(RuntimeError, "MCP_HTTP_PORT"):
			_settings(http_port="invalid").validate_transport()
		with self.assertRaisesRegex(RuntimeError, "MCP_HTTP_ALLOWED_HOSTS"):
			_settings(http_allowed_hosts=("*:8765",)).validate_transport()


class SharedSecretAuthenticationTests(unittest.TestCase):
	def setUp(self):
		async def app(_scope, _receive, _send):
			return None

		self.middleware = SharedSecretAuthenticationMiddleware(app, shared_secret=SECRET, path="/mcp")

	def _dispatch(self, authorization: str | None) -> Response:
		headers = [] if authorization is None else [(b"authorization", authorization.encode())]
		request = Request(
			{
				"type": "http", "method": "POST", "path": "/mcp", "headers": headers,
				"query_string": b"", "scheme": "http", "server": ("testserver", 80),
				"client": ("testclient", 50000),
			}
		)

		async def call_next(_request):
			return Response(status_code=204)

		return asyncio.run(self.middleware.dispatch(request, call_next))

	def test_missing_malformed_and_wrong_bearer_values_are_rejected(self):
		for authorization in (None, "Basic value", "Bearer wrong-secret"):
			with self.subTest(authorization=authorization):
				self.assertEqual(self._dispatch(authorization).status_code, 401)

	def test_correct_bearer_value_reaches_the_mcp_app(self):
		self.assertEqual(self._dispatch(f"Bearer {SECRET}").status_code, 204)

	@patch("mcp_erpnext.http_transport.logger")
	def test_authentication_log_never_contains_the_secret(self, logger):
		self._dispatch("Bearer incorrect")
		self.assertEqual(logger.warning.call_args.args, ("MCP HTTP authentication failed",))
		self.assertNotIn(SECRET, str(logger.warning.call_args))


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
