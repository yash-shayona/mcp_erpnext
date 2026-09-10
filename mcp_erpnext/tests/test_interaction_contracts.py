from __future__ import annotations

import asyncio
import unittest
from datetime import date
from unittest.mock import patch

from mcp_erpnext.contracts.audit import audit_tool_contracts
from mcp_erpnext.contracts.common import CustomerReference
from mcp_erpnext.contracts.interaction import InteractionAction, InteractionKind
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.tools.masters import customer as customer_tools
from mcp_erpnext.tools.masters import item as item_tools
from mcp_erpnext.tools.selling import quotation as quotation_tools


class InteractionContractTests(unittest.TestCase):
	def registered_tools(self):
		return asyncio.run(create_mcp().list_tools())

	def test_registered_interaction_schema_is_shared_and_client_neutral(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		for name in ("resolve_customer", "resolve_item", "prepare_quotation"):
			with self.subTest(name=name):
				schema = tools[name].outputSchema
				directive = schema["$defs"]["InteractionDirective"]
				self.assertEqual(
					set(schema["$defs"]["InteractionKind"]["enum"]),
					{kind.value for kind in InteractionKind},
				)
				self.assertEqual(
					set(schema["$defs"]["InteractionAction"]["enum"]),
					{action.value for action in InteractionAction},
				)
				self.assertTrue(
					{"required", "kind", "allowed_actions", "reason_code", "instructions"}
					<= set(directive["properties"])
				)
				for forbidden in ("librechat", "conversation", "message_id", "button", "component"):
					self.assertNotIn(forbidden, directive["properties"])
		self.assertEqual(audit_tool_contracts(self.registered_tools()), [])

	def test_ambiguous_customer_and_item_require_explicit_selection(self):
		cases = (
			(
				customer_tools,
				customer_tools.resolve_customer,
				{
					"status": "ambiguous",
					"doctype": "Customer",
					"query": "Acme",
					"candidates": [
						{
							"reference": {"doctype": "Customer", "name": "CUST-001"},
							"label": "Acme Private Limited",
							"score": 0.8,
						}
					],
				},
			),
			(
				item_tools,
				item_tools.resolve_item,
				{
					"status": "ambiguous",
					"doctype": "Item",
					"query": "Development item",
					"candidates": [
						{
							"reference": {"doctype": "Item", "name": "SV-FRAPPE-DEVELOPMENT"},
							"label": "Frappe Custom App Development",
							"score": 0.597,
						}
					],
				},
			),
		)
		for module, resolver, service_result in cases:
			with self.subTest(doctype=service_result["doctype"]), patch.object(
				module, "execute_tool_with_context", return_value=service_result
			):
				result = resolver(service_result["query"], object()).root
				self.assertTrue(result.interaction.required)
				self.assertEqual(result.interaction.kind, InteractionKind.SELECTION)
				self.assertIn(InteractionAction.SELECT, result.interaction.allowed_actions)
				self.assertEqual(result.candidates[0].reference.name, service_result["candidates"][0]["reference"]["name"])

	def test_exact_resolution_does_not_request_interaction(self):
		service_result = {
			"status": "resolved",
			"doctype": "Item",
			"reference": {"doctype": "Item", "name": "ITEM-001"},
			"match_type": "exact",
		}
		with patch.object(item_tools, "execute_tool_with_context", return_value=service_result):
			result = item_tools.resolve_item("ITEM-001", object()).root
		self.assertNotIn("interaction", result.model_dump())

	def test_not_found_item_does_not_request_selection_interaction(self):
		service_result = {
			"status": "not_found",
			"doctype": "Item",
			"query": "Web Development Services",
			"candidates": [],
		}
		with patch.object(item_tools, "execute_tool_with_context", return_value=service_result):
			result = item_tools.resolve_item("Web Development Services", object()).root
		self.assertNotIn("interaction", result.model_dump())

	def test_quotation_ready_and_missing_input_use_semantic_directives(self):
		ready = {
			"status": "ready",
			"approval_token": "pending-quotation",
			"expires_in_seconds": 900,
			"preview": {
				"customer": {"doctype": "Customer", "name": "CUST-001"},
				"company": "Test Company",
				"transaction_date": "2026-09-01",
				"valid_till": "2026-09-10",
				"currency": "INR",
				"selling_price_list": "Standard Selling",
				"items": [],
				"taxes": [],
				"net_total": 0,
				"total_taxes_and_charges": 0,
				"additional_discount_percentage": 0,
				"discount_amount": 0,
				"grand_total": 0,
			},
		}
		for service_result, kind, action in (
			(ready, InteractionKind.APPROVAL, InteractionAction.APPROVE),
			({"status": "needs_input", "missing": ["company"]}, InteractionKind.INPUT, InteractionAction.PROVIDE_INPUT),
		):
			with self.subTest(status=service_result["status"]), patch.object(
				quotation_tools, "execute_tool_with_context", return_value=service_result
			):
				result = quotation_tools.prepare_quotation(
					customer=CustomerReference(doctype="Customer", name="CUST-001"),
					items=[],
					valid_till=date(2026, 9, 10),
					ctx=object(),
				).root
				self.assertEqual(result.interaction.kind, kind)
				self.assertIn(action, result.interaction.allowed_actions)


if __name__ == "__main__":
	unittest.main()
