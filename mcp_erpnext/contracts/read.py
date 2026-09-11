"""Typed public contracts for safe existing-document reads."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, RootModel

from .common import NonEmptyString, PublicContractModel, ToolError


DocumentDoctype = Literal["Quotation", "Sales Order", "Purchase Order", "Sales Invoice"]


class ExistingDocumentTarget(PublicContractModel):
	doctype: DocumentDoctype
	name: NonEmptyString


class DocumentReadInput(PublicContractModel):
	target: ExistingDocumentTarget


class DocumentSearchInput(PublicContractModel):
	name: NonEmptyString | None = None
	party: NonEmptyString | None = Field(default=None, description="Exact Customer or Supplier document name.")
	docstatus: Annotated[int, Field(ge=0, le=2)] | None = None
	status: NonEmptyString | None = None
	date_from: date | None = None
	date_to: date | None = None
	limit: Annotated[int, Field(ge=1, le=50)] = 20


class DocumentSummary(PublicContractModel):
	doctype: DocumentDoctype
	name: NonEmptyString
	docstatus: int
	status: str | None = None
	party: str | None = None
	transaction_date: date | None = None
	secondary_date: date | None = None
	currency: str | None = None
	grand_total: float | None = None
	items: list[dict[str, object]] | None = None


class DocumentReadOk(PublicContractModel):
	status: Literal["ok"]
	document: DocumentSummary


class DocumentNotFound(PublicContractModel):
	status: Literal["not_found"]
	doctype: DocumentDoctype
	name: NonEmptyString


DocumentReadResult = Annotated[DocumentReadOk | DocumentNotFound | ToolError, Field(discriminator="status")]


class DocumentReadOutput(RootModel[DocumentReadResult]):
	model_config = {"json_schema_extra": {"type": "object"}}


class DocumentSearchOk(PublicContractModel):
	status: Literal["ok"]
	doctype: DocumentDoctype
	results: list[DocumentSummary]
	count: int
	limit: int


class DocumentSearchOutput(RootModel[Annotated[DocumentSearchOk | ToolError, Field(discriminator="status")]]):
	model_config = {"json_schema_extra": {"type": "object"}}
