from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mcp_erpnext.config.business_defaults import (
	BusinessDefaultKey,
	SUPPORTED_DOCUMENT_TYPES,
	get_document_business_default,
)
from mcp_erpnext.setup import install


class BusinessDefaultsInstallTests(unittest.TestCase):
	def _run_ensure(self, conf: dict):
		fake_frappe = SimpleNamespace(conf=conf)
		update_site_config = Mock()
		echo = Mock()
		with (
			patch.object(install, "frappe", fake_frappe),
			patch.object(install, "update_site_config", update_site_config),
			patch.object(install.click, "echo", echo),
		):
			created = install.ensure_business_defaults_site_config()
		return created, update_site_config, echo

	def test_missing_configuration_writes_valid_scaffold_and_reports_initialization(self):
		created, update_site_config, echo = self._run_ensure({"db_name": "test_db"})

		self.assertTrue(created)
		update_site_config.assert_called_once_with(
			"mcp_business_defaults", {"site": {}, "companies": {}, "quotation_validity_days": 0}
		)
		echo.assert_called_once_with(install.INITIALIZED_MESSAGE)

	def test_existing_configuration_is_preserved_exactly_for_every_existing_value(self):
		for existing in (
			{"site": {"Quotation": {"payment_terms_template": "Standard Plan"}}},
			{},
			None,
			["malformed"],
		):
			with self.subTest(existing=existing):
				created, update_site_config, echo = self._run_ensure(
					{"mcp_business_defaults": existing, "unrelated_key": "unchanged"}
				)

				self.assertFalse(created)
				update_site_config.assert_not_called()
				echo.assert_called_once_with(install.PRESERVED_MESSAGE)

	def test_repeated_invocation_writes_only_once_and_preserves_unrelated_config(self):
		conf = {"db_name": "test_db", "unrelated_key": {"keep": True}}
		fake_frappe = SimpleNamespace(conf=conf)
		update_site_config = Mock(
			side_effect=lambda key, value: fake_frappe.conf.__setitem__(key, value)
		)
		echo = Mock()
		with (
			patch.object(install, "frappe", fake_frappe),
			patch.object(install, "update_site_config", update_site_config),
			patch.object(install.click, "echo", echo),
		):
			self.assertTrue(install.ensure_business_defaults_site_config())
			self.assertFalse(install.ensure_business_defaults_site_config())

		update_site_config.assert_called_once_with(
			"mcp_business_defaults", {"site": {}, "companies": {}, "quotation_validity_days": 0}
		)
		self.assertEqual(conf["unrelated_key"], {"keep": True})
		self.assertEqual(
			echo.call_args_list,
			[
				((install.INITIALIZED_MESSAGE,), {}),
				((install.PRESERVED_MESSAGE,), {}),
			],
		)

	def test_scaffold_resolves_no_template_names(self):
		frappe_module = SimpleNamespace(
			conf={"mcp_business_defaults": {"site": {}, "companies": {}, "quotation_validity_days": 0}}
		)
		for doctype in SUPPORTED_DOCUMENT_TYPES:
			for key in BusinessDefaultKey:
				with self.subTest(doctype=doctype, key=key):
					self.assertIsNone(
						get_document_business_default(
							doctype, key, "Any Company", frappe_module=frappe_module
						)
					)

	def test_after_install_delegates_to_shared_helper(self):
		with patch.object(install, "ensure_business_defaults_site_config") as ensure:
			install.after_install()

		ensure.assert_called_once_with()


if __name__ == "__main__":
	unittest.main()
