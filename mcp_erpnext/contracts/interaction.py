"""Client-neutral semantic interaction contracts for conversational MCP workflows."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .common import NonEmptyString, PublicContractModel


class InteractionKind(StrEnum):
	"""The category of user continuation required before a workflow can proceed."""

	SELECTION = "SELECTION"
	INPUT = "INPUT"
	APPROVAL = "APPROVAL"


class InteractionAction(StrEnum):
	"""Semantic user intentions an Agent may interpret and act on."""

	SELECT = "SELECT"
	PROVIDE_INPUT = "PROVIDE_INPUT"
	MODIFY = "MODIFY"
	APPROVE = "APPROVE"
	REJECT = "REJECT"
	CANCEL = "CANCEL"


class InteractionDirective(PublicContractModel):
	"""Client-neutral guidance; it never interprets language or grants write approval."""

	required: bool
	kind: InteractionKind | None = None
	allowed_actions: list[InteractionAction] = Field(default_factory=list)
	reason_code: NonEmptyString | None = None
	instructions: NonEmptyString | None = None

	@model_validator(mode="after")
	def validate_required_shape(self) -> InteractionDirective:
		"""Keep an optional directive unambiguous for future tool consumers."""
		if self.required and (self.kind is None or not self.allowed_actions):
			raise ValueError("A required interaction needs a kind and at least one allowed action.")
		if not self.required and (self.kind is not None or self.allowed_actions):
			raise ValueError("An optional interaction cannot declare a kind or allowed actions.")
		return self


def selection_directive() -> InteractionDirective:
	"""Return the standard continuation for an ambiguous typed resolver result."""
	return InteractionDirective(
		required=True,
		kind=InteractionKind.SELECTION,
		allowed_actions=[InteractionAction.SELECT, InteractionAction.CANCEL],
		reason_code="AMBIGUOUS_REFERENCE",
		instructions="Select exactly one candidate.",
	)


def input_directive() -> InteractionDirective:
	"""Return the standard continuation for structured missing business input."""
	return InteractionDirective(
		required=True,
		kind=InteractionKind.INPUT,
		allowed_actions=[InteractionAction.PROVIDE_INPUT, InteractionAction.CANCEL],
		reason_code="MISSING_REQUIRED_INPUT",
		instructions="Provide the missing required business information.",
	)


def approval_directive() -> InteractionDirective:
	"""Return the semantic review requirement for a prepared protected operation."""
	return InteractionDirective(
		required=True,
		kind=InteractionKind.APPROVAL,
		allowed_actions=[
			InteractionAction.APPROVE,
			InteractionAction.REJECT,
			InteractionAction.MODIFY,
			InteractionAction.CANCEL,
		],
		reason_code="EXPLICIT_APPROVAL_REQUIRED",
		instructions="Review the prepared operation before final creation.",
	)
