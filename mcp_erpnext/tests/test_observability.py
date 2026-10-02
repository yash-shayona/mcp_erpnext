from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import frappe

from mcp_erpnext import observability


class ObservabilityTests(unittest.TestCase):
    @patch("mcp_erpnext.observability.secrets.token_hex", return_value="97c4a07f")
    def test_references_use_the_documented_unique_format(self, token_hex):
        self.assertEqual(observability.new_error_reference(), "MCP-ERR-97C4A07F")
        self.assertEqual(
            observability.public_error("ERP_REQUEST_FAILED")["reference"],
            "MCP-ERR-97C4A07F",
        )
        token_hex.assert_called()

    @patch(
        "mcp_erpnext.observability.new_error_reference", return_value="MCP-ERR-97C4A07F"
    )
    @patch("mcp_erpnext.observability.get_app_logger")
    def test_permission_failure_has_a_stable_code_and_matching_log_reference(
        self, get_app_logger, new_error_reference
    ):
        logger = Mock()
        get_app_logger.return_value = logger

        def raise_permission_error():
            raise frappe.PermissionError

        result = observability.execute_tool("search_customers", raise_permission_error)

        self.assertEqual(result["code"], "ERP_PERMISSION_DENIED")
        self.assertEqual(result["reference"], "MCP-ERR-97C4A07F")
        self.assertIn("code=%s", logger.warning.call_args.args[0])
        self.assertIn("MCP-ERR-97C4A07F", logger.warning.call_args.args)
        self.assertIn("ERP_PERMISSION_DENIED", logger.warning.call_args.args)
        new_error_reference.assert_called_once_with()

    @patch(
        "mcp_erpnext.observability.new_error_reference", return_value="MCP-ERR-97C4A07F"
    )
    @patch("mcp_erpnext.observability.get_app_logger")
    def test_exception_retryability_respects_tool_side_effect_class(
        self, get_app_logger, _new_error_reference
    ):
        get_app_logger.return_value = Mock()

        def fail():
            raise RuntimeError("uncertain execution details")

        for tool, expected_retryable in (
            ("query_sales_orders", True),
            ("confirm_document_delete", False),
            ("prepare_document_delete", False),
            ("unregistered_tool", False),
        ):
            with self.subTest(tool=tool):
                result = observability.execute_tool(tool, fail)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["retryable"], expected_retryable)
                self.assertNotIn("uncertain execution details", result["message"])

    @patch(
        "mcp_erpnext.observability.new_error_reference", return_value="MCP-ERR-97C4A07F"
    )
    @patch("mcp_erpnext.observability.get_app_logger", side_effect=PermissionError)
    @patch("mcp_erpnext.observability.sys.stderr.write")
    def test_log_file_permission_failure_does_not_mask_tool_error(
        self, stderr_write, get_app_logger, new_error_reference
    ):
        def raise_permission_error():
            raise frappe.PermissionError

        result = observability.execute_tool("search_customers", raise_permission_error)

        self.assertEqual(result["code"], "ERP_PERMISSION_DENIED")
        self.assertEqual(result["reference"], "MCP-ERR-97C4A07F")
        self.assertIn("MCP log write failed", stderr_write.call_args.args[0])
        self.assertIn("log_error=PermissionError", stderr_write.call_args.args[0])
        get_app_logger.assert_called_once_with()
        new_error_reference.assert_called_once_with()
