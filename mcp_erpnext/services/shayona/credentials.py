"""Permission-aware, secret-free Customer Service Credential reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe

from ...observability import logged_defined_error

CREDENTIAL_DOCTYPE = "Customer Service Credential"
PUBLIC_FIELDS = (
    "name",
    "customer",
    "domain_name",
    "credential_type",
    "account_name",
    "account_identity",
    "control_panel_url",
    "is_active",
)
SECRET_FIELDS = frozenset({"username", "password"})
REQUIRED_FIELDS = frozenset((*PUBLIC_FIELDS, *SECRET_FIELDS))
SEARCH_FIELDS = (
    "name",
    "customer",
    "domain_name",
    "credential_type",
    "account_name",
    "account_identity",
)
FILTER_FIELDS = SEARCH_FIELDS
SORT_FIELDS = frozenset((*SEARCH_FIELDS, "is_active"))
AGGREGATE_GROUP_FIELDS = frozenset({"customer", "credential_type", "is_active"})
COUNT_FIELD = {"COUNT": "name", "as": "count"}


class CredentialSchemaUnavailableError(RuntimeError):
    """Raised when the active site does not provide the required Shayona schema."""


@dataclass(frozen=True)
class CredentialSchema:
    public_fields: tuple[str, ...]


def credential_schema(meta: Any | None = None) -> CredentialSchema:
    """Validate live metadata without importing the Shayona Python app."""
    try:
        meta = meta or frappe.get_meta(CREDENTIAL_DOCTYPE)
        fieldnames = set(meta.get_valid_columns())
    except Exception as error:
        raise CredentialSchemaUnavailableError() from error

    if not REQUIRED_FIELDS.issubset(fieldnames):
        raise CredentialSchemaUnavailableError()
    control_panel_url = meta.get_field("control_panel_url")
    if (
        control_panel_url is None
        or control_panel_url.fieldtype != "Data"
        or control_panel_url.options != "URL"
    ):
        raise CredentialSchemaUnavailableError()
    return CredentialSchema(public_fields=PUBLIC_FIELDS)


def _value(values: Any, fieldname: str) -> Any:
    if isinstance(values, dict):
        return values.get(fieldname)
    return getattr(values, fieldname, None)


def _project(values: Any) -> dict[str, Any]:
    """Construct the fixed safe projection; never call ``as_dict`` or decrypt password."""
    return {
        field: _value(values, field) for field in PUBLIC_FIELDS if field != "is_active"
    } | {"is_active": bool(_value(values, "is_active"))}


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _active_filter(criteria: dict[str, Any]) -> dict[str, Any]:
    if criteria.get("is_active") is not None:
        return {"is_active": int(criteria["is_active"])}
    if not criteria.get("include_inactive", False):
        return {"is_active": 1}
    return {}


def _exact_filters(criteria: dict[str, Any]) -> dict[str, Any]:
    filters = {
        field: criteria[field]
        for field in FILTER_FIELDS
        if criteria.get(field) is not None
    }
    return filters | _active_filter(criteria)


def _order_by(sort_by: str, sort_order: str) -> str:
    if sort_by not in SORT_FIELDS or sort_order not in {"asc", "desc"}:
        raise ValueError("unsupported credential sort")
    if sort_by == "name":
        return f"name {sort_order}"
    return f"{sort_by} {sort_order}, name {sort_order}"


def _schema_error(tool_name: str) -> dict[str, Any] | None:
    try:
        credential_schema()
    except CredentialSchemaUnavailableError:
        return logged_defined_error(tool_name, "CREDENTIAL_SCHEMA_UNAVAILABLE")
    return None


def search_customer_service_credentials(criteria: dict[str, Any]) -> dict[str, Any]:
    if error := _schema_error("search_customer_service_credentials"):
        return error
    kwargs: dict[str, Any] = {
        "filters": _exact_filters(criteria),
        "fields": list(PUBLIC_FIELDS),
        "order_by": "name asc",
        "limit_page_length": criteria["limit"],
        "ignore_permissions": False,
    }
    if criteria.get("query") is not None:
        query = f"%{_escape_like(criteria['query'])}%"
        kwargs["or_filters"] = [[field, "like", query] for field in SEARCH_FIELDS]
    rows = frappe.get_list(CREDENTIAL_DOCTYPE, **kwargs)
    credentials = [_project(row) for row in rows]
    return {
        "status": "ok",
        "credentials": credentials,
        "count": len(credentials),
        "limit": criteria["limit"],
    }


def query_customer_service_credentials(criteria: dict[str, Any]) -> dict[str, Any]:
    if error := _schema_error("query_customer_service_credentials"):
        return error
    rows = frappe.get_list(
        CREDENTIAL_DOCTYPE,
        filters=_exact_filters(criteria),
        fields=list(PUBLIC_FIELDS),
        order_by=_order_by(criteria["sort_by"], criteria["sort_order"]),
        limit_start=criteria["offset"],
        limit_page_length=criteria["limit"],
        ignore_permissions=False,
    )
    credentials = [_project(row) for row in rows]
    return {
        "status": "ok",
        "credentials": credentials,
        "count": len(credentials),
        "limit": criteria["limit"],
        "offset": criteria["offset"],
    }


def aggregate_customer_service_credentials(criteria: dict[str, Any]) -> dict[str, Any]:
    if error := _schema_error("aggregate_customer_service_credentials"):
        return error
    group_by = criteria.get("group_by")
    if criteria.get("metrics") != ["count"]:
        raise ValueError("metrics must contain only count")
    if group_by is not None and group_by not in AGGREGATE_GROUP_FIELDS:
        raise ValueError("unsupported credential group")
    fields: list[Any] = [group_by] if group_by else []
    fields.append(COUNT_FIELD)
    rows = frappe.get_list(
        CREDENTIAL_DOCTYPE,
        filters=_exact_filters(criteria),
        fields=fields,
        group_by=group_by,
        order_by=f"{group_by} asc" if group_by else None,
        ignore_permissions=False,
    )
    results = []
    for row in rows:
        result = {"count": _value(row, "count")}
        if group_by:
            value = _value(row, group_by)
            result["group_value"] = (
                bool(value) if group_by == "is_active" and value is not None else value
            )
        results.append(result)
    return {
        "status": "ok",
        "metrics": criteria["metrics"],
        "group_by": group_by,
        "results": results,
    }


def get_customer_service_credential(credential_name: str) -> dict[str, Any]:
    if error := _schema_error("get_customer_service_credential"):
        return error
    try:
        doc = frappe.get_doc(CREDENTIAL_DOCTYPE, credential_name)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "credential_name": credential_name}
    if not doc.has_permission("read"):
        raise frappe.PermissionError()
    return {"status": "ok", "credential": _project(doc)}
