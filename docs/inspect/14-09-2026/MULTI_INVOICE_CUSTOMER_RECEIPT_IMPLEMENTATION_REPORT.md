# Multi-Invoice Customer Receipt Implementation Report

## Scope and result

Task 49 adds two Accounts-only typed tools:

- `prepare_multi_invoice_customer_receipt`
- `confirm_multi_invoice_customer_receipt`

They accept one exact Customer, 2-20 unique exact submitted Sales Invoices, and one positive explicit allocation per invoice. Preparation creates only an unsaved native Payment Entry projection. Confirmation atomically claims the shared approval, fully rebuilds the projection from fresh sources, compares the canonical fingerprint, and inserts one Draft Payment Entry with normal permissions. Submission remains the existing generic lifecycle operation.

## Files changed

- `mcp_erpnext/contracts/accounts/multi_invoice_customer_receipt.py`
- `mcp_erpnext/services/accounts/multi_invoice_customer_receipt.py`
- `mcp_erpnext/tools/accounts/multi_invoice_customer_receipt.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/accounts.py`
- `mcp_erpnext/remote_operations.py`
- `mcp_erpnext/services/common/lifecycle.py`
- `mcp_erpnext/tests/test_multi_invoice_customer_receipt.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_rest_backend.py`
- generated `docs/TOOLS.md`
- this report

The pre-existing untracked Task 48 audit/task and Task 49 task specification were preserved.

## Public contract and policy

`CustomerReceiptAllocation` exposes only `sales_invoice` and `allocated_amount`. The prepare input exposes Customer, party-side receipt amount, allocations, one mutually exclusive destination (`mode_of_payment` or `bank_account`), optional transaction reference fields, optional frozen posting date, optional destination-currency `bank_amount`, and remarks up to 1,000 characters. Public account, exchange-rate, tax, withholding, deduction, reference-DocType, identity, and site inputs are forbidden by `PublicContractModel(extra="forbid")`.

Boolean, non-positive, NaN, and infinite amounts are rejected. Duplicate invoice names and reference counts outside 2-20 are rejected. V1 requires an explicit destination rather than guessing a Company fallback.

## Native source and construction sequence

The service loads the exact Customer and every exact Sales Invoice with normal read permission. It derives the common Company and effective receivable account using ERPNext invoice-discounting account resolution, then verifies the shared party-account currency and invoice transaction currency.

Outstanding reference authority is ERPNext's installed:

```python
get_outstanding_reference_documents(args, validate=False)
```

The arguments are server-owned and contain the exact selected Sales Invoice voucher pairs. The generic Sales Invoice `outstanding_amount` field is not used as allocation authority.

Construction uses:

1. `frappe.new_doc("Payment Entry")`;
2. fixed Receive/Customer identity and native-derived Company/receivable account;
3. destination account resolved from native Mode-of-Payment defaults or a permitted Bank Account;
4. reference rows sourced from native outstanding results;
5. only each approved `allocated_amount` replaced from public intent;
6. `setup_party_account_field()`;
7. `set_missing_values()`;
8. `set_missing_ref_details(force=True)`;
9. `set_exchange_rate()`;
10. `set_amounts()`;
11. normal full validation during `insert()`.

No auto-allocation, manual GL, Payment Ledger, outstanding update, or Payment Reconciliation logic was added.

## Eligibility and amount behavior

The whole request fails if one source is missing, unreadable, not Submitted, a return, not natively outstanding, belongs to another Customer/Company, or changes the common effective receivable account or currency. Mixed invoice transaction currency is rejected. Payment Terms Templates with term allocation enabled, term-specific outstanding rows, and currently eligible early-payment discounts are rejected.

The public receipt and allocations are in the common receivable-account currency. Equality and outstanding checks use ERPNext's configured currency precision. The total receipt must exactly equal allocations; unallocated receipt, allocation above fresh outstanding, and nonzero native difference fail closed.

Same-currency destinations use the party amount as received amount. Cross-currency destination requires explicit `bank_amount`; ERPNext derives rates. Native deductions are accepted only in the cross-currency case and are previewed/fingerprinted. Unexpected same-currency deductions, taxes, or withholding state fail closed. Payment Request inputs are not exposed or intentionally populated.

## Preview, approval, and stale state

The bounded preview includes Customer, Company, resolved/frozen posting date, safe destination identity, party/destination currencies, paid/received amounts, native rates, all invoice allocations/current native outstanding values, totals, difference, bounded deductions, references, remarks, and a Draft-only warning.

The fingerprint includes normalized intent, bounded preview, safe resolved destination ledger state, and canonical per-invoice material state including modified signal, status, Customer, Company, effective account, currencies, dates, totals, fresh outstanding, allocation, terms template, and term-allocation policy. Confirm uses `ApprovalStore.claim_for_confirm_write()`, re-runs the complete build, and returns `STALE_CONFIRMATION` on any material mismatch. The final insert explicitly uses `ignore_permissions=False`, `ignore_links=False`, and `ignore_mandatory=False`, then follows the existing service commit/rollback convention.

## Payment Entry submit lifecycle

The existing Accounts lifecycle remains authoritative. Its Payment Entry submit preparation now adds a bounded `payment_entry_impact` projection containing all references, fresh Payment-Ledger outstanding values, allocations, currencies, totals, deductions/taxes, and the native ledger/outstanding warning. The approval payload fingerprints this fresh projection. Submit confirmation refreshes it again and rejects drift before calling the unchanged native `doc.submit()` path. Cancel and delete paths were not changed.

## Direct, REST, profile, and catalog

The typed MCP wrappers execute the same service through the existing direct runtime. Two fixed typed remote handlers were added to the Accounts registry; they provide no arbitrary method, DocType, site, or identity dispatch. Only the Accounts profile registers the tools. Sales and Purchase registration code is unchanged. `docs/TOOLS.md` was regenerated and passed its generated-catalog check.

Task 45 single-invoice service code and Task 47 Payment Entry read/query/aggregate code were not changed.

## Verification performed

Static parsing and whitespace:

```text
git diff --check
../../env/bin/python -c '<AST parse of all mcp_erpnext Python files>'
Result: passed; 168 Python files parsed.
```

Focused integration tests:

```text
../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_multi_invoice_customer_receipt \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_rest_backend \
  mcp_erpnext.tests.test_lifecycle
Result: 57 tests passed.
```

Catalog:

```text
../../env/bin/python scripts/generate_tool_catalog.py
../../env/bin/python scripts/generate_tool_catalog.py --check
Result: generated and check passed.
```

Full unit suite:

```text
../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
Result: 322 run; 317 passed; 1 failure and 4 errors.
```

The five failures are older approval-policy assertions in Customer, Item, Quotation, Purchase Order, and Email tests. They expected `TRUSTED_APPROVAL_UNAVAILABLE` but received a success-shaped response or `PROFILE_MISMATCH`. No Task 49 source appeared in their tracebacks. Re-running exactly those five tests in a fresh Python process produced the same five failures, while the focused Task 49/registry/profile/lifecycle selection passed. They are therefore recorded as existing approval-policy/environment failures outside the Task 49 paths, without claiming when they were introduced.

`ruff` could not be run because `/home/frappe/frappe-bench/env/bin/ruff` is not installed.

## Live and runtime verification boundary

No site, database, MCP process, or accounting document was changed. No live Customer/Sales Invoice/Payment Entry prepare-confirm-submit-cancel scenario was run because no explicit throwaway site and records were authorized for mutation. Therefore Draft insert, GL/Payment Ledger effects, outstanding changes/restoration, concurrent accounting behavior, Bank Account/Mode-of-Payment fixtures, cross-currency FX deductions, active optional-app hooks, and live permission denials remain unverified.

Installed source inspected is ERPNext v16.34.2. Static/unit evidence does not prove authenticated direct/REST MCP execution or live accounting behavior.

## Remaining limitations

Auto-allocation, unallocated advances, Sales Order advances, term-aware allocation, early-discount composition, mixed invoice currencies, credit-note netting, supplier payment, Payment Requests, reconciliation, Journal Entry, and caller-configured accounting rows remain deliberately unsupported. No next task was implemented.
