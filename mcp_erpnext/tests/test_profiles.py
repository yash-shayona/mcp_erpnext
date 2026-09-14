from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from mcp_erpnext.contracts.audit import audit_tool_contracts
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.settings import MCPProfile, MCPSettings


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
        return [tool.name for tool in asyncio.run(create_mcp(_settings(profile)).list_tools())]

    def test_sales_profile_preserves_sales_inventory_without_purchase_tools(self):
        names = self._tool_names(MCPProfile.SALES)
        self.assertIn("prepare_quotation", names)
        self.assertIn("prepare_quotation_to_sales_order", names)
        self.assertIn("confirm_quotation_to_sales_order", names)
        self.assertIn("prepare_sales_order_to_sales_invoice", names)
        self.assertIn("confirm_sales_order_to_sales_invoice", names)
        self.assertIn("prepare_sales_invoice", names)
        self.assertIn("confirm_sales_invoice", names)
        self.assertIn("prepare_sales_order_to_delivery_note", names)
        self.assertIn("confirm_sales_order_to_delivery_note", names)
        self.assertIn("prepare_sales_order", names)
        self.assertIn("get_sales_order", names)
        self.assertIn("query_sales_orders", names)
        self.assertIn("aggregate_sales_orders", names)
        self.assertIn("query_sales_order_items", names)
        self.assertNotIn("search_sales_orders", names)
        self.assertIn("get_customer", names)
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
        self.assertNotIn("prepare_purchase_order", names)
        self.assertNotIn("search_suppliers", names)
        self.assertEqual(
            audit_tool_contracts(asyncio.run(create_mcp(_settings(MCPProfile.SALES)).list_tools())), []
        )

    def test_purchase_profile_exposes_only_purchase_inventory(self):
        names = self._tool_names(MCPProfile.PURCHASE)
        self.assertEqual(
            names,
            [
                "search_suppliers",
                "resolve_supplier",
                "search_items",
                "resolve_item",
				"prepare_purchase_order",
				"confirm_purchase_order",
				"prepare_document_update",
				"confirm_document_update",
				"prepare_document_child_add",
				"confirm_document_child_add",
				"prepare_document_submit",
				"confirm_document_submit",
				"prepare_document_cancel",
				"confirm_document_cancel",
				"prepare_document_delete",
				"confirm_document_delete",
				"get_purchase_order",
				"search_purchase_orders",
				"render_document_pdf",
				"prepare_document_email",
				"confirm_document_email",
			],
        )
        self.assertNotIn("prepare_quotation", names)
        self.assertNotIn("prepare_quotation_to_sales_order", names)
        self.assertNotIn("confirm_quotation_to_sales_order", names)
        self.assertNotIn("prepare_sales_order_to_sales_invoice", names)
        self.assertNotIn("confirm_sales_order_to_sales_invoice", names)
        self.assertNotIn("prepare_sales_invoice", names)
        self.assertNotIn("confirm_sales_invoice", names)
        self.assertNotIn("prepare_sales_order", names)
        self.assertNotIn("get_customer", names)
        self.assertNotIn("query_customers", names)
        self.assertNotIn("aggregate_customers", names)
        self.assertNotIn("get_item", names)
        self.assertNotIn("query_items", names)
        self.assertNotIn("aggregate_items", names)
        self.assertEqual(
            audit_tool_contracts(asyncio.run(create_mcp(_settings(MCPProfile.PURCHASE)).list_tools())), []
        )

    def test_unknown_profile_fails_at_configuration_load(self):
        with patch.dict(os.environ, {"MCP_PROFILE": "accounts"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MCP_PROFILE"):
                MCPSettings.from_environment()


if __name__ == "__main__":
    unittest.main()
