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
        "Customer Service Credential information is unavailable in the current setup.",
    ),
    "TEA_ENTRY_SCHEMA_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        "Tea Entry information is unavailable in the current setup.",
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
    "ACCOUNT_MISMATCH": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The payment and invoice accounts are not compatible.",
    ),
    "ALLOCATION_EXCEEDS_OUTSTANDING": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Each allocation must be positive and no greater than the current outstanding amount.",
    ),
    "ALLOCATION_TOTAL_MISMATCH": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The allocation total does not match the receipt amount.",
    ),
    "AMBIGUOUS_PAYMENT_SOURCE": PublicErrorDefinition(
        ErrorCategory.AMBIGUOUS_SELECTION,
        "The Payment Entry has more than one eligible source for reconciliation.",
    ),
    "AMOUNT_EXCEEDS_AVAILABLE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The requested allocation exceeds the amount currently available from the source or invoice.",
    ),
    "AMOUNT_EXCEEDS_OUTSTANDING": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The payment amount exceeds the available outstanding amount.",
    ),
    "BANK_AMOUNT_REQUIRED": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "A bank amount is required when the payment and destination currencies differ.",
    ),
    "COMPANY_MISMATCH": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Payment Entry and Sales Invoice must belong to the same Company.",
    ),
    "CONTRADICTORY_DESTINATION": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Provide either Mode of Payment or Bank Account, not both.",
    ),
    "CONVERSION_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "ERPNext could not complete this document conversion.",
    ),
    "CONVERSION_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The converted document is unavailable for this operation.",
    ),
    "CUSTOMER_MISMATCH": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Every Sales Invoice must belong to the explicit Customer.",
    ),
    "CUSTOMER_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND, "The requested Customer was not found."
    ),
    "CUSTOM_REMARKS_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "Custom remarks are unavailable for this document on this site.",
    ),
    "DESTINATION_REQUIRED": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Provide one Mode of Payment or Bank Account.",
    ),
    "DUPLICATE_SALES_INVOICE": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Each Sales Invoice may appear only once.",
    ),
    "EARLY_PAYMENT_DISCOUNT_UNSUPPORTED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "A selected invoice is eligible for an early-payment discount.",
    ),
    "INVALID_ALLOCATION_AMOUNT": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Allocation amount must be a positive finite number.",
    ),
    "INVALID_BANK_ACCOUNT": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "Select a Bank Account with a valid ledger account for this Company.",
    ),
    "INVALID_BANK_AMOUNT": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "The bank amount must be a positive, valid number.",
    ),
    "INVALID_BUSINESS_DEFAULTS": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The site document defaults are invalid. Ask an administrator to review the configuration.",
    ),
    "INVALID_COMMERCIAL_TEMPLATE": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Use an exact template name (at most 140 characters), or null to clear it.",
    ),
    "INVALID_CUSTOMER": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "A resolved Customer reference is required.",
    ),
    "INVALID_DESTINATION_ACCOUNT": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The selected destination account is not valid for this Company.",
    ),
    "INVALID_FIELDS": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "One or more requested fields are not available for this read operation.",
    ),
    "INVALID_MODE_OF_PAYMENT": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The selected Mode of Payment has no valid bank or cash account for this Company.",
    ),
    "INVALID_ORDER_DETAILS": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "The request cannot continue because the selected business conditions are not supported.",
    ),
    "INVALID_PAYMENT_AMOUNT": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Payment amount must be greater than zero.",
    ),
    "INVALID_PAYMENT_DESTINATION": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "The selected payment destination is unavailable or invalid.",
    ),
    "INVALID_PAYMENT_ENTRY_STATE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The submitted Customer Payment Entry has no eligible unallocated or Sales Order advance amount.",
    ),
    "INVALID_PAYMENT_TERMS_TEMPLATE": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Payment Terms Template must be an exact non-empty name.",
    ),
    "INVALID_PURCHASE_ORDER_DETAILS": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "A resolved Supplier reference is required.",
    ),
    "INVALID_QUOTATION_DETAILS": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Provide either a discount percentage or discount amount, not both.",
    ),
    "INVALID_REFERENCE_COUNT": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Provide 2-20 Sales Invoice allocations.",
    ),
    "INVALID_SALES_INVOICE": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "An exact Sales Invoice name is required.",
    ),
    "INVALID_SALES_INVOICE_DETAILS": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Company is not available to the authenticated user.",
    ),
    "INVALID_SALES_ORDER": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "An exact Sales Order name is required.",
    ),
    "INVALID_SOURCE_ROW": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Every selected row must belong to the Purchase Order.",
    ),
    "INVALID_SUPPLIER": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Supplier is not available to the authenticated user.",
    ),
    "INVALID_TERMS": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Terms and conditions must be an exact non-empty name.",
    ),
    "INVALID_WAREHOUSE": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "The warehouse is disabled, belongs to another company, or is not valid for transactions.",
    ),
    "COMPANY_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND, "The requested Company was not found."
    ),
    "INVOICE_NOT_OUTSTANDING": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Only a submitted Sales Invoice can be reconciled.",
    ),
    "MIXED_CURRENCY_AGGREGATE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Choose whether the payment is received or paid before aggregating amounts across currencies.",
    ),
    "MIXED_INVOICE_CURRENCY_UNSUPPORTED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Mixed Sales Invoice transaction currencies are unsupported.",
    ),
    "MODE_OF_PAYMENT_ACCOUNT_MISSING": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The selected Mode of Payment has no valid bank or cash account for this Company.",
    ),
    "NATIVE_PAYMENT_STATE_INVALID": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Payment Entry could not be prepared as a draft.",
    ),
    "NATIVE_PAYMENT_VALIDATION_FAILED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Payment Entry did not pass validation.",
    ),
    "NATIVE_RECONCILIATION_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "Reconciliation is unavailable with the current setup.",
    ),
    "NATIVE_VALIDATION_FAILED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The document did not pass validation.",
    ),
    "NONZERO_DIFFERENCE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The prepared payment contains a difference amount this operation cannot process.",
    ),
    "NO_MAPPABLE_ITEMS": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "No eligible items are available for this conversion.",
    ),
    "NO_OUTSTANDING": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The selected invoices have no outstanding amount available for allocation.",
    ),
    "PARTY_CURRENCY_MISMATCH": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Every Sales Invoice must use one party-account currency.",
    ),
    "PARTY_MISMATCH": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Payment Entry and Sales Invoice must belong to the same Customer.",
    ),
    "PAYMENT_ENTRY_CREATION_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "ERPNext could not create the Payment Entry.",
    ),
    "PAYMENT_ENTRY_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND, "The requested Payment Entry was not found."
    ),
    "PAYMENT_TERMS_UNSUPPORTED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This reconciliation does not support allocation by payment terms.",
    ),
    "QUANTITY_EXCEEDS_REMAINING": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The requested receipt quantity exceeds the remaining quantity.",
    ),
    "RECEIVABLE_ACCOUNT_MISMATCH": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Every Sales Invoice must use one effective receivable account.",
    ),
    "RECONCILIATION_ALREADY_RUNNING": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "A Payment Reconciliation process is already running for this Customer and Company.",
    ),
    "RECONCILIATION_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "ERPNext could not complete the reconciliation. Review the payment and invoice status before trying again.",
    ),
    "REGIONAL_VALIDATION_FAILED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Regional validation rejected this reconciliation.",
    ),
    "REJECTED_WAREHOUSE_REQUIRED": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "A rejected warehouse is required for a rejected quantity.",
    ),
    "RETURN_REFERENCE_UNSUPPORTED": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Return Sales Invoices are not supported.",
    ),
    "SALES_INVOICE_CREATION_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "ERPNext could not create the Sales Invoice.",
    ),
    "SALES_INVOICE_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND,
        "The Sales Invoice was not found.",
    ),
    "SALES_INVOICE_NOT_OUTSTANDING": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Sales Invoice has no outstanding amount to receive.",
    ),
    "SALES_INVOICE_NOT_SUBMITTED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Sales Invoice must be submitted before a payment can be created.",
    ),
    "SALES_ORDER_NOT_ELIGIBLE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Sales Order is no longer eligible for a Customer advance.",
    ),
    "SALES_ORDER_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND,
        "The Sales Order was not found.",
    ),
    "SALES_ORDER_NOT_SUBMITTED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Sales Order must be submitted before an advance payment can be created.",
    ),
    "SOURCE_NOT_ELIGIBLE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The source document is not eligible for this conversion.",
    ),
    "SOURCE_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND,
        "The requested source document was not found.",
    ),
    "SOURCE_NOT_READY": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The source document is not in a state that allows this conversion.",
    ),
    "TERMS_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "ERPNext could not render the selected Terms and Conditions.",
    ),
    "TRANSACTION_REFERENCE_REQUIRED": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Reference number and reference date are required for a Bank destination.",
    ),
    "UNALLOCATED_RECEIPT_UNSUPPORTED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The receipt amount must equal the explicit allocations.",
    ),
    "UNEXPECTED_ACCOUNTING_STATE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This payment contains tax, withholding, or deduction amounts this operation cannot reconcile.",
    ),
    "UNEXPECTED_DEDUCTION_STATE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This payment includes a deduction this operation cannot process.",
    ),
    "UNEXPECTED_PAYMENT_STATE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The prepared payment amount is not supported for this operation.",
    ),
    "UNEXPECTED_REFERENCE_STATE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Payment Entry is already allocated and cannot be used for this operation.",
    ),
    "UNEXPECTED_TAX_STATE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This payment contains tax or withholding amounts this operation cannot process.",
    ),
    "UNSUPPORTED_NATIVE_PAYMENT_STATE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This payment cannot be processed because it includes tax, withholding, or deduction amounts.",
    ),
    "UNSUPPORTED_QUOTATION_PARTY": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Only Customer Quotations are supported for this conversion.",
    ),
    "UNSUPPORTED_SOURCE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This Purchase Order cannot be converted through this operation.",
    ),
    "UNSUPPORTED_SOURCE_ROW": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "Drop-ship Purchase Order rows are not supported by this conversion.",
    ),
    "WAREHOUSE_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND,
        "The requested warehouse was not found.",
    ),
    "WAREHOUSE_REQUIRED": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "A warehouse is required for the accepted receipt quantity.",
    ),
    "CONTACT_CHILD_STALE_STATE": PublicErrorDefinition(
        ErrorCategory.STALE_STATE,
        "The selected Contact details changed. Review them and prepare again.",
    ),
    "CONTACT_CREATE_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The Contact could not be created. Please try again later.",
    ),
    "CONTACT_DUPLICATE_SUSPECTED": PublicErrorDefinition(
        ErrorCategory.AMBIGUOUS_SELECTION,
        "A Contact with matching details already exists. Review the matches.",
    ),
    "CONTACT_EMAIL_AMBIGUOUS": PublicErrorDefinition(
        ErrorCategory.AMBIGUOUS_SELECTION,
        "More than one matching email address was found. Select one Contact.",
    ),
    "CONTACT_EMAIL_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND,
        "The selected email address was not found on this Contact.",
    ),
    "CONTACT_INVALID_DATA": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "The Contact details are not valid. Review the information and try again.",
    ),
    "CONTACT_INVALID_EMAIL": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Provide one valid email address for the Contact.",
    ),
    "CONTACT_INVALID_IDENTITY": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Provide a first name, last name, or company name for the Contact.",
    ),
    "CONTACT_INVALID_PHONE": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST, "Provide a valid phone number for the Contact."
    ),
    "CONTACT_INVALID_REQUEST": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Provide the Contact information required for this operation.",
    ),
    "CONTACT_LINK_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The Contact could not be linked to the Customer. Please try again.",
    ),
    "CONTACT_LINK_STALE_STATE": PublicErrorDefinition(
        ErrorCategory.STALE_STATE,
        "The Contact changed after preparation. Review it and prepare the link again.",
    ),
    "CONTACT_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND, "The requested Contact was not found."
    ),
    "CONTACT_NOT_LINKED_TO_CUSTOMER": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This Contact is not linked to the selected Customer.",
    ),
    "CONTACT_PHONE_AMBIGUOUS": PublicErrorDefinition(
        ErrorCategory.AMBIGUOUS_SELECTION,
        "More than one matching phone number was found. Select one Contact.",
    ),
    "CONTACT_PHONE_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND,
        "The selected phone number was not found on this Contact.",
    ),
    "CONTACT_PRIMARY_STATE_INCONSISTENT": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The Customer's primary Contact details are inconsistent. Review them before continuing.",
    ),
    "CONTACT_PRIMARY_UNSUPPORTED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This Contact relationship cannot be used as the Customer's primary Contact.",
    ),
    "CONTACT_SCOPE_REQUIRED": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Specify the Customer associated with this Contact before continuing.",
    ),
    "CONTACT_SHARED_WITH_OTHER_PARTIES": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This Contact is linked to another party and cannot be changed through this operation.",
    ),
    "CONTACT_STALE_STATE": PublicErrorDefinition(
        ErrorCategory.STALE_STATE,
        "The Contact or Customer changed after preparation. Review the details and prepare again.",
    ),
    "CONTACT_UPDATE_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The Contact could not be updated. Please try again later.",
    ),
    "CREDENTIAL_INACTIVE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "This Customer Service Credential is inactive.",
    ),
    "CREDENTIAL_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.NOT_FOUND,
        "The requested Customer Service Credential was not found.",
    ),
    "CREDENTIAL_READ_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The Customer Service Credential could not be read. Please try again later.",
    ),
    "CREDENTIAL_SECRET_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The credential information needed for this email is unavailable.",
    ),
    "CUSTOMER_EMAIL_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "A valid primary email address is not available for this Customer.",
    ),
    "CUSTOMER_PRIMARY_CONTACT_STALE": PublicErrorDefinition(
        ErrorCategory.STALE_STATE,
        "The Customer's primary Contact changed after preparation. Review and prepare again.",
    ),
    "CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED": PublicErrorDefinition(
        ErrorCategory.PERMISSION_DENIED,
        "You need permission to update the Customer's Contact details.",
    ),
    "CUSTOMER_STRUCTURED_QUERY_REQUIRED": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "For an email search, use the Customer search filters and enter the exact email address.",
    ),
    "EMAIL_RENDER_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The credential email could not be prepared. Please try again later.",
    ),
    "EMAIL_TEMPLATE_INVALID": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The configured credential email template cannot be used.",
    ),
    "EMAIL_TEMPLATE_NOT_CONFIGURED": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "A credential email template has not been configured.",
    ),
    "EMAIL_TEMPLATE_NOT_FOUND": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The configured credential email template is unavailable.",
    ),
    "EMAIL_TEMPLATE_UNSAFE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "The configured credential email template cannot be used for security reasons.",
    ),
    "GSTIN_UNSUPPORTED": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The provided GST identification number is not supported.",
    ),
    "INDIA_COMPLIANCE_ADDRESS_BRIDGE_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "Customer address details cannot be prepared in the current setup.",
    ),
    "INDIA_COMPLIANCE_GST_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "GST details cannot be prepared in the current setup.",
    ),
    "INVALID_CUSTOMER_DETAILS": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Review the Customer details and provide the required information.",
    ),
    "ITEM_RUNTIME_REQUIREMENT_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "Required Item details are unavailable in the current setup.",
    ),
    "OPERATOR_EMAIL_UNAVAILABLE": PublicErrorDefinition(
        ErrorCategory.CONFIGURATION_UNAVAILABLE,
        "Your user account does not have a valid email address for this operation.",
    ),
    "PRIMARY_CONTACT_PROMOTION_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The Customer's primary Contact could not be updated. Please try again.",
    ),
    "PRIMARY_CONTACT_PROMOTION_UNSAFE": PublicErrorDefinition(
        ErrorCategory.BUSINESS_RULE_BLOCKED,
        "The existing Contact relationships do not allow this primary Contact change.",
    ),
    "TEA_ENTRY_VALIDATION_FAILED": PublicErrorDefinition(
        ErrorCategory.INVALID_REQUEST,
        "Review the Tea Entry details and correct any invalid information.",
    ),
    "TEA_ENTRY_WRITE_FAILED": PublicErrorDefinition(
        ErrorCategory.TEMPORARY_FAILURE,
        "The Tea Entry could not be saved. Please try again later.",
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
