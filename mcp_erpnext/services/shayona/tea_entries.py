"""Permission-aware, fixed-projection Tea Entry reads and governed creation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe
from frappe.model.create_new import make_new_doc, set_dynamic_default_values

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...contracts.shayona.tea_entries import (
    TeaEntryCreateInput,
    TeaEntryCreatePreview,
    TeaEntryUpdateInput,
    TeaEntryUpdatePreview,
    TeaEntryUpdateState,
)
from ...observability import logged_public_error, public_error
from ...settings import WriteMode
from ..common.fingerprint import stable_fingerprint
from ..common.write_policy import (
    approval_entry_failure,
    current_mode,
    disabled_failure,
    direct_entry_failure,
    exact_mode_failure,
)
from ..common.aggregate import (
    build_aggregate_field,
    build_aggregate_fields,
    execute_aggregate,
    shape_aggregate_rows,
)

TEA_ENTRY_DOCTYPE = "Tea Entry"
PUBLIC_FIELDS = (
    "name",
    "date",
    "no_of_cups",
    "rate_per_cup",
    "total_amount",
    "vendor",
)
REQUIRED_FIELDTYPES = {
    "date": "Date",
    "no_of_cups": "Int",
    "rate_per_cup": "Currency",
    "total_amount": "Currency",
    "vendor": "Data",
}
AGGREGATE_METRICS = {
    "count": build_aggregate_field("COUNT", "name", "count"),
    "sum_no_of_cups": build_aggregate_field(
        "SUM", "no_of_cups", "sum_no_of_cups"
    ),
    "sum_total_amount": build_aggregate_field(
        "SUM", "total_amount", "sum_total_amount"
    ),
}
AGGREGATE_GROUP_FIELDS = frozenset({"date", "vendor"})


class TeaEntrySchemaUnavailableError(RuntimeError):
    """Raised when the active site cannot safely serve Tea Entry reads."""


@dataclass(frozen=True)
class TeaEntrySchema:
    public_fields: tuple[str, ...]


def tea_entry_schema(meta: Any | None = None) -> TeaEntrySchema:
    """Validate the live DocType contract without importing the Shayona app."""
    try:
        meta = meta or frappe.get_meta(TEA_ENTRY_DOCTYPE)
        columns = set(meta.get_valid_columns())
        if not set(PUBLIC_FIELDS).issubset(columns):
            raise TeaEntrySchemaUnavailableError()
        for fieldname, expected_type in REQUIRED_FIELDTYPES.items():
            field = meta.get_field(fieldname)
            if field is None or field.fieldtype != expected_type:
                raise TeaEntrySchemaUnavailableError()
    except TeaEntrySchemaUnavailableError:
        raise
    except Exception as error:
        raise TeaEntrySchemaUnavailableError() from error
    return TeaEntrySchema(public_fields=PUBLIC_FIELDS)


def _value(values: Any, fieldname: str) -> Any:
    if isinstance(values, dict):
        return values.get(fieldname)
    return getattr(values, fieldname, None)


def _project(values: Any) -> dict[str, Any]:
    """Return only the frozen public fields; never serialize the whole document."""
    return {field: _value(values, field) for field in PUBLIC_FIELDS}


def _filters(criteria: dict[str, Any]) -> list[list[Any]]:
    filters: list[list[Any]] = []
    if criteria.get("date") is not None:
        filters.append(["date", "=", criteria["date"]])
    if criteria.get("date_from") is not None:
        filters.append(["date", ">=", criteria["date_from"]])
    if criteria.get("date_to") is not None:
        filters.append(["date", "<=", criteria["date_to"]])
    if criteria.get("vendor") is not None:
        filters.append(["vendor", "=", criteria["vendor"]])
    return filters


def _schema_error(tool_name: str) -> dict[str, Any] | None:
    try:
        tea_entry_schema()
    except TeaEntrySchemaUnavailableError:
        return logged_public_error(tool_name, "TEA_ENTRY_SCHEMA_UNAVAILABLE")
    return None


def get_tea_entry(tea_entry_name: str) -> dict[str, Any]:
    if error := _schema_error("get_tea_entry"):
        return error
    try:
        doc = frappe.get_doc(TEA_ENTRY_DOCTYPE, tea_entry_name)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "tea_entry_name": tea_entry_name}
    if not doc.has_permission("read"):
        raise frappe.PermissionError()
    return {"status": "ok", "tea_entry": _project(doc)}


def query_tea_entries(criteria: dict[str, Any]) -> dict[str, Any]:
    if error := _schema_error("query_tea_entries"):
        return error
    sort_order = criteria["sort_order"]
    if sort_order not in {"asc", "desc"}:
        raise ValueError("unsupported Tea Entry sort order")
    rows = frappe.get_list(
        TEA_ENTRY_DOCTYPE,
        filters=_filters(criteria),
        fields=list(PUBLIC_FIELDS),
        order_by=f"date {sort_order}, name {sort_order}",
        limit_start=criteria["offset"],
        limit_page_length=criteria["limit"],
        ignore_permissions=False,
    )
    tea_entries = [_project(row) for row in rows]
    return {
        "status": "ok",
        "tea_entries": tea_entries,
        "count": len(tea_entries),
        "limit": criteria["limit"],
        "offset": criteria["offset"],
    }


def aggregate_tea_entries(criteria: dict[str, Any]) -> dict[str, Any]:
    if error := _schema_error("aggregate_tea_entries"):
        return error
    metrics = criteria["metrics"]
    group_by = criteria.get("group_by")
    if any(metric not in AGGREGATE_METRICS for metric in metrics):
        raise ValueError("unsupported Tea Entry aggregate metric")
    if group_by is not None and group_by not in AGGREGATE_GROUP_FIELDS:
        raise ValueError("unsupported Tea Entry aggregate group")
    fields, groups = build_aggregate_fields(
        metrics,
        AGGREGATE_METRICS,
        group_by=group_by,
    )
    rows = execute_aggregate(
        frappe.get_list,
        TEA_ENTRY_DOCTYPE,
        filters=_filters(criteria),
        fields=fields,
        groups=groups,
    )
    return {
        "status": "ok",
        "metrics": metrics,
        "group_by": group_by,
        "results": shape_aggregate_rows(rows, metrics, group_by=group_by),
    }


_CREATE_ACTION = "create_tea_entry"
_UPDATE_ACTION = "update_tea_entry"


@dataclass(frozen=True)
class TeaEntryPlan:
    # JSON strings keep the effective plan immutable and approval storage bounded.
    values_json: str
    preview_json: str

    def values(self) -> dict[str, Any]:
        return TeaEntryCreateInput.model_validate_json(self.values_json).model_dump()

    def preview(self) -> dict[str, Any]:
        return TeaEntryCreatePreview.model_validate_json(self.preview_json).model_dump()


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or str(user).casefold() == "guest":
        raise frappe.PermissionError()
    return str(user)


def _validated_native_doc(values: dict[str, Any]) -> Any:
    tea_entry_schema()
    _current_user()
    if not frappe.has_permission(TEA_ENTRY_DOCTYPE, "create"):
        raise frappe.PermissionError()
    request = TeaEntryCreateInput.model_validate(values)
    # Frappe's new_doc template caches Today in persistent stdio contexts. Use
    # the same native builders afresh; never substitute an MCP date default.
    defaults = make_new_doc(TEA_ENTRY_DOCTYPE)
    set_dynamic_default_values(defaults, None, None)
    doc = frappe.get_doc(defaults)
    for field, value in request.model_dump(exclude_none=True).items():
        doc.set(field, value)
    doc.check_permission("create")
    # The native controller owns totals and duplicate-date validation. No save hooks.
    doc.run_method("validate")
    return doc


def _native_preview(doc: Any) -> TeaEntryCreatePreview:
    return TeaEntryCreatePreview.model_validate(
        {field: _value(doc, field) for field in PUBLIC_FIELDS if field != "name"}
    )


def _plan_tea_entry(request: dict[str, Any]) -> TeaEntryPlan:
    doc = _validated_native_doc(request)
    preview = _native_preview(doc)
    # Capture the native effective date now, so approval survives midnight unchanged.
    values = TeaEntryCreateInput.model_validate(
        preview.model_dump(exclude={"total_amount"}) | {"vendor": preview.vendor or None}
    )
    return TeaEntryPlan(values.model_dump_json(), preview.model_dump_json())


def _create_error(
    tool: str, error: Exception, *, applying: bool = False, approved: bool = False,
) -> dict[str, Any]:
    if isinstance(error, TeaEntrySchemaUnavailableError):
        return logged_public_error(tool, "TEA_ENTRY_SCHEMA_UNAVAILABLE")
    if isinstance(error, frappe.PermissionError):
        return logged_public_error(tool, "ERP_PERMISSION_DENIED")
    if isinstance(error, (frappe.ValidationError, ValueError)):
        code = "STALE_CONFIRMATION" if approved else "TEA_ENTRY_VALIDATION_FAILED"
        message = (
            "The approved Tea Entry state changed. Prepare it again."
            if approved else "Native Tea Entry validation failed. Review the request."
        )
    else:
        code = "TEA_ENTRY_WRITE_FAILED" if applying else "TEA_ENTRY_VALIDATION_FAILED"
        message = "The Tea Entry operation could not be completed."
    return logged_public_error(tool, code, message=message)


def _apply_tea_entry(plan: TeaEntryPlan, expected_mode: WriteMode) -> dict[str, Any]:
    approved = expected_mode is WriteMode.APPROVAL_REQUIRED
    tool = "confirm_tea_entry" if approved else "execute_tea_entry"
    try:
        doc = _validated_native_doc(plan.values())
        if approved and (
            stable_fingerprint(_native_preview(doc).model_dump()) != stable_fingerprint(plan.preview())
        ):
            frappe.db.rollback()
            return public_error("STALE_CONFIRMATION", message="The approved Tea Entry state changed. Prepare it again.")
        if failure := exact_mode_failure("create", expected_mode):
            frappe.db.rollback()
            return public_error(failure.code, message=failure.message)
        doc.insert(ignore_permissions=False)
        result = {"status": "created", "tea_entry": _project(doc)}
        frappe.db.commit()
        return result
    except Exception as error:
        frappe.db.rollback()
        return _create_error(tool, error, applying=True, approved=approved)


def prepare_tea_entry(request: dict[str, Any]) -> dict[str, Any]:
    if failure := disabled_failure("create"):
        return public_error(failure.code, message=failure.message)
    try:
        plan = _plan_tea_entry(request)
    except Exception as error:
        frappe.db.rollback()
        return _create_error("prepare_tea_entry", error)
    if current_mode("create") is WriteMode.DIRECT:
        return {"status": "preview", "preview": plan.preview()}
    if failure := approval_entry_failure("create"):
        return public_error(failure.code, message=failure.message)
    approvals.prune_expired()
    token = approvals.create(
        action=_CREATE_ACTION, site=frappe.local.site, user=_current_user(),
        payload={"values_json": plan.values_json, "preview_json": plan.preview_json},
    )
    return {
        "status": "ready", "preview": plan.preview(), "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "interaction": approval_directive().model_dump(mode="json"),
    }


def confirm_tea_entry(approval_token: str, confirm: bool) -> dict[str, Any]:
    if failure := approval_entry_failure("create"):
        return public_error(failure.code, message=failure.message)
    user = _current_user()
    if not confirm:
        approvals.cancel(approval_token, action=_CREATE_ACTION, site=frappe.local.site, user=user)
        return public_error("CONFIRMATION_REQUIRED", message="Review the Tea Entry before confirming it.")
    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_CREATE_ACTION, site=frappe.local.site, user=user,
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Tea Entry")
        return public_error(code, message=message, retryable=retryable)
    return _apply_tea_entry(TeaEntryPlan(**approval.payload), WriteMode.APPROVAL_REQUIRED)


def execute_tea_entry(request: dict[str, Any]) -> dict[str, Any]:
    if failure := direct_entry_failure("create"):
        return public_error(failure.code, message=failure.message)
    try:
        plan = _plan_tea_entry(request)
    except Exception as error:
        frappe.db.rollback()
        return _create_error("execute_tea_entry", error)
    return _apply_tea_entry(plan, WriteMode.DIRECT)


@dataclass(frozen=True)
class TeaEntryUpdatePlan:
    request_json: str
    before_json: str
    preview_json: str
    modified: str

    def request(self) -> TeaEntryUpdateInput:
        return TeaEntryUpdateInput.model_validate_json(self.request_json)

    def preview(self) -> dict[str, Any]:
        return TeaEntryUpdatePreview.model_validate_json(self.preview_json).model_dump()


def _update_state(doc: Any) -> TeaEntryUpdateState:
    return TeaEntryUpdateState.model_validate(
        {field: _value(doc, field) for field in PUBLIC_FIELDS if field != "name"}
    )


def _plan_tea_entry_update(request: dict[str, Any]) -> TeaEntryUpdatePlan | dict[str, Any]:
    tea_entry_schema()
    _current_user()
    validated = TeaEntryUpdateInput.model_validate(request)
    try:
        doc = frappe.get_doc(TEA_ENTRY_DOCTYPE, validated.tea_entry_name)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "tea_entry_name": validated.tea_entry_name}
    doc.check_permission("write")
    before = _update_state(doc)
    modified = str(doc.modified)
    for field, value in validated.changes.model_dump(exclude_unset=True).items():
        doc.set(field, value)
    # Preview through the business controller; this recalculates totals and
    # applies the native duplicate-date rule without persisting the document.
    doc.run_method("validate")
    after = _update_state(doc)
    preview = TeaEntryUpdatePreview(
        tea_entry_name=validated.tea_entry_name,
        before=before,
        after=after,
    )
    return TeaEntryUpdatePlan(
        request_json=validated.model_dump_json(exclude_unset=True),
        before_json=before.model_dump_json(),
        preview_json=preview.model_dump_json(),
        modified=modified,
    )


def _update_error(
    tool: str, error: Exception, *, applying: bool = False, stale: bool = False,
) -> dict[str, Any]:
    if isinstance(error, TeaEntrySchemaUnavailableError):
        return logged_public_error(tool, "TEA_ENTRY_SCHEMA_UNAVAILABLE")
    if isinstance(error, frappe.PermissionError):
        return logged_public_error(tool, "ERP_PERMISSION_DENIED")
    if stale:
        return public_error(
            "STALE_CONFIRMATION",
            message="The approved Tea Entry state changed. Prepare it again.",
        )
    if isinstance(error, (frappe.ValidationError, ValueError)):
        return logged_public_error(
            tool,
            "TEA_ENTRY_VALIDATION_FAILED",
            message="Native Tea Entry validation failed. Review the request.",
        )
    code = "TEA_ENTRY_WRITE_FAILED" if applying else "TEA_ENTRY_VALIDATION_FAILED"
    return logged_public_error(tool, code)


def _apply_tea_entry_update(
    plan: TeaEntryUpdatePlan,
    expected_mode: WriteMode,
    *,
    approved: bool = False,
) -> dict[str, Any]:
    tool = "confirm_tea_entry_update" if approved else "execute_tea_entry_update"
    request = plan.request()
    try:
        tea_entry_schema()
        _current_user()
        try:
            doc = frappe.get_doc(TEA_ENTRY_DOCTYPE, request.tea_entry_name)
        except frappe.DoesNotExistError:
            if approved:
                return public_error(
                    "STALE_CONFIRMATION",
                    message="The approved Tea Entry state changed. Prepare it again.",
                )
            return {"status": "not_found", "tea_entry_name": request.tea_entry_name}
        doc.check_permission("write")
        if approved and (
            str(doc.modified) != plan.modified
            or stable_fingerprint(_update_state(doc).model_dump())
            != stable_fingerprint(TeaEntryUpdateState.model_validate_json(plan.before_json).model_dump())
        ):
            frappe.db.rollback()
            return public_error(
                "STALE_CONFIRMATION",
                message="The approved Tea Entry state changed. Prepare it again.",
            )
        for field, value in request.changes.model_dump(exclude_unset=True).items():
            doc.set(field, value)
        doc.run_method("validate")
        if stable_fingerprint(_update_state(doc).model_dump()) != stable_fingerprint(
            TeaEntryUpdatePreview.model_validate_json(plan.preview_json).after.model_dump()
        ):
            frappe.db.rollback()
            if approved:
                return public_error(
                    "STALE_CONFIRMATION",
                    message="The approved Tea Entry state changed. Prepare it again.",
                )
            return public_error(
                "TEA_ENTRY_VALIDATION_FAILED",
                message="Native Tea Entry validation changed the update preview.",
            )
        if failure := exact_mode_failure("update", expected_mode):
            frappe.db.rollback()
            return public_error(failure.code, message=failure.message)
        doc.save(ignore_permissions=False)
        result = {"status": "updated", "tea_entry": _project(doc)}
        frappe.db.commit()
        return result
    except Exception as error:
        frappe.db.rollback()
        return _update_error(tool, error, applying=True, stale=approved)


def prepare_tea_entry_update(request: dict[str, Any]) -> dict[str, Any]:
    if failure := disabled_failure("update"):
        return public_error(failure.code, message=failure.message)
    try:
        plan = _plan_tea_entry_update(request)
    except Exception as error:
        frappe.db.rollback()
        return _update_error("prepare_tea_entry_update", error)
    if isinstance(plan, dict):
        return plan
    if current_mode("update") is WriteMode.DIRECT:
        return {"status": "preview", "preview": plan.preview()}
    if failure := approval_entry_failure("update"):
        return public_error(failure.code, message=failure.message)
    try:
        token = approvals.create(
            action=_UPDATE_ACTION,
            site=frappe.local.site,
            user=_current_user(),
            payload={
                "request_json": plan.request_json,
                "before_json": plan.before_json,
                "preview_json": plan.preview_json,
                "modified": plan.modified,
            },
        )
    except Exception as error:
        return _update_error("prepare_tea_entry_update", error, applying=True)
    return {
        "status": "ready",
        "preview": plan.preview(),
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "interaction": approval_directive().model_dump(mode="json"),
    }


def confirm_tea_entry_update(approval_token: str, confirm: bool) -> dict[str, Any]:
    if failure := approval_entry_failure("update"):
        return public_error(failure.code, message=failure.message)
    user = _current_user()
    if not confirm:
        approvals.cancel(
            approval_token, action=_UPDATE_ACTION, site=frappe.local.site, user=user
        )
        return public_error(
            "CONFIRMATION_REQUIRED",
            message="Review the Tea Entry update before confirming it.",
        )
    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_UPDATE_ACTION, site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Tea Entry update")
        return public_error(code, message=message, retryable=retryable)
    return _apply_tea_entry_update(TeaEntryUpdatePlan(**approval.payload), WriteMode.APPROVAL_REQUIRED, approved=True)


def execute_tea_entry_update(request: dict[str, Any]) -> dict[str, Any]:
    if failure := direct_entry_failure("update"):
        return public_error(failure.code, message=failure.message)
    try:
        plan = _plan_tea_entry_update(request)
    except Exception as error:
        frappe.db.rollback()
        return _update_error("execute_tea_entry_update", error)
    if isinstance(plan, dict):
        return plan
    return _apply_tea_entry_update(plan, WriteMode.DIRECT)
