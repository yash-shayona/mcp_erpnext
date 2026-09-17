from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.approvals import ApprovalMode, approvals
from mcp_erpnext.contracts.accounts.customer_payment_reconciliation import (
    CustomerPaymentReconciliationConfirmInput,
    CustomerPaymentReconciliationPrepareInput,
)
from mcp_erpnext.services.accounts import customer_payment_reconciliation as service
from mcp_erpnext.tests.approval_test_backend import install_fake_backend


class CustomerPaymentReconciliationContractTests(unittest.TestCase):
    def test_public_intent_is_exact_payment_invoice_and_amount(self):
        request = CustomerPaymentReconciliationPrepareInput(
            payment_entry="ACC-PAY-0001",
            sales_invoice="ACC-SINV-0001",
            amount="25.00",
        )
        self.assertEqual(request.payment_entry, "ACC-PAY-0001")
        self.assertEqual(request.sales_invoice, "ACC-SINV-0001")
        self.assertEqual(request.amount, 25.0)

    def test_amount_is_positive_finite_and_not_boolean(self):
        for amount in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                CustomerPaymentReconciliationPrepareInput(
                    payment_entry="ACC-PAY-0001",
                    sales_invoice="ACC-SINV-0001",
                    amount=amount,
                )

    def test_unknown_and_internal_fields_are_rejected(self):
        for field in ("reference_row", "account", "exchange_rate", "user", "site"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                CustomerPaymentReconciliationPrepareInput(
                    payment_entry="ACC-PAY-0001",
                    sales_invoice="ACC-SINV-0001",
                    amount=25,
                    **{field: "forbidden"},
                )

    def test_confirmation_has_only_shared_approval_fields(self):
        with self.assertRaises(ValidationError):
            CustomerPaymentReconciliationConfirmInput(
                approval_token="opaque", confirm=True, amount=25
            )


class _Row:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def update(self, values):
        self.values.update(values)


class _Doc(_Row):
    def __init__(self, doctype, name, *, docstatus=0, **values):
        super().__init__(**values)
        self.doctype = doctype
        self.name = name
        self.docstatus = docstatus
        self.values["name"] = name
        self.values["docstatus"] = docstatus

    def get(self, key, default=None):
        if key == "name":
            return self.name
        if key == "docstatus":
            return self.docstatus
        return super().get(key, default)

    def has_permission(self, permission):
        return self.values.get(f"can_{permission}", True)


class _VirtualReconciliation:
    def __init__(self):
        self.values = {"allocation": [], "payments": [], "invoices": []}
        self.validation_calls = 0
        self.reconcile_calls = 0

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def add_payment_entries(self, rows):
        self.values["payments"] = [_Row(**row) for row in rows]

    def add_invoice_entries(self, rows):
        self.values["invoices"] = [_Row(**row) for row in rows]

    def allocate_entries(self, args):
        payment = args["payments"][0]
        invoice = args["invoices"][0]
        self.values["allocation"] = [
            _Row(
                reference_type=payment.get("reference_type"),
                reference_name=payment.get("reference_name"),
                reference_row=payment.get("reference_row"),
                invoice_type=invoice.get("invoice_type"),
                invoice_number=invoice.get("invoice_number"),
                unreconciled_amount=payment.get("amount"),
                amount=payment.get("amount"),
                allocated_amount=min(
                    float(payment.get("amount")),
                    float(invoice.get("outstanding_amount")),
                ),
                difference_amount=0,
                difference_account=None,
                exchange_rate=1,
                currency=invoice.get("currency"),
                gain_loss_posting_date=None,
            )
        ]

    def validate_allocation(self):
        self.validation_calls += 1

    def reconcile_allocations(self):
        self.reconcile_calls += 1


class CustomerPaymentReconciliationServiceTests(unittest.TestCase):
    def setUp(self):
        self.previous_approval_mode = approvals._approval_mode
        self.backend = install_fake_backend(approvals)
        approvals.configure_approval_mode(ApprovalMode.AGENT_DELEGATED)

        self.payment = _Doc(
            "Payment Entry",
            "ACC-PAY-0001",
            docstatus=1,
            party_type="Customer",
            party="CUST-0001",
            company="Test Company",
            payment_type="Receive",
            paid_from="Debtors - TC",
            paid_from_account_currency="INR",
            source_exchange_rate=1,
            posting_date="2026-09-17",
            unallocated_amount=100,
            book_advance_payments_in_separate_party_account=False,
            references=[],
            modified="2026-09-17 10:00:00",
        )
        self.invoice = _Doc(
            "Sales Invoice",
            "ACC-SINV-0001",
            docstatus=1,
            customer="CUST-0001",
            company="Test Company",
            debit_to="Debtors - TC",
            currency="INR",
            conversion_rate=1,
            outstanding_amount=1,
            payment_terms_template=None,
            is_return=False,
            return_against=None,
            modified="2026-09-17 10:00:00",
        )
        self.source_row = {
            "reference_type": "Payment Entry",
            "reference_name": "ACC-PAY-0001",
            "amount": 100,
            "currency": "INR",
            "exchange_rate": 1,
            "book_advance_payments_in_separate_party_account": False,
        }
        self.invoice_row = {
            "invoice_type": "Sales Invoice",
            "invoice_number": "ACC-SINV-0001",
            "invoice_amount": 100,
            "outstanding_amount": 75,
            "currency": "INR",
            "posting_date": "2026-09-17",
            "account": "Debtors - TC",
        }
        self.reconciliations = []
        self.fake_frappe = SimpleNamespace(
            session=SimpleNamespace(user="accounts@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            get_doc=lambda doctype, name: {
                ("Payment Entry", "ACC-PAY-0001"): self.payment,
                ("Sales Invoice", "ACC-SINV-0001"): self.invoice,
            }[(doctype, name)],
            has_permission=lambda *_args, **_kwargs: True,
            get_single_value=lambda *_args, **_kwargs: False,
            get_system_settings=lambda *_args, **_kwargs: None,
            get_cached_value=lambda *_args, **_kwargs: None,
            DoesNotExistError=frappe.DoesNotExistError,
            PermissionError=frappe.PermissionError,
            ValidationError=frappe.ValidationError,
            db=SimpleNamespace(
                get_value=lambda *_args, **_kwargs: None,
                rollback=Mock(),
                commit=Mock(),
            ),
            throw=lambda message, error: (_ for _ in ()).throw(error(message)),
        )
        self.frappe_patch = patch.object(service, "frappe", self.fake_frappe)
        self.frappe_patch.start()
        self.flt_patch = patch.object(
            service,
            "flt",
            side_effect=lambda value, precision=None: round(float(value or 0), precision or 2),
        )
        self.flt_patch.start()

        self.common_patches = [
            patch.object(service, "_effective_receivable", return_value="Debtors - TC"),
            patch.object(
                service,
                "_party_accounts",
                return_value=("Debtors - TC", "Customer Advances - TC", None),
            ),
            patch.object(service, "_link_permissions", return_value=None),
            patch.object(service, "_term_allocation_enabled", return_value=False),
            patch.object(
                service,
                "_regional_state",
                return_value={
                    "region": None,
                    "discovery_override": None,
                    "allocation_override": None,
                },
            ),
            patch.object(service, "_effective_reconciliation_date", return_value=None),
            patch.object(service, "_exchange_warning", return_value=None),
            patch.object(service, "_cached_company_value", return_value=None),
            patch.object(
                service,
                "_native_discovery",
                return_value=([self.source_row], [self.invoice_row], None),
            ),
            patch.object(service, "_native_post_state", return_value=(25, 50)),
        ]
        for item in self.common_patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.common_patches):
            item.stop()
        self.flt_patch.stop()
        self.frappe_patch.stop()
        approvals.configure_approval_mode(self.previous_approval_mode)
        self.backend.clear()

    def _new_reconciliation(self):
        reconciliation = _VirtualReconciliation()
        self.reconciliations.append(reconciliation)
        return reconciliation

    def test_prepare_supports_unallocated_source_without_mutation_or_commit(self):
        with patch.object(service, "_new_reconciliation", side_effect=self._new_reconciliation):
            result = service.prepare_customer_payment_reconciliation(
                {
                    "payment_entry": "ACC-PAY-0001",
                    "sales_invoice": "ACC-SINV-0001",
                    "amount": 25,
                }
            )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["preview"]["source_kind"], "unallocated")
        self.assertEqual(result["preview"]["allocation_currency"], "INR")
        self.assertEqual(self.reconciliations[0].reconcile_calls, 0)
        self.fake_frappe.db.commit.assert_not_called()
        self.fake_frappe.db.rollback.assert_not_called()

    def test_confirm_reconstructs_and_calls_only_native_reconciliation(self):
        with patch.object(service, "_new_reconciliation", side_effect=self._new_reconciliation):
            prepared = service.prepare_customer_payment_reconciliation(
                {
                    "payment_entry": "ACC-PAY-0001",
                    "sales_invoice": "ACC-SINV-0001",
                    "amount": 25,
                }
            )
            result = service.confirm_customer_payment_reconciliation(
                prepared["approval_token"], True
            )

        self.assertEqual(result["status"], "reconciled")
        self.assertEqual(result["applied_amount"], 25)
        self.assertEqual(len(self.reconciliations), 2)
        self.assertEqual(self.reconciliations[1].validation_calls, 1)
        self.assertEqual(self.reconciliations[1].reconcile_calls, 1)
        self.fake_frappe.db.commit.assert_not_called()

    def test_sales_order_advance_source_is_selected_without_choosing_reference_locally(self):
        reference = _Doc(
            "Payment Entry Reference",
            "PE-REF-0001",
            reference_doctype="Sales Order",
            reference_name="SAL-ORD-0001",
            allocated_amount=100,
        )
        self.payment.values["references"] = [reference]
        source = dict(self.source_row)
        source.update(
            {"reference_row": "PE-REF-0001", "against_order": "SAL-ORD-0001"}
        )
        self.common_patches[8].stop()
        self.common_patches[8] = patch.object(
            service,
            "_native_discovery",
            return_value=([source], [self.invoice_row], None),
        )
        self.common_patches[8].start()

        with patch.object(service, "_new_reconciliation", side_effect=self._new_reconciliation):
            result = service.prepare_customer_payment_reconciliation(
                {
                    "payment_entry": "ACC-PAY-0001",
                    "sales_invoice": "ACC-SINV-0001",
                    "amount": 25,
                }
            )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["preview"]["source_kind"], "sales_order_advance")
        self.assertEqual(result["preview"]["source_sales_order"], "SAL-ORD-0001")

    def test_ambiguous_source_fails_closed(self):
        self.common_patches[8].stop()
        self.common_patches[8] = patch.object(
            service,
            "_native_discovery",
            return_value=([self.source_row, dict(self.source_row)], [self.invoice_row], None),
        )
        self.common_patches[8].start()

        with patch.object(service, "_new_reconciliation", side_effect=self._new_reconciliation):
            result = service.prepare_customer_payment_reconciliation(
                {
                    "payment_entry": "ACC-PAY-0001",
                    "sales_invoice": "ACC-SINV-0001",
                    "amount": 25,
                }
            )
        self.assertEqual(result["code"], "AMBIGUOUS_PAYMENT_SOURCE")
        self.assertTrue(self.backend.is_empty())

    def test_confirm_rejects_material_source_drift_before_native_call(self):
        changed = dict(self.source_row)
        changed["amount"] = 50
        self.common_patches[8].stop()
        self.common_patches[8] = patch.object(
            service,
            "_native_discovery",
            side_effect=(
                ([self.source_row], [self.invoice_row], None),
                ([changed], [self.invoice_row], None),
            ),
        )
        self.common_patches[8].start()

        with patch.object(service, "_new_reconciliation", side_effect=self._new_reconciliation):
            prepared = service.prepare_customer_payment_reconciliation(
                {
                    "payment_entry": "ACC-PAY-0001",
                    "sales_invoice": "ACC-SINV-0001",
                    "amount": 25,
                }
            )
            result = service.confirm_customer_payment_reconciliation(
                prepared["approval_token"], True
            )

        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        self.assertEqual(self.reconciliations[1].reconcile_calls, 0)

    def test_payment_terms_are_rejected_before_approval(self):
        self.common_patches[3].stop()
        self.common_patches[3] = patch.object(
            service, "_term_allocation_enabled", return_value=True
        )
        self.common_patches[3].start()

        result = service.prepare_customer_payment_reconciliation(
            {
                "payment_entry": "ACC-PAY-0001",
                "sales_invoice": "ACC-SINV-0001",
                "amount": 25,
            }
        )
        self.assertEqual(result["code"], "PAYMENT_TERMS_UNSUPPORTED")
        self.assertTrue(self.backend.is_empty())

    def test_payment_reconciliation_permission_is_required(self):
        self.frappe_patch.stop()
        self.fake_frappe.has_permission = (
            lambda doctype, *_args, **_kwargs: doctype != "Payment Reconciliation"
        )
        self.frappe_patch.start()

        result = service.prepare_customer_payment_reconciliation(
            {
                "payment_entry": "ACC-PAY-0001",
                "sales_invoice": "ACC-SINV-0001",
                "amount": 25,
            }
        )
        self.assertEqual(result["code"], "PERMISSION_DENIED")


if __name__ == "__main__":
    unittest.main()
