from __future__ import annotations

import unittest
from unittest.mock import patch

from mcp_erpnext.services.common.write_policy import (
    approval_entry_failure,
    current_mode,
    direct_entry_failure,
    exact_mode_failure,
)
from mcp_erpnext.settings import WriteMode


class SharedWritePolicyTests(unittest.TestCase):
    def test_create_policy_failures_are_stable_for_each_entry_path(self):
        with patch.dict("os.environ", {"MCP_CREATE_MODE": "disabled"}, clear=True):
            self.assertEqual(
                direct_entry_failure("create").code, "CREATE_DISABLED"
            )
            self.assertEqual(
                approval_entry_failure("create").code, "CREATE_DISABLED"
            )
        with patch.dict("os.environ", {"MCP_CREATE_MODE": "direct"}, clear=True):
            self.assertIsNone(direct_entry_failure("create"))
            self.assertEqual(
                approval_entry_failure("create").code,
                "DIRECT_EXECUTION_REQUIRED",
            )
        with patch.dict(
            "os.environ", {"MCP_CREATE_MODE": "approval_required"}, clear=True
        ):
            self.assertIsNone(approval_entry_failure("create"))
            self.assertEqual(
                direct_entry_failure("create").code, "APPROVAL_REQUIRED"
            )

    def test_final_boundary_requires_exact_current_mode(self):
        with patch.dict("os.environ", {"MCP_CREATE_MODE": "direct"}, clear=True):
            self.assertIsNone(exact_mode_failure("create", WriteMode.DIRECT))
            self.assertEqual(
                exact_mode_failure("create", WriteMode.APPROVAL_REQUIRED).code,
                "DIRECT_EXECUTION_REQUIRED",
            )
        with patch.dict("os.environ", {"MCP_CREATE_MODE": "disabled"}, clear=True):
            self.assertEqual(
                exact_mode_failure("create", WriteMode.DIRECT).code,
                "CREATE_DISABLED",
            )

    def test_child_mutations_share_update_policy(self):
        with patch.dict("os.environ", {"MCP_UPDATE_MODE": "direct"}, clear=True):
            self.assertEqual(current_mode("child_add"), WriteMode.DIRECT)
            self.assertEqual(current_mode("child_remove"), WriteMode.DIRECT)


if __name__ == "__main__":
    unittest.main()
