# TASK 33 — Sales Invoice Field-Aware Read / Query / Aggregate Capability

## Status

Ready for implementation after:

- Task 30 — Sales Order Field-Aware Query Naming Normalization
- Task 31 — Shared Internal Aggregate Foundation
- Task 32 — Quotation Field-Aware Read / Query / Aggregate Capability

Task 32 has established the current Sales-profile Quotation read pattern:

```text
get_quotation
query_quotations
aggregate_quotations
```

Task 31 has already created the shared internal aggregate foundation:

```text
mcp_erpnext/services/common/aggregate.py
```

This task must reuse those established patterns rather than creating another read architecture.

---

## 1. Scope

Upgrade the existing Sales Invoice read capability from the current compact/common-reader implementation to a first-class, field-aware Sales Invoice read/query/aggregate capability.

The final public Sales Invoice read surface for this task must be:

```text
get_sales_invoice
query_sales_invoices
aggregate_sales_invoices
```

This task includes:

- preserving and upgrading `get_sales_invoice` as the exact single-document read tool;
- replacing the current deterministic multi-record `search_sales_invoices` public capability with `query_sales_invoices`;
- implementing `aggregate_sales_invoices`;
- adding Sales Invoice-specific field/filter/sort/group/metric policy;
- handling Sales Invoice accounting semantics deliberately, especially:
  - posting date,
  - due date,
  - status/docstatus,
  - outstanding amount,
  - paid amount where appropriate,
  - returns/credit notes,
  - return references,
  - currency;
- reusing Task 31 shared aggregate mechanics;
- updating contracts, wrapper registration, registry, Sales profile, generated catalog/docs, and tests required by the public read capability.

This task does **not** implement a Sales Invoice Item query/aggregate tool.

---

## 2. Objective

Make Sales Invoice capable of answering three distinct classes of questions cleanly:

```text
Exact document question
    -> get_sales_invoice

Filtered/list/detail question
    -> query_sales_invoices

Count/total/outstanding/grouped analytics question
    -> aggregate_sales_invoices
```

Examples:

```text
"Give me ACC-SINV-2026-00010 details"
    -> get_sales_invoice

"Show unpaid invoices for Customer X"
    -> query_sales_invoices

"Show overdue invoices due before today"
    -> query_sales_invoices

"How many Sales Invoices does Customer X have?"
    -> aggregate_sales_invoices

"What is Customer X's total outstanding Sales Invoice amount?"
    -> aggregate_sales_invoices

"Give outstanding amount status-wise"
    -> aggregate_sales_invoices
```

Pure aggregate questions must not retrieve source rows and count/sum them in the agent.

---

## 3. Frozen Public Naming Convention

The project public read naming convention is:

```text
search_*     = discovery/resolution candidate search
get_*        = exact single-document read
query_*      = deterministic field-aware multi-record retrieval
aggregate_*  = server-side analytics
```

Therefore, if current-tree inspection confirms the existing `search_sales_invoices` is the deterministic compact list read, rename/replace it with:

```text
query_sales_invoices
```

Do not keep a public alias merely for historical compatibility unless an actual current repository/external integration dependency is found and documented.

Do not rename legitimate resolver/discovery `search_*` tools.

---

## 4. Architecture Decisions to Preserve

### Explicit public tools

Public MCP surface remains DocType-specific:

```text
get_sales_invoice
query_sales_invoices
aggregate_sales_invoices
```

Do not add:

```text
get_document
query_documents
aggregate_documents
```

or any other public generic DocType tool.

### Internal reuse

Reuse:

```text
mcp_erpnext/services/common/aggregate.py
```

for generic COUNT/SUM/AVG/MIN/MAX/group execution mechanics.

Reuse other established read/filter helpers only where they fit without weakening Sales Invoice-specific policy.

### DocType policy remains local

Sales Invoice-specific policy must remain in Sales Invoice-specific contracts/services/constants.

Do not centralize all fields, filters, metrics, or groups into one global config.

### Contract/service separation remains as-is

Do not merge contract literals and service constants.

Do not implement contract/service allowlist synchronization infrastructure in this task.

### Runtime metadata is validation/evidence, not auto-exposure

Do not automatically expose every runtime/custom field.

Any public field/filter/sort/group/metric must be deliberately allowlisted.

---

## 5. Mandatory Current-Tree Inspection Before Editing

Before changing code, inspect the current working tree and trace the existing Sales Invoice flow.

At minimum inspect:

```text
mcp_erpnext/services/common/read.py
mcp_erpnext/services/common/aggregate.py

mcp_erpnext/services/selling/sales_invoice.py
mcp_erpnext/services/selling/sales_invoice_read.py   # if it already exists
mcp_erpnext/services/selling/quotation_read.py
mcp_erpnext/services/selling/sales_order_read.py

mcp_erpnext/contracts/selling/
mcp_erpnext/tools/selling/
mcp_erpnext/tools/read.py

mcp_erpnext/contracts/registry.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tests/

scripts/generate_tool_catalog.py
docs/TOOLS.md
docs/architecture/
```

Confirm actual paths before editing.

Specifically identify:

1. current public `get_sales_invoice`;
2. current public `search_sales_invoices`;
3. whether they are still thin wrappers over `services/common/read.py`;
4. current fixed/default output fields;
5. existing permissions behavior;
6. current contract classes;
7. current registry/profile inventory;
8. all tests referencing those names;
9. any repository-local production consumer hardcoding `search_sales_invoices`;
10. the current create/confirm Sales Invoice service in `services/selling/sales_invoice.py`.

### Critical boundary

The existing Sales Invoice create/confirm workflow must not be mixed up with this read refactor.

If `services/selling/sales_invoice.py` already owns write/create behavior, strongly prefer a separate read module such as:

```text
services/selling/sales_invoice_read.py
contracts/selling/sales_invoice_read.py
tools/selling/sales_invoice_read.py
```

if that matches the Quotation/Sales Order conventions.

Do not reorganize write code merely for naming symmetry.

---

## 6. Inspect Mature Existing Read Patterns

Before designing Sales Invoice contracts/services, inspect the current implementations of:

```text
Customer
  get_customer
  query_customers
  aggregate_customers

Item
  get_item
  query_items
  aggregate_items

Quotation
  get_quotation
  query_quotations
  aggregate_quotations

Sales Order
  get_sales_order
  query_sales_orders
  aggregate_sales_orders
  query_sales_order_items
```

Quotation Task 32 is likely the closest header-level template, but do not copy it mechanically.

Sales Invoice has accounting semantics that Quotation does not have.

---

## 7. Mandatory ERPNext Source and Runtime Metadata Inspection

Before freezing any field/filter/sort/group/metric allowlist, inspect the **installed** Sales Invoice metadata and controller.

The Task 32 report identified the current installed versions as:

```text
Frappe 16.33.1
ERPNext 16.34.2
```

Reconfirm the actual versions in the implementation environment before coding.

Inspect installed source equivalent to:

```text
apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.json
apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py
```

Also inspect relevant parent/controller behavior if needed.

Attempt runtime metadata inspection with:

```python
frappe.get_meta("Sales Invoice")
```

through the safe existing Bench/site mechanism if a usable site is available.

### Report requirements

The implementation report must state:

- Frappe version;
- ERPNext version;
- whether runtime metadata succeeded;
- fallback source/JSON used if runtime metadata failed;
- actual important fieldnames discovered;
- deliberately exposed fields;
- meaningful fields intentionally excluded.

Do not guess fieldnames from prior tasks.

Do not auto-expose custom fields found at runtime.

---

## 8. Accounting Semantics That Must Be Understood Before Coding

Sales Invoice is not just another selling document.

Before selecting public fields/metrics, inspect and account for these concepts:

### Posting date

`posting_date` determines the accounting period for the invoice.

### Due date

`due_date` is relevant to payment due/overdue behavior.

### Outstanding amount

`outstanding_amount` represents the amount that remains open after payments/credits/allocations according to ERPNext's current accounting/payment-ledger behavior.

It is a first-class read/analytics use case.

### Status

Sales Invoice status may distinguish concepts such as:

- Draft
- Unpaid
- Overdue
- Partly Paid
- Paid
- Return
- Credit Note Issued
- Cancelled

Do not hardcode this list from this task document.

Inspect the installed ERPNext implementation and existing metadata/controller behavior and expose only validated status semantics.

### Returns / Credit Notes

Inspect:

```text
is_return
return_against
```

and any relevant debit-note/rate-adjustment fields in the installed version.

A return/credit note can affect totals and outstanding analytics.

Do not silently exclude returns from all queries or aggregates unless there is an existing ERPNext/project convention supporting that behavior.

Instead, provide explicit filtering/grouping where appropriate and document aggregate semantics.

### Currency

Do not combine transaction-currency monetary values across different currencies into an unlabeled result.

Use the safe currency grouping policy already established for Quotation/Sales Order where appropriate.

### Company/base currency

If base-currency metrics are considered, remember that base currency belongs to Company context.

Do not aggregate base values across companies without preserving Company/base-currency meaning.

Prefer a smaller safe metric set over complicated or misleading base-currency analytics.

---

## 9. Deliberate Public Field Policy

After source/runtime inspection, define a bounded Sales Invoice field allowlist.

Evaluate useful fields in the following categories.

These are candidates to inspect, not mandatory blind exposure.

### Identity

```text
name
customer
customer_name
```

### Accounting/lifecycle

```text
posting_date
due_date
docstatus
status
company
```

### Return/credit-note context

```text
is_return
return_against
is_debit_note
```

Only expose fields that exist and are semantically useful in the installed ERPNext version.

### Currency and pricing

```text
currency
conversion_rate
selling_price_list
price_list_currency
```

### Commercial totals

```text
total_qty
base_total
base_net_total
total
net_total
base_grand_total
grand_total
base_total_taxes_and_charges
total_taxes_and_charges
```

Do not expose all of these automatically; choose the useful set.

### Receivable/payment state

Evaluate:

```text
outstanding_amount
paid_amount
base_paid_amount
total_advance
write_off_amount
```

`outstanding_amount` should receive special consideration because it directly supports Accounts Receivable questions.

Other payment-related fields should only be exposed if their invoice-header semantics are clear and useful.

### Accounting dimensions/context

Evaluate:

```text
debit_to
cost_center
project
territory
customer_group
sales_partner
```

Expose only stable/useful header fields.

### Customer PO/reference

Evaluate:

```text
po_no
po_date
```

### Stock behavior

Evaluate:

```text
update_stock
```

only if useful for read/search questions.

### Audit

Consistent with existing mature read tools, evaluate:

```text
owner
creation
modified
```

### Exclude by default

Do not expose indiscriminately:

- child tables,
- full tax breakup structures,
- payment schedule rows,
- advance rows,
- packed items,
- timesheet rows,
- addresses/contact display blobs,
- terms text,
- print fields,
- pricing-rule internals,
- hidden workflow/support fields,
- internal implementation flags with no MCP use case.

---

## 10. Default Projection

Do not dump the entire Sales Invoice document.

Define bounded defaults for:

```text
get_sales_invoice
query_sales_invoices
```

### Exact read default

Should provide a useful invoice summary.

Evaluate a default equivalent in intent to:

```text
name
customer
customer_name
posting_date
due_date
docstatus
status
currency
grand_total
outstanding_amount
is_return
return_against
```

Exact fields must be validated against current metadata and existing project style.

### Query default

Use a smaller list/business projection.

Evaluate something equivalent in intent to:

```text
name
customer
customer_name
posting_date
due_date
status
currency
grand_total
outstanding_amount
```

Do not mechanically use this exact list if inspection finds better existing conventions.

---

## 11. `get_sales_invoice`

`get_sales_invoice` remains the exact single-document read tool.

Target conceptual request:

```text
get_sales_invoice(
    sales_invoice=<exact Sales Invoice name>,
    fields=[optional allowlisted projection]
)
```

Requirements:

- exact known document identifier;
- explicit read permission check consistent with mature exact-read services;
- bounded default projection;
- optional typed field projection;
- arbitrary fields rejected;
- no full-document dump;
- no write behavior;
- current MCP error envelope preserved.

Inspect Task 32's `get_quotation` implementation and reuse its sound permission/projection strategy where applicable.

---

## 12. `query_sales_invoices`

Replace the deterministic compact public:

```text
search_sales_invoices
```

with:

```text
query_sales_invoices
```

if current-tree inspection confirms the naming mismatch.

This becomes the main multi-record Sales Invoice read tool.

### Filter categories to inspect and intentionally support

#### Identity

```text
name
customer
customer_name
```

#### Lifecycle/accounting

```text
status
docstatus
company
```

#### Return state

```text
is_return
return_against
is_debit_note
```

where actually present/useful.

#### Currency

```text
currency
```

and selected price-list/account currency context only if useful.

#### Posting/due dates

Support appropriate ranges:

```text
posting_date_from
posting_date_to

due_date_from
due_date_to
```

These are important for questions such as:

```text
"Show invoices posted this month"
"Show invoices due this week"
"Show invoices due before X"
```

#### Audit ranges

If consistent with mature tools:

```text
creation_from
creation_to
modified_from
modified_to
```

#### Monetary ranges

Evaluate useful ranges such as:

```text
min_grand_total
max_grand_total

min_outstanding_amount
max_outstanding_amount
```

Potentially:

```text
min_net_total
max_net_total
```

only if useful.

### Overdue questions

Do not invent a separate public:

```text
get_overdue_invoices
```

Use `query_sales_invoices` through:

- validated status filtering where ERPNext status supports `Overdue`, and/or
- due-date/outstanding filters when appropriate.

Do not derive an alternative status model that conflicts with ERPNext.

### Sorting

Allowlist useful deterministic sort fields, likely including candidates such as:

```text
name
customer
customer_name
posting_date
due_date
status
company
grand_total
outstanding_amount
creation
modified
```

Validate all against source/metadata.

As established by Task 32, add deterministic document-name tie-breaking where the current pattern requires it.

### Pagination

Support established:

```text
limit
offset
```

semantics.

The query response:

```text
count
```

must mean **rows returned in the current result/page**, not total matching database records.

Database-wide counts belong to `aggregate_sales_invoices`.

---

## 13. `aggregate_sales_invoices`

Add:

```text
aggregate_sales_invoices
```

using Task 31:

```text
services/common/aggregate.py
```

Do not duplicate generic aggregate builders/executors.

### Core metric candidates

After source/metadata inspection, evaluate a deliberate metric set such as:

```text
count

sum_grand_total
avg_grand_total
min_grand_total
max_grand_total

sum_outstanding_amount
```

Additional candidates may include:

```text
sum_net_total
sum_total_qty
```

if they provide clear business value and match existing patterns.

### Outstanding amount

`sum_outstanding_amount` is particularly important because it answers:

```text
"How much does Customer X still owe across Sales Invoices?"
"What is total outstanding by customer?"
"What is overdue outstanding?"
```

But make sure the exact semantics are based on the current stored Sales Invoice field/payment-ledger behavior and filters.

### Paid amount

Do **not** automatically treat:

```text
sum_paid_amount
```

as equivalent to "total payments received against invoices".

Inspect ERPNext semantics first.

If `paid_amount` is primarily POS/direct invoice payment state or does not reliably represent all separately allocated Payment Entries in the intended way, do not expose a misleading aggregate metric.

Record the finding in the implementation report.

### Return / Credit Note semantics

Aggregate behavior must be explicit.

If return invoices carry negative amounts, normal aggregate results may naturally net them with positive invoices.

Do not silently rewrite signs.

Support `is_return` filtering/grouping where useful so callers can separate:

```text
normal invoices
returns/credit notes
```

Document the behavior.

---

## 14. Aggregate Grouping

Evaluate useful group fields such as:

```text
customer
customer_name
status
company
currency
is_return
posting_date
due_date
customer_group
territory
```

Only expose useful fields actually confirmed in the installed source.

Do not permit arbitrary grouping.

### Important

For daily/date grouping, use the actual stored Date field only.

Do not implement month/week/year expression grouping in this task unless the existing shared aggregate architecture already supports it cleanly without new complexity.

---

## 15. Currency-Safe Aggregate Policy

Follow the sound monetary grouping principle established by Sales Order/Quotation.

For transaction-currency monetary metrics such as:

```text
grand_total
net_total
outstanding_amount
```

automatically preserve/include `currency` grouping unless the request already groups by currency or filters to one currency in a way consistent with the existing shared pattern.

Do not return:

```text
total_outstanding = 50000
```

across INR/USD/EUR documents without currency context.

Example safe shape conceptually:

```text
currency = INR
sum_outstanding_amount = ...

currency = USD
sum_outstanding_amount = ...
```

### Base-currency metrics

If base metrics are exposed at all, ensure Company/base-currency context cannot be mixed misleadingly.

A safe choice for Task 33 may be to keep aggregate metrics primarily transaction-currency based unless current business requirements justify base metrics.

---

## 16. Query and Aggregate Filter Consistency

Where a filter logically applies to both tools, it must have the same meaning in:

```text
query_sales_invoices
aggregate_sales_invoices
```

Examples:

```text
customer
status
docstatus
company
currency
is_return
posting_date range
due_date range
grand_total range
outstanding_amount range
```

Prefer a shared Sales Invoice-local filter helper if it mirrors the Task 32 Quotation pattern cleanly.

Do not duplicate slightly different filter behavior in query and aggregate.

---

## 17. Permission Requirements

All Sales Invoice reads must preserve Frappe permissions and MCP user identity context.

### Exact read

Use a permission-aware exact-document strategy consistent with current mature reads.

If using:

```python
frappe.get_doc("Sales Invoice", name)
```

explicitly verify/read-check permission according to established project behavior.

### Query

Use:

```python
frappe.get_list(..., ignore_permissions=False)
```

or the current equivalent permission-aware seam.

### Aggregate

Use Task 31's shared permission-aware aggregate executor.

Do not use:

```text
frappe.get_all
ignore_permissions=True
raw SQL permission bypass
```

for these public MCP reads.

---

## 18. Error Handling

Preserve the existing MCP error architecture.

Do not add a new error framework.

Handle cases such as:

- Sales Invoice not found;
- permission denied;
- unsupported field;
- invalid filter;
- invalid status/docstatus value;
- invalid sort field;
- invalid date range;
- invalid numeric range;
- invalid metric;
- invalid group;
- invalid pagination;
- Frappe database/query failure.

Reuse current helpers/error envelopes and follow Customer/Item/Quotation/Sales Order patterns.

---

## 19. Typed Contract Design

Create/update Sales Invoice-specific typed contracts consistent with current project style.

Likely concepts to inspect/design include equivalents of:

```text
SalesInvoiceField
SalesInvoiceSortField

SalesInvoiceGetInput
SalesInvoiceGetOutput

SalesInvoiceQueryInput
SalesInvoiceQueryOutput

SalesInvoiceAggregateMetric
SalesInvoiceAggregateGroupField
SalesInvoiceAggregateInput
SalesInvoiceAggregateOutput
```

Use actual repository naming conventions.

Do not introduce a cross-DocType public generic Pydantic model.

Do not redesign existing contracts in unrelated DocTypes.

---

## 20. Public Registration

After implementation, active Sales profile must contain:

```text
get_sales_invoice
query_sales_invoices
aggregate_sales_invoices
```

The old deterministic public:

```text
search_sales_invoices
```

must be absent from active registration/catalog if current inspection confirms it is only the old compact query tool.

Update as required:

- read wrapper exports;
- contract exports;
- contract registry;
- Sales profile;
- generated tool catalog;
- registration/profile/contract tests;
- active architecture documentation.

Historical task/report docs may retain prior names as historical evidence.

---

## 21. Sales Invoice Item Boundary

Do **not** implement:

```text
query_sales_invoice_items
aggregate_sales_invoice_items
```

in Task 33.

Do not add child rows to `query_sales_invoices`.

Do not turn `get_sales_invoice` into an unbounded full invoice + items + taxes + payments dump.

The report may recommend a future Sales Invoice Item task if inspection confirms clear business value, for example questions involving:

```text
"How many units of Item X were invoiced?"
"How much was invoiced for Item X?"
"Which invoices contain Item X?"
```

But do not implement those capabilities now.

---

## 22. Existing Sales Invoice Write Flow Must Remain Untouched

The current Sales Invoice creation flow is outside this task.

Do not change:

```text
prepare_sales_invoice
confirm_sales_invoice
```

or whatever exact current write tools/services are registered.

Do not change:

- creation validation;
- items;
- taxes;
- posting behavior;
- approval behavior;
- lifecycle tools;
- submit/cancel/delete;
- Payment Entry logic.

Read architecture and write architecture may live in separate modules.

That separation is intentional.

---

## 23. Allowed Changes

After current-tree inspection, expected allowed areas include:

```text
mcp_erpnext/contracts/selling/sales_invoice_read.py
mcp_erpnext/services/selling/sales_invoice_read.py
mcp_erpnext/tools/selling/sales_invoice_read.py

mcp_erpnext/contracts/selling/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/read.py

mcp_erpnext/tests/test_sales_invoice_read.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_contracts.py

scripts/generate_tool_catalog.py
docs/TOOLS.md
docs/architecture/*
docs/inspect/*
```

Actual files must be confirmed before editing.

Minimal updates elsewhere are allowed only if required by imports/registration.

### Shared aggregate helper

Prefer reusing:

```text
mcp_erpnext/services/common/aggregate.py
```

unchanged.

Only modify it if Sales Invoice reveals a genuinely generic missing behavior and existing Customer/Item/Quotation/Sales Order tests prove compatibility.

Do not expand the common helper merely to avoid a few Sales Invoice-local lines.

---

## 24. Areas Not to Change

Do not change:

- Customer read behavior;
- Item read behavior;
- Quotation read behavior;
- Sales Order read behavior;
- Sales Order Item query behavior;
- Quotation Item scope;
- Purchase Order read behavior;
- Customer GST / India Compliance work;
- Sales Invoice creation/confirm behavior;
- Quotation -> Sales Order conversion;
- update/submit/cancel/delete flow;
- approval architecture;
- identity/authentication;
- MCP shared secret/user-header contract;
- print/PDF/email foundation;
- LibreChat/LangGraph orchestration;
- global config architecture;
- runtime metadata auto-exposure policy.

Record unrelated findings in the report only.

---

## 25. Implementation Steps

### Step 1 — Inspect current tree

Record:

- Git root/branch;
- `git status`;
- pre-existing modifications;
- current Sales Invoice read files;
- current write files;
- current registration/contracts/tests.

Preserve unrelated changes.

### Step 2 — Trace current Sales Invoice read flow

Trace current:

```text
get_sales_invoice
search_sales_invoices
```

from:

```text
MCP wrapper
 -> contract
 -> service/common reader
 -> Frappe
 -> output
```

Document the current behavior before replacing it.

### Step 3 — Inspect mature field-aware patterns

Compare:

- Quotation Task 32;
- Sales Order;
- Customer;
- Item.

Reuse current project conventions.

### Step 4 — Inspect Sales Invoice source/runtime metadata

Inspect installed:

```text
sales_invoice.json
sales_invoice.py
frappe.get_meta("Sales Invoice")
```

where possible.

Confirm field names/types and accounting semantics.

### Step 5 — Freeze Sales Invoice public policy

Define Sales Invoice-local:

- output field allowlist;
- exact-read defaults;
- query defaults;
- filters;
- sort fields;
- aggregate metrics;
- group fields;
- currency behavior;
- return/credit-note behavior.

### Step 6 — Implement `get_sales_invoice`

Upgrade exact read to controlled field-aware projection.

### Step 7 — Implement `query_sales_invoices`

Replace old deterministic `search_sales_invoices`.

Implement controlled filters/projection/sort/pagination.

### Step 8 — Implement `aggregate_sales_invoices`

Reuse Task 31 shared aggregate foundation.

Implement safe invoice-value and outstanding analytics.

### Step 9 — Update registry/profile/contracts

Ensure active public surface contains exactly the intended names.

### Step 10 — Update generated catalog/docs

Regenerate catalog using current project generator.

Update only active architecture docs that need the new capability/name.

### Step 11 — Focused tests

Run Sales Invoice read + registration/profile/contracts.

### Step 12 — Full regression suite

Run all `mcp_erpnext/tests`.

### Step 13 — Static quality checks

Run:

- catalog `--check`;
- `git diff --check`;
- targeted compile check if established by prior tasks.

### Step 14 — Live read-only verification

Attempt on a usable site with `mcp_erpnext` installed.

Do not restart services or mutate database/server state unless separately authorized.

---

## 26. Required Tests

At minimum cover the following.

### `get_sales_invoice`

- default projection;
- selected field projection;
- unsupported field rejection;
- exact document retrieval;
- missing document;
- permission denial/read check;
- return-related fields if exposed.

### `query_sales_invoices`

- default projection;
- custom projection;
- customer filter;
- status filter;
- docstatus filter;
- company filter;
- currency filter;
- `is_return` filter if exposed;
- posting-date range;
- due-date range;
- grand-total range if exposed;
- outstanding-amount range;
- deterministic sort;
- limit;
- offset;
- invalid field;
- invalid sort;
- invalid range;
- permission-aware `get_list`.

### `aggregate_sales_invoices`

- count;
- `sum_grand_total`;
- `avg_grand_total`;
- `min_grand_total`;
- `max_grand_total`;
- `sum_outstanding_amount`;
- one other approved numeric metric if included;
- customer grouping;
- status grouping;
- currency grouping;
- `is_return` grouping/filter if included;
- shared filters;
- invalid metric;
- invalid group;
- monetary automatic currency context;
- permission-aware shared aggregate executor.

### Returns/Credit Notes

Where supported by the selected public policy, test that:

- normal invoices can be separated from returns;
- return amounts are not silently sign-flipped;
- filters preserve stored ERPNext meaning.

### Naming/registration

Assert active Sales profile contains:

```text
get_sales_invoice
query_sales_invoices
aggregate_sales_invoices
```

Assert old active:

```text
search_sales_invoices
```

is absent.

### Regression

All existing:

- Customer;
- Item;
- Quotation;
- Sales Order;
- creation;
- conversion;
- lifecycle;
- India Compliance

tests remain green.

---

## 27. Verification Commands

Use the actual current environment paths found during implementation.

Focused command should cover at least:

```text
test_sales_invoice_read
test_tool_registration
test_profiles
test_tool_contracts
```

Then run full suite equivalent to:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
```

Run catalog checks equivalent to:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
```

Run:

```bash
git diff --check
```

Use current-tree paths, not blindly copied paths if the environment differs.

---

## 28. Live Read-Only Verification

If a usable site with `mcp_erpnext` installed is available, verify safe examples equivalent to:

```text
get_sales_invoice(<existing invoice>)
```

```text
query_sales_invoices(limit=1)
```

```text
aggregate_sales_invoices(metrics=["count"])
```

If appropriate test data exists:

```text
aggregate_sales_invoices(
    metrics=["sum_outstanding_amount"],
    customer=<existing customer>
)
```

Also verify:

- one monetary aggregate with currency context;
- one grouped aggregate;
- one return/normal filter if return data exists.

If live MCP transport is unavailable but a site context is available, service-level verification is acceptable.

Clearly distinguish:

```text
unit/mock verification
in-process registration verification
site/database verification
live MCP transport verification
```

Do not claim one as another.

---

## 29. Acceptance Criteria

Task 33 is complete only when all of the following are true.

### Public surface

Active Sales Invoice read tools are:

```text
get_sales_invoice
query_sales_invoices
aggregate_sales_invoices
```

Old deterministic:

```text
search_sales_invoices
```

is absent from active registration/catalog.

### Field-aware read

- exact read uses controlled projection;
- query uses controlled projection;
- default projections are bounded;
- arbitrary fields are rejected;
- filters are deliberate and metadata-backed;
- sorting/pagination are deterministic.

### Accounting usefulness

The capability can safely answer:

```text
invoice value questions
unpaid/outstanding questions
due/overdue filtering questions
customer invoice count questions
status/customer/company grouped questions
```

without adding separate one-off public tools.

### Aggregate architecture

- shared Task 31 aggregate foundation is reused;
- no duplicate generic aggregate engine is created;
- Frappe v16 aggregate dictionaries remain used;
- no unsupported raw SQL-style aggregate field strings are introduced.

### Currency correctness

Transaction-currency monetary totals preserve currency context.

No cross-currency unlabeled monetary total is returned.

### Return correctness

Returns/credit notes are not silently hidden or sign-rewritten.

Their semantics are explicitly filterable/groupable where included in public policy.

### Permissions

- exact read checks read permission;
- query is permission-aware;
- aggregate is permission-aware;
- no permission bypass is introduced.

### Scope

- no Sales Invoice Item query tool;
- no write-flow changes;
- no generic public document tool;
- no config/contract consolidation;
- no runtime metadata auto-exposure.

### Verification

- focused tests pass;
- full suite passes;
- catalog check passes;
- `git diff --check` passes;
- live verification performed where environment allows, otherwise limitation is explicit.

---

## 30. Expected Final Sales Read Surface

After Task 33, the mature Sales-profile header read capabilities should conceptually be:

```text
Customer
  get_customer
  query_customers
  aggregate_customers

Item
  get_item
  query_items
  aggregate_items

Quotation
  get_quotation
  query_quotations
  aggregate_quotations

Sales Order
  get_sales_order
  query_sales_orders
  aggregate_sales_orders
  query_sales_order_items

Sales Invoice
  get_sales_invoice
  query_sales_invoices
  aggregate_sales_invoices
```

Resolver/discovery tools such as:

```text
search_customers
search_items
```

remain separately named because they serve candidate resolution rather than deterministic field-aware listing.

---

## 31. Known Limitations / Boundaries

This task intentionally does not:

- implement `query_sales_invoice_items`;
- implement Sales Invoice item-level analytics;
- implement Payment Entry read/query tools;
- implement Accounts Receivable report replication;
- implement ageing buckets;
- implement payment reconciliation;
- calculate outstanding from raw ledger entries itself;
- change ERPNext's stored Sales Invoice outstanding logic;
- implement Purchase Order aggregate capability;
- implement Purchase Invoice reads;
- change Sales Invoice creation/write/lifecycle flows;
- change approvals;
- change identity/security;
- redesign the common aggregate foundation.

For v1 Sales Invoice read capability, prefer reading ERPNext's established document/accounting state rather than rebuilding Accounts Receivable logic inside MCP.

---

## 32. Implementation Report Required

Create an implementation report under the existing repository inspect/report convention.

It must include:

1. files inspected;
2. pre-existing working-tree changes;
3. Sales Invoice read architecture before Task 33;
4. separation from existing Sales Invoice create/write service;
5. Frappe version;
6. ERPNext version;
7. runtime metadata result or exact failure;
8. installed source/JSON fallback inspected;
9. selected public output fields and rationale;
10. intentionally excluded meaningful fields;
11. exact-read default projection;
12. query default projection;
13. selected query filters;
14. selected sort fields;
15. selected aggregate metrics;
16. selected aggregate group fields;
17. outstanding-amount semantics;
18. decision on whether `paid_amount` is exposed/aggregated and why;
19. return/credit-note policy;
20. currency policy;
21. exact files changed;
22. `get_sales_invoice` implementation summary;
23. `query_sales_invoices` implementation summary;
24. `aggregate_sales_invoices` implementation summary;
25. confirmation Task 31 aggregate helper was reused;
26. confirmation old active `search_sales_invoices` was removed;
27. confirmation no Sales Invoice Item tool was added;
28. permission behavior;
29. focused tests and results;
30. full suite result;
31. catalog/diff/compile checks;
32. live site/service/MCP verification or exact limitation;
33. unrelated findings/recommendations;
34. exact next task recommendation.

---

## 33. Exact Next Task

After Task 33 is complete and verified, do **not** automatically implement the next DocType merely for symmetry.

First inspect the remaining Sales-profile read gaps and business value.

The likely next decision task is:

# TASK 34 — Sales Read Capability Gap Review / Next DocType Selection

That review should compare at least:

```text
Sales Invoice Item
Purchase Order read/aggregate status
other current Sales-profile exposed transaction reads
```

and decide the next implementation based on actual user/business questions and tool-surface value.

If the project direction is already explicitly to bring Purchase Order to the same field-aware architecture, then Task 34 may instead become:

```text
Purchase Order Field-Aware Read / Query / Aggregate Capability
```

but do not implement it as part of Task 33.
