"""Task 76: bounded Buying policy, authoring, approvals, and native seams."""
from __future__ import annotations

import unittest
import logging
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from pydantic import TypeAdapter

from mcp_erpnext.approvals import approvals
from mcp_erpnext.contracts.buying.purchase_order import PreparePurchaseOrderResult
from mcp_erpnext.contracts.lifecycle import LifecycleResult
from mcp_erpnext.remote_operations import execute_remote_operation, RemoteOperationError
from mcp_erpnext.services.buying import commercial_terms as commercial
from mcp_erpnext.services.buying import purchase_order as service
from mcp_erpnext.services.buying.terms import resolve_buying_terms_and_conditions
from mcp_erpnext.services.common import lifecycle
from mcp_erpnext.settings import ApprovalMode
from mcp_erpnext.tests import test_purchase_order_service as creation_tests
from mcp_erpnext.tests.test_purchase_order_service import FakePurchaseOrder, FakeRow
from mcp_erpnext.tests import test_lifecycle as lifecycle_tests
from mcp_erpnext.tests.test_lifecycle import FakePurchaseOrderDocument, FakeField, FakeMeta
from mcp_erpnext.tests.test_terms_resolution import FakeTermsList
from mcp_erpnext.tools.buying import terms as terms_tools
from mcp_erpnext.tools.buying.purchase_order import _with_interaction


def template_rows():
    return [
        {"name": "Buying Terms", "title": "Buying Terms", "buying": 1, "selling": 0, "disabled": 0, "modified": "one"},
        {"name": "Buying Terms Two", "title": "Buying Terms Two", "buying": 1, "selling": 0, "disabled": 0, "modified": "one"},
        {"name": "Sales Only", "title": "Sales Only", "buying": 0, "selling": 1, "disabled": 0, "modified": "one"},
        {"name": "Disabled", "title": "Disabled", "buying": 1, "disabled": 1, "modified": "one"},
        {"name": "Private", "title": "Private", "buying": 1, "disabled": 0, "visible": False, "modified": "one"},
    ]


class BuyingResolutionTests(unittest.TestCase):
    def test_exact_ambiguity_and_permission_filters(self):
        rows = template_rows()
        get_list = FakeTermsList(rows)
        self.assertEqual(resolve_buying_terms_and_conditions("Buying Terms", get_list=get_list)["status"], "resolved")
        result = resolve_buying_terms_and_conditions("buying", get_list=get_list)
        self.assertEqual(result["status"], "ambiguous")
        with patch.object(terms_tools, "execute_tool_with_context", return_value=result):
            output = terms_tools.resolve_buying_terms_and_conditions("buying", object()).root
        self.assertEqual(output.interaction.kind, "SELECTION")
        self.assertTrue(all(c[1]["filters"] == {"buying": 1, "disabled": 0} for c in get_list.calls))
        self.assertTrue(all(c[1]["ignore_permissions"] is False for c in get_list.calls))
        self.assertNotIn("terms", str(result))

    def test_disabled_sales_only_and_hidden_are_not_candidates(self):
        for row in template_rows()[2:]:
            with self.subTest(name=row["name"]):
                result = resolve_buying_terms_and_conditions(row["name"], get_list=FakeTermsList([row]))
                self.assertEqual(result["status"], "not_found")

    def test_rest_buying_resolution_and_profile_boundaries(self):
        with patch("mcp_erpnext.remote_operations.buying_terms.resolve_buying_terms_and_conditions", return_value={"status": "not_found"}) as resolve:
            for profile in ("purchase", "all"):
                self.assertEqual(execute_remote_operation("resolve_buying_terms_and_conditions", profile, {"query": "Buying"})["status"], "not_found")
            self.assertEqual(resolve.call_count, 2)
            for profile in ("sales", "accounts"):
                with self.assertRaises(RemoteOperationError):
                    execute_remote_operation("resolve_buying_terms_and_conditions", profile, {"query": "Buying"})
        with patch("mcp_erpnext.remote_operations.payment_terms.resolve_payment_terms_template", return_value={"status": "not_found"}):
            self.assertEqual(execute_remote_operation("resolve_payment_terms_template", "purchase", {"query": "Plan"})["status"], "not_found")


class PurchaseCommercialCreationTests(creation_tests.PurchaseOrderServiceTests):
    def setUp(self):
        super().setUp()
        self.rows = template_rows()
        self.payments = [{"name": "Plan", "template_name": "Plan", "modified": "one"},
                         {"name": "Company Plan", "template_name": "Company Plan", "modified": "one"}]
        self.fake_frappe.conf = {}
        self.fake_frappe.get_value = Mock(return_value=None)
        self.fake_frappe.get_list = self.templates_list
        self.fake_frappe.db.rollback = Mock()
        self.inserted = []
        self.fake_frappe.get_doc = self.load_prepared

    def templates_list(self, doctype, **kwargs):
        if doctype == "Terms and Conditions":
            return FakeTermsList(self.rows)(doctype, **kwargs)
        if doctype == "Payment Terms Template":
            return FakeTermsList(self.payments)(doctype, **kwargs)
        return super()._get_list(doctype, **kwargs)

    def load_prepared(self, data):
        doc = FakePurchaseOrder(data)
        self.inserted.append(doc)
        return doc

    def prepare(self, **choices):
        return service.prepare_purchase_order(*self._request(), **choices)

    def approve(self, prepared):
        approvals.record_trusted_user_approval(prepared["approval_token"], action="create_purchase_order", site="test.localhost", user="purchase@example.com")

    def test_all_creation_combinations_and_typed_preview(self):
        for choices in ({}, {"tc_name": "Buying Terms"}, {"payment_terms_template": "Plan"}, {"tc_name": "Buying Terms", "payment_terms_template": "Plan"}):
            with self.subTest(choices=choices):
                result = self.prepare(**choices)
                typed = TypeAdapter(PreparePurchaseOrderResult).validate_python(_with_interaction(result))
                self.assertEqual(typed.status, "ready")
                self.assertEqual(result["preview"]["tc_name"], choices.get("tc_name"))
                self.assertEqual(result["preview"]["payment_terms_template"], choices.get("payment_terms_template"))
                self.assertEqual(len(result["preview"]["payment_schedule"]), 1)
                self.assertEqual(self.commit_count, 0)

    def test_company_default_precedence_and_explicit_override(self):
        self.fake_frappe.conf = {"mcp_business_defaults": {
            "site": {"Purchase Order": {"tc_name": "invalid key"}},
        }}
        self.assertEqual(self.prepare()["code"], "INVALID_BUSINESS_DEFAULTS")
        self.fake_frappe.conf = {"mcp_business_defaults": {
            "site": {"Purchase Order": {"terms_and_conditions_template": "Buying Terms", "payment_terms_template": "Plan"}},
            "companies": {"Test Company": {"Purchase Order": {"payment_terms_template": "Company Plan"}}},
        }}
        result = self.prepare()
        self.assertEqual(result["preview"]["tc_name"], "Buying Terms")
        self.assertEqual(result["preview"]["payment_terms_template"], "Company Plan")
        result = self.prepare(tc_name="Buying Terms Two", payment_terms_template="Plan")
        self.assertEqual(result["preview"]["tc_name"], "Buying Terms Two")
        self.assertEqual(result["preview"]["payment_terms_template"], "Plan")

    def test_native_terms_default_and_unavailable_defaults(self):
        self.fake_frappe.get_value.return_value = ""
        self.assertEqual(self.prepare()["status"], "ready")
        self.fake_frappe.get_value.return_value = "Buying Terms"
        self.assertEqual(self.prepare()["preview"]["tc_name"], "Buying Terms")
        self.fake_frappe.conf = {"mcp_business_defaults": {"site": {"Purchase Order": {"payment_terms_template": "Missing"}}}}
        result = self.prepare()
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["missing"], ["payment_terms_template"])
        self.assertEqual(result["interaction"]["kind"], "INPUT")

    def test_invalid_terms_and_payment_choices_fail_closed(self):
        for name in ("Sales Only", "Disabled", "Private", "Missing"):
            self.assertEqual(self.prepare(tc_name=name)["status"], "needs_input")
        self.assertEqual(self.prepare(payment_terms_template="Missing")["status"], "needs_input")
        self.assertEqual(self.prepare(tc_name=" ")["code"], "INVALID_COMMERCIAL_TEMPLATE")

    def test_confirmation_persists_selections_with_normal_permissions(self):
        prepared = self.prepare(tc_name="Buying Terms", payment_terms_template="Plan")
        self.approve(prepared)
        result = service.confirm_purchase_order(prepared["approval_token"], True)
        self.assertEqual(result["status"], "created")
        self.assertEqual(self.inserted[-1].tc_name, "Buying Terms")
        self.assertEqual(self.inserted[-1].terms, "Rendered Buying Terms")
        self.assertEqual(self.inserted[-1].payment_terms_template, "Plan")
        self.assertEqual(self.inserted[-1].insert_calls, [{"ignore_permissions": False, "ignore_links": False, "ignore_mandatory": False}])

    def test_stale_ineligible_or_hidden_template_is_rejected_before_insert(self):
        for mutation in ({"modified": "two"}, {"disabled": 1}, {"buying": 0}, {"visible": False}):
            self.rows = template_rows()
            prepared = self.prepare(tc_name="Buying Terms")
            self.approve(prepared)
            self.rows[0].update(mutation)
            result = service.confirm_purchase_order(prepared["approval_token"], True)
            self.assertEqual(result["code"], "STALE_CONFIRMATION")
            self.assertFalse(self.inserted[-1].insert_calls)
        self.assertEqual(self.commit_count, 0)

    def test_changed_payment_template_and_insert_hook_rejected(self):
        prepared = self.prepare(payment_terms_template="Plan")
        self.approve(prepared)
        self.payments[0]["modified"] = "two"
        self.assertEqual(service.confirm_purchase_order(prepared["approval_token"], True)["code"], "STALE_CONFIRMATION")
        prepared = self.prepare(tc_name="Buying Terms")
        self.approve(prepared)
        def changed_insert(doc, **kwargs):
            doc.terms = "Unapproved hook content"
        with patch.object(FakePurchaseOrder, "insert", changed_insert):
            self.assertEqual(service.confirm_purchase_order(prepared["approval_token"], True)["code"], "STALE_CONFIRMATION")
        self.fake_frappe.db.rollback.assert_called()
        self.assertEqual(self.commit_count, 0)

    def test_native_payment_default_is_permission_checked_and_frozen(self):
        original = FakePurchaseOrder.set_missing_values
        def native_defaults(doc):
            original(doc)
            if not doc.payment_terms_template and not doc.ignore_default_payment_terms_template:
                doc.payment_terms_template = "Plan"
        with patch.object(FakePurchaseOrder, "set_missing_values", native_defaults):
            result = self.prepare()
            self.assertEqual(result["preview"]["payment_terms_template"], "Plan")
            self.payments[0]["visible"] = False
            self.assertEqual(self.prepare()["status"], "needs_input")

    def test_shared_delegated_policy_and_replay(self):
        approvals.configure_approval_mode(ApprovalMode.AGENT_DELEGATED)
        prepared = self.prepare(tc_name="Buying Terms")
        self.assertEqual(service.confirm_purchase_order(prepared["approval_token"], True)["status"], "created")
        self.assertEqual(service.confirm_purchase_order(prepared["approval_token"], True)["status"], "error")

    def test_rest_forwards_both_choices(self):
        supplier, items = self._request()
        with patch("mcp_erpnext.remote_operations.purchase_order.prepare_purchase_order", return_value={"status": "ready"}) as prepare:
            execute_remote_operation("prepare_purchase_order", "purchase", {"supplier": supplier, "items": items, "tc_name": "Buying Terms", "payment_terms_template": "Plan"})
        self.assertEqual(prepare.call_args.args[-2:], ("Buying Terms", "Plan"))


class CommercialDraft(FakePurchaseOrderDocument):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.company = "Test Company"
        self.transaction_date = "2026-09-28"
        self.grand_total = 100
        self.tc_name = "Buying Terms"
        self.terms = "Old rendered terms"
        self.payment_terms_template = "Plan"
        self.payment_schedule = [frappe._dict(payment_term="Old", invoice_portion=100, payment_amount=100)]
        self.meta = FakeMeta(*self.meta.fields,
                             FakeField("tc_name", "Link", options="Terms and Conditions"),
                             FakeField("payment_terms_template", "Link", options="Payment Terms Template"))

    def set_missing_values(self):
        super().set_missing_values()
        if not self.payment_terms_template and not self.get("ignore_default_payment_terms_template"):
            self.payment_terms_template = "Plan"

    def set_missing_terms(self):
        if self.tc_name and not self.terms:
            self.terms = f"Rendered {self.tc_name}"

    def set_payment_schedule(self):
        if not self.payment_schedule:
            self.payment_schedule = [frappe._dict(payment_term=self.payment_terms_template, due_date=self.transaction_date, invoice_portion=100, payment_amount=100)]


class PurchaseCommercialLifecycleTests(unittest.TestCase):
    tearDown = lifecycle_tests.LifecycleServiceTests.tearDown

    def setUp(self):
        lifecycle_tests.LifecycleServiceTests.setUp(self)
        self.rows = template_rows()
        self.payments = [{"name": "Plan", "modified": "one"}, {"name": "New Plan", "modified": "one"}]
        def permitted(doctype, **kwargs):
            return FakeTermsList(self.rows if doctype == "Terms and Conditions" else self.payments)(doctype, **kwargs)
        lifecycle.frappe.get_list.side_effect = permitted

    def prepare_commercial(self, changes, **doc_kwargs):
        self.prepared_doc = CommercialDraft(**doc_kwargs)
        self.confirm_doc = CommercialDraft(**doc_kwargs)
        lifecycle.frappe.get_doc.side_effect = [self.prepared_doc, self.confirm_doc]
        return lifecycle.prepare_update({"doctype": "Purchase Order", "name": "PO-001"}, changes, "purchase")

    def test_replace_and_clear_refresh_then_confirm(self):
        for changes in (
            [{"field": "tc_name", "value": "Buying Terms Two"}],
            [{"field": "payment_terms_template", "value": "New Plan"}],
            [{"field": "tc_name", "value": None}, {"field": "payment_terms_template", "value": None}],
        ):
            result = self.prepare_commercial(changes)
            self.assertEqual(result["status"], "ready")
            self.assertFalse(self.prepared_doc.saved)
            self.assertIn("commercial_terms", result["preview"])
            confirmed = lifecycle.confirm("update", result["approval_token"], True, "purchase")
            self.assertEqual(confirmed["status"], "updated")
            self.assertTrue(self.confirm_doc.saved)
            for change in changes:
                self.assertEqual(self.confirm_doc.get(change["field"]), change["value"])
            if changes[-1]["value"] is None:
                self.assertEqual(self.confirm_doc.terms, "")
                self.assertIsNone(self.confirm_doc.payment_schedule[0].payment_term)
            elif changes[0]["field"] == "payment_terms_template":
                self.assertEqual(self.confirm_doc.payment_schedule[0].payment_term, "New Plan")

    def test_unavailable_choice_requests_input_and_arbitrary_values_rejected(self):
        result = self.prepare_commercial([{"field": "tc_name", "value": "Sales Only"}])
        self.assertEqual(LifecycleResult.model_validate(result).interaction.kind, "INPUT")
        for field, value in (("terms", "arbitrary"), ("payment_schedule", []), ("payment_terms_template", {"name": "Plan"})):
            result = self.prepare_commercial([{"field": field, "value": value}])
            self.assertEqual(result["status"], "error")
        for state in (1, 2):
            self.assertEqual(self.prepare_commercial([{"field": "tc_name", "value": None}], docstatus=state)["code"], "INVALID_DOCUMENT_STATE")

    def test_template_or_parent_staleness_and_permission_loss_prevent_save(self):
        for kind in ("terms", "payment", "parent", "permission"):
            self.rows = template_rows()
            self.payments[1]["modified"] = "one"
            result = self.prepare_commercial([{"field": "tc_name", "value": "Buying Terms Two"}, {"field": "payment_terms_template", "value": "New Plan"}])
            if kind == "terms":
                self.rows[1]["disabled"] = 1
            elif kind == "payment":
                self.payments[1]["modified"] = "two"
            elif kind == "parent":
                self.confirm_doc.modified = "two"
            else:
                self.confirm_doc.has_permission = lambda permission: permission == "read"
                self.confirm_doc.check_permission = Mock(side_effect=frappe.PermissionError)
            result = lifecycle.confirm("update", result["approval_token"], True, "purchase")
            self.assertEqual(result["status"], "error")
            self.assertFalse(self.confirm_doc.saved)


class NativeCommercialTests(unittest.TestCase):
    """Run installed ERPNext schedule/render methods with database seams mocked."""
    def test_native_schedule_generate_replace_clear_and_month_boundary(self):
        with patch.object(frappe, "logger", return_value=logging.getLogger("task76-test")):
            from erpnext.controllers.accounts_controller import AccountsController

        class NativeRow(frappe._dict):
            def precision(self, field):
                return 2

        class NativePO(FakePurchaseOrder):
            set_payment_schedule = AccountsController.set_payment_schedule

            def append(self, table, values):
                row = NativeRow(values)
                getattr(self, table).append(row)
                return row

        def term(portion, days):
            return frappe._dict(payment_term=f"{days} days", invoice_portion=portion,
                                credit_days=days, due_date_based_on="Day(s) after invoice date")

        templates = {"Split": frappe._dict(terms=[term(40, 0), term(60, 30)]),
                     "Later": frappe._dict(terms=[term(100, 60)])}
        doc = NativePO({"doctype": "Purchase Order", "party_account_currency": "INR",
                        "transaction_date": "2026-01-31", "grand_total": 1000,
                        "base_grand_total": 2000, "payment_terms_template": "Split"})
        with patch.object(frappe, "get_doc", side_effect=lambda dt, name: templates[name]), patch.object(frappe, "db", SimpleNamespace(get_value=lambda *args: 0)), patch.object(frappe, "get_system_settings", return_value="Banker's Rounding (legacy)"):
            doc.set_payment_schedule()
            self.assertEqual([row.payment_amount for row in doc.payment_schedule], [400, 600])
            self.assertEqual([row.base_payment_amount for row in doc.payment_schedule], [800, 1200])
            self.assertEqual(str(doc.payment_schedule[1].due_date), "2026-03-02")
            doc.payment_terms_template = "Later"
            doc.set("payment_schedule", [])
            doc.set_payment_schedule()
            self.assertEqual(len(doc.payment_schedule), 1)
            self.assertEqual(str(doc.payment_schedule[0].due_date), "2026-04-01")
            self.assertEqual(doc.payment_schedule[0].payment_amount, 1000)
            doc.payment_terms_template = None
            doc.set("payment_schedule", [])
            doc.set_payment_schedule()
            self.assertEqual(doc.payment_schedule[0].invoice_portion, 100)
            self.assertEqual(str(doc.payment_schedule[0].due_date), "2026-01-31")
            self.assertIsNone(doc.payment_schedule[0].payment_term)

    def test_native_terms_adapter_renders_context_and_checks_permission(self):
        with patch.object(frappe, "logger", return_value=logging.getLogger("task76-test")):
            from erpnext.controllers.accounts_controller import AccountsController
        from jinja2.sandbox import SandboxedEnvironment

        template = SimpleNamespace(terms="Order for {{ supplier }}", check_permission=Mock())
        doc = FakePurchaseOrder({"tc_name": "Buying Terms", "supplier": "SUP-001"})
        def render(body, context, *, restrict_globals):
            self.assertEqual(restrict_globals, 1)
            return SandboxedEnvironment().from_string(body).render(context)
        with patch.object(frappe, "get_cached_doc", return_value=template), patch.object(frappe, "render_template", side_effect=render):
            AccountsController.set_missing_terms(doc)
        template.check_permission.assert_called_once_with()
        self.assertEqual(doc.terms, "Order for SUP-001")
