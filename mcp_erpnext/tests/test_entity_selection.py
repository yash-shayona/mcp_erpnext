from __future__ import annotations

import unittest

from mcp_erpnext.services.common.entity_resolution import (
	resolve_ranked_candidates,
)
from mcp_erpnext.services.masters.selection import select_resolved_candidate


class EntitySelectionTests(unittest.TestCase):
	def test_development_item_candidates_remain_ambiguous_without_a_selection(self):
		candidates = [
			{
				"value": "SV-FRAPPE-DEVELOPMENT",
				"label": "Frappe Custom App Development",
				"score": 0.597,
			},
			{
				"value": "SV-WEBSITE-DEVELOPMENT",
				"label": "Website Development",
				"score": 0.55,
			},
		]
		result = resolve_ranked_candidates("Development Item", candidates)
		self.assertEqual(result["status"], "ambiguous")
		self.assertEqual(result["candidates"][0]["value"], "SV-FRAPPE-DEVELOPMENT")
		self.assertNotIn("candidate", result)

	def test_selected_candidate_is_revalidated_with_entity_filters_and_permissions(self):
		calls = []

		def get_list(doctype, **kwargs):
			calls.append((doctype, kwargs))
			return [
				{
					"name": "SV-FRAPPE-DEVELOPMENT",
					"item_code": "SV-FRAPPE-DEVELOPMENT",
					"item_name": "Frappe Custom App Development",
					"stock_uom": "Nos",
				}
			]

		result = select_resolved_candidate("Item", "SV-FRAPPE-DEVELOPMENT", get_list=get_list)
		self.assertEqual(
			result,
			{
				"status": "resolved",
				"doctype": "Item",
				"reference": {"doctype": "Item", "name": "SV-FRAPPE-DEVELOPMENT"},
				"match_type": "exact",
			},
		)
		self.assertEqual(calls[0][0], "Item")
		self.assertEqual(calls[0][1]["filters"]["name"], "SV-FRAPPE-DEVELOPMENT")
		self.assertEqual(calls[0][1]["filters"]["is_sales_item"], 1)
		self.assertFalse(calls[0][1]["ignore_permissions"])

	def test_unknown_or_unpermitted_selection_has_no_fallback(self):
		result = select_resolved_candidate(
			"Customer", "CUST-PRIVATE", get_list=lambda *_args, **_kwargs: []
		)
		self.assertEqual(
			result,
			{
				"status": "not_found",
				"doctype": "Customer",
				"query": "CUST-PRIVATE",
				"candidates": [],
			},
		)


if __name__ == "__main__":
	unittest.main()
