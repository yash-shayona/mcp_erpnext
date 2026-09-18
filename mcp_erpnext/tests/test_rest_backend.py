from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mcp_erpnext import remote_operations, runtime
from mcp_erpnext.contracts.common import ToolError
from mcp_erpnext import remote_api
from mcp_erpnext.rest_client import ERPNextRestClient, RestBackendError
from mcp_erpnext.settings import MCPSettings


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
            erpnext_base_url="http://yob.localhost:8000",
            rest_allow_insecure_http=True,
        )
        self.assertEqual(
            settings.rest_endpoint_url(),
            "http://yob.localhost:8000/api/method/mcp_erpnext.remote_api.execute_mcp_operation",
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

    @patch("mcp_erpnext.observability.execute_tool", side_effect=lambda _name, operation: operation())
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
    @patch("mcp_erpnext.remote_operations.customer.search_customers")
    def test_sales_operation_uses_fixed_handler(self, search_customers):
        search_customers.return_value = {"status": "resolved", "results": []}
        result = remote_operations.execute_remote_operation(
            "search_customers", "sales", {"query": "Acme"}
        )
        self.assertEqual(result["status"], "resolved")
        search_customers.assert_called_once_with("Acme")

    @patch("mcp_erpnext.remote_operations.delivery_note_to_sales_invoice.prepare_delivery_note_to_sales_invoice")
    def test_delivery_note_conversion_uses_fixed_typed_handler(self, prepare):
        prepare.return_value = {"status": "error", "code": "SOURCE_NOT_FOUND", "message": "missing", "reference": "MCP-ERR-TEST"}
        result = remote_operations.execute_remote_operation(
            "prepare_delivery_note_to_sales_invoice", "sales", {"delivery_note": "MAT-DN-0001"}
        )
        self.assertEqual(result["code"], "SOURCE_NOT_FOUND")
        prepare.assert_called_once_with("MAT-DN-0001")

    @patch("mcp_erpnext.remote_operations.sales_invoice_to_delivery_note.prepare_sales_invoice_to_delivery_note")
    def test_sales_invoice_delivery_note_conversion_uses_fixed_typed_handler(self, prepare):
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

    @patch("mcp_erpnext.remote_operations.sales_invoice_to_delivery_note.confirm_sales_invoice_to_delivery_note")
    def test_sales_invoice_delivery_note_confirm_uses_fixed_typed_handler(self, confirm):
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
            remote_operations.execute_remote_operation("search_customers", "sales", {"unknown": True})

    def test_sales_operation_is_not_available_in_purchase_profile(self):
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation("search_customers", "purchase", {"query": "Acme"})

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
            remote_operations.execute_remote_operation("get_payment_entry", "sales", {"name": "PE-1"})

    @patch("mcp_erpnext.remote_operations.multi_invoice_customer_receipt.prepare_multi_invoice_customer_receipt")
    def test_multi_invoice_receipt_uses_fixed_typed_accounts_handler(self, prepare):
        prepare.return_value = {"status": "error", "code": "NO_OUTSTANDING", "message": "missing", "reference": "MCP-ERR-TEST"}
        result = remote_operations.execute_remote_operation(
            "prepare_multi_invoice_customer_receipt", "accounts",
            {"customer": "CUST-1", "amount": 30, "allocations": [
                {"sales_invoice": "SINV-1", "allocated_amount": 10},
                {"sales_invoice": "SINV-2", "allocated_amount": 20},
            ], "mode_of_payment": "Bank Transfer"},
        )
        self.assertEqual(result["code"], "NO_OUTSTANDING")
        prepare.assert_called_once()

    def test_multi_invoice_receipt_is_accounts_only(self):
        with self.assertRaises(remote_operations.RemoteOperationError):
            remote_operations.execute_remote_operation(
                "prepare_multi_invoice_customer_receipt", "sales",
                {"customer": "CUST-1", "amount": 20, "allocations": [
                    {"sales_invoice": "SINV-1", "allocated_amount": 10},
                    {"sales_invoice": "SINV-2", "allocated_amount": 10},
                ], "bank_account": "BANK-1"},
            )

    @patch("mcp_erpnext.remote_operations.sales_order_advance_payment.prepare_sales_order_advance_payment")
    def test_sales_order_advance_payment_uses_fixed_typed_accounts_handler(self, prepare):
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

    @patch("mcp_erpnext.remote_operations.sales_order_advance_payment.confirm_sales_order_advance_payment")
    def test_sales_order_advance_payment_confirm_uses_fixed_typed_handler(self, confirm):
        confirm.return_value = {"status": "error", "code": "CONFIRMATION_UNAVAILABLE"}
        result = remote_operations.execute_remote_operation(
            "confirm_sales_order_advance_payment",
            "accounts",
            {"approval_token": "opaque", "confirm": True},
        )
        self.assertEqual(result["code"], "CONFIRMATION_UNAVAILABLE")
        confirm.assert_called_once_with("opaque", True)

    @patch("mcp_erpnext.remote_operations.customer_payment_reconciliation.prepare_customer_payment_reconciliation")
    def test_customer_payment_reconciliation_uses_fixed_typed_accounts_handler(self, prepare):
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

    @patch("mcp_erpnext.remote_operations.customer_payment_reconciliation.confirm_customer_payment_reconciliation")
    def test_customer_payment_reconciliation_confirm_uses_fixed_typed_handler(self, confirm):
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
                {"payment_entry": "ACC-PAY-1", "sales_invoice": "ACC-SINV-1", "amount": 25},
            )


class RemoteErrorTests(unittest.TestCase):
    @patch("mcp_erpnext.remote_api.logged_public_error")
    def test_remote_safe_error_keeps_the_required_reference_contract(self, logged_error):
        logged_error.return_value = {
            "status": "error",
            "code": "ERP_PERMISSION_DENIED",
            "message": "The remote ERPNext request could not be completed.",
            "reference": "MCP-ERR-97C4A07F",
            "retryable": False,
        }

        result = remote_api._safe_error("ERP_PERMISSION_DENIED")

        self.assertEqual(ToolError.model_validate(result).reference, "MCP-ERR-97C4A07F")
        logged_error.assert_called_once_with(
            "remote_api",
            "ERP_PERMISSION_DENIED",
            message="The remote ERPNext request could not be completed.",
            retryable=False,
            level="warning",
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
                operation="search_customers", profile="sales", arguments={"query": "Acme"}
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

        with patch(
            "mcp_erpnext.rest_client.build_opener",
            return_value=SimpleNamespace(open=lambda *_args, **_kwargs: Response()),
        ), self.assertRaises(RestBackendError):
            ERPNextRestClient(_settings()).execute(
                operation="search_customers", profile="sales", arguments={"query": "Acme"}
            )
