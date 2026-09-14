from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import approvals
from mcp_erpnext.contracts.selling.sales_invoice_to_delivery_note import (
    SalesInvoiceToDeliveryNoteInput,
    SalesInvoiceToDeliveryNoteReady,
)
from mcp_erpnext.services.selling import sales_invoice_to_delivery_note as service
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
        self.packed_items = values.pop("packed_items", [])
        self.insert_calls = []
        self.submit_calls = 0

    def get(self, key, default=None):
        if key == "items":
            return self.items
        if key == "packed_items":
            return self.packed_items
        return self.values.get(key, default)

    def has_permission(self, permission):
        return self.values.get(f"can_{permission}", True)

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        if self.values.get("insert_error"):
            raise RuntimeError("native insert failure")
        return self

    def submit(self):
        self.submit_calls += 1


def sales_invoice(**values):
    return Document(
        "Sales Invoice",
        "ACC-SINV-0001",
        docstatus=1,
        status="Unpaid",
        customer="CUST-001",
        customer_name="Acme Customer",
        company="Test Company",
        currency="INR",
        posting_date="2026-09-14",
        update_stock=0,
        is_return=0,
        total_qty=5,
        grand_total=500,
        items=[Row(item_code="ITEM-001", qty=5, delivered_qty=2)],
        **values,
    )


def mapped_delivery_note(qty=3, **values):
    return Document(
        "Delivery Note",
        "MAT-DN-0001",
        docstatus=0,
        customer="CUST-001",
        customer_name="Acme Customer",
        company="Test Company",
        currency="INR",
        posting_date="2026-09-14",
        posting_time="10:00:00",
        total_qty=qty,
        net_total=300,
        total_taxes_and_charges=0,
        grand_total=300,
        items=[
            Row(
                item_code="ITEM-001",
                item_name="Known Item",
                qty=qty,
                uom="Nos",
                conversion_factor=1,
                rate=100,
                amount=300,
                warehouse="Stores - TC",
                against_sales_invoice="ACC-SINV-0001",
                si_detail="SINV-ITEM-0001",
                against_sales_order="SAL-ORD-0001",
                so_detail="SO-ITEM-0001",
            )
        ],
        **values,
    )


class SalesInvoiceToDeliveryNoteTests(unittest.TestCase):
    def setUp(self):
        self.backend = install_fake_backend(approvals)
        self.source = sales_invoice()
        self.create_permission = True
        self.frappe = SimpleNamespace(
            session=SimpleNamespace(user="sales@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            get_doc=self.get_doc,
            has_permission=lambda *_: self.create_permission,
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

    def get_doc(self, doctype, name):
        if name != self.source.name:
            raise frappe.DoesNotExistError(name)
        return self.source

    def approve(self, prepared):
        approvals.record_trusted_user_approval(
            prepared["approval_token"],
            action=service._ACTION,
            site="test.localhost",
            user="sales@example.com",
        )

    def native(self, source_name):
        self.assertEqual(source_name, self.source.name)
        return self.targets.pop(0)

    def prepare(self, *targets):
        self.targets = list(targets)
        with patch.object(service, "_native", side_effect=self.native):
            return service.prepare_sales_invoice_to_delivery_note(self.source.name)

    def test_prepare_returns_bounded_native_preview_without_insert(self):
        target = mapped_delivery_note(qty=3)
        result = self.prepare(target)

        self.assertEqual(result["status"], "ready")
        validated = SalesInvoiceToDeliveryNoteReady.model_validate(result)
        self.assertEqual(validated.preview.source.doctype, "Sales Invoice")
        self.assertEqual(validated.preview.delivery_note.target_doctype, "Delivery Note")
        self.assertEqual(validated.preview.delivery_note.items[0].qty, 3)
        self.assertEqual(target.insert_calls, [])

    def test_prepare_preserves_native_invoice_and_sales_order_links(self):
        result = self.prepare(mapped_delivery_note())
        row = result["preview"]["delivery_note"]["items"][0]
        self.assertEqual(row["against_sales_invoice"], "ACC-SINV-0001")
        self.assertEqual(row["si_detail"], "SINV-ITEM-0001")
        self.assertEqual(row["against_sales_order"], "SAL-ORD-0001")
        self.assertEqual(row["so_detail"], "SO-ITEM-0001")

    def test_confirm_inserts_exactly_one_draft_with_normal_flags_and_no_submit(self):
        prepared_target = mapped_delivery_note()
        confirmed_target = mapped_delivery_note()
        prepared = self.prepare(prepared_target, confirmed_target)
        self.approve(prepared)
        with patch.object(service, "_native", side_effect=self.native):
            result = service.confirm_sales_invoice_to_delivery_note(
                prepared["approval_token"], True
            )

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["docstatus"], 0)
        self.assertEqual(len(prepared_target.insert_calls), 0)
        self.assertEqual(len(confirmed_target.insert_calls), 1)
        self.assertEqual(
            confirmed_target.insert_calls[0],
            {"ignore_permissions": False, "ignore_links": False, "ignore_mandatory": False},
        )
        self.assertEqual(confirmed_target.submit_calls, 0)

    def test_no_mappable_items_is_bounded_and_does_not_insert(self):
        target = mapped_delivery_note()
        target.items = []
        result = self.prepare(target)
        self.assertEqual(result["code"], "NO_MAPPABLE_ITEMS")
        self.assertEqual(target.insert_calls, [])

    def test_draft_source_is_rejected(self):
        self.source.docstatus = 0
        result = service.prepare_sales_invoice_to_delivery_note(self.source.name)
        self.assertEqual(result["code"], "SOURCE_NOT_READY")

    def test_missing_source_is_bounded(self):
        result = service.prepare_sales_invoice_to_delivery_note("missing")
        self.assertEqual(result["code"], "SOURCE_NOT_FOUND")

    def test_source_read_permission_is_bounded(self):
        self.source.values["can_read"] = False
        result = service.prepare_sales_invoice_to_delivery_note(self.source.name)
        self.assertEqual(result["code"], "PERMISSION_DENIED")

    def test_delivery_note_create_permission_is_checked_before_mapper(self):
        self.create_permission = False
        with patch.object(service, "_native") as native:
            result = service.prepare_sales_invoice_to_delivery_note(self.source.name)
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        native.assert_not_called()

    def test_return_invoice_is_not_eligible(self):
        self.source.values["is_return"] = 1
        result = service.prepare_sales_invoice_to_delivery_note(self.source.name)
        self.assertEqual(result["code"], "SOURCE_NOT_ELIGIBLE")

    def test_update_stock_invoice_is_not_eligible(self):
        self.source.values["update_stock"] = 1
        result = service.prepare_sales_invoice_to_delivery_note(self.source.name)
        self.assertEqual(result["code"], "SOURCE_NOT_ELIGIBLE")

    def test_confirm_false_cancels_and_creates_nothing(self):
        target = mapped_delivery_note()
        prepared = self.prepare(target)
        result = service.confirm_sales_invoice_to_delivery_note(
            prepared["approval_token"], False
        )
        self.assertEqual(result["code"], "CONFIRMATION_REQUIRED")
        self.assertEqual(target.insert_calls, [])
        self.assertEqual(
            service.confirm_sales_invoice_to_delivery_note(
                prepared["approval_token"], True
            )["code"],
            "CONFIRMATION_CONSUMED",
        )

    def test_changed_native_mapping_is_stale_and_does_not_insert(self):
        prepared_target = mapped_delivery_note(qty=3)
        changed_target = mapped_delivery_note(qty=2)
        prepared = self.prepare(prepared_target, changed_target)
        self.approve(prepared)
        with patch.object(service, "_native", side_effect=self.native):
            result = service.confirm_sales_invoice_to_delivery_note(
                prepared["approval_token"], True
            )
        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        self.assertEqual(changed_target.insert_calls, [])

    def test_consumed_approval_cannot_be_replayed(self):
        first = mapped_delivery_note()
        second = mapped_delivery_note()
        prepared = self.prepare(first, second)
        self.approve(prepared)
        with patch.object(service, "_native", side_effect=self.native):
            result = service.confirm_sales_invoice_to_delivery_note(
                prepared["approval_token"], True
            )
        self.assertEqual(result["status"], "created")
        replay = service.confirm_sales_invoice_to_delivery_note(
            prepared["approval_token"], True
        )
        self.assertEqual(replay["status"], "error")
        self.assertEqual(len(second.insert_calls), 1)

    def test_native_validation_failure_is_bounded(self):
        with patch.object(service, "_native", side_effect=frappe.ValidationError("internal")):
            result = service.prepare_sales_invoice_to_delivery_note(self.source.name)
        self.assertEqual(result["code"], "NATIVE_VALIDATION_FAILED")
        self.assertNotIn("internal", result["message"])

    def test_insert_failure_rolls_back_and_is_bounded(self):
        rollback = []
        self.frappe.db.rollback = lambda: rollback.append(True)
        prepared_target = mapped_delivery_note()
        failing_target = mapped_delivery_note(insert_error=True)
        prepared = self.prepare(prepared_target, failing_target)
        self.approve(prepared)
        with patch.object(service, "_native", side_effect=self.native):
            result = service.confirm_sales_invoice_to_delivery_note(
                prepared["approval_token"], True
            )
        self.assertEqual(result["code"], "CONVERSION_FAILED")
        self.assertEqual(rollback, [True])

    def test_public_input_forbids_mapper_and_business_fields(self):
        with self.assertRaises(Exception):
            SalesInvoiceToDeliveryNoteInput(
                sales_invoice=self.source.name, items=[], target_doc=None
            )


if __name__ == "__main__":
    unittest.main()
