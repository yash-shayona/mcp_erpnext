# Task 44 — Accounts Profile + Payment Entry Native Flow Audit

## Status

**Inspection-only / architecture audit**

This task follows:

- Task 41 — Delivery Note Native Flow Audit
- Task 42 — Delivery Note V1 Implementation Foundation
- Task 43 — Delivery Note → Sales Invoice Native Conversion

The current Sales flow now reaches a normal Draft/Submitted Sales Invoice through either:

```text
Quotation
    ↓
Sales Order
    ↓
Sales Invoice
```

or:

```text
Quotation
    ↓
Sales Order
    ↓
Delivery Note
    ↓
Sales Invoice
```

The next business stage is settlement/accounting through ERPNext Accounts.

This task must determine the correct native ERPNext architecture **before any Accounts-profile production implementation is written**.

---

# 1. Objective

Inspect the current `mcp_erpnext` repository and the exact installed Frappe/ERPNext source to determine how the MCP server should safely continue from a submitted Sales Invoice into the Accounts domain.

The main business question is:

```text
Submitted Sales Invoice
        ↓
Outstanding receivable
        ↓
Customer payment
        ↓
Payment Entry
        ↓
Reference allocation
        ↓
Payment Entry submit
        ↓
General Ledger + Payment Ledger
        ↓
Sales Invoice outstanding reduced
```

The audit must determine:

1. the correct Accounts-profile boundary;
2. the exact native ERPNext APIs/helpers that should be reused;
3. what the LLM/client must provide versus what ERPNext should derive;
4. what should be one public MCP capability versus separate explicit business-intent tools;
5. how full, partial, advance, unallocated, multi-invoice, multi-currency, and reconciliation flows work;
6. what submit/cancel/delete effects occur;
7. what read/query/aggregate capabilities are useful and safe;
8. what should be implemented first in Task 45;
9. what must be deferred.

No production behavior may change in Task 44.

---

# 2. Critical Architecture Principle

The MCP server is a bridge to ERPNext, not a second accounting engine.

The target architecture is:

```text
User / Agent business intent
        ↓
typed MCP capability
        ↓
ERPNext native business document/helper
        ↓
ERPNext validation/defaults/permissions
        ↓
ERPNext General Ledger / Payment Ledger
```

The architecture must NOT become:

```text
LLM chooses debit account
LLM chooses credit account
LLM constructs GL lines
MCP manually updates outstanding
MCP manually reconciles ledgers
```

ERPNext must remain authoritative for:

- Chart of Accounts
- party accounts
- bank/cash accounts
- account currencies
- payment type rules
- invoice outstanding amounts
- allocations
- exchange rates
- deductions
- exchange gain/loss
- payment terms
- payment schedules
- General Ledger
- Payment Ledger
- reconciliation
- cancellation effects
- permissions
- runtime metadata
- installed-app hooks

---

# 3. Inputs / Evidence to Inspect

## 3.1 Current MCP repository

Inspect the **current worktree after Task 43**, not an older ZIP/task specification.

At minimum inspect:

- profile architecture
- `sales` profile
- `purchase` profile
- profile selection/runtime
- tool registration/catalog
- typed contracts
- generic lifecycle
- generic read/query/aggregate foundations
- PDF/email foundations
- `ApprovalStore`
- `claim_for_confirm_write()`
- direct backend
- REST backend from Task 40
- fixed remote-operation registry
- current conversion service patterns
- current Sales Invoice read/query/aggregate/lifecycle support
- current error/observability conventions
- existing tests
- docs/inspect reports from Tasks 41–43

Confirm whether `accounts` exists anywhere already, even partially.

Do not assume it is absent without inspecting the current repository.

## 3.2 Exact installed ERPNext source

Use the **installed ERPNext checkout on this Bench/site**, not only online docs.

At minimum inspect the installed equivalents of:

```text
erpnext/accounts/doctype/payment_entry/payment_entry.py
erpnext/accounts/doctype/payment_entry/payment_entry.json
erpnext/accounts/doctype/payment_entry/payment_entry.js
erpnext/accounts/doctype/payment_entry/test_payment_entry.py

erpnext/accounts/doctype/payment_reconciliation/payment_reconciliation.py
erpnext/accounts/doctype/payment_reconciliation/payment_reconciliation.json

erpnext/accounts/utils.py

erpnext/accounts/doctype/sales_invoice/sales_invoice.py
erpnext/accounts/doctype/sales_invoice/sales_invoice.js

erpnext/accounts/general_ledger.py
```

Also trace any installed source actually called by Payment Entry for:

- Payment Ledger
- outstanding recalculation
- payment reference allocation
- exchange gain/loss
- payment schedule updates
- advance payment ledger
- Mode of Payment account resolution
- Bank Account resolution
- party account resolution
- write-off/deductions
- reconciliation/unreconciliation
- Accounting Dimensions
- tax withholding if relevant
- optional app hooks

Do not rely on filenames alone. Follow actual call sites.

## 3.3 Official Frappe/ERPNext behavior

Use official Frappe documentation/repository only as supporting evidence.

Installed source is the runtime authority for exact behavior.

---

# 4. No Production Changes

Task 44 is inspection-only.

Allowed repository change:

```text
docs/inspect/ACCOUNTS_PAYMENT_ENTRY_NATIVE_FLOW_AUDIT.md
```

Only this audit report should be created/updated unless an existing documentation convention requires an audit index update.

Do NOT change:

- Python production code
- contracts
- tools
- services
- profiles
- lifecycle allowlists
- REST handlers
- settings
- DocTypes
- site data
- Accounts Settings
- Selling Settings
- Company
- Customer
- Supplier
- Bank Account
- Mode of Payment
- Chart of Accounts
- Payment Entry
- Sales Invoice
- Purchase Invoice
- tests
- fixtures
- migrations

Do not install dependencies.

Do not create live accounting entries.

---

# 5. Confirm Current Domain Boundary

Document the current profile state after Task 43.

Expected conceptually:

```text
mcp_erpnext

Sales profile
    Customer
    Item
    Quotation
    Sales Order
    Delivery Note
    Sales Invoice
    ...

Purchase profile
    Supplier
    Item
    Purchase Order
    ...
    intentionally not being expanded now

Accounts profile
    not yet implemented
```

Verify rather than assume.

The audit must answer whether the clean boundary should be:

```text
Sales Invoice stays in Sales
Payment Entry starts in Accounts
```

or whether any part of payment initiation should remain under Sales.

Default architectural preference is:

- Sales Invoice remains Sales-domain.
- Payment Entry is Accounts-domain.
- Cross-domain source references are allowed.
- Profiles should not duplicate the same public business tool without a concrete reason.

Explain the final recommendation.

---

# 6. Primary Flow to Audit: Customer Payment Against Sales Invoice

The first implementation candidate is the most common continuation from the current Sales profile:

```text
Submitted Sales Invoice
        ↓
customer owes money
        ↓
customer pays
        ↓
ERPNext Payment Entry
        ↓
Payment Type = Receive
        ↓
Customer reference
        ↓
Sales Invoice allocation
        ↓
Draft Payment Entry
        ↓
separate submit
```

Identify the exact installed native helper used by ERPNext's own UI for creating a Payment Entry from a Sales Invoice.

The audit must locate and document its exact installed signature.

Likely source to verify:

```python
erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry(...)
```

Do not copy this signature from generic knowledge.

Read the installed function and report:

- callable/import path
- parameters
- required parameters
- optional parameters
- defaults
- internal permission behavior
- source document loading behavior
- source docstatus/outstanding validation
- party/account defaulting
- bank account handling
- party amount handling
- bank amount handling
- reference date handling
- payment-term handling
- exchange-rate behavior
- return value type
- whether it saves/inserts
- whether it remains unsaved Draft
- whether it submits
- hooks it triggers

---

# 7. Determine Minimum MCP Input for Invoice Payment

The audit must determine the **minimum safe user/LLM inputs** for:

```text
"Receive payment against Sales Invoice X"
```

Do not assume the answer.

Specifically determine whether a safe first capability can accept something like:

```text
sales_invoice
amount (optional?)
bank_account or mode_of_payment (when needed?)
reference_no
reference_date
posting_date (optional?)
```

or whether native defaults make some of these unnecessary.

For every candidate input classify it as one of:

```text
A. Must be provided by caller
B. May be provided by caller
C. Must be derived by ERPNext
D. Must remain server/config derived
E. Must not be exposed to LLM
```

Audit at least:

- Company
- Customer
- party type
- payment type
- party account
- paid_from
- paid_to
- bank/cash account
- Bank Account
- Mode of Payment
- posting date
- reference number
- reference date
- paid amount
- received amount
- allocated amount
- unallocated amount
- source exchange rate
- target exchange rate
- currency
- cost center
- project
- accounting dimensions
- deductions
- taxes on Payment Entry
- remarks
- Sales Invoice reference
- Payment Term
- payment request
- advance flags
- internal transfer fields

The MCP must avoid asking the LLM for fields ERPNext can correctly derive.

---

# 8. Full Payment

Trace exact native behavior for:

```text
Sales Invoice outstanding = 11,800
customer pays = 11,800
```

Document:

- Draft Payment Entry values
- reference row values
- allocated amount
- paid/received amounts
- account defaults
- submit behavior
- Sales Invoice outstanding result
- Sales Invoice status result
- GL behavior
- Payment Ledger behavior
- cancellation behavior

Do not manually infer ledger rows when installed source can be traced.

---

# 9. Partial Payment

Trace:

```text
Sales Invoice outstanding = 11,800
customer pays = 5,000
```

Determine:

- how native helper accepts partial amount;
- which public input controls it;
- whether `party_amount` is appropriate;
- how allocated amount is set;
- resulting unallocated amount;
- remaining SI outstanding;
- Payment Schedule interaction;
- validation against latest outstanding;
- stale/concurrent payment protection.

Identify whether Task 45 should support partial payment immediately or defer it.

Recommendation must be evidence-based.

---

# 10. Overpayment

Audit what happens when:

```text
invoice outstanding = 11,800
customer sends = 15,000
```

Determine native supported alternatives:

- allocate 11,800 to invoice and leave remainder unallocated;
- customer advance;
- reject;
- separate allocation mechanism;
- reconciliation later.

Do not invent MCP behavior.

Document how ERPNext represents the excess amount and how the Payment Ledger sees it.

---

# 11. Advance Customer Payment

Audit money received **before Sales Invoice exists**.

Examples:

```text
Customer pays advance with no document
```

and:

```text
Customer pays advance against Sales Order
```

Trace:

- native Payment Entry creation;
- valid reference types;
- Sales Order reference behavior;
- unallocated advance behavior;
- Company's "book advance payments in separate party account" setting if present;
- default advance received account;
- advance ledger behavior;
- later Sales Invoice allocation/reconciliation.

Decide whether advance receipt belongs in Accounts Profile V1 or a later task.

Do not implement it.

---

# 12. Multiple Sales Invoices in One Payment

Audit:

```text
Customer payment = 30,000

allocate:
SINV-001 = 10,000
SINV-002 = 8,000
SINV-003 = 12,000
```

Determine:

- native method to retrieve outstanding invoices;
- reference row structure;
- allocation validation;
- whether all invoices must have same Customer;
- Company/account constraints;
- currency constraints;
- payment-term interactions;
- stale outstanding validation;
- partial allocations across several references.

Compare two possible public MCP designs:

### Option A — single-invoice first

```text
prepare_sales_invoice_payment
```

Very narrow and safe.

### Option B — generic customer receipt with references

```text
prepare_customer_payment
references=[...]
```

More powerful but larger contract.

Do not preselect one automatically.

Recommend which belongs in the **first Accounts implementation** and why.

---

# 13. Payment Terms / Payment Schedule

Inspect invoices using payment terms.

Trace native behavior for:

- one Payment Term
- multiple Payment Terms
- allocate-payment-based-on-payment-terms enabled
- early payment discount
- term-specific outstanding
- payment schedule paid amount
- payment schedule outstanding
- discount posting

Determine whether a simple SI → Payment Entry tool works safely when term-based allocation is enabled.

If special user input is required, document it.

Do not hide this edge case.

---

# 14. Mode of Payment

Audit native `Mode of Payment` behavior.

Determine:

- whether it is required;
- whether it is optional;
- how its default accounts are resolved by Company;
- whether selecting Mode of Payment can safely derive `paid_to` for Receive;
- behavior when no default account exists;
- Cash versus Bank behavior;
- account currency implications.

Determine whether the MCP should preferably ask for:

```text
mode_of_payment
```

instead of raw account names where possible.

Do not decide without installed-source evidence.

---

# 15. Bank Account vs Ledger Account

ERPNext can distinguish a `Bank Account` master from an accounting `Account`.

Audit:

- `bank_account` helper argument;
- how Bank Account maps to ledger Account;
- party bank account behavior;
- company bank account behavior;
- bank account currency;
- default bank/cash account logic;
- Mode of Payment account defaults.

Recommend the safest LLM-facing abstraction.

Do not expose raw ledger-account selection if a safer native business-level choice exists.

---

# 16. Bank Reference / Transaction Reference

Trace native validation for:

- `reference_no`
- `reference_date`

Determine:

- when mandatory;
- whether requirement changes by bank/cash/Mode of Payment;
- duplicate reference validation;
- transaction reference rules;
- whether cash receipts can omit them;
- whether a draft can exist without them;
- what is required before submit.

Use this to define prepare versus submit expectations.

---

# 17. Payment Types

Audit all installed Payment Entry types:

```text
Receive
Pay
Internal Transfer
```

## Receive

Primary current use case:

```text
Customer → Company
```

## Pay

Future use case:

```text
Company → Supplier
```

Purchase profile is intentionally not being expanded now, but Accounts architecture must not make supplier payment impossible later.

Inspect Purchase Invoice → Payment Entry native flow sufficiently to prove whether the same internal engine can support it.

Do NOT implement Purchase Invoice or Purchase Payment tools.

## Internal Transfer

Inspect:

```text
Bank/Cash Account A → Bank/Cash Account B
```

Determine whether this should be:

- part of Accounts V1;
- later separate capability;
- excluded from LLM operation initially.

Provide recommendation.

---

# 18. Standalone Customer Receipt

Audit receiving customer money without referencing a Sales Invoice or Sales Order.

Determine:

- required fields;
- party account defaults;
- bank/cash account defaults;
- unallocated amount behavior;
- Payment Ledger representation;
- later reconciliation.

Decide whether standalone receipt should be:

- in first Payment Entry implementation;
- separate later tool;
- handled only after Payment Reconciliation is implemented.

---

# 19. Supplier Payment Future Compatibility

Although Purchase development is frozen for now, inspect enough native behavior to answer:

- Can Accounts profile later support supplier Payment Entry independently of Purchase profile growth?
- Does Payment Entry `Pay` use the same controller/helper?
- What source references are valid for Supplier?
- Purchase Order advance?
- Purchase Invoice payment?
- on-hold supplier/invoice validations?
- tax withholding interactions?

The audit must not create Purchase tools.

This section exists only to prevent designing Accounts around Customer-only assumptions.

---

# 20. Multi-Currency

This is a high-risk area.

Trace exact installed source for:

- company currency
- invoice currency
- party account currency
- bank account currency
- paid-from account currency
- paid-to account currency
- source exchange rate
- target exchange rate
- transaction exchange rate
- paid amount
- received amount
- base paid/received amounts
- exchange gain/loss
- deductions caused by exchange differences

Include at least these conceptual cases:

```text
A. INR invoice / INR bank
B. USD invoice / USD receivable / USD bank
C. USD invoice / INR bank
D. invoice currency != party account currency
E. bank currency != invoice currency
```

Inspect installed tests for these scenarios.

Do not design custom currency formulas in MCP.

Task 45 recommendation must state whether V1:

- supports native multi-currency;
- safely passes through native behavior;
- or explicitly limits the first public contract while leaving native engine intact.

---

# 21. Deductions / Write-Off / Bank Fees / Exchange Difference

Audit Payment Entry deductions and difference amount.

Determine:

- what `difference_amount` means;
- submit requirement for zero difference;
- how deductions are represented;
- early payment discounts;
- write-offs;
- bank charges;
- exchange gain/loss;
- account selection;
- cost center/accounting dimension requirements.

Decide whether first MCP payment capability should allow caller-defined deductions.

Default safety preference:

```text
Do not expose arbitrary deduction/account lines in first V1
```

unless native helper automatically creates required lines safely.

Report evidence and recommendation.

---

# 22. Taxes / Withholding on Payment Entry

Inspect whether Payment Entry can contain:

- taxes
- tax withholding
- advance taxes/charges
- payment taxes

Determine:

- relevant Customer Receive cases;
- relevant Supplier Pay cases;
- which native logic can add them automatically;
- whether India Compliance hooks affect Payment Entry;
- whether caller inputs would be required.

Do not implement.

Recommend whether first Accounts V1 should exclude caller-configurable tax rows.

---

# 23. Payment Request

Payment Request is a different business document.

Audit its relationship to:

```text
Sales Invoice
    ↓
Payment Request
    ↓
gateway/customer payment
    ↓
Payment Entry / settlement
```

Determine:

- whether Payment Request is required for normal manual customer receipts;
- whether Payment Entry can be created directly from Sales Invoice;
- whether Payment Request should be explicitly deferred;
- whether Payment Entry updates linked Payment Requests.

Do not implement Payment Request in Task 44.

Do not let Payment Request unnecessarily block the basic Payment Entry flow.

---

# 24. Payment Reconciliation

Audit Payment Reconciliation and unreconciliation.

Understand:

```text
unallocated Payment Entry
        +
outstanding Sales Invoice
        ↓
Payment Reconciliation
        ↓
allocation updated
```

Trace:

- how outstanding references are retrieved;
- how payments are retrieved;
- permissions;
- Payment Ledger updates;
- whether underlying GL is changed/reposted;
- how unreconcile works;
- what mutations occur on submitted Payment Entries/references.

Determine whether reconciliation belongs:

- in Accounts V1;
- immediately after Payment Entry;
- or later.

Do not implement it.

---

# 25. Payment Ledger

Trace exact relationship between:

```text
General Ledger
```

and:

```text
Payment Ledger
```

Document:

- what Sales Invoice submission creates;
- what Payment Entry submission creates/updates;
- how invoice outstanding is calculated;
- how advances are represented;
- how allocation changes affect Payment Ledger;
- how reconciliation affects Payment Ledger;
- how cancellation reverses effects.

The MCP must never manually update Payment Ledger Entry records.

---

# 26. General Ledger Effects

Trace Payment Entry submit behavior from installed source.

At minimum document:

```text
Receive:
Bank/Cash Dr
Receivable Cr
```

```text
Pay:
Payable Dr
Bank/Cash Cr
```

```text
Internal Transfer:
Destination Dr
Source Cr
```

But report the actual installed source mechanisms rather than treating these examples as complete.

Inspect:

- `make_gl_entries()`
- deductions/tax GL
- exchange gain/loss
- advance-account behavior
- accounting dimensions
- party references
- cancellation reversal/repost

MCP must not prebuild GL rows.

---

# 27. Submit Effects

Trace `PaymentEntry.on_submit()` in the installed version.

Document every material side effect, including at least whether it:

- validates zero difference
- processes tax withholding
- updates Payment Requests
- updates Payment Schedule
- writes GL
- updates outstanding/payment references
- updates status
- triggers subscription invoice updates
- writes Payment Ledger indirectly
- creates repost jobs/documents
- invokes hooks

Use exact source evidence.

This section determines the submit approval preview requirements for a future implementation.

---

# 28. Cancel Effects

Trace `PaymentEntry.on_cancel()`.

Document:

- GL reversal
- Payment Ledger/outstanding effects
- Payment Schedule reversal
- Payment Request updates
- advance reference delinking
- repost behavior
- ignored linked ledger doctypes
- restrictions/blockers
- status changes

Determine what downstream relationships can prevent cancellation.

Do not design cascade behavior.

---

# 29. Delete Behavior

Inspect Frappe/ERPNext behavior for deleting:

- Draft Payment Entry
- Cancelled Payment Entry
- Submitted Payment Entry

Document:

- cancel-before-delete requirement
- linked document behavior
- ledger records
- reconciliation links
- payment requests
- references

Recommend whether Payment Entry should be added to existing generic lifecycle:

```text
submit
cancel
delete
```

and nothing else.

---

# 30. Read Capability

Determine what a safe future:

```text
get_payment_entry
```

should expose.

Classify fields.

Potentially useful:

- name
- status/docstatus
- payment type
- company
- posting date
- party type
- party
- party name
- mode of payment
- paid_from / paid_to only if needed for accounting review
- account currencies
- paid amount
- received amount
- total allocated amount
- unallocated amount
- reference no/date
- bounded references
- bounded deductions summary
- remarks

Potentially sensitive/noisy:

- all custom fields
- raw GL rows
- full bank account numbers
- secrets
- complete account metadata
- arbitrary child tables
- raw internal flags

Provide a DocType-local field-policy recommendation.

---

# 31. Query Capability

Determine safe future:

```text
query_payment_entries
```

filters/projections.

Useful business filters may include:

- date range
- status/docstatus
- payment type
- party type
- party
- company
- mode of payment
- amount range
- reference number
- submitted/cancelled status

Determine whether filtering by linked Sales Invoice requires:

- child table joins;
- a specialized query;
- existing Frappe query mechanisms.

Do not propose raw SQL/LLM expressions.

---

# 32. Aggregate Capability

Determine useful future:

```text
aggregate_payment_entries
```

Examples:

```text
count payments
sum received amount
sum paid amount
group by payment type
group by status
group by customer/party
group by date period
```

Verify which amount field is semantically safe to aggregate when currencies differ.

Do not blindly sum amounts across mixed currencies without grouping/normalization.

Document recommended currency-grouping rules.

Reuse the current shared aggregate foundation if suitable.

---

# 33. PDF / Email

Determine whether generic Payment Entry PDF/email should be supported in Accounts.

Audit:

- native Print support
- standard print format
- read/print permission
- whether email is a normal/useful Payment Entry operation
- recipient resolution risks
- bank/payment-reference exposure risks

Recommend:

```text
PDF: include or defer
Email: include or defer
```

Do not implement.

---

# 34. Approval Model

Determine future mutating capability requirements.

Expected model:

```text
prepare Payment Entry
        ↓
bounded preview
        ↓
shared ApprovalStore
        ↓
atomic claim
        ↓
fresh native rebuild / latest outstanding
        ↓
fingerprint comparison
        ↓
Draft insert only
```

Then separately:

```text
generic lifecycle submit
```

Audit whether this pattern fits Payment Entry.

Important stale-state cases:

- invoice partially paid by another process
- invoice fully paid after prepare
- invoice cancelled
- invoice outstanding changed
- payment terms changed
- bank/default account changed
- exchange rate changed
- Customer/Company account changed
- source helper output changed
- Payment Request allocation changed

Determine what material fields belong in the approval fingerprint.

---

# 35. Create Draft vs Submit

Decide whether the first payment tool should:

### Pattern A

```text
prepare
confirm → create Draft Payment Entry
submit separately through generic lifecycle
```

or:

### Pattern B

```text
prepare
confirm → submit Payment Entry immediately
```

Default architectural preference based on current MCP design is **Pattern A**, because financial ledger impact should remain a separate approved lifecycle action.

But verify against actual current project conventions and explain the recommendation.

---

# 36. Payment Entry Public Tool Shape

Compare candidate public designs.

## Candidate A — Invoice-specific explicit tool

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment
```

Pros:

- narrow intent
- minimal fields
- safer
- directly continues current Sales flow

Cons:

- future supplier/advance/multi-invoice capabilities need separate tools

## Candidate B — Customer receipt tool

```text
prepare_customer_payment
confirm_customer_payment
```

May support invoice, multiple invoices, or unallocated receipt.

## Candidate C — generic Payment Entry tool

```text
prepare_payment_entry
confirm_payment_entry
```

Could accept:

- payment_type
- party_type
- party
- accounts
- references
- amounts
- etc.

Potentially too broad and exposes accounting internals to the LLM.

## Candidate D — explicit business tools over shared internal Payment Entry engine

Example future public capabilities:

```text
receive_sales_invoice_payment
receive_customer_advance
pay_purchase_invoice
transfer_internal_funds
```

while sharing one internal native Payment Entry adapter.

This is likely aligned with the existing project's principle that **genericity should primarily live in internal mechanics while public MCP tools expose clear business intent**, but the audit must verify and recommend rather than assume.

Provide a decision matrix and one recommended Task 45 public surface.

---

# 37. Accounts Profile Granularity

Determine what enabling:

```text
MCP_PROFILE=accounts
```

should mean.

It should not require each company to configure:

```text
enable_sales_invoice_payment=yes
enable_partial_payment=yes
enable_advance=yes
...
```

unless a genuine security/capability policy requires such controls.

Distinguish:

```text
ERPNext business configuration
```

from:

```text
MCP capability exposure/security configuration
```

Do not duplicate ERPNext business workflow settings.

Recommend the minimal Accounts profile registration model.

---

# 38. Cross-Profile Dependencies

Answer:

- Can Accounts profile operate on Sales Invoice even if the Sales MCP process is not running?
- Should it depend only on the Frappe database/ERPNext DocTypes rather than another MCP profile process?
- Can Accounts profile later operate on Purchase Invoice independently?
- Does it need Customer/Supplier search tools duplicated?
- Should it have narrow lookup capabilities for party/invoice references?
- Should shared master read services be reused internally without duplicating public tools?

Architecture requirement:

```text
Accounts MCP profile must not depend on another MCP process being alive.
```

Each profile should independently call the same ERPNext site through its own allowed tools.

---

# 39. Identity and Site Boundary

Verify future Accounts tools continue to use:

- configured site
- current authenticated Frappe identity
- existing shared-secret/user-header identity boundary for HTTP where applicable
- existing stdio identity model
- Task 40 REST principal model

No:

- hard-coded site
- hard-coded company
- hard-coded customer
- Administrator impersonation
- caller-controlled identity
- caller-controlled site

Document direct and REST implications.

---

# 40. Permission Boundary

Task 44 is not the cross-project permission refactor discussed separately.

However, audit the native Payment Entry flow enough to state:

- which native helpers enforce permissions;
- which document reads use permission-enforcing APIs;
- where final insert/submit checks occur;
- whether current MCP preflight patterns would be redundant.

Do NOT modify existing permission code.

Do NOT broaden this task into fixing Sales permissions.

Simply record evidence needed for Task 45.

Preferred future principle:

```text
Use permission-enforcing native Frappe/ERPNext APIs,
let Frappe decide,
catch/translate exceptions,
avoid independent MCP authorization logic.
```

---

# 41. Data Minimization / LLM Exposure

The audit must define exactly what the LLM needs to see.

For invoice payment preview likely useful:

- Payment Entry target
- Sales Invoice name
- Customer
- Company
- invoice outstanding
- payment amount
- allocated amount
- unallocated amount
- posting date
- Mode of Payment / bank-cash destination in human-readable bounded form
- currency
- exchange rate only when material
- reference no/date
- bounded deductions if any

Likely avoid:

- full Chart of Accounts
- arbitrary account lists
- raw GL rows
- full Bank Account number
- IBAN/SWIFT unless explicitly necessary for a separate banking use case
- raw Payment Ledger entries
- internal metadata
- complete Customer master
- unrelated invoices
- all outstanding documents
- secrets
- cache state
- tracebacks

Provide a field-by-field recommendation.

---

# 42. Concurrency / Stale Financial State

Payment is highly state-sensitive.

Audit how ERPNext protects against:

```text
Agent A prepares payment for SI outstanding 10,000

Meanwhile:
Agent B submits another payment 6,000

Agent A confirms old 10,000 preview
```

Installed source has latest-reference/outstanding validations; trace them.

Determine whether MCP fingerprint + fresh native rebuild adds useful protection on top.

Recommend exact stale-state handling.

Do not implement custom locking unless native/MCP approval architecture demonstrably requires it.

---

# 43. Runtime Metadata

Inspect static DocType metadata and document what must be runtime-verified later for:

- Payment Entry
- Payment Entry Reference
- Payment Entry Deduction
- Mode of Payment
- Mode of Payment Account
- Bank Account
- Account
- Company
- Customer
- Supplier
- Sales Invoice
- Sales Order
- Purchase Invoice
- Purchase Order
- Payment Schedule

Account for custom fields/property setters.

Do not hard-code a site-specific schema.

---

# 44. Optional Apps

Inspect installed app hooks affecting:

- Payment Entry
- Sales Invoice payment
- Payment Ledger
- bank/payment fields
- tax withholding
- India Compliance

Do not assume India Compliance affects Payment Entry merely because it is installed.

Report only verified hooks/overrides.

MCP must remain optional-app neutral.

---

# 45. Security / Financial Risk Classification

Classify future Payment Entry operations by risk:

```text
Read only
Draft financial document creation
Ledger-impacting submit
Cancellation/reversal
Reconciliation
Internal fund transfer
Arbitrary accounting adjustment
```

Use this to explain why some capabilities belong in first Accounts V1 and others should be deferred.

Journal Entry must be explicitly compared and **not recommended as the first routine payment capability** unless installed ERPNext behavior proves otherwise.

---

# 46. Candidate Accounts V1 Capability Matrix

Produce a table like:

| Capability | Native support | Risk | V1 decision | Reason |
|---|---|---:|---|---|
| SI → customer Receive PE | | | | |
| partial SI payment | | | | |
| multi-SI receipt | | | | |
| customer advance | | | | |
| standalone receipt | | | | |
| supplier PI payment | | | | |
| internal transfer | | | | |
| get Payment Entry | | | | |
| query Payment Entry | | | | |
| aggregate Payment Entry | | | | |
| submit/cancel/delete | | | | |
| PDF | | | | |
| email | | | | |
| Payment Reconciliation | | | | |
| Payment Request | | | | |
| Journal Entry | | | | |

This matrix must drive Task 45.

---

# 47. Required Audit Questions

The final report must answer all of these directly.

1. What exact event marks the handoff from Sales to Accounts?
2. Should Sales Invoice remain only in Sales profile?
3. Should Payment Entry live only in Accounts profile?
4. What exact installed native function creates a Payment Entry from Sales Invoice?
5. Does that function return an unsaved Draft?
6. What input does it actually need?
7. Does it support full payment?
8. Does it support partial payment?
9. How is amount override passed?
10. How is bank/cash destination selected?
11. Is Mode of Payment a better MCP input than raw account?
12. When are reference number/date mandatory?
13. How are payment terms handled?
14. How are multi-invoice allocations handled?
15. How are advances handled?
16. How is overpayment/unallocated amount handled?
17. How are multi-currency payments handled?
18. How are exchange gains/losses handled?
19. How are deductions handled?
20. What does submit do?
21. What does cancel do?
22. How does Payment Ledger change?
23. How does Sales Invoice outstanding change?
24. What stale-state checks does ERPNext already perform?
25. What stale-state/fingerprint protection should MCP add?
26. What is the safest first public tool contract?
27. Should first confirm create Draft only?
28. Can existing generic lifecycle handle submit/cancel/delete?
29. What read/query/aggregate should be added?
30. Should PDF/email be included?
31. What should be deferred?
32. Can future Supplier Pay use the same internal engine?
33. Can Accounts profile run independently from Sales/Purchase MCP processes?
34. What minimum data should the LLM see?
35. What exact Task 45 should implement?

---

# 48. Required Test/Verification Planning

Task 44 does not run destructive accounting tests unless an explicitly authorized throwaway environment already exists.

The audit must produce a future Task 45 test matrix covering at least:

## Invoice payment

- full payment
- partial payment
- overpayment
- fully paid invoice
- cancelled invoice
- wrong Customer/reference
- payment terms
- multiple payment terms
- stale outstanding
- simultaneous payment attempt

## Accounts/defaults

- default bank/cash account
- Mode of Payment default
- missing default account
- account currency mismatch
- disabled account
- wrong Company account

## Currency

- same currency
- invoice foreign currency
- bank foreign currency
- exchange gain
- exchange loss

## Approval

- prepare no write
- confirm Draft only
- user/site/action binding
- expiry
- one-shot
- stale fingerprint
- concurrent repeat

## Lifecycle

- submit
- cancel
- delete
- linked/reference behavior
- outstanding restoration on cancel

## Read/query/aggregate

- permission behavior
- allowed fields
- filters
- pagination
- currency-safe aggregate

## REST/direct

- direct parity
- fixed REST operation
- malformed payload
- unknown operation
- identity/site boundary

## Regression

- Sales profile unchanged
- Purchase profile unchanged
- Tasks 42/43 still pass
- existing shared approval behavior
- existing REST backend

---

# 49. Deliverable

Create exactly:

```text
docs/inspect/ACCOUNTS_PAYMENT_ENTRY_NATIVE_FLOW_AUDIT.md
```

The report must contain at least:

1. Executive conclusion
2. Current MCP profile baseline
3. Sales → Accounts handoff diagram
4. Installed ERPNext source/version evidence
5. Exact `get_payment_entry` callable/signature
6. SI → Payment Entry native call chain
7. Minimum public input analysis
8. Full payment behavior
9. Partial payment behavior
10. Overpayment/unallocated behavior
11. Customer advance behavior
12. Multi-invoice allocation
13. Payment Terms behavior
14. Mode of Payment behavior
15. Bank Account vs Account analysis
16. Reference no/date behavior
17. Receive/Pay/Internal Transfer analysis
18. Supplier future compatibility
19. Multi-currency analysis
20. Deductions/write-off/exchange-difference analysis
21. Tax/withholding analysis
22. Payment Request relationship
23. Payment Reconciliation relationship
24. Payment Ledger behavior
25. General Ledger behavior
26. Submit side effects
27. Cancel side effects
28. Delete behavior
29. Permission/native authority findings
30. Approval/fingerprint/stale-state design
31. Read field-policy recommendation
32. Query recommendation
33. Aggregate recommendation
34. PDF/email recommendation
35. Direct/REST architecture
36. Cross-profile independence
37. Data-minimization review
38. Optional-app findings
39. Risk classification
40. Candidate Accounts V1 capability matrix
41. Task 45 test matrix
42. Risks/limitations
43. Exact Task 45 recommendation

Do not produce production code.

---

# 50. Acceptance Criteria

Task 44 is complete only when:

1. No production code is changed.
2. No site/accounting data is changed.
3. Current post-Task-43 MCP architecture is inspected.
4. Exact installed Frappe/ERPNext source is inspected.
5. The exact native SI → Payment Entry helper is identified.
6. Its exact signature and behavior are documented.
7. Full payment is traced.
8. Partial payment is traced.
9. Overpayment/unallocated behavior is traced.
10. Advance behavior is traced.
11. Multi-invoice behavior is traced.
12. Payment Terms behavior is traced.
13. Mode of Payment/default-account behavior is traced.
14. multi-currency behavior is traced.
15. deduction/exchange behavior is traced.
16. submit side effects are traced.
17. cancel side effects are traced.
18. Payment Ledger behavior is traced.
19. GL behavior is traced.
20. reconciliation is understood and scoped.
21. Receive/Pay/Internal Transfer are classified.
22. Purchase remains implementation-out-of-scope.
23. Journal Entry remains implementation-out-of-scope.
24. Accounts-profile boundary is recommended.
25. direct/REST implications are documented.
26. LLM data-minimization policy is proposed.
27. a concrete minimal Task 45 is recommended.
28. limitations and unverified runtime/site behavior are explicitly stated.

---

# 51. Expected Result

The audit should leave us with a clear architecture similar to:

```text
SALES PROFILE
────────────────────────
Sales Invoice
    ↓
submit
    ↓
receivable exists
    ↓
domain handoff

ACCOUNTS PROFILE
────────────────────────
native customer-payment capability
    ↓
Draft Payment Entry
    ↓
generic lifecycle submit
    ↓
ERPNext GL + Payment Ledger
    ↓
invoice outstanding reduced
```

But the exact public tool names and first-scope behavior must come from the audit evidence.

The likely safe first implementation may be a narrow submitted Sales Invoice → Draft customer Payment Entry flow, but Task 44 must validate that rather than assuming it.

---

# 52. Limitations

This audit does not implement:

- Accounts profile
- Payment Entry tools
- Payment Request
- Payment Reconciliation
- Journal Entry
- Purchase Invoice
- supplier payment tools
- internal transfer
- advance tools
- bank reconciliation
- bank transaction import
- payment gateways
- write-off tools
- custom accounting logic
- permission refactor
- live production accounting tests

If the installed source reveals additional relevant accounting documents, record them but do not expand implementation scope automatically.

---

# 53. Exact Next Task

The audit must end by recommending one exact next implementation task:

```text
Task 45 — <evidence-based Accounts/Payment Entry V1 implementation title>
```

Task 45 should be the **smallest safe vertical slice** that continues the current submitted Sales Invoice flow into Accounts.

Preferred qualities:

- native ERPNext helper
- minimal public input
- business-intent-oriented tool contract
- prepare/approval/confirm
- Draft-only creation
- separate generic lifecycle submit
- permission-safe native behavior
- bounded preview
- stale-state protection
- direct + REST parity
- no raw debit/credit construction
- no arbitrary Journal Entry

Do not implement Task 45 during Task 44.
