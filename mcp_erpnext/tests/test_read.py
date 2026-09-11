from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.services.common import read


class FakeRow:
	def __init__(self, **values):
		self.values = values
		self.name = values.get("name")
		self.docstatus = values.get("docstatus", 0)

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)


class ReadServiceTests(unittest.TestCase):
	def setUp(self):
		self.rows = [
			{"name": "SO-002", "customer": "CUST-001", "transaction_date": date(2026, 9, 2), "delivery_date": date(2026, 9, 9), "docstatus": 1, "status": "To Deliver", "currency": "INR", "grand_total": 200.0},
			{"name": "SO-001", "customer": "CUST-001", "transaction_date": date(2026, 9, 1), "docstatus": 0, "status": "Draft", "currency": "INR", "grand_total": 100.0},
		]
		self.doc = FakeRow(**{**self.rows[0], "items": [{"item_code": "ITEM-1", "item_name": "Widget", "qty": 2, "rate": 100, "amount": 200, "internal": "hidden"}]})
		self.fake_frappe = SimpleNamespace(
			get_doc=lambda _doctype, _name: self.doc,
			get_list=self._get_list,
			DoesNotExistError=frappe.DoesNotExistError,
		)
		self.patch = patch.object(read, "frappe", self.fake_frappe)
		self.patch.start()

	def tearDown(self):
		self.patch.stop()

	def _get_list(self, doctype, **kwargs):
		self.last_query = (doctype, kwargs)
		return self.rows

	def test_sales_order_search_is_bounded_and_permission_aware(self):
		result = read.search_documents("Sales Order", {"party": "CUST-001", "limit": 200}, "sales")
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["limit"], 50)
		self.assertEqual(self.last_query[1]["limit_page_length"], 50)
		self.assertFalse(self.last_query[1]["ignore_permissions"])
		self.assertEqual(self.last_query[1]["filters"], {"customer": "CUST-001"})

	def test_exact_get_returns_status_and_compact_items(self):
		self.doc.has_permission = lambda permission: permission == "read"
		result = read.get_document({"doctype": "Sales Order", "name": "SO-002"}, "sales")
		document = result["document"]
		self.assertEqual((document["docstatus"], document["status"]), (1, "To Deliver"))
		self.assertEqual(document["items"], [{"item_code": "ITEM-1", "item_name": "Widget", "qty": 2, "rate": 100, "amount": 200}])

	def test_exact_get_fails_closed_for_profile_boundary(self):
		result = read.get_document({"doctype": "Purchase Order", "name": "PO-001"}, "sales")
		self.assertEqual(result["code"], "DOCTYPE_NOT_ALLOWED")

	def test_exact_get_does_not_expose_document_without_read_permission(self):
		self.doc.has_permission = lambda _permission: False
		result = read.get_document({"doctype": "Sales Order", "name": "SO-002"}, "sales")
		self.assertEqual(result["code"], "PERMISSION_DENIED")
		self.assertNotIn("status", result.get("document", {}))

	def test_empty_search_is_a_successful_empty_read(self):
		self.rows = []
		result = read.search_documents("Sales Order", {"party": "CUST-NONE", "limit": 20}, "sales")
		self.assertEqual(result, {"status": "ok", "doctype": "Sales Order", "results": [], "count": 0, "limit": 20})

	def test_sales_invoice_get_uses_customer_posting_and_due_dates(self):
		self.doc = FakeRow(
			name="SINV-001",
			customer="CUST-001",
			posting_date=date(2026, 9, 3),
			due_date=date(2026, 10, 3),
			docstatus=1,
			status="Paid",
			currency="INR",
			grand_total=300.0,
			items=[{"item_code": "ITEM-1", "qty": 3, "amount": 300, "secret": "hidden"}],
		)
		self.doc.has_permission = lambda permission: permission == "read"
		result = read.get_document({"doctype": "Sales Invoice", "name": "SINV-001"}, "sales")

		self.assertEqual(result["status"], "ok")
		document = result["document"]
		self.assertEqual(document["party"], "CUST-001")
		self.assertEqual(document["transaction_date"], date(2026, 9, 3))
		self.assertEqual(document["secondary_date"], date(2026, 10, 3))
		self.assertEqual(document["items"], [{"item_code": "ITEM-1", "qty": 3, "amount": 300}])

	def test_sales_invoice_search_uses_posting_date_and_customer(self):
		self.rows = []
		result = read.search_documents(
			"Sales Invoice",
			{
				"party": "CUST-001",
				"docstatus": 1,
				"status": "Paid",
				"date_from": date(2026, 9, 1),
				"date_to": date(2026, 9, 30),
			},
			"sales",
		)

		self.assertEqual(result["status"], "ok")
		self.assertEqual(self.last_query[1]["filters"], {
			"customer": "CUST-001",
			"docstatus": 1,
			"status": "Paid",
			"posting_date": ["between", ["2026-09-01", "2026-09-30"]],
		})
		self.assertEqual(self.last_query[1]["order_by"], "posting_date desc, name desc")

	def test_sales_invoice_is_not_available_to_purchase_profile(self):
		result = read.search_documents("Sales Invoice", {}, "purchase")
		self.assertEqual(result["code"], "DOCTYPE_NOT_ALLOWED")


if __name__ == "__main__":
	unittest.main()
