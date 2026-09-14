"""Permission-aware, bounded Payment Entry reads and analytics."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe

from ...observability import new_error_reference
from ..common.aggregate import (
	build_aggregate_field,
	build_aggregate_fields,
	execute_aggregate,
	shape_aggregate_rows,
)


_FIELDS = frozenset(
	"name docstatus status payment_type company posting_date party_type party party_name "
	"mode_of_payment paid_from paid_from_account_currency paid_to paid_to_account_currency "
	"paid_amount received_amount total_allocated_amount unallocated_amount difference_amount "
	"reference_no reference_date project remarks owner creation modified".split()
)
_SORT_FIELDS = frozenset(
	"posting_date name modified paid_amount received_amount status payment_type".split()
)
_GROUP_FIELDS = frozenset(
	"docstatus status payment_type company party_type party mode_of_payment "
	"paid_from_account_currency paid_to_account_currency posting_date".split()
)
_REFERENCE_DOCTYPES = frozenset(
	{"Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order"}
)
_REFERENCE_FIELDS = frozenset(
	"reference_doctype reference_name bill_no due_date payment_term total_amount "
	"outstanding_amount allocated_amount exchange_rate".split()
)
_METRICS = {
	"count": build_aggregate_field("COUNT", "*", "count"),
	"sum_paid_amount": build_aggregate_field("SUM", "paid_amount", "sum_paid_amount"),
	"sum_received_amount": build_aggregate_field(
		"SUM", "received_amount", "sum_received_amount"
	),
	"sum_total_allocated_amount": build_aggregate_field(
		"SUM", "total_allocated_amount", "sum_total_allocated_amount"
	),
	"sum_unallocated_amount": build_aggregate_field(
		"SUM", "unallocated_amount", "sum_unallocated_amount"
	),
}
_ALLOCATION_METRICS = frozenset(
	{"sum_total_allocated_amount", "sum_unallocated_amount"}
)
_MAX_REFERENCE_CANDIDATES = 1000


def _error(code: str, message: str) -> dict[str, Any]:
	return {
		"status": "error",
		"code": code,
		"message": message,
		"reference": new_error_reference(),
		"retryable": False,
	}


def _date(value: date | None) -> str | None:
	return value.isoformat() if value else None


def _validate_fields(fields: list[str]) -> list[str]:
	if any(field not in _FIELDS for field in fields):
		raise ValueError("Payment Entry projection contains an unsupported field.")
	return fields


def _range(
	filters: list[list[Any]], field: str, start: date | None, end: date | None
) -> None:
	if start and end:
		filters.append([field, "between", [_date(start), _date(end)]])
	elif start:
		filters.append([field, ">=", _date(start)])
	elif end:
		if field in {"creation", "modified"}:
			filters.append([field, "<", (end + timedelta(days=1)).isoformat()])
		else:
			filters.append([field, "<=", _date(end)])


def _parent_filters(criteria: dict[str, Any], parent_names: list[str] | None = None) -> list[list[Any]]:
	filters: list[list[Any]] = []
	for field in (
		"name",
		"docstatus",
		"status",
		"payment_type",
		"company",
		"party_type",
		"party",
		"mode_of_payment",
		"paid_from_account_currency",
		"paid_to_account_currency",
		"reference_no",
	):
		if criteria.get(field) is not None:
			filters.append([field, "=", criteria[field]])
	for field, start, end in (
		("posting_date", criteria.get("posting_date_from"), criteria.get("posting_date_to")),
		("creation", criteria.get("created_from"), criteria.get("created_to")),
		("modified", criteria.get("modified_from"), criteria.get("modified_to")),
	):
		_range(filters, field, start, end)
	for field, exact, minimum, maximum in (
		(
			"paid_amount",
			criteria.get("paid_amount"),
			criteria.get("paid_amount_min"),
			criteria.get("paid_amount_max"),
		),
		(
			"received_amount",
			criteria.get("received_amount"),
			criteria.get("received_amount_min"),
			criteria.get("received_amount_max"),
		),
	):
		if exact is not None:
			filters.append([field, "=", exact])
		if minimum is not None:
			filters.append([field, ">=", minimum])
		if maximum is not None:
			filters.append([field, "<=", maximum])
	if parent_names is not None:
		filters.append(["name", "in", parent_names])
	return filters


def _reference_parent_names(criteria: dict[str, Any]) -> list[str] | None:
	reference_doctype = criteria.get("reference_doctype")
	reference_name = criteria.get("reference_name")
	if reference_doctype is None and reference_name is None:
		return None
	if reference_doctype not in _REFERENCE_DOCTYPES or not reference_name:
		raise ValueError("Payment Entry reference filter is incomplete or unsupported.")
	rows = frappe.get_list(
		"Payment Entry Reference",
		filters=[
			["reference_doctype", "=", reference_doctype],
			["reference_name", "=", reference_name],
		],
		fields=["parent"],
		limit_page_length=_MAX_REFERENCE_CANDIDATES,
		ignore_permissions=False,
	)
	return list(dict.fromkeys(row.get("parent") for row in rows if row.get("parent")))


def _project(values: Any, fields: list[str], *, references: list[dict[str, Any]] | None = None) -> dict[str, Any]:
	result = {field: values.get(field) for field in fields if values.get(field) is not None}
	if references is not None:
		result["references"] = references
	return result


def _reference_project(row: Any) -> dict[str, Any]:
	return {
		field: row.get(field)
		for field in _REFERENCE_FIELDS
		if row.get(field) is not None
	}


def _sort_expression(sort_by: str, sort_order: str) -> str:
	if sort_by not in _SORT_FIELDS or sort_order not in {"asc", "desc"}:
		raise ValueError("Payment Entry sort contains an unsupported field or order.")
	return f"{sort_by} {sort_order}, name {sort_order}"


def _currency_fields(
	metrics: list[str], criteria: dict[str, Any], group_by: str | None
) -> list[str] | dict[str, Any]:
	if any(metric not in _METRICS for metric in metrics):
		raise ValueError("Payment Entry aggregate contains an unsupported metric.")
	if group_by is not None and group_by not in _GROUP_FIELDS:
		raise ValueError("Payment Entry aggregate contains an unsupported grouping field.")

	required: list[str] = []
	if "sum_paid_amount" in metrics:
		required.append("paid_from_account_currency")
	if "sum_received_amount" in metrics:
		required.append("paid_to_account_currency")
	if _ALLOCATION_METRICS.intersection(metrics):
		payment_type = criteria.get("payment_type")
		if payment_type == "Receive":
			required.append("paid_from_account_currency")
		elif payment_type == "Pay":
			required.append("paid_to_account_currency")
		else:
			return _error(
				"MIXED_CURRENCY_AGGREGATE",
				"Allocation totals require payment_type Receive or Pay so their native currency is unambiguous.",
			)
	return required


def _aggregate_fields(
	metrics: list[str], criteria: dict[str, Any], group_by: str | None
) -> tuple[list[Any], list[str]] | dict[str, Any]:
	currency_fields = _currency_fields(metrics, criteria, group_by)
	if isinstance(currency_fields, dict):
		return currency_fields
	fields, groups = build_aggregate_fields(metrics, _METRICS, group_by=group_by)
	for currency_field in reversed(currency_fields):
		if criteria.get(currency_field) is None and currency_field not in groups:
			fields.insert(0, currency_field)
			groups.insert(0, currency_field)
	return fields, groups


def get_payment_entry(name: str, fields: list[str]) -> dict[str, Any]:
	fields = _validate_fields(fields)
	try:
		doc = frappe.get_doc("Payment Entry", name)
	except frappe.DoesNotExistError:
		return {"status": "not_found", "name": name}
	if not doc.has_permission("read"):
		return _error("PERMISSION_DENIED", "The authenticated user cannot read that Payment Entry.")
	references = [_reference_project(row) for row in (doc.get("references") or [])]
	return {"status": "ok", "document": _project(doc, fields, references=references)}


def query_payment_entries(criteria: dict[str, Any]) -> dict[str, Any]:
	fields = _validate_fields(criteria["fields"])
	parent_names = _reference_parent_names(criteria)
	if parent_names == []:
		return {
			"status": "ok",
			"payment_entries": [],
			"count": 0,
			"limit": criteria["limit"],
			"offset": criteria["offset"],
		}
	rows = frappe.get_list(
		"Payment Entry",
		filters=_parent_filters(criteria, parent_names),
		fields=fields,
		order_by=_sort_expression(criteria["sort_by"], criteria["sort_order"]),
		limit_start=criteria["offset"],
		limit_page_length=criteria["limit"],
		ignore_permissions=False,
	)
	return {
		"status": "ok",
		"payment_entries": [_project(row, fields) for row in rows],
		"count": len(rows),
		"limit": criteria["limit"],
		"offset": criteria["offset"],
	}


def aggregate_payment_entries(criteria: dict[str, Any]) -> dict[str, Any]:
	metrics = criteria["metrics"]
	group_by = criteria.get("group_by")
	built = _aggregate_fields(metrics, criteria, group_by)
	if isinstance(built, dict):
		return built
	fields, groups = built
	parent_names = _reference_parent_names(criteria)
	if parent_names == []:
		return {
			"status": "ok",
			"metrics": metrics,
			"group_by": group_by,
			"results": [],
		}
	rows = execute_aggregate(
		frappe.get_list,
		"Payment Entry",
		filters=_parent_filters(criteria, parent_names),
		fields=fields,
		groups=groups,
	)
	results = shape_aggregate_rows(rows, metrics, group_by=group_by)
	for result, row in zip(results, rows):
		for field in ("paid_from_account_currency", "paid_to_account_currency"):
			if field in groups and row.get(field) is not None:
				result[field] = row.get(field)
			elif criteria.get(field) is not None:
				# Preserve the caller's single-currency context in the result.
				result[field] = criteria[field]
	return {
		"status": "ok",
		"metrics": metrics,
		"group_by": group_by,
		"results": results,
	}
