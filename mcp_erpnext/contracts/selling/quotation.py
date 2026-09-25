"""Explicit public contracts for the controlled Quotation MCP workflow."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BeforeValidator, ConfigDict, Field, RootModel

from ..common import CustomerReference, ItemReference, NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective



def _reject_boolean(value: object) -> object:
	"""Keep the existing service rule that booleans are not numeric amounts."""
	if isinstance(value, bool):
		raise ValueError("Boolean values are not valid numbers.")
	return value


PositiveNumber = Annotated[float, Field(gt=0), BeforeValidator(_reject_boolean)]
NonNegativeNumber = Annotated[float, Field(ge=0), BeforeValidator(_reject_boolean)]


class QuotationItemInput(PublicContractModel):
	"""One resolved Item row for a Quotation preview."""

	item: ItemReference
	qty: PositiveNumber
	rate: NonNegativeNumber | None = None
	discount_percentage: NonNegativeNumber | None = None
	discount_amount: NonNegativeNumber | None = None
	description: str | None = None

	def to_service_payload(self) -> dict[str, object]:
		"""Preserve the existing service's internal row shape."""
		return {
			"item": self.item.model_dump(),
			"qty": self.qty,
			**({"rate": self.rate} if self.rate is not None else {}),
			**(
				{"discount_percentage": self.discount_percentage}
				if self.discount_percentage is not None
				else {}
			),
			**({"discount_amount": self.discount_amount} if self.discount_amount is not None else {}),
			**({"description": self.description} if self.description is not None else {}),
		}


QuotationItems = list[QuotationItemInput]


class QuotationPrepareInput(PublicContractModel):
	"""Public, non-persistent Quotation preparation request."""

	customer: CustomerReference
	items: QuotationItems
	valid_till: date | None = None
	company: NonEmptyString | None = None
	transaction_date: date | None = None
	selling_price_list: NonEmptyString | None = None
	taxes_and_charges: NonEmptyString | None = None
	additional_discount_percentage: NonNegativeNumber | None = None
	discount_amount: NonNegativeNumber | None = None
	tc_name: NonEmptyString | None = None


class QuotationPreviewCustomer(PublicContractModel):
	doctype: Literal["Customer"]
	name: NonEmptyString
	customer_name: str | None = None


class QuotationPreviewItem(PublicContractModel):
	item_code: NonEmptyString
	item_name: str | None = None
	description: str | None = None
	qty: float
	uom: str | None = None
	rate: float | None = None
	discount_percentage: float | None = None
	discount_amount: float | None = None
	amount: float | None = None
	net_amount: float | None = None


class QuotationPreviewTax(PublicContractModel):
	charge_type: str | None = None
	account_head: str | None = None
	rate: float | None = None
	tax_amount: float | None = None
	total: float | None = None


class QuotationPreview(PublicContractModel):
	customer: QuotationPreviewCustomer
	company: NonEmptyString
	transaction_date: date
	valid_till: date
	currency: NonEmptyString
	selling_price_list: NonEmptyString
	items: list[QuotationPreviewItem]
	taxes: list[QuotationPreviewTax]
	net_total: float
	total_taxes_and_charges: float
	additional_discount_percentage: float
	discount_amount: float
	grand_total: float
	tc_name: str | None = None
	terms: str | None = None


class QuotationReady(PublicContractModel):
	status: Literal["ready"]
	approval_token: Annotated[
		NonEmptyString,
		Field(description="Opaque pending-operation handle; it is not proof of user approval."),
	]
	expires_in_seconds: Annotated[int, Field(gt=0)]
	preview: QuotationPreview
	interaction: InteractionDirective


class QuotationNeedsInput(PublicContractModel):
	status: Literal["needs_input"]
	missing: list[NonEmptyString]
	message: str | None = None
	interaction: InteractionDirective


class QuotationPermissionDenied(PublicContractModel):
	status: Literal["permission_denied"]
	missing_permissions: list[Literal["Quotation"]]
	message: NonEmptyString


PrepareQuotationResult = Annotated[
	QuotationReady | QuotationNeedsInput | QuotationPermissionDenied | ToolError,
	Field(discriminator="status"),
]


class PrepareQuotationOutput(RootModel[PrepareQuotationResult]):
	"""Root-shaped output preserving the existing prepare result payload."""

	# LibreChat's MCP SDK requires every tool output schema to declare an object root.
	# Every discriminated result variant is an object, so this preserves the root payload.
	model_config = ConfigDict(json_schema_extra={"type": "object"})


class QuotationConfirmInput(PublicContractModel):
	"""Requested execution for a pending Quotation operation, never an approval grant."""

	approval_token: NonEmptyString
	confirm: Annotated[
		bool,
		Field(description="Requested confirmation step only; the server enforces its configured approval policy."),
	]


class QuotationCreated(PublicContractModel):
	status: Literal["created"]
	quotation: NonEmptyString
	docstatus: int
	idempotent: bool


ConfirmQuotationResult = Annotated[
	QuotationCreated | QuotationPermissionDenied | ToolError,
	Field(discriminator="status"),
]


class ConfirmQuotationOutput(RootModel[ConfirmQuotationResult]):
	"""Root-shaped output preserving the existing confirm result payload."""

	# Keep the existing root response while producing a LibreChat-compatible schema.
	model_config = ConfigDict(json_schema_extra={"type": "object"})
