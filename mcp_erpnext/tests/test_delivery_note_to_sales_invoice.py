from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import approvals
from mcp_erpnext.contracts.selling.delivery_note_to_sales_invoice import (
    DeliveryNoteToSalesInvoiceInput,
    DeliveryNoteToSalesInvoiceReady,
)
from mcp_erpnext.services.selling import delivery_note_to_sales_invoice as service
from mcp_erpnext.tests.approval_test_backend import install_fake_backend


class Row:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class Document:
    def __init__(self, doctype, name, *, docstatus=0, items=None, **values):
        self.doctype = doctype
        self.name = name
        self.docstatus = docstatus
        self.items = items or []
        self.values = values
        self.taxes = values.pop("taxes", [])
        self.payment_schedule = values.pop("payment_schedule", [])
        self.insert_calls = []

    def get(self, key, default=None):
        if key == "items":
            return self.items
        if key == "taxes":
            return self.taxes
        if key == "payment_schedule":
            return self.payment_schedule
        return self.values.get(key, default)

    def has_permission(self, permission):
        return self.values.get(f"can_{permission}", True)

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        return self


def delivery_note():
    return Document(
        "Delivery Note", "MAT-DN-0001", docstatus=1, status="To Bill",
        customer="CUST-001", customer_name="Acme", company="Test Company", currency="INR",
        posting_date="2026-09-14", total_qty=3, net_total=500, grand_total=590,
        items=[Row(name="DN-ITEM-1", item_code="ITEM-1", qty=1, rate=100), Row(name="DN-ITEM-2", item_code="ITEM-2", qty=2, rate=200)],
    )


def mapped_invoice():
    return Document(
        "Sales Invoice", "ACC-SINV-0001", docstatus=0, customer="CUST-001",
        company="Test Company", currency="INR", posting_date="2026-09-14",
        due_date="2026-10-14", net_total=500, total_taxes_and_charges=90,
        grand_total=590, total_qty=3,
        items=[
            Row(item_code="ITEM-1", item_name="One", qty=1, uom="Nos", rate=100, amount=100, delivery_note="MAT-DN-0001", dn_detail="DN-ITEM-1", sales_order="SO-1", so_detail="SO-ITEM-1"),
            Row(item_code="ITEM-2", item_name="Two", qty=2, uom="Nos", rate=200, amount=400, delivery_note="MAT-DN-0001", dn_detail="DN-ITEM-2"),
        ],
    )


class DeliveryNoteConversionTests(unittest.TestCase):
    def setUp(self):
        self.backend = install_fake_backend(approvals)
        self.source = delivery_note()
        self.target = mapped_invoice()
        self.frappe = SimpleNamespace(
            session=SimpleNamespace(user="sales@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            get_doc=lambda doctype, name: self.source if name == self.source.name else (_ for _ in ()).throw(frappe.DoesNotExistError(name)),
            has_permission=lambda *_: True,
            DoesNotExistError=frappe.DoesNotExistError,
            PermissionError=frappe.PermissionError,
            ValidationError=frappe.ValidationError,
            db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
            throw=lambda message, error: (_ for _ in ()).throw(error(message)),
        )
        self.patch = patch.object(service, "frappe", self.frappe)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.backend.clear()

    def native(self, source_name, *, target_doc=None, args=None):
        self.assertEqual(source_name, self.source.name)
        self.assertIsNone(target_doc)
        self.assertIsNone(args)
        return self.target

    def test_prepare_preserves_native_rates_lineage_and_stock_boundary(self):
        with patch.object(service, "_native", side_effect=self.native):
            result = service.prepare_delivery_note_to_sales_invoice(self.source.name)
        self.assertEqual(result["status"], "ready")
        validated = DeliveryNoteToSalesInvoiceReady.model_validate(result)
        self.assertEqual(validated.preview.source.doctype, "Delivery Note")
        self.assertEqual(validated.preview.source.name, self.source.name)
        self.assertEqual(validated.preview.source.docstatus, 1)
        self.assertEqual(validated.preview.sales_invoice.target_doctype, "Sales Invoice")
        rows = result["preview"]["sales_invoice"]["items"]
        self.assertEqual([(row["rate"], row["dn_detail"]) for row in rows], [(100, "DN-ITEM-1"), (200, "DN-ITEM-2")])
        self.assertNotIn("update_stock", result["preview"])
        self.assertNotIn("update_stock", self.target.values)

    def test_confirm_claims_once_and_inserts_only_a_draft(self):
        with patch.object(service, "_native", side_effect=self.native):
            prepared = service.prepare_delivery_note_to_sales_invoice(self.source.name)
        approvals.record_trusted_user_approval(prepared["approval_token"], action=service._ACTION, site="test.localhost", user="sales@example.com")
        with patch.object(service, "_native", side_effect=self.native):
            result = service.confirm_delivery_note_to_sales_invoice(prepared["approval_token"], True)
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["docstatus"], 0)
        self.assertEqual(self.target.insert_calls[0]["ignore_permissions"], False)
        self.assertEqual(len(self.target.insert_calls), 1)

    def test_public_input_forbids_mapper_options(self):
        with self.assertRaises(Exception):
            DeliveryNoteToSalesInvoiceInput(delivery_note=self.source.name, args={})


if __name__ == "__main__":
    unittest.main()
