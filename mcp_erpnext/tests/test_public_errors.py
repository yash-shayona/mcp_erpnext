from __future__ import annotations

import unittest
from unittest.mock import patch

from mcp_erpnext.contracts.common import ToolError
from mcp_erpnext.instructions.base import BASE_INSTRUCTIONS
from mcp_erpnext.observability import logged_public_error, public_error
from mcp_erpnext.public_errors import (
    ErrorCategory,
    PUBLIC_ERROR_DEFINITIONS,
    defined_error,
    definition_for,
)


class PublicErrorFoundationTests(unittest.TestCase):
    @patch(
        "mcp_erpnext.observability.new_error_reference", return_value="MCP-ERR-ABCDEF12"
    )
    def test_defined_error_uses_registered_safe_message_and_retry_default(
        self, reference
    ):
        result = defined_error("ERP_REQUEST_FAILED")

        self.assertEqual(
            result["message"], PUBLIC_ERROR_DEFINITIONS["ERP_REQUEST_FAILED"].message
        )
        self.assertTrue(result["retryable"])
        self.assertEqual(result["reference"], "MCP-ERR-ABCDEF12")
        reference.assert_called_once_with()

    def test_unknown_code_keeps_semantics_but_uses_bounded_fallback(self):
        result = defined_error("NEW_UNREGISTERED_CODE")

        self.assertEqual(result["code"], "NEW_UNREGISTERED_CODE")
        self.assertEqual(
            result["message"], PUBLIC_ERROR_DEFINITIONS["ERP_REQUEST_FAILED"].message
        )
        self.assertTrue(result["retryable"])
        self.assertEqual(
            definition_for("NEW_UNREGISTERED_CODE").category,
            ErrorCategory.UNEXPECTED_FAILURE,
        )
        self.assertNotIn("diagnostic", result["message"])

    def test_defined_error_does_not_accept_message_or_raw_diagnostic(self):
        with self.assertRaises(TypeError):
            defined_error("ERP_REQUEST_FAILED", message="database password=secret")

    def test_explicit_retry_override_is_deterministic(self):
        self.assertFalse(
            defined_error("ERP_REQUEST_FAILED", retryable=False)["retryable"]
        )
        self.assertTrue(defined_error("DELETE_DISABLED")["retryable"] is False)

    def test_tool_error_envelope_fields_remain_compatible(self):
        self.assertEqual(
            set(ToolError.model_fields),
            {"status", "code", "message", "reference", "retryable"},
        )

    def test_legacy_helpers_remain_compatible_and_unknown_errors_are_bounded(self):
        result = public_error("UNKNOWN_CODE", message="legacy safe message")
        self.assertEqual(result["message"], "legacy safe message")
        unknown = public_error("UNKNOWN_CODE")
        self.assertEqual(
            unknown["message"], definition_for("ERP_REQUEST_FAILED").message
        )

    @patch("mcp_erpnext.observability._log_tool_failure")
    @patch(
        "mcp_erpnext.observability.new_error_reference", return_value="MCP-ERR-ABCDEF12"
    )
    def test_logged_public_error_keeps_matching_reference(self, reference, log_failure):
        result = logged_public_error("sample_tool", "ERP_REQUEST_FAILED")

        self.assertEqual(result["reference"], "MCP-ERR-ABCDEF12")
        self.assertTrue(result["retryable"] is False)
        self.assertEqual(log_failure.call_args.kwargs["reference"], result["reference"])
        reference.assert_called_once_with()

    def test_base_instructions_cover_client_neutral_error_presentation(self):
        for expected in (
            "user-facing business",
            "machine error codes",
            "correlation",
            "capability",
            "required approval",
            "do not invent",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, BASE_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
