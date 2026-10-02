"""Resolve a narrow master-creation contract from live Frappe metadata."""

from __future__ import annotations

from typing import Any, Callable

ValueSource = str


def _field_value(field: Any, fieldname: str, default: Any = None) -> Any:
    if isinstance(field, dict):
        return field.get(fieldname, default)
    getter = getattr(field, "get", None)
    if callable(getter):
        return getter(fieldname, default)
    return getattr(field, fieldname, default)


def _document_value(document: Any, fieldname: str) -> Any:
    getter = getattr(document, "get", None)
    if callable(getter):
        return getter(fieldname)
    return getattr(document, fieldname, None)


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def _field_map(meta: Any) -> dict[str, Any]:
    fields = getattr(meta, "fields", None)
    if fields is None and hasattr(meta, "get"):
        fields = meta.get("fields", [])
    return {
        fieldname: field
        for field in fields or []
        if (fieldname := _field_value(field, "fieldname"))
    }


def _field_description(
    doctype: str, fieldname: str, field: Any, path_prefix: str
) -> dict[str, Any]:
    return {
        "doctype": doctype,
        "fieldname": fieldname,
        "path": f"{path_prefix}.{fieldname}",
        "label": _field_value(field, "label") or fieldname.replace("_", " ").title(),
        "fieldtype": _field_value(field, "fieldtype") or "Data",
    }


def resolve_creation_contract(
    *,
    doctype: str,
    input_values: dict[str, Any],
    creation_fields: tuple[str, ...],
    policy_values: dict[str, Any],
    path_prefix: str,
    get_meta: Callable[[str], Any],
    new_document: Callable[[str], Any],
) -> dict[str, Any]:
    """Resolve supplied, policy, and installed runtime-default values without writing.

    ``new_document`` must create an unsaved Frappe document (normally
    ``frappe.new_doc``). It applies the installed site metadata and user defaults
    before this helper checks what still remains mandatory.
    """
    meta = get_meta(doctype)
    fields_by_name = _field_map(meta)
    runtime_document = new_document(doctype)
    values: dict[str, Any] = {}
    sources: dict[str, ValueSource] = {}

    for fieldname in dict.fromkeys(creation_fields):
        if _has_value(input_values.get(fieldname)):
            values[fieldname] = input_values[fieldname]
            sources[fieldname] = "user_input"
        elif fieldname in policy_values and _has_value(policy_values[fieldname]):
            values[fieldname] = policy_values[fieldname]
            sources[fieldname] = "mcp_policy"
        elif _has_value(default := _document_value(runtime_document, fieldname)):
            values[fieldname] = default
            sources[fieldname] = "erpnext_default"

    missing_fields = []
    conditional_fields = []
    for fieldname in dict.fromkeys(creation_fields):
        field = fields_by_name.get(fieldname)
        if not field:
            continue
        if _field_value(field, "mandatory_depends_on"):
            conditional_fields.append(
                {
                    **_field_description(doctype, fieldname, field, path_prefix),
                    "reason": "conditional_mandatory",
                    "source": "erpnext_metadata",
                }
            )
        if _field_value(field, "reqd") and fieldname not in values:
            missing_fields.append(
                {
                    **_field_description(doctype, fieldname, field, path_prefix),
                    "reason": "mandatory",
                    "source": "erpnext_metadata",
                }
            )

    return {
        "values": values,
        "sources": sources,
        "missing": [field["path"] for field in missing_fields],
        "missing_fields": missing_fields,
        "fields": fields_by_name,
        "conditional_fields": conditional_fields,
    }


def missing_input_response(contract: dict[str, Any]) -> dict[str, Any]:
    """Keep the existing ``missing`` list while adding metadata for future agents."""
    return {
        "status": "needs_input",
        "missing": contract["missing"],
        "missing_fields": contract["missing_fields"],
    }


def select_options(contract: dict[str, Any], fieldname: str) -> set[str]:
    """Return current metadata options for one Select field, if available."""
    field = contract["fields"].get(fieldname)
    if not field or _field_value(field, "fieldtype") != "Select":
        return set()
    options = _field_value(field, "options") or ""
    return {option.strip() for option in str(options).splitlines() if option.strip()}
