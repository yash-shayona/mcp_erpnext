# Customer Payment to Sales Invoice Reconciliation V1 — Implementation Report

**Task:** `55_TASK_CUSTOMER_PAYMENT_ADVANCE_TO_SALES_INVOICE_RECONCILIATION_V1_IMPLEMENTATION.md`  
**Implementation date:** 2026-09-17  
**Scope:** `mcp_erpnext` Accounts profile; static and unit verification only

## 1. Repository state before work

- Checkout: `apps/mcp_erpnext`
- Branch: `master`
- Baseline commit recorded by the preceding audit: `9486dbc1b496a9017450c7ef9cf982f993d4a01a`
- Frappe: `16.34.0`
- ERPNext: `16.35.0`
- India Compliance: `16.9.0`

The worktree already contained Task 53 Sales Order advance-payment changes,
the Task 52/54 audit documents, and modifications to shared registry/profile/
REST/test files. Those changes were preserved. No `apps/frappe`,
`apps/erpnext`, or `apps/india_compliance` files were changed.

## 2. Native source re-inspected

The installed ERPNext source was re-inspected before implementation. The
implemented path uses:

```text
PaymentReconciliation.get_payment_entries()
  -> get_advance_payment_entries_for_regional()
  -> get_advance_payment_entries()

PaymentReconciliation.get_invoice_entries()
  -> get_outstanding_invoices()
  -> Payment Ledger query

PaymentReconciliation.allocate_entries()
  -> native allocation/difference/exchange projection

PaymentReconciliation.reconcile_allocations()
  -> reconcile_against_document()
  -> update_reference_in_payment_entry()
  -> submitted Payment Entry update-after-submit
  -> native ledger and Sales Invoice outstanding maintenance
```

`get_advance_payment_entries_for_regional()` remains the decorated ERPNext
entry point, so an installed India Compliance override remains reachable.
The service does not import the base helper to bypass regional behavior.

## 3. Public contract and supported source kinds

The new fixed tools are:

```text
prepare_customer_payment_reconciliation
confirm_customer_payment_reconciliation
```

Prepare accepts only:

```json
{
  "payment_entry": "ACC-PAY-00001",
  "sales_invoice": "ACC-SINV-00001",
  "amount": 100.0
}
```

Confirm accepts only the shared `approval_token` and `confirm` fields. The
service accepts only a submitted Customer `Receive` Payment Entry and a
submitted ordinary Customer Sales Invoice belonging to the same Customer and
Company. It supports either one native positive unallocated source or one
native Sales Order advance reference.

Multiple eligible source rows fail closed with
`AMBIGUOUS_PAYMENT_SOURCE`; no first-row selection or automatic split is
performed. Supplier, Internal Transfer, Journal Entry, return/credit-note,
term-specific, multi-document, refund, unreconcile, and background/bulk paths
remain outside V1.

## 4. Native outstanding, terms, accounts, and currency

The target amount is taken from the exact native Payment Ledger outstanding
row, not from `Sales Invoice.outstanding_amount`. The same native discovery is
repeated during confirmation and after successful reconciliation where a row
is available.

Invoices whose Payment Terms Template enables term-specific allocation are
rejected with `PAYMENT_TERMS_UNSUPPORTED`. No Payment Schedule row is selected
or flattened.

The effective invoice receivable account and Customer advance account are
resolved through ERPNext helpers. The public contract exposes neither account
choice nor exchange/rate/gain-loss inputs. Separate Customer advance-account
behavior, reconciliation effect date, exchange differences, rounding, and
gain/loss remain ERPNext-native. The preview exposes only bounded currency and
warning fields.

## 5. Permission and identity model

The service uses the current authenticated `frappe.session.user` and current
site. It explicitly requires:

- read and write permission on the exact Payment Entry;
- read permission on the exact Sales Invoice;
- write permission on the virtual Payment Reconciliation capability;
- read permission for the linked Customer, Company, and relevant Account
  context.

No public user, site, role, `ignore_permissions`, approval-mode, or native
bypass field is accepted. This explicit MCP authorization is required because
the audited ERPNext internal reconciliation helper may save the submitted
Payment Entry with `ignore_permissions=True` internally.

## 6. Prepare projection and approval

Prepare configures a virtual `Payment Reconciliation` object in memory, runs
native source and invoice discovery, and uses `allocate_entries()` to project
one exact allocation. It does not call `reconcile_allocations()`,
`reconcile_against_document()`, submitted Payment Entry save/update, ledger
mutation, invoice-outstanding mutation, or `frappe.db.commit()`.

The response is explicitly a current native reconciliation projection. It is
bounded to the exact source/target, source kind, native currency and amounts,
projection after amount, separate-account/date information, and regional or
exchange warnings. Raw documents, reference rows, GL, Payment Ledger,
Advance Payment Ledger, bank details, SQL, and tracebacks are not returned.

The shared `ApprovalStore` binds the request and fingerprint to the action,
site, current user, and expiry. Confirmation uses atomic
`claim_for_confirm_write()`, reconstructs the state from fresh documents and
native discovery, and rejects material drift with the repository's
`STALE_CONFIRMATION` convention before mutation.

## 7. Confirm mutation and result

After fresh approval and fingerprint validation, the service calls native
`reconcile_allocations()` exactly once for the reconstructed virtual object.
It does not append Payment Entry Reference rows, call generic document update,
write GL/Payment Ledger/Advance Payment Ledger rows, submit a Payment Entry,
submit a Sales Invoice, or commit midway through reconciliation. Native
validation failures roll back the current request transaction through the
existing Frappe database boundary.

On success, the exact Payment Entry and Sales Invoice are reloaded. The result
is bounded and reports `status: "reconciled"`, source/target names, customer,
Company, source kind, applied amount, allocation currency, before/after native
outstanding where available, source availability where safely available, and
warnings. A non-required shared interaction directive states that no further
continuation is required.

## 8. Files changed for Task 55

Added:

- `mcp_erpnext/contracts/accounts/customer_payment_reconciliation.py`
- `mcp_erpnext/services/accounts/customer_payment_reconciliation.py`
- `mcp_erpnext/tools/accounts/customer_payment_reconciliation.py`
- `mcp_erpnext/tests/test_customer_payment_reconciliation.py`
- this implementation report

Updated consistently with the existing Task 53 worktree changes:

- `mcp_erpnext/contracts/accounts/__init__.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/accounts.py`
- `mcp_erpnext/remote_operations.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_tool_contracts.py`
- `mcp_erpnext/tests/test_rest_backend.py`
- generated `docs/TOOLS.md`

The tools are registered only in the Accounts profile. Sales and Purchase
inventories remain isolated.

## 9. Verification

Focused implementation and regression command:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_customer_payment_reconciliation \
  mcp_erpnext.tests.test_customer_payment_entry \
  mcp_erpnext.tests.test_sales_order_advance_payment \
  mcp_erpnext.tests.test_accounts_sales_invoice_payment \
  mcp_erpnext.tests.test_multi_invoice_customer_receipt \
  mcp_erpnext.tests.test_payment_entry_read \
  mcp_erpnext.tests.test_approvals \
  mcp_erpnext.tests.test_fingerprint \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_rest_backend
```

Result: **115 tests passed**.

Full MCP discovery command:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
```

Result: **378 tests run; 373 passed, 1 failure, 4 errors**. The failure and
errors are in pre-existing approval-policy/profile/mock tests for Email,
Customer, Item, Purchase Order, and Quotation services. They were outside the
Task 55 focused paths and are recorded here without attributing them to this
implementation.

Generated catalog verification:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
```

Both completed successfully. `git diff --check` also completed successfully.

## 10. Evidence boundary and limitations

The above results are static/unit, profile, registry, REST-dispatch, and
mocked-native-seam evidence. No live database, Redis approval, MCP transport,
authenticated `yob.localhost` call, Payment Entry, Sales Invoice, Payment
Ledger, Advance Payment Ledger, GL, queue, regional-company configuration,
rollback, or browser behavior was verified. The implementation therefore
does not claim live accounting success.

The next task is verification-only:

```text
Task 56 — Customer Payment Reconciliation Live MCP Verification
```

It should use explicitly approved disposable or clearly identified test
records on `yob.localhost`, without expanding the public API.
