"""Typed public contracts for generic prepared document email."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, RootModel, StringConstraints

from .common import NonEmptyString, PublicContractModel, ToolError
from .interaction import InteractionDirective


DocumentEmailDoctype = Literal["Quotation", "Sales Order", "Purchase Order", "Sales Invoice", "Delivery Note"]
DocumentEmailRecipientScope = Literal["party", "self"]
EmailSubject = Annotated[str, StringConstraints(min_length=1, max_length=255)]
EmailMessage = Annotated[str, StringConstraints(min_length=1, max_length=10_000)]


class DocumentEmailPrepareInput(PublicContractModel):
	"""Request one exact, permission-checked document email preview."""

	doctype: DocumentEmailDoctype
	name: NonEmptyString
	recipient_email: NonEmptyString | None = None
	recipient_scope: DocumentEmailRecipientScope = "party"
	subject: EmailSubject | None = None
	message: EmailMessage | None = None
	print_format: NonEmptyString | None = None
	letterhead: NonEmptyString | None = None
	language: NonEmptyString | None = None


class DocumentEmailConfirmInput(PublicContractModel):
	"""Confirm only a server-held, trusted prepared email operation."""

	approval_token: NonEmptyString


class DocumentEmailCandidate(PublicContractModel):
	"""Minimal recipient choice data; unrelated Contact fields stay private."""

	email: NonEmptyString
	label: NonEmptyString | None = None


class DocumentEmailPreview(PublicContractModel):
	"""The exact human-reviewable content bound to the approval token."""

	doctype: DocumentEmailDoctype
	name: NonEmptyString
	recipient: NonEmptyString
	recipient_scope: DocumentEmailRecipientScope
	subject: NonEmptyString
	message: NonEmptyString
	attachment_filename: NonEmptyString
	print_format_used: NonEmptyString
	mime_type: Literal["application/pdf"]


class DocumentEmailReady(PublicContractModel):
	status: Literal["ready_for_approval"]
	preview: DocumentEmailPreview
	approval_token: NonEmptyString
	expires_in_seconds: Annotated[int, Field(gt=0)]
	interaction: InteractionDirective


class DocumentEmailNeedsInput(PublicContractModel):
	status: Literal["needs_input"]
	doctype: DocumentEmailDoctype
	name: NonEmptyString
	candidates: list[DocumentEmailCandidate] = Field(min_length=1)
	message: NonEmptyString
	interaction: InteractionDirective


class DocumentEmailNotFound(PublicContractModel):
	status: Literal["not_found"]
	doctype: DocumentEmailDoctype
	name: NonEmptyString


DocumentEmailPrepareResult = Annotated[
	DocumentEmailReady | DocumentEmailNeedsInput | DocumentEmailNotFound | ToolError,
	Field(discriminator="status"),
]


class DocumentEmailPrepareOutput(RootModel[DocumentEmailPrepareResult]):
	"""Structured prepare result with explicit terminal states."""

	model_config = {"json_schema_extra": {"type": "object"}}


class DocumentEmailQueued(PublicContractModel):
	status: Literal["queued"]
	doctype: DocumentEmailDoctype
	name: NonEmptyString
	recipient: NonEmptyString
	queue_reference: NonEmptyString | None = None
	message: NonEmptyString


DocumentEmailConfirmResult = Annotated[
	DocumentEmailQueued | ToolError,
	Field(discriminator="status"),
]


class DocumentEmailConfirmOutput(RootModel[DocumentEmailConfirmResult]):
	"""Structured confirmation result; queued is not delivery confirmation."""

	model_config = {"json_schema_extra": {"type": "object"}}
