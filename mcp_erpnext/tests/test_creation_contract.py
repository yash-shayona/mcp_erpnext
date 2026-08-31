from __future__ import annotations

import unittest
from types import SimpleNamespace

from mcp_erpnext.services.common.creation_contract import resolve_creation_contract


class CreationContractTests(unittest.TestCase):
	def test_user_input_precedes_policy_and_runtime_default(self):
		meta = SimpleNamespace(
			fields=[SimpleNamespace(fieldname="code", label="Code", fieldtype="Data", reqd=1)]
		)
		contract = resolve_creation_contract(
			doctype="Example",
			input_values={"code": "USER-CODE"},
			creation_fields=("code",),
			policy_values={"code": "POLICY-CODE"},
			path_prefix="example",
			get_meta=lambda _: meta,
			new_document=lambda _: {"code": "DEFAULT-CODE"},
		)
		self.assertEqual(contract["values"], {"code": "USER-CODE"})
		self.assertEqual(contract["sources"], {"code": "user_input"})

	def test_runtime_default_satisfies_required_field(self):
		meta = SimpleNamespace(
			fields=[SimpleNamespace(fieldname="customer_type", label="Customer Type", fieldtype="Select", reqd=1)]
		)
		contract = resolve_creation_contract(
			doctype="Customer",
			input_values={},
			creation_fields=("customer_type",),
			policy_values={},
			path_prefix="customer",
			get_meta=lambda _: meta,
			new_document=lambda _: {"customer_type": "Company"},
		)
		self.assertEqual(contract["missing"], [])
		self.assertEqual(contract["sources"], {"customer_type": "erpnext_default"})

	def test_missing_metadata_field_has_structured_contract(self):
		meta = SimpleNamespace(
			fields=[SimpleNamespace(fieldname="custom_registration_number", label="Registration Number", fieldtype="Data", reqd=1)]
		)
		contract = resolve_creation_contract(
			doctype="Customer",
			input_values={},
			creation_fields=("custom_registration_number",),
			policy_values={},
			path_prefix="customer",
			get_meta=lambda _: meta,
			new_document=lambda _: {},
		)
		self.assertEqual(contract["missing"], ["customer.custom_registration_number"])
		self.assertEqual(contract["missing_fields"][0]["source"], "erpnext_metadata")

	def test_policy_value_is_distinct_from_runtime_default(self):
		meta = SimpleNamespace(
			fields=[SimpleNamespace(fieldname="is_sales_item", label="Is Sales Item", fieldtype="Check", reqd=0)]
		)
		contract = resolve_creation_contract(
			doctype="Item",
			input_values={},
			creation_fields=("is_sales_item",),
			policy_values={"is_sales_item": 1},
			path_prefix="item",
			get_meta=lambda _: meta,
			new_document=lambda _: {"is_sales_item": 0},
		)
		self.assertEqual(contract["values"], {"is_sales_item": 1})
		self.assertEqual(contract["sources"], {"is_sales_item": "mcp_policy"})


if __name__ == "__main__":
	unittest.main()
