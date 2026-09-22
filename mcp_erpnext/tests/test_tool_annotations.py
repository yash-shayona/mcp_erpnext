from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace

from mcp_erpnext.contracts.registry import TOOL_CONTRACTS
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.settings import MCPProfile, MCPSettings


def _settings(profile: MCPProfile) -> MCPSettings:
    return replace(MCPSettings.from_environment(), profile=profile)


class ToolAnnotationTests(unittest.TestCase):
    def _tools_by_profile(self) -> dict[MCPProfile, dict[str, object]]:
        return {
            profile: {
                tool.name: tool
                for tool in asyncio.run(create_mcp(_settings(profile)).list_tools())
            }
            for profile in MCPProfile
        }

    def test_every_profile_tool_publishes_its_contract_annotations(self):
        tools_by_profile = self._tools_by_profile()
        registered_names = set().union(*(tools.keys() for tools in tools_by_profile.values()))
        self.assertEqual(registered_names, set(TOOL_CONTRACTS))

        required_hints = {
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        }
        for tools in tools_by_profile.values():
            for name, tool in tools.items():
                with self.subTest(name=name):
                    self.assertIsNotNone(tool.annotations)
                    self.assertEqual(
                        tool.annotations.model_dump(by_alias=True, exclude_none=True),
                        TOOL_CONTRACTS[name]
                        .mcp_annotations()
                        .model_dump(by_alias=True, exclude_none=True),
                    )
                    self.assertEqual(tool.meta, TOOL_CONTRACTS[name].mcp_meta())
                    self.assertTrue(
                        required_hints.issubset(
                            tool.annotations.model_dump(by_alias=True, exclude_none=True)
                        )
                    )

    def test_read_resolve_prepare_and_confirm_defaults_are_truthful(self):
        tools = {
            name: tool
            for profile_tools in self._tools_by_profile().values()
            for name, tool in profile_tools.items()
        }
        for name in (
            "get_customer",
            "query_customers",
            "aggregate_customers",
            "search_customers",
            "resolve_customer",
            "resolve_item",
            "resolve_supplier",
            "get_sales_order",
            "get_payment_entry",
        ):
            with self.subTest(name=name):
                self.assertTrue(tools[name].annotations.readOnlyHint)
                self.assertTrue(tools[name].annotations.idempotentHint)

        for name in (
            "prepare_quotation",
            "prepare_sales_order",
            "prepare_purchase_order",
            "prepare_document_update",
            "prepare_document_email",
            "prepare_sales_invoice_payment",
            "confirm_quotation",
            "confirm_sales_order",
            "confirm_purchase_order",
            "confirm_customer",
            "confirm_sales_invoice_payment",
        ):
            with self.subTest(name=name):
                self.assertFalse(tools[name].annotations.readOnlyHint)

    def test_explicit_destructive_and_open_world_exceptions(self):
        tools = {
            name: tool
            for profile_tools in self._tools_by_profile().values()
            for name, tool in profile_tools.items()
        }
        for name in (
            "confirm_customer_primary_contact",
            "confirm_contact_update",
            "confirm_document_update",
            "confirm_document_submit",
            "confirm_document_cancel",
            "confirm_document_delete",
            "confirm_customer_payment_reconciliation",
        ):
            with self.subTest(name=name):
                self.assertTrue(tools[name].annotations.destructiveHint)

        self.assertTrue(tools["confirm_document_email"].annotations.openWorldHint)
        self.assertFalse(tools["prepare_document_email"].annotations.openWorldHint)
        self.assertFalse(tools["confirm_sales_order"].annotations.openWorldHint)
        self.assertEqual(
            tools["confirm_document_delete"].meta,
            TOOL_CONTRACTS["confirm_document_delete"].mcp_meta(),
        )
