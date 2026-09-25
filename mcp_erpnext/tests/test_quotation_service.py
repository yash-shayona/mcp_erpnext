from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import TypeAdapter

from mcp_erpnext.approvals import APPROVAL_TTL_SECONDS, approvals
from mcp_erpnext.contracts.selling.quotation import PrepareQuotationResult
from mcp_erpnext.services.selling import quotation as quotation_service
from mcp_erpnext.settings import ApprovalMode
from mcp_erpnext.tests.approval_test_backend import (
	install_fake_backend,
	mutate_record,
)


class FakeRow(SimpleNamespace):
	def as_dict(self):
		return dict(self.__dict__)


class FakeQuotation:
	def __init__(self, values: dict | None = None):
		self.__dict__.update(values or {})
		self.doctype = getattr(self, "doctype", None) or "Quotation"
		self.name = getattr(self, "name", None) or "SAL-QTN-TEST-0001"
		self.docstatus = getattr(self, "docstatus", None) or 0
		self.items = [FakeRow(**row) if isinstance(row, dict) else row for row in (getattr(self, "items", None) or [])]
		self.taxes = [FakeRow(**row) if isinstance(row, dict) else row for row in (getattr(self, "taxes", None) or [])]
		self.insert_calls: list[dict] = []
		self.validate_calls = 0
		self.native_validation_error = None

	def __getattr__(self, name):
		return None

	def get(self, name, default=None):
		return getattr(self, name, default)

	def append(self, table, values):
		row = FakeRow(**values)
		getattr(self, table).append(row)
		return row

	def set_missing_values(self):
		self.customer_name = "Acme Customer"
		self.selling_price_list = self.selling_price_list or "Standard Selling"
		self.price_list_currency = "INR"
		self.currency = "INR"
		self.conversion_rate = 1
		self.plc_conversion_rate = 1
		for row in self.items:
			row.item_name = row.item_code
			row.uom = "Nos"
			row.rate = getattr(row, "rate", None) if getattr(row, "rate", None) is not None else 100
			row.discount_percentage = getattr(row, "discount_percentage", None) or 0
			row.discount_amount = getattr(row, "discount_amount", None) or 0
			row.amount = row.qty * row.rate
			row.net_amount = row.amount - row.discount_amount
		if self.taxes_and_charges:
			self.taxes = [FakeRow(charge_type="On Net Total", account_head="GST", rate=18, tax_amount=18, total=118)]
		if self.tc_name:
			self.terms = "Standard terms"

	def set_missing_terms(self):
		if self.tc_name and not self.terms:
			self.terms = "Standard terms"

	def calculate_taxes_and_totals(self):
		self.net_total = sum(row.net_amount for row in self.items)
		self.total_taxes_and_charges = sum(row.tax_amount for row in self.taxes)
		self.grand_total = self.net_total + self.total_taxes_and_charges - (self.discount_amount or 0)

	def validate(self):
		self.validate_calls += 1
		if self.native_validation_error:
			raise self.native_validation_error

	def as_dict(self):
		result = dict(self.__dict__)
		result["items"] = [row.as_dict() for row in self.items]
		result["taxes"] = [row.as_dict() for row in self.taxes]
		result.pop("insert_calls", None)
		return result

	def insert(self, **kwargs):
		self.insert_calls.append(kwargs)
		return self


class QuotationServiceTests(unittest.TestCase):
	def setUp(self):
		self.approval_backend = install_fake_backend(approvals)
		self.docs: list[FakeQuotation] = []
		self.commit_count = 0
		self.rollback_count = 0
		self.native_validation_error = None
		self.available_customers = {"CUST-001"}
		self.available_items = {"ITEM-001", "ITEM-002"}
		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			has_permission=lambda *_: True,
			get_list=self._get_list,
			new_doc=self._new_doc,
			get_doc=self._get_doc,
			defaults=SimpleNamespace(get_user_default=lambda _: "Test Company"),
			db=SimpleNamespace(commit=self._commit, rollback=self._rollback),
			PermissionError=frappe.PermissionError,
			ValidationError=frappe.ValidationError,
		)
		self.patches = [
			patch.object(quotation_service, "frappe", self.fake_frappe),
			patch.object(quotation_service, "nowdate", return_value="2026-08-25"),
			patch.object(quotation_service, "getdate", side_effect=date.fromisoformat),
		]
		for active_patch in self.patches:
			active_patch.start()

	def tearDown(self):
		for active_patch in reversed(self.patches):
			active_patch.stop()

	def _get_list(self, doctype, *, filters=None, fields=None, **kwargs):
		name = filters.get("name") if filters else None
		if doctype == "Customer" and name in self.available_customers:
			return [{"name": name, "customer_name": "Acme Customer"}]
		if doctype == "Item" and name in self.available_items:
			return [{"name": name, "item_code": name, "item_name": name, "stock_uom": "Nos"}]
		if doctype == "Company" and name == "Test Company":
			return [{"name": name}]
		if doctype == "Price List" and name == "Standard Selling":
			return [{"name": name}]
		if doctype == "Sales Taxes and Charges Template" and name == "GST 18%":
			return [{"name": name}]
		if doctype == "Terms and Conditions" and name == "Standard Terms":
			return [{"name": name}]
		return []

	def _new_doc(self, doctype):
		self.assertEqual(doctype, "Quotation")
		doc = FakeQuotation()
		doc.native_validation_error = self.native_validation_error
		self.docs.append(doc)
		return doc

	def _get_doc(self, values):
		doc = FakeQuotation(values)
		self.docs.append(doc)
		return doc

	def _commit(self):
		self.commit_count += 1

	def _rollback(self):
		self.rollback_count += 1

	@staticmethod
	def customer():
		return {"doctype": "Customer", "name": "CUST-001"}

	@staticmethod
	def item(name="ITEM-001", **values):
		return {"item": {"doctype": "Item", "name": name}, "qty": 2, **values}

	def prepare(self, **overrides):
		arguments = {
			"customer": self.customer(),
			"items": [self.item()],
			"valid_till": "2026-08-31",
		}
		arguments.update(overrides)
		return quotation_service.prepare_quotation(**arguments)

	def test_valid_existing_customer_and_item_prepare_without_insert(self):
		result = self.prepare()
		self.assertEqual(result["status"], "ready")
		self.assertEqual(self.commit_count, 0)
		self.assertTrue(all(not doc.insert_calls for doc in self.docs))
		self.assertEqual(result["preview"]["customer"]["name"], "CUST-001")
		self.assertEqual(self.docs[0].validate_calls, 1)

	def test_multiple_item_lines_are_in_erpnext_preview(self):
		result = self.prepare(items=[self.item("ITEM-001"), self.item("ITEM-002", qty=3)])
		self.assertEqual(result["status"], "ready")
		self.assertEqual([row["item_code"] for row in result["preview"]["items"]], ["ITEM-001", "ITEM-002"])

	def test_omitted_valid_till_defaults_to_the_transaction_date(self):
		result = self.prepare(valid_till=None)
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["valid_till"], "2026-08-25")

	def test_omitted_valid_till_uses_configured_validity_days(self):
		with patch.dict("os.environ", {"MCP_QUOTATION_VALIDITY_DAYS": "30"}):
			result = self.prepare(valid_till=None, transaction_date="2026-08-20")
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["valid_till"], "2026-09-19")

	def test_native_validation_rejects_valid_till_before_transaction_date(self):
		self.native_validation_error = frappe.ValidationError(
			"Valid till date cannot be before transaction date"
		)

		result = self.prepare(valid_till="2026-08-24")

		self.assertEqual(result["status"], "error")
		self.assertEqual(result["code"], "NATIVE_VALIDATION_FAILED")
		self.assertNotIn("Valid till date", result["message"])
		self.assertTrue(self.approval_backend.is_empty())
		self.assertEqual(self.docs[0].validate_calls, 1)

	def test_date_order_is_not_checked_outside_native_validation(self):
		result = self.prepare(
			valid_till="2026-08-24", transaction_date="2026-08-25"
		)

		self.assertEqual(result["status"], "ready")
		self.assertEqual(self.docs[0].validate_calls, 1)

	def test_same_transaction_and_validity_date_is_accepted_by_native_path(self):
		result = self.prepare(
			valid_till="2026-08-25", transaction_date="2026-08-25"
		)

		self.assertEqual(result["status"], "ready")

	def test_invalid_quantity_and_rate_are_rejected(self):
		for row in (self.item(qty=0), self.item(rate=-1)):
			with self.subTest(row=row):
				result = self.prepare(items=[row])
				self.assertEqual(result["code"], "INVALID_QUOTATION_DETAILS")

	def test_explicit_description_and_terms_are_in_the_reviewed_payload(self):
		result = self.prepare(items=[self.item(description="Document-specific")], tc_name="Standard Terms")
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["items"][0]["description"], "Document-specific")
		self.assertEqual(result["preview"]["tc_name"], "Standard Terms")
		self.assertEqual(result["preview"]["terms"], "Standard terms")

	def test_erpnext_pricing_and_explicit_rate_are_previewed(self):
		priced = self.prepare()
		explicit = self.prepare(items=[self.item(rate=250)])
		self.assertEqual(priced["preview"]["items"][0]["rate"], 100)
		self.assertEqual(explicit["preview"]["items"][0]["rate"], 250)

	def test_standard_tax_template_and_discount_fields_are_previewed(self):
		result = self.prepare(
			taxes_and_charges="GST 18%",
			additional_discount_percentage=5,
			tc_name="Standard Terms",
		)
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["taxes"][0]["account_head"], "GST")
		self.assertEqual(result["preview"]["additional_discount_percentage"], 5)
		self.assertEqual(result["preview"]["terms"], "Standard terms")

	def test_unset_additional_discounts_are_zero_in_the_typed_preview(self):
		result = self.prepare()
		self.assertEqual(result["preview"]["additional_discount_percentage"], 0)
		self.assertEqual(result["preview"]["discount_amount"], 0)
		TypeAdapter(PrepareQuotationResult).validate_python(result)

	def test_unreadable_commercial_settings_are_rejected(self):
		for keyword, value in (
			("selling_price_list", "Private Price List"),
			("taxes_and_charges", "Private Tax Template"),
			("tc_name", "Private Terms"),
		):
			with self.subTest(keyword=keyword):
				result = self.prepare(**{keyword: value})
				self.assertEqual(result["code"], "INVALID_QUOTATION_DETAILS")

	def test_invalid_customer_or_item_is_safely_rejected(self):
		customer = self.prepare(customer={"doctype": "Customer", "name": "MISSING"})
		item = self.prepare(items=[self.item("MISSING")])
		self.assertEqual(customer["code"], "INVALID_CUSTOMER")
		self.assertEqual(item["code"], "INVALID_ITEM")

	def test_user_without_quotation_create_permission_is_rejected(self):
		with patch.object(self.fake_frappe, "has_permission", return_value=False):
			result = self.prepare()
		self.assertEqual(result["status"], "permission_denied")

	def test_valid_confirmation_creates_draft_once(self):
		prepared = self.prepare()
		approvals.record_trusted_user_approval(
			prepared["approval_token"], action="create_quotation", site="test.localhost", user="sales@example.com"
		)
		result = quotation_service.confirm_quotation(prepared["approval_token"], True)
		self.assertEqual(result, {"status": "created", "quotation": "SAL-QTN-TEST-0001", "docstatus": 0, "idempotent": False})
		self.assertEqual(self.commit_count, 1)
		self.assertEqual(self.docs[-1].insert_calls, [{"ignore_permissions": False, "ignore_links": False, "ignore_mandatory": False}])

	def test_expired_wrong_user_and_wrong_action_are_rejected(self):
		prepared = self.prepare()
		mutate_record(approvals, self.approval_backend, prepared["approval_token"], lambda approval: setattr(approval, "created_at", approval.created_at - APPROVAL_TTL_SECONDS - 1), ttl_seconds=0)
		self.assertEqual(quotation_service.confirm_quotation(prepared["approval_token"], True)["code"], "CONFIRMATION_EXPIRED")

		prepared = self.prepare()
		self.fake_frappe.session.user = "other@example.com"
		self.assertEqual(quotation_service.confirm_quotation(prepared["approval_token"], True)["code"], "CONFIRMATION_UNAVAILABLE")
		self.fake_frappe.session.user = "sales@example.com"

		wrong_action = approvals.create(action="create_sales_order", site="test.localhost", user="sales@example.com", payload={"doctype": "Quotation", "party_name": "CUST-001", "items": [{}]})
		self.assertEqual(quotation_service.confirm_quotation(wrong_action, True)["code"], "CONFIRMATION_UNAVAILABLE")

	def test_tampered_server_payload_is_rejected(self):
		prepared = self.prepare()
		mutate_record(approvals, self.approval_backend, prepared["approval_token"], lambda approval: approval.payload.update({"party_name": "MISSING"}))
		result = quotation_service.confirm_quotation(prepared["approval_token"], True)
		self.assertEqual(result["code"], "CONFIRMATION_UNAVAILABLE")
		self.assertEqual(self.commit_count, 0)

	def test_model_confirm_true_cannot_self_grant_approval(self):
		previous_mode = approvals._approval_mode
		approvals.configure_approval_mode(ApprovalMode.TRUSTED_HUMAN)
		try:
			prepared = self.prepare()
			result = quotation_service.confirm_quotation(prepared["approval_token"], True)
			self.assertEqual(result["code"], "TRUSTED_APPROVAL_UNAVAILABLE")
			self.assertEqual(self.commit_count, 0)
		finally:
			approvals.configure_approval_mode(previous_mode)


if __name__ == "__main__":
	unittest.main()
