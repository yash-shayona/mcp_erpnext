from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.contracts.selling.quotation_read import (
	QuotationAggregateInput,
	QuotationGetInput,
	QuotationQueryInput,
)
from mcp_erpnext.services.selling import quotation_read as read


class FakeQuotation:
	def __init__(self, **values):
		self.values = values

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)

	def has_permission(self, permission):
		return permission == "read"


class QuotationReadServiceTests(unittest.TestCase):
	def setUp(self):
		self.document = FakeQuotation(
			name="SAL-QTN-0001",
			quotation_to="Customer",
			party_name="CUST-001",
			customer_name="Acme Ltd",
			transaction_date=date(2026, 9, 1),
			valid_till=date(2026, 9, 30),
			docstatus=1,
			status="Open",
			currency="INR",
			grand_total=1200.0,
		)
		self.rows = [
			{
				"name": "SAL-QTN-0001",
				"party_name": "CUST-001",
				"status": "Open",
				"currency": "INR",
				"grand_total": 1200.0,
			}
		]
		self.last_list = None
		self.fake_frappe = SimpleNamespace(
			get_doc=lambda _doctype, _name: self.document,
			get_list=self._get_list,
			DoesNotExistError=frappe.DoesNotExistError,
		)
		self.patch = patch.object(read, "frappe", self.fake_frappe)
		self.patch.start()

	def tearDown(self):
		self.patch.stop()

	def _get_list(self, doctype, **kwargs):
		self.last_list = (doctype, kwargs)
		fields = kwargs.get("fields") or []
		aliases = {
			field.get("as"): field
			for field in fields
			if isinstance(field, dict) and field.get("as")
		}
		if aliases:
			return [
				{
					"status": "Open",
					"party_name": "CUST-001",
					"currency": "INR",
					**{
						alias: {
							"count": 2,
							"sum_grand_total": 2400.0,
							"avg_grand_total": 1200.0,
							"min_grand_total": 800.0,
							"max_grand_total": 1600.0,
							"sum_net_total": 2000.0,
							"sum_total_qty": 4.0,
						}[alias]
						for alias in aliases
					},
				}
			]
		return self.rows

	def test_exact_read_uses_bounded_requested_projection_and_permission(self):
		result = read.get_quotation("SAL-QTN-0001", ["name", "status", "grand_total"])
		self.assertEqual(
			result,
			{
				"status": "ok",
				"document": {"name": "SAL-QTN-0001", "status": "Open", "grand_total": 1200.0},
			},
		)

		self.document.has_permission = lambda _permission: False
		self.assertEqual(read.get_quotation("SAL-QTN-0001", ["name"])["code"], "PERMISSION_DENIED")

	def test_exact_read_missing_document_is_not_found(self):
		self.fake_frappe.get_doc = lambda _doctype, _name: (_ for _ in ()).throw(frappe.DoesNotExistError)
		self.assertEqual(
			read.get_quotation("MISSING", ["name"]),
			{"status": "not_found", "quotation": "MISSING"},
		)

	def test_query_shares_typed_filters_and_is_permission_aware(self):
		criteria = QuotationQueryInput(
			party_name="CUST-001",
			status="Open",
			transaction_date_from=date(2026, 9, 1),
			transaction_date_to=date(2026, 9, 30),
			min_grand_total=100,
			max_grand_total=2000,
			fields=["name", "party_name", "grand_total"],
			limit=5,
			offset=2,
			sort_by="grand_total",
			sort_order="asc",
		).model_dump()
		result = read.query_quotations(criteria)
		self.assertEqual(result["quotations"], [{"name": "SAL-QTN-0001", "party_name": "CUST-001", "grand_total": 1200.0}])
		self.assertEqual(self.last_list[0], "Quotation")
		self.assertFalse(self.last_list[1]["ignore_permissions"])
		self.assertEqual(self.last_list[1]["order_by"], "grand_total asc, name asc")
		self.assertEqual(self.last_list[1]["limit_start"], 2)
		self.assertIn(["party_name", "=", "CUST-001"], self.last_list[1]["filters"])
		self.assertIn(["transaction_date", "between", ["2026-09-01", "2026-09-30"]], self.last_list[1]["filters"])
		self.assertIn(["grand_total", ">=", 100.0], self.last_list[1]["filters"])

	def test_aggregate_count_and_grouping_use_shared_frappe_fields(self):
		result = read.aggregate_quotations(
			QuotationAggregateInput(status="Open", metrics=["count"], group_by="status").model_dump()
		)
		self.assertEqual(result["results"], [{"count": 2, "group_value": "Open"}])
		self.assertFalse(self.last_list[1]["ignore_permissions"])
		self.assertEqual(self.last_list[1]["fields"], ["status", {"COUNT": "*", "as": "count"}])
		self.assertEqual(self.last_list[1]["group_by"], "status")

	def test_monetary_aggregate_includes_currency_context(self):
		result = read.aggregate_quotations(
			QuotationAggregateInput(
				party_name="CUST-001", metrics=["sum_grand_total"], group_by="party_name"
			).model_dump()
		)
		self.assertEqual(
			result["results"],
			[{"sum_grand_total": 2400.0, "group_value": "CUST-001", "currency": "INR"}],
		)
		self.assertEqual(self.last_list[1]["group_by"], "currency, party_name")
		self.assertIn("currency", self.last_list[1]["fields"])
		self.assertIn({"SUM": "grand_total", "as": "sum_grand_total"}, self.last_list[1]["fields"])

	def test_all_approved_aggregate_metrics_are_supported(self):
		metrics = [
			"count",
			"sum_grand_total",
			"avg_grand_total",
			"min_grand_total",
			"max_grand_total",
			"sum_net_total",
			"sum_total_qty",
		]
		result = read.aggregate_quotations(
			QuotationAggregateInput(metrics=metrics, currency="INR").model_dump()
		)
		self.assertEqual(result["results"][0]["count"], 2)
		self.assertEqual(result["results"][0]["avg_grand_total"], 1200.0)
		self.assertEqual(result["results"][0]["sum_total_qty"], 4.0)
		self.assertEqual(
			{field["as"] for field in self.last_list[1]["fields"] if isinstance(field, dict)},
			set(metrics),
		)


class QuotationReadContractTests(unittest.TestCase):
	def test_default_projections_are_bounded(self):
		self.assertEqual(
			QuotationGetInput(quotation="QTN-1").fields,
			[
				"name",
				"quotation_to",
				"party_name",
				"customer_name",
				"transaction_date",
				"valid_till",
				"docstatus",
				"status",
				"currency",
				"grand_total",
			],
		)
		self.assertEqual(
			QuotationQueryInput().fields,
			[
				"name",
				"party_name",
				"customer_name",
				"transaction_date",
				"valid_till",
				"status",
				"currency",
				"grand_total",
			],
		)

	def test_contracts_reject_unsupported_projection_and_invalid_ranges(self):
		with self.assertRaises(ValidationError):
			QuotationGetInput(quotation="QTN-1", fields=["terms"])
		with self.assertRaises(ValidationError):
			QuotationQueryInput(fields=["terms"])
		with self.assertRaises(ValidationError):
			QuotationQueryInput(sort_by="grand_total desc")
		with self.assertRaises(ValidationError):
			QuotationQueryInput(transaction_date_from="2026-09-30", transaction_date_to="2026-09-01")
		with self.assertRaises(ValidationError):
			QuotationAggregateInput(metrics=["count"], group_by="terms")
		with self.assertRaises(ValidationError):
			QuotationAggregateInput(metrics=["median_grand_total"])


if __name__ == "__main__":
	unittest.main()
