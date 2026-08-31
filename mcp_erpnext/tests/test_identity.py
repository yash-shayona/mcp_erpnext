from __future__ import annotations

import os
import unittest
from json import loads
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from mcp_erpnext.identity import resolve_frappe_user_for_runtime
from mcp_erpnext.observability import ERPAccessNotConfiguredError, MCPIdentityConfigurationError
from mcp_erpnext.settings import MCPSettings
from mcp_erpnext.transport_identity import RuntimeIdentity


def _settings(**overrides) -> MCPSettings:
	values = {
		"backend": "direct",
		"frappe_site": "test.localhost",
		"frappe_user": "service@example.com",
		"identity_mode": "librechat",
		"librechat_user_id": "lc-user-a",
		"librechat_user_email": "reference@example.com",
		"erpnext_base_url": None,
		"erpnext_api_key": None,
		"erpnext_api_secret": None,
	}
	values.update(overrides)
	return MCPSettings(**values)


class SettingsIdentityTests(unittest.TestCase):
	@patch.dict(os.environ, {"MCP_BACKEND": "direct", "MCP_FRAPPE_SITE": "test.localhost"}, clear=True)
	def test_identity_mode_defaults_to_service(self):
		settings = MCPSettings.from_environment()
		self.assertEqual(settings.identity_mode, "service")

	@patch.dict(
		os.environ,
		{
			"MCP_BACKEND": "direct",
			"MCP_FRAPPE_SITE": "test.localhost",
			"MCP_IDENTITY_MODE": "service",
			"MCP_FRAPPE_USER": "sales@example.com",
		},
		clear=True,
	)
	def test_explicit_service_mode_uses_configured_frappe_user(self):
		self.assertEqual(resolve_frappe_user_for_runtime(MCPSettings.from_environment()), "sales@example.com")

	def test_librechat_mode_requires_a_user_id(self):
		with self.assertRaises(MCPIdentityConfigurationError):
			_settings(librechat_user_id="  ").validate_identity_mode()

	def test_invalid_identity_mode_fails_deterministically(self):
		with self.assertRaises(MCPIdentityConfigurationError):
			_settings(identity_mode="unknown").validate_identity_mode()


class LibreChatIdentityResolutionTests(unittest.TestCase):
	def setUp(self) -> None:
		self.frappe = Mock()
		self.frappe.db.get_value.side_effect = [
			"sales.a@example.com",
			SimpleNamespace(name="sales.a@example.com", enabled=1),
		]
		self.frappe_patch = patch("mcp_erpnext.identity.frappe", self.frappe)
		self.frappe_patch.start()
		self.addCleanup(self.frappe_patch.stop)

	def test_exact_librechat_id_maps_to_the_expected_frappe_user(self):
		self.assertEqual(resolve_frappe_user_for_runtime(_settings()), "sales.a@example.com")
		self.assertEqual(
			self.frappe.db.get_value.call_args_list,
			[
				call(
					"LibreChat User Mapping",
					{"librechat_user_id": "lc-user-a", "enabled": 1},
					"frappe_user",
				),
				call("User", "sales.a@example.com", ["name", "enabled"], as_dict=True),
			],
		)

	def test_librechat_id_remains_authoritative_when_email_changes(self):
		self.assertEqual(
			resolve_frappe_user_for_runtime(_settings(librechat_user_email="changed@example.com")),
			"sales.a@example.com",
		)
		self.assertNotIn("changed@example.com", str(self.frappe.db.get_value.call_args_list))

	def test_matching_email_without_matching_id_does_not_grant_access(self):
		self.frappe.db.get_value.side_effect = [None]
		with self.assertRaises(ERPAccessNotConfiguredError):
			resolve_frappe_user_for_runtime(_settings(librechat_user_id="unknown-id"))
		self.assertEqual(
			self.frappe.db.get_value.call_args.args[1],
			{"librechat_user_id": "unknown-id", "enabled": 1},
		)

	def test_disabled_mapping_is_denied(self):
		self.frappe.db.get_value.side_effect = [None]
		with self.assertRaises(ERPAccessNotConfiguredError):
			resolve_frappe_user_for_runtime(_settings())

	def test_disabled_frappe_user_is_denied(self):
		self.frappe.db.get_value.side_effect = ["sales.a@example.com", SimpleNamespace(name="sales.a@example.com", enabled=0)]
		with self.assertRaises(ERPAccessNotConfiguredError):
			resolve_frappe_user_for_runtime(_settings())

	def test_guest_mapping_is_denied(self):
		self.frappe.db.get_value.side_effect = ["Guest", SimpleNamespace(name="Guest", enabled=1)]
		with self.assertRaises(ERPAccessNotConfiguredError):
			resolve_frappe_user_for_runtime(_settings())

	def test_librechat_mode_ignores_mcp_frappe_user(self):
		self.assertEqual(
			resolve_frappe_user_for_runtime(_settings(frappe_user="Administrator")),
			"sales.a@example.com",
		)

	def test_http_identity_cannot_fall_back_to_environment_identity(self):
		with self.assertRaises(MCPIdentityConfigurationError):
			resolve_frappe_user_for_runtime(
				_settings(
					frappe_user="Administrator",
					librechat_user_id="environment-user",
				),
				RuntimeIdentity("librechat_http", None, "reference@example.com"),
			)


class LibreChatMappingDocTypeTests(unittest.TestCase):
	def test_doctype_enforces_one_to_one_mapping_for_system_managers(self):
		path = (
			Path(__file__).parents[1]
			/ "mcp_erpnext/doctype/librechat_user_mapping/librechat_user_mapping.json"
		)
		doctype = loads(path.read_text())
		fields = {field["fieldname"]: field for field in doctype["fields"]}

		self.assertTrue(fields["librechat_user_id"]["unique"])
		self.assertTrue(fields["frappe_user"]["unique"])
		self.assertEqual(fields["frappe_user"]["options"], "User")
		self.assertEqual(fields["enabled"]["default"], "1")
		self.assertEqual(doctype["permissions"], [{"create": 1, "delete": 1, "read": 1, "role": "System Manager", "write": 1}])
