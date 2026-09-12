from __future__ import annotations

import asyncio
import unittest
from json import dumps
from unittest.mock import patch

from mcp_erpnext.contracts.common import CustomerReference
from mcp_erpnext.contracts.masters.customer import CustomerPrepareInput
from mcp_erpnext.contracts.masters.item import ItemPrepareInput
from mcp_erpnext.contracts.registry import (
	FROZEN_LEGACY_TOOL_NAMES,
	TRUSTED_PENDING_OPERATION_GUARD,
	get_tool_contract,
)
from mcp_erpnext.contracts.selling.sales_order import SalesOrderPrepareInput
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.tools.masters import customer as customer_tools
from mcp_erpnext.tools.masters import item as item_tools
from mcp_erpnext.tools.selling import sales_order as sales_order_tools
from pydantic import ValidationError


class CreateContractTests(unittest.TestCase):
	def registered_tools(self):
		return {tool.name: tool for tool in asyncio.run(create_mcp().list_tools())}

	def test_legacy_inventory_is_empty_and_confirm_guards_remain_declared(self):
		self.assertEqual(FROZEN_LEGACY_TOOL_NAMES, frozenset())
		for name in ("confirm_customer", "confirm_item", "confirm_sales_order"):
			with self.subTest(name=name):
				contract = get_tool_contract(name)
				self.assertFalse(contract.legacy)
				self.assertEqual(contract.side_effect.value, "CONFIRM_WRITE")
				self.assertEqual(contract.approval_guard, TRUSTED_PENDING_OPERATION_GUARD)

	def test_six_create_tools_publish_typed_object_schemas(self):
		tools = self.registered_tools()
		for name in (
			"prepare_customer",
			"confirm_customer",
			"prepare_item",
			"confirm_item",
			"prepare_sales_order",
			"confirm_sales_order",
		):
			with self.subTest(name=name):
				self.assertEqual(tools[name].inputSchema["type"], "object")
				self.assertEqual(tools[name].outputSchema["type"], "object")
				self.assertNotIn("ctx", dumps(tools[name].inputSchema))

	def test_creation_inputs_are_bounded_and_reject_legacy_shapes(self):
		with self.assertRaises(ValidationError):
			CustomerPrepareInput.model_validate({"customer_name": "New", "unknown": "x"})
		with self.assertRaises(ValidationError):
			ItemPrepareInput.model_validate({"item_code": "NEW", "standard_rate": 10})
		with self.assertRaises(ValidationError):
			SalesOrderPrepareInput.model_validate(
				{
					"customer": {"doctype": "Customer", "name": "CUST-001"},
					"items": [
						{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": True}
					],
				}
			)

		order = SalesOrderPrepareInput.model_validate(
			{
				"customer": {"doctype": "Customer", "name": "CUST-001"},
				"items": [{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": 2}],
			}
		)
		self.assertNotIn("item_code", order.items[0].model_dump())
		self.assertNotIn("quantity", order.items[0].model_dump())

	def test_customer_wrapper_converts_nested_public_input_and_adds_input_directive(self):
		service_result = {"status": "needs_input", "missing": ["customer.customer_type"]}
		with patch.object(
			customer_tools,
			"execute_tool_with_context",
			side_effect=lambda _ctx, _name, operation: operation(),
		), patch.object(customer_tools, "_prepare_customer", return_value=service_result) as service:
			result = customer_tools.prepare_customer(
				{
					"customer_name": "New Customer",
					"contact": {"email": "new@example.com"},
					"address": {"address_line1": "1 Test Road", "city": "Pune", "country": "India"},
				},
				object(),
			).root

		self.assertEqual(result.interaction.kind, "INPUT")
		self.assertEqual(
			service.call_args.args[0],
			{
				"customer_name": "New Customer",
				"contact": {"email": "new@example.com"},
				"address": {"address_line1": "1 Test Road", "city": "Pune", "country": "India"},
			},
		)

	def test_item_wrapper_keeps_hsn_input_and_does_not_control_sales_policy(self):
		service_result = {"status": "needs_input", "missing": ["item.gst_hsn_code"], "message": "Provide HSN/SAC."}
		with patch.object(
			item_tools,
			"execute_tool_with_context",
			side_effect=lambda _ctx, _name, operation: operation(),
		), patch.object(item_tools, "_prepare_item", return_value=service_result) as service:
			result = item_tools.prepare_item(
				{"item_code": "NEW-ITEM", "gst_hsn_code": "123456"}, object()
			).root

		self.assertEqual(result.interaction.kind, "INPUT")
		self.assertEqual(service.call_args.args[0]["gst_hsn_code"], "123456")
		self.assertNotIn("is_sales_item", service.call_args.args[0])

	def test_sales_order_wrapper_passes_resolved_names_and_adds_approval_or_input(self):
		service_result = {"status": "needs_input", "missing": ["company"], "message": "Choose a Company."}
		with patch.object(
			sales_order_tools,
			"execute_tool_with_context",
			side_effect=lambda _ctx, _name, operation: operation(),
		), patch.object(sales_order_tools, "_prepare_sales_order", return_value=service_result) as service:
			result = sales_order_tools.prepare_sales_order(
				CustomerReference(doctype="Customer", name="CUST-001"),
				[{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": 2}],
				object(),
			).root

		self.assertEqual(result.interaction.kind, "INPUT")
		self.assertEqual(service.call_args.args[:2], ("CUST-001", [{"item": "ITEM-001", "qty": 2.0}]))


if __name__ == "__main__":
	unittest.main()
