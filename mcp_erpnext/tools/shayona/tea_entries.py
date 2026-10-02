"""Typed MCP adapters for Shayona Tea Entry tools."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context

from ...contracts.common import NonEmptyString
from ...contracts.shayona.tea_entries import (
    PositiveLimit,
    PositiveCups,
    NonNegativeRate,
    TeaEntryCreateInput,
    TeaEntryConfirmInput,
    TeaEntryPrepareOutput,
    TeaEntryCreateOutput,
    TeaEntryUpdateChanges,
    TeaEntryUpdateConfirmInput,
    TeaEntryUpdateInput,
    TeaEntryUpdateOutput,
    TeaEntryUpdatePrepareOutput,
    TeaEntryAggregateGroup,
    TeaEntryAggregateInput,
    TeaEntryAggregateMetric,
    TeaEntryAggregateOutput,
    TeaEntryGetInput,
    TeaEntryGetOutput,
    TeaEntryQueryInput,
    TeaEntryQueryOutput,
    TeaEntrySortOrder,
)
from ...runtime import execute_tool_with_context
from ...services.shayona import tea_entries as service


def get_tea_entry(
    tea_entry_name: NonEmptyString,
    ctx: Context,
) -> TeaEntryGetOutput:
    request = TeaEntryGetInput(tea_entry_name=tea_entry_name)
    result = execute_tool_with_context(
        ctx,
        "get_tea_entry",
        lambda: service.get_tea_entry(request.tea_entry_name),
        rest_arguments=request.model_dump(mode="json"),
    )
    return TeaEntryGetOutput.model_validate(result)


def query_tea_entries(
    ctx: Context,
    date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor: NonEmptyString | None = None,
    limit: PositiveLimit = 20,
    offset: int = 0,
    sort_order: TeaEntrySortOrder = "desc",
) -> TeaEntryQueryOutput:
    request = TeaEntryQueryInput(
        date=date,
        date_from=date_from,
        date_to=date_to,
        vendor=vendor,
        limit=limit,
        offset=offset,
        sort_order=sort_order,
    )
    result = execute_tool_with_context(
        ctx,
        "query_tea_entries",
        lambda: service.query_tea_entries(request.model_dump()),
        rest_arguments=request.model_dump(mode="json"),
    )
    return TeaEntryQueryOutput.model_validate(result)


def aggregate_tea_entries(
    metrics: list[TeaEntryAggregateMetric],
    ctx: Context,
    date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor: NonEmptyString | None = None,
    group_by: TeaEntryAggregateGroup | None = None,
) -> TeaEntryAggregateOutput:
    request = TeaEntryAggregateInput(
        metrics=metrics,
        date=date,
        date_from=date_from,
        date_to=date_to,
        vendor=vendor,
        group_by=group_by,
    )
    result = execute_tool_with_context(
        ctx,
        "aggregate_tea_entries",
        lambda: service.aggregate_tea_entries(request.model_dump()),
        rest_arguments=request.model_dump(mode="json"),
    )
    return TeaEntryAggregateOutput.model_validate(result)


def prepare_tea_entry(
    no_of_cups: PositiveCups,
    rate_per_cup: NonNegativeRate,
    ctx: Context,
    date: date | None = None,
    vendor: NonEmptyString | None = None,
) -> TeaEntryPrepareOutput:
    request = TeaEntryCreateInput(no_of_cups=no_of_cups, rate_per_cup=rate_per_cup, date=date, vendor=vendor)
    result = execute_tool_with_context(
        ctx, "prepare_tea_entry", lambda: service.prepare_tea_entry(request.model_dump()),
        rest_arguments=request.model_dump(mode="json"),
    )
    return TeaEntryPrepareOutput.model_validate(result)


def confirm_tea_entry(
    approval_token: NonEmptyString, confirm: bool, ctx: Context,
) -> TeaEntryCreateOutput:
    request = TeaEntryConfirmInput(approval_token=approval_token, confirm=confirm)
    result = execute_tool_with_context(
        ctx, "confirm_tea_entry", lambda: service.confirm_tea_entry(request.approval_token, request.confirm),
        rest_arguments=request.model_dump(mode="json"),
    )
    return TeaEntryCreateOutput.model_validate(result)


def execute_tea_entry(
    no_of_cups: PositiveCups,
    rate_per_cup: NonNegativeRate,
    ctx: Context,
    date: date | None = None,
    vendor: NonEmptyString | None = None,
) -> TeaEntryCreateOutput:
    request = TeaEntryCreateInput(no_of_cups=no_of_cups, rate_per_cup=rate_per_cup, date=date, vendor=vendor)
    result = execute_tool_with_context(
        ctx, "execute_tea_entry", lambda: service.execute_tea_entry(request.model_dump()),
        rest_arguments=request.model_dump(mode="json"),
    )
    return TeaEntryCreateOutput.model_validate(result)


def prepare_tea_entry_update(
    tea_entry_name: NonEmptyString,
    changes: TeaEntryUpdateChanges,
    ctx: Context,
) -> TeaEntryUpdatePrepareOutput:
    request = TeaEntryUpdateInput(tea_entry_name=tea_entry_name, changes=changes)
    result = execute_tool_with_context(
        ctx,
        "prepare_tea_entry_update",
        lambda: service.prepare_tea_entry_update(request.model_dump(exclude_unset=True)),
        rest_arguments=request.model_dump(mode="json", exclude_unset=True),
    )
    return TeaEntryUpdatePrepareOutput.model_validate(result)


def confirm_tea_entry_update(
    approval_token: NonEmptyString,
    confirm: bool,
    ctx: Context,
) -> TeaEntryUpdateOutput:
    request = TeaEntryUpdateConfirmInput(approval_token=approval_token, confirm=confirm)
    result = execute_tool_with_context(
        ctx,
        "confirm_tea_entry_update",
        lambda: service.confirm_tea_entry_update(request.approval_token, request.confirm),
        rest_arguments=request.model_dump(mode="json"),
    )
    return TeaEntryUpdateOutput.model_validate(result)


def execute_tea_entry_update(
    tea_entry_name: NonEmptyString,
    changes: TeaEntryUpdateChanges,
    ctx: Context,
) -> TeaEntryUpdateOutput:
    request = TeaEntryUpdateInput(tea_entry_name=tea_entry_name, changes=changes)
    result = execute_tool_with_context(
        ctx,
        "execute_tea_entry_update",
        lambda: service.execute_tea_entry_update(request.model_dump(exclude_unset=True)),
        rest_arguments=request.model_dump(mode="json", exclude_unset=True),
    )
    return TeaEntryUpdateOutput.model_validate(result)


def register_shayona_tea_entry_tools(mcp: Any) -> None:
    for tool in (
        get_tea_entry, query_tea_entries, aggregate_tea_entries,
        prepare_tea_entry, confirm_tea_entry, execute_tea_entry,
        prepare_tea_entry_update, confirm_tea_entry_update, execute_tea_entry_update,
    ):
        mcp.tool()(tool)
