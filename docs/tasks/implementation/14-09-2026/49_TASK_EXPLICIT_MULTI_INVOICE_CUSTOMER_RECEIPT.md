# Task 49 — Accounts V1: Explicit Multi-Invoice Customer Receipt as Draft

## Status

**Implementation task**

This task follows:

- Task 48 — Multi-Invoice Customer Receipt Native Allocation Audit

The audit established that ERPNext v16.34.2 supports multiple invoice references on one Payment Entry, but there is no installed high-level native factory for an explicit multi-invoice customer receipt.

The safe implementation must therefore use:

```text
exact Customer
+ 2–20 exact submitted Sales Invoice names
+ explicit positive allocation for each
+ one receipt destination
        ↓
native Payment-Ledger-backed outstanding retrieval
        ↓
native-derived Payment Entry header/reference rows
        ↓
bounded Draft preview
        ↓
shared approval
        ↓
fresh complete rebuild + fingerprint
        ↓
Draft Payment Entry insert only
        ↓
existing generic lifecycle submit later
```

This is **not** a generic Payment Entry builder.

---

# 1. Objective

Implement an Accounts-only business capability that records one Customer receipt and explicitly allocates it across multiple submitted Sales Invoices.

Public tools:

```text
prepare_multi_invoice_customer_receipt
confirm_multi_invoice_customer_receipt
```

The first V1 must:

- require one explicit Customer;
- require 2–20 unique exact Sales Invoice names;
- require one positive explicit allocation per invoice;
- require all selected invoices to share:
  - Customer
  - Company
  - effective receivable account
  - receivable/party account currency
  - invoice transaction currency for V1
- require receipt amount to equal total explicit allocations at native currency precision;
- reject unallocated remainder;
- reject returns/negative outstanding references;
- reject enabled payment-term allocation;
- reject currently eligible early-payment discount cases;
- reject caller-configured taxes/withholding/deductions;
- allow one destination using either:
  - Mode of Payment, or
  - Bank Account;
- support optional `bank_amount` for supported cross-currency bank settlement;
- support optional posting date;
- prepare without writing;
- confirm with shared atomic approval and fresh complete rebuild;
- insert Draft Payment Entry only;
- reuse generic Payment Entry lifecycle for later submit/cancel/delete;
- enrich Payment Entry submit approval so multi-reference financial impact is reviewable and stale-state safe;
- support direct and fixed REST backends.

---

# 2. Critical Native Authority

Do not invent an MCP outstanding/allocation engine.

Use installed ERPNext native building blocks identified by Task 48.

## 2.1 Native outstanding retrieval

Use:

```python
erpnext.accounts.doctype.payment_entry.payment_entry.get_outstanding_reference_documents(
    args,
    validate=False,
)
```

with server-owned arguments constrained to the selected Customer/Company/party account and exact selected Sales Invoice vouchers.

The installed native implementation delegates invoice outstanding to Payment-Ledger-backed:

```python
erpnext.accounts.utils.get_outstanding_invoices(...)
```

or its installed equivalent.

## 2.2 Native reference refresh/validation

Use native Payment Entry behavior including:

```text
PaymentEntry.set_missing_ref_details()
PaymentEntry.validate()
PaymentEntry.validate_allocated_amount_with_latest_data()
```

through normal document validation/insert behavior.

Do not manually recreate their accounting rules.

## 2.3 Native auto-allocation

Do NOT use:

```text
PaymentEntry.allocate_amount_to_references()
```

for Task 49.

The user is explicitly approving exact allocations. Native sequential auto-allocation would overwrite that intent and introduce ordering policy.

Auto-allocation remains deferred.

---

# 3. Construction Strategy

Task 48 selected:

```python
frappe.new_doc("Payment Entry")
```

plus native-derived header/default/reference state.

Do not start from:

```python
get_payment_entry("Sales Invoice", first_invoice, ...)
```

because the single-source factory allows the first invoice to control project, Mode of Payment, terms, discounts, contact/default state without a valid rule for why that invoice is privileged.

Do not use Payment Reconciliation internals.

Do not manually build GL or Payment Ledger rows.

---

# 4. Scope

## In scope

Implement:

1. `prepare_multi_invoice_customer_receipt`
2. `confirm_multi_invoice_customer_receipt`
3. typed public contracts
4. explicit allocation child contract
5. exact Customer validation
6. 2–20 unique exact Sales Invoice validation
7. per-invoice read permission
8. native Payment-Ledger outstanding retrieval
9. common Customer/Company/effective-account/currency invariants
10. explicit positive per-invoice allocations
11. exact receipt-total equality policy
12. native Payment Entry Draft construction
13. native reference refresh/validation
14. same-currency receipt support
15. supported cross-currency destination support with optional `bank_amount`
16. mutually exclusive Mode of Payment / Bank Account
17. reference number/date handling
18. optional posting date resolved/frozen at prepare
19. bounded remarks
20. shared ApprovalStore
21. atomic `claim_for_confirm_write()`
22. fresh complete rebuild
23. deterministic canonical fingerprint
24. Draft-only normal-permission insert
25. multi-reference Payment Entry submit-preview/fingerprint enrichment
26. direct backend support
27. fixed typed REST operations
28. Accounts-only registry/profile/catalog updates
29. focused tests
30. live authorized test-site verification
31. implementation report

## Explicitly out of scope

Do NOT implement:

- generic Payment Entry creation
- one-invoice Task 45 rewrite
- auto oldest-invoice allocation
- native ordered auto-allocation
- invoice-list-without-explicit-allocation mode
- unallocated receipt
- customer advance
- Sales Order advance
- mixed Customer receipt
- cross-company receipt
- mixed effective receivable accounts
- mixed party-account currencies
- mixed invoice transaction currencies
- payment-term-specific allocation
- early-payment discount composition
- return/credit-note allocation
- negative allocation
- zero allocation
- supplier payment
- Purchase Invoice Pay flow
- Internal Transfer
- Payment Request creation
- Payment Reconciliation
- unreconciliation
- arbitrary taxes
- caller-configurable withholding
- arbitrary deduction rows
- caller-configurable write-off/bank-fee accounts
- caller exchange-rate input
- raw ledger account input
- Journal Entry
- GL writes
- Payment Ledger writes
- Payment Entry update
- reconciliation of existing submitted payments
- PDF/email changes
- Payment Entry read/query/aggregate changes except regression compatibility
- global permission refactor

---

# 5. Public Allocation Contract

Add a typed child model conceptually equivalent to:

```python
class CustomerReceiptAllocation(PublicContractModel):
    sales_invoice: NonEmptyString
    allocated_amount: PositiveFiniteAmount
```

Rules:

- exact Sales Invoice name required;
- `allocated_amount > 0`;
- boolean must not coerce to number;
- NaN/infinite rejected;
- one row per Sales Invoice;
- no duplicate invoice names;
- no arbitrary reference doctype;
- no Payment Term;
- no account;
- no currency override;
- no exchange-rate override.

The amount is explicitly:

```text
positive amount in the shared receivable / party-account currency
```

Preview must display this currency next to every allocation.

---

# 6. Prepare Public Contract

Add:

```text
prepare_multi_invoice_customer_receipt
```

Recommended input:

```python
customer: str
amount: positive finite number
allocations: list[CustomerReceiptAllocation]  # min 2, max 20

mode_of_payment: str | None = None
bank_account: str | None = None

reference_no: str | None = None
reference_date: date | None = None
posting_date: date | None = None

bank_amount: positive finite number | None = None
remarks: bounded string | None = None
```

Use `PublicContractModel(extra="forbid")` or the current equivalent.

---

# 7. Required Inputs

## 7.1 `customer`

Required.

Do not silently derive the public Customer intent from the first invoice.

Every selected Sales Invoice must match this exact Customer.

The explicit Customer is part of:

- reviewed intent;
- validation;
- approval payload;
- fingerprint.

## 7.2 `amount`

Required.

Meaning:

```text
party-side receipt amount in the shared receivable-account currency
```

Must equal total explicit allocations at native currency precision.

## 7.3 `allocations`

Required.

Rules:

```text
minimum: 2
maximum: 20
unique Sales Invoice names
every amount > 0
```

One selected invoice = use existing Task 45 single-invoice capability instead.

21+ invoices = reject with bounded policy error; bulk/reconciliation workflows are a separate design.

---

# 8. Optional Inputs

## `mode_of_payment`

Business-level destination.

Mutually exclusive with `bank_account`.

Use native Company/Mode-of-Payment default account resolution.

Do not invent fallback account selection.

## `bank_account`

Explicit Bank Account fallback.

Mutually exclusive with `mode_of_payment`.

Load with permission, validate Company, resolve native ledger Account, and let normal Account validation establish enabled/type/currency validity.

Do not expose bank account number/IBAN/SWIFT.

## `reference_no`

Transaction/bank reference.

Do not fabricate.

## `reference_date`

Transaction reference date.

Do not fabricate.

Must be included in fingerprint.

## `posting_date`

Optional.

If omitted:

```text
resolve to native current date at prepare
```

Then freeze the resolved date in approval payload/fingerprint.

Confirm must reuse the approved resolved date.

Do not recalculate to a newer "today".

## `bank_amount`

Optional.

Meaning:

```text
received amount in destination account currency
```

Use only where destination currency differs and native calculations require it.

No exchange-rate input may be public.

## `remarks`

Optional, maximum 1,000 characters.

Never parse remarks as accounting instructions.

Preserve using the correct native `custom_remarks` semantics if necessary so validation does not unexpectedly overwrite approved text.

---

# 9. Forbidden Public Inputs

Do not expose:

```text
company
party_type
payment_type
party_account
paid_from
paid_to
account currency
source exchange rate
target exchange rate
reference exchange rate
allocated total
unallocated amount
difference amount
payment terms
payment request
deductions
taxes
withholding
write-off account
bank-fee account
cost center
project
accounting dimensions
advance account
reference doctype
raw reference rows
GL entries
Payment Ledger rows
ignore_permissions
site
user
identity
arbitrary DocType
arbitrary import/method path
```

---

# 10. Prepare Flow — High Level

Prepare must perform:

```text
validate public shape
        ↓
load explicit Customer with normal permission
        ↓
load every selected Sales Invoice with normal read permission
        ↓
validate common invariants
        ↓
derive Company / effective party account / currencies
        ↓
retrieve native Payment-Ledger outstanding for exact selected invoices
        ↓
verify every selected invoice is present and eligible
        ↓
build unsaved native Payment Entry
        ↓
populate exact native reference rows
        ↓
replace only allocation values with approved explicit allocations
        ↓
resolve destination / dates / receipt amounts
        ↓
run native missing-reference/default/amount calculations
        ↓
apply V1 safety exclusions
        ↓
bounded preview
        ↓
fingerprint
        ↓
shared approval
```

Prepare writes nothing.

---

# 11. Per-Source Permission Boundary

Task 48 found the native outstanding retrieval API checks party permission but is not sufficient as proof of per-invoice read permission.

Therefore before treating any selected invoice as usable:

```text
load exact Sales Invoice
→ enforce native/Frappe read permission
```

for every requested invoice.

If one invoice is unreadable, fail the **whole request**.

Do not:

- return allocations for the readable subset;
- reveal which other invoices are valid beyond the exact requested identities;
- use generic `outstanding_amount` as fallback authority.

Do not add an MCP role matrix.

---

# 12. Source Sales Invoice Eligibility

Every selected Sales Invoice must be:

- exact requested name;
- readable;
- Submitted;
- non-return for V1;
- positive outstanding;
- present in fresh native Payment-Ledger outstanding retrieval;
- same explicit Customer;
- same Company;
- same effective receivable account;
- same party-account currency;
- same invoice transaction currency for V1;
- not payment-term allocation-enabled for V1;
- not currently eligible for early-payment discount for V1.

Any one invalid invoice fails the entire prepare.

No partial-success Payment Entry.

---

# 13. Common Customer

Require:

```text
invoice.customer == request.customer
```

for every selected source.

Also preserve native `PaymentEntry.validate_reference_documents()` as final authority.

Do not rely only on the MCP fail-fast check.

---

# 14. Common Company

Derive Company from sources.

All invoices must share exactly one Company.

Do not accept Company from caller.

Cross-company receipt is invalid for Task 49.

---

# 15. Effective Receivable Account

For each Sales Invoice determine the effective native party/receivable account according to installed ERPNext rules, including invoice-discounting behavior where applicable.

All selected invoices must share exactly one effective receivable account.

Reject even if:

```text
account A and account B have the same currency
```

One Customer Payment Entry has one party account.

This account is server/native derived, never LLM-selected.

---

# 16. Party-Account Currency

All invoices must share the same effective party-account currency.

This currency defines:

```text
request.amount
allocation.allocated_amount
total_allocated_amount
unallocated_amount
```

for Task 49.

Show the currency explicitly in preview.

---

# 17. Invoice Transaction Currency

Task 49 V1 must also require the selected invoices to share one transaction currency.

Even though lower-level ERPNext primitives may support some mixed transaction-currency combinations through one party account, Task 48 deliberately deferred them for review clarity and FX risk.

Return a bounded error such as:

```text
MIXED_INVOICE_CURRENCY_UNSUPPORTED
```

or current equivalent.

No FX normalization.

---

# 18. Native Outstanding Retrieval

Build server-owned arguments for:

```python
get_outstanding_reference_documents(...)
```

constrained conceptually to:

```python
{
    "company": common_company,
    "party_type": "Customer",
    "payment_type": "Receive",
    "party": explicit_customer,
    "party_account": common_receivable_account,
    "get_outstanding_invoices": True,
    "get_orders_to_be_billed": False,
    "vouchers": [
        {"voucher_type": "Sales Invoice", "voucher_no": exact_name},
        ...
    ],
    "book_advance_payments_in_separate_party_account": native_company_policy,
    ...
}
```

Use the exact installed function contract.

Do not expose this argument object publicly.

Do not use generic date/outstanding-range filters when exact vouchers were supplied unless native API requires internal fields.

---

# 19. Selected Invoice Must Exist in Native Outstanding Results

For every requested Sales Invoice, there must be a matching positive native outstanding row.

Missing result means fail.

Do not fallback to:

```text
Sales Invoice.outstanding_amount
```

because allocation authority is Payment-Ledger-backed outstanding retrieval.

Cases that should fail include:

- fully paid invoice;
- cancelled invoice;
- non-positive return/credit-note outstanding;
- incompatible account/company;
- source no longer represented as outstanding.

---

# 20. Return / Credit Note Policy

Reject:

- `is_return` Sales Invoice;
- negative outstanding row;
- negative explicit allocation.

Task 49 is positive Customer Receive only.

Do not net credits against invoice allocations.

Credit-note settlement requires separate design.

---

# 21. Duplicate Invoice Policy

Public `allocations` must contain each Sales Invoice exactly once.

Reject:

```text
SINV-A 5000
SINV-A 5000
```

Native ERPNext can have repeated invoice identity in term-specific rows, but Task 49 explicitly rejects term allocation, so duplicate invoice input is invalid.

---

# 22. Payment Terms Policy

If any selected Sales Invoice uses:

```text
allocate_payment_based_on_payment_terms
```

or native outstanding retrieval expands it into term-specific references requiring Payment Term identity:

```text
fail closed
```

Task 49 cannot flatten:

```text
invoice + payment_term
```

into:

```text
invoice
```

Return a bounded error explaining term-aware multi-invoice receipt is not supported in this V1.

Do not automatically allocate terms.

---

# 23. Early Payment Discount Policy

If any selected invoice is currently eligible for an early-payment discount under native rules/date:

```text
reject Task 49 prepare
```

There is no installed multi-invoice high-level composer that safely combines the single-invoice discount behavior across several invoices.

Do not:

- silently apply one invoice's discount;
- manually compose deductions;
- choose a discount account;
- alter allocation.

A later term/discount-aware task may add this.

---

# 24. Allocation Validation

Each explicit allocation must satisfy:

```text
0 < allocated_amount <= fresh native outstanding
```

at native currency precision.

Do not manually reduce source outstanding.

Do not write Payment Ledger.

Use native reference refresh/latest-outstanding validation again during final Draft insert.

---

# 25. Receipt Total Policy

Task 49 requires:

```text
request.amount
==
sum(request.allocations[].allocated_amount)
```

at native currency precision.

After native calculations the prepared document must also satisfy:

```text
unallocated_amount == 0
difference_amount == 0
```

for supported V1 cases.

If receipt > allocations:

```text
UNALLOCATED_RECEIPT_UNSUPPORTED
```

If allocations > receipt:

```text
ALLOCATION_TOTAL_MISMATCH
```

or project-standard equivalent.

No implicit advance.

---

# 26. Native Payment Entry Header

Create:

```python
frappe.new_doc("Payment Entry")
```

Populate only the small native-derived boundary.

Conceptually:

```text
company = derived common Company
payment_type = Receive
party_type = Customer
party = explicit validated Customer
paid_from = common native-derived receivable account
paid_from_account_currency = native account currency
posting_date = resolved/frozen date
mode_of_payment = approved mode if used
paid_to = native-resolved destination ledger account
paid_to_account_currency = native destination currency
paid_amount = request amount in party currency
received_amount = native-derived / bank_amount-supported destination amount
reference_no/date = approved values
remarks = approved bounded text
```

Use installed native methods/default functions wherever possible.

Do not hand-copy unrelated invoice fields.

---

# 27. Reference Row Construction

Use the native outstanding rows for the exact selected invoices as the source of truth for:

- reference doctype/name
- current outstanding
- invoice amount
- due date
- account
- currency
- exchange/reference details
- other installed native required reference metadata

Then set only the caller-approved:

```text
allocated_amount
```

for that exact invoice.

Do not populate totals/exchange/account data from the LLM request.

After construction run native reference detail refresh/validation in the safe installed order.

Document the exact sequence in implementation report.

---

# 28. Mode of Payment

Reuse Task 45's business-level abstraction.

If `mode_of_payment` is supplied:

- resolve Company default bank/cash account using native ERPNext helper;
- require a usable account;
- no fallback account invented by MCP;
- repeat resolution at confirm;
- include resolved account identity/currency/state in fingerprint.

Caller-supplied Mode of Payment controls the receipt.

Do not pick one invoice's Mode of Payment.

---

# 29. Bank Account

If `bank_account` is supplied:

- load with read permission;
- validate Company;
- resolve its native ledger Account;
- allow native Account validation to establish account type/currency/disabled state;
- include safe identity and resolved ledger state in fingerprint.

Never expose:

- account number
- IBAN
- SWIFT/BIC
- credentials.

---

# 30. Destination Inputs Are Mutually Exclusive

Reject request containing both:

```text
mode_of_payment
bank_account
```

Do not attempt to reconcile them.

Do not accept neither if the current Company/native configuration cannot resolve a valid destination through a documented server default.

The final implementation may require one of the two explicitly if that is safer and consistent with Task 45 behavior; document the decision.

---

# 31. Reference Number / Date

After destination resolution:

- if native Bank account rules require `reference_no` and/or `reference_date`, return `needs_input` / bounded missing-input response at prepare;
- never fabricate values;
- fingerprint both;
- preserve native validation at insert/submit.

Do not add an undocumented duplicate-reference rule.

---

# 32. Posting Date

Task 49 adds optional `posting_date`.

Rules:

- omitted → resolve once at prepare to native current date;
- explicit → validate date type and use it;
- store resolved date in approval payload;
- confirm reuses exactly the approved resolved date;
- do not update to a newer current date;
- native closed/frozen period and accounting-date validation remain authority.

Show posting date prominently in preview.

---

# 33. Currency Support

## Supported V1

### Same party / bank currency

Native calculations.

### Same invoice/party currency, destination bank in another currency

Support only if:

- all selected invoices share one transaction currency;
- all share one receivable-account currency;
- one destination currency is resolved;
- native calculation can produce a valid Draft;
- required `bank_amount` is supplied where needed;
- difference reaches zero;
- only allowed native FX adjustment is produced.

## Deferred

Reject:

- mixed invoice transaction currencies;
- caller exchange-rate overrides;
- mixed party accounts/currencies;
- ambiguous bank amount;
- unsupported native difference.

---

# 34. `bank_amount`

When destination currency differs:

```text
bank_amount = received amount in destination account currency
```

Pass through the supported internal calculation path.

No source/target/reference exchange-rate field may be accepted from the caller.

Preview should show:

- party paid amount + currency;
- bank received amount + currency;
- native source/target rates when material;
- native exchange difference summary.

---

# 35. Tax / Withholding Policy

Task 49 public contract exposes no:

- tax rows;
- withholding rows;
- templates;
- apply-TDS flags;
- accounts.

Normal native hooks still run.

If the prepared native document unexpectedly contains caller-unrequested tax/withholding state that materially changes the receipt:

```text
fail closed for Task 49
```

unless it is a specifically audited unavoidable native effect.

Do not suppress installed optional-app hooks.

Do not copy India Compliance rules.

---

# 36. Deduction Policy

No arbitrary deduction input.

No write-off account.

No bank-fee account.

No caller-selected exchange gain/loss account.

A native FX-related deduction may be allowed only when:

- it results from the supported cross-currency destination case;
- it is created by native ERPNext calculations;
- difference amount resolves to zero;
- it is summarized in preview;
- it is fingerprinted;
- focused tests verify it.

Any unexpected non-FX deduction should fail closed in Task 49.

---

# 37. Payment Request Boundary

Do not intentionally allocate/open Payment Requests.

Keep Payment Request fields blank unless unavoidable native behavior sets them.

If save/validation auto-links or mutates Payment Request state:

- detect during testing;
- include material state in preview/fingerprint, or
- fail closed and document limitation.

Do not make Payment Request a Task 49 public input.

---

# 38. Prepare Must Write Nothing

Prepare must not:

- insert Payment Entry;
- save Payment Entry;
- submit Payment Entry;
- update Sales Invoice;
- update Payment Schedule;
- create GL Entry;
- create Payment Ledger Entry;
- create Journal Entry;
- reconcile documents;
- update Payment Request;
- mutate Customer/Account/Bank state.

Use unsaved/native preview only.

---

# 39. Prepare Preview

Minimum bounded preview:

```text
target = Payment Entry
payment_type = Receive
Draft / no-ledger-effect notice

Customer
Company

posting_date
reference_no
reference_date

destination type:
  Mode of Payment OR Bank Account
safe destination display identity

party account currency
destination account currency

paid_amount
received_amount

for each selected Sales Invoice:
  name
  posting_date
  due_date
  invoice transaction currency
  party-account currency
  current native outstanding
  requested/native allocated amount

total_allocated_amount
unallocated_amount
difference_amount

cross-currency rate summary if material
allowed FX deduction summary if material

explicit:
"Draft only; submit requires separate approval"
```

Do not expose:

- raw Payment Entry JSON;
- full invoice documents;
- all Customer invoices;
- full Customer master;
- Chart of Accounts;
- raw GL;
- raw Payment Ledger;
- Bank Account number;
- IBAN/SWIFT;
- secrets;
- arbitrary metadata;
- tracebacks.

---

# 40. Approval

Reuse shared ApprovalStore.

No Task 49-specific approval mechanism.

Prepare creates approval bound to:

```text
action
site
authenticated user
normalized public intent
resolved native material state
fingerprint
```

Do not expose internal fingerprint material.

---

# 41. Canonical Fingerprint

Fingerprint must include at least:

## Request

- explicit Customer
- resolved posting date
- amount
- ordered/canonical explicit allocations
- destination choice
- reference number/date
- bank amount
- bounded remarks

## Party / Company

- Customer
- Company
- payment type
- party type
- effective receivable account
- receivable-account currency
- Company currency

## Destination

- destination kind
- selected Mode of Payment or Bank Account identity
- resolved ledger Account
- account type
- account currency
- enabled state
- Company binding

## Each source invoice

Canonical sort by exact Sales Invoice name.

Include:

- name
- docstatus/status
- modified/version signal
- Customer
- Company
- effective receivable account
- transaction currency
- party-account currency
- posting date
- due date
- native total
- fresh Payment-Ledger outstanding
- requested allocated amount
- reference exchange rate
- term/template allocation flags
- relevant payment schedule/discount eligibility state

## Result

- paid amount
- received amount
- native source/target rates
- total/base allocated
- unallocated
- difference
- bounded tax/withholding summary
- bounded deduction/FX summary
- exact bounded preview

Do not include:

- raw GL
- bank numbers
- secrets
- unrestricted document JSON.

---

# 42. Confirm Public Contract

Add:

```text
confirm_multi_invoice_customer_receipt
```

Input only:

```text
approval_token
confirm
```

No payment/allocation fields during confirm.

---

# 43. Confirm Behavior

Confirm must:

1. validate normal confirmation intent;
2. atomically claim via `claim_for_confirm_write()`;
3. enforce action/site/user;
4. enforce expiry;
5. enforce one-shot;
6. rebuild from the stored approved intent;
7. reload Customer;
8. reload every exact Sales Invoice with permission;
9. re-derive Company/effective account/currencies;
10. re-run fresh Payment-Ledger outstanding retrieval;
11. re-run eligibility/term/discount/tax policies;
12. re-resolve destination;
13. rebuild unsaved native Payment Entry;
14. recreate exact reference rows;
15. reapply approved explicit allocations;
16. recalculate native totals/rates;
17. recreate bounded preview;
18. recompute canonical fingerprint;
19. reject any material drift as `STALE_CONFIRMATION`;
20. insert exactly one normal-permission Draft Payment Entry;
21. commit according to current write-service convention;
22. never submit.

Any one failed invoice fails whole confirmation.

No partial Draft/reference creation.

---

# 44. Draft Insert

Final insert:

```text
docstatus = 0
```

Normal permission only.

No:

```text
ignore_permissions=True
Administrator impersonation
manual DB insert
manual GL
manual Payment Ledger
```

Draft insertion must create no ledger/outstanding settlement.

---

# 45. Stale-State Policy

Any material change in any selected reference fails the entire confirm.

Examples:

- invoice partially paid by another process;
- invoice fully paid;
- invoice cancelled;
- credit note changes outstanding;
- source modified materially;
- Customer mismatch;
- Company/account change;
- invoice-discounting account change;
- currency change;
- payment term/template change;
- early discount becomes eligible/ineligible;
- native outstanding changes;
- Mode of Payment default changes;
- Bank Account becomes disabled/changed;
- destination currency changes;
- FX/rate/deduction changes;
- tax/withholding state changes.

Never resize one allocation silently.

Require new prepare/approval.

---

# 46. Concurrency

Approval token one-shot protects duplicate confirmation of the same token.

It does **not** reserve invoices.

Task 49 must test:

```text
two separate approved Draft PEs targeting same invoices
```

and later concurrent submit behavior.

Do not add custom locks unless a reproducible failing native transaction case demonstrates the need.

Document observed native behavior.

---

# 47. Important Draft-vs-Submit Boundary

A Draft Payment Entry does not settle or reserve invoice outstanding.

Therefore:

```text
prepare/confirm Draft
```

can be correct now but become stale before:

```text
submit
```

The existing generic Payment Entry lifecycle submit must be reviewed/enriched in Task 49.

---

# 48. Multi-Reference Submit Preview Enrichment

If the current generic lifecycle submit preview only shows generic Payment Entry identity/status, enhance the **Payment Entry-specific submit projection** without creating a new submit tool.

Before user approves Payment Entry submit, preview must show bounded:

- Payment Entry name
- Customer
- Company
- payment type
- posting date
- destination
- party/destination currencies
- paid amount
- received amount
- every reference:
  - Sales Invoice
  - latest/current outstanding
  - allocated amount
  - payment term if any
- total allocated
- unallocated amount
- difference amount
- native exchange/deduction/tax summary
- explicit ledger/outstanding impact warning

Do not show raw GL.

---

# 49. Submit Approval Freshness

For Payment Entry submit, the lifecycle approval/fingerprint must include fresh reference/outstanding state sufficient to detect:

```text
Draft was valid,
but another payment settled one invoice before submit
```

At submit confirmation:

- native document validation remains final authority;
- latest Payment-Ledger outstanding must be refreshed/revalidated;
- material preview drift should require re-prepare of submit approval;
- no silent allocation shrinking.

Implement the smallest Payment Entry-specific lifecycle extension needed.

Do not create a second lifecycle framework.

---

# 50. Submit Effects Remain Native

Generic lifecycle submit must call normal:

```text
doc.submit()
```

Native ERPNext handles:

- latest reference validation
- GL
- Payment Ledger
- Sales Invoice outstanding
- Payment Schedule
- FX
- deductions/taxes
- hooks

MCP writes none of these directly.

---

# 51. Cancel / Delete

No new cancel/delete tool.

Reuse existing Accounts generic lifecycle.

Ensure Task 49 changes do not regress:

- native cancel reversal;
- outstanding restoration;
- linked-document behavior;
- Draft delete;
- cancelled delete policy.

No cascade.

---

# 52. Direct Backend

Add direct typed wrappers using the same Accounts service.

Requirements:

- configured site
- authenticated user
- Accounts profile
- no hard-coded site/user/Company/Customer
- JSON-safe input/output
- same authoritative service as REST.

---

# 53. REST Backend

Add fixed operations:

```text
prepare_multi_invoice_customer_receipt
confirm_multi_invoice_customer_receipt
```

Requirements:

- static remote registry
- typed payload
- no arbitrary method/import path
- no arbitrary DocType
- no caller-selected site
- no caller-selected identity
- approval authoritative where service executes
- direct/REST semantic parity.

If lifecycle submit preview/fingerprint receives Payment Entry-specific enrichment, ensure REST lifecycle parity remains intact.

---

# 54. Accounts Profile Registration

Add only the two new business tools to Accounts:

```text
prepare_multi_invoice_customer_receipt
confirm_multi_invoice_customer_receipt
```

Keep:

- Task 45 single-invoice payment tools;
- Task 47 read/query/aggregate;
- generic lifecycle.

Do not register in Sales or Purchase.

---

# 55. Do Not Replace Task 45

Single-invoice user intent continues to use:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment
```

Do not route one invoice through Task 49.

Task 49 contract minimum remains 2 references.

Shared internal helpers may be refactored only when safe and covered by regression tests.

---

# 56. Error Handling

Use existing bounded public error/reference envelope.

Add/reuse semantic errors for cases such as:

```text
INVALID_REFERENCE_COUNT
DUPLICATE_SALES_INVOICE
SOURCE_NOT_FOUND
SOURCE_NOT_READY
PERMISSION_DENIED
CUSTOMER_MISMATCH
COMPANY_MISMATCH
RECEIVABLE_ACCOUNT_MISMATCH
PARTY_CURRENCY_MISMATCH
MIXED_INVOICE_CURRENCY_UNSUPPORTED
NO_OUTSTANDING
ALLOCATION_EXCEEDS_OUTSTANDING
ALLOCATION_TOTAL_MISMATCH
UNALLOCATED_RECEIPT_UNSUPPORTED
RETURN_REFERENCE_UNSUPPORTED
PAYMENT_TERMS_UNSUPPORTED
EARLY_PAYMENT_DISCOUNT_UNSUPPORTED
DESTINATION_REQUIRED
INVALID_MODE_OF_PAYMENT
INVALID_BANK_ACCOUNT
BANK_AMOUNT_REQUIRED
UNEXPECTED_TAX_STATE
UNEXPECTED_DEDUCTION_STATE
NONZERO_DIFFERENCE
STALE_CONFIRMATION
APPROVAL_EXPIRED
APPROVAL_ALREADY_USED
```

Reuse existing project codes when equivalent.

Do not expose raw native tracebacks.

---

# 57. Permissions

Use normal Frappe/ERPNext permission enforcement.

Task 49 must:

- authenticate current user through existing runtime;
- require Customer read permission;
- require read permission on every selected Sales Invoice;
- require Payment Entry create permission;
- require Bank Account read permission when explicitly selected;
- rely on native Account/Link validation;
- insert with normal permissions;
- leave submit/cancel/delete permissions to generic lifecycle.

No role matrix.

No hard-coded roles.

No Administrator impersonation.

No permission bypass.

Do not perform the postponed global permission refactor.

---

# 58. Runtime Metadata

Verify configured-site runtime metadata for at least:

```text
Payment Entry
Payment Entry Reference
Payment Entry Deduction
Sales Invoice
Payment Schedule
Customer
Company
Account
Bank Account
Mode of Payment
Mode of Payment Account
```

Use metadata to verify field existence/requirements.

Do not make every custom field public.

---

# 59. Optional Apps

Inspect active site hooks during implementation verification.

India Compliance or another installed app may alter Payment Entry:

- validation;
- taxes;
- withholding;
- advance behavior;
- submit/cancel.

Do not suppress hooks.

Do not copy optional-app accounting rules into MCP.

Unexpected material native state outside Task 49's audited V1 policy should fail closed and be documented.

---

# 60. Allowed Changes

Allowed changes only where required, including current equivalents of:

```text
contracts/accounts/...
services/accounts/...
tools/accounts/...
profiles/accounts.py
contracts/registry.py
remote_operations.py
services/common/lifecycle.py      only for PE submit preview/fingerprint enrichment
tools/lifecycle.py                only if needed by current architecture
tests/...
docs/TOOLS.md
docs/inspect/...
```

Shared refactors must be:

- minimal;
- justified;
- backwards compatible;
- regression-tested.

Do not widen into unrelated cleanup.

---

# 61. Implementation Steps

## Step 1
Inspect current post-Task-47 / post-verification repository.

## Step 2
Add typed allocation and prepare/confirm contracts.

## Step 3
Implement exact Customer + per-SI permission-safe loading.

## Step 4
Derive and validate common Company/effective account/currencies.

## Step 5
Call native Payment-Ledger outstanding retrieval for exact vouchers.

## Step 6
Map selected native outstanding rows to exact allocations.

## Step 7
Reject returns/terms/discounts/mixed currencies and other V1 exclusions.

## Step 8
Build unsaved Payment Entry using `frappe.new_doc("Payment Entry")` plus native helpers/defaults.

## Step 9
Resolve Mode of Payment / Bank Account destination.

## Step 10
Apply posting/reference dates, bank amount, remarks.

## Step 11
Run native reference/amount calculations.

## Step 12
Enforce exact receipt/allocation totals, zero unallocated, zero difference.

## Step 13
Build bounded preview/fingerprint and shared approval.

## Step 14
Implement confirm fresh complete rebuild + fingerprint.

## Step 15
Insert Draft only.

## Step 16
Enrich Payment Entry generic lifecycle submit preview/fingerprint if current implementation is insufficient.

## Step 17
Add direct/REST/profile/catalog registration.

## Step 18
Implement full tests.

## Step 19
Run authorized live verification.

## Step 20
Create implementation report.

---

# 62. Required Tests — Contract

1. Customer required.
2. Amount required and positive.
3. Allocations required.
4. 1 allocation rejected.
5. 2 allocations accepted.
6. 20 allocations accepted.
7. 21 allocations rejected.
8. duplicate invoice rejected.
9. zero allocation rejected.
10. negative allocation rejected.
11. bool allocation rejected.
12. NaN rejected.
13. infinity rejected.
14. extra fields rejected.
15. raw account field unavailable.
16. exchange-rate fields unavailable.
17. tax/deduction fields unavailable.
18. reference DocType unavailable.

---

# 63. Required Tests — Core Native Flow

19. two fully allocated invoices.
20. three invoices full/full/partial.
21. exact 10k + 8k + 12k = 30k scenario.
22. prepare writes no Payment Entry.
23. prepare creates no GL.
24. prepare creates no Payment Ledger.
25. native outstanding API called for exact vouchers.
26. generic SI outstanding field is not allocation authority.
27. each native reference row preserved.
28. only allocated amount replaced by public intent.
29. deterministic reference ordering/fingerprint.

---

# 64. Required Tests — Source Eligibility

30. nonexistent invoice fails all.
31. Draft invoice fails all.
32. cancelled invoice fails all.
33. fully paid invoice fails all.
34. negative/return invoice fails all.
35. missing native outstanding row fails all.
36. one unreadable invoice fails all.
37. no subset Payment Entry is produced.

---

# 65. Required Tests — Party / Company / Account

38. explicit Customer mismatch fails.
39. two Customers fail.
40. two Companies fail.
41. different effective receivable accounts fail.
42. invoice-discounting effective-account mismatch fails.
43. different accounts with same currency still fail.
44. different party-account currencies fail.
45. Company derived, not public.
46. party account derived, not public.

---

# 66. Required Tests — Currency

47. INR invoices / INR bank works.
48. USD invoices / USD bank works if fixtures/native config support.
49. USD invoices / INR bank works with valid bank amount if supported.
50. missing required bank amount fails.
51. mixed invoice transaction currencies fail.
52. no caller exchange-rate input exists.
53. native rate change after prepare causes stale confirmation.
54. allowed FX deduction appears only from native calculation.
55. nonzero difference fails.
56. preview displays amount currencies explicitly.

---

# 67. Required Tests — Allocation Totals

57. allocation exactly equals outstanding accepted.
58. partial per-invoice allocation accepted.
59. allocation above invoice outstanding rejected.
60. sum allocations > receipt rejected.
61. receipt > sum allocations rejected.
62. unallocated must be zero.
63. difference must be zero.
64. precision/rounding equality uses native currency precision, not naive float equality.

---

# 68. Required Tests — Payment Terms / Discounts

65. no-term invoices supported.
66. template with term allocation disabled may proceed if native state remains simple.
67. enabled term allocation rejected.
68. one selected invoice with enabled terms fails whole request.
69. early-payment discount eligibility rejected.
70. discount eligibility appearing after prepare causes stale/failure.
71. no manual discount/deduction composition.

---

# 69. Required Tests — Destination

72. valid Mode of Payment resolves destination.
73. missing Mode of Payment default fails boundedly.
74. changed Mode of Payment default after prepare causes stale.
75. valid Bank Account works.
76. unreadable Bank Account fails.
77. wrong Company Bank Account fails.
78. disabled/invalid native account fails.
79. both Mode of Payment and Bank Account rejected.
80. full bank account data never returned.

---

# 70. Required Tests — Dates / References / Remarks

81. posting date omitted resolves once.
82. confirm reuses approved resolved posting date.
83. explicit valid posting date preserved.
84. invalid posting date rejected/native validation.
85. bank destination missing reference input returns bounded needs-input/error.
86. no fake reference generated.
87. reference date fingerprinted.
88. remarks <= 1000 accepted.
89. >1000 rejected.
90. custom/native remarks behavior preserves approved text deterministically.

---

# 71. Required Tests — Tax / Deductions / Requests

91. caller cannot supply tax rows.
92. caller cannot supply withholding.
93. unexpected material native tax state fails closed according to V1 policy.
94. caller cannot supply deduction.
95. unexpected non-FX deduction fails closed.
96. native supported FX deduction is summarized/fingerprinted.
97. Payment Request not explicitly allocated.
98. unexpected Payment Request mutation/linking is detected/documented.

---

# 72. Required Tests — Approval

99. prepare creates approval.
100. correct user/site/action can confirm.
101. wrong user fails.
102. wrong site fails.
103. wrong action fails.
104. expired token fails.
105. `confirm=false` writes nothing.
106. repeated token fails.
107. concurrent same-token confirm creates at most one Draft.
108. canonical allocation order fingerprint stable.
109. any one invoice outstanding drift fails all.
110. one invoice cancellation fails all.
111. one source modification fails all.
112. account/currency/default drift fails all.
113. destination drift fails all.
114. FX/deduction/tax material drift fails all.

---

# 73. Required Tests — Confirm / Atomicity

115. confirm performs fresh full rebuild.
116. successful confirm inserts exactly one Payment Entry.
117. created PE `docstatus == 0`.
118. all expected references inserted.
119. no partial reference subset survives failure.
120. transaction rollback leaves no Draft on validation failure.
121. no submit occurs.
122. no SI outstanding changes while Draft.
123. no GL/Payment Ledger effect while Draft.

---

# 74. Required Tests — Submit Preview / Freshness

124. generic PE submit preview lists all references.
125. preview shows each allocation/current outstanding.
126. preview shows currencies.
127. preview shows total allocated/unallocated/difference.
128. preview shows material FX/deduction summary.
129. submit fingerprint includes reference/outstanding state.
130. outstanding change after submit-prepare rejects stale lifecycle confirm.
131. fully paid reference before submit rejects native submit.
132. cancelled reference before submit rejects.
133. native submit updates every invoice outstanding correctly.
134. partial invoice residual is correct.
135. no MCP manual outstanding update occurs.

---

# 75. Required Tests — Cancel / Delete

136. cancel reverses all native invoice outstanding effects.
137. cancel reverses native Payment Ledger/GL through ERPNext only.
138. Draft delete remains supported.
139. cancelled delete follows existing policy.
140. no cascade behavior introduced.

---

# 76. Required Tests — Permissions

141. Customer read denied fails.
142. one SI read denied fails whole request.
143. Payment Entry create denied fails.
144. Bank Account read denied fails.
145. native Account/Link failure bounded.
146. submit permission remains lifecycle-native.
147. no role matrix.
148. no permission bypass.
149. no Administrator impersonation.

---

# 77. Required Tests — Direct / REST

150. direct prepare works.
151. direct confirm works.
152. fixed REST prepare exists.
153. fixed REST confirm exists.
154. malformed allocations fail REST schema.
155. unknown operation fails closed.
156. arbitrary method/import path impossible.
157. arbitrary DocType dispatch impossible.
158. caller cannot choose site.
159. caller cannot choose identity.
160. direct/REST success shapes conform.
161. direct/REST bounded errors conform.
162. lifecycle submit enrichment has transport parity.

---

# 78. Required Regression Tests

163. Task 45 single-invoice payment unchanged.
164. Task 47 get/query/aggregate unchanged.
165. Accounts profile inventory expected.
166. Sales profile inventory unchanged.
167. Purchase profile inventory unchanged.
168. shared ApprovalStore tests.
169. generic lifecycle tests.
170. REST backend tests.
171. Delivery Note Tasks 42/43 regressions.
172. Sales Invoice lifecycle.
173. catalog generation/check.
174. contract audit.
175. compile/static checks.
176. `git diff --check`.

If known pre-existing tests still fail, list exact names and independently demonstrate they fail without Task 49 files involved.

---

# 79. Live Authorized Verification

Task 49 must use an explicitly authorized throwaway/test site for accounting verification where safe.

At minimum attempt:

## Same-currency

- Customer with 2 submitted unpaid Sales Invoices
- prepare explicit allocations
- prove no write
- confirm Draft
- prove invoice outstanding unchanged in Draft
- submit through generic lifecycle
- verify both invoice outstanding values
- verify GL/Payment Ledger native effects
- cancel and verify restoration

## Partial

- one invoice full
- one invoice partial
- verify residual outstanding

## Stale

- prepare
- alter one outstanding through another valid payment
- confirm should fail/re-prepare

## Destination

- Mode of Payment
- Bank Account

## Permission

- permitted user
- denied source or PE-create scenario if safely available

## Cross-currency

Only if safe configured fixtures/accounts exist.

Do not create production bank/account structures just to satisfy coverage.

Document unverified scenarios honestly.

---

# 80. Acceptance Criteria

Task 49 is complete only when:

1. two Accounts-only public tools exist;
2. exact Customer required;
3. 2–20 unique exact SIs required;
4. explicit positive allocation per SI required;
5. native Payment-Ledger outstanding retrieval used;
6. every source read permission enforced;
7. Customer common invariant enforced;
8. Company common invariant enforced;
9. effective receivable account common invariant enforced;
10. party-account currency common invariant enforced;
11. mixed invoice transaction currency rejected;
12. return/negative references rejected;
13. term allocation rejected;
14. early-discount cases rejected;
15. receipt equals allocation total;
16. unallocated remainder rejected;
17. no caller tax/withholding/deduction rows;
18. no caller exchange-rate fields;
19. Mode of Payment supported;
20. Bank Account supported;
21. both destination inputs mutually exclusive;
22. optional bank amount works only through native currency logic;
23. optional posting date resolved/frozen;
24. prepare writes nothing;
25. shared approval reused;
26. confirm uses atomic one-shot claim;
27. confirm fully rebuilds native state;
28. any material drift fails whole request;
29. confirm inserts exactly one Draft Payment Entry;
30. no auto submit;
31. no GL/Payment Ledger manual writes;
32. generic Payment Entry submit preview is multi-reference aware;
33. submit approval is fresh-outstanding aware;
34. lifecycle submit remains native;
35. cancel/delete remain native;
36. direct/REST parity exists;
37. Task 45 remains unchanged;
38. Task 47 remains unchanged;
39. Sales/Purchase inventories remain unchanged;
40. focused/regression tests pass except explicitly proven pre-existing failures;
41. live verification is truthfully reported;
42. no site/company/customer/user is hard-coded.

---

# 81. Expected Result

After Task 49:

```text
ACCOUNTS PROFILE

Single Invoice
────────────────────────
prepare_sales_invoice_payment
confirm_sales_invoice_payment


Multiple Invoices
────────────────────────
prepare_multi_invoice_customer_receipt
confirm_multi_invoice_customer_receipt


Payment Entry Intelligence
────────────────────────
get_payment_entry
query_payment_entries
aggregate_payment_entries


Lifecycle
────────────────────────
prepare/confirm submit
prepare/confirm cancel
prepare/confirm delete
```

Example:

```text
User:
"Arkee Foods paid ₹30,000.
Apply ₹10,000 to SINV-A,
₹8,000 to SINV-B,
₹12,000 to SINV-C."

        ↓

prepare_multi_invoice_customer_receipt
        ↓
native fresh outstanding
        ↓
bounded review
        ↓
approval
        ↓
confirm
        ↓
Draft Payment Entry
```

No invoice is settled until separately approved submit.

---

# 82. Limitations After Task 49

Still deliberately unsupported:

- auto-allocation by oldest/due date
- unallocated customer receipt
- customer advance
- Sales Order advance
- Payment Terms multi-invoice allocation
- early-payment-discount multi-invoice composition
- mixed invoice transaction currencies
- return/credit-note netting
- supplier payment
- supplier multi-invoice payment
- Internal Transfer
- Payment Request business flow
- Payment Reconciliation
- Journal Entry
- caller tax/deduction/account construction
- bank reconciliation/import

These are not Task 49 defects.

---

# 83. Deliverable Report

Create:

```text
docs/inspect/MULTI_INVOICE_CUSTOMER_RECEIPT_IMPLEMENTATION_REPORT.md
```

Report must include:

1. exact files changed
2. public tools/contracts
3. allocation contract
4. max-reference policy
5. native outstanding API used
6. native Payment Entry construction sequence
7. per-source permission behavior
8. Customer/Company/account/currency invariants
9. amount/allocation currency semantics
10. native reference-row construction
11. receipt-total/unallocated policy
12. term/discount rejection behavior
13. return/negative reference behavior
14. Mode of Payment behavior
15. Bank Account behavior
16. posting/reference date behavior
17. cross-currency/bank amount behavior
18. tax/withholding/deduction policy
19. Payment Request observations
20. preview fields
21. fingerprint fields
22. stale-state behavior
23. Draft insertion/atomicity
24. submit-preview enrichment
25. submit freshness behavior
26. direct backend
27. REST backend
28. profile/catalog changes
29. tests added
30. exact test commands/results
31. known pre-existing failures with exact evidence
32. live verification performed
33. GL/Payment Ledger/outstanding observations
34. live scenarios not verified and why
35. optional-app observations
36. confirmation Task 45 unchanged
37. confirmation Task 47 unchanged
38. confirmation Sales/Purchase unchanged
39. confirmation no manual GL/Payment Ledger logic
40. limitations

Do not claim verification not actually performed.

---

# 84. Exact Next Task

Do not automatically implement the next feature.

After Task 49 is reviewed, choose between the next Accounts gaps based on real usage.

Likely candidates:

```text
A. Customer advance / unallocated receipt native-flow audit
B. Supplier Purchase Invoice payment native-flow audit
C. Auto-allocation strategy audit
D. Payment Terms-aware multi-invoice receipt audit
E. Payment Reconciliation audit
```

The next task must be selected only after reviewing Task 49 implementation and runtime results.
