# TASK 32 — Quotation Field-Aware Read / Query / Aggregate Capability

## Status

Ready for implementation after:

- Task 30 — Sales Order Field-Aware Query Naming Normalization
- Task 31 — Shared Internal Aggregate Foundation

Task 31 has already created the shared internal aggregate foundation in:

```text
mcp_erpnext/services/common/aggregate.py
```

This task must reuse that foundation rather than recreating aggregate mechanics.

---

## 1. Scope

Upgrade the existing Quotation read capability from the current compact/common-reader implementation to the same explicit field-aware read architecture already established for Customer, Item, and Sales Order.

The final public Quotation read surface for this task must be:

```text
get_quotation
query_quotations
aggregate_quotations
```

This task includes:

- preserving and upgrading `get_quotation` as the exact single-document read tool,
- replacing the current deterministic multi-record `search_quotations` public capability with `query_quotations`,
- implementing `aggregate_quotations`,
- adding DocType-specific field/filter/sort/group/metric policy,
- reusing the shared internal aggregate foundation from Task 31,
- updating contracts, registry, profile registration, catalog/docs, and tests required by these public changes.

This task does **not** add `query_quotation_items`.

Quotation Item analytics/read capability must be evaluated in a separate later task.

---

## 2. Objective

Make Quotation a first-class field-aware read capability with the same mental model as the existing mature read tools:

```text
get_quotation
    = exact known Quotation

query_quotations
    = deterministic filtered/sorted/paginated multi-record retrieval

aggregate_quotations
    = server-side count/sum/avg/min/max/grouping analytics
```

The implementation must remain:

- explicit at the public MCP layer,
- reusable internally,
- permission-aware,
- configuration/allowlist controlled,
- runtime-metadata validated,
- conservative about exposed fields,
- compatible with Frappe/ERPNext v16 behavior.

---

## 3. Frozen Naming Convention

The public naming convention is now:

```text
search_*     = discovery/resolution candidate search
get_*        = exact single-document read
query_*      = deterministic field-aware multi-record retrieval
aggregate_*  = server-side analytics
```

Therefore the existing Quotation multi-record read name:

```text
search_quotations
```

must become:

```text
query_quotations
```

Do not keep a public compatibility alias unless inspection finds a repository-external hard requirement that cannot be safely removed.

Repository-local historical task/report documentation may retain the old name as historical evidence.

Do not rename resolver/discovery tools such as `search_customers` or `search_items`.

---

## 4. Architecture Decisions to Preserve

### Public tools stay DocType-specific

Do not create:

```text
get_document
query_documents
aggregate_documents
```

or any public generic DocType parameter.

The public tools must remain:

```text
get_quotation
query_quotations
aggregate_quotations
```

### Genericity remains internal

Reuse:

```text
mcp_erpnext/services/common/aggregate.py
```

for common aggregate mechanics.

Reuse other existing common read/filter helpers only when they fit cleanly.

### Do not redesign config/contract structure

Do not centralize every field/filter/sort/metric into one global config file.

DocType-specific policy may remain in Quotation-specific contract/service constants.

Do not merge contract literals and service constants.

Do not introduce automatic contract/service synchronization or invariant-generation infrastructure in this task.

### Do not auto-expose runtime metadata

Runtime metadata is evidence/validation, not the public schema.

A new custom/ERPNext field appearing in metadata must not automatically become available through MCP.

Public fields must remain deliberately allowlisted.

---

## 5. Mandatory Inspection Before Editing

Before implementation, inspect the current working tree and trace the existing Quotation read capability end-to-end.

At minimum inspect:

```text
mcp_erpnext/services/common/read.py
mcp_erpnext/services/selling/quotation.py
mcp_erpnext/services/selling/
mcp_erpnext/contracts/selling/
mcp_erpnext/tools/selling/
mcp_erpnext/contracts/registry.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tests/
scripts/generate_tool_catalog.py
docs/TOOLS.md
docs/architecture/
```

Confirm actual paths and function/class names before editing.

Specifically identify:

1. current `get_quotation`,
2. current `search_quotations`,
3. whether both are wrappers over the compact common reader,
4. their current public input/output contracts,
5. current default output fields,
6. how permissions are applied,
7. current registry/profile registration,
8. tests that lock the current behavior,
9. any repository-local consumer of `search_quotations`.

Also inspect the existing mature implementations:

```text
Customer:
  get_customer
  query_customers
  aggregate_customers

Item:
  get_item
  query_items
  aggregate_items

Sales Order:
  get_sales_order
  query_sales_orders
  aggregate_sales_orders
  query_sales_order_items
```

Reuse the established strategy where it is sound.

Do not invent a different Quotation architecture unless the existing patterns genuinely do not fit.

---

## 6. Mandatory ERPNext / Runtime Metadata Inspection

Before freezing Quotation field/filter/sort/group/metric allowlists, inspect the actual Quotation DocType metadata available in the target Frappe/ERPNext environment.

Also inspect the official ERPNext Quotation DocType/controller source available in the bench checkout or official repository context.

The implementation report must state:

- the ERPNext/Frappe version inspected,
- whether live/runtime metadata was available,
- relevant actual fieldnames discovered,
- which fields were selected for public exposure,
- which meaningful fields were intentionally not exposed.

Do not guess fieldnames.

If runtime metadata is unavailable, use the installed ERPNext source/JSON as the fallback and explicitly record the limitation.

---

## 7. Field-Aware Capability Policy

Create a controlled Quotation read policy analogous to Customer/Item/Sales Order.

The exact field list must be decided only after inspection.

The allowlist should normally cover useful header-level business fields in categories such as:

### Identity

- document name
- quotation party type / party identity
- customer/lead-related display identity where actually present

### Dates

- transaction date
- validity date
- creation / modified timestamps only if the established read pattern exposes them and they are useful

### Status / lifecycle

- docstatus
- status
- order/quotation type where relevant

### Commercial totals

- currency
- conversion rate if useful
- total quantity
- net total
- grand total
- base totals only if justified

### Commercial context

- selling price list
- territory
- company
- sales partner / campaign / source fields only if confirmed useful and actually present

Do not expose every Quotation field.

Avoid large text, internal implementation fields, hidden/system-only values, or low-value data unless there is a concrete read use case.

---

## 8. Default Projection

`get_quotation` and `query_quotations` must not dump the full ERPNext Quotation document by default.

Define a useful bounded default projection through Quotation-specific constants/contracts consistent with existing field-aware tools.

The exact defaults must be derived from current project patterns and Quotation metadata.

### Important compatibility rule

Inspect the current compact `get_quotation` / `search_quotations` default output.

Where reasonable, the new default field-aware projection should preserve the useful fields users already received so the upgrade does not unnecessarily reduce information.

However, do not preserve obsolete naming or weak architecture merely for compatibility.

---

## 9. `get_quotation`

`get_quotation` remains the exact-document read tool.

Target conceptual behavior:

```text
get_quotation(
    quotation=<exact Quotation name>,
    fields=[optional allowed field projection]
)
```

Requirements:

- exact known Quotation identifier,
- permission-aware retrieval,
- optional controlled field projection,
- bounded default projection when `fields` is omitted,
- reject unsupported fields through typed/public validation,
- do not return arbitrary full document JSON,
- clear not-found / permission-safe behavior consistent with current MCP error architecture.

Do not create a second exact-read tool.

---

## 10. `query_quotations`

Replace the deterministic multi-record `search_quotations` public surface with:

```text
query_quotations
```

This should be the main field-aware Quotation list/query tool.

It should support only intentionally selected, useful filters confirmed against metadata.

Potential categories to evaluate include:

- exact/partial party filters where appropriate,
- customer/party identity,
- status,
- docstatus,
- company,
- currency,
- quotation/order type,
- transaction date range,
- valid-till date range,
- minimum/maximum grand total,
- minimum/maximum net total,
- minimum/maximum total quantity,
- selected commercial dimensions where useful.

Do not blindly implement every possible filter.

### Query capabilities

The mature query should support, where consistent with existing read architecture:

- controlled field projection,
- deterministic sorting,
- sort direction,
- limit,
- offset,
- filters,
- date ranges,
- numeric ranges.

The response `count` must retain the project convention for query tools:

```text
count = number of rows returned in this page/result
```

It must **not** pretend to be a database-wide aggregate count.

For database-wide counts, use `aggregate_quotations`.

---

## 11. `aggregate_quotations`

Add the explicit public tool:

```text
aggregate_quotations
```

Reuse Task 31's shared internal aggregate foundation.

Do not duplicate generic COUNT/SUM/AVG/MIN/MAX mechanics.

### Metrics

After metadata/business-field inspection, define a deliberate Quotation metric allowlist.

Expected categories to evaluate:

```text
count
sum_grand_total
avg_grand_total
min_grand_total
max_grand_total
```

Potentially other numeric Quotation header metrics may be allowed only if they provide clear business value and match established patterns.

Do not add metrics merely because a field is numeric.

### Grouping

Evaluate useful Quotation grouping fields such as:

- status,
- customer/party,
- company,
- currency,
- quotation/order type,
- other stable header dimensions actually present and useful.

Group fields must be explicit and allowlisted.

Do not allow arbitrary field names.

### Currency correctness

Do not produce misleading cross-currency monetary aggregates.

Inspect the existing Sales Order currency policy and apply the same sound principle to Quotation.

If monetary metrics are requested:

- preserve currency context,
- group/include currency as required by the established project behavior,
- do not sum heterogeneous currencies into one unlabeled amount.

Document the chosen behavior and test it.

---

## 12. Filters Must Be Shared Semantically Across Query and Aggregate

Where a filter logically applies to both:

```text
query_quotations
aggregate_quotations
```

they should have consistent meaning.

Examples:

- customer/party,
- status,
- company,
- transaction date range,
- validity date range,
- amount ranges where meaningful.

Do not create two inconsistent filter implementations for the same concept.

Internal helper reuse is encouraged only when it keeps the code clear and does not weaken DocType policy.

---

## 13. Permission Requirements

All Quotation read/query/aggregate operations must remain permission-aware.

Use the same user context established by MCP identity handling.

Do not bypass normal Frappe permissions through:

```text
frappe.get_all
ignore_permissions=True
```

or direct SQL that skips permission handling.

If Query Builder is required for a special expression, explicitly ensure the surrounding authorization/permission behavior remains equivalent to the existing project policy.

The implementation report must state how permissions are preserved.

---

## 14. Error Handling

Preserve the current MCP error envelope and error-handling architecture.

Do not introduce a new error framework.

Errors should remain clear for cases such as:

- invalid Quotation name,
- unsupported field,
- invalid filter value,
- invalid metric,
- invalid group field,
- invalid sort field,
- invalid limit/offset,
- invalid numeric/date range,
- permission denial,
- Frappe query failure.

Reuse existing error helpers and codes/patterns where applicable.

---

## 15. Contract Design

Create/update Quotation-specific typed contracts consistent with the project's current approach.

Likely concepts include equivalents of:

```text
QuotationField
QuotationSortField
QuotationQueryInput
QuotationQueryOutput
QuotationAggregateMetric
QuotationAggregateGroupField
QuotationAggregateInput
QuotationAggregateOutput
```

Names must follow the actual repository convention after inspection.

Do not copy types mechanically if a smaller contract is more appropriate.

Do not introduce one generic cross-DocType public Pydantic contract.

---

## 16. Public Tool Registration

After implementation, the Sales profile should expose:

```text
get_quotation
query_quotations
aggregate_quotations
```

and should no longer expose:

```text
search_quotations
```

if repository inspection confirms that `search_quotations` is the existing deterministic Quotation read and not a separate resolver/discovery tool.

Update:

- wrapper/tool registration,
- contract registry,
- Sales profile,
- exports/imports,
- generated tool catalog,
- active architecture docs,
- tests.

Historical task/report documents should not be rewritten simply to erase historical names.

---

## 17. Quotation Item Boundary

Do **not** implement:

```text
query_quotation_items
aggregate_quotation_items
```

in Task 32.

This task is for Quotation header-level field-aware capability.

The implementation report may record whether a future Quotation Item capability would be useful, but it must not implement it.

Do not force child-table retrieval into `query_quotations`.

---

## 18. Allowed Changes

After inspection, expected allowed areas include:

```text
mcp_erpnext/contracts/selling/*
mcp_erpnext/services/selling/*
mcp_erpnext/tools/selling/*
mcp_erpnext/contracts/registry.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tests/*
scripts/generate_tool_catalog.py
docs/TOOLS.md
docs/architecture/*
docs/inspect/*
```

Reuse:

```text
mcp_erpnext/services/common/aggregate.py
```

Minimal changes to shared helpers are allowed only if Quotation exposes a genuinely reusable missing mechanic and all existing aggregate behavior remains compatible.

Do not enlarge shared helpers merely to make Quotation code shorter.

---

## 19. Areas Not to Change

Do not change:

- Customer field-aware behavior,
- Item field-aware behavior,
- Sales Order public contracts/behavior,
- `query_sales_order_items`,
- shared aggregate semantics already established by Task 31,
- Sales Invoice implementation,
- Purchase Order implementation,
- Customer GST / India Compliance work,
- write/create/update/submit/cancel/delete flows,
- approval architecture,
- MCP identity/authentication,
- shared secret/header behavior,
- PDF/print/email features,
- LibreChat/LangGraph orchestration,
- global config architecture.

Do not implement unrelated cleanup discovered during inspection.

Record it in the report only.

---

## 20. Implementation Steps

### Step 1 — Inspect current tree

Record:

- `git status`,
- pre-existing modifications,
- current Quotation files/contracts/tools/tests,
- current public tool names,
- current compact-reader behavior.

Preserve unrelated changes.

### Step 2 — Trace existing Quotation read flow

Trace:

```text
public MCP wrapper
  -> contract
  -> service
  -> common reader / Frappe
  -> response
```

for both current exact and multi-record reads.

### Step 3 — Inspect mature field-aware patterns

Compare Customer, Item, and Sales Order.

Choose the closest sound pattern for Quotation.

### Step 4 — Inspect Quotation metadata/source

Confirm actual fields and types.

Do not code allowlists before this inspection.

### Step 5 — Define Quotation field policy

Define:

- allowed output fields,
- default fields,
- filterable fields,
- sortable fields,
- aggregate metrics,
- group fields.

Keep these Quotation-specific.

### Step 6 — Upgrade `get_quotation`

Implement field-aware exact retrieval with optional projection and safe defaults.

### Step 7 — Implement `query_quotations`

Rename/replace the current deterministic `search_quotations` public capability.

Add field-aware filtering/projection/sorting/pagination.

### Step 8 — Implement `aggregate_quotations`

Reuse `services/common/aggregate.py`.

Keep Quotation-specific metrics, filters, group rules, and currency policy local.

### Step 9 — Update public registration/contracts

Update:

- wrappers,
- registry,
- Sales profile,
- exports/imports,
- typed schemas.

Ensure old active `search_quotations` public registration is absent.

### Step 10 — Update generated catalog/docs

Run the existing tool catalog generator.

Update active architecture docs where naming/capability inventory is documented.

Do not rewrite historical reports.

### Step 11 — Add focused tests

Cover get/query/aggregate behavior and naming normalization.

### Step 12 — Run full tests

Run the full `mcp_erpnext/tests` suite.

### Step 13 — Live verification

If a valid site with `mcp_erpnext` installed is available, perform safe read-only verification.

Do not restart services or alter server/database state unless explicitly authorized.

---

## 21. Required Tests

At minimum cover:

### `get_quotation`

- default projection,
- requested valid field projection,
- unsupported field rejection,
- known document,
- missing document,
- permission-aware read seam.

### `query_quotations`

- default projection,
- custom projection,
- status filter,
- party/customer filter where supported,
- date range,
- numeric amount range where supported,
- deterministic sorting,
- limit,
- offset,
- invalid sort field,
- invalid requested field,
- invalid range validation,
- permission-aware `frappe.get_list` behavior.

### `aggregate_quotations`

- count,
- sum grand total,
- avg grand total,
- min grand total,
- max grand total,
- supported grouping,
- filters shared with query,
- invalid metric,
- invalid group,
- monetary currency behavior,
- permission-aware execution,
- use of shared Task 31 aggregate helper.

### Naming/registration

Assert:

```text
get_quotation
query_quotations
aggregate_quotations
```

are registered in the Sales profile.

Assert old active public:

```text
search_quotations
```

is absent.

### Regression

Existing Customer, Item, Sales Order, creation, conversion, and lifecycle tests must remain green.

---

## 22. Suggested Verification Commands

Use the repository's actual environment/path discovered during inspection.

Focused tests should include the new/updated Quotation tests plus registration/contract/profile tests.

Then run:

```bash
python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
```

using the bench Python environment as appropriate.

Also run:

```bash
git diff --check
```

and the existing targeted compile/catalog checks used by prior tasks.

Run:

```bash
python scripts/generate_tool_catalog.py
python scripts/generate_tool_catalog.py --check
```

from the correct app root if those remain the current commands.

Do not blindly copy paths from prior reports if the current environment differs.

---

## 23. Live Read-Only Verification

If an installed usable site is available, verify examples equivalent to:

```text
get_quotation(<existing quotation>)
```

```text
query_quotations(limit=1)
```

```text
aggregate_quotations(metrics=["count"])
```

and, if test data permits:

```text
aggregate_quotations(
    metrics=["sum_grand_total"],
    <safe filter>
)
```

plus one grouped aggregate.

If live MCP transport is not running, service-level site-context verification is acceptable and must be labeled accurately.

If no usable site exists, record that live verification was not possible.

Do not present mocks as live verification.

---

## 24. Acceptance Criteria

Task 32 is complete only when:

### Public surface

The active Quotation read tools are:

```text
get_quotation
query_quotations
aggregate_quotations
```

The old deterministic public name:

```text
search_quotations
```

is absent from active registration/catalog.

### Field-aware behavior

- exact Quotation read supports controlled projection,
- multi-record query supports controlled projection,
- useful DocType-specific filters exist,
- sorting/pagination are deterministic,
- arbitrary fields are rejected,
- default output remains bounded.

### Aggregate behavior

- `aggregate_quotations` exists,
- it reuses Task 31 shared aggregate mechanics,
- count/sum/avg/min/max work for the approved metric set,
- grouping works for approved group fields,
- currency semantics are safe,
- no raw SQL-style aggregate strings are introduced.

### Architecture

- public Quotation tools remain explicit,
- no public generic DocType tool is introduced,
- Quotation policy remains local,
- runtime metadata is not auto-exposed,
- contract/config architecture is not redesigned,
- no Quotation Item tool is added.

### Permissions

- read/query/aggregate remain permission-aware,
- no `ignore_permissions=True` / `get_all` shortcut is introduced.

### Quality

- focused tests pass,
- full suite passes,
- catalog check passes,
- `git diff --check` passes,
- unrelated behavior remains unchanged.

---

## 25. Expected Result

After Task 32, the Sales read architecture should conceptually include:

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

Quotation should now answer:

```text
"Give me QTN-X details"
    -> get_quotation

"Show last 10 quotations for customer X"
    -> query_quotations

"How many quotations does customer X have?"
    -> aggregate_quotations

"What is this month's total quoted value?"
    -> aggregate_quotations

"Count quotations status-wise"
    -> aggregate_quotations
```

without dumping unnecessary source rows for pure aggregate questions.

---

## 26. Known Limitations / Boundaries

Task 32 intentionally does not:

- implement Quotation Item query/analytics,
- implement Sales Invoice field-aware capabilities,
- implement Purchase Order aggregates,
- change write/create/update/lifecycle flows,
- change conversion from Quotation to Sales Order,
- change approval behavior,
- add arbitrary metadata-driven fields,
- redesign all read contracts,
- consolidate all field constants,
- introduce a generic public query/aggregate engine.

---

## 27. Implementation Report Required

Create a report under the repository's existing inspect/report convention.

It must include:

1. files inspected,
2. pre-existing working-tree changes,
3. current Quotation read architecture before changes,
4. ERPNext/Frappe version inspected,
5. metadata/source inspection result,
6. selected public output fields and rationale,
7. selected default projection,
8. selected query filters,
9. selected sort fields,
10. selected aggregate metrics,
11. selected group fields,
12. currency aggregate policy,
13. exact files changed,
14. `get_quotation` implementation summary,
15. `query_quotations` implementation summary,
16. `aggregate_quotations` implementation summary,
17. confirmation that shared Task 31 aggregate foundation was reused,
18. confirmation that `search_quotations` is no longer active,
19. confirmation that no `query_quotation_items` was added,
20. permission behavior,
21. focused test commands/results,
22. full suite result,
23. catalog/diff/compile verification,
24. live verification or exact reason it was unavailable,
25. limitations,
26. exact recommendation for the next task.

---

## 28. Exact Next Task

After Task 32 is implemented and verified, the next task is:

# TASK 33 — Sales Invoice Field-Aware Read / Query / Aggregate Capability

Task 33 should inspect the current Sales Invoice compact reader, ERPNext Sales Invoice metadata/source, accounting-relevant field semantics, currency/outstanding amount behavior, and existing field-aware patterns before implementing:

```text
get_sales_invoice
query_sales_invoices
aggregate_sales_invoices
```

It must reuse the Task 31 shared aggregate foundation and preserve the same explicit-public / generic-internal architecture.

Do not start Task 33 as part of Task 32.
