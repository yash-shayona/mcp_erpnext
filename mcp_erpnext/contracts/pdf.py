"""Typed contracts for generic existing-document PDF rendering."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, RootModel

from .common import NonEmptyString, PublicContractModel, ToolError


DocumentPdfDoctype = Literal["Quotation", "Sales Order", "Purchase Order"]


class RenderDocumentPdfInput(PublicContractModel):
	"""Request one permission-checked PDF for an exact existing document."""

	doctype: DocumentPdfDoctype
	name: NonEmptyString
	print_format: NonEmptyString | None = None
	letterhead: NonEmptyString | None = None
	language: NonEmptyString | None = None


class RenderDocumentPdfOk(PublicContractModel):
	status: Literal["ok"]
	doctype: DocumentPdfDoctype
	name: NonEmptyString
	print_format_used: NonEmptyString
	filename: NonEmptyString
	mime_type: Literal["application/pdf"]
	artifact_uri: NonEmptyString
	size_bytes: Annotated[int, Field(ge=0)]


class RenderDocumentPdfNotFound(PublicContractModel):
	status: Literal["not_found"]
	doctype: DocumentPdfDoctype
	name: NonEmptyString


RenderDocumentPdfResult = Annotated[
	RenderDocumentPdfOk | RenderDocumentPdfNotFound | ToolError,
	Field(discriminator="status"),
]


class RenderDocumentPdfOutput(RootModel[RenderDocumentPdfResult]):
	"""Structured metadata paired with the embedded PDF resource."""

	model_config = {"json_schema_extra": {"type": "object"}}
