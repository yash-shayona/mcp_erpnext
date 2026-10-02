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
