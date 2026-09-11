from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import TypeAdapter, ValidationError

from mcp_erpnext.approvals import approvals
from mcp_erpnext.contracts.selling.sales_order_to_sales_invoice import (
    PrepareSalesOrderToSalesInvoiceResult,
    SalesOrderToSalesInvoiceInput,
)
from mcp_erpnext.services.selling import sales_order_to_sales_invoice as service


class FakeRow:
	def __init__(self, **values):
		self.values = values

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)


class FakeDocument:
	def __init__(self, doctype, name, *, docstatus=0, items=None, **values):
		self.doctype = doctype
		self.name = name
		self.docstatus = docstatus
		self.values = values
		self.items = items or []
		self.taxes = values.pop("taxes", [])
		self.payment_schedule = values.pop("payment_schedule", [])
		self.insert_calls = []
		self.run_methods = []

	def get(self, fieldname, default=None):
		if fieldname == "items":
			return self.items
		if fieldname == "taxes":
			return self.taxes
		if fieldname == "payment_schedule":
			return self.payment_schedule
		return self.values.get(fieldname, default)

	def has_permission(self, permission):
		return self.values.get(f"can_{permission}", True)

	def insert(self, **kwargs):
		self.insert_calls.append(kwargs)
		return self

	def run_method(self, method):
		self.run_methods.append(method)
		return self


def source_document(*, docstatus=1, can_read=True):
	return FakeDocument(
		"Sales Order",
		"SAL-ORD-0001",
		docstatus=docstatus,
		can_read=can_read,
		status="To Bill",
		customer="CUST-001",
		customer_name="Acme Customer",
		company="Test Company",
		currency="INR",
		transaction_date="2026-09-10",
		delivery_date="2026-09-20",
		per_billed=40,
		per_delivered=100,
		per_returned=0,
		total_qty=5,
		net_total=500,
		total_taxes_and_charges=90,
		grand_total=590,
		items=[
			FakeRow(
				name="SAL-ORD-ITEM-0001",
				item_code="ITEM-001",
				uom="Nos",
				stock_uom="Nos",
				conversion_factor=1,
				qty=5,
				delivered_qty=5,
				returned_qty=0,
				billed_qty=2,
				billed_amt=200,
				rate=100,
				amount=500,
				warehouse="Stores - TC",
				project="PROJ-001",
			)
		],
	)


def mapped_invoice(*, qty=3, rate=100, items=True, name="ACC-SINV-0001"):
	return FakeDocument(
		"Sales Invoice",
		name,
		docstatus=0,
		customer="CUST-001",
		customer_name="Acme Customer",
		company="Test Company",
		posting_date="2026-09-11",
		due_date="2026-10-11",
		currency="INR",
		selling_price_list="Standard Selling",
		debit_to="Debtors - TC",
		billing_address="Billing Address",
		shipping_address="Shipping Address",
		company_address="Company Address",
		net_total=qty * rate,
		total_taxes_and_charges=qty * rate * 0.18,
		grand_total=qty * rate * 1.18,
		rounded_total=qty * rate * 1.18,
		outstanding_amount=qty * rate * 1.18,
		base_net_total=qty * rate,
		base_grand_total=qty * rate * 1.18,
		total_qty=qty,
		taxes=[
			FakeRow(
				charge_type="On Net Total",
				account_head="GST - TC",
				rate=18,
				tax_amount=qty * rate * 0.18,
				total=qty * rate * 1.18,
			)
		],
		payment_schedule=[
			FakeRow(
				due_date="2026-10-11",
				payment_term="Net 30",
				invoice_portion=100,
				payment_amount=qty * rate * 1.18,
				discount_type=None,
				discount_date=None,
				discount=0,
			)
		],
		items=(
			[
				FakeRow(
					item_code="ITEM-001",
					item_name="Known Item",
					qty=qty,
					uom="Nos",
					conversion_factor=1,
					rate=rate,
					amount=qty * rate,
					warehouse="Stores - TC",
					project="PROJ-001",
					sales_order="SAL-ORD-0001",
					so_detail="SAL-ORD-ITEM-0001",
				)
			]
			if items
			else []
		),
	)


class SalesOrderToSalesInvoiceServiceTests(unittest.TestCase):
	def setUp(self):
		approvals._approvals.clear()
		self.source = source_document()
		self.mapped = mapped_invoice()
		self.map_results = [self.mapped]
		self.allow_target_create = True
		self.commit_calls = 0
		self.rollback_calls = 0

		def get_doc(doctype, name):
			if doctype == "Sales Order" and name == self.source.name:
				return self.source
			raise frappe.DoesNotExistError(name)

		def commit():
			self.commit_calls += 1

		def rollback():
			self.rollback_calls += 1

		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			has_permission=lambda *_: self.allow_target_create,
			get_doc=get_doc,
			DoesNotExistError=frappe.DoesNotExistError,
			PermissionError=frappe.PermissionError,
			ValidationError=frappe.ValidationError,
			db=SimpleNamespace(commit=commit, rollback=rollback),
			throw=lambda message, error: (_ for _ in ()).throw(error(message)),
		)
		self.patches = [patch.object(service, "frappe", self.fake_frappe)]
		for active_patch in self.patches:
			active_patch.start()

	def tearDown(self):
		for active_patch in reversed(self.patches):
			active_patch.stop()
		approvals._approvals.clear()

	def native_mapper(self, source_name, *, target_doc=None, args=None, ignore_permissions=False):
		self.assertEqual(source_name, self.source.name)
		return self.map_results.pop(0)

	def prepare(self):
		with patch.object(service, "_native_make_sales_invoice", side_effect=self.native_mapper):
			return service.prepare_sales_order_to_sales_invoice("SAL-ORD-0001")

	def approve(self, result):
		approvals.record_trusted_user_approval(
			result["approval_token"],
			action="convert_sales_order_to_sales_invoice",
			site="test.localhost",
			user="sales@example.com",
		)

	def confirm(self, token):
		with patch.object(service, "_native_make_sales_invoice", side_effect=self.native_mapper):
			return service.confirm_sales_order_to_sales_invoice(token, True)

	def test_prepare_uses_native_remaining_qty_lineage_and_no_validation_or_write(self):
		with patch.object(service, "_native_make_sales_invoice", side_effect=self.native_mapper):
			result = service.prepare_sales_order_to_sales_invoice("SAL-ORD-0001")

		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["source"]["name"], "SAL-ORD-0001")
		item = result["preview"]["sales_invoice"]["items"][0]
		self.assertEqual(item["qty"], 3)
		self.assertEqual(item["sales_order"], "SAL-ORD-0001")
		self.assertEqual(item["so_detail"], "SAL-ORD-ITEM-0001")
		self.assertEqual(self.mapped.insert_calls, [])
		self.assertEqual(self.mapped.run_methods, [])
		self.assertEqual(result["preview"]["sales_invoice"]["payment_schedule"][0]["payment_term"], "Net 30")

	def test_draft_cancelled_missing_and_permission_denied_sources_do_not_map(self):
		for docstatus in (0, 2):
			self.source.docstatus = docstatus
			with patch.object(service, "_native_make_sales_invoice") as native:
				result = service.prepare_sales_order_to_sales_invoice("SAL-ORD-0001")
			self.assertEqual(result["code"], "SOURCE_NOT_READY")
			native.assert_not_called()

		self.source.docstatus = 1
		with patch.object(service, "_native_make_sales_invoice") as native:
			result = service.prepare_sales_order_to_sales_invoice("missing")
		self.assertEqual(result["code"], "SOURCE_NOT_FOUND")
		native.assert_not_called()

		self.source.values["can_read"] = False
		with patch.object(service, "_native_make_sales_invoice") as native:
			result = service.prepare_sales_order_to_sales_invoice("SAL-ORD-0001")
		self.assertEqual(result["code"], "PERMISSION_DENIED")
		native.assert_not_called()

		self.source.values["can_read"] = True
		self.allow_target_create = False
		with patch.object(service, "_native_make_sales_invoice") as native:
			result = service.prepare_sales_order_to_sales_invoice("SAL-ORD-0001")
		self.assertEqual(result["code"], "PERMISSION_DENIED")
		native.assert_not_called()

	def test_no_mappable_items_do_not_create_approval(self):
		self.map_results = [mapped_invoice(items=False)]
		result = self.prepare()
		self.assertEqual(result["code"], "NO_MAPPABLE_ITEMS")
		self.assertEqual(approvals._approvals, {})

	def test_confirm_claims_approval_remaps_and_inserts_only_fresh_draft(self):
		prepared = self.prepare()
		self.approve(prepared)
		fresh = mapped_invoice(name="ACC-SINV-0002")
		self.map_results = [fresh]
		created = self.confirm(prepared["approval_token"])

		self.assertEqual(created["status"], "created")
		self.assertEqual(created["doctype"], "Sales Invoice")
		self.assertEqual(created["sales_invoice"], "ACC-SINV-0002")
		self.assertEqual(created["docstatus"], 0)
		self.assertEqual(fresh.insert_calls, [{
			"ignore_permissions": False,
			"ignore_links": False,
			"ignore_mandatory": False,
		}])
		self.assertEqual(self.mapped.insert_calls, [])
		self.assertEqual(self.commit_calls, 1)
		self.assertEqual(self.rollback_calls, 0)
		self.assertEqual(
			service.confirm_sales_order_to_sales_invoice(prepared["approval_token"], True)["code"],
			"CONFIRMATION_CONSUMED",
		)

	def test_partial_billing_change_is_stale_even_without_source_modified_check(self):
		prepared = self.prepare()
		self.approve(prepared)
		self.map_results = [mapped_invoice(qty=1, name="ACC-SINV-0003")]
		result = self.confirm(prepared["approval_token"])
		self.assertEqual(result["code"], "STALE_CONFIRMATION")
		self.assertEqual(self.map_results, [])
		self.assertEqual(self.mapped.insert_calls, [])

	def test_source_change_and_cancellation_are_stale_without_insert(self):
		prepared = self.prepare()
		self.approve(prepared)
		self.source.values["customer"] = "CUST-CHANGED"
		self.map_results = [mapped_invoice(name="ACC-SINV-0004")]
		result = self.confirm(prepared["approval_token"])
		self.assertEqual(result["code"], "STALE_CONFIRMATION")
		self.assertEqual(self.map_results, [])

		self.source.values["customer"] = "CUST-001"
		self.map_results = [mapped_invoice(name="ACC-SINV-0005")]
		prepared = self.prepare()
		self.approve(prepared)
		self.source.docstatus = 2
		result = service.confirm_sales_order_to_sales_invoice(prepared["approval_token"], True)
		self.assertEqual(result["code"], "STALE_CONFIRMATION")

	def test_confirm_without_approval_is_denied(self):
		result = service.confirm_sales_order_to_sales_invoice("not-a-token", True)
		self.assertEqual(result["code"], "CONFIRMATION_EXPIRED")

	def test_contract_accepts_only_exact_sales_order_name(self):
		self.assertEqual(
			SalesOrderToSalesInvoiceInput.model_validate({"sales_order": "SAL-ORD-0001"}).sales_order,
			"SAL-ORD-0001",
		)
		for payload in ({}, {"sales_order": " "}, {"sales_order": "SAL-ORD-0001", "items": []}):
			with self.subTest(payload=payload), self.assertRaises(ValidationError):
				SalesOrderToSalesInvoiceInput.model_validate(payload)

	def test_ready_result_is_typed(self):
		result = self.prepare()
		validated = TypeAdapter(PrepareSalesOrderToSalesInvoiceResult).validate_python(result)
		self.assertEqual(validated.status, "ready")


if __name__ == "__main__":
	unittest.main()
