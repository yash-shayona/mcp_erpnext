"""Explicit public contracts for the controlled Customer creation workflow."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


ScalarValue = str | int | float | bool


class CustomerContactInput(PublicContractModel):
	"""The narrow Contact fields accepted by Customer creation."""

	first_name: NonEmptyString | None = None
	last_name: NonEmptyString | None = None
	email: NonEmptyString | None = None
	mobile: NonEmptyString | None = None


class CustomerAddressInput(PublicContractModel):
	"""The narrow Address fields accepted by Customer creation."""

	address_line1: NonEmptyString | None = None
	address_line2: NonEmptyString | None = None
	city: NonEmptyString | None = None
	state: NonEmptyString | None = None
	pincode: NonEmptyString | None = None
	country: NonEmptyString | None = None


class CustomerPrepareInput(PublicContractModel):
	"""Bounded Customer fields; runtime metadata decides mandatory/default state."""

	customer_name: NonEmptyString | None = None
	customer_type: NonEmptyString | None = None
	customer_group: NonEmptyString | None = None
	territory: NonEmptyString | None = None
	tax_id: NonEmptyString | None = None
	gstin: NonEmptyString | None = None
	gst_category: NonEmptyString | None = None
	contact: CustomerContactInput | None = None
	address: CustomerAddressInput | None = None

	def to_service_payload(self) -> dict[str, object]:
		"""Convert public nested names to the existing service payload shape."""
		payload = self.model_dump(exclude_none=True)
		contact = payload.pop("contact", None)
		address = payload.pop("address", None)
		if contact is not None:
			payload["contact"] = contact
		if address is not None:
			payload["address"] = address
		return payload


class CustomerPreviewContact(PublicContractModel):
	first_name: NonEmptyString | None = None
	last_name: NonEmptyString | None = None
	email_id: NonEmptyString | None = None
	mobile_no: NonEmptyString | None = None


class CustomerPreviewAddress(PublicContractModel):
	address_line1: NonEmptyString | None = None
	address_line2: NonEmptyString | None = None
	city: NonEmptyString | None = None
	state: NonEmptyString | None = None
	pincode: NonEmptyString | None = None
	country: NonEmptyString | None = None


class CustomerPreview(PublicContractModel):
	customer_name: NonEmptyString
	customer_type: NonEmptyString
	customer_group: NonEmptyString | None = None
	territory: NonEmptyString | None = None
	contact: CustomerPreviewContact
	address: CustomerPreviewAddress
	gstin: NonEmptyString | None = None
	gst_category: NonEmptyString | None = None


class CustomerReady(PublicContractModel):
	status: Literal["ready"]
	approval_token: Annotated[
		NonEmptyString,
		Field(description="Opaque pending-operation handle; it is not proof of approval."),
	]
	expires_in_seconds: Annotated[int, Field(gt=0)]
	preview: CustomerPreview
	interaction: InteractionDirective


class CustomerMissingField(PublicContractModel):
	doctype: Literal["Customer"]
	fieldname: NonEmptyString
	path: NonEmptyString
	label: NonEmptyString
	fieldtype: NonEmptyString
	reason: NonEmptyString
	source: NonEmptyString


class CustomerNeedsInput(PublicContractModel):
	status: Literal["needs_input"]
	missing: list[NonEmptyString]
	missing_fields: list[CustomerMissingField] = Field(default_factory=list)
	message: NonEmptyString | None = None
	interaction: InteractionDirective


class CustomerFieldCandidate(PublicContractModel):
	value: NonEmptyString
	label: NonEmptyString | None = None
	score: float | None = None


class CustomerDuplicateCandidate(PublicContractModel):
	value: NonEmptyString
	label: NonEmptyString | None = None
	customer_name: NonEmptyString | None = None
	customer_group: NonEmptyString | None = None
	territory: NonEmptyString | None = None


class CustomerDuplicateGroup(PublicContractModel):
	identifier: NonEmptyString
	candidates: list[CustomerDuplicateCandidate]


class CustomerDuplicateSuspected(PublicContractModel):
	status: Literal["duplicate_suspected"]
	duplicates: list[CustomerDuplicateGroup]


class CustomerPermissionDenied(PublicContractModel):
	status: Literal["permission_denied"]
	missing_permissions: list[Literal["Customer", "Contact", "Address"]]
	message: NonEmptyString


class CustomerNeedsSelection(PublicContractModel):
	status: Literal["needs_selection"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	query: NonEmptyString
	target_doctype: NonEmptyString | None = None
	candidates: list[CustomerFieldCandidate]
	interaction: InteractionDirective


class CustomerNotFound(PublicContractModel):
	status: Literal["not_found"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	query: NonEmptyString
	target_doctype: NonEmptyString | None = None
	candidates: list[CustomerFieldCandidate]


class CustomerInvalidValue(PublicContractModel):
	status: Literal["invalid_value"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	input: ScalarValue | None = None
	allowed_values: list[NonEmptyString] = Field(default_factory=list)
	category: NonEmptyString | None = None


class CustomerUnsupportedField(PublicContractModel):
	status: Literal["unsupported_field"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	input: ScalarValue | None = None
	category: NonEmptyString


class CustomerUnresolvedDependency(PublicContractModel):
	status: Literal["unresolved_dependency"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	input: ScalarValue | None = None
	controller_field: NonEmptyString | None = None


CustomerPrepareResult = Annotated[
	CustomerReady
	| CustomerNeedsInput
	| CustomerNeedsSelection
	| CustomerNotFound
	| CustomerInvalidValue
	| CustomerUnsupportedField
	| CustomerUnresolvedDependency
	| CustomerPermissionDenied
	| CustomerDuplicateSuspected
	| ToolError,
	Field(discriminator="status"),
]


class PrepareCustomerOutput(RootModel[CustomerPrepareResult]):
	"""Root-shaped typed output for Customer preparation."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})


class CustomerConfirmInput(PublicContractModel):
	"""Requested execution of a pending Customer operation, never an approval grant."""

	approval_token: NonEmptyString
	confirm: bool


class CustomerCreatedReference(PublicContractModel):
	doctype: Literal["Customer"]
	name: NonEmptyString
	customer_name: NonEmptyString


class CustomerCreated(PublicContractModel):
	status: Literal["created"]
	customer: CustomerCreatedReference
	idempotent: bool


CustomerConfirmResult = Annotated[
	CustomerCreated | CustomerPermissionDenied | CustomerDuplicateSuspected | ToolError,
	Field(discriminator="status"),
]


class ConfirmCustomerOutput(RootModel[CustomerConfirmResult]):
	"""Root-shaped typed output for Customer confirmation."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})
