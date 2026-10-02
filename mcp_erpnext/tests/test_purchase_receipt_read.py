from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.services.buying import purchase_receipt_read as service


class PurchaseReceiptReadTests(unittest.TestCase):
    def test_exact_read_projects_selected_header_and_lineage_fields(self):
        item = SimpleNamespace(get=lambda key, default=None: {
            "name": "PRE-ITEM-001", "item_code": "ITEM-001", "purchase_order": "PO-001",
            "purchase_order_item": "PO-ITEM-001", "qty": 2, "rejected_qty": 0,
        }.get(key, default))
        doc = SimpleNamespace(
            get=lambda key, default=None: {"name": "PRE-001", "supplier": "SUP-001", "docstatus": 0, "items": [item]}.get(key, default),
            has_permission=lambda permission: True,
        )
        fake_frappe = SimpleNamespace(get_doc=lambda *_: doc, DoesNotExistError=frappe.DoesNotExistError, PermissionError=frappe.PermissionError)
        with patch.object(service, "frappe", fake_frappe):
            result = service.get_purchase_receipt("PRE-001", ["name", "supplier"], True, ["name", "purchase_order", "purchase_order_item", "qty"])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["document"]["items"][0]["purchase_order_item"], "PO-ITEM-001")
        self.assertNotIn("unrestricted", result["document"])

    def test_exact_read_rejects_unallowlisted_fields(self):
        result = service.get_purchase_receipt("PRE-001", ["name", "internal_account"])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "INVALID_FIELDS")


if __name__ == "__main__":
    unittest.main()
