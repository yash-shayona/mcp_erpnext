from __future__ import annotations

import inspect
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

    def run_method(self, _method):
        return self

    def as_dict(self):
        result = dict(self.__dict__)
        result["items"] = [row.as_dict() for row in self.items]
        result.pop("insert_calls", None)
        return result

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        return self


class SalesOrderServiceTests(unittest.TestCase):
    def setUp(self):
        self.approval_backend = install_fake_backend(approvals)
        self.docs: list[FakeSalesOrder] = []
        self.commit_count = 0
        self.fake_frappe = SimpleNamespace(
            session=SimpleNamespace(user="sales@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            defaults=SimpleNamespace(get_user_default=lambda _name: "Test Company"),
            get_list=lambda *_args, **_kwargs: [{"name": "Test Company"}],
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
        payload = read_record(approvals, result["approval_token"]).payload
        self.assertEqual(payload["naming_series"], "ST-SORD-2627-.####")
        self.assertNotEqual(payload["naming_series"], "SAL-ORD-.YYYY.-")
        self.assertEqual(self.commit_count, 0)

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


if __name__ == "__main__":
    unittest.main()
