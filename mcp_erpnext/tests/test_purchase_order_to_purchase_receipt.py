from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import approvals
from mcp_erpnext.services.buying import purchase_order_to_purchase_receipt as service
from mcp_erpnext.tests.approval_test_backend import install_fake_backend


class Row:
    def __init__(self, name: str, **values):
        self.name = name
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)
    def __getattr__(self, key):
        try:
            return self.values[key]
        except KeyError as error:
            raise AttributeError(key) from error

    def __setattr__(self, key, value):
        if key in {"name", "values"}:
            object.__setattr__(self, key, value)
        else:
            self.values[key] = value


class Document:
    def __init__(self, doctype, name, *, docstatus=0, items=None, **values):
        self.doctype = doctype
        self.name = name
        self.docstatus = docstatus
        self.items = items or []
        self.values = values
        self.insert_calls = []

    def get(self, key, default=None):
        if key == "items":
            return self.items
        return self.values.get(key, default)
    def __getattr__(self, key):
        try:
            return self.values[key]
        except KeyError as error:
            raise AttributeError(key) from error

    def has_permission(self, permission):
        return self.values.get(f"can_{permission}", True)

    def run_method(self, _method):
        return None

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        return self


class PurchaseOrderToPurchaseReceiptTests(unittest.TestCase):
    def setUp(self):
        self.create_mode_patch = patch.dict("os.environ", {"MCP_CREATE_MODE": "approval_required"})
        self.create_mode_patch.start()
        self.addCleanup(self.create_mode_patch.stop)
        self.backend = install_fake_backend(approvals)
        self.source = Document(
            "Purchase Order", "PO-001", docstatus=1, status="To Receive", supplier="SUP-001", company="Test Company", per_received=0,
            items=[Row("PO-ITEM-001", item_code="ITEM-001", item_name="Known", qty=5, received_qty=0, conversion_factor=1, delivered_by_supplier=0)],
        )
        self.target = Document(
            "Purchase Receipt", "PRE-001", supplier="SUP-001", company="Test Company", currency="INR", posting_date="2026-09-29", docstatus=0,
            items=[Row("PRE-ITEM-001", item_code="ITEM-001", item_name="Known", purchase_order_item="PO-ITEM-001", purchase_order="PO-001", qty=5, rejected_qty=0, received_qty=5, warehouse="Stores - TC")],
        )
        self.fake_frappe = SimpleNamespace(
            session=SimpleNamespace(user="purchase@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            get_doc=lambda doctype, name: self.source if doctype == "Purchase Order" else self.target,
            has_permission=lambda *_: True,
            get_cached_value=lambda *_args, **_kwargs: {"inspection_required_before_purchase": False, "has_serial_no": False, "has_batch_no": False, "is_fixed_asset": False, "is_stock_item": True},
            DoesNotExistError=frappe.DoesNotExistError,
            PermissionError=frappe.PermissionError,
            ValidationError=frappe.ValidationError,
            db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
            throw=lambda message, error: (_ for _ in ()).throw(error(message)),
        )
        self.frappe_patch = patch.object(service, "frappe", self.fake_frappe)
        self.frappe_patch.start()

    def tearDown(self):
        self.frappe_patch.stop()
        self.backend.clear()

    def test_native_mapper_receives_exact_row_and_confirmation_inserts_draft(self):
        line = {"purchase_order_item": "PO-ITEM-001", "accepted_qty": 3.0, "rejected_qty": 1.0, "warehouse": "Stores - TC", "rejected_warehouse": "Reject - TC"}
        with patch.object(service, "_native", return_value=self.target) as native, patch.object(service, "_warehouse", side_effect=lambda name, company: (name, None)):
            prepared = service.prepare_purchase_order_to_purchase_receipt("PO-001", [line])
        self.assertEqual(prepared["status"], "ready")
        native.assert_called_once_with("PO-001", ["PO-ITEM-001"])
        self.assertEqual(self.target.items[0].get("received_qty"), 4.0)
        approvals.record_trusted_user_approval(prepared["approval_token"], action=service._ACTION, site="test.localhost", user="purchase@example.com")
        with patch.object(service, "_native", return_value=self.target), patch.object(service, "_warehouse", side_effect=lambda name, company: (name, None)):
            result = service.confirm_purchase_order_to_purchase_receipt(prepared["approval_token"], True)
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["docstatus"], 0)
        self.assertEqual(len(self.target.insert_calls), 1)

    def test_direct_preview_and_execute_do_not_use_approval_storage(self):
        line = {"purchase_order_item": "PO-ITEM-001", "accepted_qty": 3.0, "rejected_qty": 1.0, "warehouse": "Stores - TC", "rejected_warehouse": "Reject - TC"}
        with patch.dict("os.environ", {"MCP_CREATE_MODE": "direct"}), patch.object(
            approvals, "create", side_effect=AssertionError("direct create must not use approval storage")
        ), patch.object(approvals, "prune_expired", side_effect=AssertionError("direct create must not prune approvals")), patch.object(
            service, "_native", return_value=self.target
        ), patch.object(service, "_warehouse", side_effect=lambda name, company: (name, None)):
            preview = service.prepare_purchase_order_to_purchase_receipt("PO-001", [line])
            result = service.execute_purchase_order_to_purchase_receipt("PO-001", [line])
        self.assertEqual(preview["status"], "preview")
        self.assertNotIn("approval_token", preview)
        self.assertEqual(result["status"], "created")
        self.assertEqual(len(self.target.insert_calls), 1)


if __name__ == "__main__":
    unittest.main()
