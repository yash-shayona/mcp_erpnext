"""Explicit public contracts for the controlled Item creation workflow."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


ScalarValue = str | int | float | bool


class ItemPrepareInput(PublicContractModel):
	"""Bounded sales-Item fields; effective runtime requirements remain server-owned."""

	item_code: NonEmptyString | None = None
	item_name: NonEmptyString | None = None
	item_group: NonEmptyString | None = None
	stock_uom: NonEmptyString | None = None
	is_stock_item: bool | None = None
	# The capability is sales-only. Literal True documents the policy without
	# allowing callers to weaken it; the service remains authoritative.
	is_sales_item: Literal[True] = True
	gst_hsn_code: NonEmptyString | None = None

	def to_service_payload(self) -> dict[str, object]:
		"""Convert the typed request to the existing narrow service payload."""
		payload = self.model_dump(exclude_none=True)
		# is_sales_item is deliberately controlled by item service POLICY_VALUES.
		payload.pop("is_sales_item", None)
		return payload


class ItemPreview(PublicContractModel):
	item_code: NonEmptyString
	item_name: NonEmptyString
	item_group: NonEmptyString
	stock_uom: NonEmptyString
	is_stock_item: bool | int | None = None
	is_sales_item: Literal[True]


class ItemReady(PublicContractModel):
	status: Literal["ready"]
	approval_token: Annotated[
		NonEmptyString,
		Field(description="Opaque pending-operation handle; it is not proof of approval."),
	]
	expires_in_seconds: Annotated[int, Field(gt=0)]
	preview: ItemPreview
	interaction: InteractionDirective


class ItemMissingField(PublicContractModel):
	doctype: Literal["Item"]
	fieldname: NonEmptyString
	path: NonEmptyString
	label: NonEmptyString
	fieldtype: NonEmptyString
	reason: NonEmptyString
	source: NonEmptyString


class ItemNeedsInput(PublicContractModel):
	status: Literal["needs_input"]
	missing: list[NonEmptyString]
	missing_fields: list[ItemMissingField] = Field(default_factory=list)
	message: NonEmptyString | None = None
	interaction: InteractionDirective


class ItemFieldCandidate(PublicContractModel):
	value: NonEmptyString
	label: NonEmptyString | None = None
	score: float | None = None


class ItemDuplicateCandidate(PublicContractModel):
	value: NonEmptyString
	label: NonEmptyString | None = None
	item_code: NonEmptyString | None = None
	item_name: NonEmptyString | None = None
	stock_uom: NonEmptyString | None = None
	disabled: bool | int | None = None


class ItemDuplicateGroup(PublicContractModel):
	identifier: NonEmptyString
	candidates: list[ItemDuplicateCandidate]


class ItemDuplicateSuspected(PublicContractModel):
	status: Literal["duplicate_suspected"]
	duplicates: list[ItemDuplicateGroup]


class ItemPermissionDenied(PublicContractModel):
	status: Literal["permission_denied"]
	missing_permissions: list[Literal["Item"]]
	message: NonEmptyString


class ItemNeedsSelection(PublicContractModel):
	status: Literal["needs_selection"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	query: NonEmptyString
	target_doctype: NonEmptyString | None = None
	candidates: list[ItemFieldCandidate]
	interaction: InteractionDirective


class ItemNotFound(PublicContractModel):
	status: Literal["not_found"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	query: NonEmptyString
	target_doctype: NonEmptyString | None = None
	candidates: list[ItemFieldCandidate]


class ItemInvalidValue(PublicContractModel):
	status: Literal["invalid_value"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	input: ScalarValue | None = None
	allowed_values: list[NonEmptyString] = Field(default_factory=list)
	category: NonEmptyString | None = None


class ItemUnsupportedField(PublicContractModel):
	status: Literal["unsupported_field"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	input: ScalarValue | None = None
	category: NonEmptyString


class ItemUnresolvedDependency(PublicContractModel):
	status: Literal["unresolved_dependency"]
	path: NonEmptyString
	fieldname: NonEmptyString
	fieldtype: NonEmptyString
	source: NonEmptyString
	input: ScalarValue | None = None
	controller_field: NonEmptyString | None = None


ItemPrepareResult = Annotated[
	ItemReady
	| ItemNeedsInput
	| ItemNeedsSelection
	| ItemNotFound
	| ItemInvalidValue
	| ItemUnsupportedField
	| ItemUnresolvedDependency
	| ItemPermissionDenied
	| ItemDuplicateSuspected
	| ToolError,
	Field(discriminator="status"),
]


class PrepareItemOutput(RootModel[ItemPrepareResult]):
	"""Root-shaped typed output for Item preparation."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})


class ItemConfirmInput(PublicContractModel):
	approval_token: NonEmptyString
	confirm: bool


class ItemCreatedReference(PublicContractModel):
	doctype: Literal["Item"]
	name: NonEmptyString
	item_code: NonEmptyString
	item_name: NonEmptyString
	stock_uom: NonEmptyString


class ItemCreated(PublicContractModel):
	status: Literal["created"]
	item: ItemCreatedReference
	idempotent: bool


ItemConfirmResult = Annotated[
	ItemCreated | ItemPermissionDenied | ItemDuplicateSuspected | ToolError,
	Field(discriminator="status"),
]


class ConfirmItemOutput(RootModel[ItemConfirmResult]):
	"""Root-shaped typed output for Item confirmation."""

	model_config = ConfigDict(json_schema_extra={"type": "object"})
