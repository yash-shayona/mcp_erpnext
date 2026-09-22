# Task 45 — Accounts V1: Sales Invoice Customer Receive Payment Entry as Draft

## Status

**Implementation task**

This task follows:

- Task 44 — Accounts Profile + Payment Entry Native Flow Audit

The audit established the first safe Accounts vertical slice:

```text
Submitted Sales Invoice
    ↓
native ERPNext get_payment_entry(...)
    ↓
bounded Draft Payment Entry preview
    ↓
shared approval
    ↓
fresh native rebuild + fingerprint comparison
    ↓
insert Draft Payment Entry only
    ↓
generic lifecycle submit later
```

This task must implement only that slice.

---

# 1. Objective

Add the first `accounts` profile to `mcp_erpnext` and implement a narrow, business-intent-oriented customer receipt capability for a **single Submitted Sales Invoice**.

Public tools:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment
```

The implementation must:

- use ERPNext's native Payment Entry factory;
- support native full payment;
- support native partial payment;
- allow bounded destination selection through Mode of Payment and/or Bank Account;
- preserve native currency/payment-term/defaulting behavior;
- create only a Draft Payment Entry;
- reuse the shared approval/fingerprint architecture;
- reuse generic lifecycle for submit/cancel/delete;
- support both direct and REST backends;
- avoid exposing raw accounting internals.

---

# 2. Native ERPNext Authority

Use the exact installed native callable:

```python
erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry(
    dt,
    dn,
    party_amount=None,
    bank_account=None,
    bank_amount=None,
    party_type=None,
    payment_type=None,
    reference_date=None,
    created_from_payment_request=False,
)
```

For Task 45, use it only for:

```text
dt = "Sales Invoice"
dn = exact submitted Sales Invoice name
```

Do not use the public contract to expose or override:

- `party_type`
- `payment_type`
- `created_from_payment_request`
- raw party account
- raw paid-from account
- raw paid-to account
- arbitrary account fields
- arbitrary reference rows
- arbitrary GL behavior

ERPNext remains authoritative for:

- Customer
- Company
- party type
- payment type
- receivable account
- party account currency
- bank/cash account resolution
- paid/received amounts
- source/target exchange rates
- invoice outstanding
- payment terms
- early payment discounts
- reference rows
- default dimensions
- taxes/withholding hooks
- latest outstanding validation
- duplicate/reference validation
- GL
- Payment Ledger
- submit/cancel effects

---

# 3. Scope

## In scope

Implement:

1. `accounts` profile enum/config support.
2. Accounts profile tool registration.
3. `prepare_sales_invoice_payment`.
4. `confirm_sales_invoice_payment`.
5. typed public contracts.
6. shared approval/fingerprint integration.
7. native `get_payment_entry("Sales Invoice", ...)` adapter.
8. full payment.
9. native partial payment using `party_amount`.
10. bounded optional `bank_amount` for cross-currency cases.
11. Mode of Payment selection.
12. Bank Account selection as bounded explicit fallback.
13. reference number/date handling.
14. bounded remarks.
15. Draft Payment Entry insertion only.
16. Payment Entry in Accounts generic lifecycle allowlist for:
    - submit
    - cancel
    - delete
17. fixed typed direct-backend support.
18. fixed typed REST-backend support.
19. focused tests.
20. live authorized test-site verification.
21. documentation/tool catalog updates.
22. implementation report.

## Explicitly out of scope

Do NOT implement:

- multi-Sales-Invoice allocation
- generic customer receipt
- unallocated customer receipt
- customer advance
- Sales Order advance payment
- Supplier payment
- Purchase Invoice payment
- Internal Transfer
- Payment Request
- Payment Reconciliation
- unreconciliation
- Journal Entry
- bank reconciliation
- bank transaction import
- payment gateway integration
- arbitrary deductions
- arbitrary write-off account lines
- arbitrary bank-fee lines
- caller-configurable tax rows
- caller-configurable withholding rows
- raw debit/credit construction
- raw GL creation
- raw Payment Ledger mutation
- Payment Entry PDF
- Payment Entry email
- Payment Entry read/query/aggregate
- generic Payment Entry creation
- cross-project permission-boundary refactor
- changes to Sales or Purchase business flows

---

# 4. Current Architecture Reuse

Before changing code, inspect and reuse the current post-Task-43 patterns for:

- profile enum and profile registry
- Sales/Purchase profile selection
- Quotation → Sales Order conversion
- Sales Order → Sales Invoice conversion
- Sales Order → Delivery Note conversion
- Delivery Note → Sales Invoice conversion
- `ApprovalStore`
- `claim_for_confirm_write()`
- fingerprint generation/projection
- `InteractionDirective`
- bounded public error/reference handling
- generic lifecycle
- fixed REST remote operation registry
- direct runtime
- generated tool catalog

Do not create a separate Accounts-specific approval framework.

Do not create a second REST dispatch mechanism.

---

# 5. Accounts Profile

Add:

```text
MCP_PROFILE=accounts
```

to the existing profile architecture.

The Accounts process must be independently runnable.

It must NOT depend on:

- Sales MCP process being alive;
- Purchase MCP process being alive;
- another MCP profile process for source lookup.

It may read normal ERPNext Sales Invoice documents through native ERPNext/Frappe APIs under the authenticated user because all profiles operate against the same configured Frappe site.

## Initial Accounts public inventory

Task 45 should expose only:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment
```

plus the existing generic lifecycle tools insofar as Payment Entry is newly allowed under the Accounts profile.

Do not duplicate Customer/Sales Invoice public Sales tools into Accounts merely for convenience.

---

# 6. Prepare Public Contract

Add:

```text
prepare_sales_invoice_payment
```

## Required input

```json
{
  "sales_invoice": "ACC-SINV-..."
}
```

or the target site's actual Sales Invoice identifier.

## Optional inputs

Only fields proven necessary/safe by Task 44:

```text
amount
mode_of_payment
bank_account
reference_no
reference_date
bank_amount
remarks
```

All extra fields must be rejected.

## Meaning

### `sales_invoice`

Required exact source Sales Invoice name.

### `amount`

Optional payment amount on the party side.

Behavior:

```text
omitted → native full outstanding amount
provided → native partial payment intent
```

Must be positive and bounded by this narrow V1 policy.

Do not use Task 45 for overpayment/unallocated receipt.

If `amount > current invoice outstanding`, reject with a bounded V1 policy error before approval or through native validation translated into a bounded result.

Do not silently convert the excess into advance/unallocated money.

### `mode_of_payment`

Optional human/business-facing payment destination method.

Prefer this over asking the LLM for raw ledger Account names.

If Mode of Payment resolves a valid Company bank/cash account natively, use that result.

Do not invent a fallback ledger account.

### `bank_account`

Optional bounded explicit Bank Account fallback/choice where Mode of Payment is insufficient.

The adapter must resolve through native ERPNext behavior.

Do not expose full bank numbers, IBAN, SWIFT, or secrets in outputs.

### `reference_no`

Optional at prepare time only if native Draft can be built without it.

For normal bank receipt paths, Task 45 should make clear in the preview if it is required before submit.

If the current implementation chooses to require it already at prepare for a safer V1 contract, document and test that choice.

Do not fabricate a bank reference.

### `reference_date`

Optional at prepare only if the native flow allows it.

Pass to `get_payment_entry(..., reference_date=...)` where appropriate.

Do not invent a date.

### `bank_amount`

Optional only for cases where native currencies require an explicit bank-side amount.

Do not ask for or calculate exchange rates manually.

### `remarks`

Optional bounded text.

Enforce the existing project size/safety conventions.

---

# 7. Forbidden Public Inputs

Do not expose:

- company
- customer
- party_type
- payment_type
- party
- party_account
- paid_from
- paid_to
- raw ledger account
- account currency
- source_exchange_rate
- target_exchange_rate
- transaction_exchange_rate
- allocated_amount
- unallocated_amount
- raw Payment Entry references
- Payment Term row
- deductions
- taxes
- withholding rows
- write-off account
- cost center
- arbitrary dimensions
- advance account
- payment request
- `created_from_payment_request`
- arbitrary DocType
- arbitrary Python method/import path
- site
- user
- identity
- permission bypass flags

If future use cases require any of these, they need their own explicit audit/task.

---

# 8. Prepare Native Flow

Preparation must:

1. execute in the configured Accounts runtime context;
2. use the authenticated Frappe identity;
3. call:

```python
get_payment_entry(
    "Sales Invoice",
    sales_invoice,
    party_amount=<amount or None>,
    bank_account=<resolved/allowed destination input or None>,
    bank_amount=<bank_amount or None>,
    reference_date=<reference_date or None>,
)
```

with all non-V1 arguments fixed/server-owned;

4. allow the native factory to:
   - enforce Payment Entry create permission;
   - enforce source document permission;
   - determine Customer;
   - determine Company;
   - determine payment type = Receive;
   - determine party account;
   - determine invoice outstanding;
   - determine currencies;
   - resolve bank/cash destination;
   - calculate paid/received amounts;
   - calculate reference allocations;
   - expand payment-term rows where applicable;
   - apply native defaults/hooks;

5. apply the supported optional Mode of Payment/Bank Account intent without exposing raw accounting choices;
6. apply `reference_no`, `reference_date`, and remarks only through normal Payment Entry fields/native validation;
7. perform the native validation/defaulting necessary for a trustworthy Draft preview;
8. create no database Payment Entry;
9. create no GL;
10. create no Payment Ledger mutation;
11. submit nothing;
12. build a bounded preview;
13. store site/user/action-bound approval and fingerprint;
14. return the standard interaction directive.

---

# 9. Mode of Payment vs Bank Account Adapter

The audit recommends:

```text
Mode of Payment preferred
Bank Account explicit fallback
raw ledger Account not public
```

Implement this carefully.

## Rules

1. If only `mode_of_payment` is supplied:
   - let ERPNext resolve its Company default account;
   - if no usable account exists, return a bounded native/defaulting error;
   - do not choose another account in MCP.

2. If only `bank_account` is supplied:
   - resolve it through native ERPNext Bank Account/account logic;
   - ensure it belongs to/works for the invoice Company through native validation;
   - do not reveal full banking details.

3. If both are supplied:
   - either reject contradictory combinations explicitly;
   - or allow only if the current native helper proves the combination is coherent.

Choose one deterministic behavior and document it.

4. Never accept `paid_to` or arbitrary `Account` as public input.

---

# 10. Full Payment

When `amount` is omitted:

- use the native invoice outstanding amount;
- let ERPNext create the reference allocation;
- show the current outstanding and proposed allocated/payment amount;
- do not calculate outstanding manually;
- do not assume status will become Paid until actual submit occurs.

Preview must say the Payment Entry is only a Draft and the Sales Invoice outstanding will change only when Payment Entry is submitted.

---

# 11. Partial Payment

When `amount` is provided and less than current outstanding:

- pass it as native `party_amount`;
- preserve native calculations;
- preserve native Payment Term behavior;
- show:
  - current invoice outstanding;
  - proposed payment amount;
  - proposed allocated amount;
  - expected remaining outstanding as a bounded informational value only if derived directly from native preview/latest source state;
- do not manually mutate Sales Invoice;
- do not directly edit Payment Schedule.

The native helper/validation remains authority.

---

# 12. Overpayment Policy

Task 45 is intentionally **not** an advance/unallocated receipt capability.

Therefore:

```text
amount > current invoice outstanding
```

must not silently create excess unallocated money.

Return a bounded error such as:

```text
AMOUNT_EXCEEDS_OUTSTANDING
```

or a project-consistent equivalent.

Message should explain that overpayment/advance is outside this V1 capability.

Do not expose a free-form switch to override this rule.

---

# 13. Payment Terms

If the native factory returns multiple Payment Entry Reference rows because:

```text
allocate_payment_based_on_payment_terms
```

is enabled:

- preserve those native rows;
- show a bounded term/reference summary in preview;
- do not flatten into one fake reference;
- do not accept a caller-supplied Payment Term selector in Task 45;
- do not manually redistribute allocation.

If a partial payment produces an ambiguous or unsupported term-specific case for the current implementation, fail closed with a bounded result and record it in the implementation report rather than inventing allocation rules.

---

# 14. Currency Handling

No currency formula belongs in MCP.

Support only native behavior.

## Same-currency

Normal native pass-through.

## Multi-currency

Allow only when the native helper can produce a complete trustworthy preview with the supplied V1 inputs.

If native behavior requires explicit `bank_amount`, the public contract may accept it.

Do not expose:

- source exchange rate
- target exchange rate
- account exchange rate
- exchange gain/loss account

Preview may include bounded:

- invoice currency
- party account currency
- bank/cash currency
- party payment amount
- bank-side received amount
- native exchange-rate summary when material

Do not promise exact exchange gain/loss GL until submit.

---

# 15. Reference Number and Date

Task 44 found transaction reference validation is native and configuration-sensitive.

Task 45 must:

- preserve native validation;
- clearly show reference number/date in preview if present;
- clearly show if the Draft still lacks information required before submit;
- never generate a fake reference;
- never assume every Cash payment needs a bank reference;
- never assume every Bank payment can omit it.

If Task 45 chooses to require `reference_no` + `reference_date` for all supported V1 bank flows, encode and test that narrowly.

---

# 16. Prepare Preview

Return only review-relevant fields.

At minimum, where available:

- target = Payment Entry
- source Sales Invoice
- source invoice docstatus/status
- Customer
- Company
- current invoice outstanding
- payment type = Receive
- posting date
- Mode of Payment
- bounded destination label
- party currency
- bank/cash currency
- payment amount
- received/bank amount
- total allocated amount
- unallocated amount
- reference number
- reference date
- bounded Payment Entry Reference rows:
  - reference doctype
  - reference name
  - total/outstanding amount
  - allocated amount
  - payment term if native term row exists
- bounded discount summary when native early-payment logic adds it
- bounded deduction/exchange summary only when natively produced
- remarks
- explicit note:
  - Draft only
  - no ledger effect yet
  - submit is separate

Do not expose:

- raw Payment Entry JSON
- complete Chart of Accounts
- raw GL rows
- raw Payment Ledger entries
- full Bank Account number
- IBAN/SWIFT
- all account metadata
- complete Customer master
- unrelated invoices
- secrets
- tracebacks

---

# 17. Approval / Fingerprint

Reuse the existing shared ApprovalStore.

Approval must remain:

- action-bound
- site-bound
- user-bound
- expiring
- one-shot
- atomically claimed

Fingerprint must cover all material approved state.

At minimum include:

- Sales Invoice name
- Sales Invoice docstatus/status
- Sales Invoice modified/version signal where available
- Customer
- Company
- current outstanding
- invoice currency
- party account identity/currency
- requested amount
- requested bank amount
- Mode of Payment
- Bank Account identity
- resolved destination account identity in internal fingerprint material
- destination currency
- reference number/date
- posting date
- native reference rows
- Payment Term rows
- allocated amounts
- paid/received amounts
- discount summary
- deduction/exchange summary
- native preview version/projection

Do not expose fingerprint internals publicly.

---

# 18. Confirm Public Contract

Add:

```text
confirm_sales_invoice_payment
```

Use the existing shared confirmation shape:

```json
{
  "approval_token": "...",
  "confirm": true
}
```

No business/payment fields may be supplied during confirm.

---

# 19. Confirm Behavior

Confirm must:

1. validate normal confirmation intent;
2. atomically claim the approval;
3. enforce action/site/user binding;
4. enforce expiry;
5. enforce one-shot use;
6. rebuild from the exact source Sales Invoice using the exact originally approved intent;
7. call the native `get_payment_entry(...)` again;
8. recreate the bounded material preview;
9. recompute fingerprint;
10. reject material drift;
11. rely on native latest-outstanding validation;
12. insert one normal-permission Draft Payment Entry;
13. keep `docstatus == 0`;
14. never call `submit()`;
15. never create GL entries manually;
16. never update Payment Ledger manually;
17. never modify Sales Invoice manually;
18. never create Journal Entry;
19. never create Payment Request;
20. never create reconciliation records.

---

# 20. Stale-State Cases

Confirm must fail safely and create nothing if, after prepare:

- another Payment Entry reduced the outstanding;
- the invoice became fully paid;
- the invoice was cancelled;
- invoice payment terms changed;
- Mode of Payment defaults changed materially;
- Bank Account/default account changed;
- party account changed;
- account currency changed;
- exchange-rate/native amount result changed materially;
- reference allocation changed;
- early-payment discount changed;
- native tax/withholding/deduction preview changed materially;
- source invoice changed materially.

Native latest-outstanding checks remain final authority.

MCP fingerprinting provides approval consistency.

---

# 21. Draft Insert

Successful confirm must insert exactly one Payment Entry with:

```text
docstatus = 0
```

using normal Frappe permissions.

Do not submit.

Do not use:

```python
ignore_permissions=True
```

Do not set permission-bypass flags.

Do not impersonate Administrator.

---

# 22. Generic Lifecycle

Add `Payment Entry` to the **Accounts profile** lifecycle policy only for:

```text
submit
cancel
delete
```

Do not enable generic update or child-row mutation.

## Submit

Use native `doc.submit()` through the existing lifecycle architecture.

Preview/warning must make clear that submit may cause:

- General Ledger entries
- Payment Ledger/outstanding changes
- Sales Invoice outstanding reduction
- Payment Schedule updates
- Payment Request updates where natively linked
- exchange gain/loss
- deductions/tax effects
- optional-app hooks

Do not predict exact GL rows beyond bounded native review data.

## Cancel

Use native `doc.cancel()`.

Do not manually restore invoice outstanding.

Do not manually reverse GL/Payment Ledger.

Do not cascade-cancel unrelated documents.

## Delete

Use existing Frappe linked-document-aware delete logic.

Respect Draft/cancel-before-delete behavior and target-site linked-document rules.

No cascade delete.

---

# 23. Permission Boundary

Task 45 must follow the native-authority principle identified by Task 44:

```text
Use permission-enforcing native Frappe/ERPNext APIs
→ Frappe decides
→ MCP translates exceptions
```

The native `get_payment_entry` already checks:

- Payment Entry create permission;
- source document permission.

Do not add a parallel MCP authorization matrix.

Do not hard-code roles.

Do not introduce a broad permission refactor of older Sales services in this task.

Final insert/submit/cancel/delete must use normal Frappe APIs and current authenticated identity.

---

# 24. Direct Backend

Accounts tools must work with current direct execution.

Requirements:

- configured site only
- no hard-coded site
- current authenticated Frappe user
- same approval model
- JSON-safe outputs
- bounded errors
- independent Accounts process

Do not add a second runtime.

---

# 25. REST Backend

Add fixed typed REST operations for:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment
```

and ensure generic lifecycle targeting Payment Entry works under Accounts according to current REST architecture.

Requirements:

- typed JSON-safe arguments
- fixed remote operation names
- static remote registry
- no arbitrary DocType/method/import dispatch
- no caller-supplied site
- no caller-supplied identity
- remote approval token remains authoritative according to current architecture
- direct/REST success contract parity
- direct/REST bounded error parity

---

# 26. Errors

Use the current public error/reference pattern.

At minimum map safely:

- source Sales Invoice not found
- source not Submitted
- source fully paid
- source cancelled
- permission denied
- Payment Entry create denied
- missing Mode of Payment account/default
- invalid Bank Account
- wrong Company destination
- invalid payment amount
- amount exceeds outstanding
- missing transaction reference
- currency/bank amount requirement
- stale outstanding
- stale approval fingerprint
- approval expired
- approval already used
- wrong action/user/site
- native validation failure
- insert failure

Do not expose:

- tracebacks
- SQL
- filesystem paths
- Redis/cache internals
- secrets
- API credentials
- full native exception dumps

---

# 27. Accounts Tool Registration

Add the Accounts profile to all required current registries/config.

Register:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment
```

Do not register Sales tools wholesale under Accounts.

Do not register Purchase tools under Accounts.

Do not modify Purchase profile inventory.

Do not remove any Sales tools.

---

# 28. Tool Catalog / Documentation

Regenerate/update the current tool catalog.

Document:

```text
Accounts V1
- prepare_sales_invoice_payment
- confirm_sales_invoice_payment
- generic lifecycle submit/cancel/delete for Payment Entry
```

Clearly state limitations:

- single Sales Invoice only
- Receive only
- no overpayment/advance
- no multi-invoice
- no supplier pay
- no internal transfer
- no reconciliation
- no Journal Entry
- no PDF/email
- no read/query/aggregate

---

# 29. Allowed Changes

Allowed only where required by Task 45, including equivalents of:

- settings/profile enum/config
- `profiles/accounts.py`
- Accounts contracts
- Accounts services
- Accounts tools
- tool registration
- contract registry/catalog
- lifecycle allowlists/policies
- REST remote operation registry
- tests
- generated docs/tool catalog
- implementation report

Shared code may be refactored only if:

1. needed to avoid real duplication;
2. existing Sales/Purchase behavior remains unchanged;
3. tests prove compatibility;
4. refactor does not widen into permission cleanup or unrelated architecture work.

---

# 30. Required Tests

## A. Profile/registration

1. `accounts` is a valid profile.
2. Accounts profile can initialize independently.
3. Sales profile remains unchanged.
4. Purchase profile remains unchanged.
5. Accounts exposes prepare/confirm payment tools.
6. Accounts does not expose unrelated Sales/Purchase business tools.
7. tool catalog is deterministic.

## B. Contract

8. `sales_invoice` required.
9. `amount` optional.
10. `mode_of_payment` optional.
11. `bank_account` optional.
12. `reference_no` optional/required according to final narrow contract.
13. `reference_date` optional/required according to final narrow contract.
14. `bank_amount` optional.
15. `remarks` optional and bounded.
16. extra fields fail closed.
17. raw accounting fields are rejected.

## C. Native factory

18. adapter calls installed `get_payment_entry("Sales Invoice", ...)`.
19. no generic `Payment Entry` builder replaces the native factory.
20. party type is not caller-controlled.
21. payment type is not caller-controlled.
22. company/customer are not caller-controlled.
23. source permission/create permission remain native.
24. returned object is Draft/unsaved during prepare.

## D. Full payment

25. omitted `amount` maps native current outstanding.
26. one native Sales Invoice reference is present.
27. allocated amount matches native result.
28. prepare writes no Payment Entry.
29. prepare changes no outstanding.
30. prepare creates no GL/Payment Ledger data.

## E. Partial payment

31. partial `amount` is passed as `party_amount`.
32. native allocation is preserved.
33. remaining outstanding is not manually written.
34. payment terms are preserved.
35. unsupported term-specific ambiguity fails closed rather than inventing allocation.

## F. Overpayment

36. amount above current outstanding is rejected for V1.
37. no unallocated/advance Payment Entry is silently created.
38. error explains advance/overpayment is outside current capability.

## G. Mode of Payment / Bank Account

39. configured Mode of Payment resolves native destination.
40. missing Mode of Payment default fails boundedly.
41. explicit Bank Account uses native resolution.
42. wrong-company/invalid Bank Account fails.
43. raw ledger account is not public.
44. contradictory destination inputs behave deterministically.

## H. Transaction reference

45. reference number/date pass through safely.
46. no reference is fabricated.
47. required bank-reference validation remains native.
48. supported Cash/native exception behavior remains native.

## I. Currency

49. same-currency native flow preserved.
50. cross-currency flow preserves native paid/received amounts.
51. `bank_amount` passes only where needed.
52. no MCP exchange-rate formula exists.
53. no caller-controlled exchange-rate input exists.
54. material native exchange/deduction data is included in fingerprint.

## J. Approval

55. prepare stores shared approval.
56. correct action/site/user can confirm.
57. wrong user fails.
58. wrong site fails.
59. wrong action fails.
60. expired token fails.
61. `confirm=false` writes nothing.
62. token reuse fails.
63. concurrent repeated confirm yields at most one write.
64. changed outstanding causes stale rejection.
65. fully paid after prepare causes stale rejection.
66. changed Mode of Payment/default destination causes stale rejection when material.
67. changed currency/native amount preview causes stale rejection.

## K. Confirm

68. confirm rebuilds native Payment Entry.
69. fresh fingerprint is recomputed.
70. successful confirm inserts exactly one Payment Entry.
71. created Payment Entry has `docstatus == 0`.
72. source Sales Invoice is unchanged by Draft creation.
73. no submit call occurs.
74. no manual GL occurs.
75. no manual Payment Ledger mutation occurs.
76. no Journal Entry occurs.
77. no Payment Request/Reconciliation is created.

## L. Lifecycle

78. Payment Entry submit available only under Accounts lifecycle policy.
79. submit uses native lifecycle.
80. cancel uses native lifecycle.
81. delete uses existing linked-document-safe lifecycle.
82. generic arbitrary update remains unavailable.
83. generic child-row mutation remains unavailable.
84. cancel does not manually restore outstanding.
85. delete does not cascade.

## M. REST/direct

86. prepare direct works.
87. confirm direct works.
88. fixed REST prepare operation exists.
89. fixed REST confirm operation exists.
90. malformed payload fails closed.
91. unknown operation fails closed.
92. arbitrary method/import/DocType dispatch remains impossible.
93. caller cannot choose identity/site.
94. direct/REST success shapes conform.
95. direct/REST error semantics conform.

## N. Regression

96. Sales profile tests remain green.
97. Purchase profile tests remain green.
98. Task 42 Delivery Note tests remain green.
99. Task 43 DN → SI tests remain green.
100. existing SI create/read/query/aggregate/lifecycle remain green.
101. shared ApprovalStore tests remain green or pre-existing failures are explicitly isolated.
102. REST backend tests remain green or pre-existing failures are explicitly isolated.
103. tool catalog check passes.
104. compile/static checks pass.
105. `git diff --check` passes.

---

# 31. Required Live Authorized Verification

Task 44 explicitly requires real accounting verification on an authorized throwaway/test site.

Task 45 must not call itself fully runtime-verified using static mocks only.

Where safely available, verify:

## Source

- submitted Sales Invoice
- non-zero outstanding
- known Customer/Company
- authorized test user

## Full payment

- prepare produces native Draft preview
- prepare creates no Payment Entry
- confirm creates one Draft Payment Entry
- source outstanding remains unchanged while PE is Draft
- lifecycle submit posts payment
- Sales Invoice outstanding becomes zero/native expected state
- Payment Ledger reflects native submitted payment
- GL is created natively
- cancel restores native outstanding/ledger state

## Partial payment

- prepare/confirm Draft
- submit
- remaining outstanding is correct
- cancellation restores previous outstanding

## Payment Terms

Where available:

- one-term invoice
- multi-term invoice
- term allocation preserved
- early discount behavior captured if safely configured

## Destination

- Mode of Payment default account
- explicit Bank Account
- missing default bounded failure

## Currency

At minimum one simple same-currency test.

If safe fixtures/accounts exist:

- foreign-currency same-bank-currency
- foreign invoice → base-currency bank
- explicit `bank_amount`

Do not create risky real bank/account fixtures in production merely for coverage.

## Permissions

Verify:

- source read denial
- Payment Entry create denial
- submit denial
- cancel/delete behavior

## REST

If REST backend is configured:

- real prepare round trip
- real confirm round trip
- approval authority location
- identity/site correctness

If a scenario cannot be safely tested, mark it **not verified**.

---

# 32. Acceptance Criteria

Task 45 is complete only when all are true:

1. Accounts profile exists and runs independently.
2. Sales/Purchase profiles remain unchanged.
3. `prepare_sales_invoice_payment` exists.
4. `confirm_sales_invoice_payment` exists.
5. public contract is business-intent oriented.
6. exact source Sales Invoice is required.
7. native `get_payment_entry` is used.
8. full payment works through native outstanding.
9. partial payment uses native `party_amount`.
10. overpayment is not silently turned into advance/unallocated receipt.
11. Mode of Payment is supported.
12. Bank Account fallback is supported.
13. raw ledger account selection is not public.
14. reference number/date are handled safely.
15. multi-currency is native only; no formulas in MCP.
16. prepare writes nothing.
17. confirm creates Draft Payment Entry only.
18. shared one-shot approval is reused.
19. fresh native rebuild/fingerprint stale protection exists.
20. Payment Entry lifecycle submit/cancel/delete is enabled only in Accounts.
21. no generic Payment Entry arbitrary update is added.
22. no manual GL code is added.
23. no manual Payment Ledger code is added.
24. no Journal Entry is added.
25. no reconciliation is added.
26. no supplier pay is added.
27. no internal transfer is added.
28. no advance flow is added.
29. no PDF/email/read/query/aggregate is added.
30. direct and REST parity exists.
31. required focused tests pass.
32. authorized live verification is executed where available and truthfully reported.
33. any pre-existing unrelated test failures are documented with exact names and evidence rather than simply ignored.
34. no site/company/customer/user is hard-coded.

---

# 33. Expected Result

After Task 45:

```text
SALES PROFILE
────────────────────────
Submitted Sales Invoice
        ↓
receivable exists

         domain handoff

ACCOUNTS PROFILE
────────────────────────
prepare_sales_invoice_payment
        ↓
native ERPNext Draft Payment Entry preview
        ↓
approval
        ↓
confirm_sales_invoice_payment
        ↓
Draft Payment Entry
        ↓
generic lifecycle submit
        ↓
ERPNext GL + Payment Ledger
        ↓
Sales Invoice outstanding reduced
```

The Accounts profile must work without the Sales MCP process running.

ERPNext remains the accounting authority.

---

# 34. Limitations After Task 45

Intentional remaining Accounts gaps:

- no multi-invoice payment
- no customer advance
- no standalone unallocated receipt
- no supplier payment
- no internal transfer
- no Payment Request
- no Payment Reconciliation
- no Journal Entry
- no read/query/aggregate Payment Entry
- no Payment Entry PDF/email
- no bank reconciliation
- no bank transaction import
- no generic deduction/write-off/tax input

These are not Task 45 defects.

---

# 35. Deliverable Report

Create:

```text
docs/inspect/ACCOUNTS_V1_SALES_INVOICE_PAYMENT_IMPLEMENTATION_REPORT.md
```

The report must include:

1. exact files changed
2. Accounts profile changes
3. public tools added
4. exact public contracts
5. native `get_payment_entry` call/signature used
6. how full payment is represented
7. how partial payment is represented
8. overpayment V1 behavior
9. Mode of Payment behavior
10. Bank Account behavior
11. reference number/date behavior
12. multi-currency behavior
13. payment-term behavior
14. preview fields
15. fingerprint fields
16. approval binding behavior
17. stale-state behavior
18. Draft insert behavior
19. lifecycle policy changes
20. direct backend changes
21. REST backend changes
22. permission/native-authority behavior
23. tests added
24. exact test commands
25. exact pass/fail/error counts
26. exact pre-existing unrelated failures, if any
27. live-site verification performed
28. live-site verification not performed and why
29. GL/Payment Ledger/outstanding observations from live verification
30. optional-app observations
31. limitations
32. confirmation that Sales/Purchase business tools were not widened
33. confirmation that no site/company/customer/user is hard-coded
34. confirmation that no manual GL/Payment Ledger/Journal Entry logic was added

Do not claim runtime verification that was not actually executed.

---

# 36. Exact Next Task

Do not automatically implement the next Accounts feature.

After Task 45, inspect the implementation report and choose the next slice based on actual usage and verified behavior.

Likely candidates include:

```text
A. Payment Entry read/query/aggregate
B. multi-invoice customer receipt
C. customer advance / unallocated receipt
D. supplier Purchase Invoice payment
E. Payment Reconciliation
```

The next task must be selected only after Task 45 results are reviewed.

Do not implement any of those inside Task 45.
