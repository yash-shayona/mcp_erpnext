"""Metadata-driven resolution for fields explicitly exposed by MCP capabilities."""

from __future__ import annotations

import json
import math
from typing import Any

from .entity_resolution import (
    normalize,
    rank_candidates,
    resolve_candidate,
    resolve_ranked_candidates,
)

# This catalog is taken from the installed Frappe DocField definition. Categories
# describe how fields are handled; only strategies needed by exposed capabilities
# are enabled below. Unknown future field types are explicitly unsupported.
FIELD_TYPE_CATEGORIES = {
    "Autocomplete": "scalar_text",
    "Attach": "specialized",
    "Attach Image": "specialized",
    "Barcode": "scalar_text",
    "Button": "layout",
    "Check": "boolean",
    "Code": "scalar_text",
    "Color": "scalar_text",
    "Column Break": "layout",
    "Currency": "numeric",
    "Data": "scalar_text",
    "Date": "temporal",
    "Datetime": "temporal",
    "Duration": "scalar_text",
    "Dynamic Link": "dynamic_reference",
    "Float": "numeric",
    "Fold": "layout",
    "Geolocation": "structured",
    "Heading": "layout",
    "HTML": "layout",
    "HTML Editor": "scalar_text",
    "Icon": "scalar_text",
    "Image": "layout",
    "Int": "integer",
    "JSON": "structured",
    "Link": "reference",
    "Long Text": "scalar_text",
    "Markdown Editor": "scalar_text",
    "Password": "specialized",
    "Percent": "numeric",
    "Phone": "scalar_text",
    "Read Only": "system_managed",
    "Rating": "numeric",
    "Section Break": "layout",
    "Select": "predefined_options",
    "Signature": "specialized",
    "Small Text": "scalar_text",
    "Tab Break": "layout",
    "Table": "structured",
    "Table MultiSelect": "structured",
    "Text": "scalar_text",
    "Text Editor": "scalar_text",
    "Time": "temporal",
}


def _field_value(field: Any, fieldname: str, default: Any = None) -> Any:
    if isinstance(field, dict):
        return field.get(fieldname, default)
    getter = getattr(field, "get", None)
    if callable(getter):
        return getter(fieldname, default)
    return getattr(field, fieldname, default)


def _result(
    fieldname: str,
    field: Any,
    path_prefix: str,
    *,
    status: str,
    source: str,
    value: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    result = {
        "status": status,
        "path": f"{path_prefix}.{fieldname}",
        "fieldname": fieldname,
        "fieldtype": _field_value(field, "fieldtype") or "Unknown",
        "source": source,
    }
    if status == "resolved":
        result["value"] = value
    return {**result, **extra}


def classify_fieldtype(fieldtype: str | None) -> str:
    """Return the installed-Frappe behavior family, or a safe unknown category."""
    return FIELD_TYPE_CATEGORIES.get(fieldtype or "", "unsupported")


def _resolve_select(
    fieldname: str, field: Any, path_prefix: str, value: Any, source: str
) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return _result(
            fieldname,
            field,
            path_prefix,
            status="invalid_value",
            source=source,
            input=value,
            allowed_values=[],
        )
    options = [
        option.strip()
        for option in str(_field_value(field, "options") or "").splitlines()
        if option.strip()
    ]
    candidates = rank_candidates(
        value,
        [{"value": option, "label": option} for option in options],
        ("value", "label"),
    )
    resolution = resolve_ranked_candidates(value, candidates)
    if resolution["status"] == "resolved":
        return _result(
            fieldname,
            field,
            path_prefix,
            status="resolved",
            source=source,
            value=resolution["candidate"]["value"],
            input=value,
        )
    if resolution["status"] == "ambiguous" and any(
        normalize(value) in normalize(candidate["value"])
        for candidate in resolution["candidates"]
    ):
        return _result(
            fieldname,
            field,
            path_prefix,
            status="needs_selection",
            source=source,
            query=value,
            candidates=resolution["candidates"],
        )
    return _result(
        fieldname,
        field,
        path_prefix,
        status="invalid_value",
        source=source,
        input=value,
        allowed_values=options,
    )


def _resolve_link(
    fieldname: str,
    field: Any,
    path_prefix: str,
    value: Any,
    source: str,
    *,
    target_doctype: str,
    filters: dict[str, Any],
    get_list: Any,
) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return _result(
            fieldname,
            field,
            path_prefix,
            status="invalid_value",
            source=source,
            input=value,
            target_doctype=target_doctype,
        )
    resolution = resolve_candidate(
        target_doctype,
        value.strip(),
        filters,
        ("name",),
        ("name",),
        get_list=get_list,
    )
    if resolution["status"] == "resolved":
        return _result(
            fieldname,
            field,
            path_prefix,
            status="resolved",
            source=source,
            value=resolution["candidate"]["value"],
            input=value,
            target_doctype=target_doctype,
        )
    if resolution["status"] == "ambiguous":
        return _result(
            fieldname,
            field,
            path_prefix,
            status="needs_selection",
            source=source,
            query=value,
            target_doctype=target_doctype,
            candidates=resolution["candidates"],
        )
    # Permission-scoped candidate lookup intentionally does not distinguish an
    # inaccessible record from a record that does not exist.
    return _result(
        fieldname,
        field,
        path_prefix,
        status="not_found",
        source=source,
        query=value,
        target_doctype=target_doctype,
        candidates=[],
    )


def _resolve_boolean(
    fieldname: str, field: Any, path_prefix: str, value: Any, source: str
) -> dict[str, Any]:
    if (
        value is True
        or value in (1, "1")
        or (isinstance(value, str) and value.casefold() == "true")
    ):
        return _result(
            fieldname,
            field,
            path_prefix,
            status="resolved",
            source=source,
            value=1,
            input=value,
        )
    if (
        value is False
        or value in (0, "0")
        or (isinstance(value, str) and value.casefold() == "false")
    ):
        return _result(
            fieldname,
            field,
            path_prefix,
            status="resolved",
            source=source,
            value=0,
            input=value,
        )
    return _result(
        fieldname,
        field,
        path_prefix,
        status="invalid_value",
        source=source,
        input=value,
    )


def _resolve_scalar(
    fieldname: str, field: Any, path_prefix: str, value: Any, source: str, category: str
) -> dict[str, Any]:
    if category == "scalar_text":
        if not isinstance(value, str) or not (normalized := value.strip()):
            return _result(
                fieldname,
                field,
                path_prefix,
                status="invalid_value",
                source=source,
                input=value,
            )
        return _result(
            fieldname,
            field,
            path_prefix,
            status="resolved",
            source=source,
            value=normalized,
            input=value,
        )
    if category == "integer":
        if isinstance(value, bool):
            return _result(
                fieldname,
                field,
                path_prefix,
                status="invalid_value",
                source=source,
                input=value,
            )
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return _result(
                fieldname,
                field,
                path_prefix,
                status="invalid_value",
                source=source,
                input=value,
            )
        if isinstance(value, float) and not value.is_integer():
            return _result(
                fieldname,
                field,
                path_prefix,
                status="invalid_value",
                source=source,
                input=value,
            )
        return _result(
            fieldname,
            field,
            path_prefix,
            status="resolved",
            source=source,
            value=normalized,
            Finput=value,
        )
    if category == "numeric":
        if isinstance(value, bool):
            return _result(
                fieldname,
                field,
                path_prefix,
                status="invalid_value",
                source=source,
                input=value,
            )
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            return _result(
                fieldname,
                field,
                path_prefix,
                status="invalid_value",
                source=source,
                input=value,
            )
        if not math.isfinite(normalized):
            return _result(
                fieldname,
                field,
                path_prefix,
                status="invalid_value",
                source=source,
                input=value,
            )
        return _result(
            fieldname,
            field,
            path_prefix,
            status="resolved",
            source=source,
            value=normalized,
            input=value,
        )
    if category == "structured" and _field_value(field, "fieldtype") == "JSON":
        if isinstance(value, (dict, list)):
            return _result(
                fieldname,
                field,
                path_prefix,
                status="resolved",
                source=source,
                value=value,
                input=value,
            )
        if isinstance(value, str):
            try:
                normalized = json.loads(value)
            except ValueError:
                return _result(
                    fieldname,
                    field,
                    path_prefix,
                    status="invalid_value",
                    source=source,
                    input=value,
                )
            return _result(
                fieldname,
                field,
                path_prefix,
                status="resolved",
                source=source,
                value=normalized,
                input=value,
            )
    return _result(
        fieldname,
        field,
        path_prefix,
        status="unsupported_field",
        source=source,
        input=value,
        category=category,
    )


def resolve_field_value(
    *,
    fieldname: str,
    field: Any,
    path_prefix: str,
    value: Any,
    source: str,
    resolved_values: dict[str, Any],
    link_filters: dict[str, Any],
    get_list: Any,
) -> dict[str, Any]:
    """Resolve one configured value according to its runtime DocField metadata."""
    if not field:
        return {
            "status": "unsupported_field",
            "path": f"{path_prefix}.{fieldname}",
            "fieldname": fieldname,
            "fieldtype": "Unknown",
            "source": source,
            "input": value,
            "category": "missing_metadata",
        }
    fieldtype = _field_value(field, "fieldtype") or "Unknown"
    category = classify_fieldtype(fieldtype)
    if category == "reference":
        target_doctype = _field_value(field, "options")
        if not isinstance(target_doctype, str) or not target_doctype.strip():
            return _result(
                fieldname,
                field,
                path_prefix,
                status="unsupported_field",
                source=source,
                input=value,
                category=category,
            )
        return _resolve_link(
            fieldname,
            field,
            path_prefix,
            value,
            source,
            target_doctype=target_doctype,
            filters=link_filters,
            get_list=get_list,
        )
    if category == "dynamic_reference":
        controller = _field_value(field, "options")
        target_doctype = (
            resolved_values.get(controller) if isinstance(controller, str) else None
        )
        if not target_doctype:
            return _result(
                fieldname,
                field,
                path_prefix,
                status="unresolved_dependency",
                source=source,
                input=value,
                controller_field=controller,
            )
        if not isinstance(target_doctype, str):
            return _result(
                fieldname,
                field,
                path_prefix,
                status="invalid_value",
                source=source,
                input=value,
            )
        return _resolve_link(
            fieldname,
            field,
            path_prefix,
            value,
            source,
            target_doctype=target_doctype,
            filters=link_filters,
            get_list=get_list,
        )
    if category == "predefined_options":
        return _resolve_select(fieldname, field, path_prefix, value, source)
    if category == "boolean":
        return _resolve_boolean(fieldname, field, path_prefix, value, source)
    return _resolve_scalar(fieldname, field, path_prefix, value, source, category)


def resolve_contract_values(
    *,
    contract: dict[str, Any],
    creation_fields: tuple[str, ...],
    path_prefix: str,
    reference_filters: dict[str, dict[str, Any]],
    get_list: Any,
) -> dict[str, Any]:
    """Resolve all populated fields of one creation contract without storing state."""
    values = dict(contract["values"])
    field_results = []
    for fieldname in dict.fromkeys(creation_fields):
        if fieldname not in values:
            continue
        result = resolve_field_value(
            fieldname=fieldname,
            field=contract["fields"].get(fieldname),
            path_prefix=path_prefix,
            value=values[fieldname],
            source=contract["sources"][fieldname],
            resolved_values=values,
            link_filters=reference_filters.get(fieldname, {}),
            get_list=get_list,
        )
        field_results.append(result)
        if result["status"] != "resolved":
            return result
        values[fieldname] = result["value"]
    return {"status": "resolved", "values": values, "field_results": field_results}
