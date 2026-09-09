from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import approvals
from mcp_erpnext.services.buying import purchase_order as purchase_order_service


class FakeRow(SimpleNamespace):
    def as_dict(self):
        return dict(self.__dict__)


class FakePurchaseOrder:
    def __init__(self, values: dict | None = None):
        self.__dict__.update(values or {})
        self.name = getattr(self, "name", None) or "PUR-ORD-TEST-0001"
        self.docstatus = getattr(self, "docstatus", None) or 0
        self.items = [FakeRow(**row) if isinstance(row, dict) else row for row in (values or {}).get("items", [])]
        self.taxes = [FakeRow(**row) if isinstance(row, dict) else row for row in (values or {}).get("taxes", [])]
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
        self.supplier_name = "Acme Supplier"
        self.buying_price_list = self.buying_price_list or "Standard Buying"
        self.price_list_currency = "INR"
        self.currency = "INR"
        self.conversion_rate = 1
        self.plc_conversion_rate = 1
        for row in self.items:
            row.item_name = "Purchased Item"
            row.uom = "Nos"
            row.rate = getattr(row, "rate", None) if getattr(row, "rate", None) is not None else 100
            row.amount = row.qty * row.rate

    def calculate_taxes_and_totals(self):
        self.net_total = sum(row.amount for row in self.items)
        self.total_taxes_and_charges = 0
        self.grand_total = self.net_total

    def run_method(self, _method):
        return self

    def as_dict(self):
        result = dict(self.__dict__)
        result["items"] = [row.as_dict() for row in self.items]
        result["taxes"] = [row.as_dict() for row in self.taxes]
        result.pop("insert_calls", None)
        return result

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        return self


class PurchaseOrderServiceTests(unittest.TestCase):
    def setUp(self):
        approvals._approvals.clear()
        self.docs: list[FakePurchaseOrder] = []
        self.commit_count = 0
        self.fake_frappe = SimpleNamespace(
            session=SimpleNamespace(user="purchase@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            defaults=SimpleNamespace(get_user_default=lambda _name: "Test Company"),
            get_list=self._get_list,
            has_permission=lambda *_args: True,
            new_doc=self._new_doc,
            get_doc=self._get_doc,
            db=SimpleNamespace(commit=self._commit, rollback=lambda: None),
            PermissionError=frappe.PermissionError,
        )
        self.patches = [
            patch.object(purchase_order_service, "frappe", self.fake_frappe),
            patch.object(purchase_order_service, "nowdate", return_value="2026-09-07"),
            patch.object(
                purchase_order_service,
                "getdate",
                side_effect=lambda value: value if isinstance(value, date) else date.fromisoformat(value),
            ),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    @staticmethod
    def _get_list(doctype, *, filters=None, **_kwargs):
        name = (filters or {}).get("name")
        records = {
            "Supplier": {"SUP-001": {"name": "SUP-001", "supplier_name": "Acme Supplier"}},
            "Item": {"ITEM-001": {"name": "ITEM-001", "item_code": "ITEM-001", "item_name": "Purchased Item", "stock_uom": "Nos"}},
            "Company": {"Test Company": {"name": "Test Company"}},
        }
        row = records.get(doctype, {}).get(name)
        return [row] if row else []

    def _new_doc(self, _doctype):
        doc = FakePurchaseOrder()
        self.docs.append(doc)
        return doc

    @staticmethod
    def _get_doc(values):
        return FakePurchaseOrder(values)

    def _commit(self):
        self.commit_count += 1

    @staticmethod
    def _request():
        return (
            {"doctype": "Supplier", "name": "SUP-001"},
            [{"item": {"doctype": "Item", "name": "ITEM-001"}, "qty": 2.0}],
        )

    def test_prepare_uses_defaults_and_does_not_write(self):
        supplier, items = self._request()
        result = purchase_order_service.prepare_purchase_order(supplier, items)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["preview"]["schedule_date"], "2026-09-07")
        self.assertEqual(result["preview"]["items"][0]["item_code"], "ITEM-001")
        self.assertEqual(self.commit_count, 0)

    def test_confirm_requires_shared_approval_then_uses_normal_insert(self):
        supplier, items = self._request()
        prepared = purchase_order_service.prepare_purchase_order(supplier, items)
        rejected = purchase_order_service.confirm_purchase_order(prepared["approval_token"], True)
        self.assertEqual(rejected["code"], "TRUSTED_APPROVAL_UNAVAILABLE")
        prepared = purchase_order_service.prepare_purchase_order(supplier, items)
        approvals.record_trusted_user_approval(
            prepared["approval_token"],
            action="create_purchase_order",
            site="test.localhost",
            user="purchase@example.com",
        )
        result = purchase_order_service.confirm_purchase_order(prepared["approval_token"], True)
        self.assertEqual(result["status"], "created")
        self.assertEqual(self.commit_count, 1)


if __name__ == "__main__":
    unittest.main()
