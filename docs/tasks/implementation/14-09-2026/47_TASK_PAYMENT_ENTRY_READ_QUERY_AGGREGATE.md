# Task 47 — Accounts V1.1: Payment Entry Read, Query, and Aggregate Intelligence

## Status

**Implementation task**

Task 45 introduced the first Accounts profile and the native:

```text
Submitted Sales Invoice
    ↓
prepare_sales_invoice_payment
    ↓
confirm_sales_invoice_payment
    ↓
Draft Payment Entry
    ↓
generic lifecycle submit / cancel / delete
```

The Task 45 runtime/accounting verification has now been completed separately.

The next requirement is to make Payment Entry operationally readable from the Accounts profile without adding any new money-moving workflow.

This task adds only:

```text
get_payment_entry
query_payment_entries
aggregate_payment_entries
```

---

# 1. Objective

Implement permission-safe, bounded, typed Payment Entry intelligence for the `accounts` profile.

After Task 47, an Accounts agent should be able to answer questions such as:

```text
"Show payment ACC-PAY-2026-00012"

"Find submitted payments received from Arkee Foods this month"

"Find the payment against Sales Invoice ACC-SINV-2026-00009"

"Show cancelled customer receipts from last week"

"How many customer receipts were submitted this month?"

"What is the total received amount in INR this month?"

"Group payments by Mode of Payment"

"Count Draft / Submitted / Cancelled Payment Entries"
```

without:

- exposing the complete Payment Entry document;
- exposing raw General Ledger or Payment Ledger rows;
- exposing full bank details;
- allowing raw SQL or arbitrary filter expressions;
- mutating any accounting record.

---

# 2. Scope

## In scope

Implement:

1. `get_payment_entry`
2. `query_payment_entries`
3. `aggregate_payment_entries`
4. typed Payment Entry read/query/aggregate contracts
5. Payment Entry-specific public field policy
6. Payment Entry Reference bounded child projection
7. optional bounded deduction summary where useful
8. typed Payment Entry filters
9. typed sorting
10. bounded pagination/limits using the repository's current convention
11. safe linked-document filtering, including Sales Invoice reference lookup
12. permission-aware reads
13. currency-safe aggregate semantics
14. Accounts profile registration
15. direct backend support
16. fixed typed REST backend support
17. tool catalog/docs update
18. focused and regression tests
19. implementation report

## Explicitly out of scope

Do NOT implement:

- Payment Entry creation changes
- multi-invoice customer receipt creation
- customer advance
- unallocated standalone receipt
- supplier payment
- Purchase Invoice payment
- Internal Transfer creation
- Payment Request
- Payment Reconciliation
- unreconciliation
- Journal Entry
- Payment Entry update
- Payment Entry child-row mutation
- Payment Entry PDF
- Payment Entry email
- bank reconciliation
- bank transaction import
- GL Entry read tools
- Payment Ledger Entry read tools
- raw Account search
- raw Bank Account detail exposure
- Chart of Accounts browsing
- permission-boundary refactor across existing Sales/Purchase services
- custom accounting calculations

This is a **read/intelligence task only**.

---

# 3. Architecture Principle

Reuse the current field-aware MCP read architecture.

The public surface should be:

```text
LLM / MCP Client
        ↓
typed Accounts read contract
        ↓
DocType-local Payment Entry field/filter policy
        ↓
permission-enforcing Frappe APIs
        ↓
bounded result
```

Not:

```text
LLM → raw filters → arbitrary SQL
LLM → full Payment Entry JSON
LLM → raw GL / Payment Ledger
LLM → complete bank/account metadata
```

Genericity belongs in the internal read/query/aggregate engine.

Payment Entry-specific public policy must remain explicit and bounded.

---

# 4. Inspect Current Repository First

Before changing code, inspect the current post-Task-45 worktree.

At minimum inspect and reuse the established patterns for:

- `get_customer`
- `query_customers`
- `aggregate_customers`
- Item read/query/aggregate
- Quotation read/query/aggregate
- Sales Order read/query/aggregate
- Delivery Note read/query/aggregate
- Sales Invoice read/query/aggregate
- current shared read service
- current shared query contracts
- current aggregate service
- Frappe v16 dictionary aggregate syntax
- field allowlists
- filter allowlists
- sort allowlists
- pagination/limit convention
- direct backend
- Task 40 REST backend
- static remote-operation registry
- Accounts profile from Task 45
- generated tool catalog
- public error/reference conventions

Do not introduce a new read engine if the current shared architecture fits.

If Payment Entry's child-reference filtering requires a specialized adapter, isolate only that specialized logic while keeping parent projection/filtering on the shared foundation.

---

# 5. ERPNext / Frappe Authority

Payment Entry is the ERPNext operational document for:

- Receive
- Pay
- Internal Transfer
- invoice allocations
- advances/unallocated payments
- bank/cash movement

Task 47 is read-only.

It must display native stored/runtime state rather than derive accounting state itself.

Do not independently calculate:

- invoice outstanding
- GL impact
- Payment Ledger balances
- exchange gain/loss
- account balances
- bank balances
- reconciled balances
- party balances

For linked invoice/reference data, expose only the Payment Entry's own bounded reference rows unless a separately permission-safe source lookup is explicitly required by the query contract.

---

# 6. Public Tool 1 — `get_payment_entry`

Implement:

```text
get_payment_entry
```

## Required input

Exact Payment Entry name.

Conceptually:

```json
{
  "name": "ACC-PAY-2026-00012"
}
```

Support the repository's existing controlled optional `fields` projection pattern if current Sales read tools already use it.

Do not invent a conflicting read contract.

---

# 7. `get_payment_entry` Field Policy

Create an explicit Payment Entry-local field allowlist.

Recommended header fields, subject to verification against current runtime metadata and existing conventions:

```text
name
docstatus
status
payment_type
company
posting_date
party_type
party
party_name
mode_of_payment
paid_from
paid_from_account_currency
paid_to
paid_to_account_currency
paid_amount
received_amount
total_allocated_amount
unallocated_amount
difference_amount
reference_no
reference_date
remarks
modified
owner             only if current read policy normally exposes it
creation          only if current read policy normally exposes it
```

Be conservative.

Do not expose a field merely because it exists in the DocType.

---

# 8. Account Field Exposure

Payment Entry contains accounting account names such as:

```text
paid_from
paid_to
```

These can be useful for reviewing a Payment Entry, but raw Chart-of-Accounts exploration is not part of this task.

Recommended policy:

- allow the exact account names already stored on the permitted Payment Entry when they are needed for accounting review;
- do not expose complete Account documents;
- do not return account balances;
- do not list all possible accounts;
- do not return bank credentials or account numbers;
- do not return secrets/custom integration identifiers.

Document the final policy in the implementation report.

---

# 9. Bank Data Minimization

Do not expose:

- full bank account number
- IBAN
- SWIFT/BIC
- routing credentials
- tokens
- integration credentials
- bank API metadata

If Payment Entry stores a Bank Account link that is useful for human review, expose only a bounded identifier/display value if the existing public policy supports it.

Do not automatically dereference Bank Account into sensitive fields.

---

# 10. Payment Entry Reference Projection

A Payment Entry can contain child rows under `references`.

Task 47 must support a bounded reference summary because it is essential for questions such as:

```text
"What invoice did this payment settle?"
```

Recommended safe child fields:

```text
reference_doctype
reference_name
bill_no                    only if needed and safe
payment_term               where native term allocation exists
total_amount
outstanding_amount
allocated_amount
exchange_rate              only if materially required and already part of safe review policy
```

Avoid:

- arbitrary child fields
- raw account internals
- hidden system fields
- custom fields by default
- unrestricted child serialization

Use runtime metadata only to validate field availability; runtime metadata does not automatically make a field public.

---

# 11. Deduction Summary

Payment Entry may have native deductions for:

- exchange difference
- early payment discount
- bank fee/write-off in broader flows

For `get_payment_entry`, decide whether a **bounded deduction summary** is useful.

If included, expose only review-relevant fields such as:

```text
account
cost_center               only if needed
amount
description               if safe/current field exists
```

Do not expose arbitrary accounting dimensions/custom fields automatically.

Do not calculate deductions.

If current V1 Payment Entries do not need this projection and the shared child-read architecture would expand materially, defer detailed deduction rows and expose only:

```text
difference_amount
deduction_count
deduction_total
```

where natively derivable from the permitted document.

Choose the smallest sound implementation.

---

# 12. `get_payment_entry` Permissions

Exact document retrieval must use a permission-enforcing native Frappe API.

Preferred principle:

```text
Frappe decides permission
MCP translates exception
```

Do not use an MCP role matrix.

Do not use Administrator impersonation.

Do not expose document fields before read permission has been established.

Follow the repository's current native-permission pattern.

---

# 13. Public Tool 2 — `query_payment_entries`

Implement:

```text
query_payment_entries
```

using the current field-aware query foundation.

It must support business questions without arbitrary SQL.

---

# 14. Query Projection Fields

Allow a useful bounded parent projection.

Recommended fields:

```text
name
docstatus
status
payment_type
company
posting_date
party_type
party
party_name
mode_of_payment
paid_from
paid_from_account_currency
paid_to
paid_to_account_currency
paid_amount
received_amount
total_allocated_amount
unallocated_amount
difference_amount
reference_no
reference_date
modified
```

Do not include child references in every list row by default unless the existing query architecture safely supports bounded child expansion.

Prefer:

```text
query → compact parent records
get → richer bounded references
```

---

# 15. Query Filters

Implement explicit typed allowlisted filters.

At minimum evaluate/include:

```text
name
docstatus
status
payment_type
company
posting_date
posting_date_from
posting_date_to
party_type
party
mode_of_payment
reference_no
paid_amount
paid_amount_min
paid_amount_max
received_amount
received_amount_min
received_amount_max
currency-aware account currency filters where justified
sales_invoice / linked reference filter
```

Use the repository's current filter language rather than inventing duplicate `_from/_to` fields if it already has a safe typed operator structure.

The conceptual capabilities matter more than exact contract spelling.

---

# 16. Payment Type Filter

Support exact values only from native valid Payment Entry types:

```text
Receive
Pay
Internal Transfer
```

Do not accept arbitrary strings silently.

Even though Task 45 creates only Receive Payment Entries, read/query should be generic enough to inspect existing permitted Payment Entries of all native types.

That does NOT mean Task 47 creates Pay/Internal Transfer documents.

---

# 17. Party Filters

Support:

```text
party_type
party
```

with safe typed behavior.

Common cases:

```text
party_type = Customer
party = Arkee Foods
```

Future existing ERPNext records may include Suppliers.

The read layer may inspect them if the authenticated user has permission, even though supplier payment creation is not implemented yet.

Do not artificially hide native Payment Entries solely because MCP did not create them.

---

# 18. Linked Sales Invoice Filter

This is an important Task 47 capability.

Support a typed way to ask:

```text
"Find Payment Entries linked to Sales Invoice ACC-SINV-2026-00009"
```

The Payment Entry → invoice relationship is stored in child reference rows, not a simple parent field.

Do NOT implement this as LLM-supplied SQL.

Do NOT expose an arbitrary child-table query language.

Implement one bounded specialized reference filter.

Possible public design:

```json
{
  "reference_doctype": "Sales Invoice",
  "reference_name": "ACC-SINV-2026-00009"
}
```

or:

```json
{
  "sales_invoice": "ACC-SINV-2026-00009"
}
```

Prefer the design that best matches the current typed query architecture.

---

# 19. Permission-Safe Linked Reference Filtering

The linked-reference implementation must not leak Payment Entry names that the authenticated user cannot read.

A valid architecture may be:

```text
typed reference filter
    ↓
find candidate Payment Entry parent names through a server-owned query
    ↓
feed candidates into the normal permission-aware Payment Entry parent query
    ↓
return only permitted parent documents
```

But do not adopt this mechanically.

First inspect:

- Frappe Query Builder
- current repository helpers
- ERPNext native query helpers
- permission query conditions
- child-table query behavior

Use the most idiomatic permission-safe Frappe approach available.

Requirements:

- no raw SQL string from caller;
- no `ignore_permissions=True`;
- no child query result returned directly before parent permission filtering;
- no existence leakage in public errors/counts;
- deterministic bounded result.

Document the chosen approach.

---

# 20. General Reference Filter

If the implementation is naturally safe and small, allow:

```text
reference_doctype
reference_name
```

for an allowlisted set such as:

```text
Sales Invoice
Purchase Invoice
Sales Order
Purchase Order
```

Do not allow arbitrary reference DocTypes without policy.

If adding generic references would materially widen the task, implement Sales Invoice only and document the limitation.

Task 47's required minimum is Sales Invoice reference lookup.

---

# 21. Query Sorting

Support only an allowlist.

Recommended sort fields:

```text
posting_date
name
modified
paid_amount
received_amount
```

Use current repository conventions for ascending/descending.

No caller-supplied raw `order_by`.

---

# 22. Query Pagination / Limits

Use the project's current bounded pagination convention.

Requirements:

- safe default limit
- hard maximum
- deterministic ordering
- no unbounded result set
- no model-controlled bypass

Do not create a new pagination model if existing Sales query tools already have one.

---

# 23. Query Permissions

Use permission-aware Frappe reads.

Requirements:

```text
ignore_permissions=False
```

where applicable.

Do not reimplement role permission rules.

Do not manually maintain allowed users/roles.

Do not return rows that Frappe would not return to the authenticated user.

---

# 24. Public Tool 3 — `aggregate_payment_entries`

Implement:

```text
aggregate_payment_entries
```

through the current shared aggregate service when suitable.

Do not write a second aggregate engine.

---

# 25. Aggregate Metrics

Recommended V1 metrics:

```text
count
sum_paid_amount
sum_received_amount
sum_total_allocated_amount
sum_unallocated_amount
```

Only include metrics that can be represented safely using the existing aggregate engine.

Do not expose arbitrary SQL aggregates.

Do not expose caller-supplied expressions.

---

# 26. Currency Safety — Critical

Never return a misleading total such as:

```text
INR 10,000
+
USD 500
=
10,500
```

Payment Entry can involve different account currencies.

Task 47 must define safe aggregate semantics.

Recommended rules:

### Count

Always safe subject to filters/permissions.

### Amount sums

A sum is allowed only when:

1. the query is constrained to a single relevant currency; or
2. the aggregate groups by the corresponding currency.

For `paid_amount`, group/validate using:

```text
paid_from_account_currency
```

For `received_amount`, group/validate using:

```text
paid_to_account_currency
```

If the installed fields/contracts use another exact currency field, use the installed runtime names.

### Mixed currencies

Fail closed with a bounded semantic error or force currency grouping according to the existing aggregate contract.

Do not perform exchange conversion in MCP.

Do not normalize using current FX rates.

---

# 27. Aggregate Grouping

Evaluate/include bounded grouping by:

```text
docstatus/status
payment_type
company
party_type
party
mode_of_payment
paid_from_account_currency
paid_to_account_currency
posting date period
```

Date-period grouping must use the repository's current safe approach if one already exists.

Do not invent free-form SQL date expressions.

---

# 28. Aggregate Filters

Reuse the same compatible parent Payment Entry filter policy where possible.

At minimum:

```text
date range
docstatus/status
payment_type
company
party_type
party
mode_of_payment
currency
```

Linked invoice filtering in aggregate is optional for Task 47 unless it can be added safely on the same specialized reference-filter foundation.

Do not widen the aggregate engine merely to satisfy one specialized child filter.

---

# 29. Status / Docstatus Semantics

Do not conflate:

```text
docstatus
```

and:

```text
status
```

Expose/filter both only if useful.

`docstatus` is the Frappe lifecycle state:

```text
0 Draft
1 Submitted
2 Cancelled
```

`status` is ERPNext business status and may have its own values.

Use native stored values.

Do not derive custom MCP status.

---

# 30. Read Existing Payment Entries, Not Only MCP-Created Ones

Task 47 tools must work on any Payment Entry the authenticated Frappe user is allowed to read, including records created:

- manually in ERPNext Desk
- through other integrations
- through Task 45 MCP
- through future ERPNext workflows

Do not tag or restrict records to `mcp_erpnext` origin.

ERPNext is the system of record.

---

# 31. Data Minimization

The LLM should receive only the business information needed to answer the user's payment question.

Allowed categories:

```text
identity
lifecycle status
payment type
company
party
dates
Mode of Payment
bounded account labels
currencies
paid/received/allocated/unallocated amounts
transaction reference
bounded invoice/order references
bounded deduction summary
remarks
```

Forbidden categories by default:

```text
full document JSON
full Chart of Accounts
account balances
bank balances
full Bank Account details
IBAN/SWIFT
bank credentials
raw GL
raw Payment Ledger
cache state
secrets
integration tokens
all custom fields
framework internals
tracebacks
SQL
```

---

# 32. Runtime Metadata

Use runtime metadata to confirm fields exist on the configured site.

At minimum verify metadata for:

```text
Payment Entry
Payment Entry Reference
Payment Entry Deduction
```

Do not assume static JSON is the complete site schema.

But:

```text
field exists in metadata
```

does NOT imply:

```text
field is public to LLM
```

Public allowlists remain explicit code/policy.

---

# 33. Optional Apps

Task 44 confirmed installed India Compliance hooks can affect Payment Entry runtime behavior.

Task 47 is read-only and must remain optional-app neutral.

Do not add India Compliance-specific Payment Entry fields merely because the app is installed.

If a universally useful optional-app field is proposed, defer it unless there is an explicit public-field requirement.

---

# 34. Direct Backend

All three tools must support the current direct backend.

Requirements:

- configured site
- authenticated user
- Accounts profile
- normal Frappe permissions
- same contracts/services as REST
- JSON-safe bounded output
- no hard-coded site/user/company

---

# 35. REST Backend

Add fixed typed remote operations for:

```text
get_payment_entry
query_payment_entries
aggregate_payment_entries
```

Requirements:

- static remote registry
- typed JSON-safe payloads
- same authoritative services
- no arbitrary DocType dispatch
- no arbitrary method/import path
- no raw filter expression
- no caller-selected identity
- no caller-selected site
- direct/REST result parity
- direct/REST error parity

---

# 36. Public Errors

Use existing bounded public-error/reference handling.

Possible errors include:

```text
NOT_FOUND
PERMISSION_DENIED
INVALID_FIELD
INVALID_FILTER
INVALID_SORT
INVALID_LIMIT
INVALID_REFERENCE_FILTER
UNSUPPORTED_REFERENCE_DOCTYPE
MIXED_CURRENCY_AGGREGATE
INVALID_AGGREGATE
INVALID_GROUP_BY
```

Use project-standard codes where equivalents already exist.

Do not create duplicate error taxonomies unnecessarily.

No raw exception/traceback exposure.

---

# 37. Accounts Profile Registration

After Task 47, Accounts should expose:

```text
prepare_sales_invoice_payment
confirm_sales_invoice_payment

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

Exact inventory depends on how generic lifecycle tools are counted/registered in the current implementation.

Do not copy unrelated Sales/Purchase tools into Accounts.

---

# 38. No Write Expansion

Task 47 must not add any new mutating Payment Entry capability.

In particular, do not add:

```text
update_payment_entry
add_payment_reference
change_allocation
change_paid_amount
change_bank_account
add_deduction
reconcile_payment
```

Existing Task 45 create and generic lifecycle remain the only Accounts write surfaces.

---

# 39. Implementation Steps

## Step 1 — Inspect post-Task-45 code

Confirm:

- Accounts profile inventory
- current Payment Entry lifecycle policy
- shared field-aware read architecture
- query contracts
- aggregate architecture
- current REST patterns

## Step 2 — Define Payment Entry field policy

Add explicit:

- header read fields
- query projection fields
- filter fields/operators
- sort fields
- aggregate metrics
- group-by fields

## Step 3 — Implement `get_payment_entry`

Use permission-enforcing Frappe exact read.

Add bounded reference child projection.

Optionally add bounded deduction summary.

## Step 4 — Implement `query_payment_entries`

Reuse shared field-aware query engine for parent fields.

Implement specialized linked Sales Invoice reference filter safely.

## Step 5 — Implement `aggregate_payment_entries`

Reuse shared aggregate engine.

Enforce currency-safe sums.

## Step 6 — Contracts

Add explicit typed contracts and forbid extra fields.

## Step 7 — Accounts registration

Register only the three new read tools.

## Step 8 — REST parity

Add fixed typed remote operations.

## Step 9 — Tests

Implement the required test matrix below.

## Step 10 — Catalog/docs

Regenerate tool catalog and update architecture/read docs where current convention requires.

## Step 11 — Report

Create the required implementation report.

---

# 40. Allowed Changes

Changes are allowed only where necessary, including equivalents of:

```text
contracts/accounts/payment_entry_read.py
services/accounts/payment_entry_read.py
tools/accounts/payment_entry_read.py
profiles/accounts.py
contracts/registry.py
services/common/read.py               only if safe shared support is needed
services/common/aggregate.py          only if currency-safe reusable support is needed
remote_operations.py
tests/...
docs/TOOLS.md
```

Do not force these exact filenames if current repository conventions use different names.

Shared helper changes must:

- be generic;
- not change existing Sales/Purchase behavior unexpectedly;
- be covered by regression tests.

---

# 41. Required Tests — Registration / Contracts

1. `get_payment_entry` registered only in Accounts.
2. `query_payment_entries` registered only in Accounts.
3. `aggregate_payment_entries` registered only in Accounts.
4. Sales inventory unchanged.
5. Purchase inventory unchanged.
6. Task 45 prepare/confirm inventory unchanged.
7. contracts forbid extra fields.
8. arbitrary raw SQL/filter expressions are rejected.
9. arbitrary DocType input is absent.
10. catalog generation is deterministic.

---

# 42. Required Tests — Exact Read

11. permitted exact Payment Entry returns bounded header.
12. missing Payment Entry returns bounded not-found.
13. read-denied Payment Entry fails closed.
14. raw document is not returned.
15. unsupported requested field fails closed.
16. allowed projection works.
17. default projection is bounded.
18. Draft PE can be read when permitted.
19. Submitted PE can be read when permitted.
20. Cancelled PE can be read when permitted.
21. Receive PE is represented correctly.
22. existing Pay PE can be represented correctly.
23. existing Internal Transfer PE can be represented correctly.

---

# 43. Required Tests — References

24. SI-linked Payment Entry returns bounded SI reference.
25. multiple reference rows are bounded.
26. payment-term reference rows preserve term identity where present.
27. allocated amount comes from native stored child state.
28. full child serialization is not returned.
29. unsupported child field is not exposed.
30. references to other native allowed DocTypes remain bounded if supported.
31. references do not cause a source document permission bypass/dereference leak.

---

# 44. Required Tests — Bank / Sensitive Data

32. no full Bank Account details are returned.
33. no IBAN/SWIFT/bank credentials are returned.
34. no secrets are returned.
35. paid_from/paid_to exposure follows explicit policy only.
36. no account balances are returned.
37. no Chart-of-Accounts expansion occurs.

---

# 45. Required Tests — Query

38. query by date range.
39. query by docstatus.
40. query by status where supported.
41. query by payment type.
42. query by company.
43. query by party type.
44. query by Customer.
45. query by Mode of Payment.
46. query by reference number.
47. query by paid amount/range according to contract.
48. query by received amount/range according to contract.
49. allowed projection works.
50. unsupported projection fails.
51. allowed sort works.
52. unsupported sort fails.
53. default limit is bounded.
54. max limit is enforced.
55. permission filtering is enforced.
56. no `ignore_permissions=True`.

---

# 46. Required Tests — Linked Sales Invoice Query

57. filter by linked Sales Invoice returns matching permitted Payment Entry.
58. nonmatching invoice returns empty bounded result.
59. multiple PEs against same SI are handled.
60. cancelled PE behavior follows filter/status criteria.
61. child candidate lookup never returns unauthorized parent PE.
62. unauthorized parent PE name/existence is not leaked.
63. raw child-table filter expression is not public.
64. unsupported reference DocType fails if generic reference filter is implemented.
65. REST and direct linked-reference results conform.

---

# 47. Required Tests — Aggregate

66. count all permitted filtered Payment Entries.
67. count by docstatus.
68. count by payment type.
69. count by party.
70. group by Mode of Payment.
71. group by company.
72. group by currency where supported.
73. sum paid amount in one currency.
74. sum received amount in one currency.
75. sum allocated amount where semantically safe.
76. sum unallocated amount where semantically safe.
77. mixed-currency paid sum without grouping fails closed.
78. mixed-currency received sum without grouping fails closed.
79. currency-grouped sums return separate groups.
80. no MCP FX conversion occurs.
81. unsupported aggregate fails.
82. unsupported group-by fails.
83. aggregate respects permissions.
84. shared Frappe v16 dict aggregate syntax remains used.

---

# 48. Required Tests — Data Minimization

85. no raw GL Entry is returned.
86. no raw Payment Ledger Entry is returned.
87. no full Customer document is returned.
88. no unrelated invoices are returned.
89. no custom fields are public automatically.
90. no cache/internal approval data appears.
91. no traceback appears in bounded errors.

---

# 49. Required Tests — REST / Direct

92. direct get works.
93. direct query works.
94. direct aggregate works.
95. fixed REST get operation exists.
96. fixed REST query operation exists.
97. fixed REST aggregate operation exists.
98. malformed payload fails closed.
99. unknown remote operation fails closed.
100. arbitrary method/import dispatch remains impossible.
101. caller cannot choose site.
102. caller cannot choose identity.
103. direct/REST successful shapes conform.
104. direct/REST bounded errors conform.

---

# 50. Required Regression Tests

105. Task 45 prepare/confirm payment tests remain green.
106. Payment Entry lifecycle tests remain green.
107. Accounts profile initializes.
108. Sales profile inventory unchanged.
109. Purchase profile inventory unchanged.
110. Quotation/SO/DN/SI flows remain green.
111. Delivery Note Task 42 tests remain green.
112. DN → SI Task 43 tests remain green.
113. ApprovalStore tests retain current expected state.
114. REST backend tests retain current expected state.
115. compileall passes.
116. tool catalog generation/check passes.
117. `git diff --check` passes.

If the repository still has known unrelated pre-existing failures, report exact test names and demonstrate that Task 47 did not introduce them.

Do not simply label failures "unrelated" without evidence.

---

# 51. Runtime Verification

Because Task 47 is read-only, runtime verification should use existing authorized records and must not create accounting transactions merely for testing reads.

Where authorized records exist, verify:

```text
get existing Draft PE
get existing Submitted PE
get existing Cancelled PE
query Customer receipts
query by date
query by linked Sales Invoice
aggregate count
aggregate same-currency received amount
```

Verify authenticated permissions with at least:

- a permitted user;
- a denied/restricted scenario where safely available.

If REST backend is configured, perform real read-only REST round trips.

Do not mutate Payment Entry / GL / Payment Ledger during Task 47 runtime verification.

---

# 52. Acceptance Criteria

Task 47 is complete only when:

1. `get_payment_entry` exists.
2. `query_payment_entries` exists.
3. `aggregate_payment_entries` exists.
4. all are Accounts-profile only.
5. exact reads enforce Frappe permission.
6. get output is bounded.
7. Payment Entry references are bounded.
8. sensitive bank details are not exposed.
9. query filters are typed and allowlisted.
10. query projections are allowlisted.
11. query sorting is allowlisted.
12. result size is bounded.
13. linked Sales Invoice search exists.
14. linked-reference search is parent-permission safe.
15. no arbitrary child query language exists.
16. aggregate reuses current shared foundation where sound.
17. mixed-currency sums cannot be misleading.
18. no MCP FX normalization is introduced.
19. raw GL is not exposed.
20. raw Payment Ledger is not exposed.
21. no new Payment Entry write capability exists.
22. direct backend works.
23. REST backend parity exists.
24. Sales/Purchase profiles remain unchanged.
25. Task 45 create/lifecycle behavior remains unchanged.
26. focused tests pass.
27. runtime read-only verification is truthfully reported.
28. no site/company/customer/user is hard-coded.

---

# 53. Expected Result

After Task 47, Accounts should support:

```text
WRITE SIDE
────────────────────────────
prepare_sales_invoice_payment
confirm_sales_invoice_payment

generic submit/cancel/delete


READ SIDE
────────────────────────────
get_payment_entry
query_payment_entries
aggregate_payment_entries
```

Example agent behavior:

```text
User:
"Find payments received from Arkee Foods this month."

Accounts Agent:
→ query_payment_entries(
     payment_type="Receive",
     party_type="Customer",
     party="Arkee Foods",
     posting_date=...
   )
```

```text
User:
"Which payment settled ACC-SINV-2026-00009?"

Accounts Agent:
→ query_payment_entries(
     linked Sales Invoice = "ACC-SINV-2026-00009"
   )
```

```text
User:
"How much did we receive by bank transfer this month?"

Accounts Agent:
→ aggregate_payment_entries(
     metric=sum_received_amount,
     mode_of_payment=...,
     grouped/constrained by destination currency
   )
```

No accounting mutation is required for these questions.

---

# 54. Limitations After Task 47

Still intentionally not implemented:

- multi-invoice customer receipt creation
- customer advance
- standalone unallocated receipt
- supplier payment
- internal transfer creation
- Payment Request
- Payment Reconciliation
- Journal Entry
- Payment Entry PDF
- Payment Entry email
- bank reconciliation
- bank transaction import
- arbitrary Payment Entry update
- custom GL/Payment Ledger access

These are not Task 47 defects.

---

# 55. Deliverable Report

Create:

```text
docs/inspect/PAYMENT_ENTRY_READ_QUERY_AGGREGATE_IMPLEMENTATION_REPORT.md
```

The report must contain:

1. exact files changed
2. public tools added
3. exact contracts
4. default get fields
5. optional get fields
6. reference child fields
7. deduction exposure decision
8. sensitive-data exclusions
9. query filter policy
10. query projection policy
11. query sort policy
12. pagination/limit policy
13. linked Sales Invoice filter implementation
14. linked-reference permission strategy
15. aggregate metrics
16. aggregate group fields
17. currency-safe aggregation behavior
18. mixed-currency rejection/grouping behavior
19. direct backend behavior
20. REST backend behavior
21. runtime metadata checks
22. optional-app observations
23. test files added/changed
24. exact test commands
25. exact pass/fail/error counts
26. any pre-existing unrelated failures with exact names
27. runtime read-only checks performed
28. runtime checks not performed and why
29. confirmation that no accounting records were mutated for read verification
30. confirmation that no new write capability was added
31. confirmation that Sales/Purchase profile inventories remained unchanged
32. known limitations

Do not claim a scenario was verified unless it was actually executed.

---

# 56. Exact Next Task

After Task 47 is reviewed and accepted, the exact next task should be:

## Task 48 — Multi-Invoice Customer Receipt Native Allocation Audit

Reason:

Task 44 already established that ERPNext Payment Entry supports multiple invoice references, but the native `get_payment_entry("Sales Invoice", name, ...)` factory is single-source.

Before exposing a public:

```text
prepare_customer_payment(references=[...])
```

contract, inspect and freeze:

- outstanding invoice retrieval
- same Customer / Company constraints
- party-account compatibility
- currency compatibility
- reference-row construction
- payment-term rows
- partial allocation across multiple invoices
- overpayment/unallocated remainder
- stale outstanding/concurrency
- native validation
- approval fingerprint
- data minimization

Task 48 must be an **audit first**, not immediate implementation.

Do not implement multi-invoice allocation inside Task 47.
