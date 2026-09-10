"""Bounded Item preflight knowledge for the optional India Compliance app."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from ..common.effective_requirements import (
	EffectiveRequirement,
	EffectiveRequirementContext,
	RequirementResult,
	RequirementStatus,
)

logger = logging.getLogger(__name__)

_APP_NAME = "india_compliance"
_HSN_FIELDNAME = "gst_hsn_code"
_HSN_FIELD_LABEL = "HSN/SAC"
_HSN_DOCTYPE = "GST HSN Code"
_ITEM_GROUP_FETCH_FROM = "item_group.gst_hsn_code"
_VALID_HSN_LENGTHS = (4, 6, 8)


def _field_value(field: Any, fieldname: str, default: Any = None) -> Any:
	if isinstance(field, Mapping):
		return field.get(fieldname, default)
	getter = getattr(field, "get", None)
	if callable(getter):
		return getter(fieldname, default)
	return getattr(field, fieldname, default)


def _is_truthy(value: Any) -> bool:
	if value is True or value == 1 or value == "1":
		return True
	if isinstance(value, str):
		return value.strip().casefold() == "true"
	return False


def _requirement(*, reason: str, guidance: str) -> EffectiveRequirement:
	return EffectiveRequirement(
		doctype="Item",
		fieldname=_HSN_FIELDNAME,
		label=_HSN_FIELD_LABEL,
		reason=reason,
		guidance=guidance,
	)


def _lengths(min_hsn_digits: Any) -> tuple[int, ...] | None:
	try:
		minimum = int(min_hsn_digits)
	except (TypeError, ValueError):
		return None
	accepted = tuple(length for length in _VALID_HSN_LENGTHS if length >= minimum)
	return accepted or None


def _length_guidance(lengths: tuple[int, ...]) -> str:
	joined = ", ".join(str(length) for length in lengths)
	return f"Provide the HSN/SAC code for this sales Item. Accepted lengths: {joined} digits."


def _unavailable(reason: str) -> RequirementResult:
	return RequirementResult(status=RequirementStatus.UNAVAILABLE, reason=reason)


def _read_settings(context: EffectiveRequirementContext) -> RequirementResult | tuple[bool, tuple[int, ...]]:
	if context.get_cached_value is None:
		return _unavailable("gst_settings_api_unavailable")
	try:
		settings = context.get_cached_value(
			"GST Settings",
			"GST Settings",
			("validate_hsn_code", "min_hsn_digits"),
		)
	except Exception:
		logger.exception("Unable to read GST Settings during Item preparation")
		return _unavailable("gst_settings_unavailable")
	if not isinstance(settings, (tuple, list)) or len(settings) != 2:
		return _unavailable("gst_settings_incomplete")
	validate_hsn_code, min_hsn_digits = settings
	if validate_hsn_code is None:
		return _unavailable("gst_settings_validation_value_unavailable")
	if not _is_truthy(validate_hsn_code):
		return False, ()
	accepted_lengths = _lengths(min_hsn_digits)
	if accepted_lengths is None:
		return _unavailable("gst_settings_minimum_unavailable")
	return True, accepted_lengths


def _read_item_group_hsn(
	context: EffectiveRequirementContext, item_group: Any
) -> tuple[str | None, str | None]:
	"""Read only the configured fetch source with normal list permissions."""
	if not isinstance(item_group, str) or not item_group.strip():
		return None, None
	try:
		group_meta = context.get_meta("Item Group")
		group_fields_metadata = getattr(group_meta, "fields", None)
		if group_fields_metadata is None and isinstance(group_meta, Mapping):
			group_fields_metadata = group_meta.get("fields", [])
		group_fields = {
			_field_value(field, "fieldname"): field
			for field in group_fields_metadata or []
			if _field_value(field, "fieldname")
		}
		if _HSN_FIELDNAME not in group_fields:
			return None, None
		rows = context.get_list(
			"Item Group",
			filters={"name": item_group},
			fields=["name", _HSN_FIELDNAME],
			limit_page_length=1,
			ignore_permissions=False,
		)
	except Exception:
		logger.exception("Unable to read Item Group HSN during Item preparation")
		return None, "item_group_hsn_unavailable"
	if not rows:
		return None, "item_group_hsn_unavailable"
	value = rows[0].get(_HSN_FIELDNAME)
	if not isinstance(value, str):
		return None, None
	return value.strip() or None, None


def india_compliance_item_preflight(
	context: EffectiveRequirementContext,
) -> RequirementResult:
	"""Surface only the source-confirmed conditional HSN/SAC requirement."""
	if context.doctype != "Item":
		return RequirementResult(status=RequirementStatus.NOT_APPLICABLE)
	try:
		installed_apps = context.get_installed_apps() or ()
	except Exception:
		logger.exception("Unable to inspect installed apps during Item preparation")
		return _unavailable("installed_app_discovery_unavailable")
	if _APP_NAME not in installed_apps:
		return RequirementResult(status=RequirementStatus.NOT_APPLICABLE)

	hsn_field = context.fields.get(_HSN_FIELDNAME)
	if (
		not hsn_field
		or _field_value(hsn_field, "fieldtype") != "Link"
		or _field_value(hsn_field, "options") != _HSN_DOCTYPE
	):
		return RequirementResult(status=RequirementStatus.NOT_APPLICABLE)
	if not _is_truthy(context.values.get("is_sales_item")):
		return RequirementResult(status=RequirementStatus.NOT_APPLICABLE)

	settings = _read_settings(context)
	if isinstance(settings, RequirementResult):
		return settings
	validation_enabled, accepted_lengths = settings
	if not validation_enabled:
		return RequirementResult(status=RequirementStatus.NOT_APPLICABLE)

	raw_value = context.input_values.get(_HSN_FIELDNAME)
	if _HSN_FIELDNAME in context.input_values and raw_value not in (None, ""):
		if not isinstance(raw_value, str):
			return RequirementResult(
				status=RequirementStatus.INVALID,
				requirement=_requirement(
					reason="invalid_value",
					guidance=_length_guidance(accepted_lengths),
				),
			)
		hsn_value = raw_value.strip()
		if not hsn_value:
			return RequirementResult(
				status=RequirementStatus.MISSING,
				requirement=_requirement(
					reason="conditional_mandatory",
					guidance=_length_guidance(accepted_lengths),
				),
			)
	else:
		can_inherit = (
			_field_value(hsn_field, "fetch_from") == _ITEM_GROUP_FETCH_FROM
			and _is_truthy(_field_value(hsn_field, "fetch_if_empty"))
		)
		if not can_inherit:
			hsn_value = None
			read_error = None
		else:
			hsn_value, read_error = _read_item_group_hsn(
				context,
				context.values.get("item_group"),
			)
		if read_error:
			return _unavailable(read_error)
		if not hsn_value:
			return RequirementResult(
				status=RequirementStatus.MISSING,
				requirement=_requirement(
					reason="conditional_mandatory",
					guidance=_length_guidance(accepted_lengths),
				),
			)

	if len(hsn_value) not in accepted_lengths:
		return RequirementResult(
			status=RequirementStatus.INVALID,
			requirement=_requirement(
				reason="invalid_value",
				guidance=_length_guidance(accepted_lengths),
			),
		)
	return RequirementResult(
		status=RequirementStatus.SATISFIED,
		values={_HSN_FIELDNAME: hsn_value},
	)
