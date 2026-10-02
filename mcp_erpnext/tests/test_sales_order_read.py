from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.contracts.selling.sales_order_read import (
	SalesOrderAggregateInput,
	SalesOrderItemQueryInput,
	SalesOrderQueryInput,
)
from mcp_erpnext.services.selling import sales_order_read as read


class FakeQuery:
	def __init__(self, rows):
		self.rows = rows

	def run(self, *, as_dict):
		return self.rows


class FakeDistinctCount:
	def distinct(self):
		return self

	def as_(self, alias):
		self.alias = alias
		return self


class FakeSalesOrder:
	def __init__(self):
		self.values = {
			"name": "SO-0001", "status": "To Deliver", "customer": "CUST-001", "currency": "INR",
			"grand_total": 200.0, "items": [{"item_code": "ITEM-001", "qty": 2, "rate": 100.0, "amount": 200.0, "internal_note": "hidden"}],
		}

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)

	has_permission = lambda self, permission: permission == "read"


class SalesOrderReadServiceTests(unittest.TestCase):
	def setUp(self):
		self.document = FakeSalesOrder()
		self.list_rows = [{"name": "SO-0001", "status": "To Deliver", "currency": "INR", "grand_total": 200.0}]
		self.item_rows = [{"sales_order": "SO-0001", "transaction_date": date(2026, 9, 8), "customer": "CUST-001", "item_code": "ITEM-001", "rate": 100.0}]
		self.last_list = None
		self.last_query = None
		self.fake_frappe = SimpleNamespace(
			get_doc=lambda _doctype, _name: self.document,
			get_list=self._get_list,
			qb=SimpleNamespace(get_query=self._get_query),
			DoesNotExistError=frappe.DoesNotExistError,
		)
		self.patch = patch.object(read, "frappe", self.fake_frappe)
		self.patch.start()

	def tearDown(self):
		self.patch.stop()

	def _get_list(self, doctype, **kwargs):
		self.last_list = (doctype, kwargs)
		fields = kwargs.get("fields") or []
		if any(isinstance(field, dict) and field.get("as") == "avg_rate" for field in fields):
			return [{"currency": "INR", "avg_rate": 100.0}]
		if any(isinstance(field, dict) and field.get("as") == "count" for field in fields):
			return [{"currency": "INR", "customer": "CUST-001", "count": 2, "sum_grand_total": 300.0}]
		return self.list_rows

	def _get_query(self, doctype, **kwargs):
		self.last_query = (doctype, kwargs)
		return FakeQuery(self.item_rows)

	def test_exact_read_projects_only_requested_header_and_item_fields(self):
		result = read.get_sales_order("SO-0001", ["status"], True, ["item_code", "rate"])
		self.assertEqual(result, {"status": "ok", "document": {"status": "To Deliver"}, "items": [{"item_code": "ITEM-001", "rate": 100.0}]})

	def test_exact_read_checks_document_permission(self):
		self.document.has_permission = lambda _permission: False
		result = read.get_sales_order("SO-0001", ["status"], False, ["item_code"])
		self.assertEqual(result["code"], "PERMISSION_DENIED")

	def test_query_uses_typed_child_filters_and_frappe_permissions(self):
		criteria = SalesOrderQueryInput(customer="CUST-001", item_code="ITEM-001", sales_person="Sales A", delivery_status="Not Delivered", fields=["name", "status"]).model_dump()
		result = read.query_sales_orders(criteria)
		self.assertEqual(result["sales_orders"], [{"name": "SO-0001", "status": "To Deliver"}])
		self.assertFalse(self.last_list[1]["ignore_permissions"])
		self.assertTrue(self.last_list[1]["distinct"])
		self.assertIn(["Sales Order Item", "item_code", "=", "ITEM-001"], self.last_list[1]["filters"])
		self.assertIn(["Sales Team", "sales_person", "=", "Sales A"], self.last_list[1]["filters"])

	def test_header_aggregate_groups_monetary_metrics_by_currency(self):
		criteria = SalesOrderAggregateInput(customer="CUST-001", metrics=["count", "sum_grand_total"], group_by="customer").model_dump()
		result = read.aggregate_sales_orders(criteria)
		self.assertEqual(result["results"], [{"count": 2, "sum_grand_total": 300.0, "group_value": "CUST-001", "currency": "INR"}])
		self.assertFalse(self.last_list[1]["ignore_permissions"])
		self.assertIn({"COUNT": "*", "as": "count"}, self.last_list[1]["fields"])
		self.assertIn({"SUM": "grand_total", "as": "sum_grand_total"}, self.last_list[1]["fields"])
		self.assertEqual(self.last_list[1]["group_by"], "currency, customer")

	def test_item_history_uses_permission_aware_parent_query_and_optional_metrics(self):
		criteria = SalesOrderItemQueryInput(customer="CUST-001", item_code="ITEM-001", fields=["sales_order", "rate"], metrics=["avg_rate"]).model_dump()
		result = read.query_sales_order_items(criteria)
		self.assertEqual(result["items"], [{"sales_order": "SO-0001", "rate": 100.0}])
		self.assertEqual(self.last_query[0], "Sales Order")
		self.assertFalse(self.last_query[1]["ignore_permissions"])
		self.assertIn(["Sales Order Item", "item_code", "=", "ITEM-001"], self.last_query[1]["filters"])
		self.assertEqual(result["aggregates"], [{"currency": "INR", "avg_rate": 100.0}])

	def test_item_aggregate_keeps_typed_distinct_order_expression(self):
		expression = FakeDistinctCount()
		self.fake_frappe.qb.DocType = lambda _doctype: SimpleNamespace(name="Sales Order.name")
		self.list_rows = [{"count_distinct_orders": 2}]
		with patch.object(read, "Count", return_value=expression):
			result = read._aggregate_sales_order_items(
				SalesOrderItemQueryInput(metrics=["count_distinct_orders"]).model_dump()
			)
		self.assertEqual(result, [{"count_distinct_orders": 2}])
		self.assertIs(self.last_list[1]["fields"][0], expression)
		self.assertFalse(self.last_list[1]["ignore_permissions"])


class SalesOrderReadContractTests(unittest.TestCase):
	def test_safe_contract_rejects_invalid_query_controls(self):
		for payload in (
			{"fields": ["owner; drop table"]},
			{"sort_by": "grand_total desc; delete"},
			{"limit": 101},
			{"transaction_date_from": "2026-09-09", "transaction_date_to": "2026-09-08"},
		):
			with self.subTest(payload=payload):
				with self.assertRaises(ValidationError):
					SalesOrderQueryInput.model_validate(payload)

	def test_item_metric_only_request_suppresses_source_rows(self):
		request = SalesOrderItemQueryInput(metrics=["sum_qty"])
		self.assertIsNone(request.fields)


if __name__ == "__main__":
	unittest.main()
