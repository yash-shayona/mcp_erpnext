from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import TypeAdapter, ValidationError

from mcp_erpnext.approvals import approvals
from mcp_erpnext.contracts.selling.quotation_to_sales_order import (
    PrepareQuotationToSalesOrderResult,
    QuotationToSalesOrderInput,
)
from mcp_erpnext.services.selling import quotation_to_sales_order as service


class FakeRow:
	def __init__(self, **values):
		self.values = values

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)


class FakeDocument:
	def __init__(self, doctype, name, **values):
		self.doctype = doctype
		self.name = name
		self.values = values
		self.docstatus = values.get("docstatus", 1 if doctype == "Quotation" else 0)
		self.items = values.get("items", [])
		self.taxes = values.get("taxes", [])
		self.insert_calls = []

	def get(self, fieldname, default=None):
		if fieldname == "items":
			return self.items
		if fieldname == "taxes":
			return self.taxes
		return self.values.get(fieldname, default)

	def has_permission(self, permission):
		return self.values.get(f"can_{permission}", True)

	def insert(self, **kwargs):
		self.insert_calls.append(kwargs)
		return self


def mapped_order(*, rate=500, items=True):
	rows = (
		[
			FakeRow(
				item_code="ITEM-001",
				item_name="Known Item",
				qty=2,
				uom="Nos",
				rate=rate,
				discount_percentage=0,
				discount_amount=0,
				amount=rate * 2,
				net_amount=rate * 2,
				warehouse="Stores - TC",
				delivery_date="2026-09-20",
				quotation_item="QTN-ITEM-001",
				prevdoc_docname="SAL-QTN-0001",
			)
		]
		if items
		else []
	)
	return FakeDocument(
		"Sales Order",
		"SAL-ORD-0001",
		customer="CUST-001",
		customer_name="Acme Customer",
		company="Test Company",
		transaction_date="2026-09-10",
		delivery_date="2026-09-20",
		currency="INR",
		selling_price_list="Standard Selling",
		items=rows,
		taxes=[FakeRow(charge_type="On Net Total", account_head="GST", rate=18, tax_amount=18, total=218)],
		net_total=200,
		total_taxes_and_charges=18,
		additional_discount_percentage=0,
		discount_amount=0,
		grand_total=218,
		tc_name="Standard Terms",
		terms="Pay within 30 days",
	)


class QuotationToSalesOrderServiceTests(unittest.TestCase):
	def setUp(self):
		approvals._approvals.clear()
		self.source = FakeDocument(
			"Quotation",
			"SAL-QTN-0001",
			quotation_to="Customer",
			party_name="CUST-001",
			company="Test Company",
			currency="INR",
			transaction_date="2026-09-01",
			valid_till="2026-09-30",
		)
		self.created_orders = []
		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			has_permission=lambda *_: True,
			get_doc=lambda doctype, name: self.source if doctype == "Quotation" else None,
			DoesNotExistError=frappe.DoesNotExistError,
			PermissionError=frappe.PermissionError,
			db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
			throw=lambda message, error: (_ for _ in ()).throw(error(message)),
		)
		self.native = mapped_order()
		self.patches = [
			patch.object(service, "frappe", self.fake_frappe),
			patch.object(service, "_native_make_sales_order", side_effect=lambda _: self.native),
		]
		for active_patch in self.patches:
			active_patch.start()

	def tearDown(self):
		for active_patch in reversed(self.patches):
			active_patch.stop()
		approvals._approvals.clear()

	def prepare(self):
		return service.prepare_quotation_to_sales_order("SAL-QTN-0001")

	def approve(self, result):
		approvals.record_trusted_user_approval(
			result["approval_token"],
			action="convert_quotation_to_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)

	def test_prepare_uses_native_rate_and_lineage_without_writing(self):
		result = self.prepare()
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["source"]["quotation"], "SAL-QTN-0001")
		item = result["preview"]["sales_order"]["items"][0]
		self.assertEqual(item["rate"], 500)
		self.assertEqual(item["quotation_item"], "QTN-ITEM-001")
		self.assertEqual(item["prevdoc_docname"], "SAL-QTN-0001")
		self.assertEqual(self.native.insert_calls, [])

	def test_draft_and_unsupported_party_are_rejected_before_native_mapper(self):
		self.source.docstatus = 0
		with patch.object(service, "_native_make_sales_order") as native:
			result = self.prepare()
		self.assertEqual(result["code"], "SOURCE_NOT_READY")
		native.assert_not_called()

		self.source.docstatus = 1
		self.source.values["quotation_to"] = "Lead"
		with patch.object(service, "_native_make_sales_order") as native:
			result = self.prepare()
		self.assertEqual(result["code"], "UNSUPPORTED_QUOTATION_PARTY")
		self.assertEqual(approvals._approvals, {})
		native.assert_not_called()

	def test_no_mappable_items_do_not_create_an_approval(self):
		self.native = mapped_order(items=False)
		result = self.prepare()
		self.assertEqual(result["code"], "NO_MAPPABLE_ITEMS")
		self.assertEqual(approvals._approvals, {})

	def test_confirm_revalidates_native_mapping_and_creates_one_draft(self):
		prepared = self.prepare()
		self.approve(prepared)
		created = service.confirm_quotation_to_sales_order(prepared["approval_token"], True)
		self.assertEqual(created["status"], "created")
		self.assertEqual(created["source_quotation"], "SAL-QTN-0001")
		self.assertEqual(created["docstatus"], 0)
		self.assertEqual(self.native.insert_calls, [{"ignore_permissions": False, "ignore_links": False, "ignore_mandatory": False}])
		replayed = service.confirm_quotation_to_sales_order(prepared["approval_token"], True)
		self.assertEqual(replayed["code"], "CONFIRMATION_CONSUMED")

	def test_changed_native_mapping_is_stale_and_not_inserted(self):
		prepared = self.prepare()
		self.approve(prepared)
		self.native = mapped_order(rate=600)
		result = service.confirm_quotation_to_sales_order(prepared["approval_token"], True)
		self.assertEqual(result["code"], "STALE_CONFIRMATION")
		self.assertEqual(self.native.insert_calls, [])

	def test_declined_confirmation_cancels_without_writing(self):
		prepared = self.prepare()
		result = service.confirm_quotation_to_sales_order(prepared["approval_token"], False)
		self.assertEqual(result["code"], "CONFIRMATION_REQUIRED")
		self.assertEqual(self.native.insert_calls, [])
		self.assertEqual(
			service.confirm_quotation_to_sales_order(prepared["approval_token"], True)["code"],
			"CONFIRMATION_CONSUMED",
		)

	def test_conversion_contract_accepts_only_exact_name(self):
		self.assertEqual(
			QuotationToSalesOrderInput.model_validate({"quotation": "SAL-QTN-0001"}).quotation,
			"SAL-QTN-0001",
		)
		for payload in ({}, {"quotation": " "}, {"quotation": "SAL-QTN-0001", "items": []}):
			with self.subTest(payload=payload), self.assertRaises(ValidationError):
				QuotationToSalesOrderInput.model_validate(payload)

	def test_ready_result_is_typed(self):
		result = self.prepare()
		validated = TypeAdapter(PrepareQuotationToSalesOrderResult).validate_python(result)
		self.assertEqual(validated.status, "ready")


if __name__ == "__main__":
	unittest.main()

