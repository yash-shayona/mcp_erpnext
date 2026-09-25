"""Profile-scoped MCP wrappers for generic prepared document email."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ..contracts.email import (
	DocumentEmailConfirmInput,
	DocumentEmailConfirmOutput,
	DocumentEmailPrepareInput,
	DocumentEmailPrepareOutput,
)
from ..contracts.registry import tool_meta
from ..runtime import execute_tool_with_context
from ..services.common import email as email_service


def register_document_email_tools(mcp: Any, profile: str) -> None:
	prepare_adapter = TypeAdapter(DocumentEmailPrepareOutput)
	confirm_adapter = TypeAdapter(DocumentEmailConfirmOutput)

	@mcp.tool(
		name="prepare_document_email",
		description="Prepare an exact approved email with a native PDF attachment for a permitted existing transaction.",
		meta=tool_meta("prepare_document_email"),
		structured_output=True,
	)
	def prepare_document_email(request: DocumentEmailPrepareInput, ctx: Context) -> DocumentEmailPrepareOutput:
		result = execute_tool_with_context(
			ctx,
			"prepare_document_email",
		lambda: email_service.prepare_document_email(
				request.doctype,
				request.name,
				profile,
				request.recipient_email,
				request.subject,
				request.message,
				request.print_format,
				request.letterhead,
				request.language,
				request.recipient_scope,
		),
		rest_arguments=request.model_dump(mode="json"),
		)
		return prepare_adapter.validate_python(result)

	@mcp.tool(
		name="confirm_document_email",
		description="Queue one server-approved prepared document email through Frappe.",
		meta=tool_meta("confirm_document_email"),
		structured_output=True,
	)
	def confirm_document_email(request: DocumentEmailConfirmInput, ctx: Context) -> DocumentEmailConfirmOutput:
		result = execute_tool_with_context(
			ctx,
		"confirm_document_email",
		lambda: email_service.confirm_document_email(request.approval_token, profile),
		rest_arguments=request.model_dump(mode="json"),
		)
		return confirm_adapter.validate_python(result)
