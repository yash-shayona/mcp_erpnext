"""Typed MCP adapters for safe Customer Service Credential metadata reads."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from ...contracts.common import NonEmptyString
from ...contracts.shayona.credentials import (
    CredentialAggregateGroup,
    CredentialAggregateInput,
    CredentialAggregateMetric,
    CredentialAggregateOutput,
    CredentialGetInput,
    CredentialGetOutput,
    CredentialQueryInput,
    CredentialQueryOutput,
    CredentialSearchInput,
    CredentialSearchOutput,
    CredentialSortField,
    CredentialSortOrder,
    PositiveLimit,
)
from ...runtime import execute_tool_with_context
from ...services.shayona import credentials as service


def _values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def search_customer_service_credentials(
    ctx: Context,
    query: NonEmptyString | None = None,
    customer: NonEmptyString | None = None,
    domain_name: NonEmptyString | None = None,
    credential_type: NonEmptyString | None = None,
    account_name: NonEmptyString | None = None,
    account_identity: NonEmptyString | None = None,
    is_active: bool | None = None,
    include_inactive: bool = False,
    limit: PositiveLimit = 20,
) -> CredentialSearchOutput:
    request = CredentialSearchInput(
        **_values(
            {
                "query": query,
                "customer": customer,
                "domain_name": domain_name,
                "credential_type": credential_type,
                "account_name": account_name,
                "account_identity": account_identity,
                "is_active": is_active,
                "include_inactive": include_inactive,
                "limit": limit,
            }
        )
    )
    result = execute_tool_with_context(
        ctx,
        "search_customer_service_credentials",
        lambda: service.search_customer_service_credentials(request.model_dump()),
        rest_arguments=request.model_dump(mode="json"),
    )
    return CredentialSearchOutput.model_validate(result)


def get_customer_service_credential(
    credential_name: NonEmptyString,
    ctx: Context,
) -> CredentialGetOutput:
    request = CredentialGetInput(credential_name=credential_name)
    result = execute_tool_with_context(
        ctx,
        "get_customer_service_credential",
        lambda: service.get_customer_service_credential(request.credential_name),
        rest_arguments=request.model_dump(mode="json"),
    )
    return CredentialGetOutput.model_validate(result)


def query_customer_service_credentials(
    ctx: Context,
    name: NonEmptyString | None = None,
    customer: NonEmptyString | None = None,
    domain_name: NonEmptyString | None = None,
    credential_type: NonEmptyString | None = None,
    account_name: NonEmptyString | None = None,
    account_identity: NonEmptyString | None = None,
    is_active: bool | None = None,
    include_inactive: bool = False,
    limit: PositiveLimit = 20,
    offset: int = 0,
    sort_by: CredentialSortField = "name",
    sort_order: CredentialSortOrder = "asc",
) -> CredentialQueryOutput:
    request = CredentialQueryInput(
        **_values(
            {
                "name": name,
                "customer": customer,
                "domain_name": domain_name,
                "credential_type": credential_type,
                "account_name": account_name,
                "account_identity": account_identity,
                "is_active": is_active,
                "include_inactive": include_inactive,
                "limit": limit,
                "offset": offset,
                "sort_by": sort_by,
                "sort_order": sort_order,
            }
        )
    )
    result = execute_tool_with_context(
        ctx,
        "query_customer_service_credentials",
        lambda: service.query_customer_service_credentials(request.model_dump()),
        rest_arguments=request.model_dump(mode="json"),
    )
    return CredentialQueryOutput.model_validate(result)


def aggregate_customer_service_credentials(
    metrics: list[CredentialAggregateMetric],
    ctx: Context,
    name: NonEmptyString | None = None,
    customer: NonEmptyString | None = None,
    domain_name: NonEmptyString | None = None,
    credential_type: NonEmptyString | None = None,
    account_name: NonEmptyString | None = None,
    account_identity: NonEmptyString | None = None,
    is_active: bool | None = None,
    include_inactive: bool = False,
    group_by: CredentialAggregateGroup | None = None,
) -> CredentialAggregateOutput:
    request = CredentialAggregateInput(
        **_values(
            {
                "metrics": metrics,
                "name": name,
                "customer": customer,
                "domain_name": domain_name,
                "credential_type": credential_type,
                "account_name": account_name,
                "account_identity": account_identity,
                "is_active": is_active,
                "include_inactive": include_inactive,
                "group_by": group_by,
            }
        )
    )
    result = execute_tool_with_context(
        ctx,
        "aggregate_customer_service_credentials",
        lambda: service.aggregate_customer_service_credentials(request.model_dump()),
        rest_arguments=request.model_dump(mode="json"),
    )
    return CredentialAggregateOutput.model_validate(result)


def register_shayona_credential_tools(mcp: Any) -> None:
    for tool in (
        search_customer_service_credentials,
        get_customer_service_credential,
        query_customer_service_credentials,
        aggregate_customer_service_credentials,
    ):
        mcp.tool()(tool)
