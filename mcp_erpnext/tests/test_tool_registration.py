from __future__ import annotations

import unittest

from mcp_erpnext.tools import register_tools


class RecordingMCP:
	"""Minimal FastMCP-compatible recorder for static registration verification."""

	def __init__(self):
		self.tool_names: list[str] = []

	def tool(self):
		def decorator(function):
			self.tool_names.append(function.__name__)
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
				"prepare_sales_order",
				"confirm_sales_order",
				"prepare_quotation",
				"confirm_quotation",
			],
		)

