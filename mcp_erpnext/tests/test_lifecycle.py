from __future__ import annotations

import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from mcp_erpnext.approvals import ApprovalStore
from mcp_erpnext.contracts.lifecycle import PrepareChildAddInput
from mcp_erpnext.public_errors import PUBLIC_ERROR_DEFINITIONS
from mcp_erpnext.services.common import lifecycle
from mcp_erpnext.settings import ApprovalMode
from mcp_erpnext.tests.approval_test_backend import FakeSharedApprovalBackend


class FakeDocStatus(int):
    def is_draft(self):
        return self == 0

    def is_submitted(self):
        return self == 1

    def is_cancelled(self):
        return self == 2


class FakeField:
    def __init__(self, fieldname, fieldtype="Data", *, read_only=False, options=None):
        self.fieldname = fieldname
        self.fieldtype = fieldtype
        self.read_only = read_only
        self.options = options


class FakeMeta:
    def __init__(self, *fields, is_submittable=False):
        self._fields = {field.fieldname: field for field in fields}
        self.is_submittable = is_submittable
        self.fields = list(self._fields.values())

    def get_field(self, fieldname):
        return self._fields.get(fieldname)

    def has_field(self, fieldname):
        return fieldname in self._fields


class FakeDocument:
    def __init__(
        self, doctype="Sales Order", name="SO-001", *, docstatus=0, modified="one"
    ):
        self.doctype = doctype
        self.name = name
        self.docstatus = FakeDocStatus(docstatus)
        self.modified = modified
        self.remarks = ""
        self.meta = FakeMeta(
            FakeField("remarks"),
            is_submittable=doctype
            in {"Sales Order", "Quotation", "Purchase Order", "Sales Invoice"},
        )
        self.cancel_calls = 0
        self.saved = False
        self.delete_calls = []

    def has_permission(self, permission):
        return permission in {"read", "write", "submit", "cancel", "delete"}

    def check_permission(self, permission):
        if not self.has_permission(permission):
            raise PermissionError(permission)

    def cancel(self):
        self.cancel_calls += 1
        self.docstatus = FakeDocStatus(2)

    def save(self, **kwargs):
        self.saved = True

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)

    def get(self, fieldname):
        return getattr(self, fieldname, None)

    def set(self, fieldname, value):
        setattr(self, fieldname, value)


class FakeChildRow:
    def __init__(self, values, name="new-row"):
        self.name = name
        self.idx = values.get("idx", 1)
        self.values = values

    def get(self, fieldname):
        return self.values.get(fieldname)


class FakeChildDocument(FakeDocument):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.items = [FakeChildRow({"item_code": "OLD-ITEM", "qty": 1}, "row-1")]
        self.saved = False
        self.meta = FakeMeta(
            FakeField("remarks"),
            FakeField("items", "Table", options=f"{self.doctype} Item"),
            is_submittable=True,
        )

    def append(self, table, values):
        values = {
            **values,
            "delivery_date": values.get("delivery_date", date(2026, 9, 10)),
        }
        row = FakeChildRow(values, f"row-{len(self.items) + 1}")
        self.items.append(row)
        return row

    def remove(self, row):
        self.items.remove(row)

    def save(self, **kwargs):
        self.saved = True


class FakePurchaseOrderDocument(FakeChildDocument):
    def __init__(self, *, docstatus=0, modified="one"):
        super().__init__(
            doctype="Purchase Order", docstatus=docstatus, modified=modified
        )
        self.schedule_date = "2026-09-10"
        self.currency = "INR"
        self.native_calls = []
        self.meta = FakeMeta(
            FakeField("schedule_date"),
            FakeField("currency"),
            FakeField("supplier_address", "Link", options="Address"),
            FakeField("items", "Table", options="Purchase Order Item"),
            is_submittable=True,
        )

    def set_missing_values(self):
        self.native_calls.append("set_missing_values")

    def calculate_taxes_and_totals(self):
        self.native_calls.append("calculate_taxes_and_totals")

    def run_method(self, method):
        self.native_calls.append(method)


class LifecycleServiceTests(unittest.TestCase):
    def setUp(self):
        self.doc = FakeDocument()
        self.approval_backend = FakeSharedApprovalBackend()
        self.update_mode_patch = patch.dict(
            os.environ, {"MCP_UPDATE_MODE": "approval_required"}, clear=False
        )
        self.update_mode_patch.start()
        self.store = ApprovalStore(
            ApprovalMode.AGENT_DELEGATED, backend=self.approval_backend
        )
        self.database = SimpleNamespace(commit=Mock(), rollback=Mock())
        self.frappe_patches = [
            patch.object(lifecycle.frappe, "get_doc", return_value=self.doc),
            patch.object(
                lifecycle.frappe,
                "get_meta",
                return_value=FakeMeta(FakeField("item_code"), FakeField("qty")),
            ),
            patch.object(lifecycle.frappe, "db", self.database),
            patch.object(
                lifecycle.frappe, "get_list", return_value=[{"name": "CUST-001"}]
            ),
            patch.object(
                lifecycle.frappe,
                "local",
                SimpleNamespace(
                    site="test.localhost",
                    db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
                ),
            ),
            patch.object(
                lifecycle.frappe, "session", SimpleNamespace(user="user@example.com")
            ),
            patch.object(lifecycle, "approvals", self.store),
            patch.object(lifecycle, "get_linked_docs", return_value=[]),
            patch.object(lifecycle, "get_dynamic_linked_docs", return_value=[]),
        ]
        for item in self.frappe_patches:
            item.start()

    def tearDown(self):
        self.update_mode_patch.stop()
        for item in reversed(self.frappe_patches):
            item.stop()

    def test_prepare_update_is_exact_and_does_not_mutate(self):
        result = lifecycle.prepare_update(
            {"doctype": "Sales Order", "name": "SO-001"},
            [{"field": "remarks", "value": "Urgent delivery"}],
            "sales",
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["preview"]["changes"][0]["old"], "")
        self.assertEqual(result["preview"]["changes"][0]["new"], "Urgent delivery")
        self.assertEqual(self.doc.remarks, "")

    def test_update_default_disabled_before_load_or_approval(self):
        with patch.dict(os.environ, {}, clear=True):
            result = lifecycle.prepare_update(
                {"doctype": "Sales Order", "name": "SO-001"},
                [{"field": "remarks", "value": "Urgent delivery"}],
                "sales",
            )
        self.assertEqual(result["code"], "UPDATE_DISABLED")
        self.assertEqual(
            result["message"],
            "Updating this document is unavailable in the current setup.",
        )
        self.assertFalse(result["retryable"])
        lifecycle.frappe.get_doc.assert_not_called()
        self.assertTrue(self.approval_backend.is_empty())

    def test_direct_update_preview_and_execute_do_not_use_approval_store(self):
        with (
            patch.dict(os.environ, {"MCP_UPDATE_MODE": "direct"}, clear=False),
            patch.object(
                lifecycle.approvals, "create", wraps=lifecycle.approvals.create
            ) as create,
        ):
            preview = lifecycle.prepare_update(
                {"doctype": "Sales Order", "name": "SO-001"},
                [{"field": "remarks", "value": "Direct update"}],
                "sales",
            )
            self.assertEqual(preview["status"], "ready")
            self.assertNotIn("approval_token", preview)
            self.assertNotIn("interaction", preview)
            result = lifecycle.execute_update(
                {"doctype": "Sales Order", "name": "SO-001"},
                [{"field": "remarks", "value": "Direct update"}],
                "sales",
            )
        self.assertEqual(result["status"], "updated")
        create.assert_not_called()

    def test_direct_update_final_mode_flip_blocks_before_save(self):
        original_plan = lifecycle._plan_update

        def plan_and_flip(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            os.environ["MCP_UPDATE_MODE"] = "approval_required"
            return result

        with (
            patch.dict(os.environ, {"MCP_UPDATE_MODE": "direct"}, clear=False),
            patch.object(lifecycle, "_plan_update", side_effect=plan_and_flip),
        ):
            result = lifecycle.execute_update(
                {"doctype": "Sales Order", "name": "SO-001"},
                [{"field": "remarks", "value": "Direct update"}],
                "sales",
            )
        self.assertEqual(result["code"], "APPROVAL_REQUIRED")
        self.assertFalse(self.doc.saved)
        self.database.commit.assert_not_called()

    def test_direct_mode_rejects_token_confirmation(self):
        with (
            patch.dict(os.environ, {"MCP_UPDATE_MODE": "direct"}, clear=False),
            patch.object(lifecycle.approvals, "claim_for_confirm_write") as claim,
        ):
            result = lifecycle.confirm("update", "opaque", True, "sales")
        self.assertEqual(result["code"], "DIRECT_EXECUTION_REQUIRED")
        claim.assert_not_called()

    def test_update_mode_gates_child_add(self):
        self.doc = FakeChildDocument()
        lifecycle.frappe.get_doc.return_value = self.doc
        lifecycle.frappe.get_list.return_value = [
            {
                "name": "NEW-ITEM",
                "item_code": "NEW-ITEM",
                "item_name": "New",
                "stock_uom": "Nos",
            }
        ]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty")
        )
        with patch.dict(os.environ, {"MCP_UPDATE_MODE": "disabled"}, clear=False):
            result = lifecycle.prepare_child_add(
                {"doctype": "Sales Order", "name": "SO-001"},
                {"doctype": "Item", "name": "NEW-ITEM"},
                2,
                None,
                "sales",
            )
        self.assertEqual(result["code"], "UPDATE_DISABLED")

    def test_sales_invoice_update_is_available_to_sales_profile(self):
        result = lifecycle.prepare_update(
            {"doctype": "Sales Invoice", "name": "SINV-001"},
            [{"field": "remarks", "value": "x"}],
            "sales",
        )
        self.assertEqual(result["status"], "ready")

    def test_sales_invoice_policy_allows_only_submit_cancel_delete(self):
        for action in ("submit", "cancel", "delete"):
            with self.subTest(action=action):
                self.assertTrue(
                    lifecycle.is_action_allowed("sales", "Sales Invoice", action)
                )
        for action in ("update", "child_add"):
            with self.subTest(action=action):
                self.assertTrue(
                    lifecycle.is_action_allowed("sales", "Sales Invoice", action)
                )

    def test_sales_invoice_submit_reaches_existing_prepare_flow(self):
        result = lifecycle.prepare_submit(
            {"doctype": "Sales Invoice", "name": "SINV-001"}, "sales"
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["preview"]["action"], "SUBMIT")

    def test_submit_approval_is_independent_of_create_mode(self):
        for mode in ("disabled", "direct"):
            with (
                self.subTest(mode=mode),
                patch.dict(os.environ, {"MCP_CREATE_MODE": mode}),
            ):
                result = lifecycle.prepare_submit(
                    {"doctype": "Sales Invoice", "name": "SINV-001"}, "sales"
                )
                self.assertEqual(result["status"], "ready")
                self.assertIn("approval_token", result)

    def test_sales_invoice_update_and_child_add_are_denied_before_approval(self):
        update = lifecycle.prepare_update(
            {"doctype": "Sales Invoice", "name": "SINV-001"},
            [{"field": "remarks", "value": "x"}],
            "sales",
        )
        child_add = lifecycle.prepare_child_add(
            {"doctype": "Sales Invoice", "name": "SINV-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            1,
            None,
            "sales",
        )
        self.assertEqual(update["status"], "ready")
        self.assertEqual(child_add["code"], "INVALID_CHILD_TARGET")

    def test_lifecycle_approval_cannot_be_reused_for_another_action(self):
        prepared = lifecycle.prepare_submit(
            {"doctype": "Sales Invoice", "name": "SINV-001"}, "sales"
        )
        result = lifecycle.confirm("update", prepared["approval_token"], True, "sales")
        self.assertEqual(result["code"], "CONFIRMATION_UNAVAILABLE")

    def test_system_field_is_not_writable(self):
        result = lifecycle.prepare_update(
            {"doctype": "Sales Order", "name": "SO-001"},
            [{"field": "docstatus", "value": 1}],
            "sales",
        )
        self.assertEqual(result["code"], "FIELD_NOT_WRITABLE")

    def test_customer_cannot_be_submitted(self):
        self.doc = FakeDocument("Customer", "CUST-001")
        lifecycle.frappe.get_doc.return_value = self.doc
        result = lifecycle.prepare_submit(
            {"doctype": "Customer", "name": "CUST-001"}, "sales"
        )
        self.assertEqual(result["code"], "NOT_SUBMITTABLE")

    def test_confirmation_rejects_stale_document(self):
        prepared = lifecycle.prepare_update(
            {"doctype": "Sales Order", "name": "SO-001"},
            [{"field": "remarks", "value": "Urgent delivery"}],
            "sales",
        )
        self.doc.modified = "two"
        result = lifecycle.confirm("update", prepared["approval_token"], True, "sales")
        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        self.assertEqual(self.doc.remarks, "")

    def test_prepare_child_add_is_preview_only_and_binds_profile(self):
        self.doc = FakeChildDocument()
        lifecycle.frappe.get_doc.return_value = self.doc
        lifecycle.frappe.get_list.return_value = [
            {
                "name": "NEW-ITEM",
                "item_code": "NEW-ITEM",
                "item_name": "New",
                "stock_uom": "Nos",
            }
        ]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"),
            FakeField("qty"),
            FakeField("rate"),
        )
        result = lifecycle.prepare_child_add(
            {"doctype": "Sales Order", "name": "SO-001"},
            {"doctype": "Item", "name": "NEW-ITEM"},
            2,
            None,
            "sales",
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["preview"]["action"], "ADD_ITEM")
        self.assertEqual(result["preview"]["new_row"]["item_code"], "NEW-ITEM")
        self.assertEqual(len(self.doc.items), 2)
        self.assertFalse(self.doc.saved)
        approval, state = lifecycle.approvals.lookup(
            result["approval_token"],
            action="lifecycle_child_add",
            site="test.localhost",
            user="user@example.com",
        )
        self.assertEqual(state, "available")
        self.assertEqual(approval.payload["profile"], "sales")

    def test_confirm_child_add_uses_native_save_and_preserves_old_row(self):
        self.doc = FakeChildDocument()
        confirm_doc = FakeChildDocument()
        lifecycle.frappe.get_doc.side_effect = [self.doc, confirm_doc]
        lifecycle.frappe.get_list.return_value = [
            {
                "name": "NEW-ITEM",
                "item_code": "NEW-ITEM",
                "item_name": "New",
                "stock_uom": "Nos",
            }
        ]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty")
        )
        prepared = lifecycle.prepare_child_add(
            {"doctype": "Sales Order", "name": "SO-001"},
            {"doctype": "Item", "name": "NEW-ITEM"},
            2,
            None,
            "sales",
        )
        result = lifecycle.confirm(
            "child_add", prepared["approval_token"], True, "sales"
        )
        self.assertEqual(result["status"], "added", result)
        self.assertTrue(confirm_doc.saved)
        self.assertEqual(
            [row.get("item_code") for row in confirm_doc.items],
            ["OLD-ITEM", "NEW-ITEM"],
        )

    def test_child_add_rejects_duplicate_and_non_draft(self):
        self.doc = FakeChildDocument()
        self.doc.items.append(
            FakeChildRow({"item_code": "NEW-ITEM", "qty": 1}, "row-2")
        )
        lifecycle.frappe.get_doc.return_value = self.doc
        lifecycle.frappe.get_list.return_value = [
            {
                "name": "NEW-ITEM",
                "item_code": "NEW-ITEM",
                "item_name": "New",
                "stock_uom": "Nos",
            }
        ]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty")
        )
        duplicate = lifecycle.prepare_child_add(
            {"doctype": "Sales Order", "name": "SO-001"},
            {"doctype": "Item", "name": "NEW-ITEM"},
            2,
            None,
            "sales",
        )
        self.assertEqual(duplicate["code"], "DUPLICATE_ITEM_ROW")
        self.doc.docstatus = FakeDocStatus(1)
        submitted = lifecycle.prepare_child_add(
            {"doctype": "Sales Order", "name": "SO-001"},
            {"doctype": "Item", "name": "OTHER-ITEM"},
            2,
            None,
            "sales",
        )
        self.assertEqual(submitted["code"], "INVALID_DOCUMENT_STATE")

    def test_child_remove_is_preview_only_then_removes_the_exact_row(self):
        self.doc = FakeChildDocument()
        confirm_doc = FakeChildDocument()
        lifecycle.frappe.get_doc.side_effect = [self.doc, confirm_doc]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty")
        )
        prepared = lifecycle.prepare_child_remove(
            {"doctype": "Sales Order", "name": "SO-001"},
            "items",
            {"row_name": "row-1"},
            "sales",
        )
        self.assertEqual(prepared["status"], "ready")
        self.assertEqual(prepared["preview"]["removed_row"]["item_code"], "OLD-ITEM")
        self.assertFalse(self.doc.saved)
        result = lifecycle.confirm(
            "child_remove", prepared["approval_token"], True, "sales"
        )
        self.assertEqual(result["status"], "removed")
        self.assertTrue(confirm_doc.saved)
        self.assertEqual(confirm_doc.items, [])

    def test_child_remove_rejects_non_draft(self):
        self.doc = FakeChildDocument(docstatus=1)
        lifecycle.frappe.get_doc.return_value = self.doc
        self.assertEqual(
            lifecycle.prepare_child_remove(
                {"doctype": "Sales Order", "name": "SO-001"},
                "items",
                {"row_name": "row-1"},
                "sales",
            )["code"],
            "INVALID_DOCUMENT_STATE",
        )

    def test_confirm_child_add_restores_date_fields_before_append(self):
        self.doc = FakeChildDocument()
        confirm_doc = FakeChildDocument()
        lifecycle.frappe.get_doc.side_effect = [self.doc, confirm_doc]
        lifecycle.frappe.get_list.return_value = [
            {"name": "NEW-ITEM", "item_code": "NEW-ITEM"}
        ]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty"), FakeField("delivery_date", "Date")
        )
        prepared = lifecycle.prepare_child_add(
            {"doctype": "Sales Order", "name": "SO-001"},
            {"doctype": "Item", "name": "NEW-ITEM"},
            2,
            None,
            "sales",
        )
        approval, state = lifecycle.approvals.lookup(
            prepared["approval_token"],
            action="lifecycle_child_add",
            site="test.localhost",
            user="user@example.com",
        )
        self.assertEqual(state, "available")
        self.assertEqual(approval.payload["row"]["delivery_date"], "2026-09-10")
        result = lifecycle.confirm(
            "child_add", prepared["approval_token"], True, "sales"
        )
        self.assertEqual(result["status"], "added")
        self.assertIsInstance(confirm_doc.items[-1].get("delivery_date"), date)

    def test_all_profile_lifecycle_is_the_exact_existing_action_union(self):
        self.assertTrue(lifecycle.is_action_allowed("all", "Purchase Order", "submit"))
        self.assertTrue(lifecycle.is_action_allowed("all", "Payment Entry", "delete"))
        self.assertTrue(
            lifecycle.is_action_allowed("all", "Sales Order", "child_remove")
        )
        self.assertFalse(lifecycle.is_action_allowed("all", "Payment Entry", "update"))
        self.assertFalse(
            lifecycle.is_action_allowed("all", "Payment Entry", "child_add")
        )

    def test_purchase_order_update_uses_allowlist_draft_guard_and_native_refresh(self):
        prepare_doc = FakePurchaseOrderDocument()
        confirm_doc = FakePurchaseOrderDocument()
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        prepared = lifecycle.prepare_update(
            {"doctype": "Purchase Order", "name": "PO-001"},
            [{"field": "schedule_date", "value": "2026-09-12"}],
            "purchase",
        )
        self.assertEqual(prepared["status"], "ready")
        self.assertEqual(
            prepare_doc.native_calls,
            ["set_missing_values", "calculate_taxes_and_totals", "validate"],
        )
        updated = lifecycle.confirm(
            "update", prepared["approval_token"], True, "purchase"
        )
        self.assertEqual(updated["status"], "updated")
        self.assertTrue(confirm_doc.saved)
        self.assertEqual(confirm_doc.schedule_date, "2026-09-12")
        self.assertEqual(
            confirm_doc.native_calls,
            ["set_missing_values", "calculate_taxes_and_totals", "validate"],
        )

    def test_native_validation_exception_is_logged_and_sanitized(self):
        purchase_order = FakePurchaseOrderDocument()
        purchase_order.run_method = Mock(
            side_effect=RuntimeError("SQL password=private diagnostic")
        )
        lifecycle.frappe.get_doc.return_value = purchase_order
        with patch("mcp_erpnext.observability._log_tool_failure") as log_failure:
            result = lifecycle.prepare_update(
                {"doctype": "Purchase Order", "name": "PO-001"},
                [{"field": "schedule_date", "value": "2026-09-12"}],
                "purchase",
            )

        self.assertEqual(result["code"], "LIFECYCLE_VALIDATION_FAILED")
        self.assertEqual(
            result["message"],
            PUBLIC_ERROR_DEFINITIONS["LIFECYCLE_VALIDATION_FAILED"].message,
        )
        self.assertNotIn("SQL password", result["message"])
        self.assertEqual(log_failure.call_args.kwargs["reference"], result["reference"])
        self.assertEqual(log_failure.call_args.kwargs["code"], result["code"])

    def test_linked_document_exception_is_logged_and_sanitized(self):
        doc = FakeDocument()
        doc.delete = Mock(
            side_effect=lifecycle.frappe.LinkExistsError("linked name=private diagnostic")
        )
        with (
            patch.dict(os.environ, {"MCP_DELETE_MODE": "direct"}, clear=False),
            patch("mcp_erpnext.observability._log_tool_failure") as log_failure,
        ):
            result = lifecycle._apply_mutation(
                "delete", {"plan": "delete"}, doc, "sales"
            )

        self.assertEqual(result["code"], "LINKED_DOCUMENT")
        self.assertEqual(
            result["message"], PUBLIC_ERROR_DEFINITIONS["LINKED_DOCUMENT"].message
        )
        self.assertNotIn("private diagnostic", result["message"])
        self.assertEqual(log_failure.call_args.kwargs["reference"], result["reference"])
        self.database.rollback.assert_called_once_with()

    def test_purchase_order_update_rejects_system_commercial_child_and_non_draft_changes(
        self,
    ):
        lifecycle.frappe.get_doc.return_value = FakePurchaseOrderDocument()
        for change in (
            {"field": "currency", "value": "USD"},
            {"field": "docstatus", "value": 1},
            {
                "field": "qty",
                "value": 2,
                "child_table": "items",
                "row": {"row_name": "row-1"},
            },
        ):
            with self.subTest(change=change):
                result = lifecycle.prepare_update(
                    {"doctype": "Purchase Order", "name": "PO-001"},
                    [change],
                    "purchase",
                )
                self.assertEqual(result["code"], "FIELD_NOT_WRITABLE")
        for status in (1, 2):
            with self.subTest(docstatus=status):
                lifecycle.frappe.get_doc.return_value = FakePurchaseOrderDocument(
                    docstatus=status
                )
                result = lifecycle.prepare_update(
                    {"doctype": "Purchase Order", "name": "PO-001"},
                    [{"field": "schedule_date", "value": "2026-09-12"}],
                    "purchase",
                )
                self.assertEqual(result["code"], "INVALID_DOCUMENT_STATE")

    def test_purchase_order_update_confirmation_rejects_stale_and_permission_denial(
        self,
    ):
        prepare_doc = FakePurchaseOrderDocument()
        stale_doc = FakePurchaseOrderDocument(modified="two")
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, stale_doc]
        prepared = lifecycle.prepare_update(
            {"doctype": "Purchase Order", "name": "PO-001"},
            [{"field": "schedule_date", "value": "2026-09-12"}],
            "purchase",
        )
        stale = lifecycle.confirm(
            "update", prepared["approval_token"], True, "purchase"
        )
        self.assertEqual(stale["code"], "STALE_CONFIRMATION")
        denied = FakePurchaseOrderDocument()
        denied.has_permission = lambda permission: permission != "write"
        lifecycle.frappe.get_doc.side_effect = None
        lifecycle.frappe.get_doc.return_value = denied
        result = lifecycle.prepare_update(
            {"doctype": "Purchase Order", "name": "PO-001"},
            [{"field": "schedule_date", "value": "2026-09-12"}],
            "purchase",
        )
        self.assertEqual(result["code"], "PERMISSION_DENIED")

    def test_purchase_order_child_add_is_bounded_and_recalculates_natively(self):
        self.doc = FakePurchaseOrderDocument()
        lifecycle.frappe.get_doc.return_value = self.doc
        lifecycle.frappe.get_list.return_value = [
            {
                "name": "ITEM-001",
                "item_code": "ITEM-001",
                "item_name": "Item",
                "stock_uom": "Nos",
            }
        ]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty"), FakeField("rate")
        )
        prepared = lifecycle.prepare_child_add(
            {"doctype": "Purchase Order", "name": "PO-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            2,
            None,
            "purchase",
        )
        self.assertEqual(prepared["status"], "ready")
        self.assertEqual(prepared["preview"]["new_row"]["item_code"], "ITEM-001")
        self.assertEqual(
            lifecycle.frappe.get_list.call_args.kwargs["filters"]["is_purchase_item"], 1
        )
        self.assertEqual(
            self.doc.native_calls,
            ["set_missing_values", "calculate_taxes_and_totals", "validate"],
        )

    def test_purchase_order_child_add_confirm_rechecks_item_and_saves_natively(self):
        prepare_doc = FakePurchaseOrderDocument()
        confirm_doc = FakePurchaseOrderDocument()
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        item = {
            "name": "ITEM-001",
            "item_code": "ITEM-001",
            "item_name": "Item",
            "stock_uom": "Nos",
            "modified": "item-one",
        }
        lifecycle.frappe.get_list.side_effect = [[item], [item]]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty"), FakeField("rate")
        )
        prepared = lifecycle.prepare_child_add(
            {"doctype": "Purchase Order", "name": "PO-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            2,
            None,
            "purchase",
        )
        result = lifecycle.confirm(
            "child_add", prepared["approval_token"], True, "purchase"
        )
        self.assertEqual(result["status"], "added")
        self.assertEqual(
            [row.get("item_code") for row in confirm_doc.items],
            ["OLD-ITEM", "ITEM-001"],
        )
        self.assertTrue(confirm_doc.saved)
        self.assertIn("validate", confirm_doc.native_calls)

    def test_purchase_order_child_add_rejects_item_disabled_after_prepare(self):
        prepare_doc = FakePurchaseOrderDocument()
        confirm_doc = FakePurchaseOrderDocument()
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        item = {
            "name": "ITEM-001",
            "item_code": "ITEM-001",
            "item_name": "Item",
            "stock_uom": "Nos",
            "modified": "item-one",
        }
        lifecycle.frappe.get_list.side_effect = [[item], []]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty")
        )
        prepared = lifecycle.prepare_child_add(
            {"doctype": "Purchase Order", "name": "PO-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            2,
            None,
            "purchase",
        )
        result = lifecycle.confirm(
            "child_add", prepared["approval_token"], True, "purchase"
        )
        self.assertEqual(result["code"], "INVALID_ITEM")
        self.assertEqual(len(confirm_doc.items), 1)

    def test_purchase_order_child_add_rejects_item_changed_after_prepare(self):
        prepare_doc = FakePurchaseOrderDocument()
        confirm_doc = FakePurchaseOrderDocument()
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        old_item = {
            "name": "ITEM-001",
            "item_code": "ITEM-001",
            "item_name": "Item",
            "stock_uom": "Nos",
            "modified": "item-one",
        }
        changed_item = {**old_item, "modified": "item-two"}
        lifecycle.frappe.get_list.side_effect = [[old_item], [changed_item]]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty")
        )
        prepared = lifecycle.prepare_child_add(
            {"doctype": "Purchase Order", "name": "PO-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            2,
            None,
            "purchase",
        )
        result = lifecycle.confirm(
            "child_add", prepared["approval_token"], True, "purchase"
        )
        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        self.assertEqual(len(confirm_doc.items), 1)

    def test_purchase_child_add_contract_rejects_arbitrary_child_targets_and_fields(
        self,
    ):
        with self.assertRaises(ValidationError):
            PrepareChildAddInput.model_validate(
                {
                    "target": {"doctype": "Purchase Order", "name": "PO-001"},
                    "item": {"doctype": "Item", "name": "ITEM-001"},
                    "qty": 1,
                    "child_table": "taxes",
                    "row": {"rate": 0},
                }
            )

    def test_purchase_child_add_rejects_invalid_native_items_table_metadata(self):
        self.doc = FakePurchaseOrderDocument()
        self.doc.meta = FakeMeta(
            FakeField("items", "Table", options="Purchase Taxes and Charges"),
            is_submittable=True,
        )
        lifecycle.frappe.get_doc.return_value = self.doc
        result = lifecycle.prepare_child_add(
            {"doctype": "Purchase Order", "name": "PO-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            1,
            None,
            "purchase",
        )
        self.assertEqual(result["code"], "INVALID_CHILD_TARGET")

    def test_purchase_order_child_add_rejects_ineligible_items_state_and_target(self):
        self.doc = FakePurchaseOrderDocument()
        lifecycle.frappe.get_doc.return_value = self.doc
        lifecycle.frappe.get_list.return_value = []
        invalid_item = lifecycle.prepare_child_add(
            {"doctype": "Purchase Order", "name": "PO-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            2,
            None,
            "purchase",
        )
        self.assertEqual(invalid_item["code"], "INVALID_ITEM")
        filters = lifecycle.frappe.get_list.call_args.kwargs["filters"]
        self.assertEqual(filters["is_purchase_item"], 1)
        self.assertEqual(filters["disabled"], ["!=", 1])
        for status in (1, 2):
            lifecycle.frappe.get_doc.return_value = FakePurchaseOrderDocument(
                docstatus=status
            )
            result = lifecycle.prepare_child_add(
                {"doctype": "Purchase Order", "name": "PO-001"},
                {"doctype": "Item", "name": "ITEM-001"},
                2,
                None,
                "purchase",
            )
            self.assertEqual(result["code"], "INVALID_DOCUMENT_STATE")
        lifecycle.frappe.get_doc.return_value = FakeChildDocument(doctype="Supplier")
        result = lifecycle.prepare_child_add(
            {"doctype": "Supplier", "name": "SUP-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            2,
            None,
            "purchase",
        )
        self.assertEqual(result["code"], "CHILD_TARGET_NOT_ALLOWED")
        denied = FakePurchaseOrderDocument()
        denied.has_permission = lambda permission: permission != "write"
        lifecycle.frappe.get_doc.side_effect = None
        lifecycle.frappe.get_doc.return_value = denied
        result = lifecycle.prepare_child_add(
            {"doctype": "Purchase Order", "name": "PO-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            2,
            None,
            "purchase",
        )
        self.assertEqual(result["code"], "PERMISSION_DENIED")

    def test_purchase_order_child_add_confirmation_rejects_stale_parent(self):
        prepare_doc = FakePurchaseOrderDocument()
        stale_doc = FakePurchaseOrderDocument(modified="two")
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, stale_doc]
        lifecycle.frappe.get_list.return_value = [
            {
                "name": "ITEM-001",
                "item_code": "ITEM-001",
                "item_name": "Item",
                "stock_uom": "Nos",
            }
        ]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty")
        )
        prepared = lifecycle.prepare_child_add(
            {"doctype": "Purchase Order", "name": "PO-001"},
            {"doctype": "Item", "name": "ITEM-001"},
            2,
            None,
            "purchase",
        )
        result = lifecycle.confirm(
            "child_add", prepared["approval_token"], True, "purchase"
        )
        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        self.assertEqual(len(stale_doc.items), 1)

    def test_purchase_order_child_remove_is_exact_approved_and_stale_safe(self):
        prepare_doc = FakePurchaseOrderDocument()
        confirm_doc = FakePurchaseOrderDocument()
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty")
        )
        prepared = lifecycle.prepare_child_remove(
            {"doctype": "Purchase Order", "name": "PO-001"},
            "items",
            {"row_name": "row-1"},
            "purchase",
        )
        self.assertEqual(prepared["status"], "ready")
        removed = lifecycle.confirm(
            "child_remove", prepared["approval_token"], True, "purchase"
        )
        self.assertEqual(removed["status"], "removed")
        self.assertEqual(confirm_doc.items, [])
        self.assertTrue(confirm_doc.saved)
        self.assertIn("validate", confirm_doc.native_calls)
        self.assertTrue(
            lifecycle.is_action_allowed("all", "Purchase Order", "child_remove")
        )

    def test_purchase_order_child_remove_rejects_wrong_table_state_and_stale_row(self):
        self.doc = FakePurchaseOrderDocument()
        lifecycle.frappe.get_doc.return_value = self.doc
        self.assertEqual(
            lifecycle.prepare_child_remove(
                {"doctype": "Purchase Order", "name": "PO-001"},
                "taxes",
                {"row_name": "row-1"},
                "purchase",
            )["code"],
            "CHILD_TARGET_NOT_ALLOWED",
        )
        self.doc = FakePurchaseOrderDocument(docstatus=1)
        lifecycle.frappe.get_doc.return_value = self.doc
        self.assertEqual(
            lifecycle.prepare_child_remove(
                {"doctype": "Purchase Order", "name": "PO-001"},
                "items",
                {"row_name": "row-1"},
                "purchase",
            )["code"],
            "INVALID_DOCUMENT_STATE",
        )
        prepare_doc = FakePurchaseOrderDocument()
        changed_doc = FakePurchaseOrderDocument()
        changed_doc.items[0].values["qty"] = 3
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, changed_doc]
        lifecycle.frappe.get_meta.return_value = FakeMeta(
            FakeField("item_code"), FakeField("qty")
        )
        prepared = lifecycle.prepare_child_remove(
            {"doctype": "Purchase Order", "name": "PO-001"},
            "items",
            {"row_name": "row-1"},
            "purchase",
        )
        stale = lifecycle.confirm(
            "child_remove", prepared["approval_token"], True, "purchase"
        )
        self.assertEqual(stale["code"], "STALE_CONFIRMATION")

    def test_cancel_and_delete_default_disabled_before_load_or_approval(self):
        with patch.dict(os.environ, {}, clear=True):
            for action, code, message in (
                (
                    "cancel",
                    "CANCEL_DISABLED",
                    "Cancelling this document is unavailable in the current setup.",
                ),
                (
                    "delete",
                    "DELETE_DISABLED",
                    "Deleting this document is unavailable in the current setup.",
                ),
            ):
                with self.subTest(action=action):
                    result = getattr(lifecycle, f"prepare_{action}")(
                        {"doctype": "Sales Order", "name": "SO-001"}, "sales"
                    )
                    self.assertEqual(result["code"], code)
                    self.assertEqual(result["message"], message)
                    self.assertFalse(result["retryable"])
        self.assertFalse(lifecycle.frappe.get_doc.called)
        self.assertFalse(lifecycle.get_linked_docs.called)
        self.assertFalse(lifecycle.get_dynamic_linked_docs.called)
        self.assertTrue(self.approval_backend.is_empty())

    def test_enabled_modes_keep_action_allowlists_before_document_load(self):
        with patch.dict(
            os.environ,
            {
                "MCP_CANCEL_MODE": "approval_required",
                "MCP_DELETE_MODE": "approval_required",
            },
            clear=False,
        ):
            for action in ("cancel", "delete"):
                with self.subTest(action=action):
                    result = getattr(lifecycle, f"prepare_{action}")(
                        {"doctype": "Payment Entry", "name": "PE-001"}, "sales"
                    )
                    self.assertEqual(result["code"], "DOCTYPE_NOT_ALLOWED")
        self.assertFalse(lifecycle.frappe.get_doc.called)
        self.assertTrue(self.approval_backend.is_empty())

    def test_enabled_update_keeps_action_allowlist_before_document_load(self):
        result = lifecycle.prepare_update(
            {"doctype": "Payment Entry", "name": "PE-001"},
            [{"field": "remarks", "value": "x"}],
            "sales",
        )
        self.assertEqual(result["code"], "DOCTYPE_NOT_ALLOWED")
        lifecycle.frappe.get_doc.assert_not_called()
        self.assertTrue(self.approval_backend.is_empty())

    def test_action_permissions_precede_blocker_enumeration(self):
        with patch.dict(
            os.environ,
            {
                "MCP_CANCEL_MODE": "approval_required",
                "MCP_DELETE_MODE": "approval_required",
            },
            clear=False,
        ):
            for action, docstatus, denied_permission in (
                ("cancel", 1, "cancel"),
                ("delete", 0, "delete"),
                ("delete", 1, "cancel"),
            ):
                with self.subTest(
                    action=action,
                    docstatus=docstatus,
                    denied_permission=denied_permission,
                ):
                    doc = FakeDocument(docstatus=docstatus)
                    doc.has_permission = (
                        lambda permission, denied=denied_permission: permission
                        != denied
                    )
                    lifecycle.frappe.get_doc.return_value = doc
                    lifecycle.get_linked_docs.reset_mock()
                    lifecycle.get_dynamic_linked_docs.reset_mock()
                    result = getattr(lifecycle, f"prepare_{action}")(
                        {"doctype": "Sales Order", "name": "SO-001"}, "sales"
                    )
                    self.assertEqual(result["code"], "PERMISSION_DENIED")
                    lifecycle.get_linked_docs.assert_not_called()
                    lifecycle.get_dynamic_linked_docs.assert_not_called()

    def test_enabled_cancel_preserves_preview_approval_native_write_and_commit(self):
        prepare_doc = FakeDocument(docstatus=1)
        confirm_doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        with patch.dict(
            os.environ, {"MCP_CANCEL_MODE": "approval_required"}, clear=False
        ):
            prepared = lifecycle.prepare_cancel(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
            result = lifecycle.confirm(
                "cancel", prepared["approval_token"], True, "sales"
            )
        self.assertEqual(prepared["status"], "ready")
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(confirm_doc.cancel_calls, 1)
        self.database.commit.assert_called_once_with()
        self.database.rollback.assert_not_called()

    def test_direct_cancel_final_mode_flip_blocks_before_native_cancel(self):
        doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.return_value = doc
        original_plan = lifecycle._plan_action

        def plan_and_flip(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            os.environ["MCP_CANCEL_MODE"] = "approval_required"
            return result

        with (
            patch.dict(os.environ, {"MCP_CANCEL_MODE": "direct"}, clear=False),
            patch.object(lifecycle, "_plan_action", side_effect=plan_and_flip),
        ):
            result = lifecycle.execute_cancel(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
        self.assertEqual(result["code"], "APPROVAL_REQUIRED")
        self.assertEqual(doc.cancel_calls, 0)
        self.database.commit.assert_not_called()

    def test_direct_delete_final_mode_flip_blocks_before_native_delete(self):
        doc = FakeDocument(docstatus=0)
        lifecycle.frappe.get_doc.return_value = doc
        original_plan = lifecycle._plan_action

        def plan_and_flip(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            os.environ["MCP_DELETE_MODE"] = "approval_required"
            return result

        with (
            patch.dict(os.environ, {"MCP_DELETE_MODE": "direct"}, clear=False),
            patch.object(lifecycle, "_plan_action", side_effect=plan_and_flip),
        ):
            result = lifecycle.execute_delete(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
        self.assertEqual(result["code"], "APPROVAL_REQUIRED")
        self.assertEqual(doc.delete_calls, [])
        self.database.commit.assert_not_called()

    def test_approval_update_final_mode_flip_blocks_before_save(self):
        prepared = lifecycle.prepare_update(
            {"doctype": "Sales Order", "name": "SO-001"},
            [{"field": "remarks", "value": "Approved update"}],
            "sales",
        )
        original_revalidate = lifecycle._revalidate

        def revalidate_and_flip(*args, **kwargs):
            result = original_revalidate(*args, **kwargs)
            os.environ["MCP_UPDATE_MODE"] = "direct"
            return result

        with patch.object(lifecycle, "_revalidate", side_effect=revalidate_and_flip):
            result = lifecycle.confirm(
                "update", prepared["approval_token"], True, "sales"
            )
        self.assertEqual(result["code"], "DIRECT_EXECUTION_REQUIRED")
        self.assertFalse(self.doc.saved)
        self.database.commit.assert_not_called()

    def test_approval_cancel_final_mode_flip_blocks_before_native_cancel(self):
        prepare_doc = FakeDocument(docstatus=1)
        confirm_doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        with patch.dict(
            os.environ, {"MCP_CANCEL_MODE": "approval_required"}, clear=False
        ):
            prepared = lifecycle.prepare_cancel(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
        original_revalidate = lifecycle._revalidate

        def revalidate_and_flip(*args, **kwargs):
            result = original_revalidate(*args, **kwargs)
            os.environ["MCP_CANCEL_MODE"] = "direct"
            return result

        with (
            patch.dict(
                os.environ, {"MCP_CANCEL_MODE": "approval_required"}, clear=False
            ),
            patch.object(lifecycle, "_revalidate", side_effect=revalidate_and_flip),
        ):
            result = lifecycle.confirm(
                "cancel", prepared["approval_token"], True, "sales"
            )
        self.assertEqual(result["code"], "DIRECT_EXECUTION_REQUIRED")
        self.assertEqual(confirm_doc.cancel_calls, 0)
        self.database.commit.assert_not_called()

    def test_direct_delete_needs_only_delete_mode_and_uses_native_permissions(self):
        prepare_doc = FakeDocument(docstatus=0)
        confirm_doc = FakeDocument(docstatus=0)
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        with patch.dict(
            os.environ,
            {"MCP_CANCEL_MODE": "disabled", "MCP_DELETE_MODE": "approval_required"},
            clear=False,
        ):
            prepared = lifecycle.prepare_delete(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
            result = lifecycle.confirm(
                "delete", prepared["approval_token"], True, "sales"
            )
        self.assertEqual(prepared["status"], "ready")
        self.assertEqual(result["status"], "deleted")
        self.assertEqual(confirm_doc.cancel_calls, 0)
        self.assertEqual(confirm_doc.delete_calls, [{"ignore_permissions": False}])
        self.database.commit.assert_called_once_with()

    def test_submitted_delete_requires_cancel_mode_before_blockers_or_token(self):
        doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.return_value = doc
        with patch.dict(
            os.environ,
            {"MCP_CANCEL_MODE": "disabled", "MCP_DELETE_MODE": "approval_required"},
            clear=False,
        ):
            result = lifecycle.prepare_delete(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
        self.assertEqual(result["code"], "CANCEL_DISABLED")
        self.assertFalse(lifecycle.get_linked_docs.called)
        self.assertFalse(lifecycle.get_dynamic_linked_docs.called)
        self.assertTrue(self.approval_backend.is_empty())
        self.assertEqual(doc.cancel_calls, 0)

    def test_submitted_direct_delete_requires_direct_cancel_mode(self):
        doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.return_value = doc
        with patch.dict(
            os.environ,
            {"MCP_DELETE_MODE": "direct", "MCP_CANCEL_MODE": "approval_required"},
            clear=False,
        ):
            result = lifecycle.prepare_delete(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
        self.assertEqual(result["code"], "APPROVAL_REQUIRED")
        self.assertEqual(doc.cancel_calls, 0)
        self.assertTrue(self.approval_backend.is_empty())

    def test_submitted_approval_delete_requires_approval_cancel_mode(self):
        doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.return_value = doc
        with patch.dict(
            os.environ,
            {"MCP_DELETE_MODE": "approval_required", "MCP_CANCEL_MODE": "direct"},
            clear=False,
        ):
            result = lifecycle.prepare_delete(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
        self.assertEqual(result["code"], "DIRECT_EXECUTION_REQUIRED")
        self.assertEqual(doc.cancel_calls, 0)
        self.assertTrue(self.approval_backend.is_empty())

    def test_matching_direct_submitted_delete_uses_native_cancel_and_delete(self):
        prepare_doc = FakeDocument(docstatus=1)
        deleted_doc = FakeDocument(docstatus=2)
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, deleted_doc]
        with patch.dict(
            os.environ,
            {"MCP_DELETE_MODE": "direct", "MCP_CANCEL_MODE": "direct"},
            clear=False,
        ):
            result = lifecycle.execute_delete(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
        self.assertEqual(result["status"], "deleted")
        self.assertEqual(prepare_doc.cancel_calls, 1)
        self.assertEqual(deleted_doc.delete_calls, [{"ignore_permissions": False}])
        self.assertTrue(self.approval_backend.is_empty())

    def test_submitted_delete_with_both_modes_uses_cancel_delete_plan(self):
        prepare_doc = FakeDocument(docstatus=1)
        confirm_doc = FakeDocument(docstatus=1)
        cancelled_doc = FakeDocument(docstatus=2)
        lifecycle.frappe.get_doc.side_effect = [
            prepare_doc,
            confirm_doc,
            cancelled_doc,
        ]
        with patch.dict(
            os.environ,
            {
                "MCP_CANCEL_MODE": "approval_required",
                "MCP_DELETE_MODE": "approval_required",
            },
            clear=False,
        ):
            prepared = lifecycle.prepare_delete(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
            result = lifecycle.confirm(
                "delete", prepared["approval_token"], True, "sales"
            )
        self.assertEqual(
            prepared["preview"]["plan"],
            [
                "Cancel Sales Order SO-001",
                "Delete Sales Order SO-001",
            ],
        )
        self.assertEqual(result["status"], "deleted")
        self.assertEqual(confirm_doc.cancel_calls, 1)
        self.assertEqual(cancelled_doc.delete_calls, [{"ignore_permissions": False}])
        self.database.commit.assert_called_once_with()

    def test_policy_disabled_after_prepare_blocks_before_approval_claim(self):
        for action, environment_name, code, docstatus in (
            ("cancel", "MCP_CANCEL_MODE", "CANCEL_DISABLED", 1),
            ("delete", "MCP_DELETE_MODE", "DELETE_DISABLED", 0),
        ):
            with self.subTest(action=action):
                doc = FakeDocument(docstatus=docstatus)
                lifecycle.frappe.get_doc.side_effect = None
                lifecycle.frappe.get_doc.return_value = doc
                with patch.dict(
                    os.environ, {environment_name: "approval_required"}, clear=False
                ):
                    prepared = getattr(lifecycle, f"prepare_{action}")(
                        {"doctype": "Sales Order", "name": "SO-001"}, "sales"
                    )
                with patch.dict(
                    os.environ, {environment_name: "disabled"}, clear=False
                ):
                    result = lifecycle.confirm(
                        action, prepared["approval_token"], True, "sales"
                    )
                self.assertEqual(result["code"], code)
                _approval, state = self.store.lookup(
                    prepared["approval_token"],
                    action=f"lifecycle_{action}",
                    site="test.localhost",
                    user="user@example.com",
                )
                self.assertEqual(state, "available")
                self.database.commit.assert_not_called()

    def test_update_policy_disabled_after_prepare_blocks_before_approval_claim(self):
        doc = FakeDocument()
        lifecycle.frappe.get_doc.return_value = doc
        prepared = lifecycle.prepare_update(
            {"doctype": "Sales Order", "name": "SO-001"},
            [{"field": "remarks", "value": "Urgent delivery"}],
            "sales",
        )
        with (
            patch.dict(os.environ, {"MCP_UPDATE_MODE": "disabled"}, clear=False),
            patch.object(lifecycle.approvals, "claim_for_confirm_write") as claim,
        ):
            result = lifecycle.confirm(
                "update", prepared["approval_token"], True, "sales"
            )
        self.assertEqual(result["code"], "UPDATE_DISABLED")
        claim.assert_not_called()
        _approval, state = self.store.lookup(
            prepared["approval_token"],
            action="lifecycle_update",
            site="test.localhost",
            user="user@example.com",
        )
        self.assertEqual(state, "available")

    def test_final_update_policy_check_blocks_before_field_mutation(self):
        prepare_doc = FakeDocument()
        confirm_doc = FakeDocument()
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        prepared = lifecycle.prepare_update(
            {"doctype": "Sales Order", "name": "SO-001"},
            [{"field": "remarks", "value": "Urgent delivery"}],
            "sales",
        )
        with patch.object(
            lifecycle,
            "_lifecycle_policy_failure",
            side_effect=[
                None,
                {
                    "status": "error",
                    "code": "UPDATE_DISABLED",
                    "message": "Document update is disabled by server policy.",
                    "reference": "MCP-ERR-TEST",
                    "retryable": False,
                },
            ],
        ):
            result = lifecycle.confirm(
                "update", prepared["approval_token"], True, "sales"
            )
        self.assertEqual(result["code"], "UPDATE_DISABLED")
        self.assertEqual(confirm_doc.remarks, "")
        self.assertFalse(confirm_doc.saved)
        _approval, state = self.store.lookup(
            prepared["approval_token"],
            action="lifecycle_update",
            site="test.localhost",
            user="user@example.com",
        )
        self.assertEqual(state, "consumed")
        self.database.commit.assert_not_called()

    def test_update_decline_remains_available_after_policy_is_disabled(self):
        doc = FakeDocument()
        lifecycle.frappe.get_doc.return_value = doc
        prepared = lifecycle.prepare_update(
            {"doctype": "Sales Order", "name": "SO-001"},
            [{"field": "remarks", "value": "Urgent delivery"}],
            "sales",
        )
        with patch.dict(os.environ, {"MCP_UPDATE_MODE": "disabled"}, clear=False):
            result = lifecycle.confirm(
                "update", prepared["approval_token"], False, "sales"
            )
        self.assertEqual(result["code"], "CONFIRMATION_REQUIRED")
        _approval, state = self.store.lookup(
            prepared["approval_token"],
            action="lifecycle_update",
            site="test.localhost",
            user="user@example.com",
        )
        self.assertEqual(state, "consumed")

    def test_final_policy_check_consumes_token_without_native_cancel(self):
        prepare_doc = FakeDocument(docstatus=1)
        confirm_doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        with patch.dict(
            os.environ, {"MCP_CANCEL_MODE": "approval_required"}, clear=False
        ):
            prepared = lifecycle.prepare_cancel(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
            with patch.object(
                lifecycle,
                "_lifecycle_policy_failure",
                side_effect=[
                    None,
                    {
                        "status": "error",
                        "code": "CANCEL_DISABLED",
                        "message": "Document cancellation is disabled by server policy.",
                        "reference": "MCP-ERR-TEST",
                        "retryable": False,
                    },
                ],
            ):
                result = lifecycle.confirm(
                    "cancel", prepared["approval_token"], True, "sales"
                )
        self.assertEqual(result["code"], "CANCEL_DISABLED")
        self.assertEqual(confirm_doc.cancel_calls, 0)
        _approval, state = self.store.lookup(
            prepared["approval_token"],
            action="lifecycle_cancel",
            site="test.localhost",
            user="user@example.com",
        )
        self.assertEqual(state, "consumed")
        self.database.commit.assert_not_called()

    def test_final_cancel_delete_check_blocks_before_first_native_mutation(self):
        prepare_doc = FakeDocument(docstatus=1)
        confirm_doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.side_effect = [prepare_doc, confirm_doc]
        with patch.dict(
            os.environ,
            {
                "MCP_CANCEL_MODE": "approval_required",
                "MCP_DELETE_MODE": "approval_required",
            },
            clear=False,
        ):
            prepared = lifecycle.prepare_delete(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
            with patch.object(
                lifecycle,
                "_lifecycle_policy_failure",
                side_effect=[
                    None,
                    None,
                    {
                        "status": "error",
                        "code": "CANCEL_DISABLED",
                        "message": "Document cancellation is disabled by server policy.",
                        "reference": "MCP-ERR-TEST",
                        "retryable": False,
                    },
                ],
            ):
                result = lifecycle.confirm(
                    "delete", prepared["approval_token"], True, "sales"
                )
        self.assertEqual(result["code"], "CANCEL_DISABLED")
        self.assertEqual(confirm_doc.cancel_calls, 0)
        self.assertEqual(confirm_doc.delete_calls, [])
        self.database.commit.assert_not_called()

    def test_decline_remains_available_after_policy_is_disabled(self):
        doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.return_value = doc
        with patch.dict(
            os.environ, {"MCP_CANCEL_MODE": "approval_required"}, clear=False
        ):
            prepared = lifecycle.prepare_cancel(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
        with patch.dict(os.environ, {"MCP_CANCEL_MODE": "disabled"}, clear=False):
            result = lifecycle.confirm(
                "cancel", prepared["approval_token"], False, "sales"
            )
        self.assertEqual(result["code"], "CONFIRMATION_REQUIRED")
        self.assertEqual(doc.cancel_calls, 0)
        _approval, state = self.store.lookup(
            prepared["approval_token"],
            action="lifecycle_cancel",
            site="test.localhost",
            user="user@example.com",
        )
        self.assertEqual(state, "consumed")

    def test_enabled_permissioned_cancel_still_returns_link_blockers(self):
        doc = FakeDocument(docstatus=1)
        lifecycle.frappe.get_doc.return_value = doc
        lifecycle.get_linked_docs.return_value = [
            {"reference_doctype": "Sales Invoice", "reference_docname": "SINV-1"}
        ]
        with patch.dict(
            os.environ, {"MCP_CANCEL_MODE": "approval_required"}, clear=False
        ):
            result = lifecycle.prepare_cancel(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
        self.assertEqual(result["code"], "LINKED_DOCUMENT")
        self.assertEqual(
            result["blockers"],
            [{"doctype": "Sales Invoice", "name": "SINV-1"}],
        )

    def test_late_delete_blocker_rolls_back_cancel_delete(self):
        prepare_doc = FakeDocument(docstatus=1)
        confirm_doc = FakeDocument(docstatus=1)
        cancelled_doc = FakeDocument(docstatus=2)
        lifecycle.frappe.get_doc.side_effect = [
            prepare_doc,
            confirm_doc,
            cancelled_doc,
        ]
        with patch.dict(
            os.environ,
            {
                "MCP_CANCEL_MODE": "approval_required",
                "MCP_DELETE_MODE": "approval_required",
            },
            clear=False,
        ):
            prepared = lifecycle.prepare_delete(
                {"doctype": "Sales Order", "name": "SO-001"}, "sales"
            )
            lifecycle.get_linked_docs.return_value = [
                {"reference_doctype": "Sales Invoice", "reference_docname": "SINV-1"}
            ]
            result = lifecycle.confirm(
                "delete", prepared["approval_token"], True, "sales"
            )
        self.assertEqual(result["code"], "LINKED_DOCUMENT")
        self.assertEqual(confirm_doc.cancel_calls, 1)
        self.assertEqual(cancelled_doc.delete_calls, [])
        self.database.rollback.assert_called_once_with()
        self.database.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
