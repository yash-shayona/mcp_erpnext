"""Declared MCP public-tool metadata used by audits and generated documentation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .masters.resolution import (
	CustomerResolutionOutput,
	CustomerSearchOutput,
	EntityResolveInput,
	ItemResolutionOutput,
	ItemSearchOutput,
	SelectResolvedCandidateOutput,
	SelectedCandidateInput,
)
from .selling.quotation import (
	ConfirmQuotationOutput,
	PrepareQuotationOutput,
	QuotationConfirmInput,
	QuotationPrepareInput,
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

	@property
	def compliant(self) -> bool:
		return not self.legacy and self.input_model is not None and self.output_model is not None

	def mcp_meta(self) -> dict[str, Any]:
		"""Publish safe classification metadata alongside the MCP tool."""
		resolution = (
			{"resolution_states": list(self.resolution_states)} if self.resolution_states else {}
		)
		return {
			"mcp_erpnext": {
				"domain": self.domain,
				"operation": self.operation.value,
				"side_effect": self.side_effect.value,
				"approval_required": self.approval_required,
				**({"approval_guard": self.approval_guard} if self.approval_guard else {}),
				**resolution,
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
	"search_customers": ToolContract("search_customers", "Masters", ToolOperation.SEARCH, SideEffectClass.READ, "Find permitted active Customers with explicit candidate references.", False, EntityResolveInput, CustomerSearchOutput, resolution_states=("resolved", "ambiguous", "not_found", "error")),
	"resolve_customer": ToolContract("resolve_customer", "Masters", ToolOperation.RESOLVE, SideEffectClass.RESOLVE, "Resolve one permitted Customer or return a terminal selection state.", False, EntityResolveInput, CustomerResolutionOutput, resolution_states=("resolved", "ambiguous", "not_found", "error")),
	"prepare_customer": _legacy("prepare_customer", "Masters", ToolOperation.PREPARE, SideEffectClass.PREPARE, "Validate a Customer preview without writing.", False),
	"confirm_customer": _legacy("confirm_customer", "Masters", ToolOperation.CONFIRM, SideEffectClass.CONFIRM_WRITE, "Create a prepared Customer.", True, TRUSTED_PENDING_OPERATION_GUARD),
	"search_items": ToolContract("search_items", "Masters", ToolOperation.SEARCH, SideEffectClass.READ, "Find permitted sales Items with explicit candidate references.", False, EntityResolveInput, ItemSearchOutput, resolution_states=("resolved", "ambiguous", "not_found", "error")),
	"resolve_item": ToolContract("resolve_item", "Masters", ToolOperation.RESOLVE, SideEffectClass.RESOLVE, "Resolve one permitted sales Item or return a terminal selection state.", False, EntityResolveInput, ItemResolutionOutput, resolution_states=("resolved", "ambiguous", "not_found", "error")),
	"prepare_item": _legacy("prepare_item", "Masters", ToolOperation.PREPARE, SideEffectClass.PREPARE, "Validate an Item preview without writing.", False),
	"confirm_item": _legacy("confirm_item", "Masters", ToolOperation.CONFIRM, SideEffectClass.CONFIRM_WRITE, "Create a prepared Item.", True, TRUSTED_PENDING_OPERATION_GUARD),
	"prepare_sales_order": _legacy("prepare_sales_order", "Selling", ToolOperation.PREPARE, SideEffectClass.PREPARE, "Prepare a Sales Order preview without writing.", False),
	"confirm_sales_order": _legacy("confirm_sales_order", "Selling", ToolOperation.CONFIRM, SideEffectClass.CONFIRM_WRITE, "Create a prepared Sales Order.", True, TRUSTED_PENDING_OPERATION_GUARD),
	"prepare_quotation": ToolContract("prepare_quotation", "Selling", ToolOperation.PREPARE, SideEffectClass.PREPARE, "Prepare an ERPNext-calculated Quotation preview without writing.", False, QuotationPrepareInput, PrepareQuotationOutput),
	"confirm_quotation": ToolContract("confirm_quotation", "Selling", ToolOperation.CONFIRM, SideEffectClass.CONFIRM_WRITE, "Create a prepared Draft Quotation after explicit server-verified human approval.", True, QuotationConfirmInput, ConfirmQuotationOutput, approval_guard=TRUSTED_PENDING_OPERATION_GUARD),
	"select_resolved_candidate": ToolContract("select_resolved_candidate", "Masters", ToolOperation.RESOLVE, SideEffectClass.RESOLVE, "Revalidate a user-selected Customer or Item reference without writing.", False, SelectedCandidateInput, SelectResolvedCandidateOutput, resolution_states=("resolved", "not_found", "error")),
}


def get_tool_contract(name: str) -> ToolContract:
	"""Return declared metadata, failing loudly for an ungoverned public tool."""
	return TOOL_CONTRACTS[name]


def tool_meta(name: str) -> dict[str, Any]:
	"""Return the safe metadata published for a registered public tool."""
	return get_tool_contract(name).mcp_meta()
