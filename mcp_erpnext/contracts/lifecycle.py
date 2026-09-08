"""Typed public contracts for existing-document lifecycle operations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .common import NonEmptyString, PublicContractModel
from .interaction import InteractionDirective


class LifecycleTarget(PublicContractModel):
	doctype: NonEmptyString
	name: NonEmptyString


class ChildRowSelector(PublicContractModel):
	"""Stable child-row identity; exactly one selector is required by the service."""
	row_name: NonEmptyString | None = None
	item_code: NonEmptyString | None = None
	idx: int | None = Field(default=None, ge=1)


class LifecycleChange(PublicContractModel):
	field: NonEmptyString
	value: Any
	child_table: NonEmptyString | None = None
	row: ChildRowSelector | None = None


class PrepareUpdateInput(PublicContractModel):
	target: LifecycleTarget
	changes: list[LifecycleChange] = Field(min_length=1)


class LifecycleConfirmInput(PublicContractModel):
	approval_token: NonEmptyString
	confirm: bool


class LifecycleResult(PublicContractModel):
	status: NonEmptyString
	code: NonEmptyString | None = None
	message: NonEmptyString | None = None
	reference: NonEmptyString | None = None
	retryable: bool = False
	approval_token: NonEmptyString | None = None
	expires_in_seconds: int | None = None
	preview: dict[str, Any] | None = None
	document: dict[str, Any] | None = None
	blockers: list[dict[str, Any]] | None = None
	interaction: InteractionDirective | None = None


class PrepareActionInput(PublicContractModel):
	target: LifecycleTarget


class PrepareDeleteInput(PublicContractModel):
	target: LifecycleTarget


LifecycleAction = Literal["update", "submit", "cancel", "delete"]
