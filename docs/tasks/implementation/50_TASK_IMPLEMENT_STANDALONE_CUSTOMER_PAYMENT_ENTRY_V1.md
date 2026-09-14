# Task — Implement Standalone Customer Payment Entry V1

## 1. Objective

Implement a **standalone Customer receipt / advance Payment Entry** capability in the `mcp_erpnext` Accounts profile.

The new capability must allow creating a Draft ERPNext `Payment Entry` for money received from a Customer **without requiring any Sales Invoice, Sales Order, Delivery Note, or other source transaction**.

Required public MCP tools:

```text
prepare_customer_payment_entry
confirm_customer_payment_entry
```

The workflow must remain:

```text
prepare
    ↓
native ERPNext-derived preview
    ↓
explicit approval token
    ↓
confirm
    ↓
Draft Payment Entry
```

Submitting the Payment Entry remains a separate action through the existing generic lifecycle tools:

```text
prepare_document_submit
confirm_document_submit
```

Do not submit automatically.

---

# 2. Mandatory First Step — Inspect Existing Implementation

Before changing production code, inspect the current repository and confirm the existing patterns.

At minimum inspect:

```text
mcp_erpnext/profiles/accounts.py

mcp_erpnext/contracts/accounts/sales_invoice_payment.py
mcp_erpnext/contracts/accounts/multi_invoice_customer_receipt.py
mcp_erpnext/contracts/accounts/payment_entry_read.py

mcp_erpnext/services/accounts/sales_invoice_payment.py
mcp_erpnext/services/accounts/multi_invoice_customer_receipt.py
mcp_erpnext/services/accounts/payment_entry_read.py

mcp_erpnext/tools/accounts/sales_invoice_payment.py
mcp_erpnext/tools/accounts/multi_invoice_customer_receipt.py

mcp_erpnext/contracts/registry.py

mcp_erpnext/approvals.py
mcp_erpnext/services/common/fingerprint.py

mcp_erpnext/tests/test_accounts_sales_invoice_payment.py
mcp_erpnext/tests/test_payment_entry_read.py
mcp_erpnext/tests/test_profiles.py

docs/inspect/ACCOUNTS_PAYMENT_ENTRY_NATIVE_FLOW_AUDIT.md
docs/inspect/MULTI_INVOICE_CUSTOMER_RECEIPT_NATIVE_ALLOCATION_AUDIT.md
docs/inspect/MULTI_INVOICE_CUSTOMER_RECEIPT_IMPLEMENTATION_REPORT.md
docs/TOOLS.md
```

Also inspect the **installed/current ERPNext Payment Entry implementation** used by this environment, especially:

```text
erpnext.accounts.doctype.payment_entry.payment_entry.PaymentEntry
erpnext.accounts.party.get_party_account
```

Verify the behavior of:

```text
PaymentEntry.setup_party_account_field
PaymentEntry.set_missing_values
PaymentEntry.set_liability_account
PaymentEntry.set_exchange_rate
PaymentEntry.set_amounts
PaymentEntry.validate
```

Do not reimplement ERPNext accounting/defaulting rules in MCP code when ERPNext already owns them.

If the installed ERPNext version differs from assumptions in older audit documents, installed runtime behavior wins.

---

# 3. Confirmed Current Baseline

The Accounts profile currently contains:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment

prepare_multi_invoice_customer_receipt
confirm_multi_invoice_customer_receipt

get_payment_entry
query_payment_entries
aggregate_payment_entries

prepare_document_submit
confirm_document_submit

prepare_document_cancel
confirm_document_cancel

prepare_document_delete
confirm_document_delete
```

Current invoice payment tools must remain unchanged in public behavior.

Existing flows:

```text
Sales Invoice
    ↓
prepare_sales_invoice_payment
    ↓
Draft Payment Entry allocated to one invoice
```

and:

```text
2–20 Sales Invoices
    ↓
prepare_multi_invoice_customer_receipt
    ↓
Draft Payment Entry fully allocated across invoices
```

The new flow is different:

```text
Customer + Company + Amount
    ↓
prepare_customer_payment_entry
    ↓
Payment Entry
    references = []
    allocated amount = 0
    unallocated amount > 0
```

This represents a standalone Customer receipt / Customer advance.

---

# 4. Scope

Implement only:

```text
Payment Type = Receive
Party Type   = Customer
Source       = none
References   = none
Result       = Draft Payment Entry
```

The Payment Entry must be genuinely standalone.

It must NOT require:

```text
Sales Invoice
Sales Order
Delivery Note
Quotation
Payment Request
```

---

# 5. Explicitly Out of Scope

Do NOT implement in this task:

```text
Supplier payments / Payment Type = Pay
Internal Transfer

Sales Invoice allocation
multi-invoice allocation
Sales Order advance reference
Purchase Order advance reference

partial invoice + unallocated excess receipt

Payment Reconciliation
refund workflow

Payment Request

automatic submit

automatic cancel/delete

generic prepare_payment_entry covering every Payment Entry type
```

Also do not expand this task into supporting arbitrary:

```text
paid_from
paid_to
party_account
account currency
exchange-rate controls
deductions
tax rows
withholding rows
GL accounts
cost centers
accounting dimensions
```

through the public MCP contract.

Those are accounting implementation fields and must not become arbitrary LLM-controlled inputs.

---

# 6. New Public Contracts

Create an appropriate contract module, preferably:

```text
mcp_erpnext/contracts/accounts/customer_payment_entry.py
```

Use the project's existing `PublicContractModel`, typed `RootModel`, `ToolError`, and interaction conventions.

## Prepare Input

Target public contract:

```text
CustomerPaymentEntryPrepareInput
```

Business inputs:

```text
customer           required
company            required
amount             required, positive finite number

posting_date       optional
mode_of_payment    optional*
bank_account       optional*

reference_no       optional
reference_date     optional

bank_amount        optional, positive finite number
remarks            optional, max 1000
```

Destination rule:

```text
exactly one of:

mode_of_payment
bank_account
```

must be provided.

Do not allow both.

Do not allow neither.

Follow the existing destination strategy already used by:

```text
MultiInvoiceCustomerReceiptPrepareInput
```

and its service.

### Amount validation

Reject:

```text
0
negative values
NaN
Infinity
boolean values
```

Use the same bounded numeric approach already established in the multi-invoice receipt contract.

---

# 7. Public Contract Must NOT Accept Raw Accounting Fields

Inputs such as these must be rejected as extra fields:

```text
payment_type
party_type
paid_from
paid_to
paid_from_account_currency
paid_to_account_currency
party_account
source_exchange_rate
target_exchange_rate
total_allocated_amount
unallocated_amount
difference_amount
references
deductions
taxes
docstatus
```

The LLM/client specifies business intent.

ERPNext determines accounting implementation.

---

# 8. Customer and Company Behavior

This is a source-free Payment Entry, so unlike invoice-linked payment flows there is no Sales Invoice from which Company/account details can be derived.

Therefore:

```text
customer = explicit
company  = explicit
```

Do not hardcode either.

Do not use:

```text
shayona.localhost
Shayona Technology
any fixed Customer
any fixed Company
```

The configured/current Frappe site must continue to be used naturally by the runtime.

Validate that the Customer exists and the authenticated user has appropriate read access.

Payment Entry create permission must also be enforced.

Use Frappe/ERPNext permission APIs rather than bypassing permissions.

---

# 9. Native Party Account Resolution

This is important.

Do NOT manually reproduce Customer receivable-account selection rules.

ERPNext Payment Entry already uses native party account/defaulting behavior.

The implementation must allow ERPNext to resolve the correct party account based on:

```text
Customer
Company
party configuration
Customer Group
Company defaults
existing party/account currency rules
```

Also respect ERPNext's native configuration for advance payments, including configurations where an advance is booked through a separate advance/liability account.

Do not assume:

```text
paid_from == Company's default receivable account
```

and do not hardcode that account.

The final preview must represent what the **native Payment Entry controller actually derived**.

---

# 10. Destination Resolution

Reuse the sound existing strategy in:

```text
services/accounts/multi_invoice_customer_receipt.py
```

for:

```text
Mode of Payment
OR
Bank Account
```

Do not duplicate that logic unnecessarily.

A small internal helper extraction is allowed only if:

1. existing behavior is preserved;
2. existing tests continue to pass;
3. both multi-invoice and standalone flows benefit from exactly the same semantics;
4. the refactor remains Accounts-internal.

Do NOT perform a broad refactor merely for cleanliness.

### Mode of Payment

ERPNext should determine the Company's usable Bank/Cash ledger through its native helper/default configuration.

### Bank Account

Validate the selected `Bank Account` and its Company-linked ledger using the existing pattern.

Do not expose the resulting raw ledger account in the public tool input.

---

# 11. Reference Number / Reference Date

Preserve the existing Payment Entry rule already implemented in the Accounts service.

If the resolved destination is a Bank account and native/current behavior requires transaction evidence:

```text
reference_no
reference_date
```

must be present.

Return a bounded error such as the existing:

```text
TRANSACTION_REFERENCE_REQUIRED
```

Do not invent a new conflicting rule if the existing implementation already handles this correctly.

Cash-like destinations must not be forced to provide bank references unless ERPNext itself requires them.

---

# 12. Multi-Currency Handling

Reuse the existing safe policy.

If the Customer/party-account currency and destination-account currency differ, the MCP must not silently guess the actual destination amount.

Require:

```text
bank_amount
```

where required by the existing/native multi-currency strategy.

Do not implement custom exchange-rate mathematics.

Let ERPNext derive/validate exchange rates and resulting amounts.

The preview must expose native resulting values, not MCP-computed approximations.

---

# 13. Native Payment Entry Construction

Create the document through:

```python
frappe.new_doc("Payment Entry")
```

Conceptually the business intent is:

```text
company
payment_type = "Receive"
party_type   = "Customer"
party        = customer
posting_date

destination account derived from Mode of Payment / Bank Account

paid_amount
received_amount

mode_of_payment / bank_account
reference_no
reference_date
remarks
```

Do NOT append Sales Invoice references.

Expected:

```text
references = []
```

Do not manually fabricate invoice/order references merely to make ERPNext validation pass.

Allow the native `PaymentEntry` controller to populate/validate:

```text
party account
account currencies
exchange rates
amounts
unallocated amount
difference amount
advance-account behavior
```

Use native controller methods according to the installed ERPNext implementation.

Do not copy ERPNext controller logic into `mcp_erpnext`.

---

# 14. Required Standalone State

After native preparation/validation, verify the operation still represents the intended bounded capability.

It must remain:

```text
payment_type = Receive
party_type   = Customer
party        = requested Customer

references              = []
total_allocated_amount  = 0
```

There must be a native unallocated Customer receipt amount.

Do not force the value through custom arithmetic if ERPNext already provides it.

Return the native resulting:

```text
unallocated_amount
```

in the preview.

---

# 15. Unexpected Native States

Do not silently discard or rewrite unexpected accounting state.

For V1, if native preparation creates a state currently outside this capability, return a bounded error rather than proceeding incorrectly.

Examples include unexpected:

```text
invoice/order references
deductions
tax withholding
advance tax rows / taxes requiring unsupported handling
non-zero difference that cannot safely be represented
```

First inspect installed ERPNext behavior before deciding exact checks.

Do NOT globally block a valid native configuration merely because older code made a simplifying assumption.

Document any intentionally unsupported native state in the implementation report.

---

# 16. Preview Contract

Create a bounded preview such as:

```text
CustomerPaymentEntryPreview
```

Include business-relevant information only.

Expected shape:

```text
doctype: "Payment Entry"
docstatus: 0

customer
company
payment_type: "Receive"

posting_date

reference_no
reference_date

destination_kind
destination

party_account_currency
destination_account_currency

paid_amount
received_amount

source_exchange_rate
target_exchange_rate

references: []

total_allocated_amount
unallocated_amount
difference_amount

remarks

note
```

The note should make clear:

```text
Draft only.
No ledger posting occurs until the Payment Entry is separately submitted.
```

Do NOT expose internal raw account names merely because they exist on the Frappe document unless they are genuinely required for user review.

Follow the bounded-output philosophy already used by the Accounts tools.

---

# 17. Prepare Result

Expected state:

```text
status = "ready"
approval_token
expires_in_seconds
preview
interaction = approval directive
```

The `approval_token` remains an opaque pending-operation handle.

It is not itself proof of user approval.

Use the current shared approval store and current approval policy.

Do not introduce a second approval mechanism.

---

# 18. Approval / Fingerprint Safety

Follow the current established pattern.

Prepare:

```text
approvals.prune_expired()

build fresh native Payment Entry
produce preview

stable fingerprint

approvals.create(...)
```

Fingerprint material must be sufficient to detect meaningful changes between prepare and confirm.

At minimum account for:

```text
normalized request
native preview
Customer identity/state needed for correctness
Company-sensitive derived state
resolved destination identity
resolved destination ledger internally
party-account derived state internally
currencies
native amounts
```

Raw account information may exist in fingerprint material internally even when it is intentionally omitted from the public preview.

The fingerprint is internal safety state, not business output.

---

# 19. Confirm Behavior

Create:

```text
CustomerPaymentEntryConfirmInput
```

with only:

```text
approval_token
confirm
```

No mutable business fields may be accepted during confirmation.

Flow:

```text
confirm = false
    ↓
cancel pending approval
    ↓
CONFIRMATION_REQUIRED / established project result
```

For `confirm = true`:

```text
claim approval
    ↓
rebuild Payment Entry from approved request
    ↓
re-run native current validation/defaulting
    ↓
rebuild preview/fingerprint
    ↓
compare with approved fingerprint
```

If state differs:

```text
STALE_CONFIRMATION
```

and do not insert anything.

Only after a successful comparison:

```python
doc.insert(
    ignore_permissions=False,
    ignore_links=False,
    ignore_mandatory=False,
)
```

Then commit using the existing project pattern.

On failure:

```text
rollback
bounded ToolError
```

Do not expose raw traceback/database/internal account data to the LLM.

---

# 20. Draft Only

Successful confirmation must create:

```text
Payment Entry
docstatus = 0
```

It must NOT call:

```python
doc.submit()
```

It must NOT create ledger effect intentionally through this tool.

Submission remains:

```text
prepare_document_submit
confirm_document_submit
```

This preserves the existing architecture:

```text
create Draft
    ↓
review
    ↓
separate lifecycle submit approval
```

---

# 21. Created Result Contract

Create a bounded result such as:

```text
CustomerPaymentEntryCreated
```

Suggested output:

```text
status: "created"
doctype: "Payment Entry"
payment_entry
docstatus: 0

customer
company
payment_type: "Receive"

paid_amount
unallocated_amount

idempotent
```

Do not dump the complete Payment Entry document.

Do not expose GL/account internals unnecessarily.

---

# 22. Tool Wrappers

Prefer a new file:

```text
mcp_erpnext/tools/accounts/customer_payment_entry.py
```

Register:

```text
prepare_customer_payment_entry
confirm_customer_payment_entry
```

Use:

```text
execute_tool_with_context
TypeAdapter
typed RootModel outputs
tool_meta(...)
structured_output=True
```

exactly according to current project conventions.

Suggested tool descriptions:

```text
prepare_customer_payment_entry
Prepare a native standalone Draft Customer Payment Entry with no invoice allocation.
```

```text
confirm_customer_payment_entry
Create the reviewed standalone Draft Customer Payment Entry.
```

Descriptions must be clear enough that an LLM can distinguish:

```text
single invoice payment
multi-invoice receipt
standalone customer receipt
```

---

# 23. Contract Registry

Update:

```text
mcp_erpnext/contracts/registry.py
```

Register both tools with the correct:

```text
Domain = Accounts

prepare:
    ToolOperation.PREPARE
    PREPARE side effect
    APPROVAL interaction
    approval_confirm_tool="confirm_customer_payment_entry"

confirm:
    ToolOperation.CONFIRM
    CONFIRM_WRITE side effect
```

Follow the exact current registry structure.

Do not introduce a parallel registration mechanism.

---

# 24. Accounts Profile Registration

Update:

```text
mcp_erpnext/profiles/accounts.py
```

Register the new standalone Customer Payment Entry tools.

Keep Accounts independent of the Sales profile.

After implementation, Accounts should expose:

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

prepare_document_submit
confirm_document_submit

prepare_document_cancel
confirm_document_cancel

prepare_document_delete
confirm_document_delete
```

Total expected public tools:

```text
15
```

Do not add Customer/Item/Sales tools to Accounts merely to support this feature.

---

# 25. Existing Flows Must Not Change

These existing capabilities must remain behaviorally intact:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment

prepare_multi_invoice_customer_receipt
confirm_multi_invoice_customer_receipt

get_payment_entry
query_payment_entries
aggregate_payment_entries

generic lifecycle tools
```

In particular, do NOT change:

```text
single-invoice flow → allowing advances
multi-invoice flow → allowing unallocated remainder
```

Those tools have narrow contracts intentionally.

Standalone receipt gets its own explicit capability.

---

# 26. Required Tests

Add dedicated tests, preferably:

```text
mcp_erpnext/tests/test_customer_payment_entry.py
```

## Contract tests

Verify:

### Valid

```text
customer
company
positive amount
mode_of_payment
```

works.

Also test the Bank Account alternative.

### Reject zero

```text
amount = 0
```

### Reject negative

```text
amount < 0
```

### Reject boolean

```text
amount = true
```

### Reject NaN / Infinity

where applicable.

### Reject both destinations

```text
mode_of_payment + bank_account
```

### Reject no destination

neither provided.

### Reject raw fields

Examples:

```text
paid_from
paid_to
party_account
references
payment_type
```

### Confirm input

Must reject extra business fields such as:

```text
amount
customer
company
```

Confirm should contain only:

```text
approval_token
confirm
```

---

# 27. Service Tests

Cover at least:

### Successful preparation

Given valid:

```text
Customer
Company
amount
Mode of Payment
```

returns:

```text
status = ready
Payment Type = Receive
references = []
total_allocated_amount = 0
unallocated_amount > 0
docstatus = 0
```

### Bank destination

Correctly resolves valid configured Bank Account.

### Missing bank evidence

Bank destination requiring reference evidence rejects missing:

```text
reference_no/reference_date
```

using a bounded error.

### Customer not found

Returns bounded error.

### Permission denied

No permission bypass.

### Native validation failure

Returns bounded external error without leaking traceback/account internals.

### Multi-currency

Requires `bank_amount` according to the established policy when destination/party currencies differ.

### Prepare has no Payment Entry insert

Preparation must not create a Payment Entry document.

### Confirm false

Does not create a document.

### Successful confirm

Creates exactly one:

```text
Payment Entry
docstatus = 0
```

with no invoice/order references.

### Stale confirmation

If relevant derived state changes between prepare and confirm:

```text
STALE_CONFIRMATION
```

and no document is created.

### Replay / consumed approval

Must follow current shared approval-store semantics and not create a duplicate Payment Entry.

---

# 28. Profile Tests

Update:

```text
mcp_erpnext/tests/test_profiles.py
```

The Accounts inventory must include exactly the new pair in the intended deterministic order.

Run:

```text
audit_tool_contracts(...)
```

and require:

```text
[]
```

No schema/registry/profile mismatch is acceptable.

Also verify:

```text
Sales profile unchanged
Purchase profile unchanged
```

unless an unrelated pre-existing test requires maintenance.

Do not add these tools to Sales or Purchase.

---

# 29. Generic Lifecycle Verification

Verify that after standalone Payment Entry Draft creation, the existing Accounts lifecycle allowlist permits:

```text
prepare_document_submit
confirm_document_submit
```

for `Payment Entry`.

Do not create Payment Entry-specific submit tools.

If Payment Entry is already allowed, make no lifecycle production change.

Only change lifecycle configuration if inspection proves the new Draft cannot use the already-intended Accounts lifecycle behavior.

---

# 30. Documentation

Update:

```text
docs/TOOLS.md
```

with the two new tools and their bounded contracts.

Update other existing profile documentation only where it already maintains an explicit Accounts tool inventory.

Do not rewrite unrelated documentation.

Also create:

```text
docs/inspect/STANDALONE_CUSTOMER_PAYMENT_ENTRY_IMPLEMENTATION_REPORT.md
```

The report must contain:

```text
1. inspected existing implementation
2. inspected ERPNext native behavior
3. files changed
4. public input contract
5. public output contract
6. native APIs/methods reused
7. account/defaulting behavior
8. approval/fingerprint behavior
9. unsupported V1 cases
10. tests executed
11. test results
12. remaining limitations
```

---

# 31. Security / Data Exposure Requirements

The LLM must receive only the business information needed to use the tool.

Do not expose:

```text
full Customer document
full Company document
full Account records
all Bank Account data
all Mode of Payment configuration
raw Payment Entry JSON
permission internals
SQL
tracebacks
server filesystem paths
credentials
shared secrets
```

Errors must stay bounded.

The user should receive enough information to answer:

```text
Who paid?
Which Company received it?
How much?
Where/how was it received?
How much is unallocated?
What Draft Payment Entry will be created?
```

Nothing more should be exposed without a concrete business need.

---

# 32. Important Native-Authority Rule

ERPNext remains the accounting authority.

The MCP server owns:

```text
business-intent contract
permission boundary
bounded capability
preview
approval
stale-state protection
safe output
```

ERPNext owns:

```text
party account selection
advance-account behavior
account currencies
exchange rates
Payment Entry validation
amount calculation
accounting correctness
ledger behavior on submit
```

Do not duplicate native accounting rules merely to make the MCP service self-contained.

---

# 33. Allowed Changes

Allowed:

```text
new Accounts contract
new Accounts service
new Accounts tool wrapper
contract registry registration
Accounts profile registration
focused tests
focused documentation
implementation report
```

A small reusable Accounts-internal helper extraction is allowed only when existing duplicate logic is exactly equivalent and tests protect both callers.

---

# 34. Changes Not Allowed

Do not:

```text
rewrite Payment Entry read/query/aggregate
rewrite existing invoice payment workflow
rewrite multi-invoice receipt workflow
modify Sales profile behavior
modify Purchase profile behavior
add Supplier Payment Entry
add Internal Transfer
add Payment Reconciliation
add Sales Order allocation
add invoice allocation to standalone tool
add automatic submit
add arbitrary accounting fields
hardcode site/company/customer/accounts
bypass Frappe permissions
copy ERPNext business logic
perform broad architecture refactor
```

---

# 35. Acceptance Criteria

Task is complete only when all of the following are true.

### AC-01

Accounts profile exposes:

```text
prepare_customer_payment_entry
confirm_customer_payment_entry
```

### AC-02

`prepare_customer_payment_entry` requires no Sales Invoice or other source transaction.

### AC-03

Input contains bounded business intent only.

### AC-04

Exactly one destination is accepted:

```text
mode_of_payment
OR
bank_account
```

### AC-05

ERPNext-native logic determines the Customer/advance party account.

### AC-06

Native Company configuration for advance-account behavior is respected.

### AC-07

Prepared Payment Entry has:

```text
Payment Type = Receive
Party Type = Customer
references = []
allocated amount = 0
```

### AC-08

Preview reports the native unallocated amount.

### AC-09

Prepare does not insert a Payment Entry.

### AC-10

Confirmation requires the existing trusted approval mechanism.

### AC-11

Confirm rebuilds and stale-checks the operation before writing.

### AC-12

Successful confirm creates only:

```text
Draft Payment Entry
docstatus = 0
```

### AC-13

No automatic submit occurs.

### AC-14

Existing lifecycle submit flow works for the created Payment Entry.

### AC-15

Single-invoice and multi-invoice payment behavior remains unchanged.

### AC-16

Raw accounting fields are not accepted from the LLM.

### AC-17

No permission bypass is introduced.

### AC-18

Accounts profile contract audit returns no errors.

### AC-19

Existing test suite remains green.

### AC-20

Implementation report clearly documents native behavior and remaining limitations.

---

# 36. Example MCP Usage

## Prepare

Business intent:

```text
Receive ₹10,000 from customer Arkee Foods
for company Shayona Technology
using Bank Transfer
reference UTR-10001
dated today.
This is an advance; there is no invoice yet.
```

Conceptual request:

```json
{
  "customer": "Arkee Foods",
  "company": "Shayona Technology",
  "amount": 10000,
  "mode_of_payment": "Bank Transfer",
  "reference_no": "UTR-10001",
  "reference_date": "2026-09-14"
}
```

Expected:

```text
status: ready

Payment Entry
Payment Type: Receive
Customer: Arkee Foods
Company: Shayona Technology

Paid Amount: 10000
Allocated Amount: 0
Unallocated Amount: native ERPNext value

References: []

Draft only
```

Then user approval.

## Confirm

```json
{
  "approval_token": "<opaque-token>",
  "confirm": true
}
```

Expected:

```text
status: created
doctype: Payment Entry
docstatus: 0
payment_entry: <generated name>
```

No ledger effect yet.

---

# 37. Test Commands

Use the repository's existing supported test method.

At minimum run the focused tests covering:

```text
customer Payment Entry contracts/service
existing Sales Invoice payment
existing multi-invoice receipt
Payment Entry read/query/aggregate
profile inventory
tool-contract audit
approval/fingerprint behavior
```

Then run the broader existing automated test suite if available in the current environment.

Do not claim tests passed unless they were actually executed.

---

# 38. Expected Final Result

After this task, Accounts Payment Entry coverage should conceptually be:

```text
Customer Payment Entry
│
├── One submitted Sales Invoice
│   ├── prepare_sales_invoice_payment
│   └── confirm_sales_invoice_payment
│
├── Multiple submitted Sales Invoices
│   ├── prepare_multi_invoice_customer_receipt
│   └── confirm_multi_invoice_customer_receipt
│
├── Standalone / Unallocated Customer Receipt
│   ├── prepare_customer_payment_entry
│   └── confirm_customer_payment_entry
│
├── Read
│   ├── get_payment_entry
│   ├── query_payment_entries
│   └── aggregate_payment_entries
│
└── Lifecycle
    ├── submit
    ├── cancel
    └── delete
```

All three Customer receipt creation paths remain explicit and purpose-specific.

---

# 39. Limitations After This Task

Still intentionally unsupported:

```text
Supplier payment
Supplier advance
Internal Transfer
Sales Order-linked advance
Purchase Order-linked advance
mixed allocated + unallocated receipt
Payment Reconciliation
refund
advanced deductions/tax workflows unless proven automatically safe
```

These are separate future capabilities and must not be smuggled into this implementation.

---

# 40. Exact Next Task

After implementation passes tests, the next task is:

```text
Live Standalone Customer Payment Entry Verification
```

Verify end-to-end through the actual authenticated MCP runtime:

```text
prepare_customer_payment_entry
    ↓
review preview
    ↓
confirm_customer_payment_entry
    ↓
get_payment_entry
    ↓
prepare_document_submit
    ↓
confirm_document_submit
    ↓
verify submitted Payment Entry / unallocated Customer advance
```

Use a safe test Customer/Company and test amount.

Do not start Supplier Payment Entry or Internal Transfer implementation until this standalone Customer receipt path has passed live verification.