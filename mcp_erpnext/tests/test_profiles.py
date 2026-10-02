from __future__ import annotations

import asyncio
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from mcp_erpnext.contracts.audit import audit_tool_contracts
from mcp_erpnext.approvals import approvals
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.settings import (
    ApprovalMode,
    LifecycleActionMode,
    MCPProfile,
    MCPSettings,
)


def _settings(profile: MCPProfile) -> MCPSettings:
    return MCPSettings(
        backend="direct",
        frappe_site="test.localhost",
        frappe_user="mcp@example.com",
        erpnext_base_url=None,
        erpnext_api_key=None,
        erpnext_api_secret=None,
        profile=profile,
    )


class ProfileRegistrationTests(unittest.TestCase):
    def _tool_names(self, profile: MCPProfile) -> list[str]:
        return [
            tool.name
            for tool in asyncio.run(create_mcp(_settings(profile)).list_tools())
        ]

    def test_sales_profile_preserves_sales_inventory_without_purchase_tools(self):
        names = self._tool_names(MCPProfile.SALES)
        self.assertIn("prepare_quotation", names)
        self.assertIn("resolve_terms_and_conditions", names)
        self.assertIn("resolve_payment_terms_template", names)
        self.assertIn("prepare_quotation_to_sales_order", names)
        self.assertIn("confirm_quotation_to_sales_order", names)
        self.assertIn("execute_quotation_to_sales_order", names)
        self.assertIn("prepare_sales_order_to_sales_invoice", names)
        self.assertIn("confirm_sales_order_to_sales_invoice", names)
        self.assertIn("execute_sales_order_to_sales_invoice", names)
        self.assertIn("prepare_sales_invoice", names)
        self.assertIn("confirm_sales_invoice", names)
        self.assertIn("prepare_sales_order_to_delivery_note", names)
        self.assertIn("confirm_sales_order_to_delivery_note", names)
        self.assertIn("execute_sales_order_to_delivery_note", names)
        self.assertIn("prepare_sales_invoice_to_delivery_note", names)
        self.assertIn("confirm_sales_invoice_to_delivery_note", names)
        self.assertIn("execute_sales_invoice_to_delivery_note", names)
        self.assertIn("prepare_delivery_note_to_sales_invoice", names)
        self.assertIn("confirm_delivery_note_to_sales_invoice", names)
        self.assertIn("execute_delivery_note_to_sales_invoice", names)
        self.assertIn("prepare_sales_order", names)
        self.assertIn("get_sales_order", names)
        self.assertIn("query_sales_orders", names)
        self.assertIn("aggregate_sales_orders", names)
        self.assertIn("query_sales_order_items", names)
        self.assertNotIn("search_sales_orders", names)
        self.assertIn("get_customer", names)
        self.assertIn("execute_customer", names)
        self.assertIn("execute_contact", names)
        self.assertIn("search_contacts", names)
        self.assertIn("prepare_customer_contact", names)
        self.assertIn("confirm_customer_contact", names)
        self.assertIn("prepare_customer_primary_contact", names)
        self.assertIn("confirm_customer_primary_contact", names)
        self.assertIn("prepare_contact", names)
        self.assertIn("confirm_contact", names)
        self.assertIn("query_customers", names)
        self.assertIn("aggregate_customers", names)
        self.assertIn("get_item", names)
        self.assertIn("query_items", names)
        self.assertIn("aggregate_items", names)
        self.assertIn("get_quotation", names)
        self.assertIn("query_quotations", names)
        self.assertIn("aggregate_quotations", names)
        self.assertNotIn("search_quotations", names)
        self.assertIn("get_sales_invoice", names)
        self.assertIn("query_sales_invoices", names)
        self.assertIn("aggregate_sales_invoices", names)
        self.assertIn("get_delivery_note", names)
        self.assertIn("query_delivery_notes", names)
        self.assertIn("aggregate_delivery_notes", names)
        self.assertNotIn("search_sales_invoices", names)
        self.assertNotIn("query_purchase_receipts", names)
        self.assertNotIn("aggregate_purchase_receipts", names)
        self.assertNotIn("query_purchase_receipt_items", names)
        self.assertNotIn("prepare_purchase_order", names)
        self.assertNotIn("execute_purchase_order", names)
        self.assertNotIn("search_suppliers", names)
        self.assertEqual(
            audit_tool_contracts(
                asyncio.run(create_mcp(_settings(MCPProfile.SALES)).list_tools())
            ),
            [],
        )

    def test_purchase_profile_exposes_only_purchase_inventory(self):
        names = self._tool_names(MCPProfile.PURCHASE)
        self.assertEqual(
            names,
            [
                "search_suppliers",
                "resolve_supplier",
                "get_supplier",
                "query_suppliers",
                "aggregate_suppliers",
                "search_items",
                "resolve_item",
                "get_item",
                "query_items",
                "aggregate_items",
                "get_purchase_order",
                "query_purchase_orders",
                "aggregate_purchase_orders",
                "query_purchase_order_items",
                "prepare_purchase_order",
                "confirm_purchase_order",
                "execute_purchase_order",
                "prepare_purchase_order_to_purchase_receipt",
                "confirm_purchase_order_to_purchase_receipt",
                "execute_purchase_order_to_purchase_receipt",
                "get_purchase_receipt",
                "query_purchase_receipts",
                "aggregate_purchase_receipts",
                "query_purchase_receipt_items",
                "resolve_buying_terms_and_conditions",
                "resolve_payment_terms_template",
                "prepare_document_update",
                "confirm_document_update",
                "execute_document_update",
                "prepare_document_child_add",
                "confirm_document_child_add",
                "execute_document_child_add",
                "prepare_document_child_remove",
                "confirm_document_child_remove",
                "execute_document_child_remove",
                "prepare_document_submit",
                "confirm_document_submit",
                "prepare_document_cancel",
                "confirm_document_cancel",
                "execute_document_cancel",
                "prepare_document_delete",
                "confirm_document_delete",
                "execute_document_delete",
                "search_purchase_orders",
                "render_document_pdf",
                "prepare_document_email",
                "confirm_document_email",
            ],
        )
        self.assertNotIn("prepare_quotation", names)
        self.assertNotIn("resolve_terms_and_conditions", names)
        self.assertIn("resolve_payment_terms_template", names)
        self.assertNotIn("prepare_quotation_to_sales_order", names)
        self.assertNotIn("confirm_quotation_to_sales_order", names)
        self.assertNotIn("execute_quotation_to_sales_order", names)
        self.assertNotIn("prepare_sales_order_to_sales_invoice", names)
        self.assertNotIn("confirm_sales_order_to_sales_invoice", names)
        self.assertNotIn("execute_sales_order_to_sales_invoice", names)
        self.assertNotIn("prepare_sales_invoice_to_delivery_note", names)
        self.assertNotIn("confirm_sales_invoice_to_delivery_note", names)
        self.assertNotIn("execute_sales_invoice_to_delivery_note", names)
        self.assertNotIn("prepare_sales_invoice", names)
        self.assertNotIn("confirm_sales_invoice", names)
        self.assertNotIn("prepare_sales_order", names)
        self.assertNotIn("get_customer", names)
        self.assertNotIn("search_contacts", names)
        self.assertNotIn("prepare_customer_contact", names)
        self.assertNotIn("confirm_customer_contact", names)
        self.assertNotIn("prepare_customer_primary_contact", names)
        self.assertNotIn("confirm_customer_primary_contact", names)
        self.assertNotIn("prepare_contact", names)
        self.assertNotIn("confirm_contact", names)
        self.assertNotIn("query_customers", names)
        self.assertNotIn("aggregate_customers", names)
        self.assertIn("get_item", names)
        self.assertIn("query_items", names)
        self.assertIn("aggregate_items", names)
        self.assertNotIn("get_customer", names)
        self.assertEqual(
            audit_tool_contracts(
                asyncio.run(create_mcp(_settings(MCPProfile.PURCHASE)).list_tools())
            ),
            [],
        )

    def test_all_profile_is_the_deduplicated_existing_inventory_union(self):
        sales = self._tool_names(MCPProfile.SALES)
        purchase = self._tool_names(MCPProfile.PURCHASE)
        accounts = self._tool_names(MCPProfile.ACCOUNTS)
        all_names = self._tool_names(MCPProfile.ALL)
        tea_names = {
            "get_tea_entry",
            "query_tea_entries",
            "aggregate_tea_entries",
            "prepare_tea_entry",
            "confirm_tea_entry",
            "execute_tea_entry",
            "prepare_tea_entry_update",
            "confirm_tea_entry_update",
            "execute_tea_entry_update",
        }
        for profile_names in (sales, purchase, accounts):
            self.assertTrue(tea_names.isdisjoint(profile_names))
        self.assertEqual(
            set(all_names),
            set(sales)
            | set(purchase)
            | set(accounts)
            | {
                "search_customer_service_credentials",
                "get_customer_service_credential",
                "query_customer_service_credentials",
                "aggregate_customer_service_credentials",
                "prepare_customer_service_credential_email",
                "confirm_customer_service_credential_email",
                *tea_names,
            },
        )
        self.assertEqual(len(all_names), len(set(all_names)))
        self.assertEqual(
            audit_tool_contracts(
                asyncio.run(create_mcp(_settings(MCPProfile.ALL)).list_tools())
            ),
            [],
        )

    def test_tea_write_inventory_is_static_across_modes(self):
        inventories = []
        for mode in LifecycleActionMode:
            settings = replace(_settings(MCPProfile.ALL), create_mode=mode, update_mode=mode)
            tools = asyncio.run(create_mcp(settings).list_tools())
            self.assertEqual(audit_tool_contracts(tools), [])
            names = {tool.name for tool in tools}
            self.assertTrue({"prepare_tea_entry", "confirm_tea_entry", "execute_tea_entry"}.issubset(names))
            self.assertTrue({"prepare_tea_entry_update", "confirm_tea_entry_update", "execute_tea_entry_update"}.issubset(names))
            self.assertTrue({"create_tea_entry", "update_tea_entry"}.isdisjoint(names))
            inventories.append(names)
        self.assertTrue(all(names == inventories[0] for names in inventories))

    def test_update_cancel_delete_tools_remain_static_across_policy_modes(self):
        disabled = _settings(MCPProfile.SALES)
        enabled = replace(
            disabled,
            update_mode=LifecycleActionMode.APPROVAL_REQUIRED,
            cancel_mode=LifecycleActionMode.APPROVAL_REQUIRED,
            delete_mode=LifecycleActionMode.APPROVAL_REQUIRED,
        )
        disabled_names = [
            tool.name for tool in asyncio.run(create_mcp(disabled).list_tools())
        ]
        enabled_names = [
            tool.name for tool in asyncio.run(create_mcp(enabled).list_tools())
        ]
        self.assertEqual(disabled_names, enabled_names)
        for name in (
            "prepare_document_update",
            "confirm_document_update",
            "execute_document_update",
            "execute_document_child_add",
            "execute_document_child_remove",
            "prepare_document_cancel",
            "confirm_document_cancel",
            "execute_document_cancel",
            "prepare_document_delete",
            "confirm_document_delete",
            "execute_document_delete",
        ):
            self.assertIn(name, disabled_names)

    def test_create_tools_remain_static_across_policy_modes(self):
        base = _settings(MCPProfile.SALES)
        inventories = [
            [tool.name for tool in asyncio.run(create_mcp(replace(base, create_mode=mode)).list_tools())]
            for mode in (
                LifecycleActionMode.DISABLED,
                LifecycleActionMode.DIRECT,
                LifecycleActionMode.APPROVAL_REQUIRED,
            )
        ]
        self.assertEqual(inventories[0], inventories[1])
        self.assertEqual(inventories[1], inventories[2])
        self.assertIn("execute_customer", inventories[0])
        self.assertIn("execute_item", inventories[0])

    def test_create_mcp_rejects_manual_invalid_lifecycle_mode(self):
        with self.assertRaisesRegex(RuntimeError, "MCP_UPDATE_MODE"):
            create_mcp(replace(_settings(MCPProfile.SALES), update_mode="unsafe"))

    def test_create_mode_defaults_to_disabled_and_normalizes_allowed_values(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(MCPSettings.from_environment().create_mode.value, "disabled")
        with patch.dict(os.environ, {"MCP_CREATE_MODE": "  DiReCt  "}, clear=True):
            self.assertEqual(MCPSettings.from_environment().create_mode.value, "direct")
        with patch.dict(
            os.environ, {"MCP_CREATE_MODE": " APPROVAL_REQUIRED "}, clear=True
        ):
            self.assertEqual(
                MCPSettings.from_environment().create_mode.value, "approval_required"
            )

    def test_create_mode_rejects_unknown_configuration(self):
        with patch.dict(os.environ, {"MCP_CREATE_MODE": "unsafe"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MCP_CREATE_MODE"):
                MCPSettings.from_environment()

    def test_unknown_profile_fails_at_configuration_load(self):
        with patch.dict(os.environ, {"MCP_PROFILE": "unknown"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MCP_PROFILE"):
                MCPSettings.from_environment()

    def test_accounts_profile_is_narrow_and_independent(self):
        previous_approval_mode = approvals._approval_mode
        try:
            names = self._tool_names(MCPProfile.ACCOUNTS)
            self.assertEqual(
                names,
                [
                    "prepare_sales_invoice_payment",
                    "confirm_sales_invoice_payment",
                    "prepare_multi_invoice_customer_receipt",
                    "confirm_multi_invoice_customer_receipt",
                    "prepare_customer_payment_entry",
                    "confirm_customer_payment_entry",
                    "prepare_sales_order_advance_payment",
                    "confirm_sales_order_advance_payment",
                    "prepare_customer_payment_reconciliation",
                    "confirm_customer_payment_reconciliation",
                    "get_payment_entry",
                    "query_payment_entries",
                    "aggregate_payment_entries",
                    "prepare_document_submit",
                    "confirm_document_submit",
                    "prepare_document_cancel",
                    "confirm_document_cancel",
                    "execute_document_cancel",
                    "prepare_document_delete",
                    "confirm_document_delete",
                    "execute_document_delete",
                ],
            )
            self.assertNotIn("prepare_sales_invoice", names)
            self.assertNotIn("resolve_terms_and_conditions", names)
            self.assertNotIn("resolve_payment_terms_template", names)
            self.assertNotIn("search_contacts", names)
            self.assertNotIn("prepare_customer_contact", names)
            self.assertNotIn("confirm_customer_contact", names)
            self.assertNotIn("prepare_customer_primary_contact", names)
            self.assertNotIn("confirm_customer_primary_contact", names)
            self.assertNotIn("prepare_contact", names)
            self.assertNotIn("confirm_contact", names)
            self.assertNotIn("prepare_document_update", names)
            self.assertNotIn("prepare_document_child_add", names)
            self.assertNotIn("prepare_document_child_remove", names)
            self.assertEqual(
                audit_tool_contracts(
                    asyncio.run(create_mcp(_settings(MCPProfile.ACCOUNTS)).list_tools())
                ),
                [],
            )
        finally:
            approvals.configure_approval_mode(previous_approval_mode)


if __name__ == "__main__":
    unittest.main()
