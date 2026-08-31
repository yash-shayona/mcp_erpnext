"""Public contracts for deterministic Customer and Item resolution."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import (
	CustomerReference,
	ItemReference,
	NonEmptyString,
	PublicContractModel,
	ResolvableDoctype,
	ToolError,
)


MatchType = Literal["exact", "spelling_correction"]


class EntityResolveInput(PublicContractModel):
	"""A human-entered query for a read-only entity-resolution attempt."""

	query: NonEmptyString


class CustomerResolutionReference(CustomerReference):
	"""A selected Customer plus safe display information."""

	customer_name: str | None = None


class ItemResolutionReference(ItemReference):
	"""A selected sales Item plus safe display information."""

	item_code: str | None = None
	item_name: str | None = None
	stock_uom: str | None = None


class CustomerResolutionCandidate(PublicContractModel):
	reference: CustomerResolutionReference
	label: NonEmptyString
	score: float


class CustomerSearchResult(PublicContractModel):
	status: Literal["resolved", "ambiguous", "not_found"]
	doctype: Literal["Customer"]
	query: NonEmptyString
	candidates: list[CustomerResolutionCandidate]


CustomerSearchResultContract = Annotated[
	CustomerSearchResult | ToolError,
	Field(discriminator="status"),
]


class CustomerSearchOutput(RootModel[CustomerSearchResultContract]):
	"""Root-shaped Customer search result with selectable references."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})


class ItemResolutionCandidate(PublicContractModel):
	reference: ItemResolutionReference
	label: NonEmptyString
	score: float


class ItemSearchResult(PublicContractModel):
	status: Literal["resolved", "ambiguous", "not_found"]
	doctype: Literal["Item"]
	query: NonEmptyString
	candidates: list[ItemResolutionCandidate]


ItemSearchResultContract = Annotated[
	ItemSearchResult | ToolError,
	Field(discriminator="status"),
]


class ItemSearchOutput(RootModel[ItemSearchResultContract]):
	"""Root-shaped Item search result with selectable references."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})


class CustomerResolved(PublicContractModel):
	status: Literal["resolved"]
	doctype: Literal["Customer"]
	reference: CustomerResolutionReference
	match_type: MatchType


class CustomerAmbiguous(PublicContractModel):
	status: Literal["ambiguous"]
	doctype: Literal["Customer"]
	query: NonEmptyString
	candidates: list[CustomerResolutionCandidate]


class CustomerNotFound(PublicContractModel):
	status: Literal["not_found"]
	doctype: Literal["Customer"]
	query: NonEmptyString
	candidates: list[CustomerResolutionCandidate] = Field(default_factory=list)


CustomerResolutionResult = Annotated[
	CustomerResolved | CustomerAmbiguous | CustomerNotFound | ToolError,
	Field(discriminator="status"),
]


class CustomerResolutionOutput(RootModel[CustomerResolutionResult]):
	"""Root-shaped Customer resolution result."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})


class ItemResolved(PublicContractModel):
	status: Literal["resolved"]
	doctype: Literal["Item"]
	reference: ItemResolutionReference
	match_type: MatchType


class ItemAmbiguous(PublicContractModel):
	status: Literal["ambiguous"]
	doctype: Literal["Item"]
	query: NonEmptyString
	candidates: list[ItemResolutionCandidate]


class ItemNotFound(PublicContractModel):
	status: Literal["not_found"]
	doctype: Literal["Item"]
	query: NonEmptyString
	candidates: list[ItemResolutionCandidate] = Field(default_factory=list)


ItemResolutionResult = Annotated[
	ItemResolved | ItemAmbiguous | ItemNotFound | ToolError,
	Field(discriminator="status"),
]


class ItemResolutionOutput(RootModel[ItemResolutionResult]):
	"""Root-shaped Item resolution result."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})


class SelectedCandidateInput(PublicContractModel):
	"""A client-selected candidate reference that must be revalidated."""

	doctype: ResolvableDoctype
	name: NonEmptyString


class SelectedCandidateResolved(PublicContractModel):
	status: Literal["resolved"]
	doctype: ResolvableDoctype
	reference: CustomerReference | ItemReference
	match_type: Literal["exact"]


class SelectedCandidateNotFound(PublicContractModel):
	status: Literal["not_found"]
	doctype: ResolvableDoctype
	query: NonEmptyString
	candidates: list[CustomerResolutionCandidate | ItemResolutionCandidate] = Field(default_factory=list)


SelectResolvedCandidateResult = Annotated[
	SelectedCandidateResolved | SelectedCandidateNotFound | ToolError,
	Field(discriminator="status"),
]


class SelectResolvedCandidateOutput(RootModel[SelectResolvedCandidateResult]):
	"""Root-shaped result for stateless candidate revalidation."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})
