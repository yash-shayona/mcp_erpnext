from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace

from mcp_erpnext.contracts.audit import audit_tool_contracts
from mcp_erpnext.contracts.registry import TOOL_CONTRACTS, ToolRoutingRole
from mcp_erpnext.mcp_server import MCP_ROUTING_INSTRUCTIONS, create_mcp
from mcp_erpnext.settings import MCPProfile, MCPSettings
from mcp_erpnext.tools.registration import tool_registration_kwargs


def _settings(profile: MCPProfile) -> MCPSettings:
    return replace(MCPSettings.from_environment(), profile=profile)


class ToolRoutingTests(unittest.TestCase):
    def _tools_by_profile(self) -> dict[MCPProfile, dict[str, object]]:
        return {
            profile: {
                tool.name: tool
                for tool in asyncio.run(create_mcp(_settings(profile)).list_tools())
            }
            for profile in MCPProfile
        }

    def test_initialized_servers_publish_the_cross_profile_routing_policy(self):
        for profile in MCPProfile:
            with self.subTest(profile=profile):
                self.assertEqual(
                    create_mcp(_settings(profile)).instructions,
                    MCP_ROUTING_INSTRUCTIONS,
                )
        for phrase in (
            "exact known reference",
            "natural-language reference",
            "explicit\nbrowsing/discovery",
            "structured listing/filtering",
            "aggregate questions",
            "`resolved` is terminal",
            "`ambiguous`, use returned candidates",
            "`not_found`, ask for clarification",
            "prepare -> preview/approval -> confirm",
            "Respect the selected profile and domain boundary",
            "RESPONSE PRECISION POLICY",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, MCP_ROUTING_INSTRUCTIONS)

    def test_every_registered_tool_uses_its_contract_governed_description(self):
        tools_by_profile = self._tools_by_profile()
        names = set().union(*(tools.keys() for tools in tools_by_profile.values()))
        self.assertEqual(names, set(TOOL_CONTRACTS))
        for tools in tools_by_profile.values():
            for name, tool in tools.items():
                with self.subTest(name=name):
                    self.assertEqual(tool.description, TOOL_CONTRACTS[name].routing_description())
                    self.assertTrue(tool.description.strip())
                    self.assertEqual(
                        tool.meta["mcp_erpnext"]["routing_role"],
                        TOOL_CONTRACTS[name].governed_routing_role.value,
                    )

    def test_all_governed_roles_are_represented_by_the_public_inventory(self):
        self.assertEqual(
            {contract.governed_routing_role for contract in TOOL_CONTRACTS.values()},
            set(ToolRoutingRole),
        )

    def test_read_discovery_reporting_and_resolver_roles_are_distinct(self):
        descriptions = {
            name: TOOL_CONTRACTS[name].routing_description()
            for name in (
                "get_customer",
                "resolve_customer",
                "search_customers",
                "query_customers",
                "aggregate_customers",
            )
        }
        self.assertIn("exact stable", descriptions["get_customer"])
        self.assertIn("natural-language", descriptions["resolve_customer"])
        self.assertIn("terminal for lookup", descriptions["resolve_customer"])
        self.assertIn("candidate discovery", descriptions["search_customers"])
        self.assertIn("structured filtering", descriptions["query_customers"])
        self.assertIn("server-side count", descriptions["aggregate_customers"])

    def test_resolver_terminal_states_and_selection_apply_to_customer_item_and_supplier(self):
        for name in ("resolve_customer", "resolve_item", "resolve_supplier"):
            description = TOOL_CONTRACTS[name].routing_description()
            with self.subTest(name=name):
                self.assertIn("`resolved` is terminal", description)
                self.assertIn("`ambiguous`, use the returned candidates", description)
                self.assertIn("`not_found`, ask for clarification", description)
        selection = TOOL_CONTRACTS["select_resolved_candidate"].routing_description()
        self.assertIn("`ambiguous` Customer or Item", selection)
        self.assertIn("returned by that result", selection)

    def test_prepare_confirm_and_specialized_workflows_encode_existing_sequence(self):
        for prepare, confirm in (
            ("prepare_quotation", "confirm_quotation"),
            ("prepare_purchase_order", "confirm_purchase_order"),
            ("prepare_sales_invoice_payment", "confirm_sales_invoice_payment"),
        ):
            with self.subTest(prepare=prepare):
                self.assertIn("Review the returned preview/prepared state", TOOL_CONTRACTS[prepare].routing_description())
                self.assertIn("valid prepared operation", TOOL_CONTRACTS[confirm].routing_description())
        self.assertIn("lifecycle action", TOOL_CONTRACTS["prepare_document_submit"].routing_description())
        self.assertIn("source document", TOOL_CONTRACTS["prepare_quotation_to_sales_order"].routing_description())
        self.assertIn("not a generic create tool", TOOL_CONTRACTS["confirm_quotation_to_sales_order"].routing_description())
        self.assertIn("PDF artifact", TOOL_CONTRACTS["render_document_pdf"].routing_description())
        self.assertIn("does not send email", TOOL_CONTRACTS["prepare_document_email"].routing_description())
        self.assertIn("Queue external email", TOOL_CONTRACTS["confirm_document_email"].routing_description())

    def test_governed_registration_replaces_a_local_description(self):
        kwargs = tool_registration_kwargs(
            "resolve_customer", {"description": "ungoverned local text"}
        )
        self.assertEqual(
            kwargs["description"], TOOL_CONTRACTS["resolve_customer"].routing_description()
        )

    def test_contract_audit_rejects_description_drift(self):
        tools = asyncio.run(create_mcp(_settings(MCPProfile.SALES)).list_tools())
        contracts = {
            **TOOL_CONTRACTS,
            "get_customer": replace(
                TOOL_CONTRACTS["get_customer"], purpose="Drifted purpose."
            ),
        }
        self.assertIn(
            "get_customer: public description differs from its governed routing description.",
            audit_tool_contracts(tools, contracts),
        )


if __name__ == "__main__":
    unittest.main()
