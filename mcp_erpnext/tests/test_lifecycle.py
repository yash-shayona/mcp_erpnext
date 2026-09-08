from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mcp_erpnext.approvals import ApprovalStore
from mcp_erpnext.services.common import lifecycle
from mcp_erpnext.settings import ApprovalMode


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
		self.meta = FakeMeta(FakeField("remarks"), is_submittable=doctype in {"Sales Order", "Quotation", "Purchase Order"})

	def has_permission(self, permission):
		return permission in {"read", "write", "submit", "cancel", "delete"}

	def get(self, fieldname):
		return getattr(self, fieldname, None)

	def set(self, fieldname, value):
		setattr(self, fieldname, value)


class LifecycleServiceTests(unittest.TestCase):
	def setUp(self):
		self.doc = FakeDocument()
		self.store = ApprovalStore(ApprovalMode.AGENT_DELEGATED)
		self.frappe_patches = [
			patch.object(lifecycle.frappe, "get_doc", return_value=self.doc),
			patch.object(lifecycle.frappe, "get_list", return_value=[{"name": "CUST-001"}]),
			patch.object(lifecycle.frappe, "local", SimpleNamespace(site="test.localhost")),
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


if __name__ == "__main__":
	unittest.main()
