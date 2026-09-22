# Standalone Customer Payment Entry Implementation Report

## 1. Inspected existing implementation

The Accounts profile, single-invoice Payment Entry flow, multi-invoice receipt
flow, typed registry, approval store, fingerprint helper, profile tests,
Payment Entry read tools, and Accounts documentation were inspected. The new
flow is separate and does not alter invoice-linked behavior.

## 2. Inspected ERPNext native behavior

Installed ERPNext `PaymentEntry.validate()` calls `setup_party_account_field`,
`set_missing_values`, `set_liability_account`, `set_missing_ref_details`,
`set_exchange_rate`, and `set_amounts`. The implementation constructs an
unsaved `Payment Entry` and uses those native methods. The installed
`get_party_account` implementation remains responsible for party, group,
Company-default, currency, permission, and advance-account resolution.

## 3. Files changed

Added:

- `mcp_erpnext/contracts/accounts/customer_payment_entry.py`
- `mcp_erpnext/services/accounts/customer_payment_entry.py`
- `mcp_erpnext/tools/accounts/customer_payment_entry.py`
- `mcp_erpnext/tests/test_customer_payment_entry.py`
- this report

Updated Accounts profile registration, the contract registry,
`mcp_erpnext/tests/test_profiles.py`, and `docs/TOOLS.md`.

## 4. Public input contract

Customer, Company, positive amount, exactly one Mode of Payment or Bank
Account, and optional posting/reference/bank amount/remarks fields. Raw
accounting fields and mutable confirmation business fields are rejected.

## 5. Public output contract

Prepare returns a bounded native preview, opaque approval token, expiry, and
shared approval interaction directive. Confirm returns the created Draft name,
Customer, Company, Payment Type, paid amount, and native unallocated amount.

## 6. Native APIs/methods reused

Destination resolution reuses the Accounts multi-invoice destination helper.
Payment Entry construction uses `frappe.new_doc`, native party/defaulting,
liability-account, exchange-rate, amount, and validation methods. Confirmation
uses normal Frappe insert permissions.

## 7. Account/defaulting behavior

The MCP resolves only the business-level destination. ERPNext resolves the
Customer party account and applies the Company advance-liability policy. Raw
ledger accounts are internal preview/fingerprint material only.

## 8. Approval/fingerprint behavior

Prepare stores request, bounded preview, and native derived state in the shared
approval store. Confirm atomically claims the approval, rebuilds native state,
compares the fingerprint, and inserts only after a successful comparison.

## 9. Unsupported V1 cases

Invoice/order references, deductions, taxes/withholding, Supplier or Internal
Transfer payments, refunds, reconciliation, arbitrary accounting fields, and
automatic submission are unsupported.

## 10. Tests executed

Focused command:

```text
../../env/bin/python -m unittest mcp_erpnext.tests.test_customer_payment_entry mcp_erpnext.tests.test_profiles mcp_erpnext.tests.test_accounts_sales_invoice_payment mcp_erpnext.tests.test_payment_entry_read mcp_erpnext.tests.test_approvals mcp_erpnext.tests.test_fingerprint
```

Result: **43 tests passed**. This includes the Accounts profile contract audit.

Broader command:

```text
../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
```

Result: **331 tests run, 1 failure and 4 errors**. The failures are in
existing customer/item/purchase-order/quotation/email approval-policy tests
and an existing Item-service mock path; they do not exercise the new
standalone Customer Payment Entry tool. The worktree already contained
unrelated approval/profile changes when this task started.

## 11. Test results

The new public contracts, Accounts registration, registry audit, and focused
payment regressions pass. `git diff --check` also passes.

## 12. Remaining limitations

Authenticated live MCP execution, live Redis behavior, database creation,
native site-specific Customer/Company/default-account resolution, and
subsequent lifecycle submission remain unverified by this implementation task.
