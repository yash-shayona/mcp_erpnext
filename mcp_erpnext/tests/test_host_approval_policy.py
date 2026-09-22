from __future__ import annotations

import unittest

from mcp_erpnext.contracts.host_approval_policy import (
	prepare_override_contract_issues,
	prepare_tool_names,
	render_prepare_approval_overrides,
)
from mcp_erpnext.contracts.registry import SideEffectClass, TOOL_CONTRACTS


class HostApprovalPolicyTests(unittest.TestCase):
	def test_prepare_override_set_exactly_matches_the_contract_registry(self):
		prepare_names = prepare_tool_names()
		self.assertEqual(
			set(prepare_names),
			{
				name
				for name, contract in TOOL_CONTRACTS.items()
				if contract.side_effect is SideEffectClass.PREPARE
			},
		)
		self.assertEqual(prepare_names, tuple(sorted(prepare_names)))
		self.assertNotIn(
			SideEffectClass.CONFIRM_WRITE,
			{TOOL_CONTRACTS[name].side_effect for name in prepare_names},
		)

	def test_prepare_auto_approval_targets_are_non_final_and_paired_with_guarded_confirms(self):
		self.assertEqual(prepare_override_contract_issues(), [])
		for name in prepare_tool_names():
			with self.subTest(name=name):
				contract = TOOL_CONTRACTS[name]
				annotations = contract.mcp_annotations()
				self.assertFalse(annotations.destructiveHint)
				self.assertFalse(annotations.openWorldHint)
				confirm = TOOL_CONTRACTS[contract.approval_confirm_tool or ""]
				self.assertIs(confirm.side_effect, SideEffectClass.CONFIRM_WRITE)
				self.assertTrue(confirm.approval_guard)

	def test_rendered_policy_contains_only_the_contract_derived_prepare_overrides(self):
		content = render_prepare_approval_overrides("erpnext-sales-public")
		self.assertIn('default_tools_approval_mode = "writes"', content)
		self.assertNotIn("[mcp_servers.erpnext-sales-public]", content)
		for name in prepare_tool_names():
			with self.subTest(name=name):
				self.assertIn(
					f'[mcp_servers."erpnext-sales-public".tools."{name}"]',
					content,
				)
		for name, contract in TOOL_CONTRACTS.items():
			if contract.side_effect is SideEffectClass.CONFIRM_WRITE:
				self.assertNotIn(f'.tools."{name}"]', content)

	def test_renderer_rejects_a_blank_server_id(self):
		with self.assertRaisesRegex(ValueError, "server_id"):
			render_prepare_approval_overrides("  ")


if __name__ == "__main__":
	unittest.main()
