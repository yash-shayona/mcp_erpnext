from __future__ import annotations

import unittest

from mcp_erpnext.services.common.aggregate import (
	build_aggregate_field,
	build_aggregate_fields,
	execute_aggregate,
	shape_aggregate_rows,
)


class AggregateFoundationTests(unittest.TestCase):
	def test_build_aggregate_field_uses_frappe_v16_dictionary_form(self):
		self.assertEqual(
			build_aggregate_field("sum", "grand_total", "sum_grand_total"),
			{"SUM": "grand_total", "as": "sum_grand_total"},
		)
		with self.assertRaises(ValueError):
			build_aggregate_field("median", "grand_total", "median_grand_total")

	def test_build_aggregate_fields_preserves_metric_mapping_and_group_alias(self):
		fields, groups = build_aggregate_fields(
			["count", "sum_amount"],
			{
				"count": {"COUNT": "*", "as": "count"},
				"sum_amount": {"SUM": "amount", "as": "sum_amount"},
			},
			group_by="item_code",
			group_field="`tabSales Order Item`.item_code",
			group_alias="group_value",
		)
		self.assertEqual(
			fields,
			[
				"`tabSales Order Item`.item_code as group_value",
				{"COUNT": "*", "as": "count"},
				{"SUM": "amount", "as": "sum_amount"},
			],
		)
		self.assertEqual(groups, ["`tabSales Order Item`.item_code"])

	def test_execute_aggregate_forwards_grouping_and_permissions(self):
		calls = []

		def get_list(doctype, **kwargs):
			calls.append((doctype, kwargs))
			return [{"count": 2}]

		rows = execute_aggregate(
			get_list,
			"Customer",
			filters=[["customer_group", "=", "Commercial"]],
			fields=[{"COUNT": "*", "as": "count"}],
			groups=["customer_group"],
		)
		self.assertEqual(rows, [{"count": 2}])
		self.assertEqual(calls[0][0], "Customer")
		self.assertEqual(calls[0][1]["group_by"], "customer_group")
		self.assertEqual(calls[0][1]["order_by"], "customer_group")
		self.assertFalse(calls[0][1]["ignore_permissions"])

	def test_shape_aggregate_rows_keeps_metrics_and_group_value_only(self):
		self.assertEqual(
			shape_aggregate_rows(
				[{"customer_group": "Commercial", "count": 2, "sum_amount": None}],
				["count", "sum_amount"],
				group_by="customer_group",
			),
			[{"count": 2, "group_value": "Commercial"}],
		)


if __name__ == "__main__":
	unittest.main()
