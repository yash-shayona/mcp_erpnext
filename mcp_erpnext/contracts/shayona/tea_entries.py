"""Bounded public contracts for Shayona Tea Entry tools."""

from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective

PositiveLimit = Annotated[int, Field(ge=1, le=100)]
NonNegativeOffset = Annotated[int, Field(ge=0)]
TeaEntrySortOrder = Literal["asc", "desc"]
TeaEntryAggregateMetric = Literal[
    "count", "sum_no_of_cups", "sum_total_amount"
]
TeaEntryAggregateGroup = Literal["date", "vendor"]


class TeaEntryMetadata(PublicContractModel):
    """Fixed public projection of one Tea Entry."""

    name: NonEmptyString
    date: Date
    no_of_cups: int | None = None
    rate_per_cup: Decimal | None = None
    total_amount: Decimal | None = None
    vendor: str | None = None


class TeaEntryGetInput(PublicContractModel):
    tea_entry_name: NonEmptyString


class TeaEntryGetOk(PublicContractModel):
    status: Literal["ok"]
    tea_entry: TeaEntryMetadata


class TeaEntryNotFound(PublicContractModel):
    status: Literal["not_found"]
    tea_entry_name: NonEmptyString


class TeaEntryGetOutput(
    RootModel[
        Annotated[
            TeaEntryGetOk | TeaEntryNotFound | ToolError,
            Field(discriminator="status"),
        ]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class TeaEntryFilters(PublicContractModel):
    date: Date | None = None
    date_from: Date | None = None
    date_to: Date | None = None
    vendor: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_date_filters(self):
        if self.date is not None and (
            self.date_from is not None or self.date_to is not None
        ):
            raise ValueError("date cannot be combined with date_from or date_to")
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("date_from must not be after date_to")
        return self


class TeaEntryQueryInput(TeaEntryFilters):
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_order: TeaEntrySortOrder = "desc"


class TeaEntryQueryOk(PublicContractModel):
    status: Literal["ok"]
    tea_entries: list[TeaEntryMetadata]
    count: int
    limit: int
    offset: int


class TeaEntryQueryOutput(
    RootModel[Annotated[TeaEntryQueryOk | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class TeaEntryAggregateInput(TeaEntryFilters):
    metrics: list[TeaEntryAggregateMetric] = Field(min_length=1, max_length=3)
    group_by: TeaEntryAggregateGroup | None = None

    @model_validator(mode="after")
    def require_unique_metrics(self):
        if len(self.metrics) != len(set(self.metrics)):
            raise ValueError("metrics must not contain duplicates")
        return self


class TeaEntryAggregateRow(PublicContractModel):
    group_value: str | Date | None = None
    count: int | None = None
    sum_no_of_cups: Decimal | None = None
    sum_total_amount: Decimal | None = None


class TeaEntryAggregateOk(PublicContractModel):
    status: Literal["ok"]
    metrics: list[TeaEntryAggregateMetric]
    group_by: TeaEntryAggregateGroup | None = None
    results: list[TeaEntryAggregateRow]


class TeaEntryAggregateOutput(
    RootModel[
        Annotated[TeaEntryAggregateOk | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}


PositiveCups = Annotated[int, Field(gt=0, strict=True)]
NonNegativeRate = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class TeaEntryCreateInput(PublicContractModel):
    no_of_cups: PositiveCups
    rate_per_cup: NonNegativeRate
    date: Date | None = None
    vendor: NonEmptyString | None = None


class TeaEntryCreatePreview(PublicContractModel):
    date: Date
    no_of_cups: PositiveCups
    rate_per_cup: NonNegativeRate
    total_amount: Decimal
    vendor: str | None = None


class TeaEntryPreviewOnly(PublicContractModel):
    status: Literal["preview"]
    preview: TeaEntryCreatePreview


class TeaEntryReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: NonEmptyString
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: TeaEntryCreatePreview
    interaction: InteractionDirective


class TeaEntryPrepareOutput(
    RootModel[Annotated[TeaEntryPreviewOnly | TeaEntryReady | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class TeaEntryConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class TeaEntryCreated(PublicContractModel):
    status: Literal["created"]
    tea_entry: TeaEntryMetadata


class TeaEntryCreateOutput(
    RootModel[Annotated[TeaEntryCreated | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class TeaEntryUpdateChanges(PublicContractModel):
    """Only the business fields supported by the Tea Entry update workflow."""

    date: Date | None = None
    no_of_cups: PositiveCups | None = None
    rate_per_cup: NonNegativeRate | None = None
    vendor: NonEmptyString | None = None

    @model_validator(mode="after")
    def require_non_empty_changes(self):
        fields = self.model_fields_set
        if not fields:
            raise ValueError("at least one Tea Entry change is required")
        if any(getattr(self, field) is None for field in fields):
            raise ValueError("Tea Entry changes cannot be null")
        return self


class TeaEntryUpdateInput(PublicContractModel):
    tea_entry_name: NonEmptyString
    changes: TeaEntryUpdateChanges


class TeaEntryUpdateState(PublicContractModel):
    date: Date
    no_of_cups: int | None = None
    rate_per_cup: Decimal | None = None
    total_amount: Decimal | None = None
    vendor: str | None = None


class TeaEntryUpdatePreview(PublicContractModel):
    tea_entry_name: NonEmptyString
    before: TeaEntryUpdateState
    after: TeaEntryUpdateState


class TeaEntryUpdatePreviewOnly(PublicContractModel):
    status: Literal["preview"]
    preview: TeaEntryUpdatePreview


class TeaEntryUpdateReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: NonEmptyString
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: TeaEntryUpdatePreview
    interaction: InteractionDirective


class TeaEntryUpdateNotFound(PublicContractModel):
    status: Literal["not_found"]
    tea_entry_name: NonEmptyString


class TeaEntryUpdated(PublicContractModel):
    status: Literal["updated"]
    tea_entry: TeaEntryMetadata


class TeaEntryUpdatePrepareOutput(
    RootModel[
        Annotated[
            TeaEntryUpdatePreviewOnly | TeaEntryUpdateReady | TeaEntryUpdateNotFound | ToolError,
            Field(discriminator="status"),
        ]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class TeaEntryUpdateOutput(
    RootModel[
        Annotated[TeaEntryUpdated | TeaEntryUpdateNotFound | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class TeaEntryUpdateConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool
