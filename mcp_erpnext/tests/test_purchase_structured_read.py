from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.contracts.audit import audit_tool_contracts
from mcp_erpnext.contracts.buying.purchase_order_read import (
    GetPurchaseOrderInput,
    PurchaseOrderAggregateInput,
    PurchaseOrderItemQueryInput,
    PurchaseOrderQueryInput,
)
from mcp_erpnext.contracts.masters.item_read import ItemAggregateInput, ItemQueryInput
from mcp_erpnext.contracts.masters.supplier_read import (
    SupplierAggregateInput,
    SupplierGetInput,
    SupplierQueryInput,
)
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.services.buying import purchase_order_read as purchase_orders
from mcp_erpnext.services.masters import item_read, supplier_read
from mcp_erpnext.settings import MCPProfile, MCPSettings
from mcp_erpnext.tools.buying import purchase_order_read as purchase_order_tools


class FakeDoc:
    def __init__(self, values, readable=True):
        self.values = values
        self.readable = readable
        self.name = values.get("name")

    def get(self, key, default=None):
        return self.values.get(key, default)

    def has_permission(self, permission):
        return permission == "read" and self.readable


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def run(self, *, as_dict):
        return self.rows


class PurchaseStructuredReadTests(unittest.TestCase):
    def test_contracts_reject_unbounded_and_unapproved_values(self):
        invalid_payloads = (
            (PurchaseOrderQueryInput, {"transaction_date_from": "2026-02-02", "transaction_date_to": "2026-02-01"}),
            (PurchaseOrderQueryInput, {"fields": ["supplier_bank_account"]}),
            (PurchaseOrderQueryInput, {"sort_by": "grand_total desc; delete"}),
            (PurchaseOrderQueryInput, {"limit": 101}),
            (SupplierQueryInput, {"sort_by": "tax_id"}),
            (SupplierQueryInput, {"tax_id": "sensitive"}),
            (SupplierGetInput, {"supplier": "SUP-1", "fields": ["bank_account_no"]}),
            (SupplierAggregateInput, {"group_by": "owner"}),
            (PurchaseOrderAggregateInput, {"metrics": ["count"], "min_grand_total": 2, "max_grand_total": 1}),
            (PurchaseOrderItemQueryInput, {"metrics": ["sum_qty"], "group_by": "warehouse"}),
            (PurchaseOrderItemQueryInput, {"limit": 101}),
        )
        for model, payload in invalid_payloads:
            with self.subTest(model=model.__name__, payload=payload), self.assertRaises(ValidationError):
                model.model_validate(payload)

    def test_supplier_exact_get_projects_allowlisted_fields_and_checks_permission(self):
        doc = FakeDoc({"name": "SUP-1", "supplier_name": "Acme", "country": "India", "bank_account_no": "private"})
        fake = SimpleNamespace(get_doc=lambda *_: doc, DoesNotExistError=frappe.DoesNotExistError)
        with patch.object(supplier_read, "frappe", fake):
            result = supplier_read.get_supplier("SUP-1", ["name", "supplier_name"])
            self.assertEqual(result, {"status": "ok", "document": {"name": "SUP-1", "supplier_name": "Acme"}})
            doc.readable = False
            self.assertEqual(supplier_read.get_supplier("SUP-1", ["name"])["code"], "PERMISSION_DENIED")

    def test_supplier_query_is_bounded_permission_aware_and_can_inspect_disabled(self):
        calls = []
        fake = SimpleNamespace(get_list=lambda *args, **kwargs: calls.append((args, kwargs)) or [{"name": "SUP-2", "disabled": 1}])
        with patch.object(supplier_read, "frappe", fake):
            result = supplier_read.query_suppliers(SupplierQueryInput(disabled=True, limit=7, offset=14, fields=["name", "disabled"]).model_dump())
        self.assertEqual(result["suppliers"], [{"name": "SUP-2", "disabled": 1}])
        kwargs = calls[0][1]
        self.assertEqual(kwargs["filters"], [["disabled", "=", 1]])
        self.assertEqual(kwargs["limit_page_length"], 7)
        self.assertEqual(kwargs["limit_start"], 14)
        self.assertFalse(kwargs["ignore_permissions"])

    def test_supplier_aggregate_counts_disabled_groups_server_side(self):
        calls = []
        rows = [{"disabled": 0, "count": 3}, {"disabled": 1, "count": 1}]
        fake = SimpleNamespace(get_list=lambda *args, **kwargs: calls.append((args, kwargs)) or rows)
        with patch.object(supplier_read, "frappe", fake):
            result = supplier_read.aggregate_suppliers(SupplierAggregateInput(group_by="disabled").model_dump())
        self.assertEqual(result["results"], [{"count": 3, "group_value": 0}, {"count": 1, "group_value": 1}])
        self.assertEqual(calls[0][1]["group_by"], "disabled")
        self.assertFalse(calls[0][1]["ignore_permissions"])

    def test_purchase_item_exact_get_allows_only_active_purchase_items(self):
        for values, expected in (
            ({"name": "ITEM-1", "disabled": 0, "is_purchase_item": 1}, "ok"),
            ({"name": "ITEM-1", "disabled": 0, "is_purchase_item": 0}, "not_found"),
            ({"name": "ITEM-1", "disabled": 1, "is_purchase_item": 1}, "not_found"),
        ):
            fake = SimpleNamespace(get_doc=lambda *_: FakeDoc(values), DoesNotExistError=frappe.DoesNotExistError)
            with patch.object(item_read, "frappe", fake):
                self.assertEqual(item_read.get_item("ITEM-1", ["name"], purchase_only=True)["status"], expected)
        denied = FakeDoc({"name": "ITEM-1", "disabled": 0, "is_purchase_item": 1}, readable=False)
        with patch.object(item_read, "frappe", SimpleNamespace(get_doc=lambda *_: denied, DoesNotExistError=frappe.DoesNotExistError)):
            self.assertEqual(item_read.get_item("ITEM-1", ["name"], purchase_only=True)["code"], "PERMISSION_DENIED")

    def test_purchase_item_query_and_aggregate_always_apply_eligibility(self):
        calls = []
        rows = [{"name": "ITEM-1", "item_group": "Goods", "count": 1}]
        fake = SimpleNamespace(get_list=lambda *args, **kwargs: calls.append((args, kwargs)) or rows)
        with patch.object(item_read, "frappe", fake):
            item_read.query_items(ItemQueryInput(disabled=True, fields=["name"]).model_dump(), purchase_only=True)
            item_read.aggregate_items(ItemAggregateInput(group_by="item_group").model_dump(), purchase_only=True)
        for _, kwargs in calls:
            self.assertIn(["disabled", "!=", 1], kwargs["filters"])
            self.assertIn(["is_purchase_item", "=", 1], kwargs["filters"])
            self.assertFalse(kwargs["ignore_permissions"])
        self.assertIn(["disabled", "=", 1], calls[0][1]["filters"])

    def test_all_item_read_retains_broad_shared_item_visibility(self):
        all_settings = replace(MCPSettings.from_environment(), profile=MCPProfile.ALL)
        names = [tool.name for tool in asyncio.run(create_mcp(all_settings).list_tools())]
        # The shared Item service defaults to no domain eligibility restriction.
        calls = []
        fake = SimpleNamespace(get_list=lambda *args, **kwargs: calls.append(kwargs) or [{"name": "SALES-ONLY", "is_sales_item": 1}])
        with patch.object(item_read, "frappe", fake):
            result = item_read.query_items(ItemQueryInput(fields=["name", "is_sales_item"]).model_dump())
        self.assertIn("get_item", names)
        self.assertEqual(result["items"], [{"name": "SALES-ONLY", "is_sales_item": 1}])
        self.assertEqual(calls[0]["filters"], [])

    def test_purchase_order_exact_get_projects_header_and_items_and_checks_permission(self):
        doc = FakeDoc({"name": "PO-1", "supplier": "SUP-1", "status": "To Receive", "grand_total": 25, "private": "hidden", "items": [{"item_code": "ITEM-1", "qty": 2, "amount": 25, "private": "hidden"}]})
        fake = SimpleNamespace(get_doc=lambda *_: doc, DoesNotExistError=frappe.DoesNotExistError)
        with patch.object(purchase_orders, "frappe", fake):
            result = purchase_orders.get_purchase_order("PO-1", ["name", "supplier"], True, ["item_code", "qty"])
            self.assertEqual(result, {"status": "ok", "document": {"name": "PO-1", "supplier": "SUP-1"}, "items": [{"item_code": "ITEM-1", "qty": 2}]})
            doc.readable = False
            self.assertEqual(purchase_orders.get_purchase_order("PO-1", ["name"], False, ["item_code"])["code"], "PERMISSION_DENIED")

    def test_purchase_order_query_uses_child_filter_stable_sort_pagination_and_permissions(self):
        calls = []
        fake = SimpleNamespace(get_list=lambda *args, **kwargs: calls.append((args, kwargs)) or [{"name": "PO-1", "supplier": "SUP-1"}])
        criteria = PurchaseOrderQueryInput(supplier="SUP-1", item_code="ITEM-1", fields=["name", "supplier"], limit=8, offset=16, sort_by="grand_total", sort_order="asc").model_dump()
        with patch.object(purchase_orders, "frappe", fake):
            result = purchase_orders.query_purchase_orders(criteria)
        self.assertEqual(result["purchase_orders"], [{"name": "PO-1", "supplier": "SUP-1"}])
        kwargs = calls[0][1]
        self.assertIn(["Purchase Order Item", "item_code", "=", "ITEM-1"], kwargs["filters"])
        self.assertTrue(kwargs["distinct"])
        self.assertEqual(kwargs["order_by"], "grand_total asc, name asc")
        self.assertEqual((kwargs["limit_start"], kwargs["limit_page_length"]), (16, 8))
        self.assertFalse(kwargs["ignore_permissions"])

    def test_purchase_order_aggregate_keeps_each_currency_separate(self):
        calls = []
        rows = [{"currency": "INR", "supplier": "SUP-1", "sum_grand_total": 100}, {"currency": "USD", "supplier": "SUP-1", "sum_grand_total": 20}]
        fake = SimpleNamespace(get_list=lambda *args, **kwargs: calls.append((args, kwargs)) or rows)
        criteria = PurchaseOrderAggregateInput(metrics=["sum_grand_total"], group_by="supplier").model_dump()
        with patch.object(purchase_orders, "frappe", fake):
            result = purchase_orders.aggregate_purchase_orders(criteria)
        self.assertEqual(result["results"], [{"sum_grand_total": 100, "group_value": "SUP-1", "currency": "INR"}, {"sum_grand_total": 20, "group_value": "SUP-1", "currency": "USD"}])
        self.assertEqual(calls[0][1]["group_by"], "currency, supplier")
        self.assertFalse(calls[0][1]["ignore_permissions"])

    def test_purchase_order_item_query_filters_and_item_aggregates(self):
        query_calls, aggregate_calls = [], []
        fake = SimpleNamespace(
            get_list=lambda *args, **kwargs: aggregate_calls.append((args, kwargs)) or [{"group_value": "ITEM-1", "currency": "INR", "sum_amount": 40}],
            qb=SimpleNamespace(get_query=lambda *args, **kwargs: query_calls.append((args, kwargs)) or FakeQuery([{"purchase_order": "PO-1", "item_code": "ITEM-1", "qty": 2}])),
        )
        criteria = PurchaseOrderItemQueryInput(supplier="SUP-1", item_code="ITEM-1", purchase_order="PO-1", purchase_order_status="To Receive", min_qty=1, fields=["purchase_order", "item_code", "qty"], metrics=["sum_amount"], group_by="item_code").model_dump()
        with patch.object(purchase_orders, "frappe", fake):
            result = purchase_orders.query_purchase_order_items(criteria)
        self.assertEqual(result["items"], [{"purchase_order": "PO-1", "item_code": "ITEM-1", "qty": 2}])
        self.assertEqual(result["aggregates"], [{"group_value": "ITEM-1", "currency": "INR", "sum_amount": 40}])
        filters = query_calls[0][1]["filters"]
        for expected in (["supplier", "=", "SUP-1"], ["name", "=", "PO-1"], ["status", "=", "To Receive"], ["Purchase Order Item", "item_code", "=", "ITEM-1"], ["Purchase Order Item", "qty", ">=", 1]):
            self.assertIn(expected, filters)
        self.assertFalse(query_calls[0][1]["ignore_permissions"])
        self.assertEqual(aggregate_calls[0][1]["group_by"], "currency, `tabPurchase Order Item`.item_code")

    def test_legacy_get_purchase_order_request_and_typed_request_both_work(self):
        legacy_response = {"status": "ok", "document": {"doctype": "Purchase Order", "name": "PO-1", "docstatus": 0, "status": "Draft", "party": "SUP-1", "items": [{"item_code": "ITEM-1", "qty": 1}]}}
        ctx = object()
        with patch.object(purchase_order_tools, "execute_tool_with_context", side_effect=lambda _ctx, _name, callback, **_kwargs: callback()), patch.object(purchase_order_tools.legacy_read, "get_document", return_value=legacy_response) as legacy_get:
            result = purchase_order_tools.get_purchase_order(ctx=ctx, request={"target": {"doctype": "Purchase Order", "name": "PO-1"}})
        self.assertEqual(result.root.document.doctype, "Purchase Order")
        self.assertEqual(result.root.document.items[0].item_code, "ITEM-1")
        self.assertEqual(legacy_get.call_args.args[1], "purchase")

        typed_response = {"status": "ok", "document": {"name": "PO-2", "supplier": "SUP-2"}}
        with patch.object(purchase_order_tools, "execute_tool_with_context", side_effect=lambda _ctx, _name, callback, **_kwargs: callback()), patch.object(purchase_order_tools.service, "get_purchase_order", return_value=typed_response) as typed_get:
            result = purchase_order_tools.get_purchase_order(ctx=ctx, purchase_order="PO-2", fields=["name", "supplier"])
        self.assertEqual(result.root.document.supplier, "SUP-2")
        self.assertEqual(typed_get.call_args.args, ("PO-2", ["name", "supplier"], False, ["item_code", "item_name", "qty", "rate", "amount"]))

    def test_legacy_get_purchase_order_contract_rejects_wrong_doctype_or_mixed_targets(self):
        with self.assertRaises(ValidationError):
            GetPurchaseOrderInput.model_validate({"request": {"target": {"doctype": "Sales Order", "name": "SO-1"}}})
        with self.assertRaises(ValidationError):
            GetPurchaseOrderInput.model_validate({"request": {"target": {"doctype": "Purchase Order", "name": "PO-1"}}, "purchase_order": "PO-2"})

    def test_purchase_and_all_inventories_are_audited_and_legacy_input_is_public(self):
        purchase_settings = replace(MCPSettings.from_environment(), profile=MCPProfile.PURCHASE)
        tools = {tool.name: tool for tool in asyncio.run(create_mcp(purchase_settings).list_tools())}
        self.assertIn("request", tools["get_purchase_order"].inputSchema["properties"])
        self.assertIn("purchase_order", tools["get_purchase_order"].inputSchema["properties"])
        self.assertIn("PurchaseOrderLegacyDocument", str(tools["get_purchase_order"].outputSchema))
        self.assertEqual(audit_tool_contracts(list(tools.values())), [])
        all_settings = replace(MCPSettings.from_environment(), profile=MCPProfile.ALL)
        all_tools = asyncio.run(create_mcp(all_settings).list_tools())
        all_names = [tool.name for tool in all_tools]
        self.assertEqual(len(all_names), len(set(all_names)))
        self.assertEqual(audit_tool_contracts(all_tools), [])


if __name__ == "__main__":
    unittest.main()
