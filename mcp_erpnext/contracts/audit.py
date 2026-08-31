"""Generic guard for the public MCP tool-contract standard."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .registry import FROZEN_LEGACY_TOOL_NAMES, TOOL_CONTRACTS, ToolContract


_RUNTIME_FIELD_TERMS = (
	"ctx",
	"context",
	"frappe_user",
	"frappe_session",
	"librechat_user",
	"authorization",
	"bearer",
	"run_as",
	"role",
	"credential",
	"secret",
)


def _has_untyped_object(schema: Any) -> bool:
	if isinstance(schema, list):
		return any(_has_untyped_object(value) for value in schema)
	if not isinstance(schema, dict):
		return False
	if schema.get("type") == "object" and not schema.get("properties") and "additionalProperties" in schema:
		return True
	return any(_has_untyped_object(value) for value in schema.values())


def _visible_runtime_field(schema: dict[str, Any]) -> str | None:
	for field in schema.get("properties", {}):
		if field.lower() in _RUNTIME_FIELD_TERMS:
			return field
	return None


def _declared_statuses(schema: Any) -> set[str]:
	"""Collect literal status values from a generated input or output schema."""
	if isinstance(schema, list):
		return set().union(*(_declared_statuses(value) for value in schema))
	if not isinstance(schema, dict):
		return set()
	statuses = set()
	properties = schema.get("properties")
	if isinstance(properties, dict) and isinstance(properties.get("status"), dict):
		status_schema = properties["status"]
		value = status_schema.get("const")
		if isinstance(value, str):
			statuses.add(value)
		statuses.update(value for value in status_schema.get("enum", []) if isinstance(value, str))
	for value in schema.values():
		statuses.update(_declared_statuses(value))
	return statuses


def audit_tool_contracts(
	tools: Iterable[Any], contracts: dict[str, ToolContract] = TOOL_CONTRACTS
) -> list[str]:
	"""Return policy violations for the registered public MCP tool inventory."""
	issues: list[str] = []
	registered = {tool.name: tool for tool in tools}
	if set(registered) != set(contracts):
		issues.append("Registered tools and declared contract inventory differ.")
	for name, contract in contracts.items():
		if contract.legacy != (name in FROZEN_LEGACY_TOOL_NAMES):
			issues.append(f"{name}: legacy status differs from the frozen legacy inventory.")
		if contract.side_effect.value == "CONFIRM_WRITE" and not contract.approval_guard:
			issues.append(f"{name}: CONFIRM_WRITE tool lacks a shared approval guard.")
		tool = registered.get(name)
		if tool is None:
			continue
		if not getattr(tool, "description", "").strip():
			issues.append(f"{name}: missing public description.")
		input_schema = getattr(tool, "inputSchema", None)
		if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
			issues.append(f"{name}: missing explicit input schema.")
			continue
		if runtime_field := _visible_runtime_field(input_schema):
			issues.append(f"{name}: runtime-only field {runtime_field!r} is model-visible.")
		meta = getattr(tool, "meta", None) or getattr(tool, "_meta", None) or {}
		if contract.side_effect.value == "CONFIRM_WRITE" and meta.get("mcp_erpnext", {}).get(
			"approval_guard"
		) != contract.approval_guard:
			issues.append(f"{name}: approval-guard classification is missing from public metadata.")
		if contract.legacy:
			continue
		if not contract.compliant:
			issues.append(f"{name}: non-legacy tool lacks explicit input or output contract models.")
		if _has_untyped_object(input_schema):
			issues.append(f"{name}: input schema contains an arbitrary object.")
		if not getattr(tool, "outputSchema", None):
			issues.append(f"{name}: typed output contract is not published as outputSchema.")
		if contract.operation.value == "RESOLVE" or contract.resolution_states:
			if not contract.resolution_states:
				issues.append(f"{name}: resolver contract does not declare supported resolution states.")
			elif not set(contract.resolution_states).issubset(_declared_statuses(tool.outputSchema)):
				issues.append(f"{name}: output schema does not expose every declared resolution state.")
		meta = getattr(tool, "meta", None) or getattr(tool, "_meta", None) or {}
		if meta.get("mcp_erpnext", {}).get("side_effect") != contract.side_effect.value:
			issues.append(f"{name}: side-effect classification is missing from public metadata.")
		if contract.resolution_states and meta.get("mcp_erpnext", {}).get("resolution_states") != list(
			contract.resolution_states
		):
			issues.append(f"{name}: resolution-state metadata is missing from public metadata.")
	return issues
