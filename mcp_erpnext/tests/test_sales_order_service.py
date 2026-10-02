from __future__ import annotations

import inspect
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import approvals
from mcp_erpnext.contracts.selling.sales_order import SalesOrderPrepareInput
from mcp_erpnext.services.selling import sales_order as sales_order_service
from mcp_erpnext.tests.approval_test_backend import install_fake_backend, read_record
from mcp_erpnext.tools.selling.sales_order import prepare_sales_order as prepare_sales_order_tool


class FakeRow(SimpleNamespace):
    def __getattr__(self, _name):
        return None

    def as_dict(self):
        return dict(self.__dict__)

    def get(self, name, default=None):
        return getattr(self, name, default)


class FakeSalesOrder:
    def __init__(self, values: dict | None = None):
        self.__dict__.update(values or {})
        self.doctype = getattr(self, "doctype", None) or "Sales Order"
        self.name = getattr(self, "name", None) or "ST-SORD-2627-0001"
        self.docstatus = getattr(self, "docstatus", None) or 0
        self.naming_series = (
            getattr(self, "naming_series", None) or "ST-SORD-2627-.####"
        )
        self.items = [
            FakeRow(**row) if isinstance(row, dict) else row
            for row in (getattr(self, "items", None) or [])
        ]
        self.payment_schedule = [
            FakeRow(**row) if isinstance(row, dict) else row
            for row in (getattr(self, "payment_schedule", None) or [])
        ]
        self.insert_calls: list[dict] = []

    def __getattr__(self, _name):
        return None

    def get(self, name, default=None):
        return getattr(self, name, default)

    def append(self, table, values):
        row = FakeRow(**values)
        getattr(self, table).append(row)
        return row

    def set_missing_values(self):
        self.customer_name = "Acme Customer"
        self.payment_terms_template = self.payment_terms_template or "Native Customer Terms"
        self.selling_price_list = self.selling_price_list or "Standard Selling"
        self.price_list_currency = "INR"
        self.currency = "INR"
        self.conversion_rate = 1
        self.plc_conversion_rate = 1
        for row in self.items:
            row.item_name = "Sales Item"
            row.uom = "Nos"
            row.rate = 100
            row.amount = row.qty * row.rate
            row.warehouse = None
            row.delivery_date = self.delivery_date

    def calculate_taxes_and_totals(self):
        self.grand_total = sum(row.amount for row in self.items)

    def set_missing_terms(self):
        if self.get("tc_name") and not self.get("terms"):
            self.terms = "Native rendered terms"

    def set_payment_schedule(self):
        self.payment_schedule = [
            FakeRow(
                payment_term="Net 30",
                due_date=date(2026, 10, 26),
                invoice_portion=100,
                payment_amount=self.grand_total,
                description="Native schedule",
            )
        ]

    def run_method(self, _method):
        return self

    def as_dict(self):
        result = dict(self.__dict__)
        result["items"] = [row.as_dict() for row in self.items]
        result["payment_schedule"] = [row.as_dict() for row in self.payment_schedule]
        result.pop("insert_calls", None)
        return result

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        return self


class SalesOrderServiceTests(unittest.TestCase):
    def setUp(self):
        self.create_mode_patch = patch.dict("os.environ", {"MCP_CREATE_MODE": "approval_required"})
        self.create_mode_patch.start()
        self.addCleanup(self.create_mode_patch.stop)
        self.approval_backend = install_fake_backend(approvals)
        self.docs: list[FakeSalesOrder] = []
        self.commit_count = 0
        self.fake_frappe = SimpleNamespace(
            session=SimpleNamespace(user="sales@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            conf={},
            defaults=SimpleNamespace(get_user_default=lambda _name: "Test Company"),
            get_list=lambda _doctype, *_args, **kwargs: [
                {"name": kwargs.get("filters", {}).get("name", "Test Company")}
            ],
            get_value=lambda *_args, **_kwargs: None,
            has_permission=lambda *_args, **_kwargs: True,
            new_doc=self._new_doc,
            get_doc=self._get_doc,
            db=SimpleNamespace(commit=self._commit, rollback=lambda: None),
            PermissionError=frappe.PermissionError,
            ValidationError=frappe.ValidationError,
        )
        self.patches = [
            patch.object(sales_order_service, "frappe", self.fake_frappe),
            patch.object(sales_order_service, "nowdate", return_value="2026-09-26"),
            patch.object(
                sales_order_service,
                "getdate",
                side_effect=lambda value: (
                    value if isinstance(value, date) else date.fromisoformat(value)
                ),
            ),
            patch.object(
                sales_order_service,
                "resolve_customer",
                return_value={
                    "status": "resolved",
                    "match_type": "exact",
                    "candidate": {"value": "CUST-001"},
                },
            ),
            patch.object(
                sales_order_service,
                "resolve_sales_item",
                return_value={
                    "status": "resolved",
                    "match_type": "exact",
                    "candidate": {
                        "value": "ITEM-001",
                        "item_name": "Sales Item",
                    },
                },
            ),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def _new_doc(self, doctype):
        self.assertEqual(doctype, "Sales Order")
        doc = FakeSalesOrder()
        self.docs.append(doc)
        return doc

    def _get_doc(self, values):
        doc = FakeSalesOrder(values)
        self.docs.append(doc)
        return doc

    def _commit(self):
        self.commit_count += 1

    @staticmethod
    def _prepare():
        return sales_order_service.prepare_sales_order(
            "CUST-001", [{"item": "ITEM-001", "qty": 2}]
        )

    def test_prepare_preserves_native_naming_series_in_approval_payload(self):
        result = self._prepare()

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["preview"]["payment_terms_template"], "Native Customer Terms")
        payload = read_record(approvals, result["approval_token"]).payload
        self.assertEqual(payload["naming_series"], "ST-SORD-2627-.####")
        self.assertNotEqual(payload["naming_series"], "SAL-ORD-.YYYY.-")
        self.assertEqual(self.commit_count, 0)

    def test_direct_preview_and_execute_never_use_approval_storage(self):
        with patch.dict("os.environ", {"MCP_CREATE_MODE": "direct"}), patch.object(
            approvals, "create", side_effect=AssertionError("direct create must not use approval storage")
        ), patch.object(approvals, "prune_expired", side_effect=AssertionError("direct create must not prune approvals")):
            preview = self._prepare()
            created = sales_order_service.execute_sales_order(
                customer="CUST-001", items=[{"item": "ITEM-001", "qty": 2}]
            )
        self.assertEqual(preview["status"], "preview")
        self.assertNotIn("approval_token", preview)
        self.assertEqual(created["status"], "created")

    def test_final_mode_change_blocks_direct_and_approved_inserts(self):
        original = sales_order_service.exact_mode_failure
        for changed_mode, expected in (("approval_required", "APPROVAL_REQUIRED"), ("disabled", "CREATE_DISABLED")):
            with self.subTest(changed_mode=changed_mode):
                self.docs.clear()

                def change_mode(action, mode, *, new_mode=changed_mode):
                    os.environ["MCP_CREATE_MODE"] = new_mode
                    return original(action, mode)

                with patch.dict("os.environ", {"MCP_CREATE_MODE": "direct"}), patch.object(
                    sales_order_service, "exact_mode_failure", side_effect=change_mode
                ):
                    result = sales_order_service.execute_sales_order(
                        customer="CUST-001", items=[{"item": "ITEM-001", "qty": 2}]
                    )
                self.assertEqual(result["code"], expected)
                self.assertTrue(all(not doc.insert_calls for doc in self.docs))

        prepared = self._prepare()
        approvals.record_trusted_user_approval(
            prepared["approval_token"], action="create_sales_order",
            site="test.localhost", user="sales@example.com",
        )

        def switch_to_direct(action, mode):
            os.environ["MCP_CREATE_MODE"] = "direct"
            return original(action, mode)

        with patch.dict("os.environ", {"MCP_CREATE_MODE": "approval_required"}), patch.object(
            sales_order_service, "exact_mode_failure", side_effect=switch_to_direct
        ):
            result = sales_order_service.confirm_sales_order(prepared["approval_token"], True)
        self.assertEqual(result["code"], "DIRECT_EXECUTION_REQUIRED")
        self.assertTrue(all(not doc.insert_calls for doc in self.docs))

    def test_confirm_reconstructs_the_reviewed_native_naming_series(self):
        prepared = self._prepare()
        approvals.record_trusted_user_approval(
            prepared["approval_token"],
            action="create_sales_order",
            site="test.localhost",
            user="sales@example.com",
        )

        result = sales_order_service.confirm_sales_order(
            prepared["approval_token"], True
        )

        self.assertEqual(result["status"], "created")
        self.assertEqual(self.docs[-1].naming_series, "ST-SORD-2627-.####")
        self.assertEqual(
            self.docs[-1].insert_calls,
            [
                {
                    "ignore_permissions": False,
                    "ignore_links": False,
                    "ignore_mandatory": False,
                }
            ],
        )
        self.assertEqual(self.commit_count, 1)

    def test_naming_series_is_not_a_public_prepare_input(self):
        self.assertNotIn("naming_series", SalesOrderPrepareInput.model_fields)
        self.assertNotIn(
            "naming_series", inspect.signature(prepare_sales_order_tool).parameters
        )

    def test_explicit_and_configured_payment_terms_are_previewed(self):
        explicit = sales_order_service.prepare_sales_order(
            "CUST-001",
            [{"item": "ITEM-001", "qty": 2}],
            payment_terms_template="Explicit Template",
        )
        self.assertEqual(explicit["preview"]["payment_terms_template"], "Explicit Template")
        self.assertEqual(explicit["preview"]["payment_schedule"][0]["invoice_portion"], 100)

        self.fake_frappe.conf["mcp_business_defaults"] = {
            "site": {"Sales Order": {
                "terms_and_conditions_template": "Configured Terms",
                "payment_terms_template": "Configured Template",
            }}
        }
        configured = self._prepare()
        self.assertEqual(configured["preview"]["tc_name"], "Configured Terms")
        self.assertEqual(configured["preview"]["payment_terms_template"], "Configured Template")

    def test_confirmation_rejects_configured_template_drift(self):
        self.fake_frappe.conf["mcp_business_defaults"] = {
            "site": {"Sales Order": {"payment_terms_template": "Configured Template"}}
        }
        prepared = self._prepare()
        approvals.record_trusted_user_approval(
            prepared["approval_token"],
            action="create_sales_order",
            site="test.localhost",
            user="sales@example.com",
        )
        self.fake_frappe.conf["mcp_business_defaults"]["site"]["Sales Order"]["payment_terms_template"] = "Changed Template"
        result = sales_order_service.confirm_sales_order(prepared["approval_token"], True)
        self.assertEqual(result["code"], "STALE_CONFIRMATION")


if __name__ == "__main__":
    unittest.main()
