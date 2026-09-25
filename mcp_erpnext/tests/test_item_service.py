from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import APPROVAL_TTL_SECONDS, approvals
from mcp_erpnext.config.masters import item as item_config
from mcp_erpnext.services.common.effective_requirements import EffectiveRequirementContext, RequirementStatus
from mcp_erpnext.services.integrations.india_compliance_item import india_compliance_item_preflight
from mcp_erpnext.services.masters import item as item_service
from mcp_erpnext.services.selling import sales_order
from mcp_erpnext.tests.approval_test_backend import (
	install_fake_backend,
	mutate_record,
	read_record,
)


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
		self.approval_backend = install_fake_backend(approvals)
		self.docs: list[FakeDoc] = []
		self.list_rows: dict[str, list[dict]] = {}
		self.commit_count = 0
		self.rollback_count = 0
		self.defaults: dict[str, object] = {}
		self.installed_apps: list[str] = []
		self.gst_settings: tuple[object, object] | None = (0, "6")
		self.item_group_hsn: str | None = None
		self.item_group_read_error = False
		self.hsn_rows: list[dict[str, object]] = []
		self.meta_fields = [
			SimpleNamespace(fieldname="item_code", label="Item Code", fieldtype="Data", reqd=1),
			SimpleNamespace(fieldname="item_name", label="Item Name", fieldtype="Data", reqd=0),
			SimpleNamespace(fieldname="description", label="Description", fieldtype="Text Editor", reqd=0),
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
			get_installed_apps=lambda: self.installed_apps,
			get_cached_value=lambda *args: self.gst_settings,
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
		if doctype == "GST HSN Code":
			return self.hsn_rows
		if doctype == "Item Group":
			if filters and "name" in filters:
				if self.item_group_read_error:
					raise RuntimeError("item group read failed")
				return [{"name": filters["name"], "gst_hsn_code": self.item_group_hsn}]
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
		self.assertEqual(result["doctype"], "Item")
		self.assertEqual(result["reference"], {"doctype": "Item", "name": "ITEM-001", "item_code": "ITEM-001", "item_name": "Blue Polo", "stock_uom": "Nos"})

	def test_multiple_items_require_selection(self):
		with patch.object(item_service, "resolve_sales_item", return_value={"status": "ambiguous", "candidates": [{"value": "SV-FRAPPE-DEVELOPMENT", "label": "Frappe Custom App Development", "score": 0.597}, {"value": "SV-WEBSITE-DEVELOPMENT", "label": "Website Development", "score": 0.55}]}):
			result = item_service.resolve_item_for_workflow("Development Item")
		self.assertEqual(result["status"], "ambiguous")
		self.assertEqual(result["doctype"], "Item")
		self.assertEqual(result["candidates"][0]["reference"]["name"], "SV-FRAPPE-DEVELOPMENT")
		self.assertEqual(len(result["candidates"]), 2)

	def test_missing_item_requires_controlled_creation(self):
		with patch.object(item_service, "resolve_sales_item", return_value={"status": "not_found", "candidates": []}):
			self.assertEqual(item_service.resolve_item_for_workflow("New Item")["status"], "not_found")

	def test_sales_item_search_remains_permission_scoped(self):
		candidate = {"value": "ITEM-001", "label": "Blue Polo", "score": 1.0}
		with patch.object(item_service, "find_candidates", return_value=[candidate]) as find_candidates:
			result = item_service.search_items("ITEM-001")
		self.assertEqual(result["status"], "resolved")
		self.assertEqual(
			result["candidates"],
			[
				{
					"reference": {
						"doctype": "Item",
						"name": "ITEM-001",
						"item_code": "ITEM-001",
						"item_name": "Blue Polo",
						"stock_uom": None,
					},
					"label": "Blue Polo",
					"score": 1.0,
				}
			],
		)
		self.assertEqual(find_candidates.call_args.args[2], {"disabled": ["!=", 1], "is_sales_item": 1})

	def test_weak_related_candidates_become_not_found_for_item_resolution_and_search(self):
		candidates = [
			{"value": "SV-WEBAPP-DEVELOPMENT", "label": "Custom Web Application Development", "score": 0.677},
			{"value": "SV-FRAPPE-DEVELOPMENT", "label": "Frappe Custom App Development", "score": 0.561},
			{"value": "SV-API-INTEGRATION", "label": "API Integration Development", "score": 0.499},
		]
		with patch.object(item_service, "find_candidates", return_value=candidates):
			resolved = item_service.resolve_sales_item("Web Development Services")
			searched = item_service.search_items("Web Development Services")
		self.assertEqual(resolved, {"status": "not_found", "query": "Web Development Services", "candidates": []})
		self.assertEqual(searched["status"], "not_found")
		self.assertEqual(searched["candidates"], [])

	def test_item_ambiguity_and_strong_spelling_correction_are_preserved(self):
		ambiguous = [
			{"value": "SV-WEBSITE-DEVELOPMENT", "label": "Website Development", "score": 0.693},
			{"value": "SV-FRAPPE-DEVELOPMENT", "label": "Frappe Custom App Development", "score": 0.597},
		]
		with patch.object(item_service, "find_candidates", return_value=ambiguous):
			result = item_service.resolve_sales_item("Development Item")
		self.assertEqual(result["status"], "ambiguous")
		self.assertEqual(len(result["candidates"]), 2)

		strong = [{"value": "ITEM-001", "label": "Blue Polo", "score": 0.92}]
		with patch.object(item_service, "find_candidates", return_value=strong):
			result = item_service.resolve_sales_item("Blue Plo")
		self.assertEqual(result["status"], "resolved")
		self.assertEqual(result["match_type"], "spelling_correction")

	def test_purchase_item_resolution_keeps_purchase_filters(self):
		with patch.object(item_service, "find_candidates", return_value=[]) as find_candidates:
			item_service.search_purchase_items("ITEM-001")
			item_service.resolve_purchase_item("ITEM-001")
		self.assertEqual(find_candidates.call_args.args[2], {"disabled": ["!=", 1], "is_purchase_item": 1})

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
		self.assertEqual(read_record(approvals, prepared["approval_token"]).payload["stock_uom"], "Nos")

	def _enable_hsn_requirement(self):
		self.installed_apps = ["india_compliance"]
		self.gst_settings = (1, "6")
		self.meta_fields.append(
			SimpleNamespace(
				fieldname="gst_hsn_code",
				label="HSN/SAC",
				fieldtype="Link",
				options="GST HSN Code",
				fetch_from="item_group.gst_hsn_code",
				fetch_if_empty=1,
			)
		)

	def test_erpnext_only_item_creation_does_not_require_or_carry_hsn(self):
		result = item_service.prepare_item(self.valid_item(gst_hsn_code="123456", unknown_field="ignored"))
		self.assertEqual(result["status"], "ready")
		payload = read_record(approvals, result["approval_token"]).payload
		self.assertNotIn("gst_hsn_code", payload)
		self.assertNotIn("unknown_field", payload)

	def test_installed_india_compliance_with_disabled_validation_does_not_require_hsn(self):
		self._enable_hsn_requirement()
		self.gst_settings = (0, "6")
		result = item_service.prepare_item(self.valid_item())
		self.assertEqual(result["status"], "ready")

	def test_active_hsn_requirement_stops_before_approval_when_missing(self):
		self._enable_hsn_requirement()
		result = item_service.prepare_item(self.valid_item())
		self.assertEqual(result["status"], "needs_input")
		self.assertEqual(result["missing"], ["item.gst_hsn_code"])
		self.assertIn("HSN/SAC", result["message"])
		self.assertTrue(self.approval_backend.is_empty())

	def test_supplied_hsn_continuation_is_resolved_and_bound_to_approval(self):
		self._enable_hsn_requirement()
		self.hsn_rows = [{"name": "123456"}]
		first = item_service.prepare_item(self.valid_item())
		self.assertEqual(first["status"], "needs_input")
		second = item_service.prepare_item(self.valid_item(gst_hsn_code="123456"))
		self.assertEqual(second["status"], "ready")
		self.assertEqual(
			read_record(approvals, second["approval_token"]).payload["gst_hsn_code"],
			"123456",
		)

	def test_active_hsn_requirement_accepts_six_and_eight_digits(self):
		self._enable_hsn_requirement()
		for item_code, hsn in (("NEW-ITEM-006", "123456"), ("NEW-ITEM-008", "12345678")):
			self.hsn_rows = [{"name": hsn}]
			result = item_service.prepare_item(self.valid_item(item_code=item_code, gst_hsn_code=hsn))
			self.assertEqual(result["status"], "ready")

	def test_active_hsn_requirement_rejects_invalid_length_before_approval(self):
		self._enable_hsn_requirement()
		self.hsn_rows = [{"name": "1234"}]
		result = item_service.prepare_item(self.valid_item(gst_hsn_code="1234"))
		self.assertEqual(result["status"], "needs_input")
		self.assertIn("6, 8", result["message"])
		self.assertTrue(self.approval_backend.is_empty())

	def test_item_group_hsn_is_safely_inherited(self):
		self._enable_hsn_requirement()
		self.item_group_hsn = "123456"
		self.hsn_rows = [{"name": "123456"}]
		original_get_meta = self.fake_frappe.get_meta
		self.fake_frappe.get_meta = lambda doctype: (
			FakeMeta(self.meta_fields + [SimpleNamespace(fieldname="gst_hsn_code", fieldtype="Link")])
			if doctype == "Item Group"
			else original_get_meta(doctype)
		)
		result = item_service.prepare_item(self.valid_item())
		self.assertEqual(result["status"], "ready")
		self.assertEqual(
			read_record(approvals, result["approval_token"]).payload["gst_hsn_code"],
			"123456",
		)

	def test_item_group_hsn_read_failure_does_not_satisfy_requirement(self):
		self._enable_hsn_requirement()
		self.item_group_read_error = True
		result = item_service.prepare_item(self.valid_item())
		self.assertEqual(result["status"], "error")
		self.assertEqual(result["code"], "ITEM_RUNTIME_REQUIREMENT_UNAVAILABLE")
		self.assertTrue(self.approval_backend.is_empty())

	def test_hsn_settings_failure_does_not_silently_disable_requirement(self):
		self._enable_hsn_requirement()
		self.gst_settings = None
		result = item_service.prepare_item(self.valid_item())
		self.assertEqual(result["status"], "error")
		self.assertEqual(result["code"], "ITEM_RUNTIME_REQUIREMENT_UNAVAILABLE")
		self.assertNotIn("gst_settings", result["message"])
		self.assertTrue(self.approval_backend.is_empty())

	def test_provider_does_not_apply_to_non_sales_item(self):
		self._enable_hsn_requirement()
		result = india_compliance_item_preflight(
			EffectiveRequirementContext(
				doctype="Item",
				site="test.localhost",
				values={"is_sales_item": 0, "item_group": "Products"},
				input_values={},
				fields={"gst_hsn_code": self.meta_fields[-1]},
				get_installed_apps=lambda: self.installed_apps,
				get_cached_value=lambda *args: self.gst_settings,
				get_meta=self.fake_frappe.get_meta,
				get_list=self._get_list,
			)
		)
		self.assertEqual(result.status, RequirementStatus.NOT_APPLICABLE)

	def test_active_provider_without_hsn_metadata_does_not_inject_field(self):
		self.installed_apps = ["india_compliance"]
		self.gst_settings = (1, "6")
		result = item_service.prepare_item(self.valid_item(gst_hsn_code="123456"))
		self.assertEqual(result["status"], "ready")
		payload = read_record(approvals, result["approval_token"]).payload
		self.assertNotIn("gst_hsn_code", payload)

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

	def test_custom_slug_is_bound_to_item_payload_and_preview(self):
		self.meta_fields.append(SimpleNamespace(fieldname="custom_slug", label="Slug", fieldtype="Data", reqd=1))
		result = item_service.prepare_item(self.valid_item(custom_slug="keyboard"))
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["custom_slug"], "keyboard")
		self.assertEqual(
			read_record(approvals, result["approval_token"]).payload["custom_slug"],
			"keyboard",
		)

	def test_sales_item_is_explicit_mcp_policy(self):
		prepared = item_service.prepare_item(self.valid_item())
		self.assertEqual(prepared["status"], "ready")
		self.assertEqual(read_record(approvals, prepared["approval_token"]).payload["is_sales_item"], 1)

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
		approvals.record_trusted_user_approval(
			prepared["approval_token"], action="create_item", site="test.localhost", user="sales@example.com"
		)
		result = item_service.confirm_item(prepared["approval_token"], True)
		self.assertEqual(result["status"], "created")
		self.assertFalse(result["idempotent"])
		self.assertEqual(self.commit_count, 1)
		self.assertEqual(self.docs[-1].insert_calls, [{"ignore_permissions": False, "ignore_links": False, "ignore_mandatory": False}])

	def test_wrong_or_expired_confirmation_is_rejected(self):
		wrong = item_service.confirm_item("not-issued", True)
		self.assertEqual(wrong["code"], "CONFIRMATION_EXPIRED")
		prepared = item_service.prepare_item(self.valid_item())
		mutate_record(approvals, self.approval_backend, prepared["approval_token"], lambda approval: setattr(approval, "created_at", approval.created_at - APPROVAL_TTL_SECONDS - 1), ttl_seconds=0)
		expired = item_service.confirm_item(prepared["approval_token"], True)
		self.assertEqual(expired["code"], "CONFIRMATION_EXPIRED")

	def test_confirmation_rechecks_duplicate_before_writing(self):
		prepared = item_service.prepare_item(self.valid_item())
		approvals.record_trusted_user_approval(
			prepared["approval_token"], action="create_item", site="test.localhost", user="sales@example.com"
		)
		self.list_rows = {"NEW-ITEM-001": [{"name": "NEW-ITEM-001", "item_code": "NEW-ITEM-001", "item_name": "Race", "stock_uom": "Nos", "disabled": 0}]}
		result = item_service.confirm_item(prepared["approval_token"], True)
		self.assertEqual(result["status"], "duplicate_suspected")
		self.assertEqual(self.commit_count, 0)

	def test_model_confirm_true_cannot_self_grant_approval(self):
		prepared = item_service.prepare_item(self.valid_item())
		result = item_service.confirm_item(prepared["approval_token"], True)
		self.assertEqual(result["code"], "TRUSTED_APPROVAL_UNAVAILABLE")
		self.assertEqual(self.commit_count, 0)

	def test_sales_order_item_resolution_contract_is_unchanged(self):
		with patch.object(sales_order, "resolve_sales_item", return_value={"status": "resolved", "candidate": {"value": "ITEM-001", "item_name": "Blue Polo"}, "match_type": "exact"}):
			result = sales_order._prepare_items([{"item": "ITEM-001", "qty": 2}])
		self.assertEqual(result, {"status": "resolved", "items": [{"item_code": "ITEM-001", "item_name": "Blue Polo", "qty": 2.0, "match_type": "exact"}]})

	def test_sales_order_does_not_continue_from_an_ambiguous_item(self):
		with patch.object(
			sales_order,
			"resolve_sales_item",
			return_value={"status": "ambiguous", "candidates": [{"value": "ITEM-1"}, {"value": "ITEM-2"}]},
		):
			result = sales_order._prepare_items([{"item": "Development Item", "qty": 2}])
		self.assertEqual(result["status"], "ambiguous")
		self.assertEqual(result["candidates"], [{"value": "ITEM-1"}, {"value": "ITEM-2"}])


if __name__ == "__main__":
	unittest.main()
