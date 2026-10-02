from __future__ import annotations

import unittest
from unittest.mock import patch
from types import SimpleNamespace
import sys

import frappe
from pydantic import ValidationError

from mcp_erpnext.approvals import approvals
from mcp_erpnext.contracts.buying.purchase_receipt import (
    PurchaseReceiptLineInput,
    PurchaseReceiptPrepareInput,
)
from mcp_erpnext.services.buying import purchase_order_to_purchase_receipt as service
from mcp_erpnext.tests.test_purchase_order_to_purchase_receipt import (
    PurchaseOrderToPurchaseReceiptTests,
    Row,
)


class Task78ConversionMatrixTests(PurchaseOrderToPurchaseReceiptTests):
    def _line(self, **overrides):
        line = {
            "purchase_order_item": "PO-ITEM-001",
            "accepted_qty": 3.0,
            "rejected_qty": 0.0,
            "warehouse": "Stores - TC",
        }
        line.update(overrides)
        return line

    def _prepare(self, line=None, *, native=None):
        with patch.object(service, "_native", return_value=native or self.target), patch.object(
            service, "_warehouse", side_effect=lambda name, company: (name, None)
        ):
            return service.prepare_purchase_order_to_purchase_receipt(
                "PO-001", [line or self._line()]
            )

    def test_partial_split_and_exact_selected_row_are_preserved(self):
        result = self._prepare(self._line(accepted_qty=2, rejected_qty=1, rejected_warehouse="Reject - TC"))
        self.assertEqual(result["status"], "ready")
        item = result["preview"]["purchase_receipt"]["items"][0]
        self.assertEqual(item["purchase_order_item"], "PO-ITEM-001")
        self.assertEqual(item["received_qty"], 3.0)

    def test_repeated_item_codes_use_exact_child_row_names(self):
        second_source = Row("PO-ITEM-002", item_code="ITEM-001", item_name="Known", qty=4, received_qty=0, conversion_factor=1, delivered_by_supplier=0)
        second_target = Row("PRE-ITEM-002", item_code="ITEM-001", item_name="Known", purchase_order_item="PO-ITEM-002", purchase_order="PO-001", qty=4, rejected_qty=0, received_qty=4, warehouse="Stores - TC")
        self.source.items.append(second_source)
        self.target.items.append(second_target)
        lines = [self._line(purchase_order_item="PO-ITEM-001"), self._line(purchase_order_item="PO-ITEM-002", accepted_qty=1)]
        with patch.object(service, "_native", return_value=self.target) as native, patch.object(service, "_warehouse", side_effect=lambda name, company: (name, None)):
            result = service.prepare_purchase_order_to_purchase_receipt("PO-001", lines)
        self.assertEqual(result["status"], "ready")
        native.assert_called_once_with("PO-001", ["PO-ITEM-001", "PO-ITEM-002"])

    def test_quantity_and_row_shape_guards(self):
        self.assertEqual(self._prepare(self._line(accepted_qty=6))["code"], "QUANTITY_EXCEEDS_REMAINING")
        self.assertEqual(self._prepare(self._line(purchase_order_item="OTHER-ROW"))["code"], "INVALID_SOURCE_ROW")
        self.target.items = []
        self.assertEqual(self._prepare()["code"], "NO_MAPPABLE_ITEMS")
        with self.assertRaises(ValidationError):
            PurchaseReceiptPrepareInput(lines=[PurchaseReceiptLineInput(**self._line()), PurchaseReceiptLineInput(**self._line())], purchase_order="PO-001")

    def test_drop_ship_and_zero_quantity_rows_are_bounded(self):
        self.source.items[0].values["delivered_by_supplier"] = 1
        self.assertEqual(self._prepare()["code"], "UNSUPPORTED_SOURCE_ROW")
        self.source.items[0].values["delivered_by_supplier"] = 0
        self.source.items[0].values["qty"] = 0
        self.assertEqual(self._prepare()["code"], "UNSUPPORTED_SOURCE_ROW")

    def test_source_states_and_permissions_fail_before_mapping(self):
        for status in ("Draft", "Cancelled", "Closed", "On Hold"):
            self.source.docstatus = 0 if status == "Draft" else 1
            self.source.values["status"] = status
            result = service.prepare_purchase_order_to_purchase_receipt("PO-001", [self._line()])
            self.assertIn(result["code"], {"SOURCE_NOT_READY", "SOURCE_NOT_ELIGIBLE"})
        self.source.docstatus = 1
        self.source.values["status"] = "To Receive"
        self.source.values["can_read"] = False
        self.assertEqual(service.prepare_purchase_order_to_purchase_receipt("PO-001", [self._line()])["code"], "PERMISSION_DENIED")
        self.source.values["can_read"] = True
        self.fake_frappe.has_permission = lambda doctype, permission: False
        self.assertEqual(service.prepare_purchase_order_to_purchase_receipt("PO-001", [self._line()])["code"], "PERMISSION_DENIED")

    def test_warehouse_requirements_and_invalid_native_choices(self):
        self.target.items[0].values["warehouse"] = None
        self.assertEqual(self._prepare(self._line(warehouse=None))["code"], "WAREHOUSE_REQUIRED")
        self.target.items[0].values["warehouse"] = "Stores - TC"
        with patch.object(service, "_warehouse", return_value=(None, None)):
            self.assertEqual(service._apply(self.source, self.target, [self._line(rejected_qty=1, rejected_warehouse=None)], None, None)["code"], "REJECTED_WAREHOUSE_REQUIRED")
        with patch.object(service, "_warehouse", return_value=(None, {"status": "error", "code": "INVALID_WAREHOUSE"})):
            self.assertEqual(service._apply(self.source, self.target, [self._line()], None, None)["code"], "INVALID_WAREHOUSE")
        with self.assertRaises(ValidationError):
            PurchaseReceiptLineInput(**self._line(rejected_warehouse="Stores - TC"))

    def test_native_disabled_and_company_warehouse_rules_are_bounded(self):
        with patch.dict(sys.modules, {"erpnext.stock.utils": SimpleNamespace(validate_disabled_warehouse=lambda name: (_ for _ in ()).throw(Exception("disabled")), validate_warehouse_company=lambda name, company: None, is_group_warehouse=lambda name: None)}):
            self.assertEqual(service._warehouse("Stores - TC", "Test Company")[1]["code"], "INVALID_WAREHOUSE")
        with patch.dict(sys.modules, {"erpnext.stock.utils": SimpleNamespace(validate_disabled_warehouse=lambda name: None, validate_warehouse_company=lambda name, company: (_ for _ in ()).throw(Exception("company")), is_group_warehouse=lambda name: None)}):
            self.assertEqual(service._warehouse("Stores - TC", "Test Company")[1]["code"], "INVALID_WAREHOUSE")

    def test_item_master_prerequisite_indicators(self):
        self.fake_frappe.get_cached_value = lambda *args, **kwargs: {
            "inspection_required_before_purchase": True,
            "has_serial_no": True,
            "has_batch_no": True,
            "is_fixed_asset": True,
            "is_stock_item": True,
        }
        result = self._prepare()
        requirements = result["preview"]["purchase_receipt"]["items"][0]["requirements"]
        self.assertEqual(requirements, {"quality_inspection": True, "serial_no": True, "batch_no": True, "fixed_asset": True, "rejected_warehouse": False})

    def test_prepare_has_no_insert_and_confirm_false_cancels(self):
        prepared = self._prepare()
        self.assertEqual(self.target.insert_calls, [])
        result = service.confirm_purchase_order_to_purchase_receipt(prepared["approval_token"], False)
        self.assertEqual(result["code"], "CONFIRMATION_REQUIRED")
        self.assertEqual(service.confirm_purchase_order_to_purchase_receipt(prepared["approval_token"], True)["code"], "CONFIRMATION_CONSUMED")

    def test_approval_binding_one_shot_stale_and_fresh_remap(self):
        prepared = self._prepare()
        token = prepared["approval_token"]
        self.fake_frappe.session.user = "other@example.com"
        self.assertEqual(service.confirm_purchase_order_to_purchase_receipt(token, True)["code"], "CONFIRMATION_UNAVAILABLE")
        self.fake_frappe.session.user = "purchase@example.com"
        approvals.record_trusted_user_approval(token, action=service._ACTION, site="test.localhost", user="purchase@example.com")
        self.source.items[0].values["received_qty"] = 1
        with patch.object(service, "_native", return_value=self.target) as native, patch.object(service, "_warehouse", side_effect=lambda name, company: (name, None)):
            result = service.confirm_purchase_order_to_purchase_receipt(token, True)
        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        native.assert_called_once()

    def test_native_validation_is_bounded_and_confirm_rejects_non_draft(self):
        with patch.object(service, "_native", side_effect=frappe.ValidationError):
            result = service.prepare_purchase_order_to_purchase_receipt("PO-001", [self._line()])
        self.assertEqual(result["code"], "NATIVE_VALIDATION_FAILED")
        self.target.docstatus = 1
        self.assertEqual(self._prepare()["code"], "CONVERSION_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
