# Accounts V1 Sales Invoice Customer Payment Implementation Report

**Task:** 45 — Accounts V1: Sales Invoice Customer Receive Payment Entry as Draft  
**Date:** 2026-09-14

## Scope and result

The Accounts profile now exposes a narrow submitted Sales Invoice customer
receipt flow. It prepares and previews one native Draft Payment Entry, stores a
shared approval, and confirms by rebuilding the native document and inserting
one Draft. Submission remains a separate generic lifecycle action.

## Files changed

- `mcp_erpnext/settings.py` — added the `accounts` profile.
- `mcp_erpnext/profiles/accounts.py` — Accounts inventory.
- `mcp_erpnext/contracts/accounts/sales_invoice_payment.py` — typed public contracts.
- `mcp_erpnext/tools/accounts/sales_invoice_payment.py` — direct/REST wrappers.
- `mcp_erpnext/services/accounts/sales_invoice_payment.py` — native workflow adapter.
- `mcp_erpnext/tools/__init__.py` — profile dispatch.
- `mcp_erpnext/tools/lifecycle.py` — Accounts-only submit/cancel/delete registration.
- `mcp_erpnext/services/common/lifecycle.py` — Payment Entry Accounts lifecycle allowlist.
- `mcp_erpnext/contracts/registry.py` — contract metadata.
- `mcp_erpnext/remote_operations.py` — fixed REST operations.
- `mcp_erpnext/tests/test_profiles.py` — Accounts inventory and isolation coverage.
- `mcp_erpnext/tests/test_accounts_sales_invoice_payment.py` — public contract coverage.
- `docs/TOOLS.md` — regenerated catalog.

## Public contract

`prepare_sales_invoice_payment` accepts only `sales_invoice` plus optional
`amount`, `mode_of_payment`, `bank_account`, `reference_no`, `reference_date`,
`bank_amount`, and bounded `remarks`. Extra fields and raw accounting fields
are rejected by `PublicContractModel(extra="forbid")`.

`confirm_sales_invoice_payment` accepts only `approval_token` and `confirm`.
No payment fields can be supplied during confirmation.

## Native behavior

The adapter calls the installed callable:

```python
get_payment_entry(
    "Sales Invoice", sales_invoice,
    party_amount=amount,
    bank_account=resolved_native_account,
    bank_amount=bank_amount,
    reference_date=reference_date,
)
```

Omitted `amount` leaves ERPNext to use the current invoice outstanding. A
provided lower amount is passed as native `party_amount`. Amounts above the
current outstanding are rejected as `AMOUNT_EXCEEDS_OUTSTANDING`; no advance
or unallocated receipt is created by this flow.

Mode of Payment is resolved through ERPNext's native bank/cash resolver. An
explicit public Bank Account is permission-checked, company-bound, and its
native Account is passed internally to the factory. Supplying both destination
fields is rejected deterministically. Raw Account, paid-to, party-account,
exchange-rate, GL, Payment Ledger, tax, deduction, and dimension inputs are not
public.

Reference number/date and remarks are copied to ordinary Payment Entry fields.
Prepare does not fabricate a reference; full final validation occurs at Draft
insert. Multi-currency amounts remain native; `bank_amount` is passed through
when supplied and no MCP exchange formula is used.

Native reference rows, including payment-term rows, are preserved in the
bounded preview. The preview contains source/status, Customer, Company,
Receive type, dates, destination label, currencies, paid/received amounts,
current outstanding, allocation summary, reference data, remarks, and an
explicit Draft/no-ledger-effect note. Raw Payment Entry JSON and GL/Ledger
rows are not returned.

## Approval and stale state

The shared `ApprovalStore` binds the opaque one-shot approval to action, site,
and authenticated user. Its payload includes the original typed intent, native
bounded preview, and a SHA-256 fingerprint containing the preview and resolved
destination Account identity. Confirmation atomically claims the approval,
rebuilds the native Payment Entry, recomputes the preview/fingerprint, and
fails closed on native rebuild failure or material drift. Native latest
outstanding checks remain the final authority at insert.

Successful confirmation calls one normal-permission Draft insert with no
submit call, manual GL, Payment Ledger, Journal Entry, Payment Request,
reconciliation, or Sales Invoice mutation.

## Lifecycle and backends

Accounts exposes only generic `prepare/confirm_document_submit`,
`prepare/confirm_document_cancel`, and `prepare/confirm_document_delete`.
The Accounts allowlist contains Payment Entry for those three actions only;
generic update and child-row mutation are unavailable. Native lifecycle
methods and linked-document checks remain authoritative.

Both direct runtime execution and the fixed typed REST registry use the same
service. REST has no arbitrary method/import/DocType dispatch and accepts no
caller-selected site or identity. Accounts does not register Sales or
Purchase business tools and can run as an independent profile process.

## Verification

Executed successfully:

- `../../env/bin/python -m compileall -q apps/mcp_erpnext/mcp_erpnext`
- FastMCP inventory inspection for all three profiles: Accounts exposed 8
  expected tools; Sales and Purchase inventories remained unchanged.
- Accounts `audit_tool_contracts`: no issues.
- `../../env/bin/python -m unittest mcp_erpnext.tests.test_profiles mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_accounts_sales_invoice_payment`: **9 passed, 0 failed**.
- `../../env/bin/python scripts/generate_tool_catalog.py` completed.
- `git -C apps/mcp_erpnext diff --check` was run.

`pytest` was not available in the configured environment, so no pytest count is
claimed. The full unittest discovery command ran **301 tests: 296 passed, 1
failure, and 4 errors**. The five unrelated pre-existing approval-policy
failures were:

- `test_email.EmailServiceTests.test_confirm_requires_trusted_approval_in_default_policy`
- `test_customer_service.CustomerServiceTests.test_model_confirm_true_cannot_self_grant_approval`
- `test_item_service.ItemServiceTests.test_model_confirm_true_cannot_self_grant_approval`
- `test_purchase_order_service.PurchaseOrderServiceTests.test_confirm_requires_shared_approval_then_uses_normal_insert`
- `test_quotation_service.QuotationServiceTests.test_model_confirm_true_cannot_self_grant_approval`

They return `PROFILE_MISMATCH` or a response without the expected `code`
instead of `TRUSTED_APPROVAL_UNAVAILABLE`; no failure references the Accounts
payment implementation. The FastMCP import emitted the pre-existing Frappe
`IncompleteFieldDefinitionWarning` and Python prefix warning; neither changed
the inventory result.

No live authorized test-site transaction was performed in this implementation
turn. Therefore prepare-side no-write behavior, actual Draft insertion,
submit/cancel GL and Payment Ledger effects, payment-term fixtures,
multi-currency behavior, permissions, and REST round trips remain live
unverified. No production or unknown-site accounting records were created.

## Limitations

This task does not add multi-invoice receipts, advances/unallocated receipts,
supplier payments, internal transfers, Payment Requests, reconciliation,
Journal Entries, Payment Entry read/query/aggregate, PDF/email, bank
reconciliation, imports, or generic accounting-field updates. No site,
company, Customer, or user is hard-coded.
