from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.contracts.masters.item_read import (
	ItemAggregateInput,
	ItemQueryInput,
)
from mcp_erpnext.services.masters import item_read as read


class FakeItem:
	def __init__(self):
		self.values = {
			"name": "ITEM-0001",
			"item_code": "ITEM-0001",
			"item_name": "Blue Polo",
			"item_group": "Products",
			"stock_uom": "Nos",
			"disabled": 0,
			"is_sales_item": 1,
			"is_purchase_item": 1,
			"is_stock_item": 0,
			"brand": "Acme",
			"description": "Internal description must be projected only when requested.",
			"internal_note": "must not be exposed",
		}
		self.readable = True

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)

	def has_permission(self, permission):
		return permission == "read" and self.readable


class ItemReadServiceTests(unittest.TestCase):
	def setUp(self):
		self.document = FakeItem()
		self.list_rows = [
			{"name": "ITEM-0001", "item_code": "ITEM-0001", "item_name": "Blue Polo"}
		]
		self.last_list = None
		self.fake_frappe = SimpleNamespace(
			get_doc=lambda _doctype, _name: self.document,
			get_list=self._get_list,
			DoesNotExistError=frappe.DoesNotExistError,
		)
		self.patch = patch.object(read, "frappe", self.fake_frappe)
		self.patch.start()

	def tearDown(self):
		self.patch.stop()

	def _get_list(self, doctype, **kwargs):
		self.last_list = (doctype, kwargs)
		fields = kwargs.get("fields") or []
		if any(isinstance(field, dict) and field.get("COUNT") == "*" for field in fields):
			return [{"item_group": "Products", "count": 2}]
		return self.list_rows

	def test_exact_read_projects_only_requested_fields_and_checks_permission(self):
		result = read.get_item("ITEM-0001", ["item_name", "stock_uom"])
		self.assertEqual(
			result,
			{"status": "ok", "document": {"item_name": "Blue Polo", "stock_uom": "Nos"}},
		)

		self.document.readable = False
		self.assertEqual(read.get_item("ITEM-0001", ["name"])["code"], "PERMISSION_DENIED")

	def test_query_uses_exact_filters_projection_sort_pagination_and_permissions(self):
		criteria = ItemQueryInput(
			item_name="Web Development Services",
			disabled=False,
			is_sales_item=True,
			fields=["name", "item_name", "disabled"],
			limit=10,
			offset=5,
			sort_by="item_name",
			sort_order="asc",
		).model_dump()
		result = read.query_items(criteria)
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["count"], 1)
		self.assertFalse(self.last_list[1]["ignore_permissions"])
		self.assertEqual(
			self.last_list[1]["filters"],
			[
				["item_name", "=", "Web Development Services"],
				["disabled", "=", 0],
				["is_sales_item", "=", 1],
			],
		)
		self.assertEqual(self.last_list[1]["fields"], ["name", "item_name", "disabled"])
		self.assertEqual(self.last_list[1]["order_by"], "item_name asc, name asc")
		self.assertEqual(self.last_list[1]["limit_start"], 5)
		self.assertEqual(self.last_list[1]["limit_page_length"], 10)

	def test_query_can_explicitly_request_disabled_items_without_resolver_filter(self):
		read.query_items(ItemQueryInput(disabled=True, fields=["name", "disabled"]).model_dump())
		self.assertEqual(self.last_list[1]["filters"], [["disabled", "=", 1]])

	def test_exact_absent_query_is_clean_empty_result(self):
		self.list_rows = []
		result = read.query_items(
			ItemQueryInput(item_name="Web Development Services", fields=["name", "item_name"]).model_dump()
		)
		self.assertEqual(result, {"status": "ok", "items": [], "count": 0, "limit": 20, "offset": 0})
		self.assertEqual(self.last_list[1]["filters"], [["item_name", "=", "Web Development Services"]])

	def test_query_maps_date_ranges_to_datetime_safe_filters(self):
		read.query_items(
			ItemQueryInput(
				created_from=date(2026, 9, 1),
				created_to=date(2026, 9, 9),
				modified_to=date(2026, 9, 9),
			).model_dump()
		)
		self.assertIn(["creation", "between", ["2026-09-01", "2026-09-09"]], self.last_list[1]["filters"])
		self.assertIn(["modified", "<", "2026-09-10"], self.last_list[1]["filters"])

	def test_aggregate_uses_server_side_count_and_grouping(self):
		result = read.aggregate_items(
			ItemAggregateInput(item_group="Products", group_by="item_group").model_dump()
		)
		self.assertEqual(
			result,
			{
				"status": "ok",
				"metrics": ["count"],
				"group_by": "item_group",
				"results": [{"count": 2, "group_value": "Products"}],
			},
		)
		self.assertFalse(self.last_list[1]["ignore_permissions"])
		self.assertEqual(self.last_list[1]["fields"], ["item_group", {"COUNT": "*", "as": "count"}])
		self.assertEqual(self.last_list[1]["group_by"], "item_group")

	def test_missing_exact_item_is_not_found(self):
		def missing(_doctype, _name):
			raise frappe.DoesNotExistError

		self.fake_frappe.get_doc = missing
		self.assertEqual(read.get_item("MISSING", ["name"]), {"status": "not_found", "item": "MISSING"})

	def test_pricing_and_unsafe_query_controls_are_not_public_fields(self):
		invalid_payloads = (
			(ItemQueryInput, {"fields": ["standard_rate"]}),
			(ItemQueryInput, {"fields": ["owner; drop table"]}),
			(ItemQueryInput, {"sort_by": "modified desc; delete"}),
			(ItemQueryInput, {"limit": 101}),
			(ItemQueryInput, {"offset": -1}),
			(ItemQueryInput, {"created_from": "2026-09-09", "created_to": "2026-09-08"}),
			(ItemAggregateInput, {"group_by": "owner"}),
		)
		for model, payload in invalid_payloads:
			with self.subTest(model=model.__name__, payload=payload):
				with self.assertRaises(ValidationError):
					model.model_validate(payload)


if __name__ == "__main__":
	unittest.main()
