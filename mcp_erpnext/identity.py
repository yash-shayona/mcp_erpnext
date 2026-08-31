"""Resolve the configured MCP execution identity without authorizing by email."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import frappe

from .observability import ERPAccessNotConfiguredError, MCPIdentityConfigurationError


if TYPE_CHECKING:
	from .settings import MCPSettings
	from .transport_identity import RuntimeIdentity


def resolve_frappe_user_for_runtime(
	settings: MCPSettings, runtime_identity: RuntimeIdentity | None = None
) -> str | None:
	"""Return the service user or the active Frappe user mapped from a LibreChat ID.

	The mapping lookup intentionally happens before ``frappe.set_user``. It is
	limited to the mapping DocType and User identity metadata because no mapped
	Frappe permission context exists yet.
	"""
	if settings.identity_mode == "service":
		if runtime_identity is not None:
			raise MCPIdentityConfigurationError()
		return settings.frappe_user
	if settings.identity_mode != "librechat":
		raise MCPIdentityConfigurationError()

	librechat_user_id = (
		runtime_identity.librechat_user_id
		if runtime_identity is not None
		else settings.librechat_user_id
	)
	librechat_user_id = (librechat_user_id or "").strip()
	if not librechat_user_id:
		raise MCPIdentityConfigurationError()

	frappe_user = frappe.db.get_value(
		"LibreChat User Mapping",
		{"librechat_user_id": librechat_user_id, "enabled": 1},
		"frappe_user",
	)
	if not frappe_user:
		raise ERPAccessNotConfiguredError()

	user = frappe.db.get_value("User", frappe_user, ["name", "enabled"], as_dict=True)
	if (
		not user
		or _field_value(user, "name") in {"Guest", "guest"}
		or not _is_enabled(_field_value(user, "enabled"))
	):
		raise ERPAccessNotConfiguredError()

	return _field_value(user, "name")


def _field_value(record: Any, fieldname: str) -> Any:
	if isinstance(record, dict):
		return record.get(fieldname)
	return getattr(record, fieldname, None)


def _is_enabled(value: Any) -> bool:
	return value not in {None, "", 0, "0", False, "false", "False"}
