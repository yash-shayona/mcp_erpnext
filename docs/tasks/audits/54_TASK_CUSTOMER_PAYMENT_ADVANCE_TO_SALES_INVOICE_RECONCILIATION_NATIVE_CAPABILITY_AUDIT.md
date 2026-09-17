# Task 54 — Customer Payment / Advance to Sales Invoice Reconciliation Native Capability Audit

## 1. Task Identity

**Task Number:** 54  
**Title:** Customer Payment / Advance to Sales Invoice Reconciliation Native Capability Audit  
**Profile:** `accounts`  
**Mode:** architecture / native-flow audit only  
**Production implementation:** NOT allowed in this task  
**Primary goal:** determine the smallest safe MCP capability that exposes ERPNext-native customer payment / advance reconciliation against Sales Invoice without implementing accounting logic in MCP.

---

## 2. Current Confirmed Baseline

The current Accounts profile already supports:

- submitted Sales Invoice -> Draft Customer Receive Payment Entry;
- multi-invoice Customer receipt -> Draft Payment Entry;
- standalone Customer Payment Entry -> Draft Payment Entry;
- submitted Sales Order -> Draft Customer Advance Payment Entry;
- Payment Entry read/query/aggregate;
- generic Payment Entry submit/cancel/delete lifecycle.

Task 53 added:

```text
prepare_sales_order_advance_payment
confirm_sales_order_advance_payment
```

Task 53 confirmation creates **Draft Payment Entry only**.

Submission remains a separate existing generic lifecycle action.

Therefore Task 54 must assume that Customer money may exist in at least these forms:

```text
A. Payment Entry already allocated to a Sales Invoice
B. standalone Customer Payment Entry with unallocated amount
C. Sales Order-linked Customer advance
D. other native eligible Customer advances discovered by ERPNext
```

Task 54 is about how existing eligible payment/advance value can later be applied to a submitted Sales Invoice through ERPNext-native mechanisms.

---

## 3. Objective

Inspect the installed/current ERPNext, Frappe, optional-app, and `mcp_erpnext` source and produce a source-grounded design recommendation for a future Accounts-profile reconciliation capability.

The audit must determine:

1. the exact native ERPNext APIs/classes/methods used to discover eligible Customer payments / advances;
2. the exact native APIs/classes/methods used to discover submitted Sales Invoices and current outstanding;
3. the exact native mutation path used to reconcile one existing payment/advance against one Sales Invoice;
4. whether the smallest safe public V1 should be:
   - one Payment Entry -> one Sales Invoice;
   - one advance reference -> one Sales Invoice;
   - or another equally narrow shape proven by native behavior;
5. whether Sales Order-linked advances and standalone unallocated Customer receipts can safely share one public MCP capability;
6. how separate Customer advance accounts change discovery and mutation;
7. how Payment Terms affect reconciliation;
8. how currencies, exchange rates, gain/loss, rounding, and party-account currency affect reconciliation;
9. how ERPNext mutates submitted Payment Entry references during reconciliation;
10. how Payment Ledger / Advance Payment Ledger / outstanding values are refreshed;
11. whether reconciliation is synchronous, background, or both in the installed version;
12. what concurrency guard exists;
13. what idempotency/retry behavior a future MCP wrapper requires;
14. what permissions are enforced by native code;
15. what India Compliance or other installed regional hooks affect the flow;
16. what approval + stale-state fingerprint a future MCP capability requires;
17. what bounded preview/result can be returned without leaking accounting internals;
18. what cancellation/reversal story exists after reconciliation;
19. what must remain completely out of scope for the first implementation.

---

## 4. Core Architecture Principle

Task 54 must preserve this project rule:

```text
MCP exposes capability.
ERPNext owns accounting truth.
```

MCP may eventually own:

- explicit business intent;
- typed public input;
- data minimization;
- permission-preserving source loading;
- bounded preview;
- approval;
- stale-state detection;
- transport/profile registration;
- bounded error translation.

ERPNext must continue to own:

- eligible payment/advance discovery;
- invoice outstanding;
- payment/reference allocation rules;
- Payment Terms;
- party and advance accounts;
- exchange rates;
- gain/loss;
- submitted Payment Entry mutation;
- GL;
- Payment Ledger;
- Advance Payment Ledger;
- outstanding recalculation;
- accounting reconciliation;
- hooks;
- permissions;
- concurrency semantics.

Do not design a second reconciliation engine in MCP.

---

## 5. Critical Non-Goal

This task is **not**:

```text
"implement reconciliation"
```

This task is:

```text
"find and document the exact ERPNext-native reconciliation seam
that a later narrow MCP capability can safely call"
```

Do not add production Python code.

Do not add MCP tools.

Do not mutate site/accounting data.

Do not create a Payment Entry, Sales Invoice, Journal Entry, GL Entry, Payment Ledger Entry, or reconciliation record.

---

## 6. Required Audit Inputs

Inspect the actual current repository and installed app versions.

At minimum use:

```text
apps/mcp_erpnext
apps/erpnext
apps/frappe
```

If installed:

```text
apps/india_compliance
```

Also inspect the existing project artifacts for Tasks 50–53, especially:

```text
Standalone Customer Payment Entry implementation/report
Customer Advance and Payment Reconciliation native-flow audit
Sales Order Customer Advance Payment implementation/report
Payment Entry read/query/aggregate implementation
Accounts lifecycle implementation
shared approval implementation
fixed REST operation registry
```

Do not assume an older task document is still correct if current source differs.

Current installed source is authoritative.

---

## 7. ERPNext Areas That Must Be Inspected

At minimum inspect the installed/current implementation around:

```text
erpnext/accounts/doctype/payment_reconciliation/
erpnext/accounts/doctype/process_payment_reconciliation/
erpnext/accounts/doctype/payment_entry/
erpnext/accounts/party.py
erpnext/controllers/accounts_controller.py
erpnext/accounts/utils.py
erpnext/accounts/general_ledger.py
erpnext/accounts/doctype/sales_invoice/
erpnext/selling/doctype/sales_order/
erpnext/accounts/doctype/payment_ledger_entry/
erpnext/accounts/doctype/advance_payment_ledger_entry/
```

Exact file/module names must be verified from the installed version.

Search for and trace exact call paths around concepts/functions such as:

```text
Payment Reconciliation
get_payment_entries
get_invoice_entries
allocate_entries
reconcile
reconcile_against_document
get_advance_entries
get_advance_payment_entries
get_advance_payment_entries_for_regional
set_advances
get_outstanding_reference_documents
update_voucher_outstanding
update_outstanding_amt
Payment Ledger
Advance Payment Ledger
```

Do not rely on names in this task if the installed version uses different names.

Document the actual installed names.

---

## 8. Frappe Areas That Must Be Inspected

Inspect relevant Frappe behavior for:

- document permission checks;
- submitted-document mutation rules;
- background jobs / enqueue if used;
- database transactions;
- locking/concurrency primitives if used by native reconciliation;
- whitelisted method exposure if applicable;
- session user identity;
- rollback/commit behavior;
- DocType metadata for Payment Reconciliation if it is virtual/non-persistent.

The audit must clearly distinguish:

```text
ERPNext business logic
vs
Frappe document/runtime mechanics
```

---

## 9. Verify Payment Reconciliation Document Semantics

Determine from installed source whether `Payment Reconciliation` is:

- persistent;
- virtual;
- transient/in-memory;
- or another pattern.

Verify the exact behavior of:

```text
load_from_db
save
db_insert
db_update
db_delete
```

if those overrides exist.

Answer:

1. Is a Payment Reconciliation document actually inserted?
2. Is a preview a persistent document or only operational state?
3. Can an MCP approval safely refer to a persistent reconciliation document?
4. If not, what source data must be fingerprinted instead?
5. What is the correct unit of idempotency for a future MCP confirmation?

Do not assume Payment Reconciliation behaves like Payment Entry.

---

## 10. Trace Payment Discovery

For one Customer + Company, determine exactly how native ERPNext identifies eligible existing payments/advances.

Trace at least:

```text
standalone unallocated Customer Payment Entry
Sales Order-linked Customer advance
separate advance-account payment
ordinary receivable-account payment
```

Determine native eligibility rules for:

- submitted state;
- party;
- company;
- account;
- payment type;
- unallocated amount;
- existing references;
- order-linked references;
- advance account;
- currency;
- posting date;
- reference date;
- Payment Terms;
- already reconciled value;
- cancelled records.

Answer whether a future V1 should require the caller to provide an exact Payment Entry name instead of asking ERPNext/MCP to search broadly.

Preferred safety direction to evaluate:

```text
exact Payment Entry + exact Sales Invoice + explicit amount
```

Do not freeze this until native source inspection proves it is appropriate.

---

## 11. Trace Sales Invoice Discovery and Outstanding Authority

Determine the exact native authority for current Sales Invoice outstanding during reconciliation.

Do not assume the stored:

```text
Sales Invoice.outstanding_amount
```

is always the correct sole authority.

Inspect whether native reconciliation relies on:

- Payment Ledger;
- account/party ledger queries;
- invoice outstanding query helpers;
- term-specific outstanding;
- advance account;
- currency-normalized values.

Document:

- exact source of current outstanding;
- precision behavior;
- Payment Terms behavior;
- submitted/cancelled filters;
- permission behavior.

A future MCP capability must use the same native authority, not a custom formula.

---

## 12. Trace Native Mutation End-to-End

This is the most important part of the audit.

For one eligible existing Customer payment/advance allocated to one Sales Invoice, trace the exact native mutation sequence.

Document:

```text
input operational rows
    ->
native allocation validation
    ->
native reconciliation function
    ->
submitted Payment Entry/reference mutation
    ->
ledger rebuild/update
    ->
invoice outstanding update
    ->
Sales Order advance update if relevant
    ->
hooks / regional behavior
```

For every mutation identify:

- module;
- function/method;
- document/row changed;
- whether normal `save()` is used;
- whether `db_set` / direct SQL / internal submitted-document update is used;
- permission boundary;
- validation boundary;
- transaction boundary.

The future MCP implementation must call the native operation instead of reproducing these mutations.

---

## 13. Submitted Payment Entry Mutation

Explicitly inspect how ERPNext safely changes a **submitted Payment Entry** during reconciliation.

Answer:

1. Are Payment Entry Reference child rows appended?
2. Are existing rows split?
3. Are allocation values changed?
4. Is `update_after_submit` involved?
5. Are internal flags used?
6. Does native code bypass ordinary editable-after-submit restrictions internally?
7. What current-state checks happen before mutation?
8. What prevents stale allocation?
9. Which fields are recalculated afterward?

This behavior must **never** be replaced with generic MCP update-document capability.

---

## 14. Sales Order-Linked Advance Behavior

Trace this exact business case:

```text
Submitted Sales Order
    ->
submitted Customer Advance Payment Entry linked to Sales Order
    ->
later submitted Sales Invoice
    ->
apply eligible advance to Sales Invoice
```

Determine:

- how native code recognizes the Sales Order-linked advance;
- whether the Sales Invoice must originate from that Sales Order;
- whether a Customer advance can be reconciled to another valid invoice for the same party/company/account;
- what source-order references remain after allocation;
- how `advance_paid` or equivalent Sales Order state changes;
- whether the original Sales Order reference is split/modified/retained;
- how partial allocation behaves.

Do not infer business rules from field names; trace source/tests.

---

## 15. Standalone Customer Receipt Interoperability

Task 50 creates a standalone Customer receipt with no invoice/order reference.

Audit whether that submitted Payment Entry can later be reconciled through the same native path.

Compare:

```text
A. standalone unallocated receipt
B. Sales Order-linked advance
```

Determine whether they can safely use one future public capability such as:

```text
prepare_customer_payment_reconciliation
confirm_customer_payment_reconciliation
```

or whether they need different public business tools because their native eligibility/accounting semantics differ.

The audit must make a recommendation with evidence.

---

## 16. Separate Customer Advance Account

Inspect Company behavior when:

```text
book_advance_payments_in_separate_party_account = enabled
```

Determine:

- which account contains the advance;
- how reconciliation discovers it;
- whether invoice receivable account differs;
- whether native reconciliation transfers/reclassifies amounts;
- how Payment Ledger / Advance Payment Ledger is affected;
- whether an extra Journal Entry is created;
- whether account selection is automatic;
- what happens when configuration/default advance account is missing.

Future MCP must not expose raw advance-account selection unless native source proves it is required.

---

## 17. Payment Terms

Audit reconciliation with Payment Terms.

Determine whether native discovery/allocation is:

- invoice-level;
- payment-term-row-level;
- both.

Inspect:

- term-specific outstanding;
- payment schedule references;
- partial term allocation;
- early-payment discount interaction;
- multiple term rows;
- stale term state.

Decide whether first MCP V1 should:

```text
support Payment Terms natively
```

or:

```text
explicitly reject term-specific reconciliation until a later capability
```

Do not silently flatten term rows.

---

## 18. Currency and Exchange Rate

Trace native reconciliation for:

- Customer payment and invoice in same currency;
- account currency different from invoice currency;
- bank currency different from party/account currency;
- foreign-currency Sales Order advance;
- exchange-rate drift between payment date and reconciliation date;
- gain/loss;
- rounding;
- tiny residuals.

Identify:

- which amount is public-business meaningful;
- which amount is authoritative for allocation;
- whether user must provide an amount in account currency, invoice currency, or another context;
- whether native reconciliation generates gain/loss Journal Entry or deductions;
- which rate/date drives calculation.

MCP must not implement any exchange/gain-loss formula.

---

## 19. Regional / India Compliance Behavior

If India Compliance is installed, inspect its current hooks/overrides relevant to:

- Payment Entry;
- Sales Invoice;
- advance discovery;
- Payment Reconciliation;
- tax allocation/reversal;
- submit/cancel/update-after-submit.

Determine:

- whether base ERPNext reconciliation entry points automatically preserve installed hooks;
- whether a regional wrapper must be called instead;
- whether any hook adds required input;
- whether any hook changes the future V1 boundary.

The design must remain optional-app neutral.

If India Compliance is not installed on another site, base ERPNext behavior must still work.

---

## 20. Permission Boundary

Trace native permissions for:

```text
Customer
Payment Entry
Sales Invoice
Payment Reconciliation
Account / advance account
Company
```

Answer:

1. Does native Payment Reconciliation explicitly check Payment Entry read/write permission?
2. Does invoice discovery check per-invoice read permission?
3. Does ledger-query discovery bypass ordinary DocType read permission?
4. What explicit MCP-side exact-source permission checks are needed before native calls?
5. What Accounts roles are required by Payment Reconciliation metadata/native methods?
6. Does background reconciliation execute under the initiating user or another execution identity?

Future MCP must run under the authenticated ERPNext identity.

Do not introduce public `user`, `role`, or permission-bypass inputs.

---

## 21. Synchronous vs Background Reconciliation

Inspect native `Process Payment Reconciliation` or equivalent installed code.

Determine:

- when background reconciliation is used;
- threshold/conditions if any;
- queue/job structure;
- how progress/status is stored;
- whether another process for the same party/company/account is blocked;
- pause/resume behavior;
- failure/retry behavior;
- user identity used by the job;
- transaction granularity.

Then decide whether V1 should be:

```text
synchronous only for one-payment -> one-invoice
```

or whether even that flow should use the background mechanism.

Prefer the smallest deterministic synchronous path only if native source/tests support it safely.

Do not build custom queuing in MCP during this task.

---

## 22. Concurrency

Identify native conflict protection for reconciliation.

Inspect for:

- running-process checks;
- locks;
- modified timestamps;
- latest outstanding re-check;
- latest unallocated amount re-check;
- reference modification checks;
- database transaction boundaries.

Design a future MCP stale-confirmation model that complements native checks.

At minimum evaluate fingerprinting:

```text
Payment Entry name
Payment Entry docstatus
Payment Entry modified signal
party
company
payment/account currency
current unallocated / eligible reference state
current Payment Entry references
Sales Invoice name
Sales Invoice docstatus
Sales Invoice modified signal
Customer
Company
receivable/advance account
current native outstanding
Payment Terms state
allocation amount
exchange/rate state
separate advance-account setting
regional/native material state
```

Exact fingerprint fields must come from audit findings.

---

## 23. Idempotency and Replay

A future confirm operation must be one-shot, but ERPNext mutation may also have native duplicate protections.

Audit:

- what happens if the same reconciliation is executed twice;
- whether second allocation fails, becomes zero, or duplicates references;
- whether native utilities are idempotent;
- whether background jobs can retry;
- whether partial mutation can occur before failure.

Recommend an MCP idempotency policy using the existing shared approval store.

Do not create an idempotency implementation in Task 54.

---

## 24. Reversal / Undo / Cancellation

Determine how an already-reconciled payment can be reversed or deallocated.

Inspect whether ERPNext supports:

- unreconcile;
- remove allocation;
- Payment Reconciliation undo;
- Payment Entry cancel;
- Sales Invoice cancel;
- reference-row reversal;
- ledger repost/rebuild.

Answer:

1. Is there a native "unreconcile" operation?
2. Is canceling Payment Entry sufficient/allowed after reconciliation?
3. What linked-document restrictions apply?
4. Does reconciliation need its own future reversal capability?
5. Should V1 intentionally exclude reversal and rely on existing native lifecycle only?

Do not design a custom reversal algorithm.

---

## 25. Candidate V1 Public Contract

After source inspection, compare at least these options.

### Option A — Exact one Payment Entry -> exact one Sales Invoice

Potential prepare intent:

```text
payment_entry
sales_invoice
amount
```

Pros to evaluate:

- narrow;
- deterministic;
- easier approval/fingerprint;
- avoids broad discovery;
- lower concurrency surface.

Risks to evaluate:

- Payment Terms;
- order-linked advance references;
- separate advance account;
- currency amount context;
- submitted Payment Entry mutation.

### Option B — Exact Customer + invoice + automatic eligible advance selection

Potential intent:

```text
customer
sales_invoice
amount
```

Risks:

- MCP/native layer must choose among multiple eligible payments;
- hidden allocation policy;
- less deterministic;
- larger approval surface.

### Option C — Multi-payment / multi-invoice reconciliation

Keep deferred unless the audit proves it is necessary for the smallest useful capability.

The audit must recommend one option and explain why.

Do not implement any option in Task 54.

---

## 26. Public Input Minimization

For the recommended future V1, identify the minimum safe public fields.

Preferred direction to evaluate:

```text
exact payment_entry
exact sales_invoice
explicit positive allocation amount
```

Potentially no public fields for:

```text
Customer
Company
party account
advance account
reference row
exchange rate
GL account
Payment Ledger
Payment Terms row
cost center
project
accounting dimensions
```

because those may be native-derived.

Document any field that genuinely must be public and why.

---

## 27. Public Output / Preview Minimization

Define a bounded future prepare preview.

Likely useful fields to evaluate:

```text
Payment Entry
payment type
Customer
Company
payment date
safe source description
current native available/unallocated amount
Sales Invoice
invoice date
current native outstanding
allocation amount
currencies
separate advance-account branch
Payment Terms summary if material
exchange/gain-loss warning if material
native reconciliation warning
post-reconciliation projected outstanding
```

Do not expose:

```text
raw Payment Entry JSON
raw Sales Invoice JSON
full Chart of Accounts
arbitrary Account lists
raw GL Entry rows
raw Payment Ledger rows
bank numbers
IBAN/SWIFT
secrets
SQL
tracebacks
```

If projected outstanding is returned, define whether it is native-derived or presentation arithmetic only. Do not make a presentation calculation the accounting authority.

---

## 28. Approval Model for Future Implementation

Design, but do not implement, the future prepare/confirm pattern.

Expected architecture to evaluate:

```text
prepare_customer_payment_reconciliation
    ->
load exact payment + invoice
    ->
native current-state discovery
    ->
native reconciliation preview/projection
    ->
bounded approval preview
    ->
shared approval token

confirm_customer_payment_reconciliation
    ->
atomic approval claim
    ->
fresh reload
    ->
fresh native eligibility/outstanding
    ->
fresh fingerprint
    ->
stale comparison
    ->
native reconciliation mutation
    ->
bounded result
```

Critical questions:

- Can native reconciliation produce a true side-effect-free preview?
- If not, how should prepare derive a trustworthy preview without mutating?
- What data is sufficient to fingerprint?
- Should confirm call a public DocType method, internal ERPNext utility, or another native seam?
- Does native operation commit internally?
- Can confirm safely rollback on failure?

Document exact answers from source.

---

## 29. Future Tool Naming

Do not add tools in Task 54.

Recommend names only after choosing the native boundary.

Candidate naming:

```text
prepare_customer_payment_reconciliation
confirm_customer_payment_reconciliation
```

or a more explicit name if the capability is only one Payment Entry -> one Sales Invoice.

Names must describe business intent, not expose a generic accounting engine.

Do not recommend:

```text
reconcile_anything
generic_reconcile
execute_payment_reconciliation
update_payment_entry_reference
```

---

## 30. Accounts Profile Boundary

Any future capability must belong only to:

```text
MCP_PROFILE=accounts
```

Task 54 must not change:

```text
sales profile
purchase profile
```

Purchase remains deferred for current business use cases.

Do not expand Supplier/Purchase flows.

---

## 31. REST Boundary

Inspect how current Accounts tools are exposed through fixed REST operations.

Recommend how a future reconciliation pair would preserve:

```text
typed operation
fixed registry
authenticated identity
same service authority as direct MCP path
```

Do not recommend:

- arbitrary Frappe method invocation;
- arbitrary DocType mutation;
- raw Payment Reconciliation payload forwarding;
- user/site supplied dispatch;
- generic internal-method execution.

---

## 32. Error Model Recommendation

The audit must propose bounded error categories for the future capability.

At minimum evaluate:

```text
PAYMENT_ENTRY_NOT_FOUND
PAYMENT_ENTRY_NOT_SUBMITTED
PAYMENT_ENTRY_NOT_ELIGIBLE
PAYMENT_ENTRY_PERMISSION_DENIED
SALES_INVOICE_NOT_FOUND
SALES_INVOICE_NOT_SUBMITTED
SALES_INVOICE_NOT_OUTSTANDING
SALES_INVOICE_PERMISSION_DENIED
PARTY_MISMATCH
COMPANY_MISMATCH
ACCOUNT_MISMATCH
INVALID_ALLOCATION_AMOUNT
ALLOCATION_EXCEEDS_AVAILABLE_PAYMENT
ALLOCATION_EXCEEDS_OUTSTANDING
PAYMENT_TERMS_UNSUPPORTED
CURRENCY_CONFIGURATION_ERROR
RECONCILIATION_ALREADY_RUNNING
STALE_CONFIRMATION
APPROVAL_REQUIRED
APPROVAL_EXPIRED
APPROVAL_ALREADY_USED
PERMISSION_DENIED
NATIVE_VALIDATION_FAILED
```

Use the project's existing error conventions where equivalent names already exist.

Do not invent a parallel error framework.

---

## 33. Source/Test Evidence Required

Inspect ERPNext's own tests for:

- Payment Reconciliation;
- Payment Entry advances;
- unallocated Customer payments;
- Sales Order advances;
- Sales Invoice advance allocation;
- multiple payments;
- multiple invoices;
- Payment Terms;
- separate advance account;
- foreign currency;
- gain/loss;
- cancellation;
- concurrency/background process.

For each important design decision, cite source/test path and relevant function/test name in the audit report.

Static source evidence and live behavior must be distinguished.

---

## 34. Optional Live Inspection

Task 54 is inspection-only.

Live mutation is **not allowed** unless separately authorized.

Safe read-only live inspection may be used only if current project conventions allow it and it does not expose secrets or mutate data.

Do not:

```text
create Payment Entry
submit Payment Entry
reconcile payment
modify Sales Invoice
modify Sales Order
create Journal Entry
change Company settings
change accounts
run destructive migration
```

If live behavior is not tested, explicitly state it as unverified.

---

## 35. Allowed Changes

Task 54 may create/update only the audit deliverable required by this task.

Expected deliverable:

```text
docs/inspect/CUSTOMER_PAYMENT_TO_SALES_INVOICE_RECONCILIATION_NATIVE_CAPABILITY_AUDIT.md
```

If the repository's existing naming convention requires a slightly different audit filename, preserve the convention and document the actual path.

Do not modify production implementation.

Do not modify tests except if the project explicitly treats source-inspection notes as non-production test assets; default is **no test changes**.

---

## 36. Forbidden Changes

Do not modify:

```text
mcp_erpnext/contracts/**
mcp_erpnext/services/**
mcp_erpnext/tools/**
mcp_erpnext/profiles/**
mcp_erpnext/remote_operations.py
mcp_erpnext/settings.py
mcp_erpnext/tests/**
hooks.py
DocType JSON
patches
fixtures
migrations
Frappe source
ERPNext source
India Compliance source
site_config.json
Company settings
Accounts
Bank Accounts
Mode of Payment
live business documents
database records
Redis approval state
```

Do not regenerate `docs/TOOLS.md` because no public tool changes in this audit.

---

## 37. Required Audit Steps

Execute the audit in this order.

### Step 1 — Establish repository state

Record:

- current branch;
- current commit;
- dirty worktree;
- pre-existing modified/untracked files;
- installed Frappe version;
- installed ERPNext version;
- installed India Compliance version if present.

Do not overwrite pre-existing changes.

### Step 2 — Inspect current Accounts implementation

Trace current:

- Task 50 standalone Customer Payment Entry;
- Task 53 Sales Order advance;
- Sales Invoice payment;
- multi-invoice receipt;
- Payment Entry lifecycle;
- approval store;
- fingerprint helper;
- REST registry;
- Accounts profile.

Establish what can be reused later.

### Step 3 — Inspect Payment Reconciliation DocType

Trace document semantics, discovery, allocation, validation, and reconcile mutation.

### Step 4 — Inspect background reconciliation

Trace Process Payment Reconciliation or current equivalent.

### Step 5 — Trace one unallocated receipt -> one invoice

Follow full native path.

### Step 6 — Trace one Sales Order-linked advance -> one invoice

Follow full native path.

### Step 7 — Compare both paths

Determine whether one public contract safely covers both.

### Step 8 — Trace separate advance account

Document differences.

### Step 9 — Trace Payment Terms

Document whether V1 can safely support them.

### Step 10 — Trace currency / gain-loss

Document exact native authority.

### Step 11 — Trace permissions

Document MCP-side minimum exact-source permission checks.

### Step 12 — Trace concurrency/idempotency

Document stale/retry/background behavior.

### Step 13 — Trace reversal

Determine future rollback/unreconcile scope.

### Step 14 — Design smallest safe V1

Recommend one exact public contract, not implementation.

### Step 15 — Produce implementation recommendation

Specify exact next task with:

- tool names;
- public fields;
- native call path;
- prepare semantics;
- confirm semantics;
- approval/fingerprint;
- error model;
- tests;
- explicit exclusions.

---

## 38. Questions the Final Audit Must Answer

The report is incomplete unless it directly answers all of these:

1. What is the exact installed native reconciliation entry point?
2. Is Payment Reconciliation persistent or virtual?
3. What is the exact native payment discovery path?
4. What is the exact native invoice outstanding authority?
5. How is a submitted Payment Entry mutated?
6. How are Payment Ledger entries rebuilt/updated?
7. How is Sales Invoice outstanding recalculated?
8. How is Sales Order advance state affected?
9. Can Task 50 standalone receipts be reconciled by the same native path?
10. Can Task 53 Sales Order advances be reconciled by the same native path?
11. Can one future MCP public capability safely cover both?
12. What is the smallest safe V1 shape?
13. Is one Payment Entry -> one Sales Invoice the recommended V1?
14. What amount/currency does the caller specify?
15. How do Payment Terms change the flow?
16. How does separate advance account configuration change the flow?
17. How do foreign currency and gain/loss change the flow?
18. Is reconciliation synchronous or background for V1?
19. What concurrency protection exists?
20. What stale-state fingerprint is required?
21. What idempotency behavior is required?
22. What permissions must MCP explicitly check?
23. What optional-app hooks apply?
24. How can reconciliation be reversed?
25. What must be excluded from the first implementation?
26. What exact Task 55 should be implemented next?

---

## 39. Acceptance Criteria

Task 54 is complete only if all criteria pass.

### AC-01
Only an audit report is created/updated; no production MCP/Frappe/ERPNext implementation changes.

### AC-02
Current Frappe/ERPNext/optional-app versions and repository state are recorded.

### AC-03
Installed ERPNext Payment Reconciliation implementation is traced from discovery through mutation.

### AC-04
Payment Reconciliation persistence/virtual-document semantics are explicitly proven from source.

### AC-05
Standalone Customer receipt -> Sales Invoice native flow is traced.

### AC-06
Sales Order-linked Customer advance -> Sales Invoice native flow is traced.

### AC-07
The audit determines whether both can share one future public MCP capability.

### AC-08
Sales Invoice outstanding authority is identified from native source.

### AC-09
Submitted Payment Entry mutation semantics are documented.

### AC-10
Payment Ledger / outstanding update path is documented.

### AC-11
Separate Customer advance account behavior is documented.

### AC-12
Payment Terms behavior is documented.

### AC-13
Currency/exchange/gain-loss behavior is documented.

### AC-14
Synchronous/background reconciliation behavior is documented.

### AC-15
Concurrency and already-running reconciliation behavior are documented.

### AC-16
Idempotency/replay behavior is documented.

### AC-17
Permission and authenticated-user boundaries are documented.

### AC-18
India Compliance/regional hooks are documented if installed.

### AC-19
Reversal/unreconcile behavior is documented.

### AC-20
A single smallest-safe future V1 contract is recommended.

### AC-21
The recommended public contract does not expose raw accounting internals.

### AC-22
The recommended implementation does not duplicate ERPNext reconciliation logic.

### AC-23
The future approval/fingerprint design is specified.

### AC-24
Future direct/REST/profile boundaries are specified.

### AC-25
Future test matrix is specified.

### AC-26
Static evidence is clearly separated from unverified live behavior.

### AC-27
Exact Task 55 recommendation is included.

---

## 40. Future Implementation Test Matrix to Design

The audit must define tests for Task 55, at minimum covering:

### Contract

- exact payment;
- exact invoice;
- positive finite allocation;
- forbidden extra fields;
- no raw accounts;
- no user/site override.

### Eligibility

- missing payment;
- Draft payment;
- cancelled payment;
- wrong payment type;
- wrong Customer;
- wrong Company;
- no allocatable/unallocated value;
- missing invoice;
- Draft invoice;
- cancelled invoice;
- fully paid invoice;
- return/credit-note cases according to audit decision.

### Allocation

- partial payment;
- partial invoice;
- exact full allocation;
- amount above available payment;
- amount above invoice outstanding;
- already-reconciled payment.

### Source Type

- Task 50 standalone receipt;
- Task 53 Sales Order-linked advance.

### Accounting Configuration

- normal party account;
- separate advance account;
- Payment Terms;
- foreign currency;
- gain/loss/rounding.

### Approval / Stale State

- missing approval;
- wrong user;
- wrong site;
- replay;
- payment changes after prepare;
- invoice outstanding changes after prepare;
- another reconciliation completes after prepare;
- account/config/rate changes.

### Concurrency

- reconciliation process already running;
- duplicate simultaneous confirm;
- native stale conflict.

### Permissions

- Payment Entry unreadable;
- Sales Invoice unreadable;
- reconciliation permission denied;
- account/company visibility failure.

### Regional

- India Compliance hooks where applicable.

### Regression

- Task 50 standalone payment;
- Task 53 Sales Order advance;
- Sales Invoice payment;
- multi-invoice receipt;
- Payment Entry lifecycle;
- read/query/aggregate;
- approval;
- REST;
- profiles.

---

## 41. Expected Result

The audit should end with a clear architecture like one of these:

```text
Exact submitted Payment Entry
        +
Exact submitted Sales Invoice
        +
Explicit allocation amount
        |
        v
prepare native reconciliation preview
        |
        v
shared approval
        |
        v
fresh native state + stale check
        |
        v
ERPNext native reconcile operation
        |
        v
native submitted Payment Entry reference mutation
        |
        v
native Payment Ledger / outstanding update
```

or, if installed source proves that shape is unsafe, a narrower alternative.

The audit must not end with a vague statement such as:

```text
"ERPNext supports reconciliation."
```

It must produce an implementation-ready native call map and contract recommendation.

---

## 42. Limitations

This task does not prove live site behavior unless separately tested.

Potential site-specific variables include:

- Company separate advance-account setting;
- actual Customer advance account;
- Chart of Accounts;
- currency defaults;
- Payment Terms;
- permissions;
- India Compliance installation/configuration;
- existing submitted payments;
- existing invoice outstanding;
- Redis/shared approval;
- queue workers;
- background reconciliation state.

Document these as live-verification boundaries.

---

## 43. Required Deliverable Structure

Create:

```text
docs/inspect/CUSTOMER_PAYMENT_TO_SALES_INVOICE_RECONCILIATION_NATIVE_CAPABILITY_AUDIT.md
```

The report must contain at least:

1. Executive conclusion
2. Scope and non-goals
3. Repository/version context
4. Current MCP Accounts baseline
5. Payment Reconciliation document semantics
6. Native payment discovery
7. Native invoice/outstanding discovery
8. Standalone Customer receipt flow
9. Sales Order-linked advance flow
10. Submitted Payment Entry mutation chain
11. Ledger/outstanding update chain
12. Separate advance account
13. Payment Terms
14. Currency/exchange/gain-loss
15. Permissions
16. Regional/India Compliance hooks
17. Background processing
18. Concurrency
19. Idempotency/retry
20. Reversal/unreconcile behavior
21. Public capability options
22. Recommended smallest V1
23. Recommended typed input/output
24. Approval/fingerprint design
25. REST/profile placement
26. Error model
27. Future test matrix
28. Risks and live boundaries
29. Exact Task 55 recommendation

Every important technical conclusion must reference installed source/test paths and relevant functions/tests.

---

## 44. Exact Next Task

If Task 54 proves that a narrow single-payment/single-invoice native wrapper is safe, recommend:

```text
Task 55 — Customer Payment / Advance to Sales Invoice Reconciliation V1 Implementation
```

Expected narrow shape, subject to Task 54 findings:

```text
prepare_customer_payment_reconciliation
confirm_customer_payment_reconciliation
```

Likely intent:

```text
payment_entry
sales_invoice
allocated_amount
```

Task 55 must:

- be Accounts-profile only;
- use exact Payment Entry + exact Sales Invoice;
- use explicit allocation;
- preserve ERPNext native reconciliation;
- use shared approval;
- fresh-revalidate at confirm;
- not expose raw accounts/references;
- not implement custom outstanding/reconciliation formulas;
- not add multi-payment/multi-invoice allocation unless Task 54 explicitly proves it belongs in V1.

If Task 54 finds that this shape is unsafe or incomplete, Task 55 must use the narrower safe shape recommended by the audit instead.

---

## 45. Final Principle

The task is successful only if the next implementation can be written as a **thin capability adapter over ERPNext-native reconciliation**, not as custom accounting logic.

Target architecture:

```text
User business intent
    ->
typed MCP Accounts capability
    ->
permission-aware exact source loading
    ->
ERPNext-native eligibility/outstanding
    ->
bounded preview
    ->
shared approval
    ->
fresh native revalidation
    ->
ERPNext-native reconciliation
    ->
ERPNext-native ledger/outstanding effects
```

MCP must never become the accounting system of record.
