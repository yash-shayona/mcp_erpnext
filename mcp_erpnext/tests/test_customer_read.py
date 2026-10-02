from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.contracts.masters.customer_read import (
    CustomerAggregateInput,
    CustomerGetInput,
    CustomerQueryInput,
)
from mcp_erpnext.services.masters import customer_read as read
from mcp_erpnext.services.masters import customer as customer_service


class FakeCustomer:
    def __init__(self):
        self.values = {
            "name": "CUST-0001",
            "customer_name": "Acme",
            "customer_group": "Commercial",
            "territory": "India",
            "email_id": "acme@example.com",
            "mobile_no": "9999999999",
            "disabled": 0,
            "is_frozen": 0,
            "internal_note": "must not be exposed",
        }
        self.readable = True

    def get(self, fieldname, default=None):
        return self.values.get(fieldname, default)

    def has_permission(self, permission):
        return permission == "read" and self.readable


class CustomerReadServiceTests(unittest.TestCase):
    def setUp(self):
        self.document = FakeCustomer()
        self.list_rows = [
            {"name": "CUST-0001", "customer_name": "Acme", "email_id": "acme@example.com"}
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
            return [{"customer_group": "Commercial", "count": 2}]
        return self.list_rows

    def test_exact_read_projects_only_requested_fields_and_checks_permission(self):
        result = read.get_customer("CUST-0001", ["customer_name", "email_id"])
        self.assertEqual(
            result,
            {"status": "ok", "document": {"customer_name": "Acme", "email_id": "acme@example.com"}},
        )

        self.document.readable = False
        self.assertEqual(read.get_customer("CUST-0001", ["name"])["code"], "PERMISSION_DENIED")

    def test_query_uses_exact_allowlisted_filters_projection_sort_pagination_and_permissions(self):
        criteria = CustomerQueryInput(
            email_id="acme@example.com",
            fields=["name", "email_id"],
            limit=10,
            offset=5,
            sort_by="creation",
            sort_order="desc",
        ).model_dump()
        result = read.query_customers(criteria)
        self.assertEqual(result["customers"], [{"name": "CUST-0001", "email_id": "acme@example.com"}])
        self.assertFalse(self.last_list[1]["ignore_permissions"])
        self.assertEqual(self.last_list[1]["filters"], [["email_id", "=", "acme@example.com"]])
        self.assertEqual(self.last_list[1]["fields"], ["name", "email_id"])
        self.assertEqual(self.last_list[1]["order_by"], "creation desc, name desc")
        self.assertEqual(self.last_list[1]["limit_start"], 5)
        self.assertEqual(self.last_list[1]["limit_page_length"], 10)

    def test_query_can_explicitly_request_disabled_customers_without_resolver_filter(self):
        criteria = CustomerQueryInput(disabled=True, fields=["name", "disabled"]).model_dump()
        read.query_customers(criteria)
        self.assertEqual(self.last_list[1]["filters"], [["disabled", "=", 1]])

    def test_query_maps_creation_and_modified_date_ranges_to_datetime_safe_filters(self):
        criteria = CustomerQueryInput(
            created_from=date(2026, 9, 1),
            created_to=date(2026, 9, 9),
            modified_to=date(2026, 9, 9),
        ).model_dump()
        read.query_customers(criteria)
        self.assertIn(["creation", "between", ["2026-09-01", "2026-09-09"]], self.last_list[1]["filters"])
        self.assertIn(["modified", "<", "2026-09-10"], self.last_list[1]["filters"])

    def test_aggregate_uses_server_side_count_and_grouping(self):
        criteria = CustomerAggregateInput(customer_group="Commercial", group_by="customer_group").model_dump()
        result = read.aggregate_customers(criteria)
        self.assertEqual(
            result,
            {
                "status": "ok",
                "metrics": ["count"],
                "group_by": "customer_group",
                "results": [{"count": 2, "group_value": "Commercial"}],
            },
        )
        self.assertFalse(self.last_list[1]["ignore_permissions"])
        self.assertEqual(self.last_list[1]["fields"], ["customer_group", {"COUNT": "*", "as": "count"}])
        self.assertEqual(self.last_list[1]["group_by"], "customer_group")

    def test_exact_email_filter_returns_empty_without_fuzzy_candidates(self):
        self.list_rows = []
        criteria = CustomerQueryInput(
            email_id="customer@example.com", fields=["name", "email_id"]
        ).model_dump()
        result = read.query_customers(criteria)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["customers"], [])
        self.assertEqual(result["count"], 0)
        self.assertEqual(self.last_list[1]["filters"], [["email_id", "=", "customer@example.com"]])

    def test_invalid_field_sort_group_limit_and_date_range_are_rejected(self):
        invalid_payloads = (
            (CustomerQueryInput, {"fields": ["owner; drop table"]}),
            (CustomerQueryInput, {"sort_by": "creation desc; delete"}),
            (CustomerQueryInput, {"limit": 101}),
            (CustomerQueryInput, {"created_from": "2026-09-09", "created_to": "2026-09-08"}),
            (CustomerAggregateInput, {"group_by": "owner"}),
        )
        for model, payload in invalid_payloads:
            with self.subTest(model=model.__name__, payload=payload):
                with self.assertRaises(ValidationError):
                    model.model_validate(payload)

    def test_missing_exact_customer_is_not_found(self):
        def missing(_doctype, _name):
            raise frappe.DoesNotExistError

        self.fake_frappe.get_doc = missing
        self.assertEqual(
            read.get_customer("MISSING", ["name"]),
            {"status": "not_found", "customer": "MISSING"},
        )


class CustomerResolverStructuredIdentifierTests(unittest.TestCase):
    def test_email_shaped_input_never_reaches_fuzzy_name_search(self):
        with patch.object(customer_service, "find_candidates") as find_candidates:
            result = customer_service.search_customers("customer@example.com")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "CUSTOMER_STRUCTURED_QUERY_REQUIRED")
        self.assertFalse(find_candidates.called)

        with patch.object(customer_service, "resolve_candidate") as resolve_candidate:
            result = customer_service.resolve_customer("customer@example.com")
        self.assertEqual(result["code"], "CUSTOMER_STRUCTURED_QUERY_REQUIRED")
        self.assertFalse(resolve_candidate.called)

    def test_name_resolution_still_uses_existing_resolver(self):
        with patch.object(customer_service, "find_candidates", return_value=[]) as find_candidates:
            result = customer_service.search_customers("Sunrise Auto")
        self.assertEqual(result["status"], "not_found")
        self.assertTrue(find_candidates.called)


if __name__ == "__main__":
    unittest.main()
