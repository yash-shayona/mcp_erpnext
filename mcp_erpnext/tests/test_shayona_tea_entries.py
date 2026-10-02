from __future__ import annotations

import unittest
import os
from contextlib import ExitStack
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from pydantic import ValidationError

import mcp_erpnext
from mcp_erpnext.observability import public_error
from mcp_erpnext.approvals import ApprovalStore
from mcp_erpnext.settings import ApprovalMode
from mcp_erpnext.tests.approval_test_backend import FakeSharedApprovalBackend, mutate_record
from shayona.shayona.doctype.tea_entry.tea_entry import TeaEntry
from mcp_erpnext.contracts.registry import (
    SideEffectClass,
    TOOL_CONTRACTS,
    ToolOperation,
)
from mcp_erpnext.contracts.shayona.tea_entries import (
    TeaEntryAggregateInput,
    TeaEntryCreateInput,
    TeaEntryConfirmInput,
    TeaEntryPrepareOutput,
    TeaEntryCreateOutput,
    TeaEntryGetInput,
    TeaEntryQueryInput,
    TeaEntryUpdateChanges,
    TeaEntryUpdateInput,
    TeaEntryUpdateOutput,
    TeaEntryUpdatePrepareOutput,
)
from mcp_erpnext.services.shayona import tea_entries
from mcp_erpnext.tools.shayona import tea_entries as tea_entry_tools

SAFE_ROW = {
    "name": "TEA-1",
    "date": date(2026, 10, 1),
    "no_of_cups": 10,
    "rate_per_cup": Decimal("15"),
    "total_amount": Decimal("150"),
    "vendor": "Vendor A",
}


def _meta(*, missing: str | None = None, wrong: tuple[str, str] | None = None):
    fieldtypes = dict(tea_entries.REQUIRED_FIELDTYPES)
    if wrong:
        fieldtypes[wrong[0]] = wrong[1]
    columns = [field for field in tea_entries.PUBLIC_FIELDS if field != missing]
    return SimpleNamespace(
        get_valid_columns=lambda: columns,
        get_field=lambda fieldname: (
            SimpleNamespace(fieldtype=fieldtypes[fieldname])
            if fieldname in fieldtypes and fieldname != missing
            else None
        ),
    )


class TeaEntryContractTests(unittest.TestCase):
    def test_version_and_safe_schema_message(self):
        self.assertEqual(mcp_erpnext.__version__, "4.0.2")
        result = public_error(
            "TEA_ENTRY_SCHEMA_UNAVAILABLE", reference="MCP-ERR-TEST"
        )
        self.assertEqual(
            result["message"], "Tea Entry capability is unavailable on this site."
        )

    def test_contracts_reject_unbounded_or_mutation_inputs(self):
        invalid_query_inputs = (
            {"ignore_permissions": True},
            {"fields": ["owner"]},
            {"owner": "Administrator"},
            {"sort_order": "sideways"},
            {"limit": 0},
            {"limit": 101},
            {"offset": -1},
            {"date": "2026-10-01", "date_from": "2026-09-01"},
            {"date_from": "2026-10-02", "date_to": "2026-10-01"},
            {"no_of_cups": 10},
        )
        for values in invalid_query_inputs:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                TeaEntryQueryInput(**values)

        for values in (
            {"metrics": ["avg_rate_per_cup"]},
            {"metrics": ["count"], "group_by": "owner"},
            {"metrics": ["count", "count"]},
            {"metrics": []},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                TeaEntryAggregateInput(**values)

        with self.assertRaises(ValidationError):
            TeaEntryGetInput(tea_entry_name=" ")

    def test_governed_contracts_are_read_only(self):
        expected = {
            "get_tea_entry": ToolOperation.RESOLVE,
            "query_tea_entries": ToolOperation.SEARCH,
            "aggregate_tea_entries": ToolOperation.SEARCH,
        }
        for name, operation in expected.items():
            contract = TOOL_CONTRACTS[name]
            self.assertEqual(contract.domain, "Shayona")
            self.assertEqual(contract.operation, operation)
            self.assertEqual(contract.side_effect, SideEffectClass.READ)
            self.assertFalse(contract.approval_required)
            self.assertTrue(contract.mcp_annotations().readOnlyHint)
        self.assertEqual(
            TOOL_CONTRACTS["get_tea_entry"].resolution_states,
            ("ok", "not_found", "error"),
        )


class TeaEntryServiceTests(unittest.TestCase):
    def test_complete_schema_is_accepted(self):
        schema = tea_entries.tea_entry_schema(_meta())
        self.assertEqual(schema.public_fields, tea_entries.PUBLIC_FIELDS)

    def test_incompatible_schema_fails_closed(self):
        for meta in (
            _meta(missing="vendor"),
            _meta(wrong=("date", "Data")),
            _meta(wrong=("total_amount", "Float")),
        ):
            with self.subTest(meta=meta), self.assertRaises(
                tea_entries.TeaEntrySchemaUnavailableError
            ):
                tea_entries.tea_entry_schema(meta)

    @patch.object(tea_entries, "logged_public_error")
    @patch.object(tea_entries.frappe, "get_list")
    @patch.object(tea_entries.frappe, "get_meta", side_effect=RuntimeError("raw"))
    def test_metadata_failure_is_safe_and_stops_before_read(
        self, _get_meta, get_list, logged_error
    ):
        logged_error.return_value = {
            "status": "error",
            "code": "TEA_ENTRY_SCHEMA_UNAVAILABLE",
            "message": "Tea Entry capability is unavailable on this site.",
            "reference": "MCP-ERR-TEST",
            "retryable": False,
        }
        result = tea_entries.query_tea_entries(
            {"limit": 20, "offset": 0, "sort_order": "desc"}
        )
        self.assertEqual(result["code"], "TEA_ENTRY_SCHEMA_UNAVAILABLE")
        self.assertNotIn("raw", result["message"])
        get_list.assert_not_called()

    @patch.object(tea_entries.frappe, "get_meta", return_value=_meta())
    @patch.object(tea_entries.frappe, "get_doc")
    def test_get_uses_fixed_projection_and_read_permission(self, get_doc, _get_meta):
        get_doc.return_value = SimpleNamespace(
            **SAFE_ROW,
            owner="Administrator",
            modified="secret",
            has_permission=lambda permission: permission == "read",
        )
        result = tea_entries.get_tea_entry("TEA-1")
        self.assertEqual(result, {"status": "ok", "tea_entry": SAFE_ROW})
        self.assertNotIn("owner", result["tea_entry"])
        get_doc.assert_called_once_with(tea_entries.TEA_ENTRY_DOCTYPE, "TEA-1")

    @patch.object(tea_entries.frappe, "get_meta", return_value=_meta())
    @patch.object(tea_entries.frappe, "get_doc")
    def test_get_permission_is_enforced(self, get_doc, _get_meta):
        get_doc.return_value = SimpleNamespace(
            **SAFE_ROW, has_permission=lambda _permission: False
        )
        with self.assertRaises(frappe.PermissionError):
            tea_entries.get_tea_entry("TEA-1")

    @patch.object(tea_entries.frappe, "get_meta", return_value=_meta())
    @patch.object(tea_entries.frappe, "get_doc", side_effect=frappe.DoesNotExistError)
    def test_get_missing_returns_typed_not_found(self, _get_doc, _get_meta):
        self.assertEqual(
            tea_entries.get_tea_entry("TEA-MISSING"),
            {"status": "not_found", "tea_entry_name": "TEA-MISSING"},
        )

    @patch.object(tea_entries.frappe, "get_meta", return_value=_meta())
    @patch.object(tea_entries.frappe, "get_list", return_value=[SAFE_ROW])
    def test_query_maps_filters_order_and_pagination(self, get_list, _get_meta):
        result = tea_entries.query_tea_entries(
            {
                "date_from": date(2026, 9, 1),
                "date_to": date(2026, 10, 1),
                "vendor": "Vendor A",
                "limit": 10,
                "offset": 5,
                "sort_order": "asc",
            }
        )
        self.assertEqual(result["tea_entries"], [SAFE_ROW])
        kwargs = get_list.call_args.kwargs
        self.assertEqual(
            kwargs["filters"],
            [
                ["date", ">=", date(2026, 9, 1)],
                ["date", "<=", date(2026, 10, 1)],
                ["vendor", "=", "Vendor A"],
            ],
        )
        self.assertEqual(kwargs["fields"], list(tea_entries.PUBLIC_FIELDS))
        self.assertEqual(kwargs["order_by"], "date asc, name asc")
        self.assertEqual(kwargs["limit_start"], 5)
        self.assertEqual(kwargs["limit_page_length"], 10)
        self.assertFalse(kwargs["ignore_permissions"])

    @patch.object(tea_entries.frappe, "get_meta", return_value=_meta())
    @patch.object(tea_entries.frappe, "get_list", return_value=[])
    def test_query_exact_date_and_no_filter_have_no_today_default(
        self, get_list, _get_meta
    ):
        tea_entries.query_tea_entries(
            {
                "date": date(2026, 10, 1),
                "limit": 20,
                "offset": 0,
                "sort_order": "desc",
            }
        )
        self.assertEqual(
            get_list.call_args.kwargs["filters"],
            [["date", "=", date(2026, 10, 1)]],
        )
        tea_entries.query_tea_entries(
            {"limit": 20, "offset": 0, "sort_order": "desc"}
        )
        self.assertEqual(get_list.call_args.kwargs["filters"], [])
        self.assertEqual(get_list.call_args.kwargs["order_by"], "date desc, name desc")

    @patch.object(tea_entries.frappe, "get_meta", return_value=_meta())
    @patch.object(
        tea_entries.frappe,
        "get_list",
        return_value=[
            {
                "vendor": "Vendor A",
                "count": 2,
                "sum_no_of_cups": Decimal("20"),
                "sum_total_amount": Decimal("300"),
            }
        ],
    )
    def test_aggregate_uses_allowlisted_permission_aware_helper(
        self, get_list, _get_meta
    ):
        result = tea_entries.aggregate_tea_entries(
            {
                "metrics": ["count", "sum_no_of_cups", "sum_total_amount"],
                "group_by": "vendor",
                "vendor": "Vendor A",
            }
        )
        self.assertEqual(result["results"][0]["group_value"], "Vendor A")
        kwargs = get_list.call_args.kwargs
        self.assertEqual(kwargs["group_by"], "vendor")
        self.assertEqual(kwargs["order_by"], "vendor")
        self.assertEqual(kwargs["filters"], [["vendor", "=", "Vendor A"]])
        self.assertFalse(kwargs["ignore_permissions"])
        self.assertEqual(
            kwargs["fields"],
            [
                "vendor",
                tea_entries.AGGREGATE_METRICS["count"],
                tea_entries.AGGREGATE_METRICS["sum_no_of_cups"],
                tea_entries.AGGREGATE_METRICS["sum_total_amount"],
            ],
        )

        tea_entries.aggregate_tea_entries(
            {"metrics": ["count"], "group_by": "date"}
        )
        self.assertEqual(get_list.call_args.kwargs["group_by"], "date")
        self.assertEqual(get_list.call_args.kwargs["order_by"], "date")


class TeaEntryToolTests(unittest.TestCase):
    @patch.object(tea_entry_tools, "execute_tool_with_context")
    def test_query_adapter_uses_shared_runtime_and_json_rest_payload(self, execute):
        execute.return_value = {
            "status": "ok",
            "tea_entries": [],
            "count": 0,
            "limit": 20,
            "offset": 0,
        }
        tea_entry_tools.query_tea_entries(
            ctx=object(), date=date(2026, 10, 1), vendor="Vendor A"
        )
        self.assertEqual(execute.call_args.args[1], "query_tea_entries")
        self.assertEqual(
            execute.call_args.kwargs["rest_arguments"],
            {
                "date": "2026-10-01",
                "date_from": None,
                "date_to": None,
                "vendor": "Vendor A",
                "limit": 20,
                "offset": 0,
                "sort_order": "desc",
            },
        )

    @patch.object(tea_entry_tools, "execute_tool_with_context")
    def test_create_adapters_use_json_safe_rest_and_same_service(self, execute):
        for name in ("prepare_tea_entry", "execute_tea_entry", "confirm_tea_entry"):
            with self.subTest(name=name), patch.object(tea_entries, name, return_value=public_error("CREATE_DISABLED")) as service:
                def invoke(ctx, tool, callback, *, rest_arguments):
                    self.assertEqual(tool, name)
                    if name != "confirm_tea_entry":
                        self.assertEqual(rest_arguments["date"], "2026-10-02")
                        self.assertEqual(rest_arguments["rate_per_cup"], "15.5")
                    return callback()
                execute.side_effect = invoke
                if name == "confirm_tea_entry":
                    getattr(tea_entry_tools, name)("token", True, ctx=object())
                    service.assert_called_once_with("token", True)
                else:
                    getattr(tea_entry_tools, name)(2, Decimal("15.5"), ctx=object(), date=date(2026, 10, 2))
                    service.assert_called_once()

    def test_only_governed_tea_create_trio_is_exposed(self):
        for name in ("prepare_tea_entry", "confirm_tea_entry", "execute_tea_entry"):
            self.assertIn(name, TOOL_CONTRACTS)
            self.assertTrue(hasattr(tea_entries, name))
            self.assertTrue(hasattr(tea_entry_tools, name))
        for module in (tea_entries, tea_entry_tools):
            self.assertFalse(hasattr(module, "create_tea_entry"))
            self.assertFalse(hasattr(module, "update_tea_entry"))
        self.assertNotIn("create_tea_entry", TOOL_CONTRACTS)
        self.assertNotIn("update_tea_entry", TOOL_CONTRACTS)


class TeaEntryCreateTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"MCP_CREATE_MODE": "approval_required"}))
        self.backend = FakeSharedApprovalBackend()
        self.store = ApprovalStore(ApprovalMode.AGENT_DELEGATED, backend=self.backend)
        self.stack.enter_context(patch.object(tea_entries, "approvals", self.store))
        self.docs = []
        self.today = "2026-10-02"
        self.validation_hook = lambda: None
        self.insert_error = None
        self.db = SimpleNamespace(commit=Mock(), rollback=Mock(), exists=Mock(return_value=None))
        self.fake = SimpleNamespace(
            session=SimpleNamespace(user="test@example.com"), local=SimpleNamespace(site="test.localhost"),
            get_meta=Mock(return_value=_meta()), has_permission=Mock(return_value=True),
            get_doc=lambda values: self.new_doc(values["doctype"]), db=self.db, PermissionError=frappe.PermissionError,
            ValidationError=frappe.ValidationError,
        )
        self.stack.enter_context(patch.object(tea_entries, "frappe", self.fake))
        self.native_defaults = self.stack.enter_context(patch.object(
            tea_entries, "make_new_doc", side_effect=lambda doctype: {"doctype": doctype}
        ))
        self.dynamic_defaults = self.stack.enter_context(patch.object(tea_entries, "set_dynamic_default_values"))
        self.stack.enter_context(patch.object(tea_entries, "logged_public_error", side_effect=lambda tool, code, **kw: public_error(code, **kw)))
        self.request = {"no_of_cups": 10, "rate_per_cup": "15"}

    def new_doc(self, doctype):
        self.assertEqual(doctype, "Tea Entry")
        doc = SimpleNamespace(name=None, date=self.today, no_of_cups=None, rate_per_cup=15, vendor=None)
        doc.set = lambda key, value: setattr(doc, key, value)
        doc.check_permission = Mock()
        doc.set_total_amount = lambda: TeaEntry.set_total_amount(doc)
        def duplicate():
            # Exercise the actual native controller with only its database/throw seams replaced.
            with patch("shayona.shayona.doctype.tea_entry.tea_entry.frappe", SimpleNamespace(
                db=self.db, throw=lambda **kw: (_ for _ in ()).throw(frappe.ValidationError("RAW-SENTINEL"))
            )):
                TeaEntry.validate_duplicate_date(doc)
        doc.validate_duplicate_date = duplicate
        def validate(method):
            self.assertEqual(method, "validate")
            TeaEntry.validate(doc)
            self.validation_hook()
        doc.run_method = Mock(side_effect=validate)
        def insert(**kwargs):
            self.assertEqual(kwargs, {"ignore_permissions": False})
            if self.insert_error:
                raise self.insert_error
            doc.name = "TEA-NEW"
            # Prove the response uses post-insert native values, not the preview.
            doc.total_amount = Decimal("151")
            return doc
        doc.insert = Mock(side_effect=insert)
        self.docs.append(doc)
        return doc

    def assert_no_write(self):
        self.db.commit.assert_not_called()
        for doc in self.docs:
            doc.insert.assert_not_called()

    def test_bounded_contracts(self):
        TeaEntryCreateInput(no_of_cups=1, rate_per_cup=0)
        for extra in ({"no_of_cups": 0}, {"no_of_cups": -1}, {"no_of_cups": True},
                      {"no_of_cups": 1.2}, {"rate_per_cup": -1}, {"rate_per_cup": "NaN"},
                      {"vendor": " "}, {"total_amount": 1}, {"name": "x"},
                      {"ignore_permissions": True}, {"create_mode": "direct"},
                      {"MCP_CREATE_MODE": "direct"}, {"approval_needed": False}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                TeaEntryCreateInput(**(self.request | extra))
        with self.assertRaises(ValidationError):
            TeaEntryConfirmInput(approval_token="x", confirm=True, total_amount=1)

    def test_native_prepare_date_total_and_bounded_payload(self):
        ready = tea_entries.prepare_tea_entry(self.request)
        TeaEntryPrepareOutput.model_validate(ready)
        self.assertEqual(ready["preview"]["date"], date(2026, 10, 2))
        self.assertEqual(ready["preview"]["total_amount"], Decimal("150"))
        self.assertNotIn("name", ready["preview"])
        approval, state = self.store.lookup(ready["approval_token"], action="create_tea_entry", site="test.localhost", user="test@example.com")
        self.assertEqual(state, "available")
        plan = tea_entries.TeaEntryPlan(**approval.payload)
        self.assertEqual(set(plan.values()), {"date", "no_of_cups", "rate_per_cup", "vendor"})
        self.assert_no_write()
        explicit = tea_entries.prepare_tea_entry(self.request | {"date": "2026-09-01", "vendor": "Vendor"})
        self.assertEqual(explicit["preview"]["date"], date(2026, 9, 1))

    def test_disabled_and_wrong_entry_modes_never_plan_or_touch_approvals(self):
        for mode, expected in (("disabled", "CREATE_DISABLED"), ("direct", "DIRECT_EXECUTION_REQUIRED")):
            with patch.dict(os.environ, {"MCP_CREATE_MODE": mode}), patch.object(tea_entries, "approvals") as store:
                result = tea_entries.confirm_tea_entry("token", True)
                self.assertEqual(result["code"], expected)
                if mode == "disabled":
                    self.assertEqual(tea_entries.prepare_tea_entry(self.request)["code"], expected)
                    self.assertEqual(tea_entries.execute_tea_entry(self.request)["code"], expected)
                self.assertEqual(store.mock_calls, [])
        self.assertEqual(tea_entries.execute_tea_entry(self.request)["code"], "APPROVAL_REQUIRED")
        self.assertEqual(self.docs, [])

    def test_direct_preview_and_fresh_execute_are_store_inert(self):
        with patch.dict(os.environ, {"MCP_CREATE_MODE": "direct"}), patch.object(tea_entries, "approvals") as store:
            preview = tea_entries.prepare_tea_entry(self.request)
            TeaEntryPrepareOutput.model_validate(preview)
            self.assertEqual(preview["status"], "preview")
            self.assertNotIn("approval_token", preview)
            self.assert_no_write()
            self.today = "2026-10-03"
            result = tea_entries.execute_tea_entry(self.request)
            TeaEntryCreateOutput.model_validate(result)
            self.assertEqual(str(result["tea_entry"]["date"]), self.today)
            self.assertEqual(result["tea_entry"]["total_amount"], 151)
            self.assertEqual(store.mock_calls, [])
        self.db.commit.assert_called_once()
        self.assertEqual(len(self.docs), 3)
        self.assertEqual(self.native_defaults.call_count, 3)
        self.assertEqual(self.dynamic_defaults.call_count, 3)

    def test_confirm_preserves_effective_date_and_replay_is_blocked(self):
        ready = tea_entries.prepare_tea_entry(self.request)
        self.today = "2026-10-03"
        result = tea_entries.confirm_tea_entry(ready["approval_token"], True)
        TeaEntryCreateOutput.model_validate(result)
        self.assertEqual(str(result["tea_entry"]["date"]), "2026-10-02")
        self.assertEqual(result["tea_entry"]["total_amount"], 151)
        self.assertEqual(tea_entries.confirm_tea_entry(ready["approval_token"], True)["code"], "CONFIRMATION_CONSUMED")
        self.db.commit.assert_called_once()

    def test_final_mode_switches_block_both_paths(self):
        for entry, target, expected in (
            ("direct", "approval_required", "APPROVAL_REQUIRED"),
            ("direct", "disabled", "CREATE_DISABLED"),
            ("approval_required", "direct", "DIRECT_EXECUTION_REQUIRED"),
            ("approval_required", "disabled", "CREATE_DISABLED"),
        ):
            with self.subTest(entry=entry, target=target), patch.dict(os.environ, {"MCP_CREATE_MODE": entry}):
                self.validation_hook = lambda: None
                if entry == "approval_required":
                    ready = tea_entries.prepare_tea_entry(self.request)
                    self.validation_hook = lambda: os.environ.__setitem__("MCP_CREATE_MODE", target)
                    result = tea_entries.confirm_tea_entry(ready["approval_token"], True)
                else:
                    # Switch during apply revalidation, after fresh direct planning.
                    calls = []
                    def switch():
                        calls.append(1)
                        if len(calls) == 2:
                            os.environ["MCP_CREATE_MODE"] = target
                    self.validation_hook = switch
                    with patch.object(tea_entries, "approvals") as store:
                        result = tea_entries.execute_tea_entry(self.request)
                        self.assertEqual(store.mock_calls, [])
                self.assertEqual(result["code"], expected)
                self.assert_no_write()

    def test_duplicate_at_prepare_is_safe_and_at_confirm_is_stale(self):
        ready = tea_entries.prepare_tea_entry(self.request)
        self.db.exists.return_value = "EXISTING"
        result = tea_entries.confirm_tea_entry(ready["approval_token"], True)
        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        result = tea_entries.prepare_tea_entry(self.request)
        self.assertEqual(result["code"], "TEA_ENTRY_VALIDATION_FAILED")
        self.assertNotIn("RAW-SENTINEL", str(result))
        self.db.rollback.assert_called()
        self.assert_no_write()

    def test_changed_native_total_is_stale(self):
        ready = tea_entries.prepare_tea_entry(self.request)
        self.validation_hook = lambda: setattr(self.docs[-1], "total_amount", Decimal("999"))
        self.assertEqual(tea_entries.confirm_tea_entry(ready["approval_token"], True)["code"], "STALE_CONFIRMATION")
        self.assert_no_write()

    def test_schema_and_permissions_prevent_token_creation(self):
        self.fake.get_meta.return_value = _meta(missing="date")
        self.assertEqual(tea_entries.prepare_tea_entry(self.request)["code"], "TEA_ENTRY_SCHEMA_UNAVAILABLE")
        self.fake.get_meta.return_value = _meta()
        self.fake.has_permission.return_value = False
        self.assertEqual(tea_entries.prepare_tea_entry(self.request)["code"], "ERP_PERMISSION_DENIED")
        self.fake.has_permission.return_value = True
        self.fake.session.user = "Guest"
        self.assertEqual(tea_entries.prepare_tea_entry(self.request)["code"], "ERP_PERMISSION_DENIED")
        self.assertTrue(self.backend.is_empty())
        self.assert_no_write()

    def test_permission_revoked_after_prepare_blocks_confirmation(self):
        ready = tea_entries.prepare_tea_entry(self.request)
        self.fake.has_permission.return_value = False
        self.assertEqual(tea_entries.confirm_tea_entry(ready["approval_token"], True)["code"], "ERP_PERMISSION_DENIED")
        self.db.rollback.assert_called_once()
        self.assert_no_write()

    def test_direct_validation_and_insert_failures_remain_store_inert(self):
        with patch.dict(os.environ, {"MCP_CREATE_MODE": "direct"}), patch.object(tea_entries, "approvals") as store:
            self.db.exists.return_value = "EXISTING"
            result = tea_entries.execute_tea_entry(self.request)
            self.assertEqual(result["code"], "TEA_ENTRY_VALIDATION_FAILED")
            self.assert_no_write()
            self.db.exists.return_value = None
            self.insert_error = RuntimeError("RAW-SENTINEL")
            result = tea_entries.execute_tea_entry(self.request)
            self.assertEqual(result["code"], "TEA_ENTRY_WRITE_FAILED")
            self.assertNotIn("RAW-SENTINEL", str(result))
            self.assertEqual(store.mock_calls, [])
        self.db.commit.assert_not_called()
        self.assertEqual(self.db.rollback.call_count, 2)

    def test_insert_failures_rollback_without_raw_errors(self):
        for error, code in ((frappe.PermissionError("RAW-SENTINEL"), "ERP_PERMISSION_DENIED"),
                            (frappe.ValidationError("RAW-SENTINEL"), "STALE_CONFIRMATION"),
                            (RuntimeError("RAW-SENTINEL"), "TEA_ENTRY_WRITE_FAILED")):
            with self.subTest(code=code):
                ready = tea_entries.prepare_tea_entry(self.request)
                self.insert_error = error
                result = tea_entries.confirm_tea_entry(ready["approval_token"], True)
                self.assertEqual(result["code"], code)
                self.assertNotIn("RAW-SENTINEL", str(result))
                self.db.commit.assert_not_called()
        self.assertEqual(self.db.rollback.call_count, 3)

    def test_shared_trusted_human_guard_and_decline(self):
        self.store.configure_approval_mode(ApprovalMode.TRUSTED_HUMAN)
        ready = tea_entries.prepare_tea_entry(self.request)
        token = ready["approval_token"]
        self.assertEqual(tea_entries.confirm_tea_entry(token, True)["code"], "TRUSTED_APPROVAL_UNAVAILABLE")
        self.assert_no_write()
        self.store.record_trusted_user_approval(token, action="create_tea_entry", site="test.localhost", user="test@example.com")
        self.assertEqual(tea_entries.confirm_tea_entry(token, True)["status"], "created")
        declined = tea_entries.prepare_tea_entry(self.request)["approval_token"]
        self.assertEqual(tea_entries.confirm_tea_entry(declined, False)["code"], "CONFIRMATION_REQUIRED")
        self.assertEqual(tea_entries.confirm_tea_entry(declined, True)["code"], "CONFIRMATION_CONSUMED")
        self.db.commit.assert_called_once()

    def test_shared_binding_expiry_invalid_and_corruption(self):
        for field in ("action", "site", "user"):
            token = tea_entries.prepare_tea_entry(self.request)["approval_token"]
            mutate_record(self.store, self.backend, token, lambda row: setattr(row, field, "other"))
            self.assertEqual(tea_entries.confirm_tea_entry(token, True)["code"], "CONFIRMATION_UNAVAILABLE")
        token = tea_entries.prepare_tea_entry(self.request)["approval_token"]
        mutate_record(self.store, self.backend, token, lambda row: None, ttl_seconds=-1)
        self.assertEqual(tea_entries.confirm_tea_entry(token, True)["code"], "CONFIRMATION_EXPIRED")
        self.assertEqual(tea_entries.confirm_tea_entry("invalid", True)["code"], "CONFIRMATION_EXPIRED")
        token = tea_entries.prepare_tea_entry(self.request)["approval_token"]
        mutate_record(self.store, self.backend, token, lambda row: row.payload.update({"values_json": "{}"}))
        self.assertEqual(tea_entries.confirm_tea_entry(token, True)["code"], "CONFIRMATION_UNAVAILABLE")
        self.assert_no_write()


class TeaEntryUpdateTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"MCP_UPDATE_MODE": "approval_required"}))
        self.backend = FakeSharedApprovalBackend()
        self.store = ApprovalStore(ApprovalMode.AGENT_DELEGATED, backend=self.backend)
        self.stack.enter_context(patch.object(tea_entries, "approvals", self.store))
        self.db = SimpleNamespace(
            commit=Mock(),
            rollback=Mock(),
            exists=Mock(side_effect=lambda *_args, **_kwargs: "TEA-OTHER" if self.duplicate else None),
        )
        native_frappe = SimpleNamespace(
            db=self.db,
            throw=lambda **_kwargs: (_ for _ in ()).throw(
                frappe.ValidationError("RAW-SENTINEL")
            ),
        )
        self.stack.enter_context(
            patch("shayona.shayona.doctype.tea_entry.tea_entry.frappe", native_frappe)
        )
        self.source = dict(
            name="TEA-1", date=date(2026, 10, 1), no_of_cups=10,
            rate_per_cup=Decimal("15"), total_amount=Decimal("150"),
            vendor="Vendor A", modified="2026-10-01 10:00:00", permission=True,
        )
        self.documents = []
        self.duplicate = False
        self.save_error = None
        self.deleted = False
        self.validation_hook = lambda: None

        def load_doc(_doctype, _name):
            if self.deleted:
                raise frappe.DoesNotExistError("RAW-SENTINEL")
            doc = SimpleNamespace(**self.source)
            doc.set = lambda field, value: setattr(doc, field, value)
            doc.set_total_amount = lambda: TeaEntry.set_total_amount(doc)
            doc.validate_duplicate_date = lambda: TeaEntry.validate_duplicate_date(doc)
            doc.check_permission = lambda _permission: (
                None if doc.permission else (_ for _ in ()).throw(frappe.PermissionError())
            )
            def validate(_method):
                TeaEntry.validate(doc)
                self.validation_hook()
            doc.run_method = validate
            def save(**kwargs):
                self.assertEqual(kwargs, {"ignore_permissions": False})
                if self.save_error:
                    raise self.save_error
                doc.modified = "2026-10-02 11:00:00"
                self.source.update({key: getattr(doc, key) for key in (
                    "date", "no_of_cups", "rate_per_cup", "total_amount", "vendor", "modified",
                )})
                return doc
            doc.save = Mock(side_effect=save)
            self.documents.append(doc)
            self.doc = doc
            return doc

        self.doc = load_doc("Tea Entry", "TEA-1")
        self.fake = SimpleNamespace(
            session=SimpleNamespace(user="test@example.com"),
            local=SimpleNamespace(site="test.localhost"),
            get_meta=Mock(return_value=_meta()),
            get_doc=Mock(side_effect=load_doc),
            PermissionError=frappe.PermissionError,
            ValidationError=frappe.ValidationError,
            DoesNotExistError=frappe.DoesNotExistError,
            db=self.db,
        )
        self.stack.enter_context(patch.object(tea_entries, "frappe", self.fake))
        self.stack.enter_context(patch.object(
            tea_entries, "logged_public_error",
            side_effect=lambda tool, code, **kw: public_error(code, **kw),
        ))
        self.request = {
            "tea_entry_name": "TEA-1",
            "changes": {"no_of_cups": 12},
        }

    def _reset_source(self):
        self.source.update({
            "date": date(2026, 10, 1), "no_of_cups": 10,
            "rate_per_cup": Decimal("15"), "total_amount": Decimal("150"),
            "vendor": "Vendor A", "modified": "2026-10-01 10:00:00",
        })

    def test_bounded_contract_requires_supported_non_null_change(self):
        TeaEntryUpdateInput.model_validate(self.request)
        for value in (
            {"tea_entry_name": "TEA-1", "changes": {}},
            self.request | {"total_amount": 999},
            {"tea_entry_name": "TEA-1", "changes": {"no_of_cups": 0}},
            {"tea_entry_name": "TEA-1", "changes": {"rate_per_cup": "NaN"}},
            {"tea_entry_name": "TEA-1", "changes": {"vendor": " "}},
            {"tea_entry_name": "TEA-1", "changes": {"vendor": None}},
            {"tea_entry_name": "TEA-1", "changes": {"date": "2026-10-02", "owner": "x"}},
            self.request | {"ignore_permissions": True},
            self.request | {"MCP_UPDATE_MODE": "direct"},
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                TeaEntryUpdateInput.model_validate(value)

    def test_prepare_binds_fixed_before_after_and_native_total_without_saving(self):
        result = tea_entries.prepare_tea_entry_update(self.request)
        TeaEntryUpdatePrepareOutput.model_validate(result)
        self.assertEqual(result["status"], "ready")
        preview = result["preview"]
        self.assertEqual(preview["before"]["total_amount"], Decimal("150"))
        self.assertEqual(preview["after"]["total_amount"], Decimal("180"))
        self.assertEqual(preview["after"]["no_of_cups"], 12)
        self.assertNotIn("modified", str(preview))
        self.doc.save.assert_not_called()
        self.db.commit.assert_not_called()
        approval, state = self.store.lookup(
            result["approval_token"], action="update_tea_entry",
            site="test.localhost", user="test@example.com",
        )
        self.assertEqual(state, "available")
        self.assertEqual(set(approval.payload), {"request_json", "before_json", "preview_json", "modified"})

    def test_confirm_and_direct_execute_save_normally(self):
        ready = tea_entries.prepare_tea_entry_update(self.request)
        self._reset_source()
        result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)
        TeaEntryUpdateOutput.model_validate(result)
        self.assertEqual(result["status"], "updated")
        self.doc.save.assert_called_once_with(ignore_permissions=False)
        self.db.commit.assert_called_once()

        self.doc.save.reset_mock()
        self.db.commit.reset_mock()
        with patch.dict(os.environ, {"MCP_UPDATE_MODE": "direct"}), patch.object(tea_entries, "approvals") as store:
            preview = tea_entries.prepare_tea_entry_update(self.request)
            TeaEntryUpdatePrepareOutput.model_validate(preview)
            self.assertEqual(preview["status"], "preview")
            self.assertNotIn("approval_token", preview)
            self._reset_source()
            result = tea_entries.execute_tea_entry_update(self.request)
            TeaEntryUpdateOutput.model_validate(result)
            self.assertEqual(result["status"], "updated")
            self.assertEqual(store.mock_calls, [])
        self.doc.save.assert_called_once_with(ignore_permissions=False)
        self.db.commit.assert_called_once()

    def test_policy_rejections_and_final_mode_switches_do_not_save(self):
        for mode, expected in (
            ("disabled", "UPDATE_DISABLED"),
            ("approval_required", "APPROVAL_REQUIRED"),
        ):
            with patch.dict(os.environ, {"MCP_UPDATE_MODE": mode}):
                result = tea_entries.execute_tea_entry_update(self.request)
                self.assertEqual(result["code"], expected)
        transitions = (
            ("direct", "approval_required", "APPROVAL_REQUIRED"),
            ("direct", "disabled", "UPDATE_DISABLED"),
            ("approval_required", "direct", "DIRECT_EXECUTION_REQUIRED"),
            ("approval_required", "disabled", "UPDATE_DISABLED"),
        )
        for entry, target, expected in transitions:
            with self.subTest(entry=entry, target=target), patch.dict(os.environ, {"MCP_UPDATE_MODE": entry}):
                self.validation_hook = lambda: None
                if entry == "approval_required":
                    ready = tea_entries.prepare_tea_entry_update(self.request)
                    self._reset_source()
                    self.validation_hook = lambda: os.environ.__setitem__("MCP_UPDATE_MODE", target)
                    result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)
                else:
                    calls = []
                    def switch_mode():
                        calls.append(True)
                        if len(calls) == 1:
                            self._reset_source()
                        if len(calls) == 2:
                            os.environ["MCP_UPDATE_MODE"] = target
                    self.validation_hook = switch_mode
                    with patch.object(tea_entries, "approvals") as store:
                        result = tea_entries.execute_tea_entry_update(self.request)
                        self.assertEqual(store.mock_calls, [])
                self.assertEqual(result["code"], expected)
        self.assertEqual(self.doc.save.call_count, 0)
        self.db.commit.assert_not_called()

    def test_disabled_and_wrong_path_modes_reject_before_document_or_store_access(self):
        with patch.dict(os.environ, {"MCP_UPDATE_MODE": "disabled"}), patch.object(
            tea_entries.frappe, "get_doc"
        ) as get_doc, patch.object(tea_entries, "approvals") as store:
            self.assertEqual(tea_entries.prepare_tea_entry_update(self.request)["code"], "UPDATE_DISABLED")
            self.assertEqual(tea_entries.confirm_tea_entry_update("token", True)["code"], "UPDATE_DISABLED")
            self.assertEqual(tea_entries.execute_tea_entry_update(self.request)["code"], "UPDATE_DISABLED")
            get_doc.assert_not_called()
            self.assertEqual(store.mock_calls, [])
        with patch.dict(os.environ, {"MCP_UPDATE_MODE": "direct"}), patch.object(
            tea_entries, "approvals"
        ) as store:
            self.assertEqual(tea_entries.confirm_tea_entry_update("token", True)["code"], "DIRECT_EXECUTION_REQUIRED")
            self.assertEqual(store.mock_calls, [])
        with patch.dict(os.environ, {"MCP_UPDATE_MODE": "approval_required"}):
            self.assertEqual(tea_entries.execute_tea_entry_update(self.request)["code"], "APPROVAL_REQUIRED")

    def test_stale_and_native_failure_paths_rollback(self):
        ready = tea_entries.prepare_tea_entry_update(self.request)
        self.source["modified"] = "2026-10-02 10:00:00"
        self.assertEqual(
            tea_entries.confirm_tea_entry_update(ready["approval_token"], True)["code"],
            "STALE_CONFIRMATION",
        )
        self.assertEqual(self.doc.save.call_count, 0)
        self.db.commit.assert_not_called()

        ready = tea_entries.prepare_tea_entry_update(self.request)
        self.source["no_of_cups"] = 11
        self.source["total_amount"] = Decimal("165")
        self.assertEqual(
            tea_entries.confirm_tea_entry_update(ready["approval_token"], True)["code"],
            "STALE_CONFIRMATION",
        )
        self.assertEqual(self.doc.save.call_count, 0)

        with patch.dict(os.environ, {"MCP_UPDATE_MODE": "direct"}):
            self.duplicate = True
            result = tea_entries.execute_tea_entry_update(self.request)
            self.assertEqual(result["code"], "TEA_ENTRY_VALIDATION_FAILED")
            self.assertNotIn("RAW-SENTINEL", str(result))
        self.assertEqual(self.doc.save.call_count, 0)

    def test_deleted_target_after_prepare_is_stale_without_write(self):
        ready = tea_entries.prepare_tea_entry_update(self.request)
        self.deleted = True

        result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)

        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        self.assertNotIn("RAW-SENTINEL", str(result))
        self.assertEqual(self.doc.save.call_count, 0)
        self.db.commit.assert_not_called()

    def test_permission_revoked_after_prepare_blocks_confirmation_safely(self):
        ready = tea_entries.prepare_tea_entry_update(self.request)
        self.source["permission"] = False

        result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)

        self.assertEqual(result["code"], "ERP_PERMISSION_DENIED")
        self.assertNotIn("RAW-SENTINEL", str(result))
        self.doc.save.assert_not_called()
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    def test_duplicate_date_appearing_after_prepare_is_stale_and_safe(self):
        request = {"tea_entry_name": "TEA-1", "changes": {"date": "2026-10-02"}}
        ready = tea_entries.prepare_tea_entry_update(request)
        self._reset_source()
        self.duplicate = True

        result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)

        self.assertEqual(result["code"], "STALE_CONFIRMATION")
        self.assertNotIn("RAW-SENTINEL", str(result))
        self.doc.save.assert_not_called()
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    def test_confirmation_token_replay_is_rejected_after_single_write(self):
        ready = tea_entries.prepare_tea_entry_update(self.request)
        self._reset_source()

        first = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)
        second = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)

        self.assertEqual(first["status"], "updated")
        self.assertEqual(second["code"], "CONFIRMATION_CONSUMED")
        self.doc.save.assert_called_once_with(ignore_permissions=False)
        self.db.commit.assert_called_once()

    def test_shared_approval_binding_and_trusted_human_guard(self):
        for field in ("action", "site", "user"):
            with self.subTest(binding=field):
                ready = tea_entries.prepare_tea_entry_update(self.request)
                mutate_record(
                    self.store,
                    self.backend,
                    ready["approval_token"],
                    lambda approval: setattr(approval, field, "other"),
                )
                result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)
                self.assertEqual(result["code"], "CONFIRMATION_UNAVAILABLE")
                self.doc.save.assert_not_called()

        self.store.configure_approval_mode(ApprovalMode.TRUSTED_HUMAN)
        ready = tea_entries.prepare_tea_entry_update(self.request)
        result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)
        self.assertEqual(result["code"], "TRUSTED_APPROVAL_UNAVAILABLE")
        self.doc.save.assert_not_called()

        self.store.record_trusted_user_approval(
            ready["approval_token"],
            action="update_tea_entry",
            site="test.localhost",
            user="test@example.com",
        )
        self._reset_source()
        result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)
        self.assertEqual(result["status"], "updated")
        self.doc.save.assert_called_once_with(ignore_permissions=False)

    def test_apply_permission_and_save_failures_rollback_without_leaking_details(self):
        ready = tea_entries.prepare_tea_entry_update(self.request)
        self.source["permission"] = False
        result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)
        self.assertEqual(result["code"], "ERP_PERMISSION_DENIED")
        self.assertNotIn("RAW-SENTINEL", str(result))
        self.doc.save.assert_not_called()
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

        self._reset_source()
        self.source["permission"] = True
        self.db.rollback.reset_mock()
        ready = tea_entries.prepare_tea_entry_update(self.request)
        self._reset_source()
        self.save_error = RuntimeError("RAW-SENTINEL")
        result = tea_entries.confirm_tea_entry_update(ready["approval_token"], True)
        self.assertEqual(result["code"], "TEA_ENTRY_WRITE_FAILED")
        self.assertNotIn("RAW-SENTINEL", str(result))
        self.doc.save.assert_called_once_with(ignore_permissions=False)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
