from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mcp_identity.identity import HTTPIdentityInputs, MCPAuthenticationInvalidError
from mcp_erpnext import observability, runtime
from mcp_erpnext.settings import MCPSettings


SECRET = "this-is-a-development-only-secret-with-32-chars"


def _settings() -> MCPSettings:
	return MCPSettings(
		backend="direct", frappe_site="test.localhost", frappe_user="Administrator",
		erpnext_base_url=None, erpnext_api_key=None, erpnext_api_secret=None,
		transport="streamable-http",
	)


class RuntimeIdentityTests(unittest.TestCase):
	@patch.dict(os.environ, {"MCP_HTTP_SHARED_SECRET": SECRET}, clear=True)
	@patch("mcp_erpnext.runtime.resolve_frappe_user_from_http", return_value="sales.a@example.com")
	@patch("mcp_erpnext.runtime.frappe")
	def test_http_user_comes_from_request_identity_not_service_user(self, frappe, resolve_user):
		frappe.local = SimpleNamespace(site="test.localhost", initialised=True)
		frappe.session = SimpleNamespace(user="Guest")
		frappe.set_user.side_effect = lambda user: setattr(frappe.session, "user", user)
		identity = HTTPIdentityInputs(f"Bearer {SECRET}", "sales.a@example.com")

		self.assertEqual(runtime._ensure_context(_settings(), runtime_identity=identity), {
			"site": "test.localhost", "user": "sales.a@example.com"
		})
		resolve_user.assert_called_once_with(identity, shared_secret=SECRET)
		frappe.set_user.assert_called_once_with("sales.a@example.com")

	@patch.dict(os.environ, {"MCP_HTTP_SHARED_SECRET": SECRET}, clear=True)
	@patch("mcp_erpnext.runtime.resolve_frappe_user_from_http", side_effect=MCPAuthenticationInvalidError())
	@patch("mcp_erpnext.runtime.frappe")
	def test_invalid_identity_does_not_execute_the_http_tool(self, frappe, resolve_user):
		frappe.local = SimpleNamespace(site=None, initialised=False)
		frappe.session = SimpleNamespace(user="Guest")
		operation = Mock()
		with self.assertRaises(MCPAuthenticationInvalidError):
			runtime._run_http_tool(
				_settings(), HTTPIdentityInputs("Bearer wrong", "sales@example.com"), operation
			)
		operation.assert_not_called()
		self.assertEqual(frappe.destroy.call_count, 2)

	@patch("mcp_erpnext.observability.get_app_logger")
	def test_identity_failures_use_safe_public_error_codes(self, get_app_logger):
		get_app_logger.return_value = Mock()
		result = observability.execute_tool(
			"search_customers", lambda: (_ for _ in ()).throw(MCPAuthenticationInvalidError())
		)
		self.assertEqual(result["code"], "MCP_AUTHENTICATION_INVALID")
		self.assertFalse(result["retryable"])

	def test_concurrent_http_identities_do_not_cross_frappe_contexts(self):
		class ContextScopedFrappe:
			def __init__(self):
				self._local = ContextVar("frappe_local", default=None)

			@property
			def local(self):
				return self._local.get() or SimpleNamespace(site=None, initialised=False)

			@property
			def session(self):
				return self.local.session

			def destroy(self): self._local.set(None)
			def init(self, *, site, **_kwargs):
				self._local.set(SimpleNamespace(site=site, initialised=True, session=SimpleNamespace(user="Guest")))
			def connect(self, **_kwargs): return None
			def set_user(self, user): self.session.user = user

		frappe = ContextScopedFrappe()
		identities = {"a@example.com": "sales.a@example.com", "b@example.com": "sales.b@example.com"}
		with patch.dict(os.environ, {"MCP_HTTP_SHARED_SECRET": SECRET}, clear=True), patch(
			"mcp_erpnext.runtime.frappe", frappe
		), patch(
			"mcp_erpnext.runtime.resolve_frappe_user_from_http",
			side_effect=lambda identity, **_kwargs: identities[identity.user_email],
		):
			with ThreadPoolExecutor(max_workers=2) as executor:
				results = list(executor.map(
					lambda email: runtime._run_http_tool(
						_settings(), HTTPIdentityInputs(f"Bearer {SECRET}", email), lambda: frappe.session.user
					), identities
				))
		self.assertEqual(results, ["sales.a@example.com", "sales.b@example.com"])
