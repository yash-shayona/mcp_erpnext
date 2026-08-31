from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mcp_erpnext import observability, runtime
from mcp_erpnext.observability import ERPAccessNotConfiguredError, MCPIdentityConfigurationError
from mcp_erpnext.settings import MCPSettings
from mcp_erpnext.transport_identity import RuntimeIdentity


def _librechat_settings() -> MCPSettings:
	return MCPSettings(
		backend="direct",
		frappe_site="test.localhost",
		frappe_user="Administrator",
		identity_mode="librechat",
		librechat_user_id="lc-user-a",
		librechat_user_email=None,
		erpnext_base_url=None,
		erpnext_api_key=None,
		erpnext_api_secret=None,
	)


class RuntimeIdentityTests(unittest.TestCase):
	@patch("mcp_erpnext.runtime.resolve_frappe_user_for_runtime", return_value="sales.a@example.com")
	@patch("mcp_erpnext.runtime.MCPSettings.from_environment")
	@patch("mcp_erpnext.runtime.frappe")
	def test_librechat_mode_cannot_be_bypassed_by_a_user_override(self, frappe, from_environment, resolve_user):
		settings = _librechat_settings()
		from_environment.return_value = settings
		frappe.local = SimpleNamespace(site="test.localhost", initialised=True)
		frappe.session = SimpleNamespace(user="Guest")
		frappe.set_user.side_effect = lambda user: setattr(frappe.session, "user", user)

		result = runtime.ensure_context(user="Administrator")

		self.assertEqual(result, {"site": "test.localhost", "user": "sales.a@example.com"})
		self.assertEqual(frappe.session.user, "sales.a@example.com")
		resolve_user.assert_called_once_with(settings)
		frappe.set_user.assert_called_once_with("sales.a@example.com")

	@patch("mcp_erpnext.runtime.resolve_frappe_user_for_runtime")
	@patch("mcp_erpnext.runtime.MCPSettings.from_environment")
	@patch("mcp_erpnext.runtime.frappe")
	def test_distinct_librechat_users_remain_isolated_across_context_calls(
		self, frappe, from_environment, resolve_user
	):
		settings_a = _librechat_settings()
		settings_b = _librechat_settings()
		settings_b = MCPSettings(
			**{**settings_b.__dict__, "librechat_user_id": "lc-user-b"}
		)
		from_environment.side_effect = [settings_a, settings_b]
		resolve_user.side_effect = ["sales.a@example.com", "sales.b@example.com"]
		frappe.local = SimpleNamespace(site="test.localhost", initialised=True)
		frappe.session = SimpleNamespace(user="Guest")
		frappe.set_user.side_effect = lambda user: setattr(frappe.session, "user", user)

		self.assertEqual(runtime.ensure_context()["user"], "sales.a@example.com")
		self.assertEqual(runtime.ensure_context()["user"], "sales.b@example.com")
		self.assertEqual(frappe.set_user.call_args_list[0].args, ("sales.a@example.com",))
		self.assertEqual(frappe.set_user.call_args_list[1].args, ("sales.b@example.com",))

	@patch("mcp_erpnext.observability.get_app_logger")
	def test_identity_failures_use_the_safe_public_error_codes(self, get_app_logger):
		get_app_logger.return_value = Mock()
		for error, code in (
			(ERPAccessNotConfiguredError(), "ERP_ACCESS_NOT_CONFIGURED"),
			(MCPIdentityConfigurationError(), "ERP_IDENTITY_CONFIGURATION_ERROR"),
		):
			with self.subTest(code=code):
				result = observability.execute_tool("search_customers", lambda: (_ for _ in ()).throw(error))
				self.assertEqual(result["code"], code)
				self.assertFalse(result["retryable"])
				if code == "ERP_ACCESS_NOT_CONFIGURED":
					self.assertEqual(
						result["message"],
						"Your LibreChat account is not linked to an active ERPNext user. "
						"Please contact your administrator.",
					)

	@patch("mcp_erpnext.runtime.resolve_frappe_user_for_runtime", return_value="sales.a@example.com")
	@patch("mcp_erpnext.runtime.frappe")
	def test_http_scope_is_destroyed_after_success_and_exception(self, frappe, resolve_user):
		settings = MCPSettings(
			**{
				**_librechat_settings().__dict__,
				"transport": "streamable-http",
				"http_shared_secret": "this-is-a-development-only-secret-with-32-chars",
			}
		)
		frappe.local = SimpleNamespace(site=None, initialised=False)
		frappe.session = SimpleNamespace(user="Guest")
		frappe.set_user.side_effect = lambda user: setattr(frappe.session, "user", user)
		identity = RuntimeIdentity("librechat_http", "lc-user-a", None)

		self.assertEqual(
			runtime._run_http_tool(settings, identity, lambda: {"user": frappe.session.user}),
			{"user": "sales.a@example.com"},
		)
		self.assertEqual(frappe.destroy.call_count, 2)

		with self.assertRaisesRegex(RuntimeError, "failure"):
			runtime._run_http_tool(settings, identity, lambda: (_ for _ in ()).throw(RuntimeError("failure")))
		self.assertEqual(frappe.destroy.call_count, 4)

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

			def destroy(self):
				self._local.set(None)

			def init(self, *, site, **_kwargs):
				self._local.set(
					SimpleNamespace(site=site, initialised=True, session=SimpleNamespace(user="Guest"))
				)

			def connect(self, **_kwargs):
				return None

			def set_user(self, user):
				self.session.user = user

		settings = MCPSettings(
			**{
				**_librechat_settings().__dict__,
				"transport": "streamable-http",
				"http_shared_secret": "this-is-a-development-only-secret-with-32-chars",
			}
		)
		frappe = ContextScopedFrappe()
		identities = {
			"lc-user-a": "sales.a@example.com",
			"lc-user-b": "sales.b@example.com",
		}

		with patch("mcp_erpnext.runtime.frappe", frappe), patch(
			"mcp_erpnext.runtime.resolve_frappe_user_for_runtime",
			side_effect=lambda _settings, identity: identities[identity.librechat_user_id],
		):
			with ThreadPoolExecutor(max_workers=2) as executor:
				results = list(
					executor.map(
						lambda librechat_user_id: runtime._run_http_tool(
							settings,
							RuntimeIdentity("librechat_http", librechat_user_id, None),
							lambda: frappe.session.user,
						),
						identities,
					)
				)

		self.assertEqual(results, ["sales.a@example.com", "sales.b@example.com"])
