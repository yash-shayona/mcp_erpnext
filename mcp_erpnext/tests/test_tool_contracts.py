from __future__ import annotations

import asyncio
import unittest
from datetime import date
from json import dumps
from typing import Any
from unittest.mock import patch

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from mcp_erpnext.contracts.audit import audit_tool_contracts
from mcp_erpnext.contracts.common import CustomerReference
from mcp_erpnext.contracts.registry import (
	SideEffectClass,
	ToolContract,
	ToolOperation,
	get_tool_contract,
)
from mcp_erpnext.contracts.selling.quotation import QuotationPrepareInput
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.tools.selling import quotation as quotation_tools


class ToolContractTests(unittest.TestCase):
	def registered_tools(self):
		return asyncio.run(create_mcp().list_tools())

	def test_registered_inventory_passes_the_contract_audit(self):
		self.assertEqual(audit_tool_contracts(self.registered_tools()), [])

	def test_quotation_public_schema_has_resolved_nested_references(self):
		tool = next(tool for tool in self.registered_tools() if tool.name == "prepare_quotation")
		schema = tool.inputSchema
		customer = schema["$defs"]["CustomerReference"]
		item = schema["$defs"]["ItemReference"]
		row = schema["$defs"]["QuotationItemInput"]
		self.assertEqual(schema["required"], ["customer", "items", "valid_till"])
		self.assertEqual(customer["properties"]["doctype"]["const"], "Customer")
		self.assertEqual(customer["required"], ["doctype", "name"])
		self.assertEqual(item["properties"]["doctype"]["const"], "Item")
		self.assertEqual(item["required"], ["doctype", "name"])
		self.assertEqual(row["properties"]["qty"]["exclusiveMinimum"], 0)
		self.assertEqual(schema["properties"]["valid_till"]["format"], "date")
		self.assertNotIn("item_code", schema["properties"])
		self.assertNotIn("quantity", row["properties"])
		self.assertNotIn("ctx", schema["properties"])

	def test_quotation_output_schema_models_every_prepare_state(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		tool = tools["prepare_quotation"]
		mapping = tool.outputSchema["discriminator"]["mapping"]
		self.assertEqual(set(mapping), {"ready", "needs_input", "permission_denied", "error"})
		self.assertEqual(tool.meta["mcp_erpnext"]["side_effect"], "PREPARE")
		for name in ("prepare_quotation", "confirm_quotation"):
			with self.subTest(name=name):
				self.assertEqual(tools[name].outputSchema["type"], "object")

	def test_sales_order_to_sales_invoice_contract_is_typed_and_bounded(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		prepare = tools["prepare_sales_order_to_sales_invoice"]
		confirm = tools["confirm_sales_order_to_sales_invoice"]
		self.assertEqual(prepare.inputSchema["required"], ["sales_order"])
		self.assertEqual(confirm.inputSchema["required"], ["approval_token", "confirm"])
		self.assertEqual(prepare.meta["mcp_erpnext"]["side_effect"], "PREPARE")
		self.assertEqual(confirm.meta["mcp_erpnext"]["side_effect"], "CONFIRM_WRITE")
		self.assertEqual(
			get_tool_contract("prepare_sales_order_to_sales_invoice").approval_confirm_tool,
			"confirm_sales_order_to_sales_invoice",
		)
		self.assertNotIn("extra_fields", dumps(prepare.inputSchema))
		self.assertNotIn("ignore_permissions", dumps(prepare.inputSchema))

	def test_standalone_sales_invoice_contract_is_typed_and_bounded(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		prepare = tools["prepare_sales_invoice"]
		confirm = tools["confirm_sales_invoice"]
		self.assertEqual(prepare.inputSchema["required"], ["customer", "items"])
		self.assertEqual(confirm.inputSchema["required"], ["approval_token", "confirm"])
		self.assertEqual(prepare.meta["mcp_erpnext"]["side_effect"], "PREPARE")
		self.assertEqual(confirm.meta["mcp_erpnext"]["side_effect"], "CONFIRM_WRITE")
		self.assertEqual(
			get_tool_contract("prepare_sales_invoice").approval_confirm_tool,
			"confirm_sales_invoice",
		)
		self.assertNotIn("extra_fields", dumps(prepare.inputSchema))
		self.assertNotIn("update_stock", dumps(prepare.inputSchema))
		self.assertNotIn("sales_order", dumps(prepare.inputSchema))

	def test_delivery_note_to_sales_invoice_contract_is_typed_and_bounded(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		prepare = tools["prepare_delivery_note_to_sales_invoice"]
		confirm = tools["confirm_delivery_note_to_sales_invoice"]
		self.assertEqual(prepare.inputSchema["required"], ["delivery_note"])
		self.assertEqual(confirm.inputSchema["required"], ["approval_token", "confirm"])
		self.assertEqual(prepare.meta["mcp_erpnext"]["side_effect"], "PREPARE")
		self.assertEqual(confirm.meta["mcp_erpnext"]["side_effect"], "CONFIRM_WRITE")
		self.assertEqual(get_tool_contract("prepare_delivery_note_to_sales_invoice").approval_confirm_tool, "confirm_delivery_note_to_sales_invoice")
		self.assertNotIn("update_stock", dumps(prepare.inputSchema))
		self.assertNotIn("args", dumps(prepare.inputSchema))

	def test_sales_invoice_read_schemas_are_typed_and_accounting_aware(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		for name in ("get_sales_invoice", "query_sales_invoices", "aggregate_sales_invoices"):
			with self.subTest(name=name):
				self.assertEqual(tools[name].inputSchema["type"], "object")
				self.assertEqual(tools[name].outputSchema["type"], "object")
				self.assertEqual(tools[name].meta["mcp_erpnext"]["side_effect"], "READ")
		self.assertIn("outstanding_amount", dumps(tools["get_sales_invoice"].inputSchema))
		self.assertIn("sum_outstanding_amount", dumps(tools["aggregate_sales_invoices"].inputSchema))
		self.assertNotIn("search_sales_invoices", tools)

	def test_public_schemas_do_not_expose_server_approval_policy_internals(self):
		schemas = dumps(
			[
				{"input": tool.inputSchema, "output": tool.outputSchema}
				for tool in self.registered_tools()
			]
		)
		for internal in ("MCP_APPROVAL_MODE", "approval_mode", "trusted_at", "record_trusted_user_approval"):
			with self.subTest(internal=internal):
				self.assertNotIn(internal, schemas)

	def test_resolver_schemas_expose_terminal_states_and_explicit_selection(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		for name in ("search_customers", "resolve_customer", "search_items", "resolve_item"):
			with self.subTest(name=name):
				self.assertEqual(tools[name].outputSchema["type"], "object")
				self.assertEqual(
					set(tools[name].outputSchema["discriminator"]["mapping"]),
					{"resolved", "ambiguous", "not_found", "error"},
				)
				self.assertEqual(
					tools[name].meta["mcp_erpnext"]["resolution_states"],
					["resolved", "ambiguous", "not_found", "error"],
				)
		selection = tools["select_resolved_candidate"]
		self.assertEqual(selection.outputSchema["type"], "object")
		self.assertEqual(selection.inputSchema["properties"]["doctype"]["enum"], ["Customer", "Item"])
		self.assertEqual(selection.inputSchema["required"], ["doctype", "name"])
		self.assertEqual(
			set(selection.outputSchema["discriminator"]["mapping"]),
			{"resolved", "not_found", "error"},
		)

	def test_item_read_schemas_are_typed_permission_safe_and_sales_only(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		for name in ("get_item", "query_items", "aggregate_items"):
			with self.subTest(name=name):
				self.assertEqual(tools[name].inputSchema["type"], "object")
				self.assertEqual(tools[name].outputSchema["type"], "object")
				self.assertEqual(tools[name].meta["mcp_erpnext"]["side_effect"], "READ")
		self.assertIn("item_name", tools["query_items"].inputSchema["properties"])
		self.assertNotIn("standard_rate", dumps(tools["query_items"].inputSchema))

	def test_sales_order_query_contract_is_typed_and_preserves_allowlists(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		query = tools["query_sales_orders"]
		self.assertEqual(query.inputSchema["type"], "object")
		self.assertEqual(query.outputSchema["type"], "object")
		self.assertEqual(query.meta["mcp_erpnext"]["side_effect"], "READ")
		for field in ("customer", "item_code", "limit", "offset", "sort_by", "fields"):
			self.assertIn(field, query.inputSchema["properties"])
		self.assertNotIn("standard_rate", dumps(query.inputSchema))
		self.assertNotIn("search_sales_orders", tools)

	def test_quotation_read_contract_is_typed_and_bounded(self):
		tools = {tool.name: tool for tool in self.registered_tools()}
		for name in ("get_quotation", "query_quotations", "aggregate_quotations"):
			with self.subTest(name=name):
				self.assertEqual(tools[name].inputSchema["type"], "object")
				self.assertEqual(tools[name].outputSchema["type"], "object")
				self.assertEqual(tools[name].meta["mcp_erpnext"]["side_effect"], "READ")
		self.assertIn("party_name", tools["query_quotations"].inputSchema["properties"])
		self.assertIn("sum_grand_total", dumps(tools["aggregate_quotations"].inputSchema))
		self.assertNotIn("terms", dumps(tools["query_quotations"].inputSchema))
		self.assertNotIn("search_quotations", tools)

	def test_quotation_request_rejects_legacy_or_invalid_reference_shapes(self):
		valid = {
			"customer": {"doctype": "Customer", "name": "CUST-001"},
			"items": [{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": 2}],
			"valid_till": "2026-09-01",
		}
		self.assertEqual(QuotationPrepareInput.model_validate(valid).valid_till, date(2026, 9, 1))
		for invalid in (
			{**valid, "items": [{"item_code": "ITEM-001", "quantity": 2}]},
			{**valid, "customer": {"name": "CUST-001"}},
			{**valid, "customer": {"doctype": "Item", "name": "CUST-001"}},
			{**valid, "customer": {"doctype": "Customer", "name": "   "}},
			{**valid, "items": [{"item": {"doctype": "Customer", "name": "ITEM-001"}, "qty": 2}]},
			{**valid, "items": [{"item": {"doctype": "Item", "name": "ITEM-001"}}]},
			{**valid, "items": [{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": 0}]},
			{**valid, "items": [{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": True}]},
			{
				**valid,
				"customer": {
					"status": "ambiguous",
					"doctype": "Customer",
					"query": "Acme",
					"candidates": [],
				},
			},
		):
			with self.subTest(invalid=invalid):
				with self.assertRaises(ValidationError):
					QuotationPrepareInput.model_validate(invalid)

	def test_quotation_wrapper_converts_the_typed_request_without_business_logic(self):
		service_result = {
			"status": "needs_input",
			"missing": ["company"],
			"message": "No permitted Company is available.",
		}
		with patch.object(quotation_tools, "execute_tool_with_context", side_effect=lambda _ctx, _name, operation, **_kwargs: operation()), patch.object(
			quotation_tools, "_prepare_quotation", return_value=service_result
		) as service:
			result = quotation_tools.prepare_quotation(
				customer=CustomerReference(doctype="Customer", name="CUST-001"),
				items=[QuotationPrepareInput.model_validate({
					"customer": {"doctype": "Customer", "name": "CUST-001"},
					"items": [{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": 2}],
					"valid_till": "2026-09-01",
				}).items[0]],
				valid_till=date(2026, 9, 1),
				ctx=object(),
			)
		self.assertEqual(result.root.status, "needs_input")
		self.assertTrue(result.root.interaction.required)
		self.assertEqual(result.root.interaction.kind, "INPUT")
		self.assertIn("PROVIDE_INPUT", result.root.interaction.allowed_actions)
		self.assertEqual(service.call_args.args[0], {"doctype": "Customer", "name": "CUST-001"})
		self.assertEqual(service.call_args.args[1], [{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": 2.0}])
		self.assertEqual(service.call_args.args[2], "2026-09-01")

	def test_untyped_temporary_tool_fails_the_non_legacy_contract_policy(self):
		mcp = FastMCP("contract-audit-test")

		@mcp.tool(meta={"mcp_erpnext": {"side_effect": "READ"}})
		def temporary_untyped(payload: dict[str, Any]) -> dict[str, Any]:
			"""Temporary test tool with an intentionally invalid public payload."""
			return payload

		contracts = {
			"temporary_untyped": ToolContract(
				"temporary_untyped",
				"Tests",
				ToolOperation.SEARCH,
				SideEffectClass.READ,
				"Temporary test tool.",
				False,
				QuotationPrepareInput,
				QuotationPrepareInput,
			),
		}
		issues = audit_tool_contracts(asyncio.run(mcp.list_tools()), contracts)
		self.assertIn("temporary_untyped: input schema contains an arbitrary object.", issues)

	def test_confirm_write_without_shared_approval_guard_fails_the_contract_policy(self):
		mcp = FastMCP("contract-audit-test")

		@mcp.tool(meta={"mcp_erpnext": {"side_effect": "CONFIRM_WRITE"}})
		def temporary_confirm(approval_token: str) -> str:
			"""Temporary confirm tool with an intentionally missing approval guard."""
			return approval_token

		contracts = {
			"temporary_confirm": ToolContract(
				"temporary_confirm",
				"Tests",
				ToolOperation.CONFIRM,
				SideEffectClass.CONFIRM_WRITE,
				"Temporary confirm tool.",
				True,
				QuotationPrepareInput,
				QuotationPrepareInput,
			),
		}
		issues = audit_tool_contracts(asyncio.run(mcp.list_tools()), contracts)
		self.assertIn("temporary_confirm: CONFIRM_WRITE tool lacks a shared approval guard.", issues)


if __name__ == "__main__":
	unittest.main()
