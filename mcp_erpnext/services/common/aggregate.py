"""Shared mechanics for permission-aware, allowlisted aggregate services."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

_SUPPORTED_OPERATIONS = frozenset({"COUNT", "SUM", "AVG", "MIN", "MAX"})


def build_aggregate_field(operation: str, source: str, alias: str) -> dict[str, str]:
    """Return a Frappe v16-compatible dictionary aggregate field."""
    operation = operation.upper()
    if operation not in _SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported aggregate operation: {operation}")
    return {operation: source, "as": alias}


def build_aggregate_fields(
    metrics: Sequence[str],
    metric_fields: Mapping[str, Any],
    *,
    group_by: str | None = None,
    group_field: str | None = None,
    group_alias: str | None = None,
) -> tuple[list[Any], list[str]]:
    """Build aggregate fields from caller-supplied, already-approved expressions.

    Metric and group allowlists remain in the calling DocType service. This
    helper only assembles their already-approved expressions.
    """
    fields: list[Any] = []
    groups: list[str] = []
    if group_by:
        resolved_group = group_field or group_by
        fields.append(
            f"{resolved_group} as {group_alias}" if group_alias else resolved_group
        )
        groups.append(resolved_group)
    fields.extend(metric_fields[metric] for metric in metrics)
    return fields, groups


def execute_aggregate(
    get_list: Callable[..., list[dict[str, Any]]],
    doctype: str,
    *,
    filters: list[list[Any]],
    fields: list[Any],
    groups: Sequence[str],
) -> list[dict[str, Any]]:
    """Execute an aggregate through the caller's permission-aware Frappe seam."""
    group_expression = ", ".join(groups) or None
    return get_list(
        doctype,
        filters=filters,
        fields=fields,
        group_by=group_expression,
        order_by=group_expression,
        ignore_permissions=False,
    )


def shape_aggregate_rows(
    rows: Sequence[Mapping[str, Any]],
    metrics: Sequence[str],
    *,
    group_by: str | None = None,
    group_value_field: str | None = None,
) -> list[dict[str, Any]]:
    """Shape the common metric/group result contract without null values."""
    results: list[dict[str, Any]] = []
    for row in rows:
        result = {
            metric: row.get(metric) for metric in metrics if row.get(metric) is not None
        }
        if group_by:
            result["group_value"] = row.get(group_value_field or group_by)
        results.append(result)
    return results
