from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mcp_erpnext import observability
from mcp_erpnext.contracts.common import ToolError
from mcp_erpnext.instructions.base import BASE_INSTRUCTIONS
from mcp_erpnext.approvals import confirmation_failure
from mcp_erpnext.observability import (
    logged_defined_error,
    logged_public_error,
    public_error,
)
from mcp_erpnext.public_errors import (
    ErrorCategory,
    PUBLIC_ERROR_DEFINITIONS,
    defined_error,
    definition_for,
)
from mcp_erpnext.services.common import email, lifecycle, pdf, read
from mcp_erpnext.remote_api import _safe_error


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

    def test_catalog_covers_the_migrated_core_and_common_codes(self):
        codes = {
            "CREATE_DISABLED",
            "UPDATE_DISABLED",
            "CANCEL_DISABLED",
            "DELETE_DISABLED",
            "APPROVAL_REQUIRED",
            "DIRECT_EXECUTION_REQUIRED",
            "CONFIRMATION_EXPIRED",
            "CONFIRMATION_CONSUMED",
            "CONFIRMATION_UNAVAILABLE",
            "TRUSTED_APPROVAL_UNAVAILABLE",
            "PERMISSION_DENIED",
            "ERP_PERMISSION_DENIED",
            "DOCTYPE_NOT_ALLOWED",
            "INVALID_TARGET",
            "STALE_CONFIRMATION",
            "LIFECYCLE_VALIDATION_FAILED",
            "LINKED_DOCUMENT",
            "INVALID_DOCUMENT_STATE",
            "INVALID_PRINT_FORMAT",
            "PDF_RENDER_FAILED",
            "ACTION_MISMATCH",
            "AMBIGUOUS_CHILD_TARGET",
            "CHILD_ROW_NOT_FOUND",
            "CHILD_TARGET_NOT_ALLOWED",
            "CONFIRMATION_REQUIRED",
            "DELETE_BLOCKED",
            "DOCUMENT_NOT_FOUND",
            "DUPLICATE_ITEM_ROW",
            "FIELD_NOT_WRITABLE",
            "INVALID_CHILD_TARGET",
            "INVALID_FIELD",
            "INVALID_FIELD_VALUE",
            "INVALID_ITEM",
            "INVALID_ITEM_DETAILS",
            "INVALID_LINK",
            "NOT_SUBMITTABLE",
            "PAYMENT_SCHEDULE_UNAVAILABLE",
            "PROFILE_MISMATCH",
            "EMAIL_ACCOUNT_NOT_CONFIGURED",
            "EMAIL_PREPARE_FAILED",
            "EMAIL_QUEUE_FAILED",
            "INVALID_EMAIL",
            "INVALID_RECIPIENT",
            "INVALID_RECIPIENT_SCOPE",
            "PREPARED_STATE_CHANGED",
            "RECIPIENT_NOT_FOUND",
            "SELF_RECIPIENT_UNAVAILABLE",
            "MCP_REMOTE_REQUEST_INVALID",
            "MCP_REMOTE_RESPONSE_INVALID",
            "EMAIL_DISABLED",
            "ORDER_CREATE_UNAVAILABLE",
            "ORDER_PREVIEW_UNAVAILABLE",
            "ERP_REQUEST_FAILED",
            "MCP_AUTHENTICATION_MISSING",
            "MCP_AUTHENTICATION_INVALID",
            "MCP_USER_IDENTITY_MISSING",
            "MCP_USER_NOT_FOUND",
            "MCP_USER_DISABLED",
            "MCP_IDENTITY_CONFIGURATION_ERROR",
        }
        self.assertLessEqual(codes, PUBLIC_ERROR_DEFINITIONS.keys())

    def test_catalog_covers_masters_and_shayona_codes(self):
        codes = {
            "CONTACT_CHILD_STALE_STATE",
            "CONTACT_CREATE_FAILED",
            "CONTACT_DUPLICATE_SUSPECTED",
            "CONTACT_EMAIL_AMBIGUOUS",
            "CONTACT_EMAIL_NOT_FOUND",
            "CONTACT_INVALID_DATA",
            "CONTACT_INVALID_EMAIL",
            "CONTACT_INVALID_IDENTITY",
            "CONTACT_INVALID_PHONE",
            "CONTACT_INVALID_REQUEST",
            "CONTACT_LINK_FAILED",
            "CONTACT_LINK_STALE_STATE",
            "CONTACT_NOT_FOUND",
            "CONTACT_NOT_LINKED_TO_CUSTOMER",
            "CONTACT_PHONE_AMBIGUOUS",
            "CONTACT_PHONE_NOT_FOUND",
            "CONTACT_PRIMARY_STATE_INCONSISTENT",
            "CONTACT_PRIMARY_UNSUPPORTED",
            "CONTACT_SCOPE_REQUIRED",
            "CONTACT_SHARED_WITH_OTHER_PARTIES",
            "CONTACT_STALE_STATE",
            "CONTACT_UPDATE_FAILED",
            "CREDENTIAL_INACTIVE",
            "CREDENTIAL_NOT_FOUND",
            "CREDENTIAL_READ_FAILED",
            "CREDENTIAL_SECRET_UNAVAILABLE",
            "CUSTOMER_EMAIL_UNAVAILABLE",
            "CUSTOMER_PRIMARY_CONTACT_STALE",
            "CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED",
            "CUSTOMER_STRUCTURED_QUERY_REQUIRED",
            "EMAIL_RENDER_FAILED",
            "EMAIL_TEMPLATE_INVALID",
            "EMAIL_TEMPLATE_NOT_CONFIGURED",
            "EMAIL_TEMPLATE_NOT_FOUND",
            "EMAIL_TEMPLATE_UNSAFE",
            "GSTIN_UNSUPPORTED",
            "INDIA_COMPLIANCE_ADDRESS_BRIDGE_UNAVAILABLE",
            "INDIA_COMPLIANCE_GST_UNAVAILABLE",
            "INVALID_CUSTOMER_DETAILS",
            "ITEM_RUNTIME_REQUIREMENT_UNAVAILABLE",
            "OPERATOR_EMAIL_UNAVAILABLE",
            "PRIMARY_CONTACT_PROMOTION_FAILED",
            "PRIMARY_CONTACT_PROMOTION_UNSAFE",
            "TEA_ENTRY_VALIDATION_FAILED",
            "TEA_ENTRY_WRITE_FAILED",
        }
        self.assertLessEqual(codes, PUBLIC_ERROR_DEFINITIONS.keys())
        for code in {
            "CONTACT_CREATE_FAILED",
            "CONTACT_LINK_FAILED",
            "CONTACT_UPDATE_FAILED",
            "PRIMARY_CONTACT_PROMOTION_FAILED",
        }:
            with self.subTest(non_retryable_write=code):
                result = defined_error(code)
                self.assertFalse(result["retryable"])
                self.assertIn("before trying again", result["message"])
        for code in codes:
            with self.subTest(code=code):
                result = defined_error(code)
                self.assertEqual(
                    result["message"], PUBLIC_ERROR_DEFINITIONS[code].message
                )
                self.assertEqual(
                    set(result), {"status", "code", "message", "reference", "retryable"}
                )

    def test_catalog_covers_sales_buying_and_accounts_codes(self):
        codes = {
            "ACCOUNT_MISMATCH",
            "ALLOCATION_EXCEEDS_OUTSTANDING",
            "ALLOCATION_TOTAL_MISMATCH",
            "AMBIGUOUS_PAYMENT_SOURCE",
            "AMOUNT_EXCEEDS_AVAILABLE",
            "AMOUNT_EXCEEDS_OUTSTANDING",
            "BANK_AMOUNT_REQUIRED",
            "COMPANY_MISMATCH",
            "CONFIRMATION_REQUIRED",
            "CONFIRMATION_UNAVAILABLE",
            "CONTRADICTORY_DESTINATION",
            "CONVERSION_FAILED",
            "CONVERSION_UNAVAILABLE",
            "CUSTOMER_MISMATCH",
            "CUSTOMER_NOT_FOUND",
            "CUSTOM_REMARKS_UNAVAILABLE",
            "COMPANY_NOT_FOUND",
            "DESTINATION_REQUIRED",
            "DUPLICATE_SALES_INVOICE",
            "EARLY_PAYMENT_DISCOUNT_UNSUPPORTED",
            "INVALID_ALLOCATION_AMOUNT",
            "INVALID_BANK_ACCOUNT",
            "INVALID_BANK_AMOUNT",
            "INVALID_BUSINESS_DEFAULTS",
            "INVALID_COMMERCIAL_TEMPLATE",
            "INVALID_CUSTOMER",
            "INVALID_DESTINATION_ACCOUNT",
            "INVALID_FIELDS",
            "INVALID_ITEM",
            "INVALID_MODE_OF_PAYMENT",
            "INVALID_ORDER_DETAILS",
            "INVALID_PAYMENT_AMOUNT",
            "INVALID_PAYMENT_DESTINATION",
            "INVALID_PAYMENT_ENTRY_STATE",
            "INVALID_PAYMENT_TERMS_TEMPLATE",
            "INVALID_PURCHASE_ORDER_DETAILS",
            "INVALID_QUOTATION_DETAILS",
            "INVALID_REFERENCE_COUNT",
            "INVALID_SALES_INVOICE",
            "INVALID_SALES_INVOICE_DETAILS",
            "INVALID_SALES_ORDER",
            "INVALID_SOURCE_ROW",
            "INVALID_SUPPLIER",
            "INVALID_TERMS",
            "INVALID_WAREHOUSE",
            "INVOICE_NOT_OUTSTANDING",
            "MIXED_CURRENCY_AGGREGATE",
            "MIXED_INVOICE_CURRENCY_UNSUPPORTED",
            "MODE_OF_PAYMENT_ACCOUNT_MISSING",
            "NATIVE_PAYMENT_STATE_INVALID",
            "NATIVE_PAYMENT_VALIDATION_FAILED",
            "NATIVE_RECONCILIATION_UNAVAILABLE",
            "NATIVE_VALIDATION_FAILED",
            "NONZERO_DIFFERENCE",
            "NO_MAPPABLE_ITEMS",
            "NO_OUTSTANDING",
            "PARTY_CURRENCY_MISMATCH",
            "PARTY_MISMATCH",
            "PAYMENT_ENTRY_CREATION_FAILED",
            "PAYMENT_ENTRY_NOT_FOUND",
            "PAYMENT_SCHEDULE_UNAVAILABLE",
            "PAYMENT_TERMS_UNSUPPORTED",
            "PERMISSION_DENIED",
            "QUANTITY_EXCEEDS_REMAINING",
            "RECEIVABLE_ACCOUNT_MISMATCH",
            "RECONCILIATION_ALREADY_RUNNING",
            "RECONCILIATION_FAILED",
            "REGIONAL_VALIDATION_FAILED",
            "REJECTED_WAREHOUSE_REQUIRED",
            "RETURN_REFERENCE_UNSUPPORTED",
            "SALES_INVOICE_CREATION_FAILED",
            "SALES_INVOICE_NOT_FOUND",
            "SALES_INVOICE_NOT_OUTSTANDING",
            "SALES_INVOICE_NOT_SUBMITTED",
            "SALES_ORDER_NOT_ELIGIBLE",
            "SALES_ORDER_NOT_FOUND",
            "SALES_ORDER_NOT_SUBMITTED",
            "SOURCE_NOT_ELIGIBLE",
            "SOURCE_NOT_FOUND",
            "SOURCE_NOT_READY",
            "STALE_CONFIRMATION",
            "TERMS_UNAVAILABLE",
            "TRANSACTION_REFERENCE_REQUIRED",
            "UNALLOCATED_RECEIPT_UNSUPPORTED",
            "UNEXPECTED_ACCOUNTING_STATE",
            "UNEXPECTED_DEDUCTION_STATE",
            "UNEXPECTED_PAYMENT_STATE",
            "UNEXPECTED_REFERENCE_STATE",
            "UNEXPECTED_TAX_STATE",
            "UNSUPPORTED_NATIVE_PAYMENT_STATE",
            "UNSUPPORTED_QUOTATION_PARTY",
            "UNSUPPORTED_SOURCE",
            "UNSUPPORTED_SOURCE_ROW",
            "WAREHOUSE_NOT_FOUND",
            "WAREHOUSE_REQUIRED",
        }
        self.assertLessEqual(codes, PUBLIC_ERROR_DEFINITIONS.keys())
        self.assertNotEqual(
            definition_for("SOURCE_NOT_FOUND").message,
            definition_for("SOURCE_NOT_READY").message,
        )
        self.assertNotEqual(
            definition_for("NO_OUTSTANDING").message,
            definition_for("AMOUNT_EXCEEDS_OUTSTANDING").message,
        )
        for code in codes:
            with self.subTest(code=code):
                self.assertIsNot(
                    definition_for(code),
                    PUBLIC_ERROR_DEFINITIONS["ERP_REQUEST_FAILED"],
                )

    def test_er03_messages_use_business_wording(self):
        expected_messages = {
            "AMOUNT_EXCEEDS_AVAILABLE": "The requested allocation exceeds the amount currently available from the source or invoice.",
            "BANK_AMOUNT_REQUIRED": "A bank amount is required when the payment and destination currencies differ.",
            "INVALID_BANK_AMOUNT": "The bank amount must be a positive, valid number.",
            "PAYMENT_TERMS_UNSUPPORTED": "This reconciliation does not support allocation by payment terms.",
            "RECONCILIATION_ALREADY_RUNNING": "A Payment Reconciliation process is already running for this Customer and Company.",
            "SALES_INVOICE_NOT_SUBMITTED": "The Sales Invoice must be submitted before a payment can be created.",
            "SALES_ORDER_NOT_SUBMITTED": "The Sales Order must be submitted before an advance payment can be created.",
            "UNSUPPORTED_SOURCE": "This Purchase Order cannot be converted through this operation.",
            "NATIVE_PAYMENT_STATE_INVALID": "The Payment Entry could not be prepared as a draft.",
            "NATIVE_PAYMENT_VALIDATION_FAILED": "The Payment Entry did not pass validation.",
            "NATIVE_RECONCILIATION_UNAVAILABLE": "Reconciliation is unavailable with the current setup.",
            "NATIVE_VALIDATION_FAILED": "The document did not pass validation.",
            "UNSUPPORTED_NATIVE_PAYMENT_STATE": "This payment cannot be processed because it includes tax, withholding, or deduction amounts.",
        }
        implementation_terms = ("native", "v1", "bank_amount", "deferred workflow")

        for code, message in expected_messages.items():
            with self.subTest(code=code):
                definition = definition_for(code)
                self.assertEqual(definition.message, message)
                self.assertFalse(definition.retryable)
                lowered_message = definition.message.lower()
                for term in implementation_terms:
                    self.assertNotIn(term, lowered_message)

    def test_logged_defined_error_correlates_without_a_public_message_override(self):
        with (
            patch("mcp_erpnext.observability._log_tool_failure") as log_failure,
            patch(
                "mcp_erpnext.observability.new_error_reference",
                return_value="MCP-ERR-ABCDEF12",
            ),
        ):
            result = logged_defined_error("test_tool", "LIFECYCLE_VALIDATION_FAILED")

        self.assertEqual(
            result["message"], definition_for("LIFECYCLE_VALIDATION_FAILED").message
        )
        self.assertEqual(result["reference"], "MCP-ERR-ABCDEF12")
        self.assertEqual(log_failure.call_args.kwargs["reference"], result["reference"])
        self.assertEqual(log_failure.call_args.kwargs["code"], result["code"])
        with self.assertRaises(TypeError):
            logged_defined_error(
                "test_tool", "ERP_REQUEST_FAILED", message="raw diagnostic"
            )

    def test_common_read_pdf_and_email_errors_use_catalog_messages(self):
        cases = (
            (
                read._error("DOCTYPE_NOT_ALLOWED", "internal details"),
                "DOCTYPE_NOT_ALLOWED",
            ),
            (
                pdf._error("INVALID_PRINT_FORMAT", "format path /private"),
                "INVALID_PRINT_FORMAT",
            ),
            (email._error("INVALID_EMAIL", "recipient token=private"), "INVALID_EMAIL"),
        )
        for result, code in cases:
            with self.subTest(code=code):
                self.assertEqual(
                    set(result), {"status", "code", "message", "reference", "retryable"}
                )
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["code"], code)
                self.assertEqual(result["message"], definition_for(code).message)
                self.assertNotIn("internal details", result["message"])

    def test_profile_mismatch_callers_use_catalog_message(self):
        expected = defined_error("PROFILE_MISMATCH")
        _document, lifecycle_failure = lifecycle._revalidate(
            SimpleNamespace(payload={"profile": "purchase"}), "update", "sales"
        )
        email_failure = email._apply_document_email(
            {"profile": "purchase"}, "sales", email.WriteMode.APPROVAL_REQUIRED
        )

        for result in (lifecycle_failure, email_failure):
            with self.subTest(result=result):
                self.assertEqual(result["code"], "PROFILE_MISMATCH")
                self.assertEqual(result["message"], expected["message"])
                self.assertNotIn("MCP", result["message"])
                self.assertNotIn("profile", result["message"].lower())

    def test_policy_and_permission_categories_remain_distinct(self):
        capability = defined_error("DELETE_DISABLED")
        permission = defined_error("PERMISSION_DENIED")
        self.assertEqual(
            definition_for(capability["code"]).category,
            ErrorCategory.CAPABILITY_UNAVAILABLE,
        )
        self.assertEqual(
            definition_for(permission["code"]).category, ErrorCategory.PERMISSION_DENIED
        )
        self.assertNotEqual(capability["message"], permission["message"])

    def test_profile_mismatch_keeps_code_and_category_with_business_wording(self):
        result = defined_error("PROFILE_MISMATCH")

        self.assertEqual(result["code"], "PROFILE_MISMATCH")
        self.assertEqual(
            definition_for(result["code"]).category, ErrorCategory.INVALID_REQUEST
        )
        self.assertFalse(result["retryable"])
        self.assertEqual(
            result["message"],
            "The prepared action does not match this operation. Prepare and review it again.",
        )
        self.assertNotIn("MCP", result["message"])
        self.assertNotIn("profile", result["message"].lower())
        self.assertEqual(
            set(result), {"status", "code", "message", "reference", "retryable"}
        )

    def test_approval_states_keep_codes_and_retry_semantics_with_catalog_wording(self):
        expected = {
            "expired": ("CONFIRMATION_EXPIRED", True),
            "consumed": ("CONFIRMATION_CONSUMED", False),
            "unavailable": ("CONFIRMATION_UNAVAILABLE", False),
            "not_trusted": ("TRUSTED_APPROVAL_UNAVAILABLE", False),
        }
        for state, (code, retryable) in expected.items():
            with self.subTest(state=state):
                actual_code, message, actual_retryable = confirmation_failure(
                    state, "document"
                )
                self.assertEqual((actual_code, actual_retryable), (code, retryable))
                self.assertEqual(message, definition_for(code).message)

    def test_rest_error_message_matches_direct_catalog_semantics(self):
        with (
            patch("mcp_erpnext.observability._log_tool_failure"),
            patch(
                "mcp_erpnext.observability.new_error_reference",
                return_value="MCP-ERR-ABCDEF12",
            ),
        ):
            remote = _safe_error("ERP_PERMISSION_DENIED")
        direct = defined_error("ERP_PERMISSION_DENIED", reference="MCP-ERR-ABCDEF12")
        self.assertEqual(remote["code"], direct["code"])
        self.assertEqual(remote["message"], direct["message"])
        self.assertEqual(remote["retryable"], direct["retryable"])

    def test_runtime_error_producer_literals_are_registered(self):
        runtime_root = Path(__file__).resolve().parents[1]
        code_pattern = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
        code_argument = {
            "logged_defined_error": 1,
            "logged_public_error": 1,
        }
        runtime_codes = set()

        for path in runtime_root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (
                        node.func.attr if isinstance(node.func, ast.Attribute) else None
                    )
                )
                if name not in {
                    "defined_error",
                    "logged_defined_error",
                    "public_error",
                    "logged_public_error",
                    "_error",
                    "_confirmation_error",
                }:
                    continue
                index = code_argument.get(name, 0)
                if len(node.args) <= index:
                    continue
                runtime_codes.update(
                    child.value
                    for child in ast.walk(node.args[index])
                    if isinstance(child, ast.Constant)
                    and isinstance(child.value, str)
                    and code_pattern.fullmatch(child.value)
                )

        missing = runtime_codes - PUBLIC_ERROR_DEFINITIONS.keys()
        self.assertEqual(missing, set())
        fallback = PUBLIC_ERROR_DEFINITIONS["ERP_REQUEST_FAILED"]
        for code in runtime_codes:
            with self.subTest(code=code):
                self.assertIsNot(definition_for(code), fallback)

    def test_catalog_messages_avoid_internal_implementation_wording(self):
        forbidden_phrases = (
            "server policy",
            "mcp profile",
            "backend",
            "redis",
            "traceback",
            "sql",
            "approval token",
            "direct execution",
            "native",
        )
        implementation_token = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
        for code, definition in PUBLIC_ERROR_DEFINITIONS.items():
            message = definition.message
            lowered = message.lower()
            with self.subTest(code=code):
                for phrase in forbidden_phrases:
                    self.assertNotIn(phrase, lowered)
                self.assertIsNone(implementation_token.search(message))

    def test_direct_and_rest_errors_match_across_semantic_categories(self):
        cases = {
            ErrorCategory.CAPABILITY_UNAVAILABLE: "DELETE_DISABLED",
            ErrorCategory.PERMISSION_DENIED: "ERP_PERMISSION_DENIED",
            ErrorCategory.APPROVAL_REQUIRED: "APPROVAL_REQUIRED",
            ErrorCategory.INTERACTION_REQUIRED: "DIRECT_EXECUTION_REQUIRED",
            ErrorCategory.INVALID_REQUEST: "INVALID_TARGET",
            ErrorCategory.NOT_FOUND: "DOCUMENT_NOT_FOUND",
            ErrorCategory.AMBIGUOUS_SELECTION: "CONTACT_EMAIL_AMBIGUOUS",
            ErrorCategory.BUSINESS_RULE_BLOCKED: "SOURCE_NOT_READY",
            ErrorCategory.STALE_STATE: "STALE_CONFIRMATION",
            ErrorCategory.CONFIGURATION_UNAVAILABLE: "EMAIL_ACCOUNT_NOT_CONFIGURED",
            ErrorCategory.TEMPORARY_FAILURE: "EMAIL_QUEUE_FAILED",
            ErrorCategory.UNEXPECTED_FAILURE: "ERP_REQUEST_FAILED",
        }
        with (
            patch("mcp_erpnext.observability._log_tool_failure"),
            patch(
                "mcp_erpnext.observability.new_error_reference",
                return_value="MCP-ERR-ABCDEF12",
            ),
        ):
            for category, code in cases.items():
                with self.subTest(category=category):
                    direct = observability.execute_tool(
                        "query_sales_orders",
                        lambda selected=code: defined_error(selected),
                    )
                    remote = _safe_error(code)
                    self.assertEqual(definition_for(code).category, category)
                    self.assertEqual(
                        (direct["code"], direct["message"], direct["retryable"]),
                        (remote["code"], remote["message"], remote["retryable"]),
                    )

    def test_explicit_retry_override_is_deterministic(self):
        self.assertFalse(
            defined_error("ERP_REQUEST_FAILED", retryable=False)["retryable"]
        )
        self.assertTrue(defined_error("DELETE_DISABLED")["retryable"] is False)
        for code in ("PDF_RENDER_FAILED", "EMAIL_PREPARE_FAILED", "EMAIL_QUEUE_FAILED"):
            with self.subTest(code=code):
                self.assertFalse(defined_error(code)["retryable"])

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
            "denied access",
            "required approval",
            "environment-variable names",
            "server-policy details",
            "technical troubleshooting",
            "do not invent",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, BASE_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
