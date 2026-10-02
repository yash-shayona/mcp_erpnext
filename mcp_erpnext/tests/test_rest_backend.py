from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mcp_erpnext import remote_operations, runtime
from mcp_erpnext.contracts.common import ToolError
from mcp_erpnext import remote_api
from mcp_erpnext.rest_client import ERPNextRestClient, RestBackendError
from mcp_erpnext.settings import MCPSettings
from mcp_erpnext.public_errors import defined_error


def _settings(**overrides) -> MCPSettings:
    values = {
        "backend": "rest",
        "frappe_site": None,
        "frappe_user": None,
        "erpnext_base_url": "https://erp.example.com",
        "erpnext_api_key": "test-key",
        "erpnext_api_secret": "test-secret",
        "transport": "stdio",
    }
    values.update(overrides)
    return MCPSettings(**values)


class RESTSettingsTests(unittest.TestCase):
    def test_rest_uses_one_fixed_https_method_endpoint(self):
        self.assertEqual(
            _settings().rest_endpoint_url(),
            "https://erp.example.com/api/method/mcp_erpnext.remote_api.execute_mcp_operation",
        )

    def test_rest_rejects_non_origin_or_insecure_non_local_base_url(self):
        for value in (
            "http://erp.example.com",
            "https://user:pass@erp.example.com",
            "https://erp.example.com/site-a",
            "https://erp.example.com?next=https://other.example",
        ):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                _settings(erpnext_base_url=value).validate()

    def test_rest_allows_explicit_loopback_http_for_local_development(self):
        settings = _settings(
            erpnext_base_url="http://your-site.localhost:8000",
            rest_allow_insecure_http=True,
        )
        self.assertEqual(
            settings.rest_endpoint_url(),
            "http://your-site.localhost:8000/api/method/mcp_erpnext.remote_api.execute_mcp_operation",
        )

    def test_insecure_http_opt_in_does_not_allow_a_live_or_lan_origin(self):
        for value in ("http://erp.example.com", "http://192.168.1.10:8000"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                _settings(
                    erpnext_base_url=value, rest_allow_insecure_http=True
                ).validate()

    def test_rest_rejects_local_streamable_http_identity_mix(self):
        with self.assertRaisesRegex(RuntimeError, "MCP_TRANSPORT=stdio"):
            _settings(transport="streamable-http").validate()

    @patch(
        "mcp_erpnext.observability.execute_tool",
        side_effect=lambda _name, operation: operation(),
    )
    @patch("mcp_erpnext.runtime.resolve_configured_frappe_user")
    @patch("mcp_erpnext.runtime._run_stdio_tool")
    @patch("mcp_erpnext.runtime.ERPNextRestClient")
    @patch("mcp_erpnext.runtime.MCPSettings.from_environment")
    def test_rest_execution_uses_only_remote_api_principal_semantics(
        self, from_environment, rest_client, run_stdio, resolve_user, _execute_tool
    ):
        from_environment.return_value = _settings(frappe_user="local@example.com")
        rest_client.return_value.execute.return_value = {"status": "ok"}

        result = runtime.execute_tool_with_context(
            Mock(), "search_customers", Mock(), rest_arguments={"query": "Acme"}
        )

        self.assertEqual(result, {"status": "ok"})
        run_stdio.assert_not_called()
        resolve_user.assert_not_called()
        rest_client.return_value.execute.assert_called_once_with(
            operation="search_customers", profile="sales", arguments={"query": "Acme"}
        )


class RemoteOperationRegistryTests(unittest.TestCase):
    def test_create_execute_handlers_are_static_typed_and_reject_policy_overrides(self):
        cases = (
            ("execute_customer", "customer", {"customer_name": "Acme"}),
            (
                "execute_contact",
                "standalone_contact",
                {"contact": {"first_name": "Amit"}},
            ),
            (
                "execute_quotation_to_sales_order",
                "quotation_to_sales_order",
                {"quotation": "SAL-QTN-1"},
            ),
            (
                "execute_sales_order_to_sales_invoice",
                "sales_order_to_sales_invoice",
                {"sales_order": "SAL-ORD-1"},
            ),
            (
                "execute_sales_order_to_delivery_note",
                "sales_order_to_delivery_note",
                {"sales_order": "SAL-ORD-1"},
            ),
            (
                "execute_sales_invoice_to_delivery_note",
                "sales_invoice_to_delivery_note",
                {"sales_invoice": "SAL-INV-1"},
            ),
            (
                "execute_delivery_note_to_sales_invoice",
                "delivery_note_to_sales_invoice",
                {"delivery_note": "DN-1"},
            ),
            (
                "execute_item",
                "item",
                {
                    "item_code": "ITEM-1",
                    "item_group": "Products",
                    "stock_uom": "Nos",
                },
            ),
            (
                "execute_customer_contact",
                "customer_contact",
                {
                    "customer": {"doctype": "Customer", "name": "CUST-1"},
                    "mode": "create",
                    "new_contact": {"first_name": "A"},
                },
            ),
            (
                "execute_sales_order",
                "sales_order",
                {
                    "customer": {"doctype": "Customer", "name": "CUST-1"},
                    "items": [
                        {"item": {"doctype": "Item", "name": "ITEM-1"}, "qty": 1}
                    ],
                },
            ),
            (
                "execute_quotation",
                "quotation",
                {
                    "customer": {"doctype": "Customer", "name": "CUST-1"},
                    "items": [
                        {"item": {"doctype": "Item", "name": "ITEM-1"}, "qty": 1}
                    ],
                },
            ),
            (
                "execute_sales_invoice",
                "sales_invoice",
                {
                    "customer": {"doctype": "Customer", "name": "CUST-1"},
                    "items": [
                        {
                            "item": {"doctype": "Item", "name": "ITEM-1"},
                            "qty": 1,
                            "rate": 1,
                        }
                    ],
                },
            ),
        )
        for operation, service_name, arguments in cases:
            service = getattr(remote_operations, service_name)
            with (
                self.subTest(operation=operation),
                patch.object(
                    service, operation, return_value={"status": "created"}
                ) as execute,
            ):
                result = remote_operations.execute_remote_operation(
                    operation, "sales", arguments
                )
            self.assertEqual(result, {"status": "created"})
            execute.assert_called_once()
            for override in ("create_mode", "MCP_CREATE_MODE"):
                with self.subTest(operation=operation, override=override):
                    with self.assertRaises(remote_operations.RemoteOperationError):
                        remote_operations.execute_remote_operation(
                            operation,
                            "sales",
                            {**arguments, override: "approval_required"},
                        )

    def test_purchase_create_execute_handlers_are_static_and_reject_policy_overrides(
        self,
    ):
        cases = (
            (
                "execute_purchase_order",
                "purchase_order",
                {
                    "supplier": {"doctype": "Supplier", "name": "SUP-1"},
                    "items": [
                        {"item": {"doctype": "Item", "name": "ITEM-1"}, "qty": 1}
                    ],
                },
            ),
            (
                "execute_purchase_order_to_purchase_receipt",
                "purchase_order_to_purchase_receipt",
                {
                    "purchase_order": "PO-1",
                    "lines": [{"purchase_order_item": "PO-ITEM-1", "accepted_qty": 1}],
                },
            ),
        )
        for operation, service_name, arguments in cases:
            service = getattr(remote_operations, service_name)
            with (
                self.subTest(operation=operation),
                patch.object(
                    service, operation, return_value={"status": "created"}
                ) as execute,
            ):
                result = remote_operations.execute_remote_operation(
                    operation, "purchase", arguments
                )
            self.assertEqual(result, {"status": "created"})
            execute.assert_called_once()
            for override in ("create_mode", "MCP_CREATE_MODE"):
                with self.subTest(operation=operation, override=override):
                    with self.assertRaises(remote_operations.RemoteOperationError):
                        remote_operations.execute_remote_operation(
                            operation, "purchase", {**arguments, override: "direct"}
                        )

    def test_shayona_tea_create_is_all_only_typed_and_uses_shared_service(self):
        operations = {
            "prepare_tea_entry": {
                "no_of_cups": 2,
                "rate_per_cup": "15",
                "date": "2026-10-02",
            },
            "execute_tea_entry": {"no_of_cups": 2, "rate_per_cup": "15"},
            "confirm_tea_entry": {"approval_token": "token", "confirm": True},
        }
        for operation, arguments in operations.items():
            with (
                self.subTest(operation=operation),
                patch.object(
                    remote_operations.shayona_tea_entries,
                    operation,
                    return_value={"status": "created"},
                ) as service,
            ):
                self.assertEqual(
                    remote_operations.execute_remote_operation(
                        operation, "all", arguments
                    ),
                    {"status": "created"},
                )
                service.assert_called_once()
                if operation == "confirm_tea_entry":
                    service.assert_called_once_with("token", True)
                else:
                    self.assertEqual(service.call_args.args[0]["no_of_cups"], 2)
                for profile in ("sales", "purchase", "accounts"):
                    with self.assertRaises(remote_operations.RemoteOperationError):
                        remote_operations.execute_remote_operation(
                            operation, profile, arguments
                        )
                for key in (
                    "total_amount",
                    "ignore_permissions",
                    "create_mode",
                    "MCP_CREATE_MODE",
                    "unknown",
                    "approved",
                    "owner",
                ):
                    with (
                        self.subTest(key=key),
                        self.assertRaises(remote_operations.RemoteOperationError),
                    ):
                        remote_operations.execute_remote_operation(
                            operation, "all", arguments | {key: True}
                        )
                self.assertEqual(service.call_count, 1)
        for operation in ("create_tea_entry", "update_tea_entry"):
            with self.assertRaises(remote_operations.RemoteOperationError):
                remote_operations.execute_remote_operation(operation, "all", {})

    def test_shayona_tea_update_is_all_only_typed_and_rejects_bypass_fields(self):
        cases = {
            "prepare_tea_entry_update": {
                "tea_entry_name": "TEA-1",
                "changes": {"no_of_cups": 12},
            },
            "execute_tea_entry_update": {
                "tea_entry_name": "TEA-1",
                "changes": {"vendor": "Vendor B"},
            },
            "confirm_tea_entry_update": {"approval_token": "token", "confirm": True},
        }
        for operation, arguments in cases.items():
            with (
                self.subTest(operation=operation),
                patch.object(
                    remote_operations.shayona_tea_entries,
                    operation,
                    return_value={"status": "updated"},
                ) as service,
            ):
                self.assertEqual(
                    remote_operations.execute_remote_operation(
                        operation, "all", arguments
                    ),
                    {"status": "updated"},
                )
                service.assert_called_once()
                if operation == "confirm_tea_entry_update":
                    service.assert_called_once_with("token", True)
                else:
                    self.assertEqual(
                        service.call_args.args[0]["tea_entry_name"], "TEA-1"
                    )
                for profile in ("sales", "purchase", "accounts"):
                    with self.assertRaises(remote_operations.RemoteOperationError):
                        remote_operations.execute_remote_operation(
                            operation, profile, arguments
                        )
                for field in (
                    "total_amount",
                    "ignore_permissions",
                    "update_mode",
                    "MCP_UPDATE_MODE",
                    "approved",
                    "owner",
                    "modified",
                    "docstatus",
                    "unknown",
                ):
                    with (
                        self.subTest(field=field),
                        self.assertRaises(remote_operations.RemoteOperationError),
                    ):
                        if "changes" in arguments:
                            invalid = arguments | {
                                "changes": arguments["changes"] | {field: 1}
                            }
                        else:
                            invalid = arguments | {field: 1}
                        remote_operations.execute_remote_operation(
                            operation, "all", invalid
                        )
                self.assertEqual(service.call_count, 1)

    def test_shayona_tea_entry_reads_are_all_only_and_typed(self):
        operations = {
            "get_tea_entry": {"tea_entry_name": "TEA-1"},
            "query_tea_entries": {"limit": 1, "offset": 0},
            "aggregate_tea_entries": {"metrics": ["count"]},
        }
        with patch.dict(
            remote_operations.shayona_tea_entries.__dict__,
            {
                "get_tea_entry": Mock(return_value={"status": "ok"}),
                "query_tea_entries": Mock(return_value={"status": "ok"}),
                "aggregate_tea_entries": Mock(return_value={"status": "ok"}),
            },
        ):
            for operation, arguments in operations.items():
                self.assertEqual(
                    remote_operations.execute_remote_operation(
                        operation, "all", arguments
                    ),
                    {"status": "ok"},
                )
                for profile in ("sales", "purchase", "accounts"):
                    with self.assertRaises(remote_operations.RemoteOperationError):
                        remote_operations.execute_remote_operation(
                            operation, profile, arguments
                        )

        for arguments in (
            {"ignore_permissions": True},
            {"fields": ["owner"]},
            {"date": "2026-10-01", "date_from": "2026-09-01"},
            {"limit": 1, "create": True},
        ):
            with self.assertRaises(remote_operations.RemoteOperationError):
                remote_operations.execute_remote_operation(
                    "query_tea_entries", "all", arguments
                )

    def test_shayona_credential_operations_are_all_only_and_typed(self):
        operations = {
            "search_customer_service_credentials": {"limit": 1},
            "get_customer_service_credential": {"credential_name": "ST-CSC-1"},
            "query_customer_service_credentials": {"limit": 1, "offset": 0},
            "aggregate_customer_service_credentials": {"metrics": ["count"]},
        }
        with patch(
            "mcp_erpnext.remote_operations.shayona_credentials.credential_schema"
        ):
            with patch.dict(
                remote_operations.shayona_credentials.__dict__,
                {
                    "search_customer_service_credentials": Mock(
                        return_value={"status": "ok"}
                    ),
                    "get_customer_service_credential": Mock(
                        return_value={"status": "ok"}
                    ),
                    "query_customer_service_credentials": Mock(
                        return_value={"status": "ok"}
                    ),
                    "aggregate_customer_service_credentials": Mock(
                        return_value={"status": "ok"}
                    ),
                },
            ):
                for operation, arguments in operations.items():
                    self.assertEqual(
                        remote_operations.execute_remote_operation(
                            operation, "all", arguments
                        ),
                        {"status": "ok"},
                    )
                    for profile in ("sales", "purchase", "accounts"):
                        with self.assertRaises(remote_operations.RemoteOperationError):
                            remote_operations.execute_remote_operation(
                                operation, profile, arguments
                            )

        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "query_customer_service_credentials",
                "all",
                {"limit": 1, "offset": 0, "username": "secret"},
            )

    def test_shayona_credential_email_operations_are_all_only_and_typed(self):
        with patch.dict(
            remote_operations.shayona_credential_email.__dict__,
            {
                "prepare_customer_service_credential_email": Mock(
                    return_value={"status": "ready_for_approval"}
                ),
                "confirm_customer_service_credential_email": Mock(
                    return_value={"status": "queued"}
                ),
                "execute_customer_service_credential_email": Mock(
                    return_value={"status": "queued"}
                ),
            },
        ):
            self.assertEqual(
                remote_operations.execute_remote_operation(
                    "prepare_customer_service_credential_email",
                    "all",
                    {"credential_name": "CSC-1", "recipient_email": "a@example.com"},
                )["status"],
                "ready_for_approval",
            )
            self.assertEqual(
                remote_operations.execute_remote_operation(
                    "confirm_customer_service_credential_email",
                    "all",
                    {"approval_token": "opaque"},
                )["status"],
                "queued",
            )
            self.assertEqual(
                remote_operations.execute_remote_operation(
                    "execute_customer_service_credential_email",
                    "all",
                    {"credential_name": "CSC-1", "recipient_email": "a@example.com"},
                )["status"],
                "queued",
            )
            for profile in ("sales", "purchase", "accounts"):
                for operation, arguments in (
                    (
                        "prepare_customer_service_credential_email",
                        {
                            "credential_name": "CSC-1",
                            "recipient_email": "a@example.com",
                        },
                    ),
                    (
                        "confirm_customer_service_credential_email",
                        {"approval_token": "opaque"},
                    ),
                    (
                        "execute_customer_service_credential_email",
                        {
                            "credential_name": "CSC-1",
                            "recipient_email": "a@example.com",
                        },
                    ),
                ):
                    with (
                        self.subTest(profile=profile, operation=operation),
                        self.assertRaises(remote_operations.RemoteOperationError),
                    ):
                        remote_operations.execute_remote_operation(
                            operation, profile, arguments
                        )

        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "prepare_customer_service_credential_email",
                "all",
                {
                    "credential_name": "CSC-1",
                    "recipient_email": "a@example.com",
                    "username": "secret",
                },
            )

        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "confirm_customer_service_credential_email",
                "all",
                {"approval_token": "opaque", "password": "secret"},
            )

        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "execute_customer_service_credential_email",
                "all",
                {
                    "credential_name": "CSC-1",
                    "recipient_email": "a@example.com",
                    "mode": "direct",
                },
            )

    def test_document_email_execute_is_a_fixed_profile_aware_remote_operation(self):
        with patch.object(
            remote_operations.email,
            "execute_document_email",
            return_value={"status": "queued"},
        ) as execute:
            result = remote_operations.execute_remote_operation(
                "execute_document_email",
                "purchase",
                {
                    "doctype": "Purchase Order",
                    "name": "PO-001",
                    "recipient_scope": "party",
                },
            )
        self.assertEqual(result["status"], "queued")
        self.assertEqual(
            execute.call_args.args[:3], ("Purchase Order", "PO-001", "purchase")
        )
        for invalid in (
            {"doctype": "Purchase Order", "name": "PO-001", "policy": "direct"},
            {"doctype": "Purchase Order", "name": "PO-001", "approval_token": "opaque"},
        ):
            with (
                self.subTest(invalid=invalid),
                self.assertRaises(remote_operations.RemoteOperationError),
            ):
                remote_operations.execute_remote_operation(
                    "execute_document_email", "purchase", invalid
                )

    def test_remote_prepare_enforces_executor_update_policy_before_load(self):
        with (
            patch.dict(os.environ, {"MCP_UPDATE_MODE": "disabled"}, clear=False),
            patch.object(remote_operations.lifecycle.frappe, "get_doc") as get_doc,
        ):
            result = remote_operations.execute_remote_operation(
                "prepare_document_update",
                "sales",
                {
                    "target": {"doctype": "Sales Order", "name": "SO-001"},
                    "changes": [{"field": "remarks", "value": "x"}],
                },
            )
        self.assertEqual(result["code"], "UPDATE_DISABLED")
        get_doc.assert_not_called()

    def test_remote_direct_update_uses_server_lifecycle_handler(self):
        with (
            patch.dict(os.environ, {"MCP_UPDATE_MODE": "direct"}, clear=False),
            patch.object(
                remote_operations.lifecycle,
                "execute_update",
                return_value={"status": "updated"},
            ) as execute,
        ):
            result = remote_operations.execute_remote_operation(
                "execute_document_update",
                "sales",
                {
                    "target": {"doctype": "Sales Order", "name": "SO-001"},
                    "changes": [{"field": "remarks", "value": "direct"}],
                },
            )
        self.assertEqual(result, {"status": "updated"})
        execute.assert_called_once_with(
            {"doctype": "Sales Order", "name": "SO-001"},
            [{"field": "remarks", "value": "direct", "child_table": None, "row": None}],
            "sales",
        )

    def test_remote_confirm_cannot_bypass_executor_update_policy(self):
        with (
            patch.dict(os.environ, {"MCP_UPDATE_MODE": "disabled"}, clear=False),
            patch.object(
                remote_operations.lifecycle.frappe,
                "session",
                SimpleNamespace(user="remote@example.com"),
            ),
            patch.object(
                remote_operations.lifecycle.frappe,
                "local",
                SimpleNamespace(site="remote.localhost"),
            ),
            patch.object(
                remote_operations.lifecycle.approvals, "claim_for_confirm_write"
            ) as claim,
        ):
            result = remote_operations.execute_remote_operation(
                "confirm_document_update",
                "sales",
                {"approval_token": "opaque", "confirm": True},
            )
        self.assertEqual(result["code"], "UPDATE_DISABLED")
        claim.assert_not_called()

    def test_invalid_remote_executor_update_policy_fails_before_load(self):
        with (
            patch.dict(os.environ, {"MCP_UPDATE_MODE": "invalid"}, clear=False),
            patch.object(remote_operations.lifecycle.frappe, "get_doc") as get_doc,
        ):
            with self.assertRaisesRegex(RuntimeError, "MCP_UPDATE_MODE"):
                remote_operations.execute_remote_operation(
                    "prepare_document_update",
                    "sales",
                    {
                        "target": {"doctype": "Sales Order", "name": "SO-001"},
                        "changes": [{"field": "remarks", "value": "x"}],
                    },
                )
        get_doc.assert_not_called()

    def test_remote_update_arguments_cannot_override_executor_policy(self):
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "prepare_document_update",
                "sales",
                {
                    "target": {"doctype": "Sales Order", "name": "SO-001"},
                    "changes": [{"field": "remarks", "value": "x"}],
                    "update_mode": "approval_required",
                },
            )

    def test_remote_prepare_enforces_executor_delete_policy_before_load(self):
        with (
            patch.dict(os.environ, {"MCP_DELETE_MODE": "disabled"}, clear=False),
            patch.object(remote_operations.lifecycle.frappe, "get_doc") as get_doc,
        ):
            result = remote_operations.execute_remote_operation(
                "prepare_document_delete",
                "sales",
                {"target": {"doctype": "Sales Order", "name": "SO-001"}},
            )
        self.assertEqual(result["code"], "DELETE_DISABLED")
        get_doc.assert_not_called()

    def test_remote_confirm_cannot_bypass_executor_cancel_policy(self):
        with (
            patch.dict(os.environ, {"MCP_CANCEL_MODE": "disabled"}, clear=False),
            patch.object(
                remote_operations.lifecycle.frappe,
                "session",
                SimpleNamespace(user="remote@example.com"),
            ),
            patch.object(
                remote_operations.lifecycle.frappe,
                "local",
                SimpleNamespace(site="remote.localhost"),
            ),
            patch.object(
                remote_operations.lifecycle.approvals, "claim_for_confirm_write"
            ) as claim,
        ):
            result = remote_operations.execute_remote_operation(
                "confirm_document_cancel",
                "sales",
                {"approval_token": "opaque", "confirm": True},
            )
        self.assertEqual(result["code"], "CANCEL_DISABLED")
        claim.assert_not_called()

    def test_invalid_remote_executor_lifecycle_policy_fails_before_load(self):
        with (
            patch.dict(os.environ, {"MCP_DELETE_MODE": "invalid"}, clear=False),
            patch.object(remote_operations.lifecycle.frappe, "get_doc") as get_doc,
        ):
            with self.assertRaisesRegex(RuntimeError, "MCP_DELETE_MODE"):
                remote_operations.execute_remote_operation(
                    "prepare_document_delete",
                    "sales",
                    {"target": {"doctype": "Sales Order", "name": "SO-001"}},
                )
        get_doc.assert_not_called()

    @patch("mcp_erpnext.remote_operations.customer_contact.search_contacts")
    def test_sales_contact_search_uses_fixed_typed_handler(self, search_contacts):
        search_contacts.return_value = {
            "status": "ok",
            "contacts": [],
            "count": 0,
            "limit": 20,
            "offset": 0,
        }
        result = remote_operations.execute_remote_operation(
            "search_contacts", "sales", {"query": "amit@example.com", "match": "email"}
        )
        self.assertEqual(result["status"], "ok")
        search_contacts.assert_called_once()

    def test_contact_mutation_is_not_available_in_purchase_or_accounts(self):
        for profile in ("purchase", "accounts"):
            with (
                self.subTest(profile=profile),
                self.assertRaises(remote_operations.RemoteOperationError),
            ):
                remote_operations.execute_remote_operation(
                    "prepare_customer_contact",
                    profile,
                    {
                        "customer": {"doctype": "Customer", "name": "CUST-1"},
                        "mode": "create",
                        "new_contact": {"first_name": "A"},
                    },
                )

    @patch("mcp_erpnext.remote_operations.terms.resolve_terms_and_conditions")
    def test_sales_terms_resolver_uses_the_same_typed_service(self, resolve_terms):
        resolve_terms.return_value = {
            "status": "resolved",
            "doctype": "Terms and Conditions",
            "reference": {
                "doctype": "Terms and Conditions",
                "name": "Sales Order Terms",
            },
            "match_type": "exact",
        }
        result = remote_operations.execute_remote_operation(
            "resolve_terms_and_conditions", "sales", {"query": "sales order terms"}
        )
        self.assertEqual(result["reference"]["name"], "Sales Order Terms")
        resolve_terms.assert_called_once_with("sales order terms")
        for profile in ("purchase", "accounts"):
            with (
                self.subTest(profile=profile),
                self.assertRaises(remote_operations.RemoteOperationError),
            ):
                remote_operations.execute_remote_operation(
                    "resolve_terms_and_conditions",
                    profile,
                    {"query": "sales order terms"},
                )

    @patch("mcp_erpnext.remote_operations.customer.search_customers")
    def test_sales_operation_uses_fixed_handler(self, search_customers):
        search_customers.return_value = {"status": "resolved", "results": []}
        result = remote_operations.execute_remote_operation(
            "search_customers", "sales", {"query": "Acme"}
        )
        self.assertEqual(result["status"], "resolved")
        search_customers.assert_called_once_with("Acme")

    @patch(
        "mcp_erpnext.remote_operations.delivery_note_to_sales_invoice.prepare_delivery_note_to_sales_invoice"
    )
    def test_delivery_note_conversion_uses_fixed_typed_handler(self, prepare):
        expected = defined_error("SOURCE_NOT_FOUND", reference="MCP-ERR-TEST")
        prepare.return_value = expected
        result = remote_operations.execute_remote_operation(
            "prepare_delivery_note_to_sales_invoice",
            "sales",
            {"delivery_note": "MAT-DN-0001"},
        )
        self.assertEqual(result, expected)
        prepare.assert_called_once_with("MAT-DN-0001")

    @patch(
        "mcp_erpnext.remote_operations.purchase_order_to_purchase_receipt.prepare_purchase_order_to_purchase_receipt"
    )
    def test_purchase_receipt_conversion_preserves_catalog_error(self, prepare):
        expected = defined_error("QUANTITY_EXCEEDS_REMAINING", reference="MCP-ERR-TEST")
        prepare.return_value = expected
        result = remote_operations.execute_remote_operation(
            "prepare_purchase_order_to_purchase_receipt",
            "purchase",
            {
                "purchase_order": "PUR-ORD-0001",
                "lines": [{"purchase_order_item": "PO-ITEM-0001", "accepted_qty": 1}],
            },
        )
        self.assertEqual(result, expected)
        prepare.assert_called_once()

    @patch(
        "mcp_erpnext.remote_operations.sales_invoice_to_delivery_note.prepare_sales_invoice_to_delivery_note"
    )
    def test_sales_invoice_delivery_note_conversion_uses_fixed_typed_handler(
        self, prepare
    ):
        prepare.return_value = {
            "status": "error",
            "code": "SOURCE_NOT_FOUND",
            "message": "missing",
            "reference": "MCP-ERR-TEST",
        }
        result = remote_operations.execute_remote_operation(
            "prepare_sales_invoice_to_delivery_note",
            "sales",
            {"sales_invoice": "ACC-SINV-0001"},
        )
        self.assertEqual(result["code"], "SOURCE_NOT_FOUND")
        prepare.assert_called_once_with("ACC-SINV-0001")

    @patch(
        "mcp_erpnext.remote_operations.sales_invoice_to_delivery_note.confirm_sales_invoice_to_delivery_note"
    )
    def test_sales_invoice_delivery_note_confirm_uses_fixed_typed_handler(
        self, confirm
    ):
        confirm.return_value = {"status": "error", "code": "CONFIRMATION_UNAVAILABLE"}
        result = remote_operations.execute_remote_operation(
            "confirm_sales_invoice_to_delivery_note",
            "sales",
            {"approval_token": "opaque", "confirm": True},
        )
        self.assertEqual(result["code"], "CONFIRMATION_UNAVAILABLE")
        confirm.assert_called_once_with("opaque", True)

    def test_unknown_operation_and_invalid_payload_fail_closed(self):
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation("frappe.db.sql", "sales", {})
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "search_customers", "sales", {"unknown": True}
            )

    def test_sales_operation_is_not_available_in_purchase_profile(self):
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "search_customers", "purchase", {"query": "Acme"}
            )

    @patch("mcp_erpnext.remote_operations.payment_entry_read.query_payment_entries")
    def test_accounts_payment_entry_read_uses_fixed_typed_handler(self, query):
        query.return_value = {
            "status": "ok",
            "payment_entries": [],
            "count": 0,
            "limit": 20,
            "offset": 0,
        }
        result = remote_operations.execute_remote_operation(
            "query_payment_entries", "accounts", {"party_type": "Customer"}
        )
        self.assertEqual(result["status"], "ok")
        query.assert_called_once()
        self.assertNotIn("ignore_permissions", query.call_args.args[0])

    def test_payment_entry_read_is_not_available_in_sales_profile(self):
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "get_payment_entry", "sales", {"name": "PE-1"}
            )

    @patch(
        "mcp_erpnext.remote_operations.multi_invoice_customer_receipt.prepare_multi_invoice_customer_receipt"
    )
    def test_multi_invoice_receipt_uses_fixed_typed_accounts_handler(self, prepare):
        expected = defined_error("NO_OUTSTANDING", reference="MCP-ERR-TEST")
        prepare.return_value = expected
        result = remote_operations.execute_remote_operation(
            "prepare_multi_invoice_customer_receipt",
            "accounts",
            {
                "customer": "CUST-1",
                "amount": 30,
                "allocations": [
                    {"sales_invoice": "SINV-1", "allocated_amount": 10},
                    {"sales_invoice": "SINV-2", "allocated_amount": 20},
                ],
                "mode_of_payment": "Bank Transfer",
            },
        )
        self.assertEqual(result, expected)
        prepare.assert_called_once()

    def test_multi_invoice_receipt_is_accounts_only(self):
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "prepare_multi_invoice_customer_receipt",
                "sales",
                {
                    "customer": "CUST-1",
                    "amount": 20,
                    "allocations": [
                        {"sales_invoice": "SINV-1", "allocated_amount": 10},
                        {"sales_invoice": "SINV-2", "allocated_amount": 10},
                    ],
                    "bank_account": "BANK-1",
                },
            )

    @patch(
        "mcp_erpnext.remote_operations.sales_order_advance_payment.prepare_sales_order_advance_payment"
    )
    def test_sales_order_advance_payment_uses_fixed_typed_accounts_handler(
        self, prepare
    ):
        prepare.return_value = {
            "status": "error",
            "code": "SALES_ORDER_NOT_FOUND",
            "message": "missing",
            "reference": "MCP-ERR-TEST",
        }
        result = remote_operations.execute_remote_operation(
            "prepare_sales_order_advance_payment",
            "accounts",
            {
                "sales_order": "SAL-ORD-1",
                "amount": 50,
                "mode_of_payment": "Bank Transfer",
            },
        )
        self.assertEqual(result["code"], "SALES_ORDER_NOT_FOUND")
        prepare.assert_called_once()

    def test_sales_order_advance_payment_is_accounts_only(self):
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "prepare_sales_order_advance_payment",
                "sales",
                {"sales_order": "SAL-ORD-1", "amount": 50, "bank_account": "BANK-1"},
            )

    @patch(
        "mcp_erpnext.remote_operations.sales_order_advance_payment.confirm_sales_order_advance_payment"
    )
    def test_sales_order_advance_payment_confirm_uses_fixed_typed_handler(
        self, confirm
    ):
        confirm.return_value = {"status": "error", "code": "CONFIRMATION_UNAVAILABLE"}
        result = remote_operations.execute_remote_operation(
            "confirm_sales_order_advance_payment",
            "accounts",
            {"approval_token": "opaque", "confirm": True},
        )
        self.assertEqual(result["code"], "CONFIRMATION_UNAVAILABLE")
        confirm.assert_called_once_with("opaque", True)

    @patch(
        "mcp_erpnext.remote_operations.customer_payment_reconciliation.prepare_customer_payment_reconciliation"
    )
    def test_customer_payment_reconciliation_uses_fixed_typed_accounts_handler(
        self, prepare
    ):
        prepare.return_value = {
            "status": "error",
            "code": "PAYMENT_ENTRY_NOT_FOUND",
            "message": "missing",
            "reference": "MCP-ERR-TEST",
        }
        result = remote_operations.execute_remote_operation(
            "prepare_customer_payment_reconciliation",
            "accounts",
            {"payment_entry": "ACC-PAY-1", "sales_invoice": "ACC-SINV-1", "amount": 25},
        )
        self.assertEqual(result["code"], "PAYMENT_ENTRY_NOT_FOUND")
        prepare.assert_called_once_with(
            {"payment_entry": "ACC-PAY-1", "sales_invoice": "ACC-SINV-1", "amount": 25}
        )

    @patch(
        "mcp_erpnext.remote_operations.customer_payment_reconciliation.confirm_customer_payment_reconciliation"
    )
    def test_customer_payment_reconciliation_confirm_uses_fixed_typed_handler(
        self, confirm
    ):
        confirm.return_value = {"status": "error", "code": "CONFIRMATION_UNAVAILABLE"}
        result = remote_operations.execute_remote_operation(
            "confirm_customer_payment_reconciliation",
            "accounts",
            {"approval_token": "opaque", "confirm": True},
        )
        self.assertEqual(result["code"], "CONFIRMATION_UNAVAILABLE")
        confirm.assert_called_once_with("opaque", True)

    def test_customer_payment_reconciliation_is_accounts_only(self):
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "prepare_customer_payment_reconciliation",
                "sales",
                {
                    "payment_entry": "ACC-PAY-1",
                    "sales_invoice": "ACC-SINV-1",
                    "amount": 25,
                },
            )


class RemoteErrorTests(unittest.TestCase):
    @patch("mcp_erpnext.remote_api.logged_defined_error")
    def test_remote_safe_error_keeps_the_required_reference_contract(
        self, logged_error
    ):
        logged_error.return_value = {
            "status": "error",
            "code": "ERP_PERMISSION_DENIED",
            "message": "The configured ERPNext user does not have permission for that request. Please contact your administrator.",
            "reference": "MCP-ERR-97C4A07F",
            "retryable": False,
        }

        result = remote_api._safe_error("ERP_PERMISSION_DENIED")

        self.assertEqual(ToolError.model_validate(result).reference, "MCP-ERR-97C4A07F")
        logged_error.assert_called_once_with(
            "remote_api", "ERP_PERMISSION_DENIED", level="warning"
        )


class RESTClientTests(unittest.TestCase):
    def test_client_uses_header_auth_and_fixed_envelope(self):
        request_seen = {}

        class Response:
            def read(self):
                return json.dumps({"message": {"status": "ok"}}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class Opener:
            def open(self, request, *, timeout):
                request_seen["request"] = request
                request_seen["timeout"] = timeout
                return Response()

        with patch("mcp_erpnext.rest_client.build_opener", return_value=Opener()):
            result = ERPNextRestClient(_settings()).execute(
                operation="search_customers",
                profile="sales",
                arguments={"query": "Acme"},
            )

        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(request_seen["timeout"], 15)
        self.assertNotIn("test-secret", request_seen["request"].full_url)
        self.assertEqual(
            json.loads(request_seen["request"].data)["payload"],
            '{"operation":"search_customers","profile":"sales","arguments":{"query":"Acme"}}',
        )

    def test_client_rejects_a_malformed_remote_response(self):
        class Response:
            def read(self):
                return b'{"message": []}'

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with (
            patch(
                "mcp_erpnext.rest_client.build_opener",
                return_value=SimpleNamespace(open=lambda *_args, **_kwargs: Response()),
            ),
            self.assertRaises(RestBackendError),
        ):
            ERPNextRestClient(_settings()).execute(
                operation="search_customers",
                profile="sales",
                arguments={"query": "Acme"},
            )

    @patch("mcp_erpnext.observability.get_app_logger")
    @patch("mcp_erpnext.runtime.MCPSettings.from_environment")
    def test_uncertain_mutation_timeout_is_not_retried_or_reported_as_success(
        self, from_environment, get_app_logger
    ):
        get_app_logger.return_value = Mock()
        from_environment.return_value = _settings()

        class Opener:
            calls = 0

            def open(self, _request, *, timeout):
                self.calls += 1
                self.timeout = timeout
                raise TimeoutError("remote commit outcome is unknown")

        opener = Opener()
        with patch("mcp_erpnext.rest_client.build_opener", return_value=opener):
            result = runtime.execute_tool_with_context(
                Mock(),
                "confirm_sales_order",
                Mock(),
                rest_arguments={"approval_token": "opaque", "confirm": True},
            )

        self.assertEqual(opener.calls, 1)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "ORDER_CREATE_UNAVAILABLE")
        self.assertFalse(result["retryable"])
        self.assertNotIn("remote commit outcome is unknown", result["message"])

    @patch("mcp_erpnext.remote_operations.item.search_all_items")
    def test_all_profile_item_lookup_uses_explicit_fixed_handler(self, search):
        search.return_value = {
            "status": "not_found",
            "doctype": "Item",
            "query": "only",
            "candidates": [],
        }
        result = remote_operations.execute_remote_operation(
            "search_items", "all", {"query": "only"}
        )
        self.assertEqual(result["status"], "not_found")
        search.assert_called_once_with("only")
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation("frappe.db.sql", "all", {})
