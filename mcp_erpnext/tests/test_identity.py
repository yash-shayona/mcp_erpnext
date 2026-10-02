from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mcp_erpnext.settings import ApprovalMode, LifecycleActionMode, MCPSettings


class SettingsTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"MCP_BACKEND": "direct", "MCP_FRAPPE_SITE": "test.localhost"},
        clear=True,
    )
    def test_approval_mode_defaults_to_agent_delegated(self):
        self.assertEqual(
            MCPSettings.from_environment().approval_mode, ApprovalMode.AGENT_DELEGATED
        )

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
        self.assertEqual(
            MCPSettings.from_environment().approval_mode, ApprovalMode.AGENT_DELEGATED
        )

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
        self.assertEqual(
            MCPSettings.from_environment().approval_mode, ApprovalMode.TRUSTED_HUMAN
        )

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
    def test_lifecycle_action_modes_default_to_disabled(self):
        settings = MCPSettings.from_environment()
        self.assertEqual(settings.update_mode, LifecycleActionMode.DISABLED)
        self.assertEqual(settings.cancel_mode, LifecycleActionMode.DISABLED)
        self.assertEqual(settings.delete_mode, LifecycleActionMode.DISABLED)

    @patch.dict(
        os.environ,
        {
            "MCP_UPDATE_MODE": " APPROVAL_REQUIRED ",
            "MCP_CANCEL_MODE": " APPROVAL_REQUIRED ",
            "MCP_DELETE_MODE": "disabled",
        },
        clear=True,
    )
    def test_lifecycle_action_modes_are_normalized_and_independent(self):
        settings = MCPSettings.from_environment()
        self.assertEqual(settings.update_mode, LifecycleActionMode.APPROVAL_REQUIRED)
        self.assertEqual(settings.cancel_mode, LifecycleActionMode.APPROVAL_REQUIRED)
        self.assertEqual(settings.delete_mode, LifecycleActionMode.DISABLED)

    @patch.dict(
        os.environ,
        {
            "MCP_UPDATE_MODE": "direct",
            "MCP_CANCEL_MODE": "direct",
            "MCP_DELETE_MODE": "approval_required",
        },
        clear=True,
    )
    def test_direct_write_mode_is_accepted(self):
        settings = MCPSettings.from_environment()
        self.assertEqual(settings.update_mode, LifecycleActionMode.DIRECT)
        self.assertEqual(settings.cancel_mode, LifecycleActionMode.DIRECT)
        self.assertEqual(settings.delete_mode, LifecycleActionMode.APPROVAL_REQUIRED)

    def test_empty_or_unknown_lifecycle_action_mode_is_rejected(self):
        for environment_name, value in (
            ("MCP_UPDATE_MODE", ""),
            ("MCP_UPDATE_MODE", "unknown"),
            ("MCP_CANCEL_MODE", ""),
            ("MCP_CANCEL_MODE", "allow"),
            ("MCP_DELETE_MODE", "   "),
            ("MCP_DELETE_MODE", "unknown"),
        ):
            with self.subTest(environment_name=environment_name, value=value):
                with (
                    patch.dict(os.environ, {environment_name: value}, clear=True),
                    self.assertRaisesRegex(RuntimeError, environment_name),
                ):
                    MCPSettings.from_environment()

    def test_manually_constructed_invalid_lifecycle_mode_is_rejected(self):
        settings = MCPSettings(
            backend="direct",
            frappe_site="test.localhost",
            frappe_user="mcp@example.com",
            erpnext_base_url=None,
            erpnext_api_key=None,
            erpnext_api_secret=None,
            update_mode="unsafe",
        )
        with self.assertRaisesRegex(RuntimeError, "MCP_UPDATE_MODE"):
            settings.validate_lifecycle_action_modes()

    @patch.dict(
        os.environ,
        {"MCP_BACKEND": "direct", "MCP_FRAPPE_SITE": "test.localhost"},
        clear=True,
    )
    def test_stdio_keeps_the_configured_development_user(self):
        self.assertIsNone(MCPSettings.from_environment().frappe_user)

    @patch.dict(
        os.environ,
        {
            "MCP_BACKEND": "direct",
            "MCP_FRAPPE_SITE": "test.localhost",
            "MCP_FRAPPE_USER": "stdio@example.com",
        },
        clear=True,
    )
    def test_stdio_user_environment_name_is_backward_compatible(self):
        self.assertEqual(
            MCPSettings.from_environment().frappe_user, "stdio@example.com"
        )
