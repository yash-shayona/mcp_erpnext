"""Declared MCP public-tool metadata used by audits and generated documentation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from mcp.types import ToolAnnotations

from .interaction import InteractionKind
from .lifecycle import (
    LifecycleConfirmInput,
    LifecycleResult,
    PrepareActionInput,
    PrepareDeleteInput,
    PrepareUpdateInput,
    PrepareChildAddInput,
)
from .masters.resolution import (
    CustomerResolutionOutput,
    CustomerSearchOutput,
    EntityResolveInput,
    ItemResolutionOutput,
    ItemSearchOutput,
    SelectResolvedCandidateOutput,
    SelectedCandidateInput,
    SupplierResolutionOutput,
    SupplierSearchOutput,
)
from .masters.customer_read import (
    CustomerAggregateInput,
    CustomerAggregateOutput,
    CustomerGetInput,
    CustomerGetOutput,
    CustomerQueryInput,
    CustomerQueryOutput,
)
from .masters.item_read import (
    ItemAggregateInput,
    ItemAggregateOutput,
    ItemGetInput,
    ItemGetOutput,
    ItemQueryInput,
    ItemQueryOutput,
)
from .masters.customer import (
	ConfirmCustomerOutput,
	CustomerConfirmInput,
	CustomerPrepareInput,
	PrepareCustomerOutput,
)
from .masters.contact import (
	ConfirmContactOutput,
	ContactConfirmInput,
	ConfirmContactUpdateOutput,
	ContactUpdateConfirmInput,
	ContactUpdatePrepareInput,
	ConfirmCustomerContactOutput,
	ContactPrepareInput,
	ContactSearchInput,
	ContactSearchOutput,
	CustomerContactConfirmInput,
	CustomerContactPrepareInput,
	ConfirmCustomerPrimaryContactOutput,
	CustomerPrimaryContactConfirmInput,
	CustomerPrimaryContactPrepareInput,
	PrepareContactOutput,
	PrepareContactUpdateOutput,
	PrepareCustomerContactOutput,
	PrepareCustomerPrimaryContactOutput,
)
from .masters.item import (
    ConfirmItemOutput,
    ItemConfirmInput,
    ItemPrepareInput,
    PrepareItemOutput,
)
from .buying.purchase_order import (
    ConfirmPurchaseOrderOutput,
    PreparePurchaseOrderOutput,
    PurchaseOrderConfirmInput,
    PurchaseOrderPrepareInput,
)
from .selling.quotation import (
    ConfirmQuotationOutput,
    PrepareQuotationOutput,
    QuotationConfirmInput,
    QuotationPrepareInput,
)
from .selling.quotation_read import (
    QuotationAggregateInput,
    QuotationAggregateOutput,
    QuotationGetInput,
    QuotationGetOutput,
    QuotationQueryInput,
    QuotationQueryOutput,
)
from .selling.quotation_to_sales_order import (
    ConfirmQuotationToSalesOrderOutput,
    PrepareQuotationToSalesOrderOutput,
    QuotationToSalesOrderInput,
    QuotationToSalesOrderConfirmInput,
)
from .selling.sales_order_to_sales_invoice import (
    ConfirmSalesOrderToSalesInvoiceOutput,
    PrepareSalesOrderToSalesInvoiceOutput,
    SalesOrderToSalesInvoiceInput,
    SalesOrderToSalesInvoiceConfirmInput,
)
from .selling.delivery_note import (
    ConfirmDeliveryNoteOutput,
    SalesOrderToDeliveryNoteConfirmInput,
    PrepareDeliveryNoteOutput,
    SalesOrderToDeliveryNoteInput,
)
from .selling.delivery_note_to_sales_invoice import (
    ConfirmDeliveryNoteToSalesInvoiceOutput,
    DeliveryNoteToSalesInvoiceConfirmInput,
    DeliveryNoteToSalesInvoiceInput,
    PrepareDeliveryNoteToSalesInvoiceOutput,
)
from .selling.sales_invoice_to_delivery_note import (
    ConfirmSalesInvoiceToDeliveryNoteOutput,
    ConfirmSalesInvoiceToDeliveryNoteResult,
    PrepareSalesInvoiceToDeliveryNoteOutput,
    PrepareSalesInvoiceToDeliveryNoteResult,
    SalesInvoiceToDeliveryNoteConfirmInput,
    SalesInvoiceToDeliveryNoteInput,
)
from .selling.delivery_note_read import (
    DeliveryNoteAggregateInput,
    DeliveryNoteAggregateOutput,
    DeliveryNoteGetInput,
    DeliveryNoteGetOutput,
    DeliveryNoteQueryInput,
    DeliveryNoteQueryOutput,
)
from .selling.sales_invoice import (
    ConfirmSalesInvoiceOutput,
    PrepareSalesInvoiceOutput,
    SalesInvoiceConfirmInput,
    SalesInvoicePrepareInput,
)
from .selling.sales_invoice_read import (
    SalesInvoiceAggregateInput,
    SalesInvoiceAggregateOutput,
    SalesInvoiceGetInput,
    SalesInvoiceGetOutput,
    SalesInvoiceQueryInput,
    SalesInvoiceQueryOutput,
)
from .selling.sales_order_read import (
    GetSalesOrderInput,
    GetSalesOrderOutput,
    SalesOrderAggregateInput,
    SalesOrderAggregateOutput,
    SalesOrderItemQueryInput,
    SalesOrderItemQueryOutput,
    SalesOrderQueryInput,
    SalesOrderQueryOutput,
)
from .selling.sales_order import (
    ConfirmSalesOrderOutput,
    PrepareSalesOrderOutput,
    SalesOrderConfirmInput,
    SalesOrderPrepareInput,
)
from .read import (
    DocumentReadInput,
    DocumentReadOutput,
    DocumentSearchInput,
    DocumentSearchOutput,
)
from .pdf import RenderDocumentPdfInput, RenderDocumentPdfOutput
from .email import (
    DocumentEmailConfirmInput,
    DocumentEmailConfirmOutput,
    DocumentEmailPrepareInput,
    DocumentEmailPrepareOutput,
)
from .accounts.sales_invoice_payment import (
    ConfirmSalesInvoicePaymentOutput,
    PrepareSalesInvoicePaymentOutput,
    SalesInvoicePaymentConfirmInput,
    SalesInvoicePaymentPrepareInput,
)
from .accounts.multi_invoice_customer_receipt import (
    ConfirmMultiInvoiceCustomerReceiptOutput,
    MultiInvoiceCustomerReceiptConfirmInput,
    MultiInvoiceCustomerReceiptPrepareInput,
    PrepareMultiInvoiceCustomerReceiptOutput,
)
from .accounts.customer_payment_entry import (
    ConfirmCustomerPaymentEntryOutput,
    CustomerPaymentEntryConfirmInput,
    CustomerPaymentEntryPrepareInput,
    PrepareCustomerPaymentEntryOutput,
)
from .accounts.sales_order_advance_payment import (
    ConfirmSalesOrderAdvancePaymentOutput,
    PrepareSalesOrderAdvancePaymentOutput,
    SalesOrderAdvancePaymentConfirmInput,
    SalesOrderAdvancePaymentPrepareInput,
)
from .accounts.customer_payment_reconciliation import (
    ConfirmCustomerPaymentReconciliationOutput,
    ConfirmCustomerPaymentReconciliationResult,
    CustomerPaymentReconciliationConfirmInput,
    CustomerPaymentReconciliationPrepareInput,
    PrepareCustomerPaymentReconciliationOutput,
    PrepareCustomerPaymentReconciliationResult,
)
from .accounts.payment_entry_read import (
    PaymentEntryAggregateInput,
    PaymentEntryAggregateOutput,
    PaymentEntryGetInput,
    PaymentEntryGetOutput,
    PaymentEntryQueryInput,
    PaymentEntryQueryOutput,
)


class ToolOperation(StrEnum):
    SEARCH = "SEARCH"
    RESOLVE = "RESOLVE"
    PREPARE = "PREPARE"
    CONFIRM = "CONFIRM"


class ToolRoutingRole(StrEnum):
    """MCP-wide role used to govern public-tool routing descriptions."""

    RESOLVE = "RESOLVE"
    SELECT_RESOLVED_CANDIDATE = "SELECT_RESOLVED_CANDIDATE"
    GET = "GET"
    SEARCH = "SEARCH"
    QUERY = "QUERY"
    AGGREGATE = "AGGREGATE"
    PREPARE = "PREPARE"
    CONFIRM = "CONFIRM"
    LIFECYCLE_PREPARE = "LIFECYCLE_PREPARE"
    LIFECYCLE_CONFIRM = "LIFECYCLE_CONFIRM"
    CONVERSION_PREPARE = "CONVERSION_PREPARE"
    CONVERSION_CONFIRM = "CONVERSION_CONFIRM"
    RENDER = "RENDER"
    EMAIL_PREPARE = "EMAIL_PREPARE"
    EMAIL_CONFIRM = "EMAIL_CONFIRM"


def routing_role_for_tool_name(
    name: str, operation: ToolOperation | None = None
) -> ToolRoutingRole:
    """Classify a stable public tool name without changing its public API."""
    if name == "select_resolved_candidate":
        return ToolRoutingRole.SELECT_RESOLVED_CANDIDATE
    if name == "render_document_pdf":
        return ToolRoutingRole.RENDER
    if name == "prepare_document_email":
        return ToolRoutingRole.EMAIL_PREPARE
    if name == "confirm_document_email":
        return ToolRoutingRole.EMAIL_CONFIRM
    if name.startswith("get_"):
        return ToolRoutingRole.GET
    if name.startswith("search_"):
        return ToolRoutingRole.SEARCH
    if name.startswith("query_"):
        return ToolRoutingRole.QUERY
    if name.startswith("aggregate_"):
        return ToolRoutingRole.AGGREGATE
    if name.startswith("prepare_document_"):
        return ToolRoutingRole.LIFECYCLE_PREPARE
    if name.startswith("confirm_document_"):
        return ToolRoutingRole.LIFECYCLE_CONFIRM
    if name.startswith("prepare_") and "_to_" in name:
        return ToolRoutingRole.CONVERSION_PREPARE
    if name.startswith("confirm_") and "_to_" in name:
        return ToolRoutingRole.CONVERSION_CONFIRM
    if name.startswith("resolve_"):
        return ToolRoutingRole.RESOLVE
    if name.startswith("prepare_"):
        return ToolRoutingRole.PREPARE
    if name.startswith("confirm_"):
        return ToolRoutingRole.CONFIRM
    if operation is not None:
        return {
            ToolOperation.SEARCH: ToolRoutingRole.SEARCH,
            ToolOperation.RESOLVE: ToolRoutingRole.RESOLVE,
            ToolOperation.PREPARE: ToolRoutingRole.PREPARE,
            ToolOperation.CONFIRM: ToolRoutingRole.CONFIRM,
        }[operation]
    raise ValueError(f"{name}: unable to derive a governed routing role.")


ROUTING_GUIDANCE: dict[ToolRoutingRole, str] = {
    ToolRoutingRole.RESOLVE: (
        "Use for one natural-language business reference needed by a workflow. "
        "`resolved` is terminal for lookup: reuse its reference; do not call "
        "search/query merely to verify. For `ambiguous`, use the returned "
        "candidates and selection flow. For `not_found`, ask for clarification; "
        "use discovery only when the user explicitly requests alternatives."
    ),
    ToolRoutingRole.SELECT_RESOLVED_CANDIDATE: (
        "Use only after an `ambiguous` Customer or Item resolution, with a "
        "candidate reference returned by that result. Do not use it for general "
        "get/search, or restart discovery when the candidate set is sufficient."
    ),
    ToolRoutingRole.GET: (
        "Use when the exact stable record or document reference is already known. "
        "Do not use for fuzzy discovery or query merely to fetch that exact record."
    ),
    ToolRoutingRole.SEARCH: (
        "Use for explicit candidate discovery, browsing, or comparison. Do not use "
        "after a successful resolver merely to verify it, or when structured "
        "filtering belongs to a query tool."
    ),
    ToolRoutingRole.QUERY: (
        "Use for structured filtering, projection, sorting, or pagination. It is "
        "not a fuzzy resolver and should not replace a dedicated aggregate tool."
    ),
    ToolRoutingRole.AGGREGATE: (
        "Use for this supported server-side count, sum, or grouped metric. Do not "
        "retrieve many rows through query and aggregate them in the client."
    ),
    ToolRoutingRole.PREPARE: (
        "Use after required references and inputs are established. Review the "
        "returned preview/prepared state, then use the paired confirm tool only "
        "through the existing approval flow; do not repeatedly prepare the same payload."
    ),
    ToolRoutingRole.CONFIRM: (
        "Execute only its valid prepared operation after the existing approval "
        "guard succeeds. It is never a read or discovery tool and cannot bypass "
        "preview or approval."
    ),
    ToolRoutingRole.LIFECYCLE_PREPARE: (
        "Use for this exact existing-document lifecycle action. Review its prepared "
        "preview/state before the paired confirm action; it does not itself apply "
        "the lifecycle change."
    ),
    ToolRoutingRole.LIFECYCLE_CONFIRM: (
        "Apply this lifecycle action only for its valid prepared exact-document "
        "state after the existing approval guard succeeds; do not use it to look up "
        "or discover documents."
    ),
    ToolRoutingRole.CONVERSION_PREPARE: (
        "Use only with the eligible exact source document required for this "
        "conversion. It returns a conversion preview/prepared state; review it and "
        "follow the paired confirm approval flow."
    ),
    ToolRoutingRole.CONVERSION_CONFIRM: (
        "Create this converted document only from its valid prepared source "
        "conversion after the existing approval guard succeeds; it is not a generic "
        "create tool."
    ),
    ToolRoutingRole.RENDER: (
        "Use with an exact permitted document reference to return PDF artifact "
        "content/metadata. It is read-only and must not be used to discover documents."
    ),
    ToolRoutingRole.EMAIL_PREPARE: (
        "Use with an exact permitted document to prepare recipients, preview, and "
        "attachment state. It does not send email; review the prepared result before "
        "the paired confirm approval flow."
    ),
    ToolRoutingRole.EMAIL_CONFIRM: (
        "Queue external email only from its valid prepared email state after the "
        "existing approval guard succeeds. It is not a document lookup or preview tool."
    ),
}


class SideEffectClass(StrEnum):
    READ = "READ"
    RESOLVE = "RESOLVE"
    PREPARE = "PREPARE"
    CONFIRM_WRITE = "CONFIRM_WRITE"


TRUSTED_PENDING_OPERATION_GUARD = "trusted_pending_operation"


@dataclass(frozen=True)
class MCPAnnotationOverrides:
    """Contract-specific deviations from the side-effect annotation defaults."""

    destructive_hint: bool | None = None
    idempotent_hint: bool | None = None
    open_world_hint: bool | None = None


@dataclass(frozen=True)
class ToolContract:
    """One public tool's stable contract declaration.

    Legacy entries are an intentionally frozen migration inventory. They may be
    removed during a focused migration but must not be added for new tools.
    """

    name: str
    domain: str
    operation: ToolOperation
    side_effect: SideEffectClass
    purpose: str
    approval_required: bool
    input_model: object | None = None
    output_model: object | None = None
    legacy: bool = False
    resolution_states: tuple[str, ...] = ()
    approval_guard: str | None = None
    interaction_kinds: tuple[InteractionKind, ...] = ()
    approval_confirm_tool: str | None = None
    annotation_overrides: MCPAnnotationOverrides = MCPAnnotationOverrides()
    routing_role: ToolRoutingRole | None = None

    @property
    def compliant(self) -> bool:
        return (
            not self.legacy
            and self.input_model is not None
            and self.output_model is not None
        )

    @property
    def governed_routing_role(self) -> ToolRoutingRole:
        """Return the explicit or centrally inferred routing role."""
        return self.routing_role or routing_role_for_tool_name(
            self.name, self.operation
        )

    def routing_description(self) -> str:
        """Build the single public description from purpose plus routing policy."""
        return f"{self.purpose} {ROUTING_GUIDANCE[self.governed_routing_role]}"

    def mcp_meta(self) -> dict[str, Any]:
        """Publish safe classification metadata alongside the MCP tool."""
        resolution = (
            {"resolution_states": list(self.resolution_states)}
            if self.resolution_states
            else {}
        )
        interaction = (
            {"interaction_kinds": [kind.value for kind in self.interaction_kinds]}
            if self.interaction_kinds
            else {}
        )
        return {
            "mcp_erpnext": {
                "domain": self.domain,
                "operation": self.operation.value,
                "routing_role": self.governed_routing_role.value,
                "side_effect": self.side_effect.value,
                "approval_required": self.approval_required,
                **(
                    {"approval_guard": self.approval_guard}
                    if self.approval_guard
                    else {}
                ),
                **resolution,
                **interaction,
            }
        }

    def mcp_annotations(self) -> ToolAnnotations:
        """Return standard MCP safety hints derived from this contract.

        PREPARE tools are intentionally non-read-only: their reviewed-operation
        state is part of the server environment even when no ERPNext business
        document has been created yet.
        """
        defaults = {
            SideEffectClass.READ: (True, False, True, False),
            SideEffectClass.RESOLVE: (True, False, True, False),
            SideEffectClass.PREPARE: (False, False, False, False),
            SideEffectClass.CONFIRM_WRITE: (False, False, False, False),
        }
        read_only, destructive, idempotent, open_world = defaults[self.side_effect]
        overrides = self.annotation_overrides
        return ToolAnnotations(
            readOnlyHint=read_only,
            destructiveHint=(
                overrides.destructive_hint
                if overrides.destructive_hint is not None
                else destructive
            ),
            idempotentHint=(
                overrides.idempotent_hint
                if overrides.idempotent_hint is not None
                else idempotent
            ),
            openWorldHint=(
                overrides.open_world_hint
                if overrides.open_world_hint is not None
                else open_world
            ),
        )


# This set is the complete pre-07A legacy inventory. Future migrations may
# remove names from it; adding names requires a new architecture decision.
FROZEN_LEGACY_TOOL_NAMES = frozenset()


TOOL_CONTRACTS = {
    "search_customers": ToolContract(
        "search_customers",
        "Masters",
        ToolOperation.SEARCH,
        SideEffectClass.READ,
        "Find permitted active Customers with explicit candidate references.",
        False,
        EntityResolveInput,
        CustomerSearchOutput,
        resolution_states=("resolved", "ambiguous", "not_found", "error"),
        interaction_kinds=(InteractionKind.SELECTION,),
    ),
    "resolve_customer": ToolContract(
        "resolve_customer",
        "Masters",
        ToolOperation.RESOLVE,
        SideEffectClass.RESOLVE,
        "Resolve one permitted Customer or return a terminal selection state.",
        False,
        EntityResolveInput,
        CustomerResolutionOutput,
        resolution_states=("resolved", "ambiguous", "not_found", "error"),
        interaction_kinds=(InteractionKind.SELECTION,),
    ),
    "prepare_customer": ToolContract(
        "prepare_customer",
        "Masters",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Validate a Customer preview without writing.",
        False,
        CustomerPrepareInput,
        PrepareCustomerOutput,
        interaction_kinds=(
            InteractionKind.INPUT,
            InteractionKind.SELECTION,
            InteractionKind.APPROVAL,
        ),
        approval_confirm_tool="confirm_customer",
    ),
    "confirm_customer": ToolContract(
        "confirm_customer",
        "Masters",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create a prepared Customer.",
        True,
        CustomerConfirmInput,
        ConfirmCustomerOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "search_contacts": ToolContract(
        "search_contacts",
        "Masters",
        ToolOperation.SEARCH,
        SideEffectClass.READ,
        "Find permission-visible Contacts with exact global or Customer-scoped bounded matching.",
        False,
        ContactSearchInput,
        ContactSearchOutput,
        interaction_kinds=(InteractionKind.SELECTION,),
    ),
    "prepare_customer_contact": ToolContract(
        "prepare_customer_contact",
        "Masters",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a native Contact create or explicit Customer link without writing.",
        False,
        CustomerContactPrepareInput,
        PrepareCustomerContactOutput,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool="confirm_customer_contact",
    ),
    "confirm_customer_contact": ToolContract(
        "confirm_customer_contact",
        "Masters",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create or link the reviewed native Contact for an existing Customer.",
        True,
        CustomerContactConfirmInput,
        ConfirmCustomerContactOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_customer_primary_contact": ToolContract(
        "prepare_customer_primary_contact",
        "Masters",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare promotion of an existing single-Customer Contact to the Customer primary Contact.",
        False,
        CustomerPrimaryContactPrepareInput,
        PrepareCustomerPrimaryContactOutput,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool="confirm_customer_primary_contact",
    ),
    "confirm_customer_primary_contact": ToolContract(
        "confirm_customer_primary_contact",
        "Masters",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Promote the reviewed existing Contact through native Contact and Customer saves.",
        True,
        CustomerPrimaryContactConfirmInput,
        ConfirmCustomerPrimaryContactOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
        annotation_overrides=MCPAnnotationOverrides(destructive_hint=True),
    ),
    "prepare_contact": ToolContract(
        "prepare_contact",
        "Masters",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a standalone native Contact without a party link.",
        False,
        ContactPrepareInput,
        PrepareContactOutput,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool="confirm_contact",
    ),
    "confirm_contact": ToolContract(
        "confirm_contact",
        "Masters",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create the reviewed standalone native Contact.",
        True,
        ContactConfirmInput,
        ConfirmContactOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_contact_update": ToolContract(
        "prepare_contact_update",
        "Masters",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
		"Prepare one standalone or Customer-scoped native Contact detail or communication update without writing.",
        False,
        ContactUpdatePrepareInput,
        PrepareContactUpdateOutput,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool="confirm_contact_update",
    ),
    "confirm_contact_update": ToolContract(
        "confirm_contact_update",
        "Masters",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
		"Apply one approved standalone or Customer-scoped native Contact update.",
        True,
        ContactUpdateConfirmInput,
        ConfirmContactUpdateOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
        annotation_overrides=MCPAnnotationOverrides(destructive_hint=True),
    ),
    "search_items": ToolContract(
        "search_items",
        "Masters",
        ToolOperation.SEARCH,
        SideEffectClass.READ,
        "Find permitted profile-enabled Items with explicit candidate references.",
        False,
        EntityResolveInput,
        ItemSearchOutput,
        resolution_states=("resolved", "ambiguous", "not_found", "error"),
        interaction_kinds=(InteractionKind.SELECTION,),
    ),
    "resolve_item": ToolContract(
        "resolve_item",
        "Masters",
        ToolOperation.RESOLVE,
        SideEffectClass.RESOLVE,
        "Resolve one permitted profile-enabled Item or return a terminal selection state.",
        False,
        EntityResolveInput,
        ItemResolutionOutput,
        resolution_states=("resolved", "ambiguous", "not_found", "error"),
        interaction_kinds=(InteractionKind.SELECTION,),
    ),
    "search_suppliers": ToolContract(
        "search_suppliers",
        "Masters",
        ToolOperation.SEARCH,
        SideEffectClass.READ,
        "Find permitted active Suppliers with explicit candidate references.",
        False,
        EntityResolveInput,
        SupplierSearchOutput,
        resolution_states=("resolved", "ambiguous", "not_found", "error"),
        interaction_kinds=(InteractionKind.SELECTION,),
    ),
    "resolve_supplier": ToolContract(
        "resolve_supplier",
        "Masters",
        ToolOperation.RESOLVE,
        SideEffectClass.RESOLVE,
        "Resolve one permitted Supplier or return a terminal selection state.",
        False,
        EntityResolveInput,
        SupplierResolutionOutput,
        resolution_states=("resolved", "ambiguous", "not_found", "error"),
        interaction_kinds=(InteractionKind.SELECTION,),
    ),
    "prepare_item": ToolContract(
        "prepare_item",
        "Masters",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Validate an Item preview without writing.",
        False,
        ItemPrepareInput,
        PrepareItemOutput,
        interaction_kinds=(
            InteractionKind.INPUT,
            InteractionKind.SELECTION,
            InteractionKind.APPROVAL,
        ),
        approval_confirm_tool="confirm_item",
    ),
    "confirm_item": ToolContract(
        "confirm_item",
        "Masters",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create a prepared Item.",
        True,
        ItemConfirmInput,
        ConfirmItemOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_sales_order": ToolContract(
        "prepare_sales_order",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a Sales Order preview without writing.",
        False,
        SalesOrderPrepareInput,
        PrepareSalesOrderOutput,
        interaction_kinds=(InteractionKind.INPUT, InteractionKind.APPROVAL),
        approval_confirm_tool="confirm_sales_order",
    ),
    "confirm_sales_order": ToolContract(
        "confirm_sales_order",
        "Selling",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create a prepared Sales Order.",
        True,
        SalesOrderConfirmInput,
        ConfirmSalesOrderOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_quotation": ToolContract(
        "prepare_quotation",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare an ERPNext-calculated Quotation preview without writing. Only the Customer and item rows are required: when the user does not provide `valid_till`, omit it and let the server apply its configured validity policy from the transaction date; do not ask the user to choose a default period.",
        False,
        QuotationPrepareInput,
        PrepareQuotationOutput,
        interaction_kinds=(InteractionKind.INPUT, InteractionKind.APPROVAL),
        approval_confirm_tool="confirm_quotation",
    ),
    "confirm_quotation": ToolContract(
        "confirm_quotation",
        "Selling",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create a prepared Draft Quotation after explicit approval.",
        True,
        QuotationConfirmInput,
        ConfirmQuotationOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_quotation_to_sales_order": ToolContract(
        "prepare_quotation_to_sales_order",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a Draft Sales Order preview from an eligible Submitted Customer Quotation using ERPNext native mapping.",
        False,
        QuotationToSalesOrderInput,
        PrepareQuotationToSalesOrderOutput,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool="confirm_quotation_to_sales_order",
    ),
    "confirm_quotation_to_sales_order": ToolContract(
        "confirm_quotation_to_sales_order",
        "Selling",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create the reviewed Draft Sales Order from a prepared Quotation conversion after the configured approval guard succeeds.",
        True,
        QuotationToSalesOrderConfirmInput,
        ConfirmQuotationToSalesOrderOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_sales_order_to_sales_invoice": ToolContract(
        "prepare_sales_order_to_sales_invoice",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a Draft Sales Invoice preview from an eligible Submitted Sales Order using ERPNext native mapping.",
        False,
        SalesOrderToSalesInvoiceInput,
        PrepareSalesOrderToSalesInvoiceOutput,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool="confirm_sales_order_to_sales_invoice",
    ),
    "confirm_sales_order_to_sales_invoice": ToolContract(
        "confirm_sales_order_to_sales_invoice",
        "Selling",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create the reviewed Draft Sales Invoice from a prepared Sales Order conversion after the configured approval guard succeeds.",
        True,
        SalesOrderToSalesInvoiceConfirmInput,
        ConfirmSalesOrderToSalesInvoiceOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_sales_invoice": ToolContract(
        "prepare_sales_invoice",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a standalone ERPNext-calculated Draft Sales Invoice preview without writing.",
        False,
        SalesInvoicePrepareInput,
        PrepareSalesInvoiceOutput,
        interaction_kinds=(InteractionKind.INPUT, InteractionKind.APPROVAL),
        approval_confirm_tool="confirm_sales_invoice",
    ),
    "confirm_sales_invoice": ToolContract(
        "confirm_sales_invoice",
        "Selling",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create a prepared standalone Draft Sales Invoice after explicit approval.",
        True,
        SalesInvoiceConfirmInput,
        ConfirmSalesInvoiceOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_sales_order_to_delivery_note": ToolContract(
        "prepare_sales_order_to_delivery_note",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a native Draft Delivery Note preview from a Submitted Sales Order.",
        False,
        SalesOrderToDeliveryNoteInput,
        PrepareDeliveryNoteOutput,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool="confirm_sales_order_to_delivery_note",
    ),
    "confirm_sales_order_to_delivery_note": ToolContract(
        "confirm_sales_order_to_delivery_note",
        "Selling",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create the approved native Draft Delivery Note from a Sales Order.",
        True,
        SalesOrderToDeliveryNoteConfirmInput,
        ConfirmDeliveryNoteOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_delivery_note_to_sales_invoice": ToolContract(
        "prepare_delivery_note_to_sales_invoice",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a native Draft Sales Invoice preview from a Submitted Delivery Note.",
        False,
        DeliveryNoteToSalesInvoiceInput,
        PrepareDeliveryNoteToSalesInvoiceOutput,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool="confirm_delivery_note_to_sales_invoice",
    ),
    "confirm_delivery_note_to_sales_invoice": ToolContract(
        "confirm_delivery_note_to_sales_invoice",
        "Selling",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create the approved native Draft Sales Invoice from a Delivery Note.",
        True,
        DeliveryNoteToSalesInvoiceConfirmInput,
        ConfirmDeliveryNoteToSalesInvoiceOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_sales_invoice_to_delivery_note": ToolContract(
        "prepare_sales_invoice_to_delivery_note",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a native Draft Delivery Note preview from a Submitted Sales Invoice.",
        False,
        SalesInvoiceToDeliveryNoteInput,
        PrepareSalesInvoiceToDeliveryNoteOutput,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool="confirm_sales_invoice_to_delivery_note",
    ),
    "confirm_sales_invoice_to_delivery_note": ToolContract(
        "confirm_sales_invoice_to_delivery_note",
        "Selling",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create the approved native Draft Delivery Note from a Sales Invoice.",
        True,
        SalesInvoiceToDeliveryNoteConfirmInput,
        ConfirmSalesInvoiceToDeliveryNoteOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_purchase_order": ToolContract(
        "prepare_purchase_order",
        "Buying",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare an ERPNext-calculated Purchase Order preview without writing.",
        False,
        PurchaseOrderPrepareInput,
        PreparePurchaseOrderOutput,
        interaction_kinds=(InteractionKind.INPUT, InteractionKind.APPROVAL),
        approval_confirm_tool="confirm_purchase_order",
    ),
    "confirm_purchase_order": ToolContract(
        "confirm_purchase_order",
        "Buying",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create a prepared Draft Purchase Order after explicit approval.",
        True,
        PurchaseOrderConfirmInput,
        ConfirmPurchaseOrderOutput,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "select_resolved_candidate": ToolContract(
        "select_resolved_candidate",
        "Masters",
        ToolOperation.RESOLVE,
        SideEffectClass.RESOLVE,
        "Revalidate a user-selected Customer or Item reference without writing.",
        False,
        SelectedCandidateInput,
        SelectResolvedCandidateOutput,
        resolution_states=("resolved", "not_found", "error"),
    ),
}

for _name, _operation, _purpose, _input_model, _confirm_tool in (
    (
        "prepare_document_update",
        ToolOperation.PREPARE,
        "Prepare an exact existing-document field update without writing.",
        PrepareUpdateInput,
        "confirm_document_update",
    ),
    (
        "prepare_document_child_add",
        ToolOperation.PREPARE,
        "Prepare adding one resolved Item as a new row to an exact Draft transaction.",
        PrepareChildAddInput,
        "confirm_document_child_add",
    ),
    (
        "prepare_document_submit",
        ToolOperation.PREPARE,
        "Prepare submission of an exact existing document.",
        PrepareActionInput,
        "confirm_document_submit",
    ),
    (
        "prepare_document_cancel",
        ToolOperation.PREPARE,
        "Prepare cancellation of an exact existing document.",
        PrepareActionInput,
        "confirm_document_cancel",
    ),
    (
        "prepare_document_delete",
        ToolOperation.PREPARE,
        "Prepare deletion of an exact existing document with link preflight.",
        PrepareDeleteInput,
        "confirm_document_delete",
    ),
):
    TOOL_CONTRACTS[_name] = ToolContract(
        _name,
        "Lifecycle",
        _operation,
        SideEffectClass.PREPARE,
        _purpose,
        False,
        _input_model,
        LifecycleResult,
        interaction_kinds=(InteractionKind.APPROVAL,),
        approval_confirm_tool=_confirm_tool,
    )

for _name, _action, _purpose, _input_model in (
    (
        "confirm_document_update",
        "update",
        "Apply a prepared exact existing-document update after approval.",
        LifecycleConfirmInput,
    ),
    (
        "confirm_document_child_add",
        "child_add",
        "Apply a prepared new transaction item row after approval.",
        LifecycleConfirmInput,
    ),
    (
        "confirm_document_submit",
        "submit",
        "Submit a prepared exact existing document after approval.",
        LifecycleConfirmInput,
    ),
    (
        "confirm_document_cancel",
        "cancel",
        "Cancel a prepared exact existing document after approval.",
        LifecycleConfirmInput,
    ),
    (
        "confirm_document_delete",
        "delete",
        "Delete a prepared exact existing document after approval.",
        LifecycleConfirmInput,
    ),
):
    TOOL_CONTRACTS[_name] = ToolContract(
        _name,
        "Lifecycle",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        _purpose,
        True,
        _input_model,
        LifecycleResult,
        approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
        annotation_overrides=MCPAnnotationOverrides(
            # Updating replaces stored values; submit makes a Draft immutable;
            # cancel invalidates it; delete removes it (and may cancel first).
            destructive_hint=_name
            in {
                "confirm_document_update",
                "confirm_document_submit",
                "confirm_document_cancel",
                "confirm_document_delete",
            }
        ),
    )

for _name, _domain, _operation, _purpose, _input_model, _output_model in (
    (
        "get_sales_order",
        "Selling",
        ToolOperation.RESOLVE,
        "Retrieve selected fields from one permitted Sales Order by exact reference.",
        GetSalesOrderInput,
        GetSalesOrderOutput,
    ),
    (
        "query_sales_orders",
        "Selling",
        ToolOperation.SEARCH,
        "Query permitted Sales Orders using typed filters, projection, sorting, and pagination.",
        SalesOrderQueryInput,
        SalesOrderQueryOutput,
    ),
    (
        "get_purchase_order",
        "Existing Documents",
        ToolOperation.RESOLVE,
        "Retrieve a permitted existing Purchase Order summary.",
        DocumentReadInput,
        DocumentReadOutput,
    ),
    (
        "search_purchase_orders",
        "Existing Documents",
        ToolOperation.SEARCH,
        "Search permitted Purchase Orders with bounded business filters.",
        DocumentSearchInput,
        DocumentSearchOutput,
    ),
):
    TOOL_CONTRACTS[_name] = ToolContract(
        _name,
        _domain,
        _operation,
        SideEffectClass.READ,
        _purpose,
        False,
        _input_model,
        _output_model,
        resolution_states=(
            ("ok", "not_found", "error") if _operation == ToolOperation.RESOLVE else ()
        ),
    )

TOOL_CONTRACTS["aggregate_sales_orders"] = ToolContract(
    "aggregate_sales_orders",
    "Selling",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Calculate deterministic permission-aware Sales Order metrics on the server.",
    False,
    SalesOrderAggregateInput,
    SalesOrderAggregateOutput,
)
TOOL_CONTRACTS["query_sales_order_items"] = ToolContract(
    "query_sales_order_items",
    "Selling",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Query permitted Sales Order Item history and optional server-side item metrics.",
    False,
    SalesOrderItemQueryInput,
    SalesOrderItemQueryOutput,
)
TOOL_CONTRACTS["get_quotation"] = ToolContract(
    "get_quotation",
    "Selling",
    ToolOperation.RESOLVE,
    SideEffectClass.READ,
    "Retrieve selected fields from one permitted Quotation by exact reference.",
    False,
    QuotationGetInput,
    QuotationGetOutput,
    resolution_states=("ok", "not_found", "error"),
)
TOOL_CONTRACTS["query_quotations"] = ToolContract(
    "query_quotations",
    "Selling",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Query permitted Quotations using typed filters, projection, sorting, and pagination.",
    False,
    QuotationQueryInput,
    QuotationQueryOutput,
)
TOOL_CONTRACTS["aggregate_quotations"] = ToolContract(
    "aggregate_quotations",
    "Selling",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Calculate deterministic permission-aware Quotation metrics on the server.",
    False,
    QuotationAggregateInput,
    QuotationAggregateOutput,
)
TOOL_CONTRACTS["get_sales_invoice"] = ToolContract(
    "get_sales_invoice",
    "Selling",
    ToolOperation.RESOLVE,
    SideEffectClass.READ,
    "Retrieve selected fields from one permitted Sales Invoice by exact reference.",
    False,
    SalesInvoiceGetInput,
    SalesInvoiceGetOutput,
    resolution_states=("ok", "not_found", "error"),
)
TOOL_CONTRACTS["query_sales_invoices"] = ToolContract(
    "query_sales_invoices",
    "Selling",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Query permitted Sales Invoices using typed filters, projection, sorting, and pagination.",
    False,
    SalesInvoiceQueryInput,
    SalesInvoiceQueryOutput,
)
TOOL_CONTRACTS["aggregate_sales_invoices"] = ToolContract(
    "aggregate_sales_invoices",
    "Selling",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Calculate deterministic permission-aware Sales Invoice metrics on the server.",
    False,
    SalesInvoiceAggregateInput,
    SalesInvoiceAggregateOutput,
)
TOOL_CONTRACTS["get_delivery_note"] = ToolContract(
    "get_delivery_note",
    "Selling",
    ToolOperation.RESOLVE,
    SideEffectClass.READ,
    "Retrieve selected fields from one permitted Delivery Note.",
    False,
    DeliveryNoteGetInput,
    DeliveryNoteGetOutput,
    resolution_states=("ok", "not_found", "error"),
)
TOOL_CONTRACTS["query_delivery_notes"] = ToolContract(
    "query_delivery_notes",
    "Selling",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Query permitted Delivery Notes using typed filters and projections.",
    False,
    DeliveryNoteQueryInput,
    DeliveryNoteQueryOutput,
)
TOOL_CONTRACTS["aggregate_delivery_notes"] = ToolContract(
    "aggregate_delivery_notes",
    "Selling",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Calculate deterministic permission-aware Delivery Note metrics.",
    False,
    DeliveryNoteAggregateInput,
    DeliveryNoteAggregateOutput,
)
TOOL_CONTRACTS["get_customer"] = ToolContract(
    "get_customer",
    "Masters",
    ToolOperation.RESOLVE,
    SideEffectClass.READ,
    "Retrieve selected fields from one permitted Customer by exact reference.",
    False,
    CustomerGetInput,
    CustomerGetOutput,
    resolution_states=("ok", "not_found", "error"),
)
TOOL_CONTRACTS["query_customers"] = ToolContract(
    "query_customers",
    "Masters",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Query permitted Customers with exact filters, projection, sorting, and pagination.",
    False,
    CustomerQueryInput,
    CustomerQueryOutput,
)
TOOL_CONTRACTS["aggregate_customers"] = ToolContract(
    "aggregate_customers",
    "Masters",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Calculate deterministic permission-aware Customer counts on the server.",
    False,
    CustomerAggregateInput,
    CustomerAggregateOutput,
)
TOOL_CONTRACTS["get_item"] = ToolContract(
    "get_item",
    "Masters",
    ToolOperation.RESOLVE,
    SideEffectClass.READ,
    "Retrieve selected fields from one permitted Item by exact reference.",
    False,
    ItemGetInput,
    ItemGetOutput,
    resolution_states=("ok", "not_found", "error"),
)
TOOL_CONTRACTS["query_items"] = ToolContract(
    "query_items",
    "Masters",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Query permitted Items with exact field filters, projection, sorting, and pagination; never fuzzy-match.",
    False,
    ItemQueryInput,
    ItemQueryOutput,
)
TOOL_CONTRACTS["aggregate_items"] = ToolContract(
    "aggregate_items",
    "Masters",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Calculate deterministic permission-aware Item counts, optionally grouped by an allowlisted field.",
    False,
    ItemAggregateInput,
    ItemAggregateOutput,
)
TOOL_CONTRACTS["render_document_pdf"] = ToolContract(
    "render_document_pdf",
    "Existing Documents",
    ToolOperation.RESOLVE,
    SideEffectClass.READ,
    "Render one permitted existing transactional document as an ephemeral PDF artifact.",
    False,
    RenderDocumentPdfInput,
    RenderDocumentPdfOutput,
    resolution_states=("ok", "not_found", "error"),
)

TOOL_CONTRACTS["prepare_document_email"] = ToolContract(
    "prepare_document_email",
    "Existing Documents",
    ToolOperation.PREPARE,
    SideEffectClass.PREPARE,
    "Prepare an exact email preview with a permission-checked PDF attachment; use recipient_scope party for the document party or self for the authenticated user's email.",
    False,
    DocumentEmailPrepareInput,
    DocumentEmailPrepareOutput,
    resolution_states=("ready_for_approval", "needs_input", "not_found", "error"),
    interaction_kinds=(InteractionKind.INPUT, InteractionKind.APPROVAL),
    approval_confirm_tool="confirm_document_email",
)
TOOL_CONTRACTS["confirm_document_email"] = ToolContract(
    "confirm_document_email",
    "Existing Documents",
    ToolOperation.CONFIRM,
    SideEffectClass.CONFIRM_WRITE,
    "Queue one exact prepared document email through Frappe's native Email Queue.",
    True,
    DocumentEmailConfirmInput,
    DocumentEmailConfirmOutput,
    approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    annotation_overrides=MCPAnnotationOverrides(open_world_hint=True),
)

TOOL_CONTRACTS["prepare_sales_invoice_payment"] = ToolContract(
    "prepare_sales_invoice_payment",
    "Accounts",
    ToolOperation.PREPARE,
    SideEffectClass.PREPARE,
    "Prepare a native Draft customer Payment Entry for one submitted Sales Invoice.",
    False,
    SalesInvoicePaymentPrepareInput,
    PrepareSalesInvoicePaymentOutput,
    interaction_kinds=(InteractionKind.APPROVAL,),
    approval_confirm_tool="confirm_sales_invoice_payment",
)
TOOL_CONTRACTS["prepare_multi_invoice_customer_receipt"] = ToolContract(
    "prepare_multi_invoice_customer_receipt",
    "Accounts",
    ToolOperation.PREPARE,
    SideEffectClass.PREPARE,
    "Prepare one explicit Customer receipt allocated across 2-20 submitted Sales Invoices.",
    False,
    MultiInvoiceCustomerReceiptPrepareInput,
    PrepareMultiInvoiceCustomerReceiptOutput,
    interaction_kinds=(InteractionKind.APPROVAL,),
    approval_confirm_tool="confirm_multi_invoice_customer_receipt",
)
TOOL_CONTRACTS["prepare_customer_payment_entry"] = ToolContract(
    "prepare_customer_payment_entry",
    "Accounts",
    ToolOperation.PREPARE,
    SideEffectClass.PREPARE,
    "Prepare a native standalone Draft Customer receipt Payment Entry with no invoice allocation.",
    False,
    CustomerPaymentEntryPrepareInput,
    PrepareCustomerPaymentEntryOutput,
    interaction_kinds=(InteractionKind.APPROVAL,),
    approval_confirm_tool="confirm_customer_payment_entry",
)
TOOL_CONTRACTS["confirm_customer_payment_entry"] = ToolContract(
    "confirm_customer_payment_entry",
    "Accounts",
    ToolOperation.CONFIRM,
    SideEffectClass.CONFIRM_WRITE,
    "Create the reviewed standalone Draft Customer receipt Payment Entry.",
    True,
    CustomerPaymentEntryConfirmInput,
    ConfirmCustomerPaymentEntryOutput,
    approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
)
TOOL_CONTRACTS["prepare_sales_order_advance_payment"] = ToolContract(
    "prepare_sales_order_advance_payment",
    "Accounts",
    ToolOperation.PREPARE,
    SideEffectClass.PREPARE,
    "Prepare a native Draft Customer advance Payment Entry for one submitted Sales Order.",
    False,
    SalesOrderAdvancePaymentPrepareInput,
    PrepareSalesOrderAdvancePaymentOutput,
    interaction_kinds=(InteractionKind.APPROVAL,),
    approval_confirm_tool="confirm_sales_order_advance_payment",
)
TOOL_CONTRACTS["confirm_sales_order_advance_payment"] = ToolContract(
    "confirm_sales_order_advance_payment",
    "Accounts",
    ToolOperation.CONFIRM,
    SideEffectClass.CONFIRM_WRITE,
    "Create the reviewed native Draft Customer advance Payment Entry.",
    True,
    SalesOrderAdvancePaymentConfirmInput,
    ConfirmSalesOrderAdvancePaymentOutput,
    approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
)
TOOL_CONTRACTS["prepare_customer_payment_reconciliation"] = ToolContract(
    "prepare_customer_payment_reconciliation",
    "Accounts",
    ToolOperation.PREPARE,
    SideEffectClass.PREPARE,
    "Prepare a bounded projection for applying one existing submitted Customer Payment Entry to one submitted Sales Invoice through native reconciliation.",
    False,
    CustomerPaymentReconciliationPrepareInput,
    PrepareCustomerPaymentReconciliationOutput,
    interaction_kinds=(InteractionKind.APPROVAL,),
    approval_confirm_tool="confirm_customer_payment_reconciliation",
)
TOOL_CONTRACTS["confirm_customer_payment_reconciliation"] = ToolContract(
    "confirm_customer_payment_reconciliation",
    "Accounts",
    ToolOperation.CONFIRM,
    SideEffectClass.CONFIRM_WRITE,
    "Apply the approved existing submitted Customer Payment Entry to one Sales Invoice through native ERPNext reconciliation.",
    True,
    CustomerPaymentReconciliationConfirmInput,
    ConfirmCustomerPaymentReconciliationOutput,
    approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
    annotation_overrides=MCPAnnotationOverrides(destructive_hint=True),
)
TOOL_CONTRACTS["confirm_multi_invoice_customer_receipt"] = ToolContract(
    "confirm_multi_invoice_customer_receipt",
    "Accounts",
    ToolOperation.CONFIRM,
    SideEffectClass.CONFIRM_WRITE,
    "Create the reviewed multi-invoice Customer receipt as one Draft Payment Entry.",
    True,
    MultiInvoiceCustomerReceiptConfirmInput,
    ConfirmMultiInvoiceCustomerReceiptOutput,
    approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
)
TOOL_CONTRACTS["confirm_sales_invoice_payment"] = ToolContract(
    "confirm_sales_invoice_payment",
    "Accounts",
    ToolOperation.CONFIRM,
    SideEffectClass.CONFIRM_WRITE,
    "Create the reviewed native Draft customer Payment Entry.",
    True,
    SalesInvoicePaymentConfirmInput,
    ConfirmSalesInvoicePaymentOutput,
    approval_guard=TRUSTED_PENDING_OPERATION_GUARD,
)
TOOL_CONTRACTS["get_payment_entry"] = ToolContract(
    "get_payment_entry",
    "Accounts",
    ToolOperation.RESOLVE,
    SideEffectClass.READ,
    "Retrieve selected fields and bounded native references from one permitted Payment Entry.",
    False,
    PaymentEntryGetInput,
    PaymentEntryGetOutput,
    resolution_states=("ok", "not_found", "error"),
)
TOOL_CONTRACTS["query_payment_entries"] = ToolContract(
    "query_payment_entries",
    "Accounts",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Query permitted Payment Entries using typed filters, bounded projection, sorting, and pagination.",
    False,
    PaymentEntryQueryInput,
    PaymentEntryQueryOutput,
)
TOOL_CONTRACTS["aggregate_payment_entries"] = ToolContract(
    "aggregate_payment_entries",
    "Accounts",
    ToolOperation.SEARCH,
    SideEffectClass.READ,
    "Calculate currency-safe permission-aware Payment Entry metrics on the server.",
    False,
    PaymentEntryAggregateInput,
    PaymentEntryAggregateOutput,
)


def get_tool_contract(name: str) -> ToolContract:
    """Return declared metadata, failing loudly for an ungoverned public tool."""
    return TOOL_CONTRACTS[name]


def tool_meta(name: str) -> dict[str, Any]:
    """Return the safe metadata published for a registered public tool."""
    return get_tool_contract(name).mcp_meta()


def tool_annotations(name: str) -> ToolAnnotations:
    """Return standard MCP safety hints for a registered public tool."""
    return get_tool_contract(name).mcp_annotations()
