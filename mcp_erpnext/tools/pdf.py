"""Profile-scoped MCP wrapper for generic document PDF rendering."""

from __future__ import annotations

import base64
import json
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, TextContent
from pydantic import TypeAdapter

from ..contracts.common import NonEmptyString
from ..contracts.pdf import (
	DocumentPdfDoctype,
	RenderDocumentPdfInput,
	RenderDocumentPdfOutput,
	RenderDocumentPdfResult,
)
from ..contracts.registry import tool_meta
from ..runtime import execute_tool_with_context
from ..services.common import pdf as pdf_service


_result_adapter = TypeAdapter(RenderDocumentPdfResult)


def _call_tool_result(result: dict[str, Any]) -> CallToolResult:
	pdf = result.pop("_pdf", None)
	validated = _result_adapter.validate_python(result)
	structured = RenderDocumentPdfOutput(root=validated).model_dump(mode="json")

	if pdf is None:
		content = [TextContent(type="text", text=json.dumps(structured))]
	else:
		content = [
			EmbeddedResource(
				type="resource",
				resource=BlobResourceContents(
					uri=structured["artifact_uri"],
					mimeType=structured["mime_type"],
					blob=base64.b64encode(pdf).decode("ascii"),
				),
			)
		]

	return CallToolResult(content=content, structuredContent=structured)


def register_document_pdf_tools(mcp: Any, profile: str) -> None:
	"""Register the same generic PDF capability in the selected profile."""

	@mcp.tool(
		name="render_document_pdf",
		description="Render a permitted existing transactional document as a PDF artifact.",
		meta=tool_meta("render_document_pdf"),
		structured_output=True,
	)
	def render_document_pdf(
		doctype: DocumentPdfDoctype,
		name: NonEmptyString,
		ctx: Context,
		print_format: NonEmptyString | None = None,
		letterhead: NonEmptyString | None = None,
		language: NonEmptyString | None = None,
	) -> Annotated[CallToolResult, RenderDocumentPdfOutput]:
		request = RenderDocumentPdfInput(
			doctype=doctype,
			name=name,
			print_format=print_format,
			letterhead=letterhead,
			language=language,
		)
		result = execute_tool_with_context(
			ctx,
			"render_document_pdf",
			lambda: pdf_service.render_document_pdf(
				request.doctype,
				request.name,
				profile,
				request.print_format,
				request.letterhead,
				request.language,
			),
			rest_arguments=request.model_dump(mode="json"),
		)
		return _call_tool_result(result)
