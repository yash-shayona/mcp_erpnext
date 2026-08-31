from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import APPROVAL_TTL_SECONDS, approvals
from mcp_erpnext.config.masters import item as item_config
from mcp_erpnext.services.masters import item as item_service
from mcp_erpnext.services.selling import sales_order


class FakeMeta:
	def __init__(self, fields: list[SimpleNamespace]):
		self.fields = fields


class DefaultDocument:
	def __init__(self, values: dict):
		self.values = values

	def get(self, fieldname: str):
		return self.values.get(fieldname)


class FakeDoc:
	def __init__(self, values: dict):
		self.values = dict(values)
		self.name = self.values.get("name", self.values.get("item_code", "ITEM-TEST-0001"))
		self.item_code = self.values.get("item_code")
		self.item_name = self.values.get("item_name") or self.item_code
		self.stock_uom = self.values.get("stock_uom")
		self.insert_calls: list[dict] = []

	def insert(self, **kwargs):
		self.insert_calls.append(kwargs)
		return self


class ItemServiceTests(unittest.TestCase):
	def setUp(self):
		approvals._approvals.clear()
		self.docs: list[FakeDoc] = []
		self.list_rows: dict[str, list[dict]] = {}
		self.commit_count = 0
		self.rollback_count = 0
		self.defaults: dict[str, object] = {}
		self.meta_fields = [
			SimpleNamespace(fieldname="item_code", label="Item Code", fieldtype="Data", reqd=1),
			SimpleNamespace(fieldname="item_name", label="Item Name", fieldtype="Data", reqd=0),
			SimpleNamespace(fieldname="item_group", label="Item Group", fieldtype="Link", options="Item Group", reqd=1),
			SimpleNamespace(fieldname="stock_uom", label="Default Unit of Measure", fieldtype="Link", options="UOM", reqd=1),
			SimpleNamespace(fieldname="is_stock_item", label="Maintain Stock", fieldtype="Check", reqd=0),
			SimpleNamespace(fieldname="is_sales_item", label="Is Sales Item", fieldtype="Check", reqd=0),
		]
		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			get_meta=lambda _: FakeMeta(self.meta_fields),
			new_doc=lambda _: DefaultDocument(self.defaults),
			has_permission=lambda *_: True,
			get_list=self._get_list,
			get_doc=self._get_doc,
			db=SimpleNamespace(commit=self._commit, rollback=self._rollback),
			PermissionError=frappe.PermissionError,
		)
		self.patches = [patch.object(item_service, "frappe", self.fake_frappe)]
		for active_patch in self.patches:
			active_patch.start()

	def tearDown(self):
		for active_patch in reversed(self.patches):
			active_patch.stop()

	def _get_list(self, doctype, *, filters=None, **kwargs):
		if doctype == "Item Group":
			query = (kwargs.get("or_filters") or [[None, None, None, ""]])[0][3].strip("%").casefold()
			return [] if query == "missing" else [{"name": "Products"}]
		if doctype == "UOM":
			query = (kwargs.get("or_filters") or [[None, None, None, ""]])[0][3].strip("%").casefold()
			return [] if query == "missing" else [{"name": "Nos"}]
		if doctype == "Item" and filters and "item_code" in filters:
			return self.list_rows.get(filters["item_code"], [])
		return []

	def _get_doc(self, values):
		doc = FakeDoc(values)
		self.docs.append(doc)
		return doc

	def _commit(self):
		self.commit_count += 1

	def _rollback(self):
		self.rollback_count += 1

	@staticmethod
	def valid_item(**overrides):
		item = {"item_code": "NEW-ITEM-001", "item_name": "New Item", "item_group": "Products", "stock_uom": "Nos"}
		item.update(overrides)
		return item

	def test_exact_item_resolves_to_reusable_reference(self):
		candidate = {"value": "ITEM-001", "label": "Blue Polo", "item_code": "ITEM-001", "item_name": "Blue Polo", "stock_uom": "Nos"}
		with patch.object(item_service, "resolve_sales_item", return_value={"status": "resolved", "candidate": candidate, "match_type": "exact"}):
			result = item_service.resolve_item_for_workflow("ITEM-001")
		self.assertEqual(result["status"], "resolved")
		self.assertEqual(result["item"], {"doctype": "Item", "name": "ITEM-001", "item_code": "ITEM-001", "item_name": "Blue Polo", "stock_uom": "Nos"})

	def test_multiple_items_require_selection(self):
		with patch.object(item_service, "resolve_sales_item", return_value={"status": "ambiguous", "candidates": [{"value": "ITEM-1"}, {"value": "ITEM-2"}]}):
			result = item_service.resolve_item_for_workflow("Polo")
		self.assertEqual(result["status"], "needs_selection")
		self.assertEqual(len(result["candidates"]), 2)

	def test_missing_item_requires_controlled_creation(self):
		with patch.object(item_service, "resolve_sales_item", return_value={"status": "not_found", "candidates": []}):
			self.assertEqual(item_service.resolve_item_for_workflow("New Item")["status"], "needs_item_creation")

	def test_sales_item_search_remains_permission_scoped(self):
		candidate = {"value": "ITEM-001", "label": "Blue Polo", "score": 1.0}
		with patch.object(item_service, "find_candidates", return_value=[candidate]) as find_candidates:
			result = item_service.search_items("ITEM-001")
		self.assertEqual(result["status"], "resolved")
		self.assertEqual(result["candidates"], [candidate])
		self.assertEqual(find_candidates.call_args.args[2], {"disabled": ["!=", 1], "is_sales_item": 1})

	def test_duplicate_item_code_blocks_preparation(self):
		self.list_rows = {"NEW-ITEM-001": [{"name": "NEW-ITEM-001", "item_code": "NEW-ITEM-001", "item_name": "Existing", "stock_uom": "Nos", "disabled": 0}]}
		result = item_service.prepare_item(self.valid_item())
		self.assertEqual(result["status"], "duplicate_suspected")
		self.assertEqual(result["duplicates"][0]["identifier"], "item_code")

	def test_missing_mandatory_item_field_is_rejected(self):
		result = item_service.prepare_item(self.valid_item(item_group=""))
		self.assertEqual(result["status"], "needs_input")
		self.assertEqual(result["missing"], ["item.item_group"])

	def test_item_group_and_uom_validation_use_metadata_derived_links(self):
		missing_group = item_service.prepare_item(self.valid_item(item_group="Missing Group"))
		self.assertEqual(missing_group["status"], "not_found")
		self.assertEqual(missing_group["target_doctype"], "Item Group")
		missing_uom = item_service.prepare_item(self.valid_item(stock_uom="Missing UOM"))
		self.assertEqual(missing_uom["status"], "not_found")
		self.assertEqual(missing_uom["target_doctype"], "UOM")

	def test_runtime_default_removes_mandatory_item_prompt(self):
		self.defaults["stock_uom"] = "Nos"
		prepared = item_service.prepare_item(self.valid_item(stock_uom=""))
		self.assertEqual(prepared["status"], "ready")
		self.assertEqual(approvals._approvals[prepared["approval_token"]].payload["stock_uom"], "Nos")

	def test_metadata_driven_custom_required_item_field_is_reported(self):
		self.meta_fields.append(SimpleNamespace(fieldname="custom_material_grade", label="Material Grade", fieldtype="Data", reqd=1))
		with patch.object(
			item_config,
			"CREATION_FIELDS",
			item_config.CREATION_FIELDS + ("custom_material_grade",),
		):
			result = item_service.prepare_item(self.valid_item())
		self.assertEqual(result["status"], "needs_input")
		self.assertEqual(result["missing"], ["item.custom_material_grade"])
		self.assertEqual(result["missing_fields"][0]["label"], "Material Grade")

	def test_sales_item_is_explicit_mcp_policy(self):
		prepared = item_service.prepare_item(self.valid_item())
		self.assertEqual(prepared["status"], "ready")
		self.assertEqual(approvals._approvals[prepared["approval_token"]].payload["is_sales_item"], 1)

	def test_user_without_item_create_permission_is_rejected(self):
		with patch.object(self.fake_frappe, "has_permission", side_effect=lambda doctype, *_: doctype != "Item"):
			result = item_service.prepare_item(self.valid_item())
		self.assertEqual(result["status"], "permission_denied")

	def test_preparation_does_not_write_or_expose_pricing(self):
		result = item_service.prepare_item(self.valid_item())
		self.assertEqual(result["status"], "ready")
		self.assertEqual(self.commit_count, 0)
		self.assertEqual(self.docs, [])
		self.assertNotIn("standard_rate", result["preview"])
		self.assertNotIn("valuation_rate", result["preview"])
		self.assertNotIn("taxes", result["preview"])

	def test_valid_confirmation_creates_once_with_normal_permissions(self):
		prepared = item_service.prepare_item(self.valid_item())
		result = item_service.confirm_item(prepared["approval_token"], True)
		self.assertEqual(result["status"], "created")
		self.assertFalse(result["idempotent"])
		self.assertEqual(self.commit_count, 1)
		self.assertEqual(self.docs[-1].insert_calls, [{"ignore_permissions": False, "ignore_links": False, "ignore_mandatory": False}])

	def test_wrong_or_expired_confirmation_is_rejected(self):
		wrong = item_service.confirm_item("not-issued", True)
		self.assertEqual(wrong["code"], "CONFIRMATION_EXPIRED")
		prepared = item_service.prepare_item(self.valid_item())
		approvals._approvals[prepared["approval_token"]].created_at -= APPROVAL_TTL_SECONDS + 1
		expired = item_service.confirm_item(prepared["approval_token"], True)
		self.assertEqual(expired["code"], "CONFIRMATION_EXPIRED")

	def test_confirmation_rechecks_duplicate_before_writing(self):
		prepared = item_service.prepare_item(self.valid_item())
		self.list_rows = {"NEW-ITEM-001": [{"name": "NEW-ITEM-001", "item_code": "NEW-ITEM-001", "item_name": "Race", "stock_uom": "Nos", "disabled": 0}]}
		result = item_service.confirm_item(prepared["approval_token"], True)
		self.assertEqual(result["status"], "duplicate_suspected")
		self.assertEqual(self.commit_count, 0)

	def test_sales_order_item_resolution_contract_is_unchanged(self):
		with patch.object(sales_order, "resolve_sales_item", return_value={"status": "resolved", "candidate": {"value": "ITEM-001", "item_name": "Blue Polo"}, "match_type": "exact"}):
			result = sales_order._prepare_items([{"item": "ITEM-001", "qty": 2}])
		self.assertEqual(result, {"status": "resolved", "items": [{"item_code": "ITEM-001", "item_name": "Blue Polo", "qty": 2.0, "match_type": "exact"}]})


if __name__ == "__main__":
	unittest.main()
