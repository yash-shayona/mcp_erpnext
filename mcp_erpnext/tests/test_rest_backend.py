from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mcp_erpnext import remote_operations
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
