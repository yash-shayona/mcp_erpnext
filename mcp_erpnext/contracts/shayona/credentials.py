"""Public contracts for safe Customer Service Credential reads."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError

PositiveLimit = Annotated[int, Field(ge=1, le=100)]
NonNegativeOffset = Annotated[int, Field(ge=0)]


class CustomerServiceCredentialMetadata(PublicContractModel):
    """Fixed non-secret projection; caller fields cannot expand it."""

    name: str
    customer: str | None = None
    domain_name: str | None = None
    credential_type: str | None = None
    account_name: str | None = None
    account_identity: str | None = None
    control_panel_url: str | None = None
    is_active: bool


class CredentialSearchInput(PublicContractModel):
    query: NonEmptyString | None = None
    customer: NonEmptyString | None = None
    domain_name: NonEmptyString | None = None
    credential_type: NonEmptyString | None = None
    account_name: NonEmptyString | None = None
    account_identity: NonEmptyString | None = None
    is_active: bool | None = None
    include_inactive: bool = False
    limit: PositiveLimit = 20


class CredentialSearchOk(PublicContractModel):
    status: Literal["ok"]
    credentials: list[CustomerServiceCredentialMetadata]
    count: int
    limit: int


class CredentialSearchOutput(
    RootModel[Annotated[CredentialSearchOk | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}


CredentialSortField = Literal[
    "name",
    "customer",
    "domain_name",
    "credential_type",
    "account_name",
    "account_identity",
    "is_active",
]
CredentialSortOrder = Literal["asc", "desc"]
CredentialAggregateMetric = Literal["count"]
CredentialAggregateGroup = Literal["customer", "credential_type", "is_active"]


class CredentialStructuredFilters(PublicContractModel):
    name: NonEmptyString | None = None
    customer: NonEmptyString | None = None
    domain_name: NonEmptyString | None = None
    credential_type: NonEmptyString | None = None
    account_name: NonEmptyString | None = None
    account_identity: NonEmptyString | None = None
    is_active: bool | None = None
    include_inactive: bool = False


class CredentialQueryInput(CredentialStructuredFilters):
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_by: CredentialSortField = "name"
    sort_order: CredentialSortOrder = "asc"


class CredentialQueryOk(PublicContractModel):
    status: Literal["ok"]
    credentials: list[CustomerServiceCredentialMetadata]
    count: int
    limit: int
    offset: int


class CredentialQueryOutput(
    RootModel[Annotated[CredentialQueryOk | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class CredentialAggregateInput(CredentialStructuredFilters):
    metrics: list[CredentialAggregateMetric] = Field(min_length=1, max_length=1)
    group_by: CredentialAggregateGroup | None = None

    @model_validator(mode="after")
    def require_count(self):
        if self.metrics != ["count"]:
            raise ValueError("metrics must contain only count")
        return self


class CredentialAggregateRow(PublicContractModel):
    group_value: str | bool | None = None
    count: int


class CredentialAggregateOk(PublicContractModel):
    status: Literal["ok"]
    metrics: list[CredentialAggregateMetric]
    group_by: CredentialAggregateGroup | None = None
    results: list[CredentialAggregateRow]


class CredentialAggregateOutput(
    RootModel[
        Annotated[CredentialAggregateOk | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class CredentialGetInput(PublicContractModel):
    credential_name: NonEmptyString


class CredentialGetOk(PublicContractModel):
    status: Literal["ok"]
    credential: CustomerServiceCredentialMetadata


class CredentialNotFound(PublicContractModel):
    status: Literal["not_found"]
    credential_name: NonEmptyString


class CredentialGetOutput(
    RootModel[
        Annotated[
            CredentialGetOk | CredentialNotFound | ToolError,
            Field(discriminator="status"),
        ]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}
