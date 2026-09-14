# Payment Entry Read, Query, and Aggregate Implementation Report

## 1. Scope and confirmed runtime context

Task 47 adds read-only Payment Entry intelligence to the Accounts profile. The
installed source is Frappe/ERPNext v16-style code, and live metadata checks
were performed against `praveg.localhost` for:

- `Payment Entry`
- `Payment Entry Reference`
- `Payment Entry Deduction`

The metadata confirms the native Payment Entry types `Receive`, `Pay`, and
`Internal Transfer`, the lifecycle status values `Draft`, `Submitted`, and
`Cancelled`, and the bounded fields used below. Metadata was used to verify
field availability; it was not treated as permission to publish every field.

No database, accounting record, queue, cache, service, or server state was
changed by the metadata checks or read tests.

## 2. Exact files changed

- `mcp_erpnext/contracts/accounts/payment_entry_read.py` — typed input/output
  contracts and allowlisted values.
- `mcp_erpnext/services/accounts/payment_entry_read.py` — permission-aware
  exact reads, parent queries, reference filtering, and aggregates.
- `mcp_erpnext/tools/accounts/payment_entry_read.py` — typed MCP wrappers.
- `mcp_erpnext/contracts/accounts/__init__.py` — Accounts contract exports.
- `mcp_erpnext/contracts/registry.py` — three typed public tool declarations.
- `mcp_erpnext/profiles/accounts.py` — Accounts-only registration.
- `mcp_erpnext/remote_operations.py` — three fixed REST handlers.
- `mcp_erpnext/tests/test_payment_entry_read.py` — focused service and
  contract tests.
- `mcp_erpnext/tests/test_profiles.py` — Accounts inventory assertions.
- `mcp_erpnext/tests/test_rest_backend.py` — fixed Accounts handler assertions.
- `mcp_erpnext/tests/test_tool_contracts.py` — typed schema assertions.
- `docs/TOOLS.md` — generated catalog.
- `docs/inspect/PAYMENT_ENTRY_READ_QUERY_AGGREGATE_IMPLEMENTATION_REPORT.md` —
  this report.

The task specification remains an existing untracked user file and was not
edited.

## 3. Public tools and profile inventory

Added exactly:

```text
get_payment_entry
query_payment_entries
aggregate_payment_entries
```

They are registered only by `register_accounts_profile`. Sales and Purchase
profile registrations are unchanged. Accounts retains the Task 45 customer
receipt tools and generic lifecycle tools; no new Payment Entry write tool was
added.

The public side-effect classification for all three tools is `READ`. Their
registry contracts are `PaymentEntryGetInput`/`PaymentEntryGetOutput`,
`PaymentEntryQueryInput`/`PaymentEntryQueryOutput`, and
`PaymentEntryAggregateInput`/`PaymentEntryAggregateOutput`.

## 4. Exact-read field and reference policy

The default `get_payment_entry` projection is:

```text
name, docstatus, status, payment_type, company, posting_date,
party_type, party, party_name, mode_of_payment, paid_from,
paid_from_account_currency, paid_to, paid_to_account_currency,
paid_amount, received_amount, total_allocated_amount, unallocated_amount,
difference_amount, reference_no, reference_date, remarks, modified
```

Callers may request only the explicit Payment Entry header allowlist. The
optional fields include `project`, `owner`, `creation`, and the bounded header
fields above. The result always includes a bounded `references` list because
invoice allocation identity is essential to Payment Entry review.

Each reference row may contain only:

```text
reference_doctype, reference_name, bill_no, due_date, payment_term,
total_amount, outstanding_amount, allocated_amount, exchange_rate
```

Rows are projected from the Payment Entry's native child state. No referenced
Sales Invoice, Purchase Invoice, Sales Order, or Purchase Order is
dereferenced, so the read cannot use a Payment Entry reference to bypass the
source document's permission boundary. Existing native reference DocTypes may
be displayed as identifiers; the filter surface accepts only the fixed set
`Sales Invoice`, `Purchase Invoice`, `Sales Order`, and `Purchase Order`.

Detailed Payment Entry Deduction rows were deliberately deferred. The current
read output exposes the native parent `difference_amount`; it does not
calculate or serialize deduction rows. This keeps the first implementation
bounded without publishing accounting dimensions or arbitrary deduction
fields.

`paid_from` and `paid_to` are exposed only as the stored Payment Entry account
labels. There is no Account dereference, Chart-of-Accounts browsing, balance,
bank balance, or bank-account expansion. `bank`, `bank_account_no`, IBAN,
SWIFT/BIC, credentials, tokens, and integration metadata are not public.

## 5. Query policy

The default query projection is a compact parent projection containing the
identity, lifecycle, payment type, company/date, party, mode, currencies, and
paid/received/allocation amounts. The same explicit header allowlist controls
custom projections; child references are not expanded in list rows.

Typed filters include exact `name`, `docstatus`, `status`, `payment_type`,
`company`, `party_type`, `party`, `mode_of_payment`, both account currencies,
and `reference_no`; posting, creation, and modified date ranges; exact and
minimum/maximum `paid_amount` and `received_amount`; and the bounded
`reference_doctype`/`reference_name` pair. Payment type is restricted to the
three native values and reference DocType is restricted to the four native
business documents above. Raw SQL, arbitrary filter dictionaries, arbitrary
operators, and arbitrary child-table expressions are not part of the public
contract.

Sorting is restricted to `posting_date`, `name`, `modified`, `paid_amount`,
`received_amount`, `status`, and `payment_type`, with `asc`/`desc` only. Every
sort adds `name` as a deterministic tie-breaker. Pagination uses the existing
limit/offset convention: default limit 20, hard maximum 100, non-negative
offset, and no unbounded result set.

## 6. Linked Sales Invoice/reference filtering

The query accepts a typed `reference_doctype` plus `reference_name`, for
example:

```json
{
  "reference_doctype": "Sales Invoice",
  "reference_name": "ACC-SINV-2026-00009"
}
```

The service first performs a bounded, permission-aware `frappe.get_list` on
`Payment Entry Reference`, selecting only `parent` and limiting candidates to
1000. Those candidate names are then passed to the normal
`frappe.get_list("Payment Entry", ..., ignore_permissions=False)` parent query.
If no candidates exist, the service returns an empty bounded result without
querying or revealing a parent name. The child result is never returned
directly. Thus child matching is specialized and server-owned, while final
Payment Entry visibility remains controlled by normal Frappe permissions.

The same strategy is used for aggregate reference filters. No source invoice
is loaded during reference matching.

## 7. Aggregate metrics, grouping, and currency safety

Supported metrics are:

```text
count
sum_paid_amount
sum_received_amount
sum_total_allocated_amount
sum_unallocated_amount
```

Supported grouping is:

```text
docstatus, status, payment_type, company, party_type, party,
mode_of_payment, paid_from_account_currency, paid_to_account_currency,
posting_date
```

The implementation reuses `services/common/aggregate.py` and Frappe v16
dictionary aggregate fields. It does not introduce a second aggregate engine
or accept caller expressions.

`sum_paid_amount` carries `paid_from_account_currency` context and
`sum_received_amount` carries `paid_to_account_currency` context. When the
relevant currency is not constrained by an exact filter, the service
automatically adds that currency to the aggregate grouping, including when a
different business group was requested. No FX conversion or current-rate
normalization occurs.

Allocation and unallocated amounts follow ERPNext's native Payment Entry
transaction-currency behavior: they require `payment_type=Receive` or
`payment_type=Pay` to identify the relevant native currency context. Receive
uses the paid-from currency and Pay uses the paid-to currency. An allocation
aggregate without that context, or for `Internal Transfer`, returns the
bounded `MIXED_CURRENCY_AGGREGATE` error. This prevents unlabeled mixed
currency totals.

The aggregate service uses `ignore_permissions=False` through the shared
executor. It does not read GL Entry or Payment Ledger Entry.

## 8. Permission and data-minimization behavior

Exact reads use `frappe.get_doc("Payment Entry", name)` followed by
`doc.has_permission("read")` before projecting any fields. List and aggregate
reads use permission-enforcing Frappe APIs with `ignore_permissions=False`.
The service does not impersonate Administrator, maintain an MCP role matrix,
or expose raw framework exceptions. Public errors use the existing bounded
error/reference envelope.

Only Payment Entry header data and native bounded reference identifiers are
returned. No full Payment Entry JSON, full Customer document, unrelated
invoice, GL row, Payment Ledger row, cache state, approval state, custom field,
traceback, or SQL is returned.

## 9. Direct and REST backend behavior

The direct backend uses the same typed wrappers and authoritative Accounts
service in the configured Frappe site/user context. The fixed REST registry
adds the same three operation names and validates each payload with the same
typed input models before calling the service. REST does not accept a site,
identity, method path, import path, arbitrary DocType, or arbitrary filter
expression from the caller. Successful and bounded-error shapes are the same
service contracts; live REST round trips were not available in this run.

## 10. Tests and verification

Focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_payment_entry_read \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_rest_backend
```

Result: **44 tests passed**.

Task 45 Payment Entry workflow and lifecycle regression command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_accounts_sales_invoice_payment \
  mcp_erpnext.tests.test_lifecycle \
  mcp_erpnext.tests.test_payment_entry_read
```

Result: **26 tests passed**.

Full suite command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ../../env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
```

Result: **313 tests run, with 1 failure and 4 errors**. The failures were
reproduced independently without Payment Entry files involved and are in
pre-existing approval-policy/email/customer/item/purchase/quotation tests:

- `test_customer_service.CustomerServiceTests.test_model_confirm_true_cannot_self_grant_approval`
- `test_item_service.ItemServiceTests.test_model_confirm_true_cannot_self_grant_approval`
- `test_purchase_order_service.PurchaseOrderServiceTests.test_confirm_requires_shared_approval_then_uses_normal_insert`
- `test_quotation_service.QuotationServiceTests.test_model_confirm_true_cannot_self_grant_approval`
- `test_email.EmailServiceTests.test_confirm_requires_trusted_approval_in_default_policy`

The isolated command produced the same four erroring approval tests and the
same email assertion failure. Those implementation files were not changed by
Task 47. The full suite also emitted existing MCP HTTP-authentication warning
logs and the mocked India Compliance item-read error-log path.

Additional checks:

- `scripts/generate_tool_catalog.py` completed.
- `scripts/generate_tool_catalog.py --check` passed.
- `git diff --check` passed.
- MCP account schemas were inspected and showed typed object inputs/outputs,
  bounded enum fields, no `ctx` property, no raw filter object, and no bank
  account number field.
- The source tree was AST-parsed through the focused test imports; no build,
  migration, formatter, or compileall command was run.

## 11. Runtime checks and limitations

Read-only runtime metadata checks against `praveg.localhost` succeeded for
all three Payment Entry DocTypes. No live `get_payment_entry`, query,
aggregate, direct MCP, authenticated permission-denial, or REST round trip was
performed because this run did not establish an authorized existing Payment
Entry record and live MCP/REST service execution was not available.

Consequently, live database permission behavior, actual site-specific custom
fields, existing Draft/Submitted/Cancelled records, and real mixed-currency
rows remain unverified. Static service seams cover permitted, missing, denied,
reference-filter, bounded-output, currency, and REST-registry behavior.

No Payment Entry, Payment Entry Reference, Payment Entry Deduction, GL Entry,
or Payment Ledger Entry was created, updated, submitted, cancelled, deleted,
or otherwise mutated for this task. No new Payment Entry write capability was
added. Sales and Purchase profile inventories and the Task 45 write/lifecycle
surface remain unchanged.

## 12. Known limitations

Task 47 intentionally does not add multi-invoice creation, advances,
standalone receipts, supplier-payment creation, internal-transfer creation,
Payment Request, Payment Reconciliation, Journal Entry, Payment Entry update,
PDF/email, bank reconciliation/import, GL/Payment Ledger reads, or detailed
deduction rows. Those require separate accounting and native-workflow
decisions.
