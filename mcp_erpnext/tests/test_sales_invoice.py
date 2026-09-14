from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import approvals
from mcp_erpnext.tests.approval_test_backend import install_fake_backend
from mcp_erpnext.services.selling import sales_invoice as service


class FakeRow:
    def __init__(self, **values):
        self.values = values

    def get(self, fieldname, default=None):
        return self.values.get(fieldname, default)


class FakeDocument:
    def __init__(self, doctype="Sales Invoice", name="new-Sales-Invoice-1"):
        self.doctype = doctype
        self.name = name
        self.values = {
            "docstatus": 0,
            "items": [],
            "taxes": [],
            "payment_schedule": [],
        }
        self.insert_calls = []
        self.set_missing_values_calls = 0
        self.calculate_calls = 0
        self.so_dn_required_calls = 0
        self.native_prerequisite_error = None

    def __getattr__(self, fieldname):
        if fieldname in self.values:
            return self.values[fieldname]
        raise AttributeError(fieldname)

    def __setattr__(self, fieldname, value):
        if fieldname in {
            "doctype",
            "name",
            "values",
            "insert_calls",
            "set_missing_values_calls",
            "calculate_calls",
            "so_dn_required_calls",
            "native_prerequisite_error",
        }:
            object.__setattr__(self, fieldname, value)
        else:
            self.values[fieldname] = value

    def get(self, fieldname, default=None):
        return self.values.get(fieldname, default)

    def append(self, fieldname, values):
        row = FakeRow(**values)
        self.values.setdefault(fieldname, []).append(row)

    def set_missing_values(self):
        self.set_missing_values_calls += 1
        self.values.update(
            {
                "customer_name": "Acme Customer",
                "posting_date": self.values.get("posting_date", "2026-09-11"),
                "due_date": "2026-10-11",
                "currency": "INR",
                "selling_price_list": self.values.get(
                    "selling_price_list", "Standard Selling"
                ),
                "debit_to": "Debtors - TC",
            }
        )
        detailed_rows = []
        for row in self.values["items"]:
            values = dict(row.values)
            values.update(
                {
                    "item_name": "Known Item",
                    "description": "Known Item",
                    "stock_uom": "Nos",
                    "uom": "Nos",
                    "conversion_factor": 1,
                    "rate": row.get("rate", 100),
                    "amount": row.get("qty", 0) * row.get("rate", 100),
                    "net_rate": row.get("rate", 100),
                    "net_amount": row.get("qty", 0) * row.get("rate", 100),
                    "income_account": "Sales - TC",
                }
            )
            detailed_rows.append(FakeRow(**values))
        self.values["items"] = detailed_rows

    def calculate_taxes_and_totals(self):
        self.calculate_calls += 1
        total = sum(row.get("amount", 0) for row in self.values["items"])
        self.values.update(
            {
                "total_qty": sum(row.get("qty", 0) for row in self.values["items"]),
                "net_total": total,
                "total_taxes_and_charges": 0,
                "grand_total": total,
                "rounded_total": total,
                "outstanding_amount": total,
                "base_net_total": total,
                "base_grand_total": total,
            }
        )

    def so_dn_required(self):
        self.so_dn_required_calls += 1
        if self.native_prerequisite_error:
            raise self.native_prerequisite_error

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        return self


class StandaloneSalesInvoiceServiceTests(unittest.TestCase):
    def setUp(self):
        self.approval_backend = install_fake_backend(approvals)
        self.documents = []
        self.native_prerequisite_error = None

        def new_doc(doctype):
            document = FakeDocument(doctype, f"new-{len(self.documents) + 1}")
            document.native_prerequisite_error = self.native_prerequisite_error
            self.documents.append(document)
            return document

        def get_list(doctype, **kwargs):
            if doctype in {"Company", "Price List", "Address", "Contact"}:
                return [{"name": kwargs["filters"]["name"]}]
            return []

        self.fake_frappe = SimpleNamespace(
            session=SimpleNamespace(user="sales@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            defaults=SimpleNamespace(get_user_default=lambda field: "Test Company"),
            has_permission=lambda *_: True,
            get_list=get_list,
            new_doc=new_doc,
            PermissionError=frappe.PermissionError,
            ValidationError=frappe.ValidationError,
            db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
            throw=lambda message, error: (_ for _ in ()).throw(error(message)),
        )
        self.patches = [patch.object(service, "frappe", self.fake_frappe)]
        for active_patch in self.patches:
            active_patch.start()

        def revalidate(doctype, name, filters, display_fields):
            if doctype == "Customer":
                return {
                    "status": "resolved",
                    "candidate": {
                        "value": name,
                        "customer_name": "Acme Customer",
                    },
                }
            return {
                "status": "resolved",
                "candidate": {
                    "value": name,
                    "item_code": name,
                    "item_name": "Known Item",
                    "stock_uom": "Nos",
                },
            }

        self.resolver_patch = patch.object(
            service, "revalidate_exact_candidate", side_effect=revalidate
        )
        self.resolver_patch.start()

    def tearDown(self):
        self.resolver_patch.stop()
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.approval_backend.clear()

    def request(self, rate=None):
        row = {"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": 2}
        if rate is not None:
            row["rate"] = rate
        return {
            "doctype": "Customer",
            "name": "CUST-001",
        }, [row]

    def approve(self, result):
        approvals.record_trusted_user_approval(
            result["approval_token"],
            action="create_sales_invoice",
            site="test.localhost",
            user="sales@example.com",
        )

    def test_prepare_uses_native_defaults_without_validation_or_insert(self):
        customer, items = self.request(rate=125)
        result = service.prepare_sales_invoice(customer, items)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["preview"]["doctype"], "Sales Invoice")
        self.assertEqual(result["preview"]["docstatus"], 0)
        self.assertEqual(result["preview"]["debit_to"], "Debtors - TC")
        self.assertEqual(result["preview"]["items"][0]["rate"], 125)
        self.assertEqual(self.documents[0].set_missing_values_calls, 1)
        self.assertEqual(self.documents[0].calculate_calls, 1)
        self.assertEqual(self.documents[0].so_dn_required_calls, 1)
        self.assertEqual(self.documents[0].insert_calls, [])

    def test_user_without_sales_invoice_create_permission_is_rejected(self):
        customer, items = self.request()
        with patch.object(self.fake_frappe, "has_permission", return_value=False):
            result = service.prepare_sales_invoice(customer, items)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        self.assertEqual(self.documents, [])

    def test_confirm_rebuilds_and_inserts_only_a_draft_with_normal_flags(self):
        customer, items = self.request()
        prepared = service.prepare_sales_invoice(customer, items)
        self.approve(prepared)

        result = service.confirm_sales_invoice(prepared["approval_token"], True)

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["docstatus"], 0)
        self.assertEqual(len(self.documents), 2)
        inserted = self.documents[1]
        self.assertEqual(
            inserted.insert_calls,
            [
                {
                    "ignore_permissions": False,
                    "ignore_links": False,
                    "ignore_mandatory": False,
                }
            ],
        )
        self.assertEqual(inserted.get("is_pos"), 0)
        self.assertEqual(inserted.get("is_return"), 0)
        self.assertEqual(inserted.get("is_debit_note"), 0)
        self.assertEqual(inserted.get("update_stock"), 0)

    def test_native_prerequisite_failure_blocks_confirmation_without_insert(self):
        customer, items = self.request()
        prepared = service.prepare_sales_invoice(customer, items)
        self.approve(prepared)
        self.native_prerequisite_error = frappe.ValidationError(
            "Sales Order is mandatory for Item ITEM-001"
        )

        result = service.confirm_sales_invoice(prepared["approval_token"], True)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["prerequisites"], ["Sales Order"])
        self.assertEqual(self.documents[0].insert_calls, [])
        self.assertEqual(self.documents[1].so_dn_required_calls, 1)
        self.assertEqual(len(self.documents), 2)

        self.native_prerequisite_error = None
        self.assertEqual(
            service.prepare_sales_invoice(customer, items)["status"], "ready"
        )

    def test_native_sales_order_and_delivery_note_results_are_both_bounded(self):
        for prerequisite, message, code in (
            (
                "Sales Order",
                "Sales Order is mandatory for Item ITEM-001",
                "SALES_ORDER_REQUIRED",
            ),
            (
                "Delivery Note",
                "Delivery Note is mandatory for Item ITEM-001",
                "DELIVERY_NOTE_REQUIRED",
            ),
        ):
            with self.subTest(prerequisite=prerequisite):
                self.native_prerequisite_error = frappe.ValidationError(message)
                customer, items = self.request()

                result = service.prepare_sales_invoice(customer, items)

                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["code"], code)
                self.assertEqual(result["prerequisites"], [prerequisite])
                self.assertNotIn("ITEM-001", result["message"])
                self.approval_backend.clear()

    def test_native_delivery_note_prerequisite_is_mapped_without_leaking_text(self):
        self.native_prerequisite_error = frappe.ValidationError(
            "Delivery Note is mandatory for Item ITEM-001"
        )
        customer, items = self.request()

        result = service.prepare_sales_invoice(customer, items)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["code"], "DELIVERY_NOTE_REQUIRED")
        self.assertEqual(result["prerequisites"], ["Delivery Note"])
        self.assertNotIn("ITEM-001", result["message"])
        self.assertTrue(self.approval_backend.is_empty())

    def test_unknown_native_prerequisite_failure_is_bounded(self):
        self.native_prerequisite_error = frappe.ValidationError("native details")
        customer, items = self.request()

        result = service.prepare_sales_invoice(customer, items)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "NATIVE_VALIDATION_FAILED")
        self.assertNotIn("native details", result["message"])

    def test_invalid_quantity_is_rejected_before_approval(self):
        customer, _ = self.request()
        result = service.prepare_sales_invoice(
            customer,
            [{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": 0}],
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "INVALID_SALES_INVOICE_DETAILS")
        self.assertTrue(self.approval_backend.is_empty())


if __name__ == "__main__":
    unittest.main()
