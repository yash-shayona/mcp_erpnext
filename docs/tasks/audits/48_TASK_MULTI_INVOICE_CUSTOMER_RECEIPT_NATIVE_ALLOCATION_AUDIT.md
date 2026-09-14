# Task 48 — Multi-Invoice Customer Receipt Native Allocation Audit

## Status

**Inspection-only / architecture audit**

This task follows:

- Task 44 — Accounts / Payment Entry Native Flow Audit
- Task 45 — Accounts V1: Sales Invoice Customer Receive Payment Entry as Draft
- Task 47 — Payment Entry Read, Query, and Aggregate Intelligence

The current Accounts profile can now:

```text
single Submitted Sales Invoice
    ↓
prepare_sales_invoice_payment
    ↓
approval
    ↓
confirm_sales_invoice_payment
    ↓
Draft Payment Entry
    ↓
generic submit/cancel/delete
```

and can read/query/aggregate existing Payment Entries.

The next business requirement is the common accounting case where **one customer receipt settles more than one Sales Invoice**.

Example:

```text
Customer: Arkee Foods

Payment received: ₹30,000

Allocate:
SINV-001  ₹10,000
SINV-002   ₹8,000
SINV-003  ₹12,000
```

ERPNext Payment Entry supports multiple reference rows, but the current Task 45 public flow intentionally starts from one Sales Invoice and uses the single-source native `get_payment_entry("Sales Invoice", ...)` factory.

Before adding a multi-invoice write tool, inspect and freeze the native allocation architecture.

---

# 1. Objective

Determine the safest native ERPNext design for a future Accounts capability that receives **one Customer payment and allocates it across multiple outstanding Sales Invoices**.

The audit must establish:

1. the exact native ERPNext outstanding-invoice retrieval APIs;
2. the exact native allocation/reference-building APIs;
3. whether a native high-level customer-payment helper already exists;
4. the correct public MCP contract;
5. which fields the caller supplies versus ERPNext derives;
6. same-Customer / same-Company / party-account constraints;
7. currency compatibility rules;
8. payment-term behavior;
9. partial allocation behavior;
10. overpayment/unallocated remainder behavior;
11. stale outstanding / concurrent payment behavior;
12. approval/fingerprint requirements;
13. what can safely reuse Task 45;
14. what must remain deferred;
15. the exact smallest Task 49 implementation.

No production code or accounting data may change in Task 48.

---

# 2. Core Architecture Principle

MCP must expose business intent, not a free-form accounting document builder.

Target mental model:

```text
User:
"We received ₹30,000 from Arkee Foods.
Apply ₹10,000 to SINV-001,
₹8,000 to SINV-002,
and ₹12,000 to SINV-003."

        ↓

typed MCP customer-receipt intent

        ↓

ERPNext native Payment Entry / outstanding / allocation APIs

        ↓

bounded Draft Payment Entry preview

        ↓

approval

        ↓

fresh outstanding rebuild + fingerprint

        ↓

Draft Payment Entry only
```

Do NOT design:

```text
generic_payment_entry(
    payment_type,
    party_type,
    party,
    paid_from,
    paid_to,
    references=[arbitrary rows],
    deductions=[arbitrary rows],
    ...
)
```

The LLM must not construct raw accounting internals.

---

# 3. No Production Changes

Task 48 is inspection-only.

Allowed repository output:

```text
docs/inspect/MULTI_INVOICE_CUSTOMER_RECEIPT_NATIVE_ALLOCATION_AUDIT.md
```

Do NOT change:

- production Python
- contracts
- profiles
- services
- tools
- REST handlers
- lifecycle policy
- tests
- DocTypes
- fixtures
- settings
- site data
- Customers
- Sales Invoices
- Payment Entries
- GL Entries
- Payment Ledger Entries
- accounts
- currencies
- bank accounts
- Mode of Payment
- Payment Terms
- reconciliation state

Do not submit, cancel, reconcile, or create accounting documents.

---

# 4. Repository Baseline to Inspect

Inspect the current post-Task-47 repository.

At minimum inspect:

- `accounts` profile
- Task 45 customer receipt service/contracts/tools
- Task 47 Payment Entry read/query/aggregate
- shared `ApprovalStore`
- `claim_for_confirm_write()`
- fingerprint patterns
- generic lifecycle
- direct backend
- REST backend
- remote operation registry
- typed contract conventions
- query/reference filter conventions
- current Payment Entry public field policy
- existing tests
- tool catalog
- previous audit/implementation reports

Confirm the actual current implementation before proposing changes.

---

# 5. Installed ERPNext Source to Inspect

Use the exact installed ERPNext checkout as runtime source of truth.

At minimum inspect the installed equivalents of:

```text
erpnext/accounts/doctype/payment_entry/payment_entry.py
erpnext/accounts/doctype/payment_entry/payment_entry.js
erpnext/accounts/doctype/payment_entry/test_payment_entry.py

erpnext/accounts/utils.py

erpnext/accounts/doctype/payment_reconciliation/payment_reconciliation.py

erpnext/controllers/accounts_controller.py
erpnext/accounts/general_ledger.py

erpnext/accounts/doctype/sales_invoice/sales_invoice.py
```

Trace actual call chains rather than relying on filenames.

Search for and inspect exact implementations/callers of:

```text
get_payment_entry
get_outstanding_reference_documents
get_outstanding_invoices
get_reference_details
set_missing_ref_details
allocate_party_amount_against_ref_docs
validate_allocated_amount
validate_allocated_amount_with_latest_data
get_payment_entry_against_order
get_payment_entry_against_invoice
reconcile_against_document
```

Names may vary by installed version.

Do not assume an API exists because it exists in another ERPNext version.

---

# 6. Primary Business Case

Audit this exact first scenario:

```text
Customer = Arkee Foods
Company = Shayona Technology

Outstanding:
SINV-A = 10,000
SINV-B = 8,000
SINV-C = 20,000

Customer pays = 30,000

Requested allocation:
SINV-A = 10,000
SINV-B = 8,000
SINV-C = 12,000
```

Expected business result after eventual submit:

```text
SINV-A outstanding = 0
SINV-B outstanding = 0
SINV-C outstanding = 8,000
Payment Entry unallocated = 0
```

Do not implement or mutate anything.

Use installed source/tests to determine exact native behavior.

---

# 7. Identify Native Outstanding Retrieval

Determine the exact installed native method(s) ERPNext uses to retrieve Customer outstanding documents.

Document:

- callable/import path
- function signature
- required inputs
- optional inputs
- Company behavior
- party type
- party
- party account
- currency
- posting date
- cost center/accounting dimensions if relevant
- min/max outstanding filters
- Payment Terms behavior
- return schema
- permissions
- whether it uses Payment Ledger
- whether it includes Sales Orders/advances
- whether it includes already allocated documents
- how it excludes fully paid/cancelled invoices

Likely APIs must be verified, not assumed.

---

# 8. Outstanding Retrieval vs Public Search

Distinguish:

```text
MCP query_sales_invoices / Payment Entry read tools
```

from:

```text
ERPNext accounting-native outstanding reference retrieval
```

The future payment-allocation tool should use accounting-native outstanding state for payment decisions.

Do not use a generic Sales Invoice search result as the source of truth for allocation.

Explain why.

---

# 9. Same Customer Constraint

Audit native validation when multiple Sales Invoice references belong to different Customers.

Example:

```text
SINV-A → Arkee Foods
SINV-B → Vertex Learning
```

Determine:

- where ERPNext rejects this;
- whether reference rows must match `party`;
- exact validation/error path;
- whether MCP should perform an early shape check;
- whether native validation alone is sufficient.

Future V1 must not silently create a payment spanning different Customers.

---

# 10. Same Company Constraint

Audit:

```text
SINV-A → Company A
SINV-B → Company B
```

Determine:

- native behavior;
- party-account behavior;
- account-currency implications;
- whether one Payment Entry can ever validly span companies.

Expected likely design is one Company per Payment Entry, but verify installed source.

Do not invent a cross-company payment abstraction.

---

# 11. Party Account Compatibility

Multiple invoices may use different receivable accounts.

Audit:

```text
SINV-A → Debtors INR
SINV-B → Overseas Debtors USD
```

or different receivable accounts within the same currency.

Determine native constraints:

- same party account required?
- same party account currency required?
- can references with different receivable accounts coexist?
- how `paid_from` is selected for Customer Receive?
- what happens with invoice discounting account?

This is critical for the public contract.

---

# 12. Currency Compatibility

Audit at least:

```text
Case A:
all invoices INR
bank INR

Case B:
all invoices USD
party account USD
bank USD

Case C:
all invoices USD
party account USD
bank INR

Case D:
same Customer but invoices in different currencies

Case E:
same Customer, same invoice currency, different receivable account currency

Case F:
bank currency differs from payment/reference currency
```

Trace:

- Payment Entry party currency;
- paid amount;
- received amount;
- source exchange rate;
- target exchange rate;
- reference exchange rate;
- allocation amount semantics;
- difference amount;
- exchange gain/loss;
- whether mixed-reference currencies are allowed.

Do not design MCP FX formulas.

---

# 13. Public Allocation Amount Semantics

For a future tool, determine what:

```text
allocation amount
```

means.

Is each amount expressed in:

- invoice currency?
- party account currency?
- Payment Entry party currency?
- company currency?
- reference currency?

Do not expose an ambiguous numeric field.

The audit must recommend explicit typed semantics.

---

# 14. Payment Amount Semantics

Determine relationship between:

```text
customer receipt amount
```

and:

```text
sum(reference allocated_amount)
```

Cases:

### Exact allocation

```text
payment = 30,000
sum allocations = 30,000
unallocated = 0
```

### Under-allocation

```text
payment = 30,000
sum allocations = 25,000
unallocated = 5,000
```

### Over-allocation

```text
payment = 30,000
sum allocations = 35,000
```

Determine native validation and future V1 policy.

Do not invent implicit advance handling.

---

# 15. Overpayment / Unallocated Remainder

Task 45 intentionally rejected overpayment.

For multi-invoice receipts audit whether future V1 should:

### Option A
require:

```text
payment amount == sum allocations
```

and reject unallocated remainder.

### Option B
allow:

```text
payment amount > allocations
```

and leave native `unallocated_amount`.

### Option C
model excess explicitly as advance.

Assess:

- ERPNext native behavior;
- accounting effect;
- reconciliation implications;
- user expectation;
- approval clarity;
- risk.

Recommend one for Task 49.

---

# 16. Partial Allocation Across Multiple Invoices

Audit:

```text
SINV-A outstanding 10,000 → allocate 10,000
SINV-B outstanding 8,000  → allocate 5,000
SINV-C outstanding 20,000 → allocate 0 / omit
```

Determine:

- valid reference construction;
- latest-outstanding validation;
- whether zero allocation rows should be omitted;
- how remaining outstanding is represented;
- whether Payment Schedule rows complicate allocation.

---

# 17. Fully Paid / Cancelled / Invalid Reference

For each requested invoice determine future behavior when:

- invoice is fully paid before prepare;
- invoice becomes fully paid between prepare and confirm;
- invoice is cancelled;
- invoice is Draft;
- invoice belongs to another Customer;
- invoice belongs to another Company;
- reference account changed;
- invoice is a return/credit note;
- invoice outstanding is negative;
- invoice is disputed/blocked by another native policy if applicable.

Classify:

```text
prepare-time rejection
confirm-time stale rejection
native validation
```

---

# 18. Duplicate Invoice Reference

Audit:

```text
references:
SINV-A 5,000
SINV-A 5,000
```

Determine:

- whether ERPNext permits duplicate rows;
- where duplicate reference validation occurs;
- future MCP contract behavior.

Preferred public behavior is likely one row per invoice, but verify.

---

# 19. Payment Terms

This is critical.

An invoice may have:

```text
Payment Term 1
Payment Term 2
Payment Term 3
```

and ERPNext may allocate against term-specific reference rows.

Audit:

- how outstanding retrieval represents Payment Terms;
- reference key identity;
- due date;
- payment term;
- term-specific outstanding;
- allocated amount;
- early payment discount;
- stale term validation.

Determine whether future public contract can simply accept:

```text
invoice + amount
```

or whether term-specific allocation must be explicit when enabled.

Do not flatten term rows if ERPNext treats them separately.

---

# 20. Early Payment Discounts

Audit when one or more selected invoices qualify for early payment discount.

Determine:

- where discount is calculated;
- reference date dependency;
- deductions generated;
- allocation amount vs paid amount;
- effect across multiple invoices;
- fingerprint material.

Do not expose arbitrary discount account fields.

---

# 21. Multiple Invoices + Different Payment Terms

Audit mixed references such as:

```text
SINV-A no payment terms
SINV-B term-based allocation
SINV-C early-payment discount
```

Determine whether one Payment Entry can safely include all.

Recommend Task 49 behavior.

Fail closed if the first implementation should not support a complex combination.

---

# 22. Native Reference Row Construction

Determine the safest way to construct multi-invoice references.

Compare:

## Approach A
Start from:

```python
frappe.new_doc("Payment Entry")
```

then use native document methods to fetch/default/allocate outstanding references.

## Approach B
Start from one native:

```python
get_payment_entry("Sales Invoice", first_invoice, ...)
```

then add additional references through native helper methods.

## Approach C
Use a higher-level native customer-payment/outstanding-allocation helper if one exists.

## Approach D
Use Payment Reconciliation internals.

Payment Reconciliation should not be reused merely because it manipulates references unless it is actually the correct native creation path.

Recommend the native path with evidence.

---

# 23. Do Not Manually Copy Invoice Fields

Future MCP must not manually reproduce:

- Customer
- Company
- party account
- account currencies
- exchange rates
- invoice total
- invoice outstanding
- payment terms
- due dates
- discounts
- reference exchange rate
- allocated amount validation

If a small explicit reference structure must be authored by MCP, it must be populated from native outstanding/reference APIs and validated by Payment Entry controller.

Document the safe boundary.

---

# 24. Mode of Payment

Audit whether Task 45's destination abstraction remains sound for multi-invoice receipt:

```text
mode_of_payment
```

Determine:

- account default resolution;
- Company constraints;
- currency constraints;
- whether invoice-specific Mode of Payment differences matter;
- which source controls the final Mode of Payment.

One customer payment should have one coherent destination.

---

# 25. Bank Account

Audit Task 45's:

```text
bank_account
```

fallback in multi-invoice context.

Determine:

- Bank Account → ledger Account mapping;
- Company binding;
- account currency;
- conflict with Mode of Payment;
- whether all references can settle through one bank/cash destination.

No raw ledger account input should be introduced unless unavoidable and separately justified.

---

# 26. Reference Number / Date

Audit future multi-invoice receipt fields:

```text
reference_no
reference_date
```

Determine:

- same semantics as Task 45?
- native mandatory rules;
- duplicate reference checks;
- effect on early payment discounts;
- whether `reference_date` drives payment terms/discounts.

Recommend exact V1 requirement.

---

# 27. Posting Date

Task 44 found native single-invoice factory sets posting date from `nowdate()`.

Audit multi-invoice creation options:

- should V1 accept `posting_date`?
- can it be safely assigned before native reference/outstanding calculation?
- does outstanding retrieval need the posting date?
- closed-period/frozen-account implications;
- future-dated/backdated payment behavior.

Recommend include/defer.

Do not silently accept a field the native path ignores.

---

# 28. Remarks

Determine whether bounded optional remarks from Task 45 can be reused unchanged.

No free-form accounting instructions should be parsed from remarks.

---

# 29. Multi-Currency Bank Amount

Determine whether future contract needs:

```text
bank_amount
```

as Task 45 does for cross-currency cases.

If all invoices share party/account currency but bank currency differs:

- what amount does caller provide?
- what amount does ERPNext derive?
- what preview is necessary?

Do not expose raw exchange-rate override unless future dedicated audit proves necessary.

---

# 30. Taxes / Withholding

Audit whether customer receive multi-invoice Payment Entry can invoke:

- taxes
- advance taxes
- withholding
- India Compliance hooks

Future V1 should not allow caller-created tax rows.

Determine whether native hooks can add/alter them automatically and what the preview/fingerprint should include.

---

# 31. Deductions / Difference Amount

Audit:

- early payment discount
- exchange difference
- native deduction rows
- difference amount zero requirement
- bank fee/write-off possibilities

Task 49 should not expose arbitrary deduction rows.

Determine whether automatically generated native deduction rows can be safely allowed and summarized.

---

# 32. Customer Advance Relationship

Multi-invoice receipt with unallocated remainder begins to overlap with customer advance.

Audit the boundary:

```text
receipt amount 35,000
allocations 30,000
unallocated 5,000
```

Is that simply unallocated party credit or an advance-account posting depending on Company settings?

Document:

- party ledger behavior;
- separate advance account setting;
- later reconciliation;
- tax implications.

This informs whether Task 49 should reject remainder.

---

# 33. Payment Reconciliation Boundary

Payment Reconciliation supports allocating existing payments to invoices.

Clarify distinction:

### Multi-invoice receipt creation
Customer payment is being recorded now with chosen invoice allocations.

### Payment Reconciliation
Payment already exists and is now being allocated/reallocated.

Do not conflate them.

Recommend separate future capability for reconciliation.

---

# 34. Payment Request Boundary

Audit whether open Payment Requests related to selected invoices can be automatically linked/updated by Payment Entry.

Do not make Payment Request part of public Task 49 unless native behavior requires no additional caller choice.

---

# 35. Payment Ledger Authority

Trace how submitted multi-reference Payment Entry affects Payment Ledger.

For each reference:

```text
against_voucher_type
against_voucher_no
amount
```

Do not propose direct Payment Ledger writes.

MCP must only create/submit normal Payment Entry.

---

# 36. General Ledger Authority

Trace native GL construction for:

```text
one customer receipt
multiple Sales Invoice references
```

Determine whether reference allocations affect the party GL line split or against-voucher metadata.

Do not manually build GL rows.

---

# 37. Approval Model

Future multi-invoice receipt must reuse:

```text
prepare
    ↓
native outstanding/reference build
    ↓
bounded preview
    ↓
shared ApprovalStore
    ↓
confirm
    ↓
atomic claim
    ↓
fresh outstanding retrieval
    ↓
fresh Payment Entry rebuild
    ↓
fingerprint compare
    ↓
Draft insert only
```

Audit whether this remains sufficient.

No immediate submit.

---

# 38. Fingerprint Material

Recommend exact material state.

At minimum evaluate:

- Customer
- Company
- party account
- party/account currency
- payment amount
- bank amount
- Mode of Payment
- Bank Account/destination
- posting/reference dates
- reference number
- each invoice name
- each invoice docstatus
- each invoice modified/version
- each current outstanding
- each requested allocation
- each Payment Term row
- each due date
- reference exchange rate
- native discount/deduction summary
- received/paid amount
- total allocated
- unallocated amount
- difference amount

Do not fingerprint raw GL.

---

# 39. Stale-State Scenarios

Audit at least:

### Another payment submitted
```text
SINV-A outstanding 10,000
prepare allocates 10,000
another user pays 6,000
confirm old allocation
```

### One invoice cancelled

### Customer changed through amendment/new document linkage

### Payment Terms changed

### Exchange rate changes

### Mode of Payment default account changes

### Bank Account disabled/changed

### Invoice becomes fully paid

### A return/credit note changes outstanding

Determine:

- native stale validation;
- MCP fingerprint protection;
- whether confirm must fail entire receipt atomically.

Preferred safety expectation:

```text
any material reference drift → fail whole confirmation → new prepare
```

Verify and recommend.

---

# 40. Concurrency / Atomicity

Determine whether inserting a multi-reference Draft Payment Entry itself protects against concurrent outstanding changes.

Native latest-outstanding validation runs during Payment Entry validation, but Draft creation does not yet settle invoices.

Audit:

- race window at Draft insert;
- race window between Draft creation and later submit;
- native submit-time validation;
- possibility of two Draft PEs targeting same invoice;
- how submit detects over-allocation/stale outstanding.

This matters because Task 45/49 deliberately separate Draft creation from submit.

Recommend whether lifecycle submit preview/fresh validation is sufficient.

Do not invent custom database locks unless evidence requires them.

---

# 41. Draft vs Submit Semantics

Future confirm should likely insert Draft only, matching Task 45.

Audit if multi-reference Payment Entry requires any stronger submit-stage preview because:

- several invoices will be affected;
- partial balances differ;
- early discounts/deductions may occur;
- exchange differences may occur.

Recommend lifecycle preview fields.

---

# 42. Public Contract Options

Compare at least:

## Option A — explicit allocations

```text
prepare_customer_payment(
    customer,
    amount,
    references=[
        {sales_invoice, amount},
        ...
    ],
    mode_of_payment?,
    bank_account?,
    reference_no?,
    reference_date?,
    bank_amount?,
    remarks?
)
```

## Option B — payment amount + automatic oldest allocation

```text
prepare_customer_payment(
    customer,
    amount,
    allocation_strategy="oldest"
)
```

## Option C — invoices only, native auto-allocate

```text
prepare_customer_payment(
    customer,
    invoices=[...],
    amount
)
```

## Option D — generic Payment Entry references

Reject if it leaks accounting internals.

Evaluate:

- determinism
- user control
- LLM ambiguity
- ERPNext native support
- partial allocation
- payment terms
- stale-state clarity
- auditability

Recommend one narrow Task 49 contract.

---

# 43. Customer Input

Determine whether future public contract should require:

```text
customer
```

in addition to invoice references.

Options:

### Derive Customer from invoices
safer/minimal input.

### Require Customer and validate all invoices
more explicit intent.

Assess whether requiring Customer helps prevent accidental cross-party allocation.

Recommend exact contract.

---

# 44. Reference Selection

Determine whether public user must provide exact Sales Invoice names.

First implementation should likely require exact source identities rather than vague search terms.

Disambiguation/search belongs in agent orchestration/read tools, not the financial write contract.

Confirm this architecture.

---

# 45. Auto-Allocation Strategy

Do not automatically add oldest-invoice or due-date allocation merely because ERPNext has utilities for it.

Audit whether an explicit later capability could support:

```text
"Apply ₹30,000 to Arkee's oldest outstanding invoices"
```

For Task 49 decide whether to:

- require explicit invoice allocations;
- allow invoice list but native allocation;
- support one safe automatic strategy.

Prefer determinism over convenience in first financial multi-reference write.

---

# 46. Maximum Number of References

Multi-invoice input must be bounded.

Audit practical/native constraints and recommend an MCP maximum, such as:

```text
10
20
25
```

Do not accept unbounded invoice lists from the LLM.

Explain the chosen bound.

---

# 47. Data Minimization

Future preview should show only:

- Customer
- Company
- payment amount
- destination/mode
- currencies
- reference number/date
- each selected Sales Invoice:
  - name
  - posting/due date if relevant
  - current outstanding
  - requested/native allocated amount
  - payment term if relevant
- total allocated
- unallocated amount
- discount/deduction/exchange summary when material
- Draft/no-ledger-effect notice

Do not expose:

- all Customer invoices
- full Customer master
- Chart of Accounts
- raw GL
- raw Payment Ledger
- Bank Account numbers
- IBAN/SWIFT
- arbitrary custom fields
- unrelated invoices
- secrets
- tracebacks

---

# 48. Permissions

Audit exact native permission behavior for:

- Payment Entry create
- each Sales Invoice read/reference
- Bank Account / Account resolution
- Customer
- Mode of Payment

Future principle remains:

```text
permission-enforcing native Frappe/ERPNext API
    ↓
Frappe decides
    ↓
MCP translates exceptions
```

Do not create an MCP role matrix.

Do not perform the postponed cross-project permission refactor.

---

# 49. Accounts Profile

Multi-invoice receipt belongs in `accounts`.

Do not add it to Sales.

Sales/Purchase MCP processes must not need to be running.

Accounts can inspect permitted Sales Invoices directly from the same ERPNext site.

---

# 50. Direct / REST

Audit future direct and REST shape.

Task 49 must use:

- same authoritative service
- typed JSON-safe inputs
- fixed remote operation
- no arbitrary DocType
- no arbitrary method/import path
- no caller-selected site
- no caller-selected identity
- remote approval authority according to existing REST architecture

---

# 51. Interaction with Task 47 Read Tools

Use Task 47 only for orchestration/discovery.

Example:

```text
User:
"Arkee paid 30,000. Apply to their three oldest outstanding invoices."

Agent may:
1. search/query relevant invoices/outstanding candidates
2. present/disambiguate
3. call future exact allocation tool
```

But the financial write service must re-resolve native outstanding state independently.

Do not trust stale read-tool results as accounting authority.

---

# 52. Risk Classification

Classify:

```text
single invoice receipt
multi-invoice explicit allocation
multi-invoice auto-allocation
unallocated receipt
advance receipt
supplier multi-invoice payment
reconciliation
internal transfer
Journal Entry
```

Provide relative risk and recommended sequence.

---

# 53. Candidate Capability Matrix

Produce a table like:

| Capability | Native support | Risk | Decision | Reason |
|---|---|---:|---|---|
| explicit Customer multi-SI receipt | | | | |
| partial allocation per invoice | | | | |
| auto oldest allocation | | | | |
| unallocated remainder | | | | |
| cross-currency references | | | | |
| payment-term references | | | | |
| early discounts | | | | |
| customer advance | | | | |
| reconciliation | | | | |

This matrix must drive Task 49.

---

# 54. Required Audit Questions

The final report must answer directly:

1. What exact installed API retrieves outstanding Customer invoices?
2. What exact installed API builds/allocates Payment Entry references?
3. Is there a high-level native multi-invoice payment factory?
4. Should Task 49 start from `new_doc("Payment Entry")`, an existing factory, or another native helper?
5. Are all invoices required to share Customer?
6. Are all invoices required to share Company?
7. Are all invoices required to share party account?
8. Are all invoices required to share party-account currency?
9. Can mixed invoice currencies coexist?
10. What currency is `allocated_amount` expressed in?
11. Can the receipt amount exceed total allocations?
12. How is unallocated amount represented?
13. Should Task 49 allow unallocated remainder?
14. Can each invoice be partially allocated?
15. How are Payment Terms represented?
16. Must term-specific rows be selected explicitly?
17. How are early-payment discounts handled?
18. Can duplicate invoice reference rows exist?
19. What happens when one invoice becomes fully paid before confirm?
20. What happens when one invoice is cancelled before confirm?
21. Does native validation reject stale outstanding?
22. What additional fingerprint state is needed?
23. Should any material change fail the whole confirmation?
24. What happens between Draft creation and later submit if outstanding changes?
25. How does submit validate latest outstanding?
26. How does multi-reference Payment Entry affect Payment Ledger?
27. How does it affect GL?
28. Is Mode of Payment abstraction still sufficient?
29. Is Bank Account fallback still sufficient?
30. Is `bank_amount` needed?
31. Should posting date be public?
32. What maximum reference count should MCP allow?
33. Should Customer be caller input or derived?
34. Should explicit allocations be required?
35. Should auto-allocation be deferred?
36. What minimum preview is safe?
37. What exact Task 49 should implement?

---

# 55. Future Test Matrix

The audit must produce a Task 49 test plan covering at least:

## Core

- two invoices full allocation
- three invoices mixed full/partial allocation
- one invoice already fully paid
- one invoice cancelled
- duplicate invoice input
- allocation exceeds one invoice outstanding
- sum allocations exceeds payment
- payment exceeds allocations
- zero/negative allocation
- max-reference bound

## Party / company / accounts

- different Customers
- different Companies
- different receivable accounts
- different party currencies
- disabled account
- wrong bank Company

## Currency

- INR invoices / INR bank
- USD invoices / USD bank
- USD invoices / INR bank
- mixed invoice currency
- explicit bank amount
- exchange gain/loss

## Payment Terms

- no terms
- one term
- multiple terms
- partial term allocation
- early-payment discount
- changed term after prepare

## Approval

- prepare no write
- confirm Draft only
- one-shot
- expiry
- wrong user/site/action
- stale invoice outstanding
- one invoice changed
- changed bank/default
- concurrent confirm

## Lifecycle

- Draft insert
- submit
- all invoice outstanding updates
- partial outstanding
- cancel restores all references
- delete Draft/cancelled

## Permissions

- one reference unreadable
- Payment Entry create denied
- bank/account permission issue
- parent Customer mismatch

## Transport

- direct
- REST
- malformed payload
- identity/site boundary

## Regression

- Task 45 single-invoice payment
- Task 47 PE reads
- Sales/Purchase profiles
- approval
- lifecycle
- REST

---

# 56. Deliverable

Create exactly:

```text
docs/inspect/MULTI_INVOICE_CUSTOMER_RECEIPT_NATIVE_ALLOCATION_AUDIT.md
```

The report must contain:

1. Executive conclusion
2. Current Accounts baseline
3. Installed ERPNext version/source evidence
4. Multi-invoice business-flow diagram
5. Native outstanding retrieval API
6. Native reference/allocation API
7. High-level factory analysis
8. Same Customer rules
9. Same Company rules
10. Party-account compatibility
11. Currency compatibility
12. Allocation amount semantics
13. Receipt amount semantics
14. Partial allocation
15. Overpayment/unallocated behavior
16. Fully paid/cancelled/stale references
17. Duplicate reference behavior
18. Payment Terms
19. Early-payment discounts
20. Native reference construction options
21. Mode of Payment
22. Bank Account
23. Reference no/date
24. Posting date decision
25. Multi-currency/bank amount
26. Taxes/withholding
27. deductions/difference amount
28. advance boundary
29. reconciliation boundary
30. Payment Request boundary
31. Payment Ledger effects
32. GL effects
33. approval design
34. fingerprint recommendation
35. concurrency/stale-state analysis
36. Draft-vs-submit analysis
37. public contract decision matrix
38. Customer input decision
39. allocation strategy decision
40. maximum-reference recommendation
41. data-minimization policy
42. permission boundary
43. direct/REST design
44. risk classification
45. capability matrix
46. Task 49 test matrix
47. risks/limitations
48. exact Task 49 recommendation

---

# 57. Acceptance Criteria

Task 48 is complete only when:

1. no production code changes;
2. no accounting/site mutations;
3. current post-Task-47 repository inspected;
4. exact installed ERPNext source inspected;
5. outstanding retrieval API identified;
6. reference/allocation API identified;
7. high-level factory options compared;
8. Customer constraint established;
9. Company constraint established;
10. party-account constraints established;
11. currency semantics established;
12. allocation amount unit/currency established;
13. partial multi-invoice allocation traced;
14. overpayment/unallocated behavior traced;
15. fully paid/cancelled reference behavior traced;
16. duplicate reference behavior traced;
17. Payment Terms behavior traced;
18. early discount behavior traced;
19. native reference construction approach recommended;
20. stale-state/concurrency traced;
21. Draft/submit race implications documented;
22. Mode of Payment/Bank Account design confirmed or revised;
23. public contract options compared;
24. deterministic V1 allocation strategy recommended;
25. maximum reference bound recommended;
26. data minimization specified;
27. permissions/native authority documented;
28. direct/REST parity specified;
29. complete Task 49 test plan provided;
30. exact Task 49 implementation recommendation provided.

---

# 58. Expected Result

Task 48 should leave a clear future architecture such as:

```text
ACCOUNTS PROFILE

exact Customer / exact Sales Invoice allocation intent
        ↓
native outstanding/reference retrieval
        ↓
native Payment Entry Draft construction
        ↓
bounded multi-invoice preview
        ↓
approval
        ↓
fresh native outstanding rebuild
        ↓
fingerprint
        ↓
Draft Payment Entry
        ↓
generic lifecycle submit
        ↓
ERPNext updates each invoice outstanding
```

The exact public contract must come from installed-source evidence.

---

# 59. Limitations

Task 48 does not implement:

- multi-invoice payment
- auto-allocation
- customer advance
- standalone receipt
- supplier payment
- internal transfer
- Payment Request
- Payment Reconciliation
- Journal Entry
- write-off/bank-fee input
- raw deductions
- bank reconciliation
- payment gateway
- any new write tool

---

# 60. Exact Next Task

The audit must end with one concrete implementation task:

```text
Task 49 — <evidence-based Multi-Invoice Customer Receipt V1 title>
```

Task 49 should be the smallest safe multi-invoice vertical slice.

Preferred characteristics:

- Accounts profile only
- Customer Receive only
- exact Sales Invoice identities
- explicit bounded allocations
- native outstanding/reference APIs
- no raw accounting fields
- no arbitrary deductions/taxes
- no reconciliation
- no supplier payment
- prepare/approval/confirm
- fresh native rebuild
- Draft-only insert
- existing lifecycle submit/cancel/delete
- direct + REST parity

Do not implement Task 49 during Task 48.
