"""MCP wrappers for bounded Customer-linked Contact operations."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import CustomerReference, NonEmptyString
from ...contracts.interaction import approval_directive, selection_directive
from ...contracts.masters.contact import (
	ConfirmCustomerContactOutput,
	ContactMatch,
	ContactSearchInput,
	ContactSearchOutput,
	ContactSearchResultContract,
	CustomerContactConfirmInput,
	CustomerContactConfirmResult,
	CustomerContactPrepareInput,
	CustomerContactPrepareResult,
	PrepareCustomerContactOutput,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.masters.customer_contact import (
	confirm_customer_contact as _confirm_customer_contact,
	prepare_customer_contact as _prepare_customer_contact,
	search_contacts as _search_contacts,
)


_search_adapter = TypeAdapter(ContactSearchResultContract)
_prepare_adapter = TypeAdapter(CustomerContactPrepareResult)
_confirm_adapter = TypeAdapter(CustomerContactConfirmResult)


def search_contacts(
	query: NonEmptyString,
	ctx: Context,
	customer: CustomerReference | None = None,
	match: ContactMatch = "auto",
	limit: int = 20,
	offset: int = 0,
) -> ContactSearchOutput:
	"""Find permission-visible Contacts, with fuzzy names only in Customer context."""
	request = ContactSearchInput(
		query=query,
		customer=customer,
		match=match,
		limit=limit,
		offset=offset,
	)
	result = execute_tool_with_context(
		ctx,
		"search_contacts",
		lambda: _search_contacts(**request.model_dump(mode="json")),
		rest_arguments=request.model_dump(mode="json"),
	)
	if result.get("status") == "ok" and result.get("count", 0) > 1:
		result = {**result, "interaction": selection_directive().model_dump(mode="json")}
	return ContactSearchOutput(root=_search_adapter.validate_python(result))


def prepare_customer_contact(
	request: CustomerContactPrepareInput, ctx: Context
) -> PrepareCustomerContactOutput:
	"""Prepare a new or explicitly selected Contact without writing."""
	request = CustomerContactPrepareInput.model_validate(request)
	result = execute_tool_with_context(
		ctx,
		"prepare_customer_contact",
		lambda: _prepare_customer_contact(request.model_dump(mode="json")),
		rest_arguments=request.model_dump(mode="json"),
	)
	if result.get("status") == "ready":
		result = {**result, "interaction": approval_directive().model_dump(mode="json")}
	return PrepareCustomerContactOutput(root=_prepare_adapter.validate_python(result))


def confirm_customer_contact(
	approval_token: NonEmptyString, confirm: bool, ctx: Context
) -> ConfirmCustomerContactOutput:
	"""Execute a prepared Contact operation only after the shared approval guard."""
	request = CustomerContactConfirmInput(approval_token=approval_token, confirm=confirm)
	result = execute_tool_with_context(
		ctx,
		"confirm_customer_contact",
		lambda: _confirm_customer_contact(request.approval_token, request.confirm),
		rest_arguments=request.model_dump(mode="json"),
	)
	return ConfirmCustomerContactOutput(root=_confirm_adapter.validate_python(result))


def register_customer_contact_tools(mcp: Any) -> None:
	"""Register the Sales-only Customer-linked Contact capability."""

	mcp.tool(meta=tool_meta("search_contacts"), structured_output=True)(search_contacts)
	mcp.tool(meta=tool_meta("prepare_customer_contact"), structured_output=True)(prepare_customer_contact)
	mcp.tool(meta=tool_meta("confirm_customer_contact"), structured_output=True)(confirm_customer_contact)
