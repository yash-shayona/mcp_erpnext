from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from mcp_erpnext.approvals import ApprovalStore
from mcp_erpnext.services.common import lifecycle
from mcp_erpnext.settings import ApprovalMode
from mcp_erpnext.tests.approval_test_backend import FakeSharedApprovalBackend


class FakeDocStatus(int):
	def is_draft(self):
		return self == 0

	def is_submitted(self):
		return self == 1

	def is_cancelled(self):
		return self == 2


class FakeField:
	def __init__(self, fieldname, fieldtype="Data", *, read_only=False, options=None):
		self.fieldname = fieldname
		self.fieldtype = fieldtype
		self.read_only = read_only
		self.options = options


class FakeMeta:
	def __init__(self, *fields, is_submittable=False):
		self._fields = {field.fieldname: field for field in fields}
		self.is_submittable = is_submittable
		self.fields = list(self._fields.values())

	def get_field(self, fieldname):
		return self._fields.get(fieldname)

	def has_field(self, fieldname):
		return fieldname in self._fields


class FakeDocument:
	def __init__(self, doctype="Sales Order", name="SO-001", *, docstatus=0, modified="one"):
		self.doctype = doctype
		self.name = name
		self.docstatus = FakeDocStatus(docstatus)
		self.modified = modified
		self.remarks = ""
		self.meta = FakeMeta(FakeField("remarks"), is_submittable=doctype in {"Sales Order", "Quotation", "Purchase Order", "Sales Invoice"})

	def has_permission(self, permission):
		return permission in {"read", "write", "submit", "cancel", "delete"}

	def check_permission(self, permission):
		if not self.has_permission(permission):
			raise PermissionError(permission)

	def get(self, fieldname):
		return getattr(self, fieldname, None)

	def set(self, fieldname, value):
		setattr(self, fieldname, value)


class FakeChildRow:
	def __init__(self, values, name="new-row"):
		self.name = name
		self.idx = values.get("idx", 1)
		self.values = values

	def get(self, fieldname):
		return self.values.get(fieldname)


class FakeChildDocument(FakeDocument):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.items = [FakeChildRow({"item_code": "OLD-ITEM", "qty": 1}, "row-1")]
		self.saved = False
		self.meta = FakeMeta(
			FakeField("remarks"), FakeField("items", "Table", options=f"{self.doctype} Item"),
			is_submittable=True,
		)

	def append(self, table, values):
		values = {**values, "delivery_date": values.get("delivery_date", date(2026, 9, 10))}
		row = FakeChildRow(values, f"row-{len(self.items) + 1}")
		self.items.append(row)
		return row

	def save(self, **kwargs):
		self.saved = True


class LifecycleServiceTests(unittest.TestCase):
	def setUp(self):
		self.doc = FakeDocument()
		self.approval_backend = FakeSharedApprovalBackend()
		self.store = ApprovalStore(ApprovalMode.AGENT_DELEGATED, backend=self.approval_backend)
		self.frappe_patches = [
			patch.object(lifecycle.frappe, "get_doc", return_value=self.doc),
			patch.object(lifecycle.frappe, "get_meta", return_value=FakeMeta(FakeField("item_code"), FakeField("qty"))),
			patch.object(lifecycle.frappe, "db", SimpleNamespace(commit=lambda: None, rollback=lambda: None)),
			patch.object(lifecycle.frappe, "get_list", return_value=[{"name": "CUST-001"}]),
			patch.object(lifecycle.frappe, "local", SimpleNamespace(site="test.localhost", db=SimpleNamespace(commit=lambda: None, rollback=lambda: None))),
			patch.object(lifecycle.frappe, "session", SimpleNamespace(user="user@example.com")),
			patch.object(lifecycle, "approvals", self.store),
		]
		for item in self.frappe_patches:
			item.start()

	def tearDown(self):
		for item in reversed(self.frappe_patches):
			item.stop()

	def test_prepare_update_is_exact_and_does_not_mutate(self):
		result = lifecycle.prepare_update(
			{"doctype": "Sales Order", "name": "SO-001"},
			[{"field": "remarks", "value": "Urgent delivery"}],
			"sales",
		)
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["changes"][0]["old"], "")
		self.assertEqual(result["preview"]["changes"][0]["new"], "Urgent delivery")
		self.assertEqual(self.doc.remarks, "")

	def test_arbitrary_doctype_is_rejected_by_profile_allowlist(self):
		result = lifecycle.prepare_update(
			{"doctype": "Sales Invoice", "name": "SINV-001"},
			[{"field": "remarks", "value": "x"}],
			"sales",
		)
		self.assertEqual(result["code"], "DOCTYPE_NOT_ALLOWED")

	def test_sales_invoice_policy_allows_only_submit_cancel_delete(self):
		for action in ("submit", "cancel", "delete"):
			with self.subTest(action=action):
				self.assertTrue(lifecycle.is_action_allowed("sales", "Sales Invoice", action))
		for action in ("update", "child_add"):
			with self.subTest(action=action):
				self.assertFalse(lifecycle.is_action_allowed("sales", "Sales Invoice", action))

	def test_sales_invoice_submit_reaches_existing_prepare_flow(self):
		result = lifecycle.prepare_submit({"doctype": "Sales Invoice", "name": "SINV-001"}, "sales")
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["action"], "SUBMIT")

	def test_sales_invoice_update_and_child_add_are_denied_before_approval(self):
		update = lifecycle.prepare_update(
			{"doctype": "Sales Invoice", "name": "SINV-001"},
			[{"field": "remarks", "value": "x"}],
			"sales",
		)
		child_add = lifecycle.prepare_child_add(
			{"doctype": "Sales Invoice", "name": "SINV-001"},
			{"doctype": "Item", "name": "ITEM-001"},
			1,
			None,
			"sales",
		)
		self.assertEqual(update["code"], "DOCTYPE_NOT_ALLOWED")
		self.assertEqual(child_add["code"], "DOCTYPE_NOT_ALLOWED")
		self.assertTrue(self.approval_backend.is_empty())

	def test_lifecycle_approval_cannot_be_reused_for_another_action(self):
		prepared = lifecycle.prepare_submit(
			{"doctype": "Sales Invoice", "name": "SINV-001"}, "sales"
		)
		result = lifecycle.confirm("update", prepared["approval_token"], True, "sales")
		self.assertEqual(result["code"], "CONFIRMATION_UNAVAILABLE")

	def test_system_field_is_not_writable(self):
		result = lifecycle.prepare_update(
			{"doctype": "Sales Order", "name": "SO-001"},
			[{"field": "docstatus", "value": 1}],
			"sales",
		)
		self.assertEqual(result["code"], "FIELD_NOT_WRITABLE")

	def test_customer_cannot_be_submitted(self):
		self.doc = FakeDocument("Customer", "CUST-001")
		lifecycle.frappe.get_doc.return_value = self.doc
		result = lifecycle.prepare_submit({"doctype": "Customer", "name": "CUST-001"}, "sales")
		self.assertEqual(result["code"], "NOT_SUBMITTABLE")

	def test_confirmation_rejects_stale_document(self):
		prepared = lifecycle.prepare_update(
			{"doctype": "Sales Order", "name": "SO-001"},
			[{"field": "remarks", "value": "Urgent delivery"}],
			"sales",
		)
		self.doc.modified = "two"
		result = lifecycle.confirm("update", prepared["approval_token"], True, "sales")
		self.assertEqual(result["code"], "STALE_CONFIRMATION")
		self.assertEqual(self.doc.remarks, "")

	def test_prepare_child_add_is_preview_only_and_binds_profile(self):
		self.doc = FakeChildDocument()
		lifecycle.frappe.get_doc.return_value = self.doc
		lifecycle.frappe.get_list.return_value = [{"name": "NEW-ITEM", "item_code": "NEW-ITEM", "item_name": "New", "stock_uom": "Nos"}]
		lifecycle.frappe.get_meta.return_value = FakeMeta(
			FakeField("item_code"), FakeField("qty"), FakeField("rate"),
		)
		result = lifecycle.prepare_child_add(
			{"doctype": "Sales Order", "name": "SO-001"},
			{"doctype": "Item", "name": "NEW-ITEM"}, 2, None, "sales",
		)
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["action"], "ADD_ITEM")
		self.assertEqual(result["preview"]["new_row"]["item_code"], "NEW-ITEM")
		self.assertEqual(len(self.doc.items), 2)
		self.assertFalse(self.doc.saved)
		approval, state = lifecycle.approvals.lookup(result["approval_token"], action="lifecycle_child_add", site="test.localhost", user="user@example.com")
		self.assertEqual(state, "available")
		self.assertEqual(approval.payload["profile"], "sales")

	def test_confirm_child_add_uses_native_save_and_preserves_old_row(self):
		self.doc = FakeChildDocument()
		confirm_doc = FakeChildDocument()
		lifecycle.frappe.get_doc.side_effect = [self.doc, confirm_doc]
		lifecycle.frappe.get_list.return_value = [{"name": "NEW-ITEM", "item_code": "NEW-ITEM", "item_name": "New", "stock_uom": "Nos"}]
		lifecycle.frappe.get_meta.return_value = FakeMeta(FakeField("item_code"), FakeField("qty"))
		prepared = lifecycle.prepare_child_add(
			{"doctype": "Sales Order", "name": "SO-001"},
			{"doctype": "Item", "name": "NEW-ITEM"}, 2, None, "sales",
		)
		result = lifecycle.confirm("child_add", prepared["approval_token"], True, "sales")
		self.assertEqual(result["status"], "added", result)
		self.assertTrue(confirm_doc.saved)
		self.assertEqual([row.get("item_code") for row in confirm_doc.items], ["OLD-ITEM", "NEW-ITEM"])

	def test_child_add_rejects_duplicate_and_non_draft(self):
		self.doc = FakeChildDocument()
		self.doc.items.append(FakeChildRow({"item_code": "NEW-ITEM", "qty": 1}, "row-2"))
		lifecycle.frappe.get_doc.return_value = self.doc
		lifecycle.frappe.get_list.return_value = [{"name": "NEW-ITEM", "item_code": "NEW-ITEM", "item_name": "New", "stock_uom": "Nos"}]
		lifecycle.frappe.get_meta.return_value = FakeMeta(FakeField("item_code"), FakeField("qty"))
		duplicate = lifecycle.prepare_child_add({"doctype": "Sales Order", "name": "SO-001"}, {"doctype": "Item", "name": "NEW-ITEM"}, 2, None, "sales")
		self.assertEqual(duplicate["code"], "DUPLICATE_ITEM_ROW")
		self.doc.docstatus = FakeDocStatus(1)
		submitted = lifecycle.prepare_child_add({"doctype": "Sales Order", "name": "SO-001"}, {"doctype": "Item", "name": "OTHER-ITEM"}, 2, None, "sales")
		self.assertEqual(submitted["code"], "INVALID_DOCUMENT_STATE")

	def test_confirm_child_add_restores_date_fields_before_append(self):
		self.doc = FakeChildDocument()
		confirm_doc = FakeChildDocument()
		lifecycle.frappe.get_doc.side_effect = [self.doc, confirm_doc]
		lifecycle.frappe.get_list.return_value = [{"name": "NEW-ITEM", "item_code": "NEW-ITEM"}]
		lifecycle.frappe.get_meta.return_value = FakeMeta(
			FakeField("item_code"), FakeField("qty"), FakeField("delivery_date", "Date")
		)
		prepared = lifecycle.prepare_child_add(
			{"doctype": "Sales Order", "name": "SO-001"},
			{"doctype": "Item", "name": "NEW-ITEM"}, 2, None, "sales",
		)
		approval, state = lifecycle.approvals.lookup(
			prepared["approval_token"],
			action="lifecycle_child_add",
			site="test.localhost",
			user="user@example.com",
		)
		self.assertEqual(state, "available")
		self.assertEqual(approval.payload["row"]["delivery_date"], "2026-09-10")
		result = lifecycle.confirm("child_add", prepared["approval_token"], True, "sales")
		self.assertEqual(result["status"], "added")
		self.assertIsInstance(confirm_doc.items[-1].get("delivery_date"), date)


if __name__ == "__main__":
	unittest.main()
