from __future__ import annotations

import unittest
from unittest.mock import patch

from mcp_erpnext.services.selling.terms import (
    TERMS_TYPO_FALLBACK_SCAN_LIMIT,
    resolve_terms_and_conditions,
)
from mcp_erpnext.tools.selling import terms as terms_tools


class FakeTermsList:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, doctype, **kwargs):
        self.calls.append((doctype, kwargs))
        rows = [row for row in self.rows if row.get("visible", True)]
        for field, expected in kwargs.get("filters", {}).items():
            rows = [row for row in rows if row.get(field) == expected]
        or_filters = kwargs.get("or_filters")
        if or_filters:
            rows = [
                row
                for row in rows
                if any(
                    condition[3].strip("%").casefold()
                    in str(row.get(condition[1]) or "").casefold()
                    for condition in or_filters
                )
            ]
        fields = kwargs["fields"]
        limit = kwargs["limit_page_length"]
        return [{field: row.get(field) for field in fields} for row in rows[:limit]]


class TermsResolutionTests(unittest.TestCase):
    def setUp(self):
        self.sales_order_terms = {
            "name": "Sales Order Terms",
            "title": "Sales Order Terms",
            "selling": 1,
            "buying": 1,
            "disabled": 0,
            "terms": "private rendered body",
        }

    def resolve(self, query, rows=None):
        fake = FakeTermsList(rows or [self.sales_order_terms])
        return resolve_terms_and_conditions(query, get_list=fake), fake

    def test_exact_and_normalized_exact_return_the_canonical_reference(self):
        for query in ("Sales Order Terms", "sales order terms", " sales-order terms "):
            with self.subTest(query=query):
                result, _fake = self.resolve(query)
                self.assertEqual(result["status"], "resolved")
                self.assertEqual(result["match_type"], "exact")
                self.assertEqual(
                    result["reference"],
                    {
                        "doctype": "Terms and Conditions",
                        "name": "Sales Order Terms",
                        "title": "Sales Order Terms",
                    },
                )

    def test_partial_phrase_uses_shared_strong_match_rules(self):
        result, _fake = self.resolve("sales order")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["match_type"], "spelling_correction")

    def test_typo_with_one_search_token_uses_normal_candidate_discovery(self):
        result, fake = self.resolve("sles order terms")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("or_filters", fake.calls[0][1])

    def test_all_token_typo_uses_bounded_permission_aware_fallback(self):
        result, fake = self.resolve("sles oder tems")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["match_type"], "spelling_correction")
        self.assertEqual(len(fake.calls), 2)
        fallback = fake.calls[1][1]
        self.assertEqual(fallback["filters"], {"selling": 1, "disabled": 0})
        self.assertEqual(fallback["fields"], ["name", "title"])
        self.assertEqual(fallback["limit_page_length"], TERMS_TYPO_FALLBACK_SCAN_LIMIT)
        self.assertFalse(fallback["ignore_permissions"])

    def test_weak_single_candidate_requires_selection(self):
        result, _fake = self.resolve(
            "payment",
            [{"name": "Payment and Delivery", "title": "Payment and Delivery", "selling": 1, "disabled": 0}],
        )
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(len(result["candidates"]), 1)

    def test_close_candidates_are_ambiguous(self):
        result, _fake = self.resolve(
            "sales order",
            [
                self.sales_order_terms,
                {"name": "Sales Orders Terms", "title": "Sales Orders Terms", "selling": 1, "disabled": 0},
            ],
        )
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(len(result["candidates"]), 2)

    def test_no_eligible_or_visible_candidate_is_not_found(self):
        rows = [
            {"name": "Disabled", "title": "Disabled", "selling": 1, "disabled": 1},
            {"name": "Buying Only", "title": "Buying Only", "selling": 0, "disabled": 0},
            {"name": "Private", "title": "Private", "selling": 1, "disabled": 0, "visible": False},
        ]
        result, fake = self.resolve("terms", rows)
        self.assertEqual(result["status"], "not_found")
        self.assertTrue(all(call[1]["filters"] == {"selling": 1, "disabled": 0} for call in fake.calls))
        self.assertTrue(all(call[1]["ignore_permissions"] is False for call in fake.calls))

    def test_candidate_payload_never_exposes_terms_body(self):
        result, _fake = self.resolve("payment", [
            {"name": "Payment and Delivery", "title": "Payment and Delivery", "selling": 1, "disabled": 0, "terms": "secret body"}
        ])
        self.assertEqual(result["status"], "ambiguous")
        candidate = result["candidates"][0]
        self.assertNotIn("terms", candidate)
        self.assertNotIn("terms", candidate["reference"])

    def test_wrapper_adds_shared_selection_directive_only_for_ambiguity(self):
        service_result = {
            "status": "ambiguous",
            "doctype": "Terms and Conditions",
            "query": "sales terms",
            "candidates": [{
                "reference": {"doctype": "Terms and Conditions", "name": "Sales Order Terms", "title": "Sales Order Terms"},
                "label": "Sales Order Terms",
                "score": 0.8,
            }],
        }
        with patch.object(terms_tools, "execute_tool_with_context", return_value=service_result):
            result = terms_tools.resolve_terms_and_conditions("sales terms", object()).root
        self.assertTrue(result.interaction.required)
        self.assertEqual(result.interaction.kind, "SELECTION")
        self.assertNotIn("terms", result.candidates[0].model_dump())


if __name__ == "__main__":
    unittest.main()
