from __future__ import annotations

import unittest

from mcp_erpnext.services.selling.payment_terms import (
    PAYMENT_TERMS_TYPO_FALLBACK_SCAN_LIMIT,
    resolve_payment_terms_template,
)


class FakePaymentTermsList:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, doctype, **kwargs):
        self.calls.append((doctype, kwargs))
        rows = [row for row in self.rows if row.get("visible", True)]
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
        return [
            {field: row.get(field) for field in kwargs["fields"]}
            for row in rows[: kwargs["limit_page_length"]]
        ]


class PaymentTermsResolutionTests(unittest.TestCase):
    def resolve(self, query, rows=None):
        fake = FakePaymentTermsList(
            rows or [{"name": "Net 30", "template_name": "Net 30"}]
        )
        return resolve_payment_terms_template(query, get_list=fake), fake

    def test_exact_partial_and_typo_resolution_use_safe_identity_fields(self):
        exact, _ = self.resolve("Net 30")
        partial, _ = self.resolve("net")
        typo, fake = self.resolve("nett therty")
        self.assertEqual(exact["status"], "resolved")
        self.assertEqual(exact["reference"]["name"], "Net 30")
        self.assertEqual(partial["status"], "ambiguous")
        self.assertEqual(typo["status"], "ambiguous")
        self.assertEqual(
            fake.calls[-1][1]["limit_page_length"],
            PAYMENT_TERMS_TYPO_FALLBACK_SCAN_LIMIT,
        )
        self.assertFalse(fake.calls[-1][1]["ignore_permissions"])

    def test_ambiguity_not_found_and_permission_exclusion(self):
        ambiguous, _ = self.resolve(
            "net",
            [
                {"name": "Net 30", "template_name": "Net 30"},
                {"name": "Net 45", "template_name": "Net 45"},
            ],
        )
        missing, _ = self.resolve(
            "private", [{"name": "Private", "template_name": "Private", "visible": False}]
        )
        self.assertEqual(ambiguous["status"], "ambiguous")
        self.assertEqual(missing["status"], "not_found")
        self.assertEqual(
            set(ambiguous["candidates"][0]["reference"]),
            {"doctype", "name", "template_name"},
        )


if __name__ == "__main__":
    unittest.main()
