"""Canonical definitions for centrally presented MCP public errors.

Service-local errors remain on the compatibility path until their migration
phase. New central callers should use :func:`defined_error` so diagnostics can
never be supplied as public message text.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCategory(str, Enum):
    """Semantic reason for a public failure, independent of its wording."""

    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    PERMISSION_DENIED = "permission_denied"
    APPROVAL_REQUIRED = "approval_required"
    INTERACTION_REQUIRED = "interaction_required"
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    AMBIGUOUS_SELECTION = "ambiguous_selection"
    BUSINESS_RULE_BLOCKED = "business_rule_blocked"
    STALE_STATE = "stale_state"
    CONFIGURATION_UNAVAILABLE = "configuration_unavailable"
    TEMPORARY_FAILURE = "temporary_failure"
    UNEXPECTED_FAILURE = "unexpected_failure"


@dataclass(frozen=True)
class PublicErrorDefinition:
    """Safe public presentation defaults for one stable machine code."""

    category: ErrorCategory
    message: str
    retryable: bool = False


PUBLIC_ERROR_DEFINITIONS: dict[str, PublicErrorDefinition] = {
    "MCP_AUTHENTICATION_MISSING": PublicErrorDefinition(
        ErrorCategory.PERMISSION_DENIED, "MCP authentication is required."
    ),
    "MCP_AUTHENTICATION_INVALID": PublicErrorDefinition(
        ErrorCategory.PERMISSION_DENIED, "MCP authentication failed."
    ),
    "MCP_USER_IDENTITY_MISSING": PublicErrorDefinition(
        ErrorCategory.PERMISSION_DENIED, "MCP user identity is required."
    ),
    "MCP_USER_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND, "The requested MCP user is not configured."
    ),
    "MCP_USER_DISABLED": PublicErrorDefinition(
        ErrorCategory.PERMISSION_DENIED, "The requested MCP user is disabled."
    ),
    "MCP_IDENTITY_CONFIGURATION_ERROR": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The MCP identity configuration is incomplete.",
    ),
    "ERP_PERMISSION_DENIED": PublicErrorDefinition(
        ErrorCategory.PERMISSION_DENIED,
        "The configured ERPNext user does not have permission for that request. "
        "Please contact your administrator.",
    ),
    "ORDER_CREATE_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "I couldn't complete the Sales Order request right now. "
        "Please contact your administrator for assistance.",
        retryable=True,
    ),
    "ORDER_PREVIEW_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "I couldn't prepare the Sales Order preview right now. Please try again later.",
        retryable=True,
    ),
    "ERP_REQUEST_FAILED": PublicErrorDefinition(
        ErrorCategory.UNEXPECTED_FAILURE,
        "I couldn't complete that ERPNext request right now. Please try again later.",
        retryable=True,
    ),
    "MCP_REMOTE_REQUEST_INVALID": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "The remote ERPNext request is invalid."
    ),
    "MCP_REMOTE_RESPONSE_INVALID": PublicErrorDefinition(
        ErrorCategory.UNEXPECTED_FAILURE, "The remote ERPNext response is invalid."
    ),
    "CREDENTIAL_SCHEMA_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "Customer Service Credential capability is unavailable on this site.",
    ),
    "TEA_ENTRY_SCHEMA_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "Tea Entry capability is unavailable on this site.",
    ),
    "CREATE_DISABLED": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "Creating this document is unavailable in the current setup.",
    ),
    "UPDATE_DISABLED": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "Updating this document is unavailable in the current setup.",
    ),
    "CANCEL_DISABLED": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "Cancelling this document is unavailable in the current setup.",
    ),
    "DELETE_DISABLED": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "Deleting this document is unavailable in the current setup.",
    ),
    "APPROVAL_REQUIRED": PublicErrorDefinition(
        ErrorCategory.APPROVAL_REQUIRED,
        "This operation requires review and approval before it can continue.",
    ),
    "DIRECT_EXECUTION_REQUIRED": PublicErrorDefinition(
        ErrorCategory.INTERACTION_REQUIRED,
        "This operation must use the configured execution flow.",
    ),
    "STALE_CONFIRMATION": PublicErrorDefinition(
        ErrorCategory.STALE_STATE,
        "The prepared action is no longer current. Prepare and review it again.",
    ),
    "CONFIRMATION_EXPIRED": PublicErrorDefinition(
        ErrorCategory.STALE_STATE,
        "This confirmation has expired. Prepare it again.",
        True,
    ),
    "CONFIRMATION_CONSUMED": PublicErrorDefinition(
        ErrorCategory.STALE_STATE,
        "This confirmation has already been used or declined. Prepare it again.",
    ),
    "CONFIRMATION_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.APPROVAL_REQUIRED,
        "This confirmation is unavailable. Prepare and review the action again.",
    ),
    "TRUSTED_APPROVAL_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.APPROVAL_REQUIRED,
        "A verified human approval is required before this action can continue.",
    ),
    "PERMISSION_DENIED": PublicErrorDefinition(
        ErrorCategory.PERMISSION_DENIED,
        "You do not have permission to perform this action.",
    ),
    "DOCTYPE_NOT_ALLOWED": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "This document type is unavailable for the current operation.",
    ),
    "INVALID_TARGET": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "Provide a valid exact document target."
    ),
    "LIFECYCLE_VALIDATION_FAILED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The document could not be prepared or changed because it failed validation.",
    ),
    "LINKED_DOCUMENT": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This document cannot be removed while other documents depend on it.",
    ),
    "INVALID_DOCUMENT_STATE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The document is not in a state that allows this action.",
    ),
    "INVALID_PRINT_FORMAT": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "The selected Print Format is not available for this document.",
    ),
    "PDF_RENDER_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The document PDF could not be prepared. Please try again later.",
    ),
    "DOCUMENT_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND, "The requested document was not found."
    ),
    "EMAIL_QUEUE_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The document email could not be queued. Please try again later.",
    ),
    "PREPARED_STATE_CHANGED": PublicErrorDefinition(
        ErrorCategory.STALE_STATE,
        "The document or email details changed. Prepare and review the action again.",
    ),
    "EMAIL_DISABLED": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "Sending document email is unavailable in the current setup.",
    ),
    "ACTION_MISMATCH": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "The prepared action does not match this request.",
    ),
    "AMBIGUOUS_CHILD_TARGET": PublicErrorDefinition(
        ErrorCategory.AMBIGUOUS_SELECTION,
        "More than one matching item row was found. Select a specific row.",
    ),
    "CHILD_TARGET_NOT_ALLOWED": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "This item row cannot be changed through this operation.",
    ),
    "CONFIRMATION_REQUIRED": PublicErrorDefinition(
        ErrorCategory.APPROVAL_REQUIRED,
        "Review and confirm the prepared action before it can continue.",
    ),
    "DELETE_BLOCKED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This document cannot be deleted while dependent records exist.",
    ),
    "DUPLICATE_ITEM_ROW": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "The item row duplicates an existing row."
    ),
    "FIELD_NOT_WRITABLE": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "One or more requested fields cannot be changed."
    ),
    "INVALID_CHILD_TARGET": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "Provide a valid item row target."
    ),
    "INVALID_FIELD": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "One or more requested fields are invalid."
    ),
    "INVALID_FIELD_VALUE": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "One or more field values are invalid."
    ),
    "INVALID_ITEM": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "A valid permitted Item is required."
    ),
    "INVALID_ITEM_DETAILS": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "The item details are invalid."
    ),
    "INVALID_LINK": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "One or more linked values are invalid."
    ),
    "NOT_SUBMITTABLE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED, "This document type cannot be submitted."
    ),
    "PAYMENT_SCHEDULE_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The payment schedule could not be prepared with the current setup.",
    ),
    "PROFILE_MISMATCH": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "The prepared action belongs to a different MCP profile.",
    ),
    "EMAIL_ACCOUNT_NOT_CONFIGURED": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "Document email is unavailable with the current email setup.",
    ),
    "EMAIL_PREPARE_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The document email could not be prepared. Please try again later.",
    ),
    "INVALID_EMAIL": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "The email subject or message is invalid."
    ),
    "INVALID_RECIPIENT": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Select a valid recipient associated with the document.",
    ),
    "INVALID_RECIPIENT_SCOPE": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "Choose a supported recipient scope."
    ),
    "RECIPIENT_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND,
        "No eligible email recipient is available for this document.",
    ),
    "SELF_RECIPIENT_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND,
        "The authenticated user does not have an eligible email address.",
    ),
}

FALLBACK_CODE = "ERP_REQUEST_FAILED"


def definition_for(code: str) -> PublicErrorDefinition:
    """Return a registered definition or the bounded generic fallback."""

    return PUBLIC_ERROR_DEFINITIONS.get(code, PUBLIC_ERROR_DEFINITIONS[FALLBACK_CODE])


def defined_error(
    code: str,
    *,
    reference: str | None = None,
    retryable: bool | None = None,
) -> dict[str, object]:
    """Build an error from registered safe defaults without accepting message text."""

    definition = definition_for(code)
    from .observability import new_error_reference

    return {
        "status": "error",
        "code": code,
        "message": definition.message,
        "reference": reference or new_error_reference(),
        "retryable": definition.retryable if retryable is None else retryable,
    }
