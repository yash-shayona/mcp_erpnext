from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.contracts.accounts.payment_entry_read import (
	PaymentEntryAggregateInput,
	PaymentEntryGetInput,
	PaymentEntryQueryInput,
)
from mcp_erpnext.services.accounts import payment_entry_read as read


class FakePaymentEntry:
	def __init__(self, **values):
		self.values = values

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)

	def has_permission(self, permission):
		return permission == "read"


class PaymentEntryReadServiceTests(unittest.TestCase):
	def setUp(self):
		self.document = FakePaymentEntry(
			name="ACC-PAY-2026-00012",
			docstatus=1,
			status="Submitted",
			payment_type="Receive",
			company="Acme India",
			posting_date=date(2026, 9, 1),
			party_type="Customer",
			party="CUST-001",
			party_name="Arkee Foods",
			mode_of_payment="Bank Transfer",
			paid_from="Debtors - AI",
			paid_from_account_currency="INR",
			paid_to="Bank - AI",
			paid_to_account_currency="INR",
			paid_amount=1200.0,
			received_amount=1200.0,
			total_allocated_amount=1200.0,
			unallocated_amount=0.0,
			difference_amount=0.0,
			reference_no="UTR-1",
			reference_date=date(2026, 9, 1),
			remarks="Invoice receipt",
			bank_account_no="MUST NOT BE PUBLIC",
			references=[
				{
					"reference_doctype": "Sales Invoice",
					"reference_name": "ACC-SINV-2026-00009",
					"bill_no": "INV-9",
					"due_date": date(2026, 9, 30),
					"payment_term": "Net 30",
					"total_amount": 1200.0,
					"outstanding_amount": 1200.0,
					"allocated_amount": 1200.0,
					"exchange_rate": 1.0,
					"account": "Debtors - AI",
				},
			],
		)
		self.rows = [
			{
				"name": "ACC-PAY-2026-00012",
				"docstatus": 1,
				"status": "Submitted",
				"payment_type": "Receive",
				"party": "CUST-001",
				"paid_amount": 1200.0,
				"received_amount": 1200.0,
				"paid_from_account_currency": "INR",
				"paid_to_account_currency": "INR",
			}
		]
		self.calls = []
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
		self.calls.append((doctype, kwargs))
		if doctype == "Payment Entry Reference":
			return [{"parent": "ACC-PAY-2026-00012"}]
		if any(isinstance(field, dict) for field in kwargs.get("fields", [])):
			return [
				{
					"paid_from_account_currency": "INR",
					"paid_to_account_currency": "INR",
					"count": 1,
					"sum_paid_amount": 1200.0,
					"sum_received_amount": 1200.0,
				}
			]
		return self.rows

	def test_exact_read_is_bounded_and_returns_native_reference_rows(self):
		result = read.get_payment_entry(
			"ACC-PAY-2026-00012", ["name", "status", "received_amount"]
		)
		self.assertEqual(
			result,
			{
				"status": "ok",
				"document": {
					"name": "ACC-PAY-2026-00012",
					"status": "Submitted",
					"received_amount": 1200.0,
					"references": [
						{
							"reference_doctype": "Sales Invoice",
							"reference_name": "ACC-SINV-2026-00009",
							"bill_no": "INV-9",
							"due_date": date(2026, 9, 30),
							"payment_term": "Net 30",
							"total_amount": 1200.0,
							"outstanding_amount": 1200.0,
							"allocated_amount": 1200.0,
							"exchange_rate": 1.0,
						},
					],
				},
			},
		)
		self.assertNotIn("bank_account_no", result["document"])
		self.assertNotIn("account", result["document"]["references"][0])

	def test_exact_read_handles_missing_and_denied_documents(self):
		self.fake_frappe.get_doc = lambda _doctype, _name: (_ for _ in ()).throw(
			frappe.DoesNotExistError
		)
		self.assertEqual(
			read.get_payment_entry("MISSING", ["name"]),
			{"status": "not_found", "name": "MISSING"},
		)
		self.fake_frappe.get_doc = lambda _doctype, _name: self.document
		self.document.has_permission = lambda _permission: False
		self.assertEqual(read.get_payment_entry("DENIED", ["name"])["code"], "PERMISSION_DENIED")

	def test_query_is_typed_bounded_and_uses_parent_permissions(self):
		criteria = PaymentEntryQueryInput(
			party_type="Customer",
			party="CUST-001",
			payment_type="Receive",
			posting_date_from=date(2026, 9, 1),
			posting_date_to=date(2026, 9, 30),
			paid_amount_min=1000,
			fields=["name", "party", "received_amount"],
			limit=5,
			offset=2,
			sort_by="received_amount",
			sort_order="asc",
		).model_dump()
		result = read.query_payment_entries(criteria)
		self.assertEqual(result["payment_entries"], [{"name": "ACC-PAY-2026-00012", "party": "CUST-001", "received_amount": 1200.0}])
		self.assertEqual(self.calls[0][0], "Payment Entry")
		kwargs = self.calls[0][1]
		self.assertFalse(kwargs["ignore_permissions"])
		self.assertEqual(kwargs["order_by"], "received_amount asc, name asc")
		self.assertEqual(kwargs["limit_start"], 2)
		self.assertIn(["paid_amount", ">=", 1000.0], kwargs["filters"])

	def test_linked_reference_filter_filters_parent_after_bounded_child_lookup(self):
		criteria = PaymentEntryQueryInput(
			reference_doctype="Sales Invoice",
			reference_name="ACC-SINV-2026-00009",
		).model_dump()
		read.query_payment_entries(criteria)
		self.assertEqual(self.calls[0][0], "Payment Entry Reference")
		self.assertFalse(self.calls[0][1]["ignore_permissions"])
		self.assertEqual(self.calls[1][0], "Payment Entry")
		self.assertIn(["name", "in", ["ACC-PAY-2026-00012"]], self.calls[1][1]["filters"])

	def test_unmatched_reference_returns_empty_without_parent_existence_leak(self):
		def get_list(doctype, **kwargs):
			self.calls.append((doctype, kwargs))
			return [] if doctype == "Payment Entry Reference" else self.rows

		self.fake_frappe.get_list = get_list
		criteria = PaymentEntryQueryInput(
			reference_doctype="Sales Invoice",
			reference_name="ACC-SINV-NONE",
		).model_dump()
		result = read.query_payment_entries(criteria)
		self.assertEqual(result["payment_entries"], [])
		self.assertEqual([call[0] for call in self.calls], ["Payment Entry Reference"])

	def test_aggregate_reuses_dict_syntax_and_currency_context(self):
		criteria = PaymentEntryAggregateInput(
			metrics=["count", "sum_paid_amount", "sum_received_amount"],
			group_by="party",
		).model_dump()
		result = read.aggregate_payment_entries(criteria)
		self.assertEqual(result["results"][0]["sum_received_amount"], 1200.0)
		kwargs = self.calls[0][1]
		self.assertFalse(kwargs["ignore_permissions"])
		self.assertIn("paid_from_account_currency", kwargs["group_by"])
		self.assertIn("paid_to_account_currency", kwargs["group_by"])
		self.assertTrue(all(isinstance(field, dict) for field in kwargs["fields"] if isinstance(field, dict)))

	def test_allocation_aggregate_fails_closed_without_payment_type_context(self):
		result = read.aggregate_payment_entries(
			PaymentEntryAggregateInput(metrics=["sum_total_allocated_amount"]).model_dump()
		)
		self.assertEqual(result["code"], "MIXED_CURRENCY_AGGREGATE")


class PaymentEntryReadContractTests(unittest.TestCase):
	def test_defaults_are_bounded_and_extra_or_raw_inputs_are_rejected(self):
		self.assertLessEqual(len(PaymentEntryGetInput(name="PE-1").fields), 30)
		with self.assertRaises(ValidationError):
			PaymentEntryGetInput(name="PE-1", fields=["bank_account_no"])
		with self.assertRaises(ValidationError):
			PaymentEntryQueryInput(filters="select * from tabPayment Entry")
		with self.assertRaises(ValidationError):
			PaymentEntryQueryInput(reference_doctype="Sales Invoice")

	def test_native_types_and_ranges_are_validated(self):
		with self.assertRaises(ValidationError):
			PaymentEntryQueryInput(payment_type="Refund")
		with self.assertRaises(ValidationError):
			PaymentEntryQueryInput(paid_amount_min=10, paid_amount_max=1)
		with self.assertRaises(ValidationError):
			PaymentEntryAggregateInput(metrics=["sum_grand_total"])
		with self.assertRaises(ValidationError):
			PaymentEntryAggregateInput(group_by="references")


if __name__ == "__main__":
	unittest.main()
