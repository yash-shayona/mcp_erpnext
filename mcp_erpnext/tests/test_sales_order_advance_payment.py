from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.approvals import ApprovalMode, approvals
from mcp_erpnext.contracts.accounts.sales_order_advance_payment import (
    SalesOrderAdvancePaymentConfirmInput,
    SalesOrderAdvancePaymentPrepareInput,
)
from mcp_erpnext.services.accounts import sales_order_advance_payment as service
from mcp_erpnext.tests.approval_test_backend import install_fake_backend


class SalesOrderAdvancePaymentContractTests(unittest.TestCase):
    def test_minimum_native_business_intent(self):
        request = SalesOrderAdvancePaymentPrepareInput(
            sales_order="SAL-ORD-0001",
            amount=100,
            mode_of_payment="Bank Transfer",
        )
        self.assertEqual(request.sales_order, "SAL-ORD-0001")
        self.assertEqual(request.amount, 100)

    def test_bank_account_destination(self):
        request = SalesOrderAdvancePaymentPrepareInput(
            sales_order="SAL-ORD-0001",
            amount=100,
            bank_account="BANK-0001",
        )
        self.assertEqual(request.bank_account, "BANK-0001")

    def test_amount_and_destination_are_bounded(self):
        for amount in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                SalesOrderAdvancePaymentPrepareInput(
                    sales_order="SAL-ORD-0001",
                    amount=amount,
                    mode_of_payment="Cash",
                )
        for values in ({}, {"mode_of_payment": "Cash", "bank_account": "BANK-1"}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                SalesOrderAdvancePaymentPrepareInput(
                    sales_order="SAL-ORD-0001", amount=100, **values
                )

    def test_raw_accounting_fields_and_unknown_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            SalesOrderAdvancePaymentPrepareInput(
                sales_order="SAL-ORD-0001",
                amount=100,
                mode_of_payment="Cash",
                paid_from="Debtors - TC",
            )

    def test_confirm_has_only_approval_fields(self):
        with self.assertRaises(ValidationError):
            SalesOrderAdvancePaymentConfirmInput(
                approval_token="opaque", confirm=True, amount=100
            )


class _Document:
    def __init__(self, doctype, name, *, docstatus=0, **values):
        self.doctype = doctype
        self.name = name
        self.docstatus = docstatus
        self.values = values
        self.insert_calls = []
        self.submit_calls = 0
        self.validate_calls = 0

    def get(self, key, default=None):
        if key == "name":
            return self.name
        if key == "docstatus":
            return self.docstatus
        return self.values.get(key, default)

    def has_permission(self, permission):
        return self.values.get(f"can_{permission}", True)

    def run_method(self, method):
        if method == "validate":
            self.validate_calls += 1

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        return self

    def submit(self):
        self.submit_calls += 1
        raise AssertionError("Task 53 confirmation must not submit Payment Entry")


class SalesOrderAdvancePaymentServiceTests(unittest.TestCase):
    def setUp(self):
        self.previous_approval_mode = approvals._approval_mode
        self.backend = install_fake_backend(approvals)
        approvals.configure_approval_mode(ApprovalMode.AGENT_DELEGATED)
        self.source = _Document(
            "Sales Order",
            "SAL-ORD-0001",
            docstatus=1,
            status="To Deliver and Bill",
            customer="CUST-0001",
            company="Test Company",
            currency="INR",
            grand_total=1000,
            advance_paid=0,
            modified="2026-09-17 10:00:00",
            payment_terms_template=None,
            payment_schedule=[],
        )
        self.destination = {
            "kind": "Mode of Payment",
            "identity": "Bank Transfer",
            "account": "Bank - TC",
            "currency": "INR",
            "account_type": "Bank",
        }
        self.first_payment = self._payment("ACC-PAY-0001")
        self.second_payment = self._payment("ACC-PAY-0002")
        self.fake_frappe = SimpleNamespace(
            session=SimpleNamespace(user="accounts@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            get_doc=lambda _doctype, _name: self.source,
            has_permission=lambda *_args, **_kwargs: True,
            DoesNotExistError=frappe.DoesNotExistError,
            PermissionError=frappe.PermissionError,
            ValidationError=frappe.ValidationError,
            db=SimpleNamespace(
                commit=lambda: None,
                rollback=lambda: None,
            ),
            throw=lambda message, error: (_ for _ in ()).throw(error(message)),
        )
        self.frappe_patch = patch.object(service, "frappe", self.fake_frappe)
        self.frappe_patch.start()
        self.nowdate_patch = patch.object(service, "nowdate", return_value="2026-09-17")
        self.nowdate_patch.start()

    def tearDown(self):
        self.frappe_patch.stop()
        self.nowdate_patch.stop()
        approvals.configure_approval_mode(self.previous_approval_mode)
        self.backend.clear()

    def _payment(self, name):
        return _Document(
            "Payment Entry",
            name,
            docstatus=0,
            party="CUST-0001",
            company="Test Company",
            payment_type="Receive",
            posting_date="2026-09-17",
            mode_of_payment="Bank Transfer",
            paid_from_account_currency="INR",
            paid_to_account_currency="INR",
            paid_amount=100,
            received_amount=100,
            source_exchange_rate=1,
            target_exchange_rate=1,
            references=[
                _Document(
                    "Payment Entry Reference",
                    "reference-1",
                    reference_doctype="Sales Order",
                    reference_name="SAL-ORD-0001",
                    due_date=None,
                    total_amount=100,
                    outstanding_amount=100,
                    allocated_amount=100,
                    payment_term=None,
                )
            ],
            total_allocated_amount=100,
            unallocated_amount=0,
            difference_amount=0,
            reference_no="UTR-1",
            reference_date="2026-09-17",
            book_advance_payments_in_separate_party_account=True,
            remarks="Advance",
            party_account="Customer Advance - TC",
            paid_from="Customer Advance - TC",
            paid_to="Bank - TC",
        )

    def test_prepare_uses_native_sales_order_factory_and_does_not_insert(self):
        native = Mock(return_value=self.first_payment)
        with patch.object(service, "_destination", return_value=(self.destination, None)):
            with patch.object(
                service, "_native_factory", return_value=native
            ) as native_factory:
                result = service.prepare_sales_order_advance_payment(
                    {
                        "sales_order": "SAL-ORD-0001",
                        "amount": 100,
                        "mode_of_payment": "Bank Transfer",
                        "reference_no": "UTR-1",
                        "reference_date": "2026-09-17",
                        "remarks": "Advance",
                    }
                )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(self.first_payment.insert_calls, [])
        self.assertEqual(self.first_payment.validate_calls, 1)
        self.assertEqual(native_factory.call_count, 1)
        native.assert_called_once()
        self.assertEqual(native.call_args.args[:2], ("Sales Order", "SAL-ORD-0001"))
        self.assertEqual(native.call_args.kwargs["party_amount"], 100)
        self.assertEqual(native.call_args.kwargs["party_type"], "Customer")
        self.assertEqual(native.call_args.kwargs["payment_type"], "Receive")
        self.assertEqual(
            result["preview"]["references"][0]["reference_doctype"], "Sales Order"
        )

    def test_confirm_rebuilds_and_inserts_one_draft_without_submit(self):
        with patch.object(service, "_destination", return_value=(self.destination, None)):
            with patch.object(
                service,
                "_native_factory",
                side_effect=[
                    lambda *args, **kwargs: self.first_payment,
                    lambda *args, **kwargs: self.second_payment,
                ],
            ):
                prepared = service.prepare_sales_order_advance_payment(
                    {
                        "sales_order": "SAL-ORD-0001",
                        "amount": 100,
                        "mode_of_payment": "Bank Transfer",
                        "reference_no": "UTR-1",
                        "reference_date": "2026-09-17",
                    }
                )
                result = service.confirm_sales_order_advance_payment(
                    prepared["approval_token"], True
                )

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["docstatus"], 0)
        self.assertEqual(len(self.second_payment.insert_calls), 1)
        self.assertEqual(self.second_payment.submit_calls, 0)
        self.assertEqual(self.first_payment.insert_calls, [])

    def test_material_source_change_returns_stale_and_creates_nothing(self):
        with patch.object(service, "_destination", return_value=(self.destination, None)):
            with patch.object(
                service,
                "_native_factory",
                side_effect=[
                    lambda *args, **kwargs: self.first_payment,
                    lambda *args, **kwargs: self.second_payment,
                ],
            ):
                prepared = service.prepare_sales_order_advance_payment(
                    {
                        "sales_order": "SAL-ORD-0001",
                        "amount": 100,
                        "mode_of_payment": "Bank Transfer",
                        "reference_no": "UTR-1",
                        "reference_date": "2026-09-17",
                    }
                )
                self.source.values["modified"] = "2026-09-17 10:01:00"
                result = service.confirm_sales_order_advance_payment(
                    prepared["approval_token"], True
                )

        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        self.assertEqual(self.second_payment.insert_calls, [])


if __name__ == "__main__":
    unittest.main()
