"""Contract-derived Codex host approval-policy helpers.

The MCP host policy is client configuration, not ERPNext business approval.
This module only identifies the non-final-write PREPARE tools eligible for an
explicit host override.  ``ToolContract`` remains the source of truth.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from .registry import SideEffectClass, TOOL_CONTRACTS, ToolContract


def prepare_tool_names(
	contracts: Mapping[str, ToolContract] = TOOL_CONTRACTS,
) -> tuple[str, ...]:
	"""Return the complete, stable-order PREPARE override set."""
	return tuple(
		sorted(
			name
			for name, contract in contracts.items()
			if contract.side_effect is SideEffectClass.PREPARE
		)
	)


def prepare_override_contract_issues(
	contracts: Mapping[str, ToolContract] = TOOL_CONTRACTS,
) -> list[str]:
	"""Return contract-policy violations before rendering host overrides.

	A host ``approve`` override is permitted only for prepared-operation tools.
	The paired final tool must remain a guarded CONFIRM_WRITE tool, and the
	prepare step must not advertise open-world or destructive semantics.
	"""
	issues: list[str] = []
	for name in prepare_tool_names(contracts):
		contract = contracts[name]
		annotations = contract.mcp_annotations()
		if contract.side_effect is not SideEffectClass.PREPARE:
			issues.append(f"{name}: host auto-approval target is not PREPARE.")
		if annotations.openWorldHint:
			issues.append(f"{name}: PREPARE override advertises open-world effects.")
		if annotations.destructiveHint:
			issues.append(f"{name}: PREPARE override advertises destructive effects.")
		confirm_name = contract.approval_confirm_tool
		confirm_contract = contracts.get(confirm_name or "")
		if (
			confirm_contract is None
			or confirm_contract.side_effect is not SideEffectClass.CONFIRM_WRITE
			or not confirm_contract.approval_guard
		):
			issues.append(
				f"{name}: PREPARE override lacks a guarded CONFIRM_WRITE counterpart."
			)
	return issues


def render_prepare_approval_overrides(
	server_id: str,
	contracts: Mapping[str, ToolContract] = TOOL_CONTRACTS,
) -> str:
	"""Render append-only TOML tables for Policy B's PREPARE overrides.

	``server_id`` is rendered as a quoted TOML key, allowing an operator to use
	the exact existing MCP-server ID without duplicating its parent table.
	"""
	if not server_id.strip():
		raise ValueError("server_id must not be blank.")
	if issues := prepare_override_contract_issues(contracts):
		raise ValueError("\n".join(issues))
	quoted_server_id = json.dumps(server_id)
	lines = [
		"# Generated from mcp_erpnext ToolContract.side_effect == PREPARE.",
		"# Add default_tools_approval_mode = \"writes\" to the existing server table first.",
		"# Append these child tables; do not duplicate [mcp_servers.<server-id>].",
	]
	for name in prepare_tool_names(contracts):
		lines.extend(
			[
				"",
				f"[mcp_servers.{quoted_server_id}.tools.{json.dumps(name)}]",
				'approval_mode = "approve"',
			]
		)
	return "\n".join(lines) + "\n"
