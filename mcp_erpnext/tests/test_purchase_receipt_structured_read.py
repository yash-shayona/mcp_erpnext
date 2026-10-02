from __future__ import annotations

import unittest
from unittest.mock import Mock, patch
from pydantic import ValidationError
from mcp_erpnext import remote_operations
from mcp_erpnext.contracts.buying.purchase_receipt_read import ReceiptQueryInput, ReceiptAggregateInput, ReceiptItemQueryInput
from mcp_erpnext.services.buying import purchase_receipt_read as service


class StructuredReceiptTests(unittest.TestCase):
    def test_bounded_contracts(self):
        for payload in ({"fields": ["valuation_rate"]}, {"limit": 101}, {"sort_by": "valuation_rate"}, {"posting_date_from": "2026-09-30", "posting_date_to": "2026-09-29"}, {"min_grand_total": 9, "max_grand_total": 8}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ReceiptQueryInput.model_validate(payload)
        with self.assertRaises(ValidationError):
            ReceiptItemQueryInput(fields=["serial_and_batch_bundle"])
        with self.assertRaises(ValidationError):
            ReceiptItemQueryInput(min_received_qty=2, max_received_qty=1)
        with self.assertRaises(ValidationError):
            ReceiptAggregateInput(metrics=["sum_valuation_rate"])

    def test_header_permission_distinct_and_sort(self):
        with patch.object(service.frappe, "get_list", return_value=[{"name": "PR-1"}]) as get_list:
            result = service.query_purchase_receipts(ReceiptQueryInput(item_code="I-1", purchase_order="PO-1").model_dump())
        self.assertEqual(result["purchase_receipts"], [{"name": "PR-1"}])
        kwargs = get_list.call_args.kwargs
        self.assertFalse(kwargs["ignore_permissions"])
        self.assertTrue(kwargs["distinct"])
        self.assertIn("name desc", kwargs["order_by"])
        self.assertIn(["Purchase Receipt Item", "purchase_order", "=", "PO-1"], kwargs["filters"])

    def test_header_currency_aggregate(self):
        with patch.object(service.frappe, "get_list", return_value=[{"currency": "USD", "sum_grand_total": 20, "status": "Completed"}]) as get_list:
            result = service.aggregate_purchase_receipts(ReceiptAggregateInput(metrics=["sum_grand_total"], group_by="status").model_dump())
        self.assertEqual(result["results"][0]["currency"], "USD")
        self.assertIn("currency", get_list.call_args.kwargs["group_by"])
        self.assertFalse(get_list.call_args.kwargs["ignore_permissions"])

    def test_item_lineage_permission_and_sort(self):
        query = Mock()
        query.run.return_value = [{"name": "PRI-1", "purchase_receipt": "PR-1", "purchase_order": "PO-1", "purchase_order_item": "POI-1", "qty": 2, "rejected_qty": 1, "received_qty": 3}]
        with patch.object(service, "frappe") as fake_frappe:
            fake_frappe.qb.get_query.return_value = query
            result = service.query_purchase_receipt_items(ReceiptItemQueryInput(purchase_receipt="PR-1").model_dump())
        self.assertEqual(result["items"][0]["purchase_order_item"], "POI-1")
        self.assertEqual(result["items"][0]["received_qty"], 3)
        self.assertFalse(fake_frappe.qb.get_query.call_args.kwargs["ignore_permissions"])
        self.assertIn("items.name", fake_frappe.qb.get_query.call_args.kwargs["order_by"])

    def test_item_currency_aggregate(self):
        with patch.object(service.frappe, "get_list", return_value=[{"currency": "INR", "sum_amount": 25}]) as get_list:
            result = service.query_purchase_receipt_items(ReceiptItemQueryInput(metrics=["sum_amount"]).model_dump())
        self.assertEqual(result["aggregates"], [{"currency": "INR", "sum_amount": 25}])
        self.assertIn("currency", get_list.call_args.kwargs["group_by"])
        self.assertFalse(get_list.call_args.kwargs["ignore_permissions"])

    def test_fixed_rest_routes(self):
        for operation, module, args in (
            ("query_purchase_receipts", remote_operations.purchase_receipt_read, {}),
            ("aggregate_purchase_receipts", remote_operations.purchase_receipt_read, {"metrics": ["count"]}),
            ("query_purchase_receipt_items", remote_operations.purchase_receipt_read, {}),
            ("query_purchase_orders", remote_operations.purchase_order_read, {}),
            ("aggregate_purchase_orders", remote_operations.purchase_order_read, {"metrics": ["count"]}),
            ("query_purchase_order_items", remote_operations.purchase_order_read, {}),
        ):
            with self.subTest(operation=operation), patch.object(module, operation, return_value={"status": "ok"}) as call:
                self.assertEqual(remote_operations.execute_remote_operation(operation, "purchase", args), {"status": "ok"})
                call.assert_called_once()
            with self.assertRaises(remote_operations.RemoteOperationError):
                remote_operations.execute_remote_operation(operation, "purchase", {**args, "arbitrary": True})
            with self.assertRaises(remote_operations.RemoteOperationError):
                remote_operations.execute_remote_operation(operation, "sales", args)

    def test_purchase_order_typed_and_legacy_exact(self):
        with patch.object(remote_operations.purchase_order_read, "get_purchase_order", return_value={"status": "ok"}) as typed:
            remote_operations.execute_remote_operation("get_purchase_order", "purchase", {"purchase_order": "PO-1"})
            typed.assert_called_once()
        legacy_request = {"request": {"target": {"doctype": "Purchase Order", "name": "PO-1"}}}
        with patch.object(remote_operations.read, "get_document", return_value={"status": "ok"}) as legacy:
            remote_operations.execute_remote_operation("get_purchase_order", "purchase", legacy_request)
            legacy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
