from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mcp_erpnext.settings import ApprovalMode, MCPSettings


class SettingsTests(unittest.TestCase):
	@patch.dict(
		os.environ,
		{"MCP_BACKEND": "direct", "MCP_FRAPPE_SITE": "test.localhost"},
		clear=True,
	)
	def test_approval_mode_defaults_to_agent_delegated(self):
		self.assertEqual(MCPSettings.from_environment().approval_mode, ApprovalMode.AGENT_DELEGATED)

	@patch.dict(
		os.environ,
		{
			"MCP_BACKEND": "direct",
			"MCP_FRAPPE_SITE": "test.localhost",
			"MCP_APPROVAL_MODE": "agent_delegated",
		},
		clear=True,
	)
	def test_agent_delegated_approval_mode_is_accepted(self):
		self.assertEqual(MCPSettings.from_environment().approval_mode, ApprovalMode.AGENT_DELEGATED)

	@patch.dict(
		os.environ,
		{
			"MCP_BACKEND": "direct",
			"MCP_FRAPPE_SITE": "test.localhost",
			"MCP_APPROVAL_MODE": "trusted_human",
		},
		clear=True,
	)
	def test_trusted_human_approval_mode_requires_explicit_configuration(self):
		self.assertEqual(MCPSettings.from_environment().approval_mode, ApprovalMode.TRUSTED_HUMAN)

	@patch.dict(
		os.environ,
		{
			"MCP_BACKEND": "direct",
			"MCP_FRAPPE_SITE": "test.localhost",
			"MCP_APPROVAL_MODE": "unsafe",
		},
		clear=True,
	)
	def test_invalid_approval_mode_fails_deterministically(self):
		with self.assertRaisesRegex(RuntimeError, "MCP_APPROVAL_MODE"):
			MCPSettings.from_environment()

	@patch.dict(
		os.environ,
		{"MCP_BACKEND": "direct", "MCP_FRAPPE_SITE": "test.localhost"},
		clear=True,
	)
	def test_stdio_keeps_the_configured_development_user(self):
		self.assertIsNone(MCPSettings.from_environment().frappe_user)
