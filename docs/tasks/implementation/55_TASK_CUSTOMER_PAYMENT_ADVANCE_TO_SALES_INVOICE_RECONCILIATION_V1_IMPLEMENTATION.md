# Task 55 — Customer Payment / Advance to Sales Invoice Reconciliation V1 Implementation

## 1. Task Identity

**Task Number:** 55  
**Title:** Customer Payment / Advance to Sales Invoice Reconciliation V1 Implementation  
**Profile:** `accounts`  
**Mode:** implementation  
**Native authority:** ERPNext Payment Reconciliation + `reconcile_against_document()` path  
**Public capability style:** explicit one-payment/one-invoice business intent, typed prepare/confirm, shared approval, fresh native revalidation

---

## 2. Objective

Implement one narrow Accounts-profile MCP capability that applies an **existing submitted Customer Payment Entry** to one **submitted Sales Invoice** through ERPNext's native reconciliation machinery.

V1 must support both audited Customer-payment source forms:

1. a submitted Customer `Receive` Payment Entry with eligible unallocated amount; and
2. a submitted Customer `Receive` Payment Entry carrying an eligible Sales Order advance reference.

The public intent must remain intentionally small:

```text
exact Payment Entry
+
exact Sales Invoice
+
one positive allocation amount
```

The implementation must delegate reconciliation to ERPNext.

MCP must **not** implement:

- custom outstanding logic;
- custom Payment Entry Reference mutation;
- custom Payment Ledger logic;
- custom advance-account logic;
- custom exchange gain/loss logic;
- custom GST/tax reconciliation;
- custom Sales Order advance adjustment.

---

## 3. Audited Native Decision

Task 54 established that the installed ERPNext version already provides the required native path.

The audited mutation chain is:

```text
virtual Payment Reconciliation allocation
    ->
PaymentReconciliation.reconcile_allocations()
    ->
erpnext.accounts.utils.reconcile_against_document(...)
    ->
update_reference_in_payment_entry(...)
    ->
native submitted Payment Entry update-after-submit
    ->
native GL / Payment Ledger / Advance Payment Ledger maintenance
    ->
update_voucher_outstanding(Sales Invoice)
```

Task 55 must preserve this path.

Do not replace it with a direct child-table update.

Do not use generic MCP document-update functionality for reconciliation.

---

## 4. V1 Business Flow

Implement:

```text
Existing submitted Customer Payment Entry
        +
Submitted Sales Invoice
        +
Explicit positive allocation amount
        |
        v
prepare_customer_payment_reconciliation
        |
        v
exact source + target permission checks
        |
        v
ERPNext-native source discovery
        |
        v
ERPNext Payment-Ledger-backed invoice outstanding discovery
        |
        v
virtual one-payment/one-invoice reconciliation projection
        |
        v
bounded preview + shared approval token
        |
        v
confirm_customer_payment_reconciliation
        |
        v
atomic approval claim
        |
        v
fresh exact source/target reload
        |
        v
fresh native discovery + fingerprint comparison
        |
        v
PaymentReconciliation.reconcile_allocations()
        |
        v
ERPNext native submitted-PE mutation + ledger/outstanding updates
        |
        v
reload exact PE + SI
        |
        v
bounded reconciliation result
```

No new Payment Entry is created by this capability.

No Sales Invoice is created or submitted by this capability.

---

## 5. Public Tools

Add exactly:

```text
prepare_customer_payment_reconciliation
confirm_customer_payment_reconciliation
```

These tools belong only to:

```text
MCP_PROFILE=accounts
```

Do not register them in:

```text
sales
purchase
```

Do not create:

```text
generic_reconcile
reconcile_anything
update_payment_entry_reference
execute_payment_reconciliation
prepare_payment_entry_update
```

---

## 6. Prepare Public Input

Recommended exact V1 input:

```text
payment_entry
sales_invoice
amount
```

Where:

- `payment_entry` = exact existing submitted Payment Entry name;
- `sales_invoice` = exact existing submitted Sales Invoice name;
- `amount` = positive finite decimal interpreted in the native reconciliation/allocation currency derived by the server.

The caller must not provide:

```text
customer
company
party_type
payment_type
source_reference_row
sales_order
account
party_account
advance_account
debit_to
paid_from
paid_to
currency
exchange_rate
source_exchange_rate
target_exchange_rate
difference_amount
gain_loss_account
posting_date
reconciliation_date
payment_term
payment_schedule_row
GL rows
Payment Ledger rows
Advance Payment Ledger rows
tax rows
GST adjustments
ignore_permissions
user
site
approval_mode
native flags
arbitrary kwargs
arbitrary DocTypes
```

All such business/accounting state must be derived by the server from the exact current ERPNext documents and native helpers.

---

## 7. Confirm Public Input

Follow the **current repository's shared confirmation contract**.

If the current project convention remains:

```text
approval_token
confirm
```

use that exact pattern.

Required semantics:

### `confirm = true`

Attempt the approved reconciliation after:

- atomic approval claim;
- full fresh reload;
- native eligibility re-check;
- full fingerprint comparison.

### `confirm = false`

Use the existing shared cancellation/decline behavior:

```text
cancel/decline pending approval
perform no accounting mutation
return bounded non-created result
```

The `confirm` boolean is a user interaction choice only.

It is **not authorization by itself**.

Authorization remains:

```text
authenticated ERPNext identity
+
shared server-side approval
+
permission checks
+
fresh native validation
```

If the current repository has since standardized confirm tools to token-only semantics, follow the current shared contract consistently and document the difference.

Do not invent a one-off confirmation shape for Task 55.

---

## 8. Source Payment Entry Eligibility

The exact Payment Entry must be loaded from the current site under the authenticated ERPNext user.

V1 supports only:

```text
party_type = Customer
payment_type = Receive
docstatus = 1
same Customer as target Sales Invoice
same Company as target Sales Invoice
compatible native party/account context
positive currently eligible source value
```

Supported source kinds:

### A. Unallocated Customer receipt

A submitted Payment Entry with currently eligible positive unallocated amount.

### B. Sales Order-linked Customer advance

A submitted Payment Entry with one currently eligible Sales Order advance reference that native ERPNext exposes for reconciliation.

Reject:

```text
Draft Payment Entry
cancelled Payment Entry
Supplier payment
Internal Transfer
wrong payment direction
wrong party
wrong Company
fully allocated source
Journal Entry advance
return/refund path
unsupported source-account context
```

---

## 9. Deterministic Source Selection

The public V1 input intentionally does not expose a Payment Entry Reference child-row ID.

Therefore the service must never silently choose among multiple materially different eligible source buckets.

During native discovery:

- filter results to the exact requested Payment Entry;
- determine the exact eligible source form;
- identify whether the source is:
  - one unallocated source; or
  - one eligible Sales Order advance reference.

If the exact Payment Entry yields multiple eligible Sales Order advance reference rows, or another ambiguous combination where choosing one would change accounting semantics, fail closed with a bounded error such as:

```text
AMBIGUOUS_PAYMENT_SOURCE
```

Do not:

- pick the first row;
- pick the oldest row;
- pick the largest row;
- auto-split the public allocation across several source references;
- combine unallocated and order-linked source buckets automatically.

A future capability may add an explicit typed source-reference selector after a separate audit if needed.

---

## 10. Target Sales Invoice Eligibility

The exact target must be a normal submitted Customer Sales Invoice with positive native outstanding.

At minimum require:

```text
Sales Invoice exists
docstatus = 1
not cancelled
not an unsupported return/credit-note case
same Customer
same Company
compatible party/account context
positive native outstanding
```

Use ERPNext's Payment-Ledger-backed outstanding discovery.

Do not treat a caller-supplied amount or stale cached:

```text
Sales Invoice.outstanding_amount
```

as final accounting authority.

The installed native Payment Ledger / `get_outstanding_invoices()` path is authoritative for Task 55.

---

## 11. Native Payment Discovery

Use the installed/current regional-aware native discovery path.

Task 54 identified the regional extension point around:

```text
get_advance_payment_entries_for_regional(...)
```

and base discovery around:

```text
get_advance_payment_entries(...)
```

The implementation must re-inspect exact current signatures before coding.

Requirements:

- use the regional-aware entry point when installed/current ERPNext expects it;
- filter server-side to the exact Payment Entry;
- do not expose broad discovery results to the model/user;
- do not trust mere document existence as eligibility;
- preserve native account/party/company/docstatus rules.

If India Compliance overrides the regional discovery point, that override must remain in the execution path.

---

## 12. Native Invoice Outstanding Discovery

Use ERPNext's native Payment-Ledger-backed invoice outstanding path.

Task 54 identified:

```text
erpnext.accounts.utils.get_outstanding_invoices()
```

with underlying Payment Ledger query behavior.

Re-inspect installed signatures and filters before coding.

The service must derive current target outstanding from native data at both:

```text
prepare
confirm
```

Do not use custom formulas like:

```text
invoice_total - payments
```

Do not use cached preview outstanding at confirm.

---

## 13. Payment Reconciliation Virtual Document

ERPNext Payment Reconciliation is an operational virtual document, not a normal persisted reconciliation record.

Task 55 must respect that.

Do not:

- insert Payment Reconciliation as a durable approval object;
- call `db_insert()` expecting a persistent record;
- store approval state inside Payment Reconciliation;
- use Payment Reconciliation document name as idempotency identity.

MCP approval state remains in the project's shared `ApprovalStore`.

The exact PE + SI + native source state + allocation + current settings form the approval/fingerprint authority.

---

## 14. Prepare Must Be Side-Effect-Free

`prepare_customer_payment_reconciliation` must not call the native mutation path.

Specifically, prepare must not call:

```text
reconcile_allocations()
reconcile_against_document()
update_reference_in_payment_entry()
submitted Payment Entry save/update-after-submit
make_advance_gl_entries()
Payment Ledger repost/rebuild mutations
update_voucher_outstanding() as a mutation
frappe.db.commit()
```

Prepare may:

- instantiate/configure virtual Payment Reconciliation state in memory;
- run native discovery;
- run native allocation/projection helpers that are proven side-effect-free;
- run regional in-memory adjustment logic that is proven side-effect-free;
- calculate a bounded projection from current native state.

ERPNext exposes no guaranteed full accounting dry-run for `reconcile_against_document()`.

Therefore prepare output must be described as:

```text
current native reconciliation projection
```

not as an already executed accounting result.

---

## 15. Native Allocation Projection

Prepare should construct the smallest in-memory one-payment/one-invoice allocation using native structures.

Re-inspect installed methods/signatures for:

```text
PaymentReconciliation
get_payment_entries
get_invoice_entries
allocate_entries
adjust_allocations_for_taxes
validate_allocation
reconcile_allocations
```

Use native helpers wherever they safely support the exact V1 case.

Do not manually recreate:

- GST adjustment;
- difference amount;
- gain/loss;
- exchange-map logic;
- advance reclassification;
- Payment Ledger behavior.

Where a native helper is mutating, do not call it during prepare.

---

## 16. Amount Semantics

The public `amount` must be:

- decimal-compatible;
- finite;
- strictly greater than zero;
- not boolean.

The audit defines V1 amount as:

```text
positive amount in the native reconciliation/account currency derived by prepare
```

The service must return that currency clearly in the preview.

Reject when the requested amount exceeds either:

- current native eligible source amount; or
- current native target outstanding.

Use ERPNext precision/tolerance rules.

MCP may perform obvious early bound checks for user-friendly errors, but ERPNext native validation remains final authority.

Do not accept public exchange rates or company-currency equivalents.

---

## 17. Payment Terms Boundary

V1 must reject target Sales Invoices where active term-specific allocation is required.

Return a stable bounded error such as:

```text
PAYMENT_TERMS_UNSUPPORTED
```

when the current invoice/template requires exact payment-term allocation.

Do not:

- silently allocate at invoice total level;
- select the first Payment Schedule row;
- flatten Payment Terms;
- expose arbitrary Payment Schedule child rows.

A future term-aware reconciliation capability requires a separate typed contract and audit.

---

## 18. Separate Customer Advance Account

ERPNext may have:

```text
book_advance_payments_in_separate_party_account
```

enabled.

Task 55 must preserve native behavior automatically.

Native reconciliation may:

- discover the Customer advance account;
- reconcile across advance/receivable account context;
- create native advance reclassification;
- update Advance Payment Ledger;
- select an effective reconciliation date from Company/Accounts settings.

MCP must not expose:

```text
advance_account
receivable_account
reclassification account
GL account
reconciliation_takes_effect_on override
```

as public inputs.

Preview may expose only bounded business information:

```text
separate advance account path = yes/no
effective native allocation/reconciliation date if material
warning that native reclassification applies
```

Do not expose raw Chart of Accounts details unless already part of an approved bounded Accounts projection and genuinely needed.

---

## 19. Currency / Exchange / Gain-Loss

ERPNext remains authoritative for:

- source account currency;
- target account currency;
- invoice currency;
- source/target exchange rates;
- reconciliation exchange map;
- difference amount;
- rounding;
- exchange gain/loss;
- gain/loss Journal Entry behavior where native code requires it.

MCP must not implement exchange formulas.

MCP must not accept:

```text
exchange_rate
company_currency_amount
gain_loss_account
difference_account
posting_date override
```

unless a later audited capability explicitly requires such input.

Prepare should expose:

```text
allocation currency
current available source amount
current target outstanding
requested amount
effective native allocation
bounded exchange/gain-loss warning if material
```

Do not expose raw exchange maps or ledger rows.

---

## 20. India Compliance / Regional Behavior

The installed India Compliance app may override:

```text
get_advance_payment_entries_for_regional
PaymentReconciliation.adjust_allocations_for_taxes
Payment Entry validate
Payment Entry update-after-submit
Payment Entry cancel
```

and may affect GST reversal / Payment Ledger / GL behavior.

Task 55 must:

1. use the regional-decorated native discovery path;
2. use the native Payment Reconciliation object/methods;
3. allow installed hooks to execute naturally;
4. not import a base helper specifically to bypass regional behavior;
5. not duplicate GST calculation in MCP;
6. rebuild the regional projection at confirm.

If India Compliance is absent on another site, base ERPNext must still work.

Do not make India Compliance a hard dependency of `mcp_erpnext`.

---

## 21. Permission and Identity Boundary

This requirement is critical.

Task 54 found that the native internal reconciliation path may save a submitted Payment Entry with:

```text
ignore_permissions=True
```

inside ERPNext.

That is an ERPNext internal mutation detail.

It must **not** become an MCP permission bypass.

Before invoking reconciliation, Task 55 must explicitly establish that the authenticated ERPNext user is allowed to perform this business operation.

At minimum inspect and enforce the installed/current permission model for:

```text
Payment Reconciliation capability/DocType
exact Payment Entry
exact Sales Invoice
Customer
Company
relevant account context
submitted Payment Entry update/reconciliation authority
```

Do not guess the exact permission combination.

Inspect:

- Payment Reconciliation DocType role permissions;
- Payment Entry permissions;
- Sales Invoice permissions;
- framework permission APIs;
- ERPNext's own exposed reconciliation methods.

Write focused tests proving supported Accounts roles can perform the operation and unauthorized users cannot.

Public input must never contain:

```text
user
role
site
ignore_permissions
run_as
administrator
```

Transport/session identity remains authoritative.

---

## 22. Prepare Permission Sequence

Recommended prepare sequence:

```text
resolve current authenticated ERPNext identity
    ->
load exact Payment Entry
    ->
explicit exact-source permission checks
    ->
load exact Sales Invoice
    ->
explicit exact-target permission checks
    ->
verify Payment Reconciliation business permission
    ->
verify Customer/Company/account consistency
    ->
native source discovery
    ->
native invoice outstanding discovery
```

Permission failures must occur before returning sensitive accounting details.

Do not use broad ledger discovery as a substitute for exact document permission.

---

## 23. Concurrency / Running Reconciliation

Task 54 found ERPNext also supports persistent/background `Process Payment Reconciliation`.

V1 remains synchronous, but must fail closed if a conflicting native reconciliation process is active for the same effective scope and current settings make that conflict material.

Use installed/current native running-process checks where available.

Return:

```text
RECONCILIATION_ALREADY_RUNNING
```

or the existing equivalent.

Do not create a custom MCP queue.

Do not create a Process Payment Reconciliation document for V1.

---

## 24. Approval Fingerprint

Use the shared canonical fingerprint helper.

Fingerprint only server-derived canonical state.

At minimum include, where available and material:

### Payment Entry

```text
name
docstatus
modified
party_type
party
company
payment_type
party/account currency
source account identity
current unallocated amount
eligible source kind
exact eligible Sales Order reference row identity if applicable
source reference type/name
source reference allocated amount
advance voucher metadata
all materially relevant source reference rows
```

### Sales Invoice

```text
name
docstatus
modified
customer
company
debit_to/effective receivable account identity
account currency
invoice currency
conversion rate
current native Payment-Ledger-backed outstanding
Payment Terms template/state
term-allocation policy
```

### Native policy/configuration

```text
separate advance-account setting
effective advance-account branch
reconciliation_takes_effect_on setting
effective reconciliation/allocation date if material
regional capability/configuration state when material
```

### Request

```text
payment_entry
sales_invoice
amount
```

Approval binding must also preserve:

```text
site
authenticated user
operation/action
```

Do not fingerprint raw GL rows generated by MCP.

MCP must not generate those rows.

---

## 25. Prepare Output

Return a bounded approval preview.

Recommended fields:

```text
status
approval_token
expires_in_seconds
interaction

payment_entry
sales_invoice
customer
company

source_kind
    unallocated
    OR sales_order_advance

source_sales_order
    only if safely relevant and source kind is SO advance

allocation_currency
available_source_amount
invoice_outstanding_before
requested_amount
effective_native_allocation

separate_advance_account_applies
effective_reconciliation_date if material

payment_terms_supported = true
regional_adjustment_applies/warning if material
exchange_or_gain_loss_warning if material

projected_invoice_outstanding_after
draft/projection warning
```

If `projected_invoice_outstanding_after` is shown, clearly label it as a projection based on current native state.

It is not accounting authority.

Do not expose:

```text
raw Payment Entry JSON
raw Sales Invoice JSON
raw Payment Entry Reference rows
raw GL
raw Payment Ledger
raw Advance Payment Ledger
full bank details
full Chart of Accounts
SQL
traceback
secret/config values
unrelated Customer data
unrelated invoices/payments
```

---

## 26. Confirm Workflow

`confirm_customer_payment_reconciliation` must follow the existing one-shot shared approval flow.

For approved confirmation:

```text
authenticated user
    ->
ApprovalStore.claim_for_confirm_write()
    ->
load original canonical request
    ->
reload exact Payment Entry
    ->
reload exact Sales Invoice
    ->
repeat explicit permission checks
    ->
repeat native source discovery
    ->
repeat Payment-Ledger target outstanding discovery
    ->
repeat Payment Terms eligibility
    ->
repeat separate-account / regional / running-process checks
    ->
rebuild exact in-memory native allocation
    ->
recompute fingerprint
    ->
compare with approved fingerprint
```

If material state differs:

```text
return APPROVAL_STALE / STALE_CONFIRMATION / SOURCE_CHANGED
create no accounting mutation
```

Use the project's current canonical stale error convention.

Only after the fresh fingerprint matches may mutation begin.

---

## 27. Native Confirm Mutation

After successful fresh approval validation, invoke ERPNext's native reconciliation seam.

Audited preferred path:

```text
PaymentReconciliation.reconcile_allocations()
```

which delegates to:

```text
reconcile_against_document()
```

Re-inspect installed/current function signatures before implementation.

The exact allocation must be constructed server-side from:

```text
exact Payment Entry
exact eligible source kind/reference
exact Sales Invoice
approved amount
native-derived account/currency/settings
```

Do not accept a caller-provided reconciliation row.

Do not append Payment Entry Reference rows directly.

Do not call generic `doc.save()` as a replacement for native reconciliation.

---

## 28. Transaction Behavior

The reconciliation must be atomic from the MCP request perspective.

Requirements:

- do not call `frappe.db.commit()` in the middle of the native mutation;
- let native ERPNext/Frappe mutation execute in the current request transaction;
- on failure, rollback according to the project's established service convention;
- do not return success before the native mutation has completed;
- after success, reload exact source and target before constructing the final response.

If native ERPNext itself performs a commit in the audited installed path, document it and adapt safely rather than pretending atomicity.

Do not add new commit boundaries casually.

---

## 29. Native Submitted Payment Entry Mutation

For unallocated source, native ERPNext may append a target Sales Invoice reference.

For Sales Order advance source, native ERPNext may:

```text
reduce/split the existing Sales Order advance reference
+
append a new Sales Invoice reference
+
retain required advance-voucher metadata
```

MCP must not implement this logic.

Tests should prove the resulting source state is native-generated.

No generic child-row update path may be called by Task 55.

---

## 30. Post-Confirm Result

After native reconciliation succeeds:

1. reload the exact Payment Entry;
2. reload the exact Sales Invoice;
3. read current native target outstanding using the appropriate native authority;
4. derive a bounded result.

Recommended output:

```text
status = reconciled

payment_entry
sales_invoice
customer
company

source_kind
applied_amount
allocation_currency

invoice_outstanding_before
invoice_outstanding_after

source_available_before
source_available_after if safely/natively available

separate_advance_account_applied
regional_adjustment_warning if material
exchange/gain_loss warning if material

interaction = completed/no further approval for this operation
```

Do not return raw accounting internals.

---

## 31. Idempotency / Replay

Approval tokens remain one-shot.

Second confirmation with the same token must fail through existing approval semantics.

Native stale/current-state guards must remain active.

For ambiguous transport timeout after possible reconciliation:

- do not auto-replay;
- do not silently mint another approval;
- instruct the caller/client flow to inspect exact Payment Entry and Sales Invoice state first.

Task 55 should expose a stable bounded outcome/error that allows the client to distinguish:

```text
definite failure before mutation
vs
reconciliation completed
vs
unexpected/ambiguous failure requiring exact-state inspection
```

Do not invent unsafe automatic retries.

---

## 32. Payment Terms Rejection

Before returning `ready`, explicitly detect whether the target invoice has active term-specific allocation requirements.

If yes:

```text
PAYMENT_TERMS_UNSUPPORTED
```

No approval token should be created for an unsupported target.

Confirm must repeat the check.

---

## 33. Unsupported V1 Cases

Task 55 must reject or exclude:

```text
Journal Entry advance
Supplier payment
Internal Transfer
Payment Entry refund
Customer refund
Credit Note / return reconciliation
Sales Invoice return
multi-Payment Entry allocation
multi-Sales Invoice allocation
one PE split across multiple invoices in one MCP call
multiple source reference rows chosen automatically
Payment-Term-specific allocation
manual GST/tax allocation
manual gain/loss
manual exchange rate
manual GL mutation
manual Payment Ledger mutation
manual Advance Payment Ledger mutation
manual Payment Entry Reference mutation
background bulk reconciliation
automatic retry after timeout
unreconcile/reversal
Payment Entry cancellation
Sales Invoice cancellation
```

Existing generic lifecycle remains separate where already supported.

---

## 34. Reversal Is Separate

ERPNext has native `Unreconcile Payment` behavior.

Do not add it in Task 55.

Do not simulate reversal by editing reference rows.

A future capability must separately inspect and wrap the native unreconcile path with its own:

- typed intent;
- preview;
- approval;
- stale state;
- accounting effects;
- tests.

---

## 35. Error Model

Reuse current MCP error/result conventions.

Add/map stable bounded errors as needed.

At minimum support:

```text
PAYMENT_ENTRY_NOT_FOUND
SALES_INVOICE_NOT_FOUND
PERMISSION_DENIED
INVALID_PAYMENT_ENTRY_STATE
INVOICE_NOT_OUTSTANDING
PARTY_MISMATCH
COMPANY_MISMATCH
ACCOUNT_MISMATCH
AMBIGUOUS_PAYMENT_SOURCE
INVALID_ALLOCATION_AMOUNT
AMOUNT_EXCEEDS_AVAILABLE
PAYMENT_TERMS_UNSUPPORTED
RECONCILIATION_ALREADY_RUNNING
REGIONAL_VALIDATION_FAILED
NATIVE_VALIDATION_FAILED
APPROVAL_REQUIRED
APPROVAL_STALE
APPROVAL_EXPIRED
APPROVAL_ALREADY_USED
SOURCE_CHANGED
NATIVE_RECONCILIATION_UNAVAILABLE
RECONCILIATION_FAILED
```

If equivalent established project codes already exist, reuse them instead of creating synonyms.

Do not return raw native exception text if it leaks:

- SQL;
- accounts not required for the user-facing result;
- bank details;
- secrets;
- stack traces;
- internal paths;
- framework internals.

Store/log a bounded diagnostic reference according to existing project conventions.

---

## 36. Contract Layer

Likely new module:

```text
mcp_erpnext/contracts/accounts/customer_payment_reconciliation.py
```

Follow current contract conventions.

Prepare input:

```text
payment_entry
sales_invoice
amount
```

Confirm input:

```text
approval_token
confirm
```

or the exact current shared confirmation schema after repository inspection.

Requirements:

- `extra="forbid"` or current equivalent;
- no arbitrary dictionaries;
- no arbitrary child rows;
- explicit typed output;
- structured approval interaction;
- canonical numeric handling;
- no internal transport context in public schemas.

---

## 37. Service Layer

Likely new module:

```text
mcp_erpnext/services/accounts/customer_payment_reconciliation.py
```

The service should contain reusable internal helpers with clear names, for example conceptually:

```text
load_and_authorize_payment_entry
load_and_authorize_sales_invoice
discover_exact_native_payment_source
get_exact_native_invoice_outstanding
validate_payment_terms_boundary
check_conflicting_reconciliation
build_virtual_reconciliation_projection
build_reconciliation_fingerprint
execute_native_reconciliation
build_bounded_result
```

Names may differ according to repository conventions.

Avoid one giant function.

Do not duplicate existing identity, approval, fingerprint, error, or account utilities.

---

## 38. Tool Layer

Likely:

```text
mcp_erpnext/tools/accounts/customer_payment_reconciliation.py
```

Use the existing tool wrapper conventions exactly.

Register:

```text
prepare_customer_payment_reconciliation
confirm_customer_payment_reconciliation
```

Descriptions must clearly distinguish reconciliation from:

```text
prepare_sales_invoice_payment
prepare_multi_invoice_customer_receipt
prepare_customer_payment_entry
prepare_sales_order_advance_payment
```

Recommended semantic distinction:

```text
sales_invoice_payment
    = create a NEW Draft Payment Entry for an invoice

customer_payment_reconciliation
    = apply an EXISTING SUBMITTED Customer Payment Entry to an invoice
```

This distinction must be obvious in tool descriptions so the model selects the correct capability.

---

## 39. Contract Registry

Register both tools in the existing registry.

Prepare metadata should follow current project semantics:

```text
Domain: Accounts
Operation: PREPARE
Side effect: PREPARE
Interaction: APPROVAL
approval_confirm_tool: confirm_customer_payment_reconciliation
```

Confirm metadata:

```text
Domain: Accounts
Operation: CONFIRM
Side effect: CONFIRM_WRITE
approval guard: existing shared trusted pending-operation guard
```

Do not create another registry.

---

## 40. Accounts Profile

Add only to:

```text
mcp_erpnext/profiles/accounts.py
```

Preserve all existing Accounts tools.

Do not change Sales/Purchase inventories except tests asserting isolation.

---

## 41. Fixed REST Parity

Add fixed remote operation parity if current Accounts write capabilities support REST.

Both REST and direct MCP paths must call the same service authority.

Do not expose:

```text
arbitrary method
arbitrary DocType
arbitrary function
caller site
caller user
raw Payment Reconciliation object
raw reconciliation allocation rows
```

Unknown operations must remain rejected.

---

## 42. Data Minimization

The LLM/client should receive only what is needed to understand and approve the action.

Do not leak:

```text
full Customer record
full Payment Entry
full Sales Invoice
all Customer payments
all Customer invoices
all Accounts
raw Payment Ledger
raw Advance Payment Ledger
raw GL
bank numbers
IBAN
SWIFT
tax secrets/configuration
site credentials
REST secret
Redis state
stack traces
SQL
```

Native internal reads may be broader where ERPNext requires them, but public output must remain bounded to the exact requested source/target and business-relevant summary.

---

## 43. Allowed Changes

Inspect current repository first.

Expected allowed areas:

```text
mcp_erpnext/contracts/accounts/customer_payment_reconciliation.py
mcp_erpnext/services/accounts/customer_payment_reconciliation.py
mcp_erpnext/tools/accounts/customer_payment_reconciliation.py

mcp_erpnext/contracts/accounts/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/profiles/accounts.py
mcp_erpnext/remote_operations.py

mcp_erpnext/tests/test_customer_payment_reconciliation.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_rest_backend.py

docs/TOOLS.md
docs/inspect/CUSTOMER_PAYMENT_TO_SALES_INVOICE_RECONCILIATION_V1_IMPLEMENTATION_REPORT.md
```

Reuse current shared helpers.

If current repository naming differs, follow current structure and document actual paths.

---

## 44. Forbidden Changes

Do not modify:

```text
apps/frappe/**
apps/erpnext/**
apps/india_compliance/**
```

Do not modify ERPNext/Frappe DocTypes.

Do not add:

```text
custom fields
fixtures
patches
migrations
hooks
new accounting DocTypes
new ledger tables
site settings
Company settings
```

Do not change live accounting data during unit/static implementation unless separately authorized.

Do not refactor unrelated:

```text
Sales
Purchase
Customer
Item
Quotation
Sales Order
Delivery Note
Sales Invoice
PDF/email
read/query/aggregate
```

---

## 45. Required Tests — Public Contract

Test:

- exact Payment Entry required;
- exact Sales Invoice required;
- amount required;
- positive decimal accepted;
- zero rejected;
- negative rejected;
- bool rejected;
- NaN rejected;
- infinity rejected;
- unknown fields rejected;
- account fields rejected;
- reference-row fields rejected;
- user/site fields rejected;
- exchange-rate fields rejected;
- confirmation mutable business fields rejected;
- typed output shape;
- approval interaction metadata;
- tool description distinction from new-payment tools.

---

## 46. Required Tests — Source Payment Entry

Test:

- valid submitted Customer Receive PE;
- Draft PE rejected;
- cancelled PE rejected;
- Supplier PE rejected;
- Internal Transfer rejected;
- wrong Customer;
- wrong Company;
- no eligible source amount;
- already fully allocated PE;
- unallocated standalone receipt supported;
- SO-linked advance supported;
- unsupported Journal Entry source cannot enter through this contract.

---

## 47. Required Tests — Source Ambiguity

Mandatory tests:

- one exact unallocated source -> accepted;
- one exact SO advance reference -> accepted;
- multiple eligible SO reference rows -> reject `AMBIGUOUS_PAYMENT_SOURCE`;
- ambiguous unallocated + multiple source-reference situation -> reject;
- no "first result" selection;
- no automatic split across source references.

This protects the narrow three-field public contract.

---

## 48. Required Tests — Sales Invoice

Test:

- valid submitted ordinary SI;
- missing SI;
- Draft SI;
- cancelled SI;
- return/credit-note excluded;
- fully paid / no outstanding;
- wrong Customer;
- wrong Company;
- incompatible account;
- exact current Payment-Ledger outstanding used;
- stale `Sales Invoice.outstanding_amount` alone is not authority.

---

## 49. Required Tests — Payment Terms

Test:

- invoice without active term allocation accepted;
- active term-specific allocation rejected;
- no automatic first-term selection;
- no flattened schedule allocation;
- confirm rechecks term state and becomes stale if changed.

---

## 50. Required Tests — Allocation Amount

Test:

- partial source -> partial invoice;
- full available source;
- full invoice outstanding;
- amount below both;
- amount above source;
- amount above invoice;
- precision-boundary amount;
- tiny residual;
- native precision remains authority.

---

## 51. Required Tests — Native Unallocated Source Mutation

For an eligible unallocated PE, verify native code is called and produces the expected native source outcome.

Test that Task 55 itself does not:

```text
append Payment Entry Reference directly
run direct SQL
write Payment Ledger directly
write GL directly
```

Mock/spy the native seam as appropriate.

---

## 52. Required Tests — Native SO Advance Mutation

For an eligible Sales Order-linked advance:

- exact source reference is discovered;
- native reconciliation is invoked;
- existing SO advance reference is reduced/split natively;
- SI reference is added natively;
- required advance metadata preserved;
- MCP does not perform child-row mutation itself;
- resulting native Sales Order advance state remains ERPNext-controlled.

---

## 53. Required Tests — Separate Advance Account

Cover:

```text
book_advance_payments_in_separate_party_account = off
book_advance_payments_in_separate_party_account = on
```

Verify:

- public contract unchanged;
- caller cannot select advance account;
- native path handles reclassification;
- effective setting participates in fingerprint;
- setting change after prepare causes stale confirmation.

Do not assert site-specific account names unless test fixtures explicitly define them.

---

## 54. Required Tests — Currency / Gain-Loss

At minimum test native seams for:

- same account currency;
- foreign-currency source/target;
- rate drift after prepare;
- native difference/gain-loss path;
- rounding;
- no public exchange-rate override;
- no MCP gain/loss formula.

Where full ERPNext accounting integration is impractical in unit tests, mock at the native seam and document live-verification boundaries.

---

## 55. Required Tests — India Compliance / Regional

When installed in the development environment, cover:

- regional advance discovery entry point used;
- regional allocation adjustment hook reachable;
- regional validation rejection maps safely;
- no direct base-helper bypass;
- no custom GST arithmetic in MCP.

Also keep design compatible with an ERPNext site without India Compliance.

---

## 56. Required Tests — Permissions

Because native internal reconciliation may save submitted PE with `ignore_permissions=True`, explicit authorization tests are mandatory.

Test:

- authenticated supported Accounts role succeeds at authorization stage;
- user lacking Payment Reconciliation capability fails;
- PE unreadable -> fail;
- SI unreadable -> fail;
- Customer/Company/account visibility failure -> fail where applicable;
- no caller-controlled user;
- no caller-controlled `ignore_permissions`;
- REST identity and direct identity use current project rules.

Do not rely only on mocked `ignore_permissions=True` native behavior as proof of security.

---

## 57. Required Tests — Prepare Side Effects

Mandatory:

```text
prepare does not call reconcile_allocations
prepare does not call reconcile_against_document
prepare does not save submitted Payment Entry
prepare does not write ledger
prepare does not update invoice outstanding
prepare does not commit
```

Prepare returns only a projection + shared approval.

---

## 58. Required Tests — Approval

Test:

- approval token created;
- correct action binding;
- correct user binding;
- correct site binding;
- exact payload binding;
- exact fingerprint binding;
- missing approval rejected;
- wrong user rejected;
- wrong site rejected;
- wrong action rejected;
- expired rejected;
- already-used rejected;
- `confirm=true` without server approval cannot authorize;
- `confirm=false` creates no mutation if current shared pattern supports it.

---

## 59. Required Tests — Stale State

After prepare simulate:

- PE modified;
- PE cancelled;
- source unallocated amount changed;
- SO reference allocation changed;
- source reference row changed;
- SI modified;
- SI outstanding changed;
- SI paid by another process;
- Customer/Company/account changes;
- Payment Terms setting changes;
- separate advance account setting changes;
- reconciliation date setting changes;
- exchange/rate state changes;
- regional effective allocation changes;
- background reconciliation becomes active.

Confirm must reject before mutation.

---

## 60. Required Tests — Native Confirm

Verify:

- exact virtual allocation reconstructed;
- native `PaymentReconciliation.reconcile_allocations()` called;
- native `reconcile_against_document()` remains downstream ERPNext authority;
- no direct PE child mutation from MCP;
- no new Payment Entry created;
- no Payment Entry submit called;
- no Sales Invoice submit called;
- current transaction commits only after success according to project convention;
- failure rolls back;
- final documents reloaded.

---

## 61. Required Tests — Background Conflict

Test the installed/current running-process guard or the MCP adapter around it.

A matching conflicting reconciliation process should return:

```text
RECONCILIATION_ALREADY_RUNNING
```

V1 must not enqueue its own job.

---

## 62. Required Tests — Idempotency

Test:

- first valid confirm succeeds;
- second same token fails;
- second newly prepared request after completed reconciliation observes fresh reduced source / reduced invoice outstanding;
- a no-longer-eligible repeated allocation is rejected;
- no automatic retry on ambiguous failure.

---

## 63. Required Tests — REST / Profile / Registry

Verify:

- Accounts profile includes both new tools;
- Sales does not;
- Purchase does not;
- registry entries correct;
- approval guard present;
- fixed REST prepare operation works;
- fixed REST confirm operation works;
- malformed input rejected;
- unknown operation rejected;
- no arbitrary dispatch added;
- direct and REST output contracts match.

---

## 64. Regression Tests

Run focused regression for at least:

```text
Task 50 standalone Customer Payment Entry
Task 53 Sales Order advance
Sales Invoice payment
multi-invoice Customer receipt
Payment Entry read/query/aggregate
Payment Entry lifecycle
approval store
fingerprint
tool contracts
tool registration
profiles
REST backend
```

Also run relevant native ERPNext Payment Reconciliation / Payment Entry tests if practical in the current bench.

Then run full `mcp_erpnext` unit discovery.

Record exact:

```text
tests run
passed
failed
errors
skipped
```

Do not attribute pre-existing failures to Task 55 without evidence.

---

## 65. Generated Documentation

Regenerate/check:

```text
docs/TOOLS.md
```

using the repository's existing generator.

Tool descriptions must make this distinction explicit:

```text
Sales Invoice payment
    -> creates a NEW Draft Payment Entry

Customer payment reconciliation
    -> applies an EXISTING SUBMITTED Payment Entry
```

This distinction is important for model tool selection.

---

## 66. Implementation Report

Create:

```text
docs/inspect/CUSTOMER_PAYMENT_TO_SALES_INVOICE_RECONCILIATION_V1_IMPLEMENTATION_REPORT.md
```

The report must include:

1. repository state before work;
2. installed Frappe/ERPNext/India Compliance versions;
3. native source re-inspected;
4. exact public contract;
5. exact supported source kinds;
6. deterministic source-selection policy;
7. native Payment Entry discovery path;
8. native Sales Invoice outstanding path;
9. Payment Terms decision;
10. separate advance-account behavior;
11. currency/gain-loss behavior;
12. regional/India Compliance behavior;
13. explicit permission model;
14. prepare projection behavior;
15. approval/fingerprint behavior;
16. native confirm mutation path;
17. transaction/rollback behavior;
18. bounded output;
19. files changed;
20. exact focused test commands/results;
21. full-suite result;
22. generated-catalog result;
23. pre-existing unrelated failures;
24. live verification performed/not performed;
25. remaining limitations;
26. exact next-task recommendation.

Do not claim live ledger behavior if only mocked/static tests were performed.

---

## 67. Acceptance Criteria

Task 55 is complete only when all are true.

### AC-01
Accounts profile exposes:

```text
prepare_customer_payment_reconciliation
confirm_customer_payment_reconciliation
```

### AC-02
Sales and Purchase profiles do not expose them.

### AC-03
Prepare public input is restricted to exact Payment Entry, exact Sales Invoice, and positive allocation amount.

### AC-04
Confirm follows the existing shared confirmation contract and accepts no mutable business fields.

### AC-05
Both standalone unallocated Customer Payment Entry and one exact eligible SO-linked advance source are supported.

### AC-06
Ambiguous multiple eligible source-reference cases fail closed.

### AC-07
Target outstanding is derived from the native Payment Ledger path.

### AC-08
Active term-specific Payment Terms allocation is rejected in V1.

### AC-09
Prepare performs no accounting mutation.

### AC-10
Prepare returns a bounded projection and shared approval token.

### AC-11
Approval is site/user/action/payload/fingerprint bound and atomically claimed.

### AC-12
Confirm fully reloads and revalidates source and target.

### AC-13
Material drift fails before mutation.

### AC-14
Explicit MCP authorization is performed before calling a native path that may internally use permission bypass.

### AC-15
Confirm invokes native Payment Reconciliation / `reconcile_against_document()` behavior.

### AC-16
MCP does not directly mutate Payment Entry Reference rows.

### AC-17
MCP does not directly write GL, Payment Ledger, Advance Payment Ledger, invoice outstanding, or Sales Order advance state.

### AC-18
Separate advance-account behavior remains ERPNext-native.

### AC-19
Currency/exchange/gain-loss behavior remains ERPNext-native.

### AC-20
India Compliance/regional behavior remains in the native execution path when installed.

### AC-21
V1 is synchronous and does not create a custom/background reconciliation job.

### AC-22
Conflicting native reconciliation process fails closed.

### AC-23
One-shot approval plus native stale validation protects replay.

### AC-24
No new Payment Entry is created or submitted by reconciliation.

### AC-25
No Sales Invoice is created/submitted by reconciliation.

### AC-26
REST/direct/profile/registry parity is complete.

### AC-27
Bounded output leaks no raw accounting/bank/ledger data.

### AC-28
Focused tests pass.

### AC-29
Generated tool catalog generation/check passes.

### AC-30
Full test result is recorded honestly.

### AC-31
Implementation report documents static vs live evidence clearly.

---

## 68. Expected Result

After Task 55, the Accounts profile should support the full bounded service-selling payment lifecycle:

```text
Sales Order
    |
    +--> Customer advance
    |       ->
    |    Draft Payment Entry
    |       ->
    |    generic lifecycle submit
    |
    v
Sales Invoice
    |
    +--> create NEW invoice-specific Payment Entry
    |
    +--> create NEW multi-invoice receipt
    |
    +--> create NEW standalone Customer receipt
    |
    +--> apply EXISTING submitted Customer Payment/Advance
            |
            v
        native reconciliation
            |
            v
        native PE reference update
        native ledger update
        native SI outstanding update
```

The LLM receives a business capability.

ERPNext remains the accounting engine.

---

## 69. Explicit Non-Goals After Task 55

Still deferred:

```text
multi-payment reconciliation
multi-invoice reconciliation in reconciliation tool
term-specific reconciliation
Journal Entry advance reconciliation
credit-note/return reconciliation
refund
unreconcile
reversal
bulk/background reconciliation
automatic payment-selection policy
automatic invoice-selection policy
Supplier reconciliation
Purchase flows
internal transfer
manual GL
manual ledger editing
generic accounting mutation
```

---

## 70. Live Verification Boundary

Task 55 implementation/unit tests do not automatically prove actual site accounting behavior.

Unless explicit test-site mutation permission is already available, do not mutate production/live accounting data.

After implementation, live verification should use approved disposable/test records and confirm:

```text
authenticated MCP identity
Payment Reconciliation permission
exact PE/SI read access
shared Redis approval
standalone unallocated PE reconciliation
SO-linked advance reconciliation
separate advance account enabled/disabled
native Payment Entry reference result
Sales Invoice outstanding result
Payment Ledger result
Advance Payment Ledger result where applicable
exchange/gain-loss result
India Compliance hooks
rollback on failure
duplicate/replay behavior
```

---

## 71. Exact Next Task

After Task 55 implementation and static/focused regression verification, the next task should be:

```text
Task 56 — Customer Payment Reconciliation Live MCP Verification
```

Task 56 should be **verification-only**, against an explicitly approved test site and disposable/clearly identified test accounting records.

It should verify end-to-end:

```text
MCP client/tool call
    ->
prepare
    ->
approval
    ->
confirm
    ->
ERPNext native reconciliation
    ->
Payment Entry reference change
    ->
Payment Ledger / Advance Payment Ledger effects
    ->
Sales Invoice outstanding change
    ->
SO advance effect where applicable
```

Task 56 must not expand the public API.

After Task 56 succeeds, the next business-capability candidate should be evaluated separately. A likely future candidate is a native **Unreconcile Payment** capability, because reversal is intentionally outside Task 55, but it must receive its own native-flow audit before implementation.

---

## 72. Final Implementation Principle

The implementation is correct only if it can be summarized as:

```text
MCP:
exact business intent
+ explicit authorization
+ bounded native projection
+ shared approval
+ stale-state protection

ERPNext:
payment eligibility
+ invoice outstanding
+ reconciliation mutation
+ submitted PE reference updates
+ advance-account handling
+ exchange/gain-loss
+ regional hooks
+ ledgers
+ accounting truth
```

Do not move reconciliation logic from ERPNext into MCP.
