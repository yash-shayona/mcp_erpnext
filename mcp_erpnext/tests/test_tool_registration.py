from __future__ import annotations

import unittest

from mcp_erpnext.tools import register_tools


class RecordingMCP:
	"""Minimal FastMCP-compatible recorder for static registration verification."""

	def __init__(self):
		self.tool_names: list[str] = []

	def tool(self, **kwargs):
		def decorator(function):
			self.tool_names.append(kwargs.get("name", function.__name__))
			return function

		return decorator


class ToolRegistrationTests(unittest.TestCase):
	def test_only_the_controlled_workflow_tools_are_registered(self):
		mcp = RecordingMCP()
		register_tools(mcp)

		self.assertEqual(
			mcp.tool_names,
			[
				"search_customers",
				"resolve_customer",
				"prepare_customer",
				"confirm_customer",
				"search_items",
				"resolve_item",
				"prepare_item",
				"confirm_item",
				"select_resolved_candidate",
				"prepare_sales_order",
				"confirm_sales_order",
				"prepare_quotation",
				"confirm_quotation",
				"prepare_quotation_to_sales_order",
				"confirm_quotation_to_sales_order",
				"prepare_sales_order_to_sales_invoice",
				"confirm_sales_order_to_sales_invoice",
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
				"get_sales_order",
				"search_sales_orders",
				"aggregate_sales_orders",
				"query_sales_order_items",
				"get_customer",
				"query_customers",
				"aggregate_customers",
				"get_item",
				"query_items",
				"aggregate_items",
				"get_quotation",
				"search_quotations",
				"render_document_pdf",
				"prepare_document_email",
				"confirm_document_email",
			],
		)
