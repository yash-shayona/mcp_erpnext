"""MCP wrappers for standalone Contact creation."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.interaction import approval_directive
from ...contracts.masters.contact import (
	ConfirmContactOutput,
	ContactConfirmInput,
	ContactConfirmResult,
	ContactPrepareInput,
	ContactPrepareResult,
	PrepareContactOutput,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.masters.contact import confirm_contact as _confirm_contact
from ...services.masters.contact import prepare_contact as _prepare_contact


_prepare_adapter = TypeAdapter(ContactPrepareResult)
_confirm_adapter = TypeAdapter(ContactConfirmResult)


def prepare_contact(request: ContactPrepareInput, ctx: Context) -> PrepareContactOutput:
	"""Prepare a standalone Contact without writing."""
	request = ContactPrepareInput.model_validate(request)
	result = execute_tool_with_context(
		ctx,
		"prepare_contact",
		lambda: _prepare_contact(request.model_dump(mode="json")),
		rest_arguments=request.model_dump(mode="json"),
	)
	if result.get("status") == "ready":
		result = {**result, "interaction": approval_directive().model_dump(mode="json")}
	return PrepareContactOutput(root=_prepare_adapter.validate_python(result))


def confirm_contact(
	approval_token: NonEmptyString, confirm: bool, ctx: Context
) -> ConfirmContactOutput:
	"""Execute a prepared standalone Contact operation after shared approval."""
	request = ContactConfirmInput(approval_token=approval_token, confirm=confirm)
	result = execute_tool_with_context(
		ctx,
		"confirm_contact",
		lambda: _confirm_contact(request.approval_token, request.confirm),
		rest_arguments=request.model_dump(mode="json"),
	)
	return ConfirmContactOutput(root=_confirm_adapter.validate_python(result))


def register_contact_tools(mcp: Any) -> None:
	"""Register the Sales-only standalone Contact capability."""

	mcp.tool(meta=tool_meta("prepare_contact"), structured_output=True)(prepare_contact)
	mcp.tool(meta=tool_meta("confirm_contact"), structured_output=True)(confirm_contact)
