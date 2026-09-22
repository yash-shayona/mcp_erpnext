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
				"search_contacts",
				"prepare_customer_contact",
				"confirm_customer_contact",
				"prepare_customer_primary_contact",
				"confirm_customer_primary_contact",
				"prepare_contact",
				"confirm_contact",
				"prepare_contact_update",
				"confirm_contact_update",
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
				"prepare_sales_invoice",
				"confirm_sales_invoice",
				"prepare_sales_order_to_delivery_note",
				"confirm_sales_order_to_delivery_note",
				"prepare_sales_invoice_to_delivery_note",
				"confirm_sales_invoice_to_delivery_note",
				"prepare_delivery_note_to_sales_invoice",
				"confirm_delivery_note_to_sales_invoice",
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
				"query_sales_orders",
				"aggregate_sales_orders",
				"query_sales_order_items",
				"get_customer",
				"query_customers",
				"aggregate_customers",
				"get_item",
				"query_items",
				"aggregate_items",
				"get_quotation",
				"query_quotations",
				"aggregate_quotations",
				"get_sales_invoice",
				"query_sales_invoices",
				"aggregate_sales_invoices",
				"get_delivery_note",
				"query_delivery_notes",
				"aggregate_delivery_notes",
				"render_document_pdf",
				"prepare_document_email",
				"confirm_document_email",
			],
		)
		self.assertNotIn("search_sales_orders", mcp.tool_names)
