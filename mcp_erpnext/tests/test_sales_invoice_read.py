from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.contracts.selling.sales_invoice_read import (
	SalesInvoiceAggregateInput,
	SalesInvoiceGetInput,
	SalesInvoiceQueryInput,
)
from mcp_erpnext.services.selling import sales_invoice_read as read


class FakeSalesInvoice:
	def __init__(self, **values):
		self.values = values

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)

	def has_permission(self, permission):
		return permission == "read"


class SalesInvoiceReadServiceTests(unittest.TestCase):
	def setUp(self):
		self.document = FakeSalesInvoice(
			name="ACC-SINV-0001",
			customer="CUST-001",
			customer_name="Acme Ltd",
			posting_date=date(2026, 9, 1),
			due_date=date(2026, 9, 30),
			docstatus=1,
			status="Unpaid",
			company="Acme India",
			currency="INR",
			grand_total=1200.0,
			outstanding_amount=1200.0,
			is_return=0,
			return_against=None,
		)
		self.rows = [
			{
				"name": "ACC-SINV-0001",
				"customer": "CUST-001",
				"posting_date": date(2026, 9, 1),
				"status": "Unpaid",
				"currency": "INR",
				"grand_total": 1200.0,
				"outstanding_amount": 1200.0,
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
					"customer": "CUST-001",
					"status": "Unpaid",
					"currency": "INR",
					"count": 2,
					"sum_grand_total": 2400.0,
					"avg_grand_total": 1200.0,
					"min_grand_total": 800.0,
					"max_grand_total": 1600.0,
					"sum_outstanding_amount": 1800.0,
					"sum_net_total": 2000.0,
					"sum_total_qty": 4.0,
				}
			]
		return self.rows

	def test_exact_read_uses_requested_projection_and_permission(self):
		result = read.get_sales_invoice(
			"ACC-SINV-0001", ["name", "status", "outstanding_amount"]
		)
		self.assertEqual(
			result,
			{
				"status": "ok",
				"document": {
					"name": "ACC-SINV-0001",
					"status": "Unpaid",
					"outstanding_amount": 1200.0,
				},
			},
		)
		self.document.has_permission = lambda _permission: False
		self.assertEqual(
			read.get_sales_invoice("ACC-SINV-0001", ["name"])["code"],
			"PERMISSION_DENIED",
		)

	def test_exact_read_missing_document_is_not_found(self):
		self.fake_frappe.get_doc = lambda _doctype, _name: (_ for _ in ()).throw(
			frappe.DoesNotExistError
		)
		self.assertEqual(
			read.get_sales_invoice("MISSING", ["name"]),
			{"status": "not_found", "sales_invoice": "MISSING"},
		)

	def test_query_uses_shared_filters_projection_sort_and_permissions(self):
		criteria = SalesInvoiceQueryInput(
			customer="CUST-001",
			status="Unpaid",
			is_return=False,
			posting_date_from=date(2026, 9, 1),
			posting_date_to=date(2026, 9, 30),
			due_date_to=date(2026, 10, 1),
			min_outstanding_amount=0,
			fields=["name", "customer", "outstanding_amount"],
			limit=5,
			offset=2,
			sort_by="outstanding_amount",
			sort_order="asc",
		).model_dump()
		result = read.query_sales_invoices(criteria)
		self.assertEqual(
			result["sales_invoices"],
			[{"name": "ACC-SINV-0001", "customer": "CUST-001", "outstanding_amount": 1200.0}],
		)
		self.assertEqual(self.last_list[0], "Sales Invoice")
		self.assertFalse(self.last_list[1]["ignore_permissions"])
		self.assertEqual(self.last_list[1]["order_by"], "outstanding_amount asc, name asc")
		self.assertEqual(self.last_list[1]["limit_start"], 2)
		self.assertIn(["is_return", "=", 0], self.last_list[1]["filters"])
		self.assertIn(
			["posting_date", "between", ["2026-09-01", "2026-09-30"]],
			self.last_list[1]["filters"],
		)

	def test_aggregate_metrics_grouping_and_currency_context_use_shared_helper(self):
		metrics = [
			"count",
			"sum_grand_total",
			"avg_grand_total",
			"min_grand_total",
			"max_grand_total",
			"sum_outstanding_amount",
			"sum_net_total",
			"sum_total_qty",
		]
		result = read.aggregate_sales_invoices(
			SalesInvoiceAggregateInput(
				customer="CUST-001", metrics=metrics, group_by="status"
			).model_dump()
		)
		self.assertEqual(result["results"][0]["sum_outstanding_amount"], 1800.0)
		self.assertEqual(result["results"][0]["group_value"], "Unpaid")
		self.assertEqual(result["results"][0]["currency"], "INR")
		self.assertEqual(self.last_list[1]["group_by"], "currency, status")
		self.assertIn("currency", self.last_list[1]["fields"])
		self.assertFalse(self.last_list[1]["ignore_permissions"])

	def test_return_amounts_are_filtered_without_sign_rewriting(self):
		criteria = SalesInvoiceAggregateInput(
			is_return=True, metrics=["sum_grand_total"], min_grand_total=-500
		).model_dump()
		read.aggregate_sales_invoices(criteria)
		self.assertIn(["is_return", "=", 1], self.last_list[1]["filters"])
		self.assertIn(["grand_total", ">=", -500.0], self.last_list[1]["filters"])


class SalesInvoiceReadContractTests(unittest.TestCase):
	def test_default_projections_are_bounded(self):
		self.assertEqual(
			SalesInvoiceGetInput(sales_invoice="SINV-1").fields,
			[
				"name",
				"customer",
				"customer_name",
				"posting_date",
				"due_date",
				"docstatus",
				"status",
				"currency",
				"grand_total",
				"outstanding_amount",
				"is_return",
				"return_against",
			],
		)
		self.assertEqual(
			SalesInvoiceQueryInput().fields,
			[
				"name",
				"customer",
				"customer_name",
				"posting_date",
				"due_date",
				"status",
				"currency",
				"grand_total",
				"outstanding_amount",
			],
		)

	def test_contract_rejects_unsupported_values_and_bad_ranges(self):
		with self.assertRaises(ValidationError):
			SalesInvoiceGetInput(sales_invoice="SINV-1", fields=["items"])
		with self.assertRaises(ValidationError):
			SalesInvoiceQueryInput(status="Not a Sales Invoice status")
		with self.assertRaises(ValidationError):
			SalesInvoiceQueryInput(
				posting_date_from="2026-09-30", posting_date_to="2026-09-01"
			)
		with self.assertRaises(ValidationError):
			SalesInvoiceAggregateInput(metrics=["sum_paid_amount"])
		with self.assertRaises(ValidationError):
			SalesInvoiceAggregateInput(metrics=["count"], group_by="items")


if __name__ == "__main__":
	unittest.main()
