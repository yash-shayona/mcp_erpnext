"""Typed contracts for the bounded Customer-linked Contact capability."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import CustomerReference, NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


ContactMatch = Literal["auto", "name", "email", "phone"]


class ContactReference(PublicContractModel):
	"""An explicitly selected native Contact."""

	doctype: Literal["Contact"]
	name: NonEmptyString


class ContactSearchInput(PublicContractModel):
	"""Bounded Contact search input; customer context narrows fuzzy lookup."""

	query: NonEmptyString
	customer: CustomerReference | None = None
	match: ContactMatch = "auto"
	limit: Annotated[int, Field(ge=1, le=50)] = 20
	offset: Annotated[int, Field(ge=0)] = 0


class ContactProjection(PublicContractModel):
	"""The minimum Contact data needed for selection and approved results."""

	doctype: Literal["Contact"]
	name: NonEmptyString
	full_name: NonEmptyString
	company_name: NonEmptyString | None = None
	email_id: NonEmptyString | None = None
	mobile_no: NonEmptyString | None = None
	phone: NonEmptyString | None = None
	is_primary_contact: bool
	linked_to_target_customer: bool = False
	other_party_link_count: Annotated[int, Field(ge=0)]


class ContactSearchResult(PublicContractModel):
	status: Literal["ok"]
	doctype: Literal["Contact"]
	query: NonEmptyString
	contacts: list[ContactProjection]
	count: Annotated[int, Field(ge=0)]
	limit: Annotated[int, Field(ge=1, le=50)]
	offset: Annotated[int, Field(ge=0)]
	interaction: InteractionDirective | None = None


ContactSearchResultContract = Annotated[
	ContactSearchResult | ToolError,
	Field(discriminator="status"),
]


class ContactSearchOutput(RootModel[ContactSearchResultContract]):
	"""Root-shaped typed output for Contact search."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})


class NewContactInput(PublicContractModel):
	"""The only identity and communication fields accepted for a new Contact."""

	first_name: NonEmptyString | None = None
	middle_name: NonEmptyString | None = None
	last_name: NonEmptyString | None = None
	company_name: NonEmptyString | None = None
	email: NonEmptyString | None = None
	mobile: NonEmptyString | None = None


class CustomerContactPrepareInput(PublicContractModel):
	"""One explicit create-or-link Customer Contact intent."""

	customer: CustomerReference
	mode: Literal["create", "link"]
	existing_contact: ContactReference | None = None
	new_contact: NewContactInput | None = None
	make_primary: bool = False


class CustomerContactPreview(PublicContractModel):
	action: Literal["create", "link"]
	customer: CustomerReference
	customer_name: NonEmptyString
	contact: ContactProjection | None = None
	new_contact: NewContactInput | None = None
	already_linked: bool = False
	make_primary: bool = False


class CustomerContactReady(PublicContractModel):
	status: Literal["ready"]
	approval_token: Annotated[
		NonEmptyString,
		Field(description="Opaque pending-operation handle; it is not proof of approval."),
	]
	expires_in_seconds: Annotated[int, Field(gt=0)]
	preview: CustomerContactPreview
	interaction: InteractionDirective


CustomerContactPrepareResult = Annotated[
	CustomerContactReady | ToolError,
	Field(discriminator="status"),
]


class PrepareCustomerContactOutput(RootModel[CustomerContactPrepareResult]):
	"""Root-shaped typed output for Customer Contact preparation."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})


class CustomerContactConfirmInput(PublicContractModel):
	"""Requested execution of a pending Customer Contact operation."""

	approval_token: NonEmptyString
	confirm: bool


class CustomerContactPrimaryResult(PublicContractModel):
	requested: bool
	applied: bool
	customer_primary_contact_updated: bool


class CustomerContactCreated(PublicContractModel):
	status: Literal["created"]
	customer: CustomerReference
	contact: ContactProjection
	idempotent: Literal[False] = False
	primary: CustomerContactPrimaryResult


class CustomerContactLinked(PublicContractModel):
	status: Literal["linked"]
	customer: CustomerReference
	contact: ContactProjection
	idempotent: bool
	primary: None = None


CustomerContactConfirmResult = Annotated[
	CustomerContactCreated | CustomerContactLinked | ToolError,
	Field(discriminator="status"),
]


class ConfirmCustomerContactOutput(RootModel[CustomerContactConfirmResult]):
	"""Root-shaped typed output for Customer Contact confirmation."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})
