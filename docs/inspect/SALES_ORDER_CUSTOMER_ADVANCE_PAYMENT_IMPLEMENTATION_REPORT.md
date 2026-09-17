# Sales Order Customer Advance Payment V1 Implementation Report

## Scope

This implementation adds the Accounts-profile pair
`prepare_sales_order_advance_payment` and
`confirm_sales_order_advance_payment`. The capability prepares and creates one
Draft Customer Receive Payment Entry against one submitted Sales Order as an
advance. Submission, cancellation, reconciliation, and ledger processing
remain the existing generic Payment Entry lifecycle responsibilities.

## Native authority inspected

The installed ERPNext checkout is version 16.35.0. The implementation was
checked against `get_payment_entry` and `PaymentEntry.validate()` in
`apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py`, party
and advance-account resolution in `apps/erpnext/erpnext/accounts/party.py`,
and the Sales Order controller. The native factory is called with source type
`Sales Order`, the exact source name, Customer/Receive direction, the requested
party amount, the resolved destination account, optional bank amount, and
reference date. Native reference rows, Payment Terms allocation, accounts,
currencies, exchange rates, and separate-advance-account policy are not
reimplemented by MCP.

## Public contract and registration

Prepare accepts an exact Sales Order name, positive finite amount, exactly one
Mode of Payment or Bank Account, and bounded transaction-reference, bank
amount, and remarks fields. Confirm accepts only `approval_token` and
`confirm`; extra and mutable business fields are rejected. The output is a
bounded native Draft preview or created Draft result with the shared semantic
approval directive. Both tools are registered only in the Accounts profile;
Sales and Purchase profiles are unchanged.

## Service behavior

Preparation checks authenticated identity, source read permission, submitted
and eligible Sales Order state, Payment Entry create permission, amount shape,
and destination validity. It calls the existing Accounts destination resolver,
then ERPNext's native Payment Entry factory and validation. It creates no
document and stores the request, bounded preview, and server-side native
fingerprint in the shared approval store.

Confirmation atomically claims the site/user/action-bound approval, reloads the
Sales Order, rebuilds the native Payment Entry and destination, and compares
source, reference, account-policy, currency/rate, amount, Payment Terms, and
native preview state. Drift returns `STALE_CONFIRMATION`. A successful
confirmation inserts exactly one Payment Entry with normal permissions and
`docstatus == 0`, commits it, and never calls `submit()`.

Fixed REST handlers call the same two service functions after validating the
same typed contracts. No arbitrary method, DocType, site, user, account, child
row, GL, Payment Ledger, or reconciliation dispatch was added.

## Files changed

Added:

- `mcp_erpnext/contracts/accounts/sales_order_advance_payment.py`
- `mcp_erpnext/services/accounts/sales_order_advance_payment.py`
- `mcp_erpnext/tools/accounts/sales_order_advance_payment.py`
- `mcp_erpnext/tests/test_sales_order_advance_payment.py`
- this report

Updated:

- `mcp_erpnext/contracts/accounts/__init__.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/accounts.py`
- `mcp_erpnext/remote_operations.py`
- focused profile, contract, and REST tests
- generated `docs/TOOLS.md`

The pre-existing `remote_operations.py` formatting changes were preserved.

## Verification

Passed focused command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=apps/mcp_erpnext ./env/bin/python -m unittest mcp_erpnext.tests.test_sales_order_advance_payment mcp_erpnext.tests.test_customer_payment_entry mcp_erpnext.tests.test_accounts_sales_invoice_payment mcp_erpnext.tests.test_payment_entry_read mcp_erpnext.tests.test_lifecycle mcp_erpnext.tests.test_approvals mcp_erpnext.tests.test_fingerprint mcp_erpnext.tests.test_tool_contracts mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_profiles mcp_erpnext.tests.test_rest_backend
```

Result: **105 tests passed**.

The narrower post-change profile/contract/REST/new-workflow run also passed:
**53 tests**.

Generated catalog generation and check both passed:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
```

Full discovery was executed:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=apps/mcp_erpnext ./env/bin/python -m unittest discover -s apps/mcp_erpnext/mcp_erpnext/tests -p 'test_*.py'
```

Result: **361 tests run, 1 failure and 4 errors**. The failures are in
existing Customer/Item/Purchase Order/Quotation/email approval-policy and
India Compliance mock paths; no Task 53 test failed. `git diff --check`
passes and the new Python modules compile successfully.

## Live boundary

No authenticated live MCP/REST call, Redis approval test, database insertion,
Payment Entry submission, GL or Payment Ledger verification, Sales Order
advance-state update, foreign-currency site test, Payment Terms site test, or
India Compliance live-hook test was performed. Those remain separate
site-specific verification work against approved test data.
