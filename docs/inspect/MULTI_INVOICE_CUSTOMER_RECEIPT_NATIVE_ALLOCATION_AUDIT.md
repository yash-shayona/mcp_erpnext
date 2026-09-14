# Multi-Invoice Customer Receipt Native Allocation Audit

**Task:** 48 — Multi-Invoice Customer Receipt Native Allocation Audit  
**Date inspected:** 2026-09-14  
**Mode:** architecture audit only; no site/accounting mutation

## 1. Executive conclusion

ERPNext 16.34.2 natively supports one submitted `Payment Entry` containing
multiple `Payment Entry Reference` rows, but this installed version has no
high-level factory for an explicit multi-invoice customer receipt. The native
building blocks are:

1. `get_outstanding_reference_documents(args, validate=False)` in
   `erpnext.accounts.doctype.payment_entry.payment_entry`, which obtains
   Payment-Ledger-backed outstanding rows for one party, Company and party
   account and splits term-enabled documents into payment-term rows; and
2. `PaymentEntry.set_missing_ref_details()`, normal document `validate()`, and
   `validate_allocated_amount_with_latest_data()`, which refresh and validate
   explicitly constructed reference rows.

`PaymentEntry.allocate_amount_to_references()` is a native ordered
auto-allocation method used by the Desk UI. It is not the right authority for
Task 49 because the proposed public intent contains exact allocations.

Task 49 should therefore create a new unsaved `Payment Entry`, populate only
native-derived header/default fields and native outstanding reference rows,
replace their allocations with the caller's explicit positive amounts, and
let the Payment Entry controller validate the Draft on insert. It should not
start from the single-invoice `get_payment_entry()` factory: that factory
derives project, discount, Mode of Payment and other state from one privileged
invoice and has no rule for choosing the privileged invoice in a multi-source
receipt.

The smallest safe V1 must require an exact Customer, 2–20 unique exact
submitted Sales Invoice names and an explicit positive allocation for each.
All invoices must share Customer, Company, effective receivable account, and
party-account currency. V1 must require receipt amount to equal total explicit
allocations, reject negative/return references, reject term-based allocation
and early-payment-discount cases, and allow one destination expressed as
either `mode_of_payment` or `bank_account`. Cross-currency bank settlement can
retain optional `bank_amount`; mixed invoice transaction currencies, caller
exchange rates, taxes, withholding, deductions, advances, auto-allocation and
reconciliation remain deferred.

Prepare must write nothing. Confirm must atomically claim the existing shared
approval, rebuild the complete native preview from fresh state, compare a
canonical fingerprint, and insert a Draft only. Any material drift in any
invoice or destination fails the entire confirmation and requires re-prepare.

## 2. Current Accounts baseline

The inspected MCP checkout is commit
`d60e3ddeaa27168a7c8cfde1f911f0bdae66e6b2` on branch `master`. Its only
pre-existing worktree change was the untracked Task 48 specification.

The Accounts profile currently registers:

- `prepare_sales_invoice_payment` and `confirm_sales_invoice_payment`;
- `get_payment_entry`, `query_payment_entries`, and
  `aggregate_payment_entries`; and
- generic lifecycle tools scoped by the Accounts policy.

The Task 45 service uses the installed
`get_payment_entry("Sales Invoice", name, ...)`, previews an unsaved Draft,
stores request/preview/destination fingerprint material, claims with
`ApprovalStore.claim_for_confirm_write()`, rebuilds, compares, inserts with
normal permissions, and commits. It intentionally supports one invoice and
rejects overpayment. Payment Entry is allowlisted for generic submit, cancel
and delete; Task 47 reads remain discovery/intelligence only.

Direct tools call the same services under the resolved Frappe user. The REST
bridge validates typed inputs and dispatches only fixed operation names in
`remote_operations.py`; the authenticated Frappe endpoint supplies the remote
identity and approval-store authority. Task 49 must preserve this shape.

## 3. Installed version and source evidence

The exact installed sources inspected were:

| Component | Version/commit |
|---|---|
| ERPNext | `16.34.2`, `4048fb70e14d1843956fcdabb7c3cca75a1cbcdd` |
| Frappe | `16.33.1`, `988e54f3c4c291e2077a83809663f123731abe76` |
| mcp_erpnext | `d60e3ddeaa27168a7c8cfde1f911f0bdae66e6b2` |

Primary evidence locations (line numbers refer to this checkout):

- `payment_entry.py:137-206`: validate/submit/cancel lifecycle;
- `payment_entry.py:331-342`: duplicate reference key;
- `payment_entry.py:420-503`: latest-outstanding validation;
- `payment_entry.py:577-621`: reference-detail refresh;
- `payment_entry.py:668-741`: reference party/account/docstatus checks;
- `payment_entry.py:802-939`: term schedule updates and currency conversion;
- `payment_entry.py:971-1134`: totals and unallocated amount;
- `payment_entry.py:1328-1466`: GL creation per reference/remainder;
- `payment_entry.py:1913-2080`: native ordered auto-allocation;
- `payment_entry.py:2300-2565`: outstanding retrieval and term splitting;
- `payment_entry.py:2800-2888`: reference details;
- `payment_entry.py:2890-3047`: single-source factory;
- `payment_entry.py:3242-3539`: accounts, amounts, discounts and term rows;
- `accounts/utils.py:1239-1315`: Payment Ledger outstanding query;
- `general_ledger.py:34-69`: GL-to-Payment-Ledger creation path;
- `payment_reconciliation.py`: allocation of existing payments;
- `test_payment_entry.py:1386-1421` and `2091-2175`: outstanding ordering
  and payment-term splitting tests.

No live DocType metadata, site records, database queries, inserts, submits,
cancels, GL/Payment Ledger writes, or authenticated MCP calls were performed.

## 4. Business flow

```text
exact Customer + exact SI allocations + one receipt destination
    -> check each source read permission and common invariants
    -> native Payment-Ledger outstanding lookup restricted to selected vouchers
    -> native-derived Payment Entry header and reference rows
    -> explicit allocation substitution + native calculations
    -> bounded Draft preview + approval token
    -> shared atomic confirm claim
    -> repeat all reads/defaults/outstanding/reference construction
    -> canonical material fingerprint comparison
    -> normal-permission Draft insert only
    -> later generic lifecycle approval and submit
    -> ERPNext GL -> Payment Ledger -> outstanding updates per reference
```

For the example 10,000 + 8,000 + 12,000 receipt, the Payment Entry contains
three reference rows and a 30,000 party-side receipt. Only submit creates the
ledger entries which settle the first two invoices and leave 8,000 on the
third; Draft confirmation has no ledger or outstanding effect.

## 5. Native outstanding retrieval API

The public installed callable is:

```python
get_outstanding_reference_documents(args, validate=False)
```

in `erpnext.accounts.doctype.payment_entry.payment_entry`. It accepts a dict or
JSON string. For Task 49 the service should supply, server-side:

```python
{
    "posting_date": effective_posting_date,
    "company": company,
    "party_type": "Customer",
    "payment_type": "Receive",
    "party": customer,
    "party_account": receivable_account,
    "get_outstanding_invoices": True,
    "get_orders_to_be_billed": False,
    "vouchers": [
        {"voucher_type": "Sales Invoice", "voucher_no": name},
        ...,
    ],
    "book_advance_payments_in_separate_party_account": native_company_policy,
}
```

Optional native filters include posting/due-date ranges, outstanding min/max,
cost center and active accounting dimensions. They are not Task 49 public
inputs. `posting_date` here is a list of query predicates assembled from the
date-range keys, while the top-level posting date is also used for order
retrieval; selected invoice V1 should rely on exact vouchers and fresh ledger
state rather than generic date filtering.

The function checks read permission on the party, gets the party-account and
Company currencies, and delegates invoices to:

```python
get_outstanding_invoices(
    party_type, party, [party_account], common_filter=...,
    posting_date=..., min_outstanding=..., max_outstanding=...,
    accounting_dimensions=..., vouchers=...,
)
```

`get_outstanding_invoices()` queries `Payment Ledger Entry` through
`QueryPaymentLedger.get_voucher_outstandings()`. It filters account type,
exact account, party type, party, Company and selected vouchers, excludes
non-positive residuals below precision tolerance, and returns rows ordered by
due date. Its row schema includes `voucher_type`, `voucher_no`, `posting_date`,
`due_date`, `invoice_amount`, `payment_amount`, `outstanding_amount`,
`currency`, and `account`. The outer function adds `exchange_rate`, may include
negative outstanding documents, and may include orders only when requested.

It does not itself prove per-invoice user read permission: it explicitly checks
the party, then uses ledger queries and `frappe.db` reads. Task 49 must load and
`check_permission("read")` on every selected Sales Invoice before treating the
native outstanding result as usable. A missing selected invoice row is an
explicit prepare/confirm failure, not permission to fall back to a generic
Sales Invoice `outstanding_amount` field.

Fully paid/cancelled invoices cease to have a qualifying positive Payment
Ledger outstanding row. Submitted return/credit notes may appear as negative
outstanding rows; Task 49 V1 should reject them rather than net them silently.

## 6. Outstanding retrieval versus MCP reads

`query_sales_invoices` and Task 47 Payment Entry reads are permission-aware,
bounded discovery tools, but they report document fields at the time of the
read. They neither reproduce the Payment Ledger aggregation nor payment-term
splitting and cannot be approval authority. They may help an Agent resolve
exact invoice names; the write service must independently run the native
outstanding lookup at both prepare and confirm.

## 7. Native reference and allocation APIs

There are three different mechanisms and they must not be conflated:

1. `get_outstanding_reference_documents()` returns the authoritative candidate
   reference rows.
2. `PaymentEntry.allocate_amount_to_references(paid_amount,
   paid_amount_change, allocate_payment_amount)` is the Desk's server-side
   sequential auto-allocator. It walks the already ordered references and
   allocates up to their outstanding values, including negative documents and
   Payment Request priority rules.
3. `PaymentEntry.set_missing_ref_details()` calls
   `get_reference_details()` for nonzero rows and fills/refreshes total,
   outstanding, exchange rate, due date and account metadata. Normal
   `validate()` then checks duplicates, party, account, docstatus and latest
   outstanding.

For explicit allocations Task 49 should use (1) to construct rows and (3) plus
normal document validation to validate them. Calling (2) would overwrite user
intent with order-dependent allocation and is therefore deferred to a later
explicit auto-allocation capability.

## 8. High-level factory analysis and construction decision

| Approach | Finding | Decision |
|---|---|---|
| `frappe.new_doc("Payment Entry")` + native helpers | Matches Desk's general multi-reference model; permits one coherent header and exact rows from native outstanding data | **Use** |
| `get_payment_entry()` from first invoice, then add rows | Factory is explicitly one source; first invoice controls Company, customer, account, project, Mode of Payment, contact, terms and early discount | Reject for multi-source V1 |
| native high-level multi-invoice factory | No such installed callable was found | Unavailable |
| Payment Reconciliation internals | Reconcile already-submitted payments/credits against invoices and writes reconciliation state | Wrong lifecycle; defer |

The service may reuse small Task 45 destination resolution and preview/approval
patterns, but should create a dedicated internal builder. It must not call
private helpers by arbitrary import path supplied by a caller.

The safe authored boundary is small: set fixed `payment_type="Receive"`,
`party_type="Customer"`, exact native-derived Company/customer/receivable
account/currencies/destination, receipt amounts and selected native reference
rows. Do not copy invoice totals, exchange rates, account or due dates from the
LLM request.

## 9. Customer, Company and party-account rules

### Customer

`PaymentEntry.validate_reference_documents()` loads every nonzero reference
and compares its customer field with the Payment Entry `party`; mismatch throws
“not associated with Customer”. Task 49 should also require `customer` in the
public request and perform a fail-fast equality check on all loaded invoices.
This is redundant by design: it makes financial intent explicit and produces a
bounded error before document construction while native validation remains the
authority.

### Company

A Payment Entry has one mandatory Company, and its two ledger accounts must be
Company-compatible. Outstanding retrieval adds a Company filter. An invoice
from another Company therefore will not be returned for the chosen party
account; its receivable account also differs by Company. Task 49 must require
all selected invoices to share exactly one Company derived from the invoices.
Cross-company receipt is not a valid V1 abstraction.

### Party account

For Customer Receive, `paid_from` is the single party/receivable account.
Reference validation determines the effective invoice account using invoice
discounting when present, otherwise `Sales Invoice.debit_to`, and rejects it if
it differs from the Payment Entry party account (except native separate-advance
logic, which does not justify mixing invoice accounts).

Consequently all V1 invoices must share the same effective receivable account,
and necessarily its single account currency. Different receivable accounts,
even in the same currency, cannot coexist in this Payment Entry. Invoice
discounting that changes the effective party account must participate in the
check and fingerprint; a mixed result fails closed.

## 10. Currency compatibility and amount semantics

`allocated_amount`, `total_allocated_amount`, `unallocated_amount` and the
outstanding values returned by `get_outstanding_invoices()` are in the Payment
Entry party-account currency. For Receive, that is `paid_from_account_currency`.
They are not necessarily the Sales Invoice transaction currency. The public
field should therefore be named/documented as:

```text
allocated_amount: positive amount in the shared receivable-account currency
```

The preview must display that currency beside every allocation.

| Case | Installed native capability | Task 49 V1 |
|---|---|---|
| INR party account, INR bank | paid = received; rates normally 1 | Support |
| USD party account, USD bank | paid = received in USD; Company base conversion remains native | Support only when all invoice transaction currencies are USD |
| USD party account, INR bank | `paid_amount` is party USD; `received_amount` is bank INR; native rates/optional `bank_amount` | Support with explicit `bank_amount` when currencies differ |
| same Customer, mixed invoice transaction currencies | Can only pass reference account validation if all resolve to the same party account; allocations still use that account currency | Defer/reject in V1 for preview clarity |
| same invoice currency, different receivable accounts/currencies | One Payment Entry has one party account | Reject |
| bank currency differs | Native source/target rates and difference calculation apply | Support boundedly; never accept caller exchange rates |

The receipt `amount` means party-side `paid_amount` in the shared receivable
currency. `bank_amount`, when required because the destination currency
differs, means `received_amount` in destination account currency. The preview
must show both amounts, both currencies, source/target rates, difference and
any exchange-gain/loss deduction summary. Task 49 must not implement FX math;
it must use native rate/default functions and native Payment Entry calculations.

## 11. Receipt total, partial allocation and remainder

ERPNext natively permits positive partial allocations up to each current
outstanding. Omitting an invoice means no row; zero rows are ignored/refreshed
inconsistently and should be rejected/omitted rather than retained. Negative
allocations model returns/reverse flows and are outside Customer Receive V1.

`set_total_allocated_amount()` sums row allocations. For Receive,
`set_unallocated_amount()` represents excess party-side paid amount after
allocations (with deductions/taxes taken into account). Native GL submission
posts an additional unallocated party row; it can later be reconciled and may
interact with the Company's separate advance-account setting.

Native behavior therefore permits `payment > allocations`. It does not turn
that remainder into an explicit caller-selected advance model. Task 49 should
choose Option A: require, at native currency precision,

```text
receipt amount == sum(explicit allocations)
unallocated amount == 0
difference amount == 0
```

If allocations exceed the receipt, calculated difference/balancing becomes
invalid for this intent and must be rejected before approval. If receipt
exceeds allocations, reject it as `UNALLOCATED_RECEIPT_UNSUPPORTED`. Explicit
advance receipts deserve a separate audit because Company settings, tax and
later reconciliation affect their meaning.

## 12. Invalid, stale and duplicate references

At prepare, reject the whole request when any selected invoice is missing,
unreadable, Draft/cancelled, not for the explicit Customer, not for the common
Company/account/currency, a return/negative-outstanding invoice, fully paid, or
has less outstanding than requested. There is no partial-success receipt.

At confirm, repeat all checks and map any change to a bounded
`STALE_CONFIRMATION` response. `validate_allocated_amount_with_latest_data()`
retrieves current selected vouchers. It throws if a row is now absent/fully
paid, if non-term outstanding differs after partial payment, or if allocation
exceeds latest invoice/term outstanding. `validate_reference_documents()`
also rejects non-submitted sources. Thus fully paid and cancelled-before-confirm
both fail the fresh rebuild.

Native duplicate identity is `(reference_doctype, reference_name,
payment_term, payment_request)`. The same invoice can validly occur more than
once only for distinct payment terms or Payment Requests. Task 49's invoice-
level, non-term V1 must reject duplicate Sales Invoice input before retrieval.

Disputed/blocked Customer invoices have no general Payment Entry block in the
inspected controller comparable to Purchase Invoice `on_hold`. No MCP-only
business rule should be invented; any installed hook/validation still runs at
insert/submit.

## 13. Payment Terms and early-payment discounts

When a selected invoice's Payment Terms Template enables
`allocate_payment_based_on_payment_terms`, outstanding retrieval expands it
into rows identified by invoice plus `payment_term`. Rows include term
outstanding/payment amount and due-date data. Payment Entry validation rejects
a blank term for such an invoice; submit updates each matching `Payment
Schedule` row. Different terms on one invoice are therefore distinct native
reference identities and cannot safely be flattened into `{invoice, amount}`.

Early discount is date-sensitive. The single-source factory's
`apply_early_payment_discount()` iterates one document's schedule using
`reference_date`, modifies paid/received amounts, and builds native deduction
rows (and possibly tax-discount loss rows). There is no installed multi-invoice
orchestration for combining discounts from several invoices.

Task 49 should fail closed if any selected invoice has term-based allocation
enabled or any currently eligible early-payment discount. This keeps its
public allocation unit unambiguous and prevents one invoice from silently
changing a multi-invoice receipt/deduction total. A later term-aware task must
use `{sales_invoice, payment_term, allocated_amount}` identities and separately
audit multi-invoice discount composition. A single PE may natively contain a
mix of such rows, but that native possibility is not enough for a safe V1.

## 14. Destination, dates and remarks

### Mode of Payment

One receipt has one Mode of Payment and one destination. Task 45's call to
ERPNext `get_default_bank_cash_account(company, account_type,
mode_of_payment=...)` remains suitable. Resolution must be repeated on confirm;
missing, disabled, wrong-Company or changed default account fails/re-fingerprints.
Invoice-local Mode of Payment values must not choose among conflicting sources.
The caller's explicit receipt Mode of Payment controls.

### Bank Account

Task 45's public `bank_account` fallback remains suitable if the service loads
the Bank Account with read permission, verifies its Company, obtains its ledger
`account`, and lets native account checks establish type/currency/disabled
state. The preview exposes only the Bank Account identity or safe display name,
never account numbers, IBAN or SWIFT. `mode_of_payment` and `bank_account` are
mutually exclusive.

### Reference number and date

Payment Entry requires both fields when the destination ledger account type is
Bank (`validate_transaction_reference()`). Keep the Task 45 optional typed
fields, but after destination resolution return `needs_input` when the native
bank rule requires either one. `reference_date` is transaction-reference data
and also controls early-discount eligibility; because V1 rejects eligible
discounts, it must still be fingerprinted and validated as a date. The
installed controller does not perform a universal duplicate bank-reference
check; do not claim uniqueness or add an undocumented MCP rule.

### Posting date

Include `posting_date` in Task 49 as an optional explicit date defaulting to
native `nowdate()` at prepare, and freeze the resolved date in the approved
request. Unlike Task 45's factory, a new-doc builder can set it before exchange
rates and outstanding/default calculations. It matters for rates and later
closed/frozen-period validation. Confirm must use the approved resolved date,
not advance to a new “today”. Back/future date validity remains native; the
preview must make the date prominent.

### Remarks

Reuse bounded optional remarks (maximum 1,000 characters). Set
`custom_remarks` consistently when preserving caller remarks, or otherwise let
native `set_remarks()` generate deterministic reference detail; verify Task 45
behavior during implementation because assigning `remarks` alone can be
overwritten by validation when `custom_remarks` is false. Never parse remarks
as accounting instructions.

## 15. Taxes, withholding, deductions and difference

Payment Entry supports taxes, tax withholding and deductions. Validation calls
native tax calculation and `PaymentTaxWithholding`; submit creates their GL
effects. Early discount and exchange gain/loss can create deductions. Installed
regional hooks may also participate through normal Frappe hooks.

Task 49 must expose no tax, withholding, account, write-off, bank-fee or
deduction rows. It should set no tax template/apply-TDS intent and reject a
prepared native document if unexpected non-exchange deduction/tax/withholding
rows appear. A native exchange-gain/loss row may be allowed only when generated
from the supported bank-currency case, fully summarized in preview and
fingerprinted. `difference_amount` must be zero before approval and again on
insert/submit.

This policy does not bypass India Compliance or other hooks: normal insert and
later submit still run them. A hook-induced material preview change causes a
native validation failure or fingerprint mismatch rather than MCP-authored tax
logic.

## 16. Advance, reconciliation and Payment Request boundaries

- **Unallocated receipt/advance:** Native `unallocated_amount` posts a party
  credit; separate-advance-account Company policy can alter the ledger path.
  Reject in Task 49 and audit as its own intent.
- **Payment Reconciliation:** operates on an existing submitted payment/JE and
  invoices using `reconcile_against_document()`. It is not a creation factory
  and must be a separate capability.
- **Payment Request:** the single-source factory calls
  `allocate_open_payment_requests_to_references()`, and Payment Entry save/submit
  can match/update Payment Requests. Task 49 should not auto-link them: leave
  `payment_request` blank and document that native before-save matching may
  report candidates. If installed behavior mutates reference links during
  validation/save, include them in preview/fingerprint or fail closed. A later
  explicit Payment Request flow should own that choice.

## 17. Payment Ledger and General Ledger authority

Draft insertion creates neither GL nor Payment Ledger effect. On submit,
`PaymentEntry.on_submit()` updates Payment Requests/schedules, calls
`make_gl_entries()`, and refreshes outstanding state.

`add_party_gl_entries()` creates a party GL line per reference. For each normal
Sales Invoice it sets `against_voucher_type="Sales Invoice"` and that invoice
name, with the allocated amount in party-account currency and native base/
transaction values. It creates one bank debit line for the receipt. If there
is an unallocated remainder, it creates a separate unreferenced party line.
Taxes/deductions/exchange differences add native lines when applicable.

`general_ledger.make_gl_entries()` creates Payment Ledger Entries from the GL
map. The per-reference `against_voucher_type`, `against_voucher`, party,
account and account-currency amount are what reduce each invoice's outstanding.
Cancellation reverses native GL/Payment Ledger effects and term schedule
updates. MCP must never write GL or Payment Ledger directly.

## 18. Approval, fingerprint and stale-state design

Reuse the shared policy exactly:

```text
prepare -> approvals.create(action/site/user/payload)
confirm -> ApprovalStore.claim_for_confirm_write(action/site/user)
```

Do not add an approval-mode argument or tool-specific policy branch. Keep
`MCP_APPROVAL_MODE` server-only, preserve `trusted_human` and
`agent_delegated`, and keep `APPROVE` interpretation outside MCP. Confirm's
one-shot atomic claim prevents token replay/concurrent confirmation; it does
not lock invoices.

Canonical fingerprint material should include:

- normalized public request and resolved posting date;
- Customer, Company, payment type and party type;
- effective party account, party-account currency and Company currency;
- destination kind/name, resolved ledger account, account type/currency and
  enabled/Company state;
- Mode of Payment/default identity or Bank Account identity;
- reference number/date and bounded remarks;
- paid/received/base amounts, native source/target exchange rates;
- for each sorted reference: invoice name, docstatus, `modified`, Customer,
  Company, effective receivable account, invoice/party currencies, posting/due
  date, native total/current outstanding, requested allocation, reference
  exchange rate, term/template flags and relevant schedule rows;
- taxes, withholding and deductions as bounded summaries;
- total/base allocated, unallocated and difference amounts; and
- the exact bounded preview.

Do not fingerprint raw GL, secrets, bank account numbers or unrestricted
document JSON. Sort references by exact invoice name for canonical hashing
while retaining a separate display order if desired.

Any material change—another submitted payment/credit note, cancellation,
invoice modification, term/template change, account/default change, exchange
rate change, Bank Account disable/change or native tax/deduction change—must
fail the whole confirm with `STALE_CONFIRMATION`. Never silently resize one row
or create the remaining rows.

## 19. Concurrency and Draft-versus-submit

Fresh rebuild plus fingerprint closes the user-review drift window up to the
confirm rebuild. Normal Draft insert re-runs latest-outstanding validation, but
there is still no invoice-level lock spanning the earlier reads and insert.
More importantly, a Draft Payment Entry does not reserve or settle outstanding:
two valid Drafts can target the same invoice.

On later submit, Payment Entry validation runs again, including
`set_missing_ref_details(force=True)`, reference/docstatus checks and latest
outstanding validation. It rejects allocations above current outstanding and
missing/fully-paid references. The generic lifecycle submit approval must show
all reference allocations, currencies, deductions, unallocated and difference
amounts—not merely Payment Entry name/status—and should fingerprint fresh
Payment-Ledger outstanding/reference state. Task 49 should add this bounded
Payment Entry submit-preview enrichment if the current generic lifecycle does
not already do so; do not add custom locks without demonstrated need.

There remains a narrow database race between latest validation and concurrent
submits. Installed source provides validation, not a custom selected-invoice
locking API. Tests must exercise concurrent submit and document the actual
transaction outcome before considering locks. Database transaction rollback
must keep the receipt atomic: no partial multi-invoice result is acceptable.

## 20. Public contract decision matrix

| Option | Determinism | Native fit | V1 decision |
|---|---|---|---|
| A: exact Customer + explicit invoice allocations | High; supports deliberate partial rows | Native outstanding rows plus controller validation | **Choose** |
| B: amount + `oldest` strategy | Order/date semantics and credit-note behavior require policy | Native UI allocator exists | Defer |
| C: invoice list + native auto-allocation | Allocation depends on native row ordering/terms/requests | Possible but less auditable | Defer |
| D: generic Payment Entry references/accounts | Leaks accounting internals and permits unrelated flows | Technically possible | Reject |

Recommended typed intent (names finalized in Task 49):

```python
class CustomerReceiptAllocation(PublicContractModel):
    sales_invoice: NonEmptyString
    allocated_amount: float = Field(gt=0)  # shared party-account currency

class MultiInvoiceCustomerReceiptPrepareInput(PublicContractModel):
    customer: NonEmptyString
    amount: float = Field(gt=0)            # shared party-account currency
    allocations: Annotated[
        list[CustomerReceiptAllocation],
        Field(min_length=2, max_length=20),
    ]
    mode_of_payment: NonEmptyString | None = None
    bank_account: NonEmptyString | None = None
    reference_no: NonEmptyString | None = None
    reference_date: date | None = None
    posting_date: date | None = None
    bank_amount: float | None = Field(default=None, gt=0)
    remarks: Annotated[str, Field(max_length=1000)] | None = None
```

Use `PublicContractModel(extra="forbid")`; reject booleans/non-finite numbers
at the service boundary as well as via Pydantic. Require exact invoice names.
Search/disambiguation remains in the Agent/read tools. The explicit Customer is
not derived silently: it is a reviewed invariant checked against every source.

Twenty references is a conservative MCP boundary: it covers ordinary receipts,
keeps preview/token/REST payloads and permission/native validation work bounded,
and is below the scale at which bulk reconciliation/import is the clearer
workflow. ERPNext provides no smaller hard native limit; 20 is MCP risk policy,
not a framework assertion.

## 21. Data minimization and minimum preview

The preview should contain only:

- Draft Payment Entry intent and no-ledger-effect notice;
- Customer and Company;
- posting/reference dates and reference number;
- destination kind/display identity and Mode of Payment;
- party and bank currencies, paid and received amounts, native rates when
  cross-currency;
- each selected invoice name, posting/due date, transaction and party-account
  currency, current outstanding and requested/native allocation;
- totals, unallocated and difference;
- bounded exchange/deduction/tax summary when material; and
- explicit “Draft only; submit requires separate approval” text.

Do not expose other customer invoices, full masters, raw accounts/GL/Payment
Ledger, Bank Account numbers, IBAN/SWIFT, arbitrary custom fields, secrets,
tracebacks or unrestricted native documents.

## 22. Permission boundary

Task 49 must rely on normal Frappe/ERPNext permission enforcement and translate
exceptions safely:

- authenticate the Frappe user via the existing runtime;
- check Customer read permission;
- load every exact Sales Invoice and call its read permission check;
- require Payment Entry create permission (and use normal-permission insert);
- read Bank Account with permission when explicitly selected;
- use native Mode of Payment/account resolution and normal Link/account checks;
- let native document validation enforce party/account/docstatus/business
  rules; and
- let generic lifecycle enforce submit/cancel/delete permissions.

Do not define an MCP role matrix. `get_outstanding_reference_documents()` only
explicitly checks party read permission, so it cannot replace per-source checks.
The whole request fails if even one reference is unreadable; never reveal which
other invoices were valid beyond the bounded requested identities.

## 23. Direct and REST design

Both transports must call one authoritative service. Direct wrappers pass the
typed model through `execute_tool_with_context()`. REST adds two fixed operation
registry entries using the same input models/service; it accepts no DocType,
method path, site or identity chosen by the caller. Confirm approval remains
authoritative where the service executes, following the existing remote
approval design. Arguments and results must remain JSON-safe and identical in
meaning across transports.

Accounts owns the tools. Do not register them in Sales/Purchase and do not
require those MCP processes; permitted Sales Invoices are on the same site.

## 24. Risk classification

| Capability | Relative risk | Recommended sequence |
|---|---:|---|
| single-invoice receipt | Medium | Existing Task 45 |
| explicit multi-invoice receipt, exact total | Medium-high | Task 49 |
| auto-allocation | High | Later dedicated strategy audit |
| unallocated receipt | High | Later advance boundary |
| customer advance | High | Separate capability/audit |
| supplier multi-invoice payment | High | Separate Pay/withholding audit |
| reconciliation | Very high | Separate existing-payment lifecycle |
| internal transfer | High | Separate accounts/destination design |
| Journal Entry | Very high | Do not generalize from Payment Entry |

## 25. Capability matrix

| Capability | Native support | Risk | Decision | Reason |
|---|---|---:|---|---|
| explicit Customer multi-SI receipt | Multiple PE reference rows | Medium-high | Task 49 | Deterministic intent and native validation |
| partial allocation per invoice | Yes, up to current outstanding | Medium | Task 49 | Explicit positive amount |
| auto oldest allocation | Ordered native allocator | High | Defer | Strategy/order/credits/terms need explicit policy |
| unallocated remainder | `unallocated_amount` and party GL row | High | Reject | Overlaps advances/reconciliation |
| cross-currency bank | Native paid/received/rates | Medium-high | Bounded support | Require bank amount when currencies differ; no rate input |
| mixed invoice currencies | Possible only through one party account | High | Reject V1 | Ambiguous review/FX semantics |
| term-specific references | Native split rows and schedule update | High | Reject V1 | Invoice-only input cannot identify terms |
| early discounts | Single-source native factory | High | Reject V1 | No native multi-source composer |
| customer advance | Native unallocated/separate-account behavior | High | Defer | Different business intent |
| reconciliation | Native Payment Reconciliation | Very high | Separate | Existing payment allocation, not creation |

## 26. Task 49 test matrix

### Contract and core service

- two invoices, both fully allocated;
- three invoices with full/full/partial allocation;
- exact example 10,000 + 8,000 + 12,000 = 30,000;
- amount precision equality and rounding boundary;
- fully paid, cancelled, Draft and nonexistent invoice;
- duplicate invoice input;
- per-row allocation above outstanding;
- allocations above receipt; receipt above allocations;
- zero, negative, boolean, NaN/infinite allocation/amount;
- 1, 2, 20 and 21 reference boundaries;
- return/credit-note/negative outstanding rejection;
- unexpected zero native row/missing selected outstanding row;
- deterministic order and fingerprint.

### Party, Company and accounts

- mismatched explicit Customer;
- two different Customers;
- two Companies;
- same Company/customer but different receivable accounts;
- invoice-discounting effective-account difference;
- same account currency but different accounts;
- different party-account currencies;
- disabled receivable/destination account;
- Bank Account wrong Company, unreadable, disabled or without ledger account;
- Mode of Payment missing/changed default and conflicting destination inputs.

### Currency

- INR invoices/INR bank;
- USD invoices/USD bank;
- USD invoices/INR bank with bank amount;
- missing/invalid bank amount for differing currencies;
- mixed invoice transaction currency rejection;
- native rate change after prepare;
- native exchange-gain/loss summary and zero difference;
- no caller exchange-rate field.

### Terms, discounts, tax and requests

- no terms;
- template present but term allocation disabled;
- one/multiple enabled terms rejected;
- partial term and changed term after prepare rejected/stale;
- eligible early discount rejected at both prepare and confirm;
- unexpected taxes/withholding/non-FX deduction rejected;
- Payment Request candidate/link behavior recorded without implicit allocation.

### Approval and concurrency

- prepare creates no Payment Entry/GL/Payment Ledger record;
- confirm creates exactly one Draft and no ledger effect;
- `claim_for_confirm_write()` one-shot, expiry, cancel, wrong user/site/action,
  trusted-human and agent-delegated shared-policy regression;
- any one invoice outstanding/modified/status/account/term drift fails all;
- Customer/Company/destination/default/rate drift fails all;
- simultaneous confirms of one token create at most one Draft;
- separate approvals racing on the same invoices and later submit behavior;
- rollback proves no partial Draft/reference creation on failure.

### Lifecycle

- enriched submit preview lists every reference and totals;
- submit updates all outstanding values correctly;
- partial residual remains correct;
- stale outstanding before submit is rejected;
- cancel restores all reference outstanding and schedules;
- Draft delete and cancelled delete follow existing policy;
- no direct MCP GL/Payment Ledger writes.

### Permissions and transport

- Customer unreadable; one selected invoice unreadable; PE create denied;
- Bank Account permission failure and native Account/Link failure;
- direct and REST parity for success and every bounded error;
- malformed/extra payload, non-object allocations and identity/site boundary;
- no remote arbitrary operation/import/DocType;
- typed `tools/list` input/output schemas omit `ctx`.

### Regression

- Task 45 single-invoice prepare/confirm behavior unchanged;
- Task 47 Payment Entry get/query/aggregate unchanged;
- Accounts inventory/catalog/registry/profile assertions;
- Sales and Purchase profile inventories unchanged;
- shared approval, lifecycle and REST suites;
- generated `docs/TOOLS.md`, contract audit, compile and diff checks.

No site-writing tests were run during this audit; these are Task 49 requirements.

## 27. Direct answers to the required questions

1. **Outstanding API:** `payment_entry.get_outstanding_reference_documents()`
   backed by `accounts.utils.get_outstanding_invoices()` and Payment Ledger.
2. **Reference/allocation APIs:** native outstanding rows plus
   `set_missing_ref_details()`/normal validation; the UI auto-allocator is
   `PaymentEntry.allocate_amount_to_references()`.
3. **High-level multi-invoice factory:** none found in the installed version.
4. **Construction:** start from `frappe.new_doc("Payment Entry")` and native
   derived defaults/rows, not the first-invoice factory or reconciliation.
5. **Same Customer:** yes.
6. **Same Company:** yes.
7. **Same party account:** yes for normal invoice references.
8. **Same party-account currency:** necessarily yes.
9. **Mixed invoice currencies:** only potentially when one party account can
   carry them; reject in V1.
10. **Allocated amount currency:** party/receivable account currency.
11. **Receipt above allocations:** native supports it.
12. **Remainder:** `Payment Entry.unallocated_amount` and a party GL row.
13. **Allow remainder in Task 49:** no.
14. **Partial per invoice:** yes, positive and not above current outstanding.
15. **Payment Terms:** separate rows keyed by invoice and payment term when the
   template enables term allocation.
16. **Select terms explicitly:** yes in any future term-aware contract; Task 49
   rejects enabled term allocation.
17. **Early discounts:** single-invoice factory calculates them from reference
   date and creates deductions/tax-loss splits; reject in Task 49.
18. **Duplicates:** identical invoice/term/request keys are rejected; V1 rejects
   any duplicate invoice input.
19. **Fully paid before confirm:** fresh lookup/validation fails the whole
   confirmation.
20. **Cancelled before confirm:** fresh docstatus/outstanding checks fail all.
21. **Native stale rejection:** yes for missing, fully/partly paid and excessive
   allocation, though MCP fingerprint covers broader reviewed state.
22. **Additional fingerprint:** all source/account/currency/term/date/default,
   native amount, rate and bounded deduction/tax state listed above.
23. **Any material change:** fail whole confirm and re-prepare.
24. **Drift after Draft:** Draft reserves nothing; another payment can make it
   stale.
25. **Submit validation:** normal Payment Entry validation refreshes reference
   details and latest Payment-Ledger outstanding before GL creation.
26. **Payment Ledger:** submit creates per-reference ledger effects through the
   normal GL pipeline.
27. **GL:** one party line per allocated invoice, one bank line, plus only
   applicable native remainder/deduction/tax lines.
28. **Mode of Payment:** Task 45 abstraction remains sufficient as one explicit
   destination source.
29. **Bank Account:** Task 45 fallback remains sufficient with Company,
   permission, account and currency checks.
30. **Bank amount:** needed when destination currency differs; no FX override.
31. **Posting date:** include optional, resolve at prepare and freeze.
32. **Maximum references:** 20.
33. **Customer input:** require it and validate every invoice.
34. **Explicit allocations:** required.
35. **Auto-allocation:** deferred.
36. **Minimum preview:** identities, dates, destination/currencies, each current
   outstanding/allocation, totals, material adjustments and Draft notice.
37. **Exact Task 49:** specified below.

## 28. Risks and limitations

- Findings are source/static evidence for the exact commits above, not live
  database behavior.
- The native outstanding endpoint's per-invoice permission behavior is not
  sufficient by itself; Task 49 must add explicit source permission checks.
- Payment Request matching during save and installed regional hooks require
  focused integration tests before allowing any unexpected mutation.
- Native submit validation reduces but does not prove elimination of every
  concurrent transaction race; no custom lock is recommended without a
  reproducible failing test.
- Mixed invoice currency, term allocation, discount composition and advance
  accounting are deliberately unsupported even where lower-level ERPNext
  primitives exist.
- No production Python, contract, profile, tool, test, DocType, site record or
  accounting ledger was changed by Task 48.

## 29. Exact next task

### Task 49 — Accounts V1: Explicit Multi-Invoice Customer Receipt as Draft

Implement exactly two typed Accounts tools, provisionally
`prepare_multi_invoice_customer_receipt` and
`confirm_multi_invoice_customer_receipt`, backed by one authoritative service.
Require explicit Customer, 2–20 unique exact submitted Sales Invoice names,
positive explicit allocations in their one shared receivable-account currency,
and exact equality between receipt and allocation total. Use native
Payment-Ledger outstanding retrieval and normal Payment Entry reference/
document validation. Require common Customer, Company, effective receivable
account, party currency and invoice transaction currency. Reject returns,
enabled term allocation, eligible early discounts, unallocated remainder,
tax/withholding/non-FX deduction rows, auto-allocation and reconciliation.

Reuse Task 45's mutually exclusive Mode of Payment/Bank Account destination,
reference fields, optional cross-currency bank amount and bounded remarks;
include an optional posting date resolved and frozen at prepare. Prepare writes
nothing. Confirm uses `claim_for_confirm_write()`, performs a complete fresh
native rebuild/fingerprint comparison and inserts one Draft only. Keep generic
submit/cancel/delete, but enrich Payment Entry submit preview/fingerprint with
all reference allocations and fresh outstanding state. Add direct/REST fixed
operation parity, Accounts-only registry/profile/catalog entries, the complete
test matrix above, and no generic Payment Entry builder or public accounting
account/exchange/tax/deduction fields.
