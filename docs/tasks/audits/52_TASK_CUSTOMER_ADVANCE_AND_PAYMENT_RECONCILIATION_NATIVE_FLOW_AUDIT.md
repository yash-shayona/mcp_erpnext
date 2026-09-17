# Task 52 - Customer Advance and Payment Reconciliation Native Flow Audit

## Status

**Inspection-only / architecture audit**

This task continues the current **Sales + Accounts** roadmap.

Purchase profile work is intentionally deferred. Do not expand Purchase in this task.

The current business is service-selling focused, so the next investigation must stay inside the existing Sales and Accounts boundary.

Current implemented Accounts capabilities include:

```text
Submitted Sales Invoice
    -> prepare_sales_invoice_payment
    -> approval
    -> confirm_sales_invoice_payment
    -> Draft Payment Entry
    -> generic lifecycle submit/cancel/delete

Multiple submitted Sales Invoices
    -> prepare_multi_invoice_customer_receipt
    -> approval
    -> confirm_multi_invoice_customer_receipt
    -> one Draft Payment Entry

Customer + Company + Amount
    -> prepare_customer_payment_entry
    -> approval
    -> confirm_customer_payment_entry
    -> standalone Draft Customer Payment Entry
    -> no invoice/order reference

Existing Payment Entry
    -> get_payment_entry
    -> query_payment_entries
    -> aggregate_payment_entries
```

Task 50 intentionally creates a standalone Customer receipt with no Sales Invoice or Sales Order reference. It does not implement a Sales Order-linked advance or later reconciliation/allocation.

The next missing business capability is therefore the **customer advance lifecycle**.

---

# 1. Objective

Audit the exact native ERPNext v16 architecture for these two related but distinct customer-advance flows:

```text
FLOW A - ORDER-LINKED ADVANCE

Submitted Sales Order
    -> native ERPNext customer advance Payment Entry
    -> Draft Payment Entry
    -> existing MCP lifecycle submit
    -> Sales Order advance state updated by ERPNext
    -> later Sales Invoice
    -> native advance allocation behavior
```

and:

```text
FLOW B - EXISTING UNALLOCATED CUSTOMER RECEIPT

Submitted standalone Customer Payment Entry
    -> still has available/unallocated amount
    -> later submitted/draft Sales Invoice as supported by ERPNext
    -> native ERPNext reconciliation/allocation mechanism
    -> invoice/payment reference state updated by ERPNext
```

The audit must determine the **smallest safe MCP capabilities** required to expose these existing ERPNext business functions.

The audit must NOT design or implement a custom reconciliation engine.

---

# 2. Core Architecture Principle - Frozen

The architecture rule is:

```text
ERPNext owns:
- accounting rules
- Payment Entry construction/defaulting
- advance rules
- party account resolution
- separate advance account policy
- outstanding calculations
- allocation validation
- reconciliation
- exchange-rate behavior
- GL Entry creation
- Payment Ledger Entry creation
- Sales Order advance_paid behavior
- Sales Invoice outstanding behavior
- cancellation/reversal effects
- accounting dimensions
- taxes / withholding / regional hooks

MCP owns only:
- an explicit business capability
- typed and bounded public input
- permission-aware source resolution
- safe preview
- approval
- stale-state/fingerprint protection
- invoking the correct native ERPNext operation
- bounded output
- direct/REST parity
```

Never implement accounting truth in MCP.

Do NOT create logic equivalent to:

```text
outstanding = invoice_total - payment
advance_remaining = payment_amount - allocated_amount
sales_order.advance_paid = ...
sales_invoice.outstanding_amount = ...
```

Do NOT manually create, update, or delete:

```text
GL Entry
Payment Ledger Entry
Payment Entry Reference
Sales Invoice Advance
Sales Order advance_paid
Sales Invoice outstanding_amount
```

unless the installed ERPNext native API itself performs those changes as part of its normal supported flow.

---

# 3. Scope

Task 52 is an audit of **Customer Receive / Sales-side Accounts behavior only**.

In scope:

1. Customer advance against a submitted Sales Order.
2. Partial and full Sales Order advance.
3. Native Payment Entry factory behavior for Sales Order references.
4. How ERPNext records and updates Sales Order advance state.
5. How a later Sales Invoice discovers or receives an order-linked advance.
6. How Task 50 standalone/unallocated Customer receipts become allocatable later.
7. Native Payment Reconciliation architecture.
8. Native invoice advance allocation architecture.
9. Interaction between Payment Entry references and Sales Invoice advance rows.
10. Separate party advance account behavior in ERPNext v16.
11. Currency and exchange-rate behavior.
12. Payment Terms / order totals / invoiced amounts where relevant.
13. Permissions.
14. Approval and stale-state design.
15. Concurrency and auto-reconciliation conflicts.
16. Direct and REST MCP parity requirements.
17. Exact public capability boundaries for future tasks.
18. Exact smallest next implementation task.

Out of scope:

```text
Supplier advances
Purchase Order
Purchase Invoice
Purchase Payment Entry
Internal Transfer
Journal Entry builder
bank reconciliation
Payment Request implementation
refund implementation
credit-note implementation
write-off implementation
manual GL adjustments
auto-reconcile scheduler implementation
generic arbitrary reconciliation tool
generic arbitrary Payment Entry builder
```

---

# 4. Required Inputs

Use these inputs as the evidence base.

## 4.1 Current mcp_erpnext repository

Inspect the latest repository supplied for this task.

Do not assume an older ZIP or report is current.

At minimum confirm the actual current state of:

```text
mcp_erpnext/profiles/accounts.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/settings.py
mcp_erpnext/remote_operations.py
mcp_erpnext/runtime.py
mcp_erpnext/approvals.py

mcp_erpnext/contracts/accounts/sales_invoice_payment.py
mcp_erpnext/contracts/accounts/multi_invoice_customer_receipt.py
mcp_erpnext/contracts/accounts/customer_payment_entry.py
mcp_erpnext/contracts/accounts/payment_entry_read.py

mcp_erpnext/services/accounts/sales_invoice_payment.py
mcp_erpnext/services/accounts/multi_invoice_customer_receipt.py
mcp_erpnext/services/accounts/customer_payment_entry.py
mcp_erpnext/services/accounts/payment_entry_read.py

mcp_erpnext/tools/accounts/sales_invoice_payment.py
mcp_erpnext/tools/accounts/multi_invoice_customer_receipt.py
mcp_erpnext/tools/accounts/customer_payment_entry.py
mcp_erpnext/tools/accounts/payment_entry_read.py

mcp_erpnext/services/common/lifecycle.py
mcp_erpnext/services/common/fingerprint.py

mcp_erpnext/tests/test_accounts_sales_invoice_payment.py
mcp_erpnext/tests/test_multi_invoice_customer_receipt.py
mcp_erpnext/tests/test_customer_payment_entry.py
mcp_erpnext/tests/test_payment_entry_read.py
mcp_erpnext/tests/test_lifecycle.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_rest_backend.py

docs/TOOLS.md
docs/MCP_PROFILES.md
```

Also inspect previous Accounts reports:

```text
docs/inspect/ACCOUNTS_PAYMENT_ENTRY_NATIVE_FLOW_AUDIT.md
docs/inspect/ACCOUNTS_V1_SALES_INVOICE_PAYMENT_IMPLEMENTATION_REPORT.md
docs/inspect/PAYMENT_ENTRY_READ_QUERY_AGGREGATE_IMPLEMENTATION_REPORT.md
docs/inspect/MULTI_INVOICE_CUSTOMER_RECEIPT_IMPLEMENTATION_REPORT.md
docs/inspect/STANDALONE_CUSTOMER_PAYMENT_ENTRY_IMPLEMENTATION_REPORT.md
```

If any named file differs in the current checkout, document the actual current path/state instead of forcing an old assumption.

## 4.2 Installed ERPNext source

The exact installed ERPNext source is the primary business-logic authority.

At minimum inspect the installed equivalents of:

```text
erpnext/accounts/doctype/payment_entry/payment_entry.py
erpnext/accounts/doctype/payment_entry/payment_entry.json
erpnext/accounts/doctype/payment_entry/payment_entry.js
erpnext/accounts/doctype/payment_entry/test_payment_entry.py

erpnext/accounts/doctype/payment_reconciliation/payment_reconciliation.py
erpnext/accounts/doctype/payment_reconciliation/payment_reconciliation.json

erpnext/accounts/utils.py
erpnext/accounts/services/advances.py

erpnext/controllers/accounts_controller.py

erpnext/selling/doctype/sales_order/sales_order.py
erpnext/selling/doctype/sales_order/sales_order.json

erpnext/accounts/doctype/sales_invoice/sales_invoice.py
erpnext/accounts/doctype/sales_invoice/sales_invoice.json
```

Also inspect relevant Frappe permission/document persistence code only where needed to prove behavior.

## 4.3 Official upstream evidence

Use only official Frappe/ERPNext documentation and official `frappe/erpnext` or `frappe/frappe` repository evidence for behavior not fully clear from the installed source.

Installed source wins if it differs from a newer/older documentation page.

---

# 5. Allowed Changes

Task 52 is inspection-only.

The only repository file that may be created or updated is:

```text
docs/inspect/CUSTOMER_ADVANCE_AND_PAYMENT_RECONCILIATION_NATIVE_FLOW_AUDIT.md
```

No production implementation is allowed.

Do not modify the Task 52 task file during execution unless the user explicitly asks for task-spec corrections.

---

# 6. Forbidden Changes

Do NOT change:

```text
mcp_erpnext/**/*.py
mcp_erpnext/**/*.json
mcp_erpnext/profiles/**
mcp_erpnext/contracts/**
mcp_erpnext/services/**
mcp_erpnext/tools/**
mcp_erpnext/tests/**
remote operation registry
lifecycle policy
approval implementation
settings
hooks
DocTypes
fixtures
patches
migrations
site_config
ERPNext source
Frappe source
India Compliance source
```

Do NOT:

```text
create Payment Entries
submit Payment Entries
cancel Payment Entries
delete Payment Entries
create Sales Orders
submit Sales Orders
create Sales Invoices
submit Sales Invoices
reconcile any payment
unreconcile any payment
change Accounts Settings
change Selling Settings
change Company defaults
change Mode of Payment defaults
change Bank Accounts
change Chart of Accounts
change Payment Ledger Entries
change GL Entries
run migrations
run destructive bench commands
```

No live accounting mutation is authorized by this audit.

---

# 7. Current Baseline to Verify First

Before investigating new capability design, verify the current public Accounts surface from code and generated catalog.

Expected baseline from the supplied latest ZIP is approximately:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment

prepare_multi_invoice_customer_receipt
confirm_multi_invoice_customer_receipt

prepare_customer_payment_entry
confirm_customer_payment_entry

get_payment_entry
query_payment_entries
aggregate_payment_entries

prepare_submit_document
confirm_submit_document
prepare_cancel_document
confirm_cancel_document
prepare_delete_document
confirm_delete_document
```

Do not treat this list as authoritative until current registration and catalog are inspected.

Confirm that Task 50 standalone Customer Payment Entry intentionally has no order/invoice reference.

Confirm whether Payment Entry lifecycle policy is Accounts-only and which actions are currently allowed.

---

# 8. Flow A - Sales Order Customer Advance

Audit the exact ERPNext native path for:

```text
Submitted Sales Order
    -> Customer Receive Payment Entry
    -> reference to Sales Order
    -> Draft Payment Entry
    -> submit
    -> Sales Order advance state
```

At minimum answer:

1. Is the installed native factory still `get_payment_entry("Sales Order", name, ...)`?
2. What source document state does it require?
3. What permissions does the factory check?
4. How does it derive Customer?
5. How does it derive Company?
6. How does it derive party receivable account?
7. How does it resolve bank/cash destination?
8. What does `party_amount` mean for a Sales Order source?
9. What does `bank_amount` mean for cross-currency cases?
10. Does the native result include a `Payment Entry Reference` row against the Sales Order?
11. Which reference fields are populated?
12. What amount is considered available/allocated against the order?
13. What happens when the Payment Entry is submitted?
14. What native code updates `Sales Order.advance_paid` or equivalent state?
15. What happens on Payment Entry cancellation?
16. What happens for a partially invoiced Sales Order?
17. What happens if advance exceeds the remaining order amount?
18. What happens if a Sales Order is closed/completed/cancelled?
19. What happens if the Sales Order is fully billed?
20. What happens if the Payment Entry is created in another currency?

Do not implement any of these behaviors in MCP.

Trace them to native ERPNext code/tests.

---

# 9. Prove Native Sales Order Advance Behavior

The audit must find installed-source proof equivalent to ERPNext's native Payment Entry tests for an order advance.

Look for native tests/functions equivalent to:

```text
get_payment_entry("Sales Order", sales_order_name, ...)
Payment Entry insert
Payment Entry submit
Sales Order advance_paid changes
Payment Entry cancel
Sales Order advance_paid restoration
```

Record the exact installed file paths, methods, and test names.

Do not rely only on documentation prose.

---

# 10. Future Public Capability Candidate - Sales Order Advance

Evaluate a future explicit business capability shaped approximately as:

```text
prepare_sales_order_advance_payment
confirm_sales_order_advance_payment
```

This is a candidate name, not permission to implement it in Task 52.

The audit must determine the smallest safe public input.

Prefer business intent such as:

```text
sales_order
amount
mode_of_payment OR bank_account
posting_date (only if safe and intentionally supported)
reference_no
reference_date
bank_amount (only when native currency behavior requires it)
remarks
```

The public contract must NOT expose raw accounting internals such as:

```text
paid_from
paid_to
party account
account currency
source exchange rate
target exchange rate
Payment Entry Reference dicts
GL rows
Payment Ledger rows
deductions
taxes
arbitrary dimensions
arbitrary account names
ignore_permissions
ignore_links
ignore_mandatory
```

If installed ERPNext requires an input not listed above, explain why and whether it is safe for the public contract.

---

# 11. Draft-Only Rule for Future Advance Creation

A future MCP advance creation capability should follow the existing project pattern unless native evidence proves otherwise:

```text
prepare
    -> no persistent accounting write
    -> bounded native Draft preview
    -> approval token

confirm
    -> atomic approval claim
    -> fresh source reload
    -> fresh native rebuild
    -> fingerprint comparison
    -> Draft Payment Entry insert only
```

Submission must remain the existing generic Accounts lifecycle action:

```text
prepare_submit_document
confirm_submit_document
```

Task 52 must verify that this boundary is correct for Sales Order advances.

Do not merge create + submit into one MCP tool.

---

# 12. Flow B - Existing Advance / Unallocated Receipt to Sales Invoice

Audit how ERPNext natively applies an existing Customer advance/payment to a later Sales Invoice.

There are at least two conceptual sources to inspect:

```text
A. Payment Entry already linked to Sales Order
B. standalone/unallocated Customer Payment Entry, such as Task 50 output after submit
```

Determine how each becomes associated with a Sales Invoice in the installed ERPNext version.

Do not assume both use the same path.

---

# 13. Sales Invoice Advance Discovery and Allocation

Inspect the native Sales Invoice / Accounts Controller / advance service flow.

Search for installed implementations equivalent to:

```text
get_advance_entries
get_advance_payment_entries
get_advance_payment_entries_for_regional
validate_advance_entries
allocate_advances_automatically
advances child rows
set_advances
advance allocation validation
```

Names may differ in the installed version.

Answer:

1. How does ERPNext discover submitted advance Payment Entries for a Customer?
2. How does it discover advances linked to Sales Orders referenced by Sales Invoice items?
3. How does it discover unallocated Customer receipts?
4. Does discovery depend on the receivable account?
5. Does it depend on a default advance liability account?
6. Does it depend on Company?
7. Does it depend on currency?
8. Does it depend on `book_advance_payments_in_separate_party_account`?
9. What fields are placed in the Sales Invoice `advances` child table?
10. When are Payment Entry references rewritten from Sales Order to Sales Invoice, if at all?
11. At what lifecycle stage does that happen?
12. Can a Draft Sales Invoice allocate advances safely before submit?
13. What changes on Sales Invoice submit?
14. What happens on Sales Invoice cancel?
15. How are partial allocations handled?
16. How are excess/unallocated advances retained?
17. How are exchange gains/losses handled?

The report must separate observed native behavior from future MCP design.

---

# 14. Payment Reconciliation Native Flow

Inspect the installed `Payment Reconciliation` implementation as a native accounting service/process.

At minimum trace:

```text
get_unreconciled_entries
payment retrieval
invoice retrieval
allocation rows
validate_allocation
reconcile
reconcile_allocations
reconcile_against_document
Payment Entry reference update path
Payment Ledger update/repost path
exchange gain/loss handling
```

Names can vary by installed version.

Determine whether the safest future MCP reconciliation capability should call:

```text
PaymentReconciliation.reconcile()
```

or a different official/native entry point.

Do not call a lower-level helper directly merely because it is easier.

Prefer the highest-level native path that preserves:

```text
validation
permissions
accounting dimensions
concurrency checks
exchange handling
hooks
native reference maintenance
```

If the high-level Document is virtual/non-persistent, document that explicitly.

---

# 15. Reconciliation is Not Custom MCP Logic

This audit must state clearly:

```text
MCP must NOT implement reconciliation math.
```

A future public capability may express only intent, for example:

```text
Customer = Arkee Foods
Payment Entry = ACC-PAY-2026-0001
Sales Invoice = ACC-SINV-2026-0005
Allocate = INR 50,000
```

Then the future service must invoke native ERPNext reconciliation/allocation behavior.

MCP must never directly:

```text
edit Payment Ledger Entry
edit GL Entry
edit Sales Invoice outstanding_amount
edit Payment Entry unallocated_amount
rewrite Payment Entry references with frappe.db.set_value
create its own reconciliation SQL
calculate exchange gain/loss formulas
bypass Payment Reconciliation validation
```

---

# 16. Compare Two Future Reconciliation Designs

The audit must compare at least these candidates.

## Candidate A - Invoice-native advance allocation

Use Sales Invoice's native advance discovery/allocation flow when the advance is naturally associated with the invoice/order.

Questions:

- Is this primarily an invoice creation/update concern rather than a separate reconciliation capability?
- Can existing Sales Invoice creation/conversion safely expose a bounded `apply_advances` behavior later?
- Does this require modifying an already-created Draft Sales Invoice?
- Would that conflict with the project's explicit mutation-tool policy?

## Candidate B - Explicit Payment Reconciliation capability

Use native Payment Reconciliation for an existing submitted payment and an existing invoice.

Possible future public intent:

```text
prepare_customer_payment_reconciliation
confirm_customer_payment_reconciliation
```

or another explicit name justified by the audit.

Questions:

- Can it safely be scoped to exactly one Customer, one Payment Entry, one Sales Invoice, and one amount in V1?
- Can permissions be checked independently before native reconcile?
- Can a meaningful preview be produced without mutating accounting state?
- How should stale outstanding/unallocated state be fingerprinted?
- Does native reconciliation itself provide all necessary current-state validation?

## Candidate C - Generic reconciliation builder

Example:

```text
reconcile_documents(party_type, payments=[], invoices=[], allocations=[])
```

This should be rejected for V1 unless extraordinary native evidence proves it is necessary.

The project preference is explicit business capability over generic accounting mutation.

---

# 17. Existing Task 50 Interaction

Inspect exactly how Task 50 constructs standalone Customer Payment Entry.

Confirm:

```text
references = []
total_allocated_amount = 0
unallocated_amount remains available according to native calculation
```

or document the actual current behavior if different.

Determine:

1. After Task 50 Payment Entry is submitted, can native Payment Reconciliation discover it?
2. Under what account/currency/party conditions?
3. Does separate-party-advance-account configuration change discoverability?
4. Can it be allocated to a Sales Invoice without rewriting MCP-owned fields?
5. What native mechanism performs the update?

This is a key acceptance criterion.

---

# 18. Separate Advance Account Behavior

ERPNext v16 may support booking advance payments in a separate party liability/asset account.

Audit the exact installed behavior around fields/settings equivalent to:

```text
book_advance_payments_in_separate_party_account
reconcile_on_advance_payment_date
default_advance_account
```

Determine:

1. Which setting/field controls this behavior?
2. Whether it is Company, party, Payment Entry, or Accounts Settings driven.
3. Which account is used for a Customer advance.
4. How later allocation clears/reclassifies it.
5. Whether Task 50 already naturally respects it.
6. Whether Sales Order advance factory naturally respects it.
7. Whether Payment Reconciliation handles it natively.
8. Whether a future MCP contract needs to expose any of these raw accounting choices.

Default expectation:

```text
MCP should NOT expose the raw advance account.
```

ERPNext should derive it from configured accounting policy.

---

# 19. Currency and Exchange-Rate Audit

Audit at least these scenarios conceptually from installed source/tests:

```text
Company INR / Sales Order INR / bank INR
Company INR / Sales Order USD / receivable USD / bank USD
Company INR / Sales Order USD / bank INR
Customer advance account differs from receivable account
reconciliation across compatible account currencies
exchange-rate change between advance and invoice
```

Determine:

- which amounts the user can safely specify;
- when `bank_amount` is required;
- which exchange rates ERPNext derives;
- when exchange gain/loss can be created;
- whether a future V1 must reject some multi-currency cases rather than expose raw rates.

Never recommend caller-supplied arbitrary source/target exchange-rate formulas unless native ERPNext specifically requires and safely supports that public input.

---

# 20. Payment Terms and Partial Billing

Audit interaction with:

```text
Sales Order payment terms
partial advance
full advance
partially billed Sales Order
multiple Sales Invoices from one Sales Order
one advance spread across multiple Sales Invoices
invoice payment terms
```

Determine whether a simple V1 Sales Order advance tool can remain independent of Payment Terms or whether native rules require term-aware preview.

Do not add custom term-allocation logic.

---

# 21. Permissions and Identity

The audit must identify native permission boundaries for future tools.

At minimum consider:

```text
Sales Order read permission
Payment Entry create permission
Payment Entry read permission
Payment Entry submit permission
Sales Invoice read permission
Payment Reconciliation access/permission behavior
Account/Bank Account/Mode of Payment access where relevant
```

Use the current request-scoped Frappe user.

Do NOT introduce:

```text
Administrator fallback
ignore_permissions=True
client-supplied user identity
client-supplied site identity
```

HTTP identity and site selection remain controlled by the existing MCP runtime/REST architecture.

---

# 22. Approval and Stale-State Requirements

Future financial writes must preserve the existing shared ApprovalStore architecture.

For Sales Order advance prepare/confirm, determine the minimum material fingerprint state, likely including:

```text
Sales Order identity
Sales Order docstatus/status
Customer
Company
currency
party account / native advance policy signal
order amount / relevant remaining amount
current advance_paid or equivalent
payment amount
destination identity
posting/reference fields
native preview amounts
```

For reconciliation prepare/confirm, determine the minimum material fingerprint state, likely including:

```text
Customer
Company
receivable/advance account
Payment Entry identity/docstatus
Payment Entry current unallocated/unreconciled amount
Sales Invoice identity/docstatus
Sales Invoice fresh outstanding
currency/exchange-rate material state
requested allocation amount
native preview/allocation projection
```

Confirm must:

```text
claim approval atomically
re-read current documents
recompute native state
reject material drift
perform native write only after successful comparison
```

Do not invent a second approval store.

---

# 23. Concurrency and Auto-Reconciliation

Inspect installed behavior for concurrent reconciliation.

Specifically check Accounts Settings / process behavior equivalent to:

```text
auto_reconcile_payments
Auto Reconcile
Process Payment Reconciliation
is_any_doc_running(...)
```

Determine:

1. Does native reconciliation reject when an auto-reconcile job is already running for the same party/account?
2. What state can change between prepare and confirm?
3. Can another payment be reconciled first?
4. Can invoice outstanding change before confirm?
5. Can unallocated Payment Entry amount change before confirm?
6. What native error should be mapped to a safe public result?

The future MCP must fail closed on stale/concurrent accounting state.

---

# 24. Optional-App / India Compliance Boundary

Inspect installed hooks affecting:

```text
Payment Entry
Sales Invoice
advance allocation
reconciliation
```

if India Compliance or another official Frappe app is installed.

Do not assume every deployment has India Compliance.

The future capability must remain optional-app neutral:

```text
ERPNext/Frappe hooks remain active
MCP does not duplicate GST/TDS/advance-tax logic
```

Document only material hooks relevant to the two audited flows.

---

# 25. Data Minimization

Future LLM-visible previews must contain only business-review information.

For Sales Order advance, candidate safe preview fields include:

```text
sales_order
customer
company
currency
order total / relevant amount
existing advance paid
new advance amount
mode of payment or safe bank destination label
posting date
reference no/date
resulting Draft Payment Entry amounts
warning that Draft has no ledger effect until submit
```

For reconciliation, candidate safe preview fields include:

```text
customer
company
payment_entry
payment date
payment available/unreconciled amount
sales_invoice
invoice outstanding
requested allocation
remaining payment amount after allocation
remaining invoice outstanding after allocation
currency
native warnings
```

Do NOT expose:

```text
full Chart of Accounts
full bank account numbers
IBAN/SWIFT unless explicitly required and safely masked
raw GL rows
raw Payment Ledger rows
internal SQL
secrets
site credentials
API keys
stack traces
unrelated Customer data
unrelated invoices/payments
```

---

# 26. Error Semantics

The report must recommend safe future error categories for cases such as:

```text
source not found
permission denied
wrong docstatus
wrong Customer
wrong Company
payment already fully allocated
invoice already fully paid
allocation exceeds available payment
allocation exceeds invoice outstanding
currency/account incompatibility
unsupported separate-advance configuration
stale confirmation
concurrent reconciliation process
native validation failure
optional-app validation failure
```

Do not expose internal traceback details to the LLM/client.

Reuse existing MCP error/result conventions wherever possible.

---

# 27. Direct and REST Parity

For every future Accounts capability recommended by the audit, require:

```text
typed direct MCP tool
fixed typed remote operation
same service authority
same input model
same output model
same approval semantics
same profile restriction
```

No arbitrary remote Python method execution.

No arbitrary DocType dispatch.

No caller-supplied site or user override.

---

# 28. Profile Boundary

The audit must preserve:

```text
Sales profile    - unchanged by Accounts implementation unless a later task explicitly needs a source read helper
Purchase profile - completely unchanged
Accounts profile - owns Customer payment/advance/reconciliation capabilities
```

Do not move Payment Entry into Sales profile merely because the source is a Sales Order.

The Sales Order is the business reference; the money movement remains an Accounts capability.

---

# 29. Audit Questions That Must Be Answered

The final report must explicitly answer all of these.

## Sales Order advance

1. What is the exact installed native API/factory?
2. Does it create or only return an unsaved Payment Entry?
3. What exact source states are supported?
4. What exact permissions are checked?
5. How is Customer/Company/account derived?
6. How is amount bounded?
7. How is cross-currency handled?
8. How is Sales Order advance state updated on submit/cancel?
9. What happens after the Sales Order is partially/fully invoiced?
10. What is the smallest safe MCP input?

## Invoice advance allocation

11. How does Sales Invoice discover Sales Order-linked advances?
12. How does it discover unallocated standalone payments?
13. What is the native `advances` child-table lifecycle?
14. When are references rewritten/updated?
15. Is a separate public capability required for order-linked advance allocation?

## Payment Reconciliation

16. What is the highest-level native reconciliation API?
17. Is Payment Reconciliation a persistent or virtual/non-persistent Document in this version?
18. What permissions apply?
19. How are unreconciled payments/invoices fetched?
20. How are allocation amounts validated?
21. How does native code update Payment Entry references/Payment Ledger?
22. How are exchange differences handled?
23. How does native concurrency protection work?
24. Can Task 50 submitted standalone receipts be reconciled through this path?
25. What is the smallest safe V1 public reconciliation scope?

## Architecture

26. Which exact future capabilities belong in Accounts?
27. Which logic must remain entirely inside ERPNext?
28. Which existing services/helpers can be reused without coupling public tools?
29. Which current profile/tool contracts remain unchanged?
30. What is the exact next implementation task?

---

# 30. Required Audit Procedure

Perform the audit in this order.

## Step 1 - Baseline repository

- inspect current Git/worktree state;
- record branch/commit if available;
- do not clean or reset existing changes;
- inspect Accounts registration and catalog;
- verify Tasks 45/47/49/50 implementation state.

## Step 2 - Trace Sales Order advance factory

- inspect native `get_payment_entry` or installed equivalent;
- trace Sales Order-specific branch;
- trace source permission checks;
- trace amount/account/currency defaulting;
- trace reference row construction;
- trace submit/cancel side effects from official native code/tests.

## Step 3 - Trace Sales Invoice advance logic

- inspect advance discovery service/functions;
- inspect Sales Invoice `advances` behavior;
- inspect Sales Order-linked advance discovery;
- inspect unallocated receipt discovery;
- inspect separate advance account logic;
- inspect invoice submit/cancel behavior.

## Step 4 - Trace Payment Reconciliation

- inspect unreconciled payment retrieval;
- inspect outstanding invoice retrieval;
- inspect allocation construction;
- inspect validation;
- inspect top-level reconcile call;
- trace low-level call only to understand native behavior, not to recommend bypassing the top-level API;
- inspect concurrency protection.

## Step 5 - Compare future public boundaries

Evaluate:

```text
A. Sales Order advance create capability
B. invoice-native advance application extension
C. explicit existing-payment-to-invoice reconciliation capability
D. generic reconciliation builder
```

Reject unnecessary genericity.

## Step 6 - Define approval/fingerprint state

Separate prepare-time read/preview state from confirm-time write state.

## Step 7 - Define data minimization

List exact candidate public input/output fields and explicitly forbidden accounting internals.

## Step 8 - Define future tests

Produce a detailed test matrix for the next implementation task(s).

## Step 9 - Write report only

Create/update only:

```text
docs/inspect/CUSTOMER_ADVANCE_AND_PAYMENT_RECONCILIATION_NATIVE_FLOW_AUDIT.md
```

---

# 31. Tests / Verification Allowed in Task 52

Because this is an audit, verification is primarily source/static/read-only.

Allowed examples:

```text
git status --short
git log -1 --oneline
grep / rg / sed / cat
Python import/static parsing that does not initialize a mutating site transaction
generated catalog inspection
read-only metadata inspection
read-only settings inspection if a configured test site is available
```

A read-only site command may be used only if it is clearly non-mutating and does not expose secrets.

Do not hardcode a historical site such as `yob.localhost`.

Use only the currently configured/authorized test site if runtime inspection is necessary.

Do NOT run live accounting tests that create/submit/cancel/reconcile records.

Do NOT claim live behavior was verified if only source/unit evidence was inspected.

---

# 32. Future Implementation Test Matrix Required in the Report

The Task 52 report must define tests for future tasks.

At minimum include the following categories.

## 32.1 Sales Order advance

```text
submitted Sales Order -> prepare succeeds
Draft Sales Order rejected
cancelled Sales Order rejected
wrong/missing Sales Order rejected
permission denied
partial advance
full advance
attempted over-advance/native bound behavior
same-currency bank/cash
cross-currency supported case
missing Mode of Payment/bank destination
stale Sales Order state
stale existing advance amount
approval replay
approval user/site/action mismatch
confirm creates Draft only
submit uses existing lifecycle
cancel restores native Sales Order advance state
```

## 32.2 Task 50 interoperability

```text
standalone Draft Payment Entry has no ledger effect
submitted standalone Customer receipt becomes natively discoverable if eligible
wrong Customer cannot be reconciled
wrong Company cannot be reconciled
wrong account/currency cannot be reconciled
fully allocated payment not offered again
```

## 32.3 Reconciliation

```text
one submitted Payment Entry + one submitted Sales Invoice + partial allocation
full allocation
allocation below both available/outstanding
allocation above payment available rejected
allocation above invoice outstanding rejected
already paid invoice rejected
cancelled invoice rejected
Draft payment rejected
wrong Customer rejected
wrong Company rejected
currency incompatibility rejected
stale invoice outstanding rejected
stale payment available amount rejected
concurrent auto-reconcile conflict handled safely
native exchange difference behavior preserved
approval replay rejected
approval binding preserved
no raw ledger/account input exposed
```

## 32.4 Regression

```text
Task 45 single-invoice payment unchanged
Task 49 multi-invoice receipt unchanged
Task 50 standalone receipt unchanged
Payment Entry reads unchanged
Accounts lifecycle unchanged
Sales profile unchanged
Purchase profile unchanged
REST registry remains fixed/typed
shared approval behavior unchanged
```

---

# 33. Acceptance Criteria

Task 52 is complete only when all of the following are true.

## AC-01 - Inspection only

Only the audit report changed.

## AC-02 - Current code verified

The report describes the actual latest Accounts implementation, not memory or an older task file.

## AC-03 - Native Sales Order advance path proven

The report identifies the exact installed ERPNext factory/call chain and proves how order-linked Customer advance works.

## AC-04 - Native submit/cancel effects proven

The report identifies native code/tests responsible for Sales Order advance state changes.

## AC-05 - Sales Invoice advance path proven

The report explains how ERPNext discovers and applies eligible advances, including order-linked and unallocated cases where supported.

## AC-06 - Native reconciliation path proven

The report identifies the highest-level supported Payment Reconciliation entry point and its validation/mutation chain.

## AC-07 - No custom accounting logic recommended

No recommendation requires MCP to implement outstanding, allocation, GL, Payment Ledger, or exchange formulas.

## AC-08 - Separate advance account behavior addressed

The report explains installed behavior and whether it changes future MCP public input.

## AC-09 - Currency boundary addressed

The report identifies what V1 can safely support and what should fail/defer.

## AC-10 - Permission model addressed

All future writes remain under the authenticated Frappe user with normal permissions.

## AC-11 - Approval/stale design addressed

The report defines material prepare/confirm fingerprint state and concurrency failure behavior.

## AC-12 - Task 50 interoperability answered

The report explicitly states whether and how a submitted Task 50 standalone Customer receipt can be allocated later through native ERPNext behavior.

## AC-13 - Public contract remains bounded

No generic arbitrary Payment Entry or reconciliation builder is recommended for V1.

## AC-14 - Profiles remain separated

Purchase is unchanged; Accounts owns the financial capability.

## AC-15 - Exact next task named

The report ends with one exact next implementation task and its boundaries.

---

# 34. Expected Result

The expected result is an evidence-backed architecture decision, not production code.

The report should make the future lifecycle visually clear, for example:

```text
Submitted Sales Order
    -> explicit Accounts advance capability
    -> ERPNext native Payment Entry factory
    -> Draft Payment Entry
    -> existing generic submit lifecycle
    -> native Sales Order advance state

Later:

Sales Invoice
    -> ERPNext native advance discovery/allocation

OR, for an existing standalone/unallocated payment:

Submitted Payment Entry + Sales Invoice
    -> explicit bounded reconciliation intent
    -> ERPNext native Payment Reconciliation
    -> native reference / Payment Ledger updates
```

The report must state which path applies to which business case.

---

# 35. Limitations

Task 52 must not claim to solve:

```text
Supplier advances
purchase-side accounting
refunds
credit notes
write-offs
bank reconciliation
payment gateway settlement
Payment Request
Internal Transfer
multi-party reconciliation
Journal Entry reconciliation
arbitrary accounting dimensions exposed to the LLM
all multi-currency combinations
all regional tax/withholding combinations
```

If installed ERPNext source reveals that one of these is inseparable from the target native flow, document the dependency and keep implementation deferred until separately approved.

---

# 36. Required Report Structure

Create:

```text
docs/inspect/CUSTOMER_ADVANCE_AND_PAYMENT_RECONCILIATION_NATIVE_FLOW_AUDIT.md
```

Use at least these sections:

```text
1. Executive conclusion
2. Current MCP Accounts baseline
3. Installed Frappe/ERPNext versions and evidence boundary
4. Native Sales Order advance factory
5. Native Payment Entry reference behavior
6. Sales Order advance submit/cancel effects
7. Sales Invoice advance discovery/allocation
8. Task 50 standalone receipt interoperability
9. Separate advance account behavior
10. Native Payment Reconciliation architecture
11. Reconciliation validation and mutation chain
12. Currency/exchange behavior
13. Payment Terms / partial billing behavior
14. Permissions and identity
15. Approval / stale / concurrency design
16. Optional-app behavior
17. Public capability options compared
18. Data minimization
19. Error model
20. Direct/REST/profile boundary
21. Future test matrix
22. Risks and deferred cases
23. Exact Task 53 recommendation
```

Every important technical conclusion should include installed source file/function evidence.

Clearly label:

```text
CONFIRMED FROM INSTALLED SOURCE
CONFIRMED FROM OFFICIAL UPSTREAM
CONFIRMED FROM CURRENT MCP CODE
INFERENCE / RECOMMENDATION
NOT LIVE-VERIFIED
```

where useful.

---

# 37. Exact Next Task After Task 52

Unless the installed audit uncovers a blocker that makes the boundary unsafe, the next implementation task should be:

```text
Task 53 - Sales Order Customer Advance Payment V1 Implementation
```

Expected Task 53 scope:

```text
Submitted Sales Order
    -> prepare_sales_order_advance_payment
    -> native ERPNext Draft Payment Entry preview
    -> approval
    -> confirm_sales_order_advance_payment
    -> Draft Payment Entry only
    -> existing Accounts lifecycle submit separately
```

Task 53 must use the installed ERPNext native Sales Order -> Payment Entry path.

Task 53 must NOT implement payment reconciliation yet.

The later reconciliation capability must remain a separate task after Task 53, using the exact native boundary proven by Task 52.

If Task 52 proves that a different native boundary is required, the report must explain the blocker and name the replacement next task explicitly instead of silently inventing custom logic.

---

# 38. Final Instruction to the Coding Agent

Do not optimize, refactor, or implement while performing this task.

Do not create a custom accounting abstraction because future capabilities may need it.

Do not broaden Accounts merely for completeness.

Follow the evidence:

```text
current mcp_erpnext code
    + installed ERPNext/Frappe source
    + official Frappe/ERPNext evidence
    -> smallest safe native capability
```

The purpose of Task 52 is to decide the exact native seam before any new financial write tool is added.
