"""Explicit public contracts for standalone Sales Order creation."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BeforeValidator, ConfigDict, Field, RootModel

from ..common import CustomerReference, ItemReference, NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


def _reject_boolean(value: object) -> object:
	"""Keep the service rule that booleans are not numeric quantities."""
	if isinstance(value, bool):
		raise ValueError("Boolean values are not valid quantities.")
	return value


PositiveQuantity = Annotated[float, Field(gt=0), BeforeValidator(_reject_boolean)]


class SalesOrderItemInput(PublicContractModel):
	"""One resolved Item reference and its positive quantity."""

	item: ItemReference
	qty: PositiveQuantity

	def to_service_payload(self) -> dict[str, object]:
		"""Pass only the existing service's name-based row shape downstream."""
		return {"item": self.item.name, "qty": self.qty}


class SalesOrderPrepareInput(PublicContractModel):
	"""Narrow Sales Order inputs; ERPNext calculates commercial values."""

	customer: CustomerReference
	items: list[SalesOrderItemInput]
	company: NonEmptyString | None = None
	delivery_date: date | None = None
	selling_price_list: NonEmptyString | None = None


class SalesOrderPreviewItem(PublicContractModel):
	item_code: NonEmptyString
	item_name: NonEmptyString | None = None
	qty: float
	uom: NonEmptyString | None = None
	rate: float | None = None
	amount: float | None = None
	warehouse: NonEmptyString | None = None
	delivery_date: date | None = None


class SalesOrderPreview(PublicContractModel):
	customer: NonEmptyString
	customer_name: NonEmptyString
	company: NonEmptyString
	order_type: NonEmptyString
	transaction_date: date
	delivery_date: date
	currency: NonEmptyString
	selling_price_list: NonEmptyString
	items: list[SalesOrderPreviewItem]
	grand_total: float


class SalesOrderCorrections(PublicContractModel):
	customer: bool
	items: list[NonEmptyString]


class SalesOrderReady(PublicContractModel):
	status: Literal["ready"]
	approval_token: Annotated[
		NonEmptyString,
		Field(description="Opaque pending-operation handle; it is not proof of approval."),
	]
	expires_in_seconds: Annotated[int, Field(gt=0)]
	corrections: SalesOrderCorrections
	preview: SalesOrderPreview
	interaction: InteractionDirective


class SalesOrderMissingQuantity(PublicContractModel):
	index: int
	item_code: NonEmptyString
	item_name: NonEmptyString | None = None


class SalesOrderResolvedItem(PublicContractModel):
	item_code: NonEmptyString
	item_name: NonEmptyString | None = None
	qty: float | None = None
	match_type: NonEmptyString | None = None


class SalesOrderNeedsInput(PublicContractModel):
	status: Literal["needs_input"]
	missing: list[NonEmptyString] = Field(default_factory=list)
	missing_quantities: list[SalesOrderMissingQuantity] = Field(default_factory=list)
	items: list[SalesOrderResolvedItem] = Field(default_factory=list)
	message: NonEmptyString | None = None
	interaction: InteractionDirective


class SalesOrderResolutionCandidate(PublicContractModel):
	value: NonEmptyString
	label: NonEmptyString | None = None
	score: float | None = None
	item_code: NonEmptyString | None = None
	item_name: NonEmptyString | None = None


class SalesOrderAmbiguous(PublicContractModel):
	status: Literal["ambiguous"]
	field: NonEmptyString
	query: NonEmptyString
	candidates: list[SalesOrderResolutionCandidate]


class SalesOrderNotFound(PublicContractModel):
	status: Literal["not_found"]
	field: NonEmptyString
	query: NonEmptyString
	candidates: list[SalesOrderResolutionCandidate]


class SalesOrderError(PublicContractModel):
	"""Preserve both public errors and the service's resolution-error shape."""

	status: Literal["error"]
	code: NonEmptyString | None = None
	message: NonEmptyString | None = None
	reference: NonEmptyString | None = None
	retryable: bool = False
	field: NonEmptyString | None = None
	query: NonEmptyString | None = None
	candidates: list[SalesOrderResolutionCandidate] = Field(default_factory=list)


SalesOrderPrepareResult = Annotated[
	SalesOrderReady
	| SalesOrderNeedsInput
	| SalesOrderAmbiguous
	| SalesOrderNotFound
	| SalesOrderError,
	Field(discriminator="status"),
]


class PrepareSalesOrderOutput(RootModel[SalesOrderPrepareResult]):
	"""Root-shaped typed output for Sales Order preparation."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})


class SalesOrderConfirmInput(PublicContractModel):
	approval_token: NonEmptyString
	confirm: bool


class SalesOrderCreated(PublicContractModel):
	status: Literal["created"]
	sales_order: NonEmptyString
	docstatus: int


SalesOrderConfirmResult = Annotated[
	SalesOrderCreated | ToolError,
	Field(discriminator="status"),
]


class ConfirmSalesOrderOutput(RootModel[SalesOrderConfirmResult]):
	"""Root-shaped typed output for Sales Order confirmation."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})
