# MCP Host Approval Policy & End-to-End Validation V1 — Implementation Report

Date: 2026-09-22

## Summary

Implemented the repository-side preparation for Task 03. The source of truth
for Policy-B host auto-approval is now the existing `ToolContract` registry:
exactly the contracts classified as `PREPARE` render Codex per-tool override
tables. No server-side ERPNext business approval, public schema, tool name,
profile membership, routing instruction, or MCP SDK version was changed.

Desktop/Codex host and connected-deployment evidence is **operator-assisted
pending**. This environment has no authorized access to the user's local
Codex/ChatGPT Desktop config or UI, and no live MCP action was invoked.

## Source and host configuration inspected

- `mcp_erpnext/contracts/registry.py`, `audit.py`, registration, server,
  profiles, approvals, generated catalog, and Task-01/Task-02 reports.
- Current registry inventory: Sales 66, Purchase 21, Accounts 19, and 85 unique
  public contracts. It has 29 `READ`, 4 `RESOLVE`, 26 `PREPARE`, and 26
  `CONFIRM_WRITE` contracts.
- The source default for the server-only `MCP_APPROVAL_MODE` is
  `agent_delegated`; the effective deployed environment value was intentionally
  not read. This task does not pass, expose, or modify that setting.
- Official OpenAI Codex MCP/config documentation was re-verified on 2026-09-22.
  It documents `mcp_servers.<id>.default_tools_approval_mode` and
  `mcp_servers.<id>.tools.<tool>.approval_mode` with `auto`, `prompt`,
  `writes`, and `approve`; `writes` prompts for non-read-only tools. It also
  confirms shared configuration for ChatGPT Desktop, Codex CLI, and the IDE
  extension.
- Effective server IDs, endpoint connection status, auth/header setup, host
  version, and live `tools/list` were not inspected. No secrets were read,
  copied, or committed.

## Policy A and Policy B

Policy A is the documented conservative baseline:

```toml
[mcp_servers.<actual-server-id>]
default_tools_approval_mode = "writes"
```

It is **not host-tested in this environment**. Based on verified host semantics
and Task-01 annotations, read/resolve tools should not prompt, while non-read-
only `PREPARE` and `CONFIRM_WRITE` tools should prompt; actual behavior awaits
operator evidence.

Policy B is an unselected, testable internal-host candidate: preserve Policy
A's `writes` default and append contract-generated `approval_mode = "approve"`
tables for every `PREPARE` tool. The current exact set contains 26 names:

```text
prepare_contact
prepare_contact_update
prepare_customer
prepare_customer_contact
prepare_customer_payment_entry
prepare_customer_payment_reconciliation
prepare_customer_primary_contact
prepare_delivery_note_to_sales_invoice
prepare_document_cancel
prepare_document_child_add
prepare_document_delete
prepare_document_email
prepare_document_submit
prepare_document_update
prepare_item
prepare_multi_invoice_customer_receipt
prepare_purchase_order
prepare_quotation
prepare_quotation_to_sales_order
prepare_sales_invoice
prepare_sales_invoice_payment
prepare_sales_invoice_to_delivery_note
prepare_sales_order
prepare_sales_order_advance_payment
prepare_sales_order_to_delivery_note
prepare_sales_order_to_sales_invoice
```

`scripts/generate_tool_catalog.py --prepare-approval-overrides --server-id
'<actual-server-id>'` renders the authoritative sanitized TOML child tables.
Its contract check rejects any target that is not `PREPARE`, is destructive or
open-world, or lacks a guarded `CONFIRM_WRITE` counterpart. All confirms,
including `confirm_document_delete` and `confirm_document_email`, remain
outside the output and host-prompted under the `writes` default.

## Automated repository verification

Passed:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python -m unittest \
  mcp_erpnext.tests.test_host_approval_policy \
  mcp_erpnext.tests.test_tool_routing \
  mcp_erpnext.tests.test_tool_annotations \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_approvals
# Ran 61 tests in 13.256s — OK
```

`scripts/generate_tool_catalog.py --check` passed, confirming that the existing
generated catalog remains current. The new
`--prepare-approval-overrides --server-id 'example-mcp-server'` command rendered
all 26 PREPARE tables and no confirm table. `git diff --check` passed.

Broader discovery was run:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
# Ran 431 tests in 14.953s — FAILED (4 errors, 1 failure)
```

The count increases by five from the Task-02 baseline (426) because of the new
host-policy tests. The failure categories are unchanged from Task 02:

- `test_customer_service`, `test_item_service`, `test_purchase_order_service`,
  and `test_quotation_service`: `KeyError: 'code'` while asserting
  `TRUSTED_APPROVAL_UNAVAILABLE`.
- `test_email`: `PROFILE_MISMATCH` instead of
  `TRUSTED_APPROVAL_UNAVAILABLE`.

No new Task-03 failure category was introduced. The test startup also emitted
the existing `pydantic_settings` `IncompleteFieldDefinitionWarning`; it did not
fail the focused suite.

## Operator-assisted validation required

Follow [MCP Host Approval Policy](../../operations/MCP_HOST_APPROVAL_POLICY.md)
to record the actual server ID(s), Policy-A result, Policy-B result if tested,
two fresh-thread checks, `/mcp` connection/tool-list evidence, and all matrix
rows for Sales, Purchase, Accounts, destructive, and open-world confirmation
boundaries. Record the Task-02 routing traces and resolver-not-found behavior.

Use safe data. A confirm-boundary prompt can be observed without approving a
write. Do not send email, delete/cancel a valuable record, or create/reconcile
a live financial transaction merely for this validation.

## Final policy and limitations

No deployment policy is selected until the actual host evidence exists. The
recommended provisional fallback is Policy A (`writes`). Promote the generated
Policy B only if the operator confirms no host prompt for READ/RESOLVE/PREPARE,
continued host prompts for every `CONFIRM_WRITE`, and unchanged server business
approval behavior across safe Sales, Purchase, and Accounts flows.

Rollback removes only generated per-tool override tables while retaining or
restoring `writes`; it does not modify ERPNext or `MCP_APPROVAL_MODE`.

MCP Python SDK v1-to-v2 migration was not performed. No ERPNext business logic,
permissions, prepared-operation policy, profile membership, tool schema, or
tool name was changed.
