# Accounts / Payment Entry Native Flow Audit

**Task:** 44 — Accounts Profile + Payment Entry Native Flow Audit  
**Date:** 2026-09-14  
**Scope:** inspection and architecture only; no production implementation

## Executive conclusion

The clean handoff is the submission of a Sales Invoice. Sales remains the owner
of the invoice and its receivable; Accounts owns the subsequent customer
receipt and Payment Entry lifecycle:

```text
Sales profile                         Accounts profile
submitted Sales Invoice ───────────▶ prepare customer receipt
  receivable exists                     ↓ native get_payment_entry
                                       Draft Payment Entry
                                           ↓ generic lifecycle submit
                                       GL + Payment Ledger + reduced outstanding
```

The installed native factory is:

```python
erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry(
    dt, dn, party_amount=None, bank_account=None, bank_amount=None,
    party_type=None, payment_type=None, reference_date=None,
    created_from_payment_request=False,
)
```

It returns an unsaved, unsubmitted `Payment Entry` document. It does not
create accounting data. The future V1 should expose a narrow business-intent
pair, recommended names `prepare_sales_invoice_payment` and
`confirm_sales_invoice_payment`, with shared approval and fresh native rebuild,
and should create a Draft only. Generic lifecycle `submit`, `cancel`, and
`delete` should remain separate approved actions. No raw debit/credit rows,
manual outstanding updates, reconciliation, or Journal Entry should be added.

Task 45 should initially support a submitted Sales Invoice, one Customer,
one Receive Payment Entry, native full/partial allocation, and a bounded bank
or cash destination choice. Mode of Payment should be preferred when its
configured account is sufficient; a Bank Account is the safer explicit
fallback. Multi-invoice, advances, reconciliation, supplier payment, internal
transfer, caller deductions/taxes, and Payment Request are later slices.

Static source evidence is strong. A live authenticated MCP/site transaction,
custom fields/property setters, exact company defaults, exchange-rate data,
and installed optional-app behavior were not executed in this audit.

## Current MCP baseline

The current app checkout is on `master`; the bench root is not a Git checkout.
The app has Sales and Purchase profiles only:

| Area | Confirmed current state |
|---|---|
| `MCPProfile` | `sales`, `purchase`; no `accounts` enum |
| Sales profile | Customer, Item, Quotation, Sales Order, Delivery Note, Sales Invoice, read/query/aggregate, PDF/email, and lifecycle |
| Purchase profile | Supplier, purchase Item, Purchase Order, read, PDF/email, and lifecycle |
| Accounts profile | not implemented or registered |
| Sales Invoice lifecycle | submit/cancel/delete are allowed; generic update/child-add are not |
| REST | fixed typed remote-operation registry calls the same services; no Accounts operations |
| Approval | shared `ApprovalStore.claim_for_confirm_write()` and action/site/user binding are already used by write workflows |

Evidence: `mcp_erpnext/settings.py:24-29,93-98,169-174`,
`profiles/sales.py:8-38`, `profiles/purchase.py:8-28`,
`tools/__init__.py:14-27`, `services/common/lifecycle.py:17-38`, and
`remote_operations.py:1-5,247-259`. The current Sales Invoice read report
already treats `outstanding_amount` as the stored ERPNext value and leaves
Payment Entry allocation outside its scope.

No existing MCP Accounts implementation, Payment Entry contract, tool,
service, or remote operation was found. The task specification itself remains
an existing untracked file; it was not modified.

## Installed runtime evidence

The installed checkout is ERPNext `version-16`, commit
`4048fb70e14d1843956fcdabb7c3cca75a1cbcdd`, version `16.34.2` from
`apps/erpnext/erpnext/__init__.py:7-10`.

Primary files inspected:

* `erpnext/accounts/doctype/payment_entry/payment_entry.py`
* `payment_entry.json`, `payment_entry.js`, and `test_payment_entry.py`
* `erpnext/accounts/doctype/payment_reconciliation/payment_reconciliation.py`
* `erpnext/accounts/utils.py` and `accounts/general_ledger.py`
* `erpnext/controllers/accounts_controller.py`
* Sales Invoice source and installed `india_compliance` hooks

Runtime authority remains the target site metadata and installed hooks. The
JSON file is a baseline, not a substitute for runtime `frappe.get_meta()`.

## Exact native factory and call chain

### Factory contract

`payment_entry.py:2889-2900` defines the exact callable shown above.
`get_payment_entry`:

1. checks `frappe.has_permission("Payment Entry", ptype="create", throw=True)`;
2. loads the source with `frappe.get_doc(dt, dn)` and calls `doc.check_permission()`;
3. derives party type (`Sales Invoice` → `Customer`) and party account (`Sales Invoice.debit_to`, or invoice-discounting account);
4. derives payment type (`Receive` for a positive Sales Invoice outstanding);
5. derives grand total/outstanding, using `party_amount` as an amount override when truthy;
6. resolves the bank/cash destination through `get_bank_cash_account()`;
7. derives paid/received amounts, using `bank_amount` where currencies differ;
8. applies configured early-payment discount logic;
9. constructs `frappe.new_doc("Payment Entry")` and fills native fields;
10. adds one reference row, or payment-term rows when term-based allocation is enabled;
11. runs document defaulting (`set_missing_values`, reference details, dimensions,
    exchange rate, amount calculation) and optionally links open Payment Requests;
12. returns the document at `payment_entry.py:2890-3060`.

The factory does not call `insert()` or `submit()`. The UI uses the same factory;
the installed tests explicitly call `insert()` and `submit()` after setting
reference fields, for example `test_payment_entry.py:166-196` and
`249-277`.

### Account and amount derivation

`set_party_type`, `set_party_account`, `set_party_account_currency`, and
`set_payment_type` are at `payment_entry.py:3263-3297`. For a Sales Invoice,
the native party account is the invoice receivable (`debit_to`) unless invoice
discounting supplies another account. `set_grand_total_and_outstanding_amount`
at `3301-3320` uses the invoice outstanding unless `party_amount` is supplied.

`get_bank_cash_account` at `3242-3260` calls the native default bank/cash
resolver with company, invoice Mode of Payment, and optional raw account.
`set_paid_amount_and_received_amount` at `3323-3348` handles same-currency
and cross-currency amounts; `bank_amount` controls the bank-side amount when
needed. The factory also copies invoice `mode_of_payment`, cost center,
letterhead, project, party bank account, and company default Bank Account
metadata (`2893-2978`).

### Validation and stale state

`PaymentEntry.validate()` at `172-198` runs defaults, account/currency and
reference validation, amount/tax calculation, duplicate checks, latest
outstanding validation, supplier blocking, withholding hooks, and status
calculation. References must point to a submitted document and the same party
(`668-742`).

For Customer/Supplier references, `validate_allocated_amount()` calls
`validate_allocated_amount_with_latest_data()` (`366-379`, `420-503`). That
reloads current outstanding reference documents with company, party, payment
type, party account, payment terms, and advance-account context. It rejects a
fully paid reference, stale partially-paid outstanding data, over-allocation,
and missing payment-term rows. This is native protection, not a transaction
lock; MCP must still rebuild fresh and compare its approval fingerprint.

## Minimum safe MCP input

For the first capability, the caller supplies business intent and payment
facts; ERPNext supplies accounting facts.

| Field | Classification | V1 conclusion |
|---|---|---|
| Sales Invoice name | A — caller required | exact submitted source identifier |
| payment amount | B — caller optional | omit means native outstanding/full amount; supply for partial payment |
| bank amount | B — caller optional | only needed when bank and party currencies differ |
| Mode of Payment | B — caller optional | preferred human-facing destination if configured |
| Bank Account | B — caller optional | explicit business-level fallback; resolve ledger account natively |
| reference number/date | A before submit for normal bank transaction | prepare may show missing; submit validation requires both when a transaction reference is required |
| posting date | B | future adapter may accept a date, but factory hardcodes `nowdate()`; do not silently pretend the factory honors it |
| company | C/D | derive from invoice; never caller-controlled for this flow |
| customer, party type, payment type | C | derive from invoice and native rules |
| party account, paid_from, paid_to | C/D | derive from invoice, Bank Account, Mode of Payment, Company, and account metadata |
| allocated amount | C for V1 | native reference allocation; do not expose as an independent field |
| unallocated amount | C | native calculation; preview only |
| source/target exchange rate | C/D | native rates and document/account currencies; no LLM formulas |
| currency/account currencies | C/D | native metadata; display bounded values only |
| cost center/project/dimensions | D/B | inherit native source/defaults; only expose explicit fields after a DocType-local audit |
| Payment Term | C/B edge case | native term rows; caller may need a term selector only in a later term-aware contract |
| deductions/write-off/bank fees | E for V1 | no arbitrary account lines |
| taxes / withholding rows | E for V1 | native hooks remain authoritative; no caller-configurable rows |
| remarks | B | optional bounded text, subject to normal validation |
| payment request / advance flags | E for V1 | separate business intents, not free-form switches |
| internal transfer fields | E | separate later capability |

Company, customer, party account, raw ledger accounts, GL lines, exchange
formulas, advance-account switches, tax rows, and approval policy must not be
LLM-selected. The public contract should reject contradictory combinations
(for example both Mode of Payment and unrelated raw ledger overrides) or let
the native helper decide through a small explicit adapter.

## Full, partial, and overpayment behavior

### Full payment

For a submitted invoice with outstanding 11,800, the factory normally creates
one `Payment Entry Reference` for the Sales Invoice with total/outstanding/
allocated amount 11,800, and paid/received amount derived from the party and
bank currencies. It remains Draft until insert. On submit, the reference is
validated against current outstanding; the invoice becomes outstanding 0 and
normally status `Paid`. Installed tests verify the same result and restoration
on cancellation (`test_payment_entry.py:249-277`; USD example
`166-196`). The exact account names and ledger amounts depend on the target
Company, invoice, account currencies, exchange rates, dimensions, discounts,
and hooks, so MCP must preview native values rather than hard-code 11,800 GL
rows.

### Partial payment

Pass `party_amount` to the factory for the party-side amount, then retain the
native reference and amount calculations. The installed tests also demonstrate
the lower-level equivalent of setting `received_amount` and reference
`allocated_amount` before submit (`test_payment_entry.py:1184-1195`). A safe
adapter should prefer `party_amount`, rebuild the document, and let native
validation calculate the resulting unallocated amount. For 5,000 against
11,800, the expected native business result is allocated 5,000, remaining
invoice outstanding 6,800, and no unallocated remainder when the bank-side
amount is equal; exact rounding/currency/term values are site-dependent.

Payment schedules are updated on submit by `update_payment_schedule()` and
reversed on cancel (`payment_entry.py:802-840`, `203-212`, `297-319`). Task 45
may support native partial payment because the helper and tests prove it, but
must reject or explicitly defer term-specific allocation until the preview
shows the required term rows.

### Overpayment and unallocated amount

The factory's single-invoice row is initially bounded by source outstanding;
the Payment Entry model nevertheless has an `unallocated_amount` field. On a
customer receipt, `add_party_gl_entries()` creates a separate party-side GL
component for an unallocated amount (`payment_entry.py:1434-1466`). Native
validation protects ordinary positive allocation against current outstanding;
overpayment must therefore not be invented by MCP. It should either be
rejected by the narrow invoice-payment contract or explicitly modeled as an
unallocated/customer advance in a later capability. Such excess remains on
the customer party account and can be reconciled later; it must not be
silently forced into the invoice.

## Advances and multiple references

### Customer advance

`get_payment_entry` requires a source doctype/name, so a no-document advance
is a separate `frappe.new_doc("Payment Entry")` business flow, not the
Sales-Invoice factory. A Sales Order can be a valid Customer Receive reference
and the installed test shows a 500 advance against an SO later being pulled
into a Sales Invoice (`test_payment_entry.py:198-220`). The native code also
supports `book_advance_payments_in_separate_party_account`; advance GL entries
are constructed by `add_advance_gl_entries()` (`payment_entry.py:1468-1587`)
and advance-account selection is Company/party configuration.

No-document advance, later invoice allocation, separate advance liability,
and India Compliance advance-tax behavior need a separate contract and tests.
Defer them from V1.

### Multiple Sales Invoices

The Payment Entry child table supports multiple `references`; native
reconciliation retrieves outstanding invoices through `get_outstanding_invoices`
and `get_outstanding_reference_documents` (`payment_entry.py:2301+` and
`accounts/utils.py`). Each reference is party-checked, submitted, account-
checked, duplicate-checked, and latest-outstanding-validated. The same Customer,
Company, party account, and compatible currency/account context are required by
these validations. Payment terms can expand one invoice into multiple term rows.

The factory itself accepts one `(dt, dn)` source and creates one source
reference. A generic multi-invoice adapter would need to retrieve and construct
all rows without bypassing native validation. Therefore V1 is Option A,
single-invoice intent. A later generic `prepare_customer_payment(references=[])`
can be built over the same internal native Payment Entry adapter after a
dedicated allocation audit.

## Payment Terms, Mode of Payment, and bank selection

If the source has a Payment Terms Template with
`allocate_payment_based_on_payment_terms`, the factory calls
`get_reference_as_per_payment_terms()` and adds term-specific rows
(`2890-2998`). Missing or stale term allocation is rejected by
`validate_allocated_amount_with_latest_data()` (`451-495`). Early-payment
discounts are applied using `reference_date`; installed tests verify both
percentage and amount discounts, discount-loss deductions, and payment
schedule updates (`test_payment_entry.py:278-391`, `394-447`). The adapter
must show term rows/discounts in the preview and must not flatten them.

The factory copies the invoice Mode of Payment. The native resolver tries Bank
then Cash with Company, Mode of Payment, and optional account
(`3242-3260`). Missing default account can leave the factory unable to build a
usable Payment Entry and should produce a native error, not an MCP fallback
account. A Mode of Payment is safer for LLM-facing intent than arbitrary
ledger-account selection, but it is not universally sufficient; an explicit
Bank Account may be required.

`bank_account` is a Bank Account or account input to the native bank/cash
resolver. Bank Account details populate bank metadata and the mapped ledger
account (`344-356`, `2966-2978`). Party bank account and Company default bank
account are distinct from the ledger `Account`; raw account names should stay
internal except for bounded accounting review.

`validate_transaction_reference()` at `1240-1272` enforces the installed
reference rules. The Payment Entry JSON marks reference fields and the
transaction-reference UI behavior; bank/reference requirements can vary by
transaction configuration. Task 45 should require `reference_no` and
`reference_date` for the normal bank receipt path before submit, while allowing
native validation to reject cash/configuration combinations that differ.

## Payment types and future supplier compatibility

The installed select allows `Receive`, `Pay`, and `Internal Transfer`
(`payment_entry.py:623-629`; JSON metadata). `Receive` uses party receivable
and destination bank/cash; `Pay` uses supplier payable and source bank/cash;
`Internal Transfer` clears party/references and requires distinct accounts.
GL construction is shared: `add_party_gl_entries()` and
`add_bank_gl_entries()` (`1328-1624`).

The same factory supports Purchase Invoice and the installed tests use
`get_payment_entry("Purchase Invoice", ...)` (`test_payment_entry.py:222-247`),
with `set_party_type`/`set_party_account` selecting Supplier and `credit_to`.
Supplier on-hold validation exists in `ensure_supplier_is_not_blocked()` and
Purchase Invoice on-hold validation is in reference validation
(`payment_entry.py:724-728`). Tax withholding is also part of the shared
controller. This proves future Supplier Pay compatibility without expanding
Purchase MCP now.

Internal transfer and standalone receipt are materially broader and more
financially risky; defer them. Journal Entry is an accounting adjustment
mechanism, not the routine payment path, and is explicitly not recommended.

## Multi-currency and exchange differences

The native model stores party/bank account currencies, paid/received amounts,
base amounts, source/target exchange rates, and transaction currency. The
factory selects party account currency from the invoice/account
(`3281-3286`), calculates cross-currency paid/received amounts
(`3323-3348`), and the document derives rates from the source/reference or
native exchange-rate lookup (`635-661`). Never reproduce these formulas in
MCP.

The installed tests cover USD receivable/USD bank and USD receivable/INR bank,
including explicit `bank_amount`, source rate, exchange loss, and remaining
outstanding (`test_payment_entry.py:166-196`, `449-565`, `638-666`). The
conceptual cases classify as follows:

| Case | Native handling | V1 |
|---|---|---|
| INR invoice / INR bank | same-currency amounts and base values | pass through |
| USD invoice / USD receivable / USD bank | party and bank amount in USD; base conversion native | pass through with bounded preview |
| USD invoice / INR bank | `party_amount` and `bank_amount` may differ; native rates/difference | allow only when preview and required input are explicit |
| invoice currency differs from party account | native invoice/account currency and reference exchange details | do not custom-calculate |
| bank currency differs from invoice | native source/target rate and received amount | defer if required rate/amount is absent |

Exchange differences can create deductions and/or exchange gain/loss Journal
Entries. `set_exchange_gain_loss`, `make_exchange_gain_loss_journal`, and
`make_gl_entries` are native (`971-977`, `1328-1340`); tests show exchange-loss
deductions and GL effects (`534-565`). V1 must not expose source/target rates,
deduction accounts, or formulas as free-form LLM inputs. It may pass native
multi-currency through only after focused site tests.

## Deductions, taxes, Payment Request, and reconciliation

Payment Entry computes `difference_amount`; submit rejects a non-zero difference
(`on_submit`, `203-212`). Native deductions are child rows with account,
cost center, and amount; their GL is generated by
`add_deductions_gl_entries()` (`1691-1713`). Early discounts and exchange
losses can populate them. Arbitrary write-off/bank-fee/account lines are out
of V1.

Payment Entry supports taxes and tax withholding. `validate()` invokes
`apply_taxes()` and `PaymentTaxWithholding.on_validate`; submit invokes its
`on_submit` (`172-212`). Payment taxes have native GL handling
(`1626-1689`). Installed India Compliance adds Payment Entry hooks for
`onload`, `validate`, `on_submit`, `on_update_after_submit`, `before_cancel`,
regional outstanding-reference and advance-payment behavior
(`apps/india_compliance/india_compliance/hooks.py:177-182,367-381,637-638`).
Therefore optional-app behavior is real in this bench, but exact site behavior
and custom fields require runtime verification. Exclude caller-configurable
tax/withholding rows from V1.

Payment Request is not required for a normal manual Sales Invoice receipt: the
factory can create Payment Entry directly. It may auto-allocate open Payment
Requests to references (`3056-3059`) and submit/cancel updates linked requests
(`321-326`). Defer Payment Request as a public business document.

Payment Reconciliation is a separate persisted process. Its source class does
not save or delete itself (`payment_reconciliation.py:72-133`), retrieves
non-reconciled Payment Entries and invoices from Payment Ledger/native
outstanding helpers (`135-220`, `372-411`), and allocates/reconciles through
native reconciliation utilities (`462-492` onward). It can create exchange
gain/loss effects (`426-460`). Defer it; do not mutate Payment Entry references
directly from MCP.

## Payment Ledger and General Ledger

Sales Invoice submission creates receivable accounting and Payment Ledger
state through the Accounts Controller. Payment Entry submission calls, in
order, zero-difference validation, withholding, Payment Request updates,
payment-schedule updates, `make_gl_entries`, outstanding/reference updates,
status update, and subscription-invoice update (`203-212`).

`make_gl_entries()` builds and processes the native GL map, calls shared
`general_ledger.make_gl_entries`, handles exchange gain/loss, and adds advance
GL entries (`1328-1340`). For a normal Receive reference, the native map
contains destination bank/cash debit and party receivable credit; reference
rows carry `against_voucher_type/name` and party metadata
(`1342-1432`, `1608-1624`). Unallocated receive amounts remain on the party
account (`1434-1466`). Taxes, deductions, dimensions, currencies, advances,
and exchange entries add native effects.

Payment Ledger entries and invoice outstanding are maintained by ERPNext's
ledger/outstanding machinery, not by the MCP. There is no safe MCP operation
to insert/update Payment Ledger Entry rows. Cancellation reverses GL, payment
schedule, outstanding/reference, advance links, Payment Request state, and
subscription status (`297-319`), while native controllers manage ledger
reversal/repost details.

## Cancel and delete

`PaymentEntry.on_cancel()` explicitly ignores linked ledger/repost/advance and
tax-withholding doctypes for the cancellation workflow, invokes the Accounts
Controller cancellation, reverses withholding/schedule/GL, updates
outstanding, delinks advances, and resets status (`297-319`). Cancellation is
not a cascade delete and must not be expanded by MCP.

Frappe document semantics require a submitted Payment Entry to be cancelled
before deletion; a Draft can be deleted through normal permission checks, and
cancelled deletion depends on linked-document protections and installed site
policy. No Payment Entry-specific `on_delete` implementation was found in the
inspected source. Future Accounts lifecycle should add only exact-target
`submit`, `cancel`, and `delete`, using the existing native document methods and
permission/error translation.

## Native authority and permission boundary

The factory enforces Payment Entry create permission and source document
permission. `get_reference_details` enforces source read permission
(`2800-2806`). Payment Entry document validation performs party, submitted
reference, account, currency, duplicate, latest-outstanding, disabled-account,
closed-period, tax, and hook validations. Final insert/submit/cancel must use
Frappe document APIs under the authenticated identity.

MCP may validate shape, bind approval, and translate exceptions, but should not
duplicate native accounting authorization or precompute business permission
rules. Direct backend identity is the Frappe session configured for the site;
REST uses the existing fixed endpoint/credential and current REST principal
model. No hard-coded site, company, party, Administrator impersonation, or
caller-controlled identity belongs in Task 45.

## Approval, fingerprint, and stale state

The existing prepare/confirm pattern fits:

```text
prepare → native unsaved preview → server-side ApprovalStore token
confirm → atomically claim token → fresh native rebuild → fingerprint check
        → permission-aware insert Draft only
```

The approval is bound to action, site, and user and must be one-shot. The
fingerprint should cover at least: source invoice name/docstatus/modified,
customer/company, invoice outstanding and currency, party account/currency,
payment amount and bank amount, Mode of Payment/Bank Account identity, resolved
paid-from/paid-to accounts and currencies, reference date/no, posting date if
supported, native reference rows/payment terms, discounts, exchange rates,
deductions/taxes summary, and native preview version. Do not fingerprint raw
GL rows generated by the MCP; use the native preview summary and rebuild.

If another process pays the invoice, cancels it, changes terms, changes account
defaults, or changes rates after prepare, fresh rebuild or native validation
must return a stale/failed confirmation and create nothing. Native latest
outstanding checks remain the final authority; MCP fingerprinting adds clear
approval semantics and detects material preview drift before insert.

## Public shape and profile decision

| Candidate | Safety | Decision |
|---|---|---|
| invoice-specific prepare/confirm | narrow intent, minimal fields, direct continuation | **Task 45** |
| generic customer receipt | supports multiple/unallocated but larger allocation contract | later |
| generic Payment Entry | exposes payment type/accounts/references and accounting internals | reject as public V1 |
| explicit business tools over shared adapter | clear intent with reusable internal native engine | target long-term architecture |

Recommended public V1:

```text
MCP_PROFILE=accounts
prepare_sales_invoice_payment(sales_invoice, amount?, mode_of_payment?,
                              bank_account?, reference_no?, reference_date?,
                              bank_amount?, remarks?)
confirm_sales_invoice_payment(approval_token, confirm)
```

The exact contract must make source invoice required, allow only one source
reference, derive Customer/Company/accounts/payment type, reject arbitrary
account/GL/deduction/tax fields, and return a bounded preview. Confirm inserts
Draft only. Generic lifecycle handles later submit/cancel/delete.

Add an independent Accounts profile registry, not a requirement for Sales or
Purchase processes to be running. It should call the same Frappe site and
shared internal helpers; it may reuse narrow internal Customer/Sales Invoice
resolution but must not duplicate those public tools merely to make Accounts
run. Accounts business configuration remains ERPNext configuration; profile
registration is MCP capability/security configuration, not a duplicate set of
ERPNext feature flags.

## Read, query, aggregate, PDF, and email recommendations

Future `get_payment_entry` should use a DocType-local allowlist and expose:
name/status/docstatus, payment type, company, posting date, party type/party,
party name, Mode of Payment, bounded destination/account review, currencies,
paid/received/allocated/unallocated amounts, reference number/date, bounded
reference summaries, bounded deduction summary, and remarks. Exclude full
custom metadata, raw GL/Payment Ledger rows, full bank numbers, secrets,
arbitrary child tables, and unrelated customer data. Runtime metadata must
control custom-field availability.

Future `query_payment_entries` should use typed filters: date range,
docstatus/status, payment type, party type/party, company, Mode of Payment,
amount range, and reference number, with projection allowlists, pagination,
permission-enforcing Frappe reads, and a specialized typed linked-invoice
filter rather than raw SQL/LLM expressions.

Future `aggregate_payment_entries` can count and sum paid/received amounts or
group by payment type, status, party, Mode of Payment, and date period. Amounts
must always group by currency/account currency (or require a single currency);
do not sum mixed currencies without native normalization. Reuse the current
field-aware read/aggregate foundation and its dict aggregate syntax.

PDF is a reasonable later read capability using generic native print support,
subject to Payment Entry read/print permission and bank-reference minimization.
Email should be deferred until recipient resolution and sensitive payment
reference exposure are explicitly bounded. Neither is part of Task 45.

## Data minimization

The approval preview needs only: target Payment Entry intent, source Sales
Invoice, Customer, Company, outstanding, payment/allocated/unallocated amount,
currency, posting/reference dates, human-readable bounded destination, and
exchange/discount/deduction summary only when material. It should not expose
Chart of Accounts, full account lists, raw GL/Payment Ledger rows, complete
Customer data, bank numbers/IBAN/SWIFT, unrelated invoices, internal flags,
secrets, or tracebacks.

## Optional applications

India Compliance is installed in this checkout and has verified Payment Entry
hooks, including validation/submit/cancel and regional outstanding/advance
overrides noted above. The audit does not assume every hook changes every
Customer Receive case. Task 45 must use normal Frappe/ERPNext document hooks
and remain optional-app neutral; it must not copy GST or withholding rules.
Runtime site hooks/property setters and custom fields must be captured during
Task 45 metadata and integration verification.

## Risk classification and capability matrix

| Capability | Native support | Risk | V1 decision | Reason |
|---|---|---:|---|---|
| SI → customer Receive PE | yes | draft financial write | **include** | smallest continuation; native factory |
| partial SI payment | yes | draft financial write | **include with native bounds** | `party_amount` and tests prove support |
| multi-SI receipt | yes in PE references | high | defer | larger allocation/stale contract |
| customer advance | yes | high | defer | separate no-source/advance-account flow |
| standalone receipt | yes via native document | high | defer | no invoice anchor and reconciliation need |
| supplier PI payment | yes | high | defer | future-compatible shared engine; Purchase frozen |
| internal transfer | yes | very high | defer | no party/reference and fund-transfer risk |
| get Payment Entry | Frappe read | read | later | field policy/runtime metadata needed |
| query Payment Entry | Frappe query | read | later | linked-reference query design needed |
| aggregate Payment Entry | Frappe query | read | later | currency-safe semantics needed |
| submit/cancel/delete | native lifecycle | ledger/reversal | **reuse generic lifecycle** | exact target, separate approval |
| PDF | native print | read | later | bounded sensitive output |
| email | generic/native support | external disclosure | defer | recipient and reference risk |
| Payment Reconciliation | native process | high | defer | submitted-reference mutation/repost |
| Payment Request | native document | medium/high | defer | separate business process |
| Journal Entry | native document | very high | exclude | adjustment engine, not routine payment |

## Task 45 test and verification matrix

Task 45 must use an explicitly authorized throwaway/test site for real document
creation. Static unit tests alone must not be reported as live accounting
verification.

| Area | Required cases |
|---|---|
| Invoice | full, partial, overpayment policy, fully paid, cancelled, wrong Customer/reference |
| Terms | one term, multiple terms, term-based allocation, early discount, discount loss |
| State | stale outstanding, concurrent payment attempt, changed terms/defaults/rates |
| Defaults | Mode of Payment bank/cash default, explicit Bank Account, missing default, wrong Company, disabled account |
| Currency | INR/INR, USD/USD, USD/INR, account mismatch, exchange gain/loss |
| Approval | prepare no write, action/site/user binding, expiry, one-shot, fingerprint drift, confirm Draft only |
| Lifecycle | submit, cancel/outstanding restoration, delete Draft, cancel-before-delete and links |
| Native effects | GL/Payment Ledger/outstanding/payment schedule/Payment Request/hooks |
| Permissions | source read, Payment Entry create/insert/submit/cancel/delete, denied party/account |
| Read | allowlist, pagination, filters, linked invoice, permission behavior |
| Aggregate | count/sum/group and mixed-currency rejection/grouping |
| Transport | direct parity, fixed REST operation, malformed/unknown operation, identity/site boundary |
| Regression | Sales/Purchase profiles, Tasks 42/43, shared approval, REST backend |

Also verify runtime `frappe.get_meta()` for Payment Entry and child tables,
Company, Customer, Supplier, Account, Bank Account, Mode of Payment, Payment
Terms, Payment Schedule, Sales/Purchase Invoice and Order. Capture installed
hooks/property setters without reading secrets.

## Limitations and unverified boundaries

* No live Payment Entry, GL, Payment Ledger, reconciliation, or site mutation
  was performed.
* Company defaults, account availability, currencies, custom fields, and
  permissions were not asserted against a live site.
* The factory sets `posting_date=nowdate()`; accepting a future posting-date
  input requires an adapter decision and a native validation test.
* Overpayment behavior is configuration/context-sensitive; V1 must not imply
  an unallocated or advance policy until a dedicated test proves it.
* Optional-app hooks are source-confirmed, not behaviorally tested for every
  scenario.
* Frappe generic delete behavior should be verified in the target site before
  exposing lifecycle delete.

## Exact Task 45 recommendation

**Task 45 — Accounts V1: prepare and confirm a submitted Sales Invoice customer
Receive Payment Entry as Draft**

Implement only:

1. `accounts` profile registration and independent direct/REST inventory;
2. typed `prepare_sales_invoice_payment` / `confirm_sales_invoice_payment`;
3. native `get_payment_entry("Sales Invoice", name, ...)` adapter;
4. submitted Sales Invoice and Customer-reference validation through ERPNext;
5. optional native partial amount and bank-side amount where currencies require;
6. Mode of Payment/Bank Account bounded destination selection;
7. reference number/date handling, bounded preview, approval fingerprint,
   atomic one-shot claim, fresh rebuild, and Draft insert only;
8. shared generic lifecycle submit/cancel/delete allowlisting for Payment Entry;
9. typed fixed REST operation parity and focused tests.

Do not implement multi-invoice allocation, advances, standalone receipts,
supplier payments, internal transfer, Payment Request, reconciliation,
caller deductions/taxes, Journal Entry, PDF/email, custom accounting logic,
or permission refactoring in Task 45.

## Actions not performed

Only this report should be created/updated:
`docs/inspect/ACCOUNTS_PAYMENT_ENTRY_NATIVE_FLOW_AUDIT.md`.

No Python, contract, tool, service, profile, lifecycle, REST, DocType, site,
settings, fixture, migration, dependency, or accounting data was changed.
No live accounting command, build, migration, or destructive operation was
run.
