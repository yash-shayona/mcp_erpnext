# Task 53 — Sales Order Customer Advance Payment V1 Implementation

## 1. Task Identity

**Task Number:** 53  
**Title:** Sales Order Customer Advance Payment V1 Implementation  
**Profile:** `accounts`  
**Mode:** implementation  
**Primary ERPNext authority:** native Payment Entry factory and normal Frappe document lifecycle  
**Public capability style:** explicit business-intent tools, typed contracts, shared approval, Draft-only creation

---

## 2. Objective

Implement one narrow Accounts-profile capability that allows an authenticated ERPNext user to prepare and create a **Draft Customer Receive Payment Entry against one submitted Sales Order as an advance**.

The MCP server must expose the business intent safely while ERPNext remains authoritative for:

- Customer / Company derivation;
- party account selection;
- separate customer advance account configuration;
- Payment Entry reference construction;
- Payment Terms behavior;
- paid / received amount derivation;
- currencies and exchange rates;
- validation;
- permissions;
- hooks;
- accounting semantics;
- advance state;
- GL / Payment Ledger effects after later submission.

The implementation must **not** create a second accounting or reconciliation engine.

---

## 3. Frozen Architecture Decision

The previous audit recommends native ERPNext operations and confirms that a submitted Sales Order can be used by ERPNext's Payment Entry factory as a Customer advance source.

However, this project already has a frozen Payment Entry lifecycle pattern:

```text
prepare business operation
    ->
native unsaved Payment Entry preview
    ->
shared approval
    ->
confirm business operation
    ->
insert Draft Payment Entry only
    ->
generic Accounts lifecycle submit
    ->
ERPNext accounting / ledger effects
```

Therefore **Task 53 must preserve Draft-only confirmation**.

Do **not** combine creation and submission in `confirm_sales_order_advance_payment`.

This matches the existing Accounts flows:

- Sales Invoice payment;
- multi-invoice customer receipt;
- standalone Customer Payment Entry.

The existing generic Payment Entry lifecycle remains authoritative for:

- submit;
- cancel;
- delete.

---

## 4. Business Flow

Implement:

```text
Submitted Sales Order
        |
        v
prepare_sales_order_advance_payment
        |
        v
ERPNext native get_payment_entry("Sales Order", ...)
        |
        v
bounded Draft Payment Entry preview
        |
        v
shared approval token
        |
        v
confirm_sales_order_advance_payment
        |
        v
fresh native rebuild + fingerprint comparison
        |
        v
Draft Payment Entry inserted with normal permissions
        |
        v
existing generic lifecycle submit
        |
        v
ERPNext GL / Payment Ledger / Sales Order advance state
```

Task 53 ends at **Draft Payment Entry insertion**.

Submission is intentionally separate.

---

## 5. Required Public Tools

Add exactly these Accounts-profile tools:

```text
prepare_sales_order_advance_payment
confirm_sales_order_advance_payment
```

Do not overload:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment
prepare_customer_payment_entry
confirm_customer_payment_entry
prepare_multi_invoice_customer_receipt
confirm_multi_invoice_customer_receipt
```

Do not create a generic `prepare_payment_entry` public tool.

---

## 6. Inputs

### 6.1 Prepare Input

The public prepare contract should accept only the minimum business-level inputs required for one Sales Order advance.

Required:

```text
sales_order
amount
```

Payment destination:

Exactly one of:

```text
mode_of_payment
bank_account
```

Optional only if justified by existing Accounts conventions and native behavior:

```text
reference_no
reference_date
bank_amount
remarks
```

If posting date is already frozen by current Accounts conventions and can be safely exposed, reuse the same bounded pattern. Do not introduce a new date policy solely for this task.

### 6.2 Confirm Input

Confirm should accept only:

```text
approval_token
confirm
```

No mutable business fields may be supplied again during confirm.

---

## 7. Inputs That Must Not Be Public

Do not expose:

```text
party_type
party
company
payment_type
paid_from
paid_to
party_account
advance_account
debit_account
credit_account
account
source_exchange_rate
target_exchange_rate
exchange_gain_loss_account
cost_center
project
payment_entry_reference rows
allocated_amount child rows
GL Entry rows
Payment Ledger Entry rows
Advance Payment Ledger Entry rows
ignore_permissions
ignore_links
ignore_mandatory
flags
docstatus
owner
user
site
target_doc
kwargs
arbitrary native method names
arbitrary DocTypes
```

Customer, Company, payment direction, reference type, accounts, and currencies must be server/native-derived.

---

## 8. Native ERPNext Authority

Before implementation, re-inspect the installed/current ERPNext source used by the repository.

At minimum inspect:

```text
erpnext/accounts/doctype/payment_entry/payment_entry.py
    get_payment_entry
    PaymentEntry.validate
    PaymentEntry.set_missing_values
    PaymentEntry.set_missing_ref_details
    PaymentEntry.validate_reference_documents
    PaymentEntry.validate_allocated_amount
    PaymentEntry.set_unallocated_amount
    PaymentEntry.set_liability_account
    PaymentEntry.on_submit
    PaymentEntry.on_cancel

erpnext/accounts/party.py
    get_party_account
    get_party_advance_account

erpnext/accounts/doctype/payment_entry/test_payment_entry.py

erpnext/selling/doctype/sales_order/sales_order.py

erpnext/controllers/accounts_controller.py

frappe/model/document.py
```

Also inspect any installed optional application hooks affecting Payment Entry, especially India Compliance if installed.

Installed/current source is authoritative if it differs from historical task documentation.

---

## 9. Required Native Factory Usage

The implementation must use ERPNext's native Payment Entry factory for the source document:

```python
get_payment_entry(
    "Sales Order",
    sales_order,
    party_amount=...,
    bank_account=...,
    bank_amount=...,
    party_type="Customer",
    payment_type="Receive",
    reference_date=...,
)
```

Exact arguments must be confirmed from the installed version before coding.

Do not manually construct the Sales Order Payment Entry Reference row when the native factory already provides it.

Do not copy ERPNext's allocation, account, currency, Payment Terms, or advance logic into MCP.

---

## 10. Source Eligibility

Prepare must require an exact Sales Order.

The service must verify through native/current document state that the source is eligible.

At minimum:

```text
Sales Order exists
current user can read it
docstatus == 1
Customer source is valid
Company is available
Payment Entry create permission is available
amount is positive and finite
payment destination selection is valid
```

Closed, cancelled, invalid, or otherwise natively ineligible Sales Orders must fail safely.

Do not derive eligibility only from an MCP-cached preview.

Confirm must re-read and re-evaluate the source.

---

## 11. Amount Rules

Public `amount` must be:

- numeric;
- finite;
- strictly positive;
- not boolean.

Do not implement custom accounting formulas to decide advance validity.

Use bounded MCP input validation for obvious invalid shape only.

Native ERPNext remains the final authority for:

- allowable advance;
- order totals;
- already-paid advances;
- Payment Terms behavior;
- separate advance account;
- account currencies;
- received amount;
- exchange rates;
- rounding;
- validation.

If current native behavior permits partial advances, preserve it.

If native behavior rejects an amount, return the bounded native validation result.

---

## 12. Payment Destination Resolution

Reuse the existing Accounts destination-resolution architecture wherever appropriate.

Support exactly one public selector:

```text
mode_of_payment
OR
bank_account
```

Do not allow both.

Do not accept a raw ledger Account from the client.

If `mode_of_payment` is used:

- resolve it through ERPNext-native/default account behavior;
- preserve Company and permission checks;
- do not invent a fallback account.

If `bank_account` is used:

- permission-check the Bank Account;
- ensure it belongs to the effective Company where required;
- resolve the underlying native account internally;
- do not expose sensitive bank details.

---

## 13. Separate Customer Advance Account

ERPNext Company configuration may enable:

```text
book_advance_payments_in_separate_party_account
```

Task 53 must preserve this native configuration automatically.

MCP must not expose a public flag to turn it on/off.

MCP must not allow the caller to choose the advance ledger account.

The native party / advance account resolver remains authoritative.

The bounded preview may state that the native separate-advance-account branch is active, but should avoid exposing unnecessary Chart of Accounts internals.

---

## 14. Payment Terms

The native Payment Entry factory can have Payment Terms-specific behavior.

Task 53 must not recreate or flatten Payment Terms logic.

Implementation rule:

1. call the native factory;
2. inspect the native result;
3. preserve deterministic native behavior;
4. if the resulting branch cannot be represented safely by the V1 contract, return a structured unsupported / needs-review result.

Do not:

- manually expand term rows;
- collapse term rows into an arbitrary single allocation;
- accept raw reference rows from the caller.

---

## 15. Currency and Exchange Rate

ERPNext owns:

- party account currency;
- bank account currency;
- source document currency;
- paid amount;
- received amount;
- source exchange rate;
- target exchange rate;
- exchange difference;
- gain/loss treatment.

MCP must not calculate these itself.

If cross-currency settlement requires `bank_amount`, follow the already established Accounts contract pattern.

Do not expose arbitrary exchange rates unless a later audited capability explicitly requires them.

The prepare preview must show enough resolved currency context for user approval without exposing raw accounting internals.

---

## 16. Prepare Behavior

`prepare_sales_order_advance_payment` must:

1. resolve the authenticated ERPNext user and configured site using existing runtime rules;
2. load the exact Sales Order;
3. enforce normal source read permission;
4. require submitted state;
5. validate bounded public input;
6. resolve the payment destination through existing/native helpers;
7. call ERPNext's native `get_payment_entry("Sales Order", ...)`;
8. preserve native reference / Payment Terms state;
9. run only the safe native preparation/validation steps consistent with current Accounts flows;
10. create **no database write**;
11. produce a bounded deterministic Draft preview;
12. build canonical fingerprint material;
13. create one shared approval proposal;
14. return the approval token and normal interaction directive.

Prepare must not:

- insert Payment Entry;
- submit Payment Entry;
- update Sales Order;
- write GL;
- write Payment Ledger;
- write Advance Payment Ledger;
- reconcile anything.

---

## 17. Prepare Preview

Return only bounded business information needed for approval.

Recommended preview:

```text
source Sales Order
Customer
Company
Sales Order status
payment type = Receive
advance amount
party-side currency
destination currency
received amount
Mode of Payment or safe Bank Account label
reference number/date if supplied
posting date if part of current Accounts contract
native Sales Order reference summary
native Payment Terms summary if material
native unallocated amount
separate advance account branch: yes/no
bounded remarks
warning that confirmation creates Draft only
warning that accounting effects happen only after separate submit
```

Do not return:

- raw Payment Entry JSON;
- arbitrary account lists;
- complete bank numbers;
- IBAN/SWIFT;
- raw GL rows;
- Payment Ledger rows;
- secrets;
- tracebacks;
- unrelated Customer data.

---

## 18. Approval and Fingerprint

Reuse the shared approval infrastructure.

Do not add:

- tool-local approval storage;
- process-local approval dictionaries;
- client-controlled approval mode;
- `confirm=true` self-authorization;
- new trust semantics.

Prepare fingerprint material should cover all material state needed to detect stale approval, including where available:

```text
source Sales Order name
source docstatus
source modified signal
Customer
Company
order total / native payment-relevant state
existing native advance state
Payment Terms state
amount
bank_amount
payment destination identity
party account / advance-account branch
currencies
native reference projection
reference number/date
posting date
resolved native preview
```

Do not fingerprint MCP-generated fake accounting rows.

---

## 19. Confirm Behavior

`confirm_sales_order_advance_payment` must:

1. validate shared `CONFIRM_WRITE` approval;
2. atomically claim the proposal using the existing shared approval store;
3. re-resolve current authenticated context;
4. re-read the Sales Order;
5. re-check permissions;
6. re-check submitted / eligible state;
7. rebuild the native Payment Entry from the original approval-bound request;
8. re-resolve destination/account state;
9. recompute canonical fingerprint material;
10. compare against the approved preview;
11. return `STALE_CONFIRMATION` or existing equivalent on material drift;
12. insert one **Draft Payment Entry only**;
13. use normal Frappe permissions, links, mandatory validation, hooks, and transaction behavior;
14. commit only on successful insert;
15. rollback on failure;
16. return a bounded Draft result.

### Critical rule

**Do not call `doc.submit()` in Task 53 confirmation.**

Generic Accounts lifecycle submission already exists and must remain the only public submit path for this Draft.

---

## 20. Existing Lifecycle Reuse

After Task 53:

```text
confirm_sales_order_advance_payment
    -> Draft Payment Entry
```

Then the caller may separately use the existing generic Accounts lifecycle:

```text
prepare_document_submit
confirm_document_submit
```

or the exact currently registered generic lifecycle names in the repository.

Do not invent a second advance-specific submit tool.

Submission remains independently approval-gated.

Cancellation remains the existing generic lifecycle capability.

Deletion remains the existing generic lifecycle capability according to current Payment Entry policy.

---

## 21. Why Draft-Only Is Mandatory

Current Accounts architecture already separates:

```text
business creation approval
```

from:

```text
financial submission approval
```

This is deliberate because Draft insertion and Payment Entry submission have materially different effects.

Draft insertion:

```text
creates a Payment Entry document
no final GL effect
no final Payment Ledger settlement
no final Sales Order advance accounting effect
```

Submission:

```text
runs native submit validation
creates accounting effects
updates native ledgers
updates Sales Order advance state
runs installed hooks
```

Combining them would remove the existing second approval boundary and make Task 53 inconsistent with Tasks 45, 49, and 50.

---

## 22. REST / Direct Parity

If current Accounts write tools support both direct and fixed REST execution, Task 53 must maintain parity.

Add only fixed typed remote operations for the two new public operations.

Do not add:

- arbitrary method dispatch;
- arbitrary DocType dispatch;
- caller-controlled site;
- caller-controlled user;
- generic Frappe method execution.

Both transports must call the same service authority.

---

## 23. Profile Registration

Register the two new tools only under:

```text
MCP_PROFILE=accounts
```

Do not register them in:

```text
sales
purchase
```

Do not change Purchase profile behavior.

Do not duplicate Sales profile tools inside Accounts.

---

## 24. Contract Registry

Add explicit typed input/output contracts to the existing registry.

The new contracts must follow existing project rules:

- `extra="forbid"` or the current equivalent;
- explicit input schema;
- explicit output schema;
- shared interaction directive;
- approval-required metadata for confirm write;
- no arbitrary dictionaries as public mutation payload;
- no `Context` or internal transport object in public schemas;
- deterministic serializable output.

Run the existing contract audit.

---

## 25. Error Model

Preserve current bounded error conventions.

Expected categories include:

```text
Sales Order not found
Sales Order not submitted
Sales Order not readable
Sales Order no longer eligible
Payment Entry create permission denied
invalid amount
unsupported payment destination combination
Mode of Payment has no valid native account
Bank Account invalid / wrong Company / unreadable
native account configuration missing
Payment Terms branch unsupported by V1
native validation failure
stale approval
approval expired
approval already consumed
approval belongs to another user/site/action
native insert failure
unexpected internal failure with bounded error reference
```

Do not expose:

- SQL;
- stack traces;
- credentials;
- raw secrets;
- internal account enumeration;
- permission role internals.

---

## 26. Allowed Changes

Inspect first, then change only files required by the implementation.

Likely areas:

```text
mcp_erpnext/contracts/accounts/sales_order_advance_payment.py
mcp_erpnext/services/accounts/sales_order_advance_payment.py
mcp_erpnext/tools/accounts/sales_order_advance_payment.py

mcp_erpnext/contracts/accounts/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/profiles/accounts.py
mcp_erpnext/remote_operations.py
mcp_erpnext/tools/__init__.py

mcp_erpnext/tests/test_sales_order_advance_payment.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_rest_backend.py

docs/TOOLS.md
docs/inspect/SALES_ORDER_CUSTOMER_ADVANCE_PAYMENT_IMPLEMENTATION_REPORT.md
```

Reuse existing Accounts helpers rather than duplicating them.

If the current repository structure uses different filenames, follow the current structure after inspection.

---

## 27. Changes Not Allowed

Do not modify:

```text
apps/frappe/**
apps/erpnext/**
apps/india_compliance/**
```

Do not create or modify ERPNext DocTypes.

Do not add migrations, fixtures, hooks, patches, or custom fields.

Do not change site configuration.

Do not change Company/account settings.

Do not create test data on a live site without explicit authorization.

Do not refactor unrelated Sales, Purchase, Customer, Item, Quotation, Sales Order, Delivery Note, Sales Invoice, PDF, email, or read/query code.

Do not implement Payment Reconciliation in this task.

---

## 28. Explicitly Out of Scope

Task 53 must not implement:

```text
Payment Reconciliation
existing payment -> Sales Invoice allocation
one payment -> multiple invoices
multiple payments -> one invoice
multiple Sales Orders in one advance request
automatic reconciliation
manual reconciliation rows
Payment Request
refund
customer credit note allocation
internal transfer
supplier payment
Purchase Invoice payment
Journal Entry
arbitrary Payment Entry
arbitrary Payment Entry reference mutation
arbitrary GL mutation
arbitrary Payment Ledger mutation
standalone receipt changes
Task 50 refactor
multi-invoice receipt changes
Sales Invoice payment changes
Purchase-profile work
```

---

## 29. Required Tests

### 29.1 Contract Tests

Test:

- valid input;
- missing Sales Order;
- missing amount;
- zero amount;
- negative amount;
- boolean amount;
- NaN;
- infinity;
- both `mode_of_payment` and `bank_account`;
- neither destination where current policy requires one;
- unknown extra fields;
- confirm with mutable business fields rejected;
- output schema;
- interaction directive;
- approval guard metadata.

### 29.2 Source-State Tests

Test:

- missing Sales Order;
- Draft Sales Order;
- submitted Sales Order;
- cancelled Sales Order;
- closed / natively ineligible Sales Order where applicable;
- wrong party/source type if possible;
- source permission denied.

### 29.3 Native Factory Tests

Verify:

- exact source type `"Sales Order"`;
- exact Sales Order name;
- Customer receive direction;
- positive amount passed correctly;
- destination passed through the established resolver;
- native Customer/Company derived;
- native Sales Order reference preserved;
- native Payment Terms branch preserved or explicitly rejected;
- no arbitrary child row creation by public input.

### 29.4 Destination Tests

Test:

- valid Mode of Payment;
- valid Bank Account;
- both supplied rejected;
- wrong Company Bank Account rejected;
- unreadable Bank Account rejected;
- missing native account configuration handled safely.

### 29.5 Advance Account Tests

Where mock/source seams permit:

- separate advance account configuration enabled;
- separate advance account configuration disabled;
- no caller override;
- preview shows only bounded branch information.

### 29.6 Currency Tests

Test at least:

- same-currency advance;
- foreign-currency source/account behavior;
- explicit bank amount when required;
- no MCP exchange-rate formula;
- native rate state participates in stale fingerprint.

### 29.7 Approval Tests

Test:

- prepare returns approval token;
- confirm without approval fails;
- wrong user fails;
- wrong site fails;
- wrong operation fails;
- expired token fails;
- reused token fails;
- request mutation after approval impossible;
- atomic claim semantics preserved.

### 29.8 Stale-State Tests

After prepare, simulate material changes such as:

- source modified;
- source cancelled;
- source becomes ineligible;
- existing advance state changes;
- destination account/default changes;
- currency/rate changes;
- Payment Terms changes.

Confirm must fail deterministically and create nothing.

### 29.9 Draft-Only Tests

Mandatory regression:

- prepare creates no document;
- confirm inserts exactly one Payment Entry;
- inserted Payment Entry has `docstatus == 0`;
- confirm never calls `submit()`;
- no GL effect is claimed during confirmation;
- no Payment Ledger settlement is claimed during confirmation;
- generic lifecycle submit remains registered for Accounts Payment Entry.

### 29.10 Lifecycle Regression

Ensure existing generic lifecycle remains unchanged:

- Payment Entry submit path still works;
- Payment Entry cancel path still works;
- Payment Entry delete policy remains unchanged;
- Task 53 does not add duplicate lifecycle tools.

### 29.11 Profile Tests

Verify:

- Accounts profile contains the two new names;
- Sales profile does not;
- Purchase profile does not;
- current Accounts tools remain present;
- no unrelated registration disappears.

### 29.12 REST Tests

Verify:

- exact fixed prepare operation;
- exact fixed confirm operation;
- malformed input rejected;
- unknown operation rejected;
- no arbitrary method dispatch;
- same service result shape as direct path.

### 29.13 Regression Tests

Run focused existing regressions for:

```text
sales invoice payment
multi-invoice customer receipt
standalone customer payment entry
payment entry reads
lifecycle
approvals
fingerprint
profiles
tool contracts
tool registration
REST backend
```

Then run the full existing `mcp_erpnext` unit suite if supported.

Record exact pass/fail counts.

Do not describe unrelated existing failures as caused by Task 53 without traceback/path evidence.

---

## 30. Live Verification Boundary

Task 53 implementation may use static/unit verification unless explicit live mutation permission is given.

Do not claim live behavior unless actually tested.

Separate live verification should eventually cover:

```text
real submitted test Sales Order
real Customer / Company
Mode of Payment / Bank Account defaults
Company separate advance account setting
permissions
Redis/shared approval
Draft Payment Entry insertion
later lifecycle submission
GL effects
Payment Ledger effects
Sales Order advance_paid / native advance state
cancellation reversal
foreign currency
Payment Terms
India Compliance hooks
```

Production data must not be used casually.

---

## 31. Acceptance Criteria

Task 53 is complete only when all are true.

### AC-01
Accounts profile exposes:

```text
prepare_sales_order_advance_payment
confirm_sales_order_advance_payment
```

### AC-02
Sales and Purchase profiles do not expose those tools.

### AC-03
Prepare requires one exact submitted Sales Order and a positive finite advance amount.

### AC-04
Exactly one supported payment destination is accepted according to current Accounts conventions.

### AC-05
ERPNext's native Payment Entry factory is used with `"Sales Order"` as source.

### AC-06
Customer, Company, payment direction, party/advance account, currencies, and native reference state are server/native-derived.

### AC-07
No raw ledger account, GL, Payment Ledger, arbitrary child-row, site, or user input is public.

### AC-08
Prepare writes no ERPNext business document.

### AC-09
Prepare returns a bounded native Draft preview and shared approval token.

### AC-10
Confirm atomically claims shared approval.

### AC-11
Confirm re-reads and fully rebuilds current native state.

### AC-12
Material drift produces stale/failed confirmation and creates nothing.

### AC-13
Confirm inserts exactly one **Draft** Payment Entry with normal Frappe permissions and validation.

### AC-14
Confirm does **not** submit the Payment Entry.

### AC-15
Existing generic Accounts lifecycle remains the only public submit/cancel/delete authority for Payment Entry.

### AC-16
Separate advance account configuration is native-controlled, not caller-controlled.

### AC-17
Payment Terms behavior is preserved natively or explicitly rejected where the V1 contract cannot represent it safely.

### AC-18
Currency/exchange logic remains ERPNext-native.

### AC-19
No custom reconciliation algorithm is added.

### AC-20
No Payment Reconciliation capability is added.

### AC-21
Direct and fixed REST behavior remain equivalent where both are supported.

### AC-22
Contract audit and focused tests pass.

### AC-23
Generated tool catalog is regenerated and its check passes.

### AC-24
Implementation report documents exact tests, versions, changed files, limitations, and unverified live boundaries.

---

## 32. Expected Result

After Task 53, the supported service-selling Accounts flow becomes:

```text
Quotation
    ->
Sales Order
    |
    +--> Customer Advance Payment
    |        ->
    |      Draft Payment Entry
    |        ->
    |      separate generic lifecycle submit
    |
    -> Sales Invoice
         |
         +--> invoice-specific Customer Payment
         |
         +--> multi-invoice Customer Receipt
         |
         +--> standalone Customer receipt remains available
```

Task 53 adds the missing **Sales Order-linked advance creation capability** only.

It does not yet allocate an existing advance to a later Sales Invoice through Payment Reconciliation.

---

## 33. Required Implementation Report

Create:

```text
docs/inspect/SALES_ORDER_CUSTOMER_ADVANCE_PAYMENT_IMPLEMENTATION_REPORT.md
```

The report must include:

1. inspected current repository state;
2. installed ERPNext/Frappe versions;
3. native ERPNext source inspected;
4. exact public input/output contract;
5. native factory call used;
6. source eligibility behavior;
7. payment destination behavior;
8. separate advance account behavior;
9. Payment Terms behavior;
10. currency behavior;
11. approval/fingerprint behavior;
12. Draft-only confirmation proof;
13. profile/REST registration;
14. files changed;
15. focused tests run and exact results;
16. full-suite result;
17. existing unrelated failures, if any;
18. live verification not performed;
19. remaining limitations;
20. exact next-task recommendation.

Do not claim site/accounting behavior that was not actually tested.

---

## 34. Limitations After Task 53

The following remain intentionally unsupported:

```text
Payment Reconciliation
existing standalone receipt -> invoice allocation
existing Sales Order advance -> invoice reconciliation via MCP
multi-payment allocation
multi-invoice reconciliation
automatic allocation policy
manual reconciliation selection
background reconciliation orchestration
customer refunds
internal transfers
supplier payments
Payment Request
credit note allocation
generic Payment Entry mutation
```

These require separate bounded capabilities.

---

## 35. Exact Next Task

After Task 53 implementation and focused regression verification, the next task should be an **audit**, not immediate implementation:

```text
Task 54 — Customer Payment / Advance to Sales Invoice Reconciliation Native Capability Audit
```

Task 54 should determine the narrowest safe MCP capability over ERPNext's native Payment Reconciliation / advance-allocation machinery.

It must answer, before implementation:

- start with one payment to one invoice or another bounded shape;
- whether Sales Order-linked advances and Task 50 standalone receipts share one public reconciliation contract;
- exact native discovery APIs;
- exact native mutation API;
- submitted Payment Entry mutation semantics;
- separate advance account handling;
- Payment Terms handling;
- currency and gain/loss behavior;
- synchronous vs background reconciliation;
- concurrency guard;
- idempotency;
- approval/fingerprint model;
- permissions;
- regional/India Compliance hooks;
- bounded preview/result;
- reversal/cancellation behavior;
- live test requirements.

Task 54 must remain inspection-only unless separately authorized.

---

## 36. Final Implementation Principle

```text
MCP owns:
- explicit business capability
- typed public contract
- input hygiene
- data minimization
- preview
- approval
- stale-state detection
- transport/profile exposure
- bounded errors

ERPNext owns:
- Payment Entry construction
- Customer / Company / account resolution
- advance-account policy
- Payment Terms
- currencies
- exchange rates
- validation
- permissions
- document hooks
- GL
- Payment Ledger
- advance state
- reconciliation
- accounting truth
```

Do not move ERPNext accounting logic into MCP.
