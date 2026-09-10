"""Declared MCP public-tool metadata used by audits and generated documentation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

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
from .selling.quotation_to_sales_order import (
	ConfirmQuotationToSalesOrderOutput,
	PrepareQuotationToSalesOrderOutput,
	QuotationToSalesOrderInput,
	QuotationToSalesOrderConfirmInput,
)
from .selling.sales_order_read import (
    GetSalesOrderInput,
    GetSalesOrderOutput,
    SalesOrderAggregateInput,
    SalesOrderAggregateOutput,
    SalesOrderItemQueryInput,
    SalesOrderItemQueryOutput,
    SalesOrderSearchInput,
    SalesOrderSearchOutput,
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


class ToolOperation(StrEnum):
    SEARCH = "SEARCH"
    RESOLVE = "RESOLVE"
    PREPARE = "PREPARE"
    CONFIRM = "CONFIRM"


class SideEffectClass(StrEnum):
    READ = "READ"
    RESOLVE = "RESOLVE"
    PREPARE = "PREPARE"
    CONFIRM_WRITE = "CONFIRM_WRITE"


TRUSTED_PENDING_OPERATION_GUARD = "trusted_pending_operation"


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

    @property
    def compliant(self) -> bool:
        return (
            not self.legacy
            and self.input_model is not None
            and self.output_model is not None
        )

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


# This set is the complete pre-07A legacy inventory. Future migrations may
# remove names from it; adding names requires a new architecture decision.
FROZEN_LEGACY_TOOL_NAMES = frozenset(
    {
        "prepare_customer",
        "confirm_customer",
        "prepare_item",
        "confirm_item",
        "prepare_sales_order",
        "confirm_sales_order",
    }
)


def _legacy(
    name: str,
    domain: str,
    operation: ToolOperation,
    side_effect: SideEffectClass,
    purpose: str,
    approval_required: bool,
    approval_guard: str | None = None,
) -> ToolContract:
    return ToolContract(
        name,
        domain,
        operation,
        side_effect,
        purpose,
        approval_required,
        legacy=True,
        approval_guard=approval_guard,
    )


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
    "prepare_customer": _legacy(
        "prepare_customer",
        "Masters",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Validate a Customer preview without writing.",
        False,
    ),
    "confirm_customer": _legacy(
        "confirm_customer",
        "Masters",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create a prepared Customer.",
        True,
        TRUSTED_PENDING_OPERATION_GUARD,
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
    "prepare_item": _legacy(
        "prepare_item",
        "Masters",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Validate an Item preview without writing.",
        False,
    ),
    "confirm_item": _legacy(
        "confirm_item",
        "Masters",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create a prepared Item.",
        True,
        TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_sales_order": _legacy(
        "prepare_sales_order",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare a Sales Order preview without writing.",
        False,
    ),
    "confirm_sales_order": _legacy(
        "confirm_sales_order",
        "Selling",
        ToolOperation.CONFIRM,
        SideEffectClass.CONFIRM_WRITE,
        "Create a prepared Sales Order.",
        True,
        TRUSTED_PENDING_OPERATION_GUARD,
    ),
    "prepare_quotation": ToolContract(
        "prepare_quotation",
        "Selling",
        ToolOperation.PREPARE,
        SideEffectClass.PREPARE,
        "Prepare an ERPNext-calculated Quotation preview without writing.",
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
        "search_sales_orders",
        "Selling",
        ToolOperation.SEARCH,
        "Search permitted Sales Orders using typed filters, projection, sorting, and pagination.",
        SalesOrderSearchInput,
        SalesOrderSearchOutput,
    ),
    (
        "get_quotation",
        "Existing Documents",
        ToolOperation.RESOLVE,
        "Retrieve a permitted existing Quotation summary.",
        DocumentReadInput,
        DocumentReadOutput,
    ),
    (
        "search_quotations",
        "Existing Documents",
        ToolOperation.SEARCH,
        "Search permitted Quotations with bounded business filters.",
        DocumentSearchInput,
        DocumentSearchOutput,
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
	"Prepare an exact email preview with a permission-checked generic PDF attachment.",
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
)


def get_tool_contract(name: str) -> ToolContract:
    """Return declared metadata, failing loudly for an ungoverned public tool."""
    return TOOL_CONTRACTS[name]


def tool_meta(name: str) -> dict[str, Any]:
    """Return the safe metadata published for a registered public tool."""
    return get_tool_contract(name).mcp_meta()
