"""Profile-scoped MCP wrappers for shared existing-document lifecycle actions."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ..contracts.lifecycle import (
	LifecycleConfirmInput,
	LifecycleResult,
	PrepareActionInput,
	PrepareDeleteInput,
	PrepareUpdateInput,
	PrepareChildAddInput,
)
from ..contracts.registry import tool_meta
from ..runtime import execute_tool_with_context
from ..services.common import lifecycle


def register_lifecycle_tools(mcp: Any, profile: str) -> None:
	result_adapter = TypeAdapter(LifecycleResult)

	@mcp.tool(description="Prepare an exact existing-document field update without writing.", meta=tool_meta("prepare_document_update"), structured_output=True)
	def prepare_document_update(request: PrepareUpdateInput, ctx: Context) -> LifecycleResult:
		return result_adapter.validate_python(execute_tool_with_context(ctx, "prepare_document_update", lambda: lifecycle.prepare_update(request.target.model_dump(), [change.model_dump() for change in request.changes], profile), rest_arguments=request.model_dump(mode="json")))

	@mcp.tool(description="Apply a prepared exact existing-document field update after approval.", meta=tool_meta("confirm_document_update"), structured_output=True)
	def confirm_document_update(request: LifecycleConfirmInput, ctx: Context) -> LifecycleResult:
		return result_adapter.validate_python(execute_tool_with_context(ctx, "confirm_document_update", lambda: lifecycle.confirm("update", request.approval_token, request.confirm, profile), rest_arguments=request.model_dump(mode="json")))

	@mcp.tool(description="Prepare adding one resolved Item as a new row to an exact existing Draft transaction.", meta=tool_meta("prepare_document_child_add"), structured_output=True)
	def prepare_document_child_add(request: PrepareChildAddInput, ctx: Context) -> LifecycleResult:
		return result_adapter.validate_python(execute_tool_with_context(ctx, "prepare_document_child_add", lambda: lifecycle.prepare_child_add(request.target.model_dump(), request.item.model_dump(), request.qty, request.rate, profile), rest_arguments=request.model_dump(mode="json")))

	@mcp.tool(description="Apply a prepared new item row after approval.", meta=tool_meta("confirm_document_child_add"), structured_output=True)
	def confirm_document_child_add(request: LifecycleConfirmInput, ctx: Context) -> LifecycleResult:
		return result_adapter.validate_python(execute_tool_with_context(ctx, "confirm_document_child_add", lambda: lifecycle.confirm("child_add", request.approval_token, request.confirm, profile), rest_arguments=request.model_dump(mode="json")))

	def prepare(name: str, action: str):
		@mcp.tool(name=name, description=f"Prepare an exact existing-document {action} action.", meta=tool_meta(name), structured_output=True)
		def tool(request: PrepareActionInput, ctx: Context) -> LifecycleResult:
			return result_adapter.validate_python(execute_tool_with_context(ctx, name, lambda: getattr(lifecycle, f"prepare_{action}")(request.target.model_dump(), profile), rest_arguments=request.model_dump(mode="json")))
		tool.__name__ = name
		return tool

	def confirm_tool(name: str, action: str):
		@mcp.tool(name=name, description=f"Confirm an exact existing-document {action} action.", meta=tool_meta(name), structured_output=True)
		def tool(request: LifecycleConfirmInput, ctx: Context) -> LifecycleResult:
			return result_adapter.validate_python(execute_tool_with_context(ctx, name, lambda: lifecycle.confirm(action, request.approval_token, request.confirm, profile), rest_arguments=request.model_dump(mode="json")))
		tool.__name__ = name
		return tool

	prepare("prepare_document_submit", "submit")
	confirm_tool("confirm_document_submit", "submit")
	prepare("prepare_document_cancel", "cancel")
	confirm_tool("confirm_document_cancel", "cancel")
	prepare("prepare_document_delete", "delete")
	confirm_tool("confirm_document_delete", "delete")
