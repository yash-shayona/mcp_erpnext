# TASK 31 — Shared Internal Aggregate Foundation

## Status

Ready for implementation after completion of Task 30 — Sales Order Field-Aware Query Naming Normalization.

Task 30 has already normalized the Sales Order field-aware multi-record read tool to:

- `get_sales_order`
- `query_sales_orders`
- `aggregate_sales_orders`
- `query_sales_order_items`

This task must not revisit that naming work.

---

## 1. Scope

Refactor the existing aggregate implementations in `mcp_erpnext` so that reusable aggregate mechanics are centralized in a shared internal foundation.

The current public aggregate tools must remain explicit and DocType-specific:

- `aggregate_customers`
- `aggregate_items`
- `aggregate_sales_orders`

This task is an **internal reuse/refactor task only**.

Do **not** add any new public aggregate tools for Quotation, Sales Invoice, Purchase Order, Employee, or any other DocType in this task.

Do **not** introduce a public generic tool such as:

- `aggregate_documents`
- `aggregate_doctype`
- `query_documents`

Genericity must remain internal.

---

## 2. Objective

Create a reusable internal aggregate execution/building foundation that removes duplicated mechanics across the currently implemented aggregate services while preserving every existing public tool contract and response shape.

The foundation should centralize only mechanics that are truly common, such as:

- building Frappe v16-compatible aggregate field expressions,
- standard aggregate metric mapping,
- group-by field construction where applicable,
- permission-aware aggregate execution,
- common result shaping helpers where the shapes are genuinely identical,
- common validation helpers only where existing implementations already share the same behavior.

DocType-specific business policy must remain outside the generic engine.

---

## 3. Confirmed Architecture Decisions

The following decisions are frozen for this task.

### Public naming convention

For field-aware document reads:

- `get_*` = exact single-document read
- `query_*` = deterministic field-aware multi-record retrieval
- `aggregate_*` = server-side analytics such as count/sum/avg/min/max/grouping
- `search_*` = discovery/resolution candidate search where that meaning already exists

Do not rename any additional tools in this task.

### Public tools remain explicit

Keep:

- `aggregate_customers`
- `aggregate_items`
- `aggregate_sales_orders`

Do not replace them with one generic MCP tool.

### Internal genericity is allowed and desired

A shared internal module/helper is appropriate.

Example conceptual location:

```text
mcp_erpnext/services/common/aggregate.py
```

The exact filename/module split may differ if inspection shows a better fit with the current repository structure.

Before adding a new file, inspect the existing `services/common/` architecture and reuse an existing appropriate helper location if one already exists.

### Configuration/constant structure stays as-is

Do not centralize all read/aggregate policy into one global config.

Existing DocType-specific constants may remain where they currently live, including patterns such as:

- `_FIELDS`
- `_HEADER_FIELDS`
- `_ITEM_FIELDS`
- `_METRICS`
- `_HEADER_METRICS`
- `_ITEM_METRICS`
- allowed group fields
- default field projections

This task is not a configuration redesign.

### Contract/service separation stays as-is

Do not merge contract literals and service constants.

Do not introduce contract/service synchronization refactors or invariant generators in this task.

That is explicitly out of scope.

---

## 4. Inputs / Existing Implementation to Inspect First

Before changing code, inspect the current working tree and trace the complete aggregate flow for at least:

### Customer

Likely relevant areas:

```text
mcp_erpnext/services/masters/customer_read.py
mcp_erpnext/contracts/masters/customer_read.py
mcp_erpnext/tools/masters/customer_read.py
```

Confirm actual current paths before editing.

Inspect:

- aggregate metric constants
- filter construction
- group-by handling
- aggregate field construction
- `frappe.get_list` / database execution
- result shape
- permission behavior

### Item

Likely relevant areas:

```text
mcp_erpnext/services/masters/item_read.py
mcp_erpnext/contracts/masters/item_read.py
mcp_erpnext/tools/masters/item_read.py
```

Inspect the same flow.

### Sales Order

Likely relevant areas:

```text
mcp_erpnext/services/selling/sales_order_read.py
mcp_erpnext/contracts/selling/sales_order_read.py
mcp_erpnext/tools/selling/sales_order_read.py
```

Inspect:

- header aggregate mechanics
- Sales Order Item aggregate mechanics
- distinct-order counting
- currency/amount behavior
- child-table filters
- normal aggregate expressions
- Query Builder expressions used for special cases

### Common read helpers

Inspect:

```text
mcp_erpnext/services/common/
```

especially any existing read/filter/field helpers.

Do not create duplicate infrastructure if current shared helpers already solve part of the problem.

---

## 5. Frappe v16 Aggregate Requirement

Preserve the already-correct Frappe v16 aggregate representation.

Do not reintroduce raw SQL-style strings such as:

```python
"count(name) as count"
"sum(grand_total) as total"
```

Ordinary aggregate fields should continue to use the Frappe-supported dictionary representation where the current implementation uses it, for example conceptually:

```python
{"COUNT": "*", "as": "count"}
{"SUM": "grand_total", "as": "sum_grand_total"}
{"AVG": "grand_total", "as": "avg_grand_total"}
{"MIN": "grand_total", "as": "min_grand_total"}
{"MAX": "grand_total", "as": "max_grand_total"}
```

Do not assume exact field names or aliases; preserve the current contracts.

Special expressions that require typed Query Builder behavior, such as distinct counting, must remain typed Query Builder expressions.

For example, existing behavior equivalent to:

```python
Count(field).distinct()
```

must not be forced into a generic dictionary abstraction if doing so changes semantics or support.

---

## 6. Permission Requirement

Existing permission-aware behavior must be preserved.

Where the current implementation uses:

```python
frappe.get_list(..., ignore_permissions=False)
```

or another permission-aware path, retain that behavior.

Do not replace permission-aware reads with `frappe.get_all` or another bypass path.

The MCP identity/user context must continue to affect aggregate visibility exactly as it does before this task.

---

## 7. What Should Become Shared

After inspection, centralize only stable/common mechanics.

A possible internal API may conceptually include helpers such as:

```python
build_aggregate_fields(...)
execute_aggregate(...)
normalize_aggregate_rows(...)
```

These names are examples only.

The implementation agent should choose names consistent with the repository style.

Potential shared responsibilities:

1. Convert allowed requested metrics into Frappe v16 aggregate field dictionaries.
2. Map common aggregate operations:
   - COUNT
   - SUM
   - AVG
   - MIN
   - MAX
3. Construct group-by values from already validated DocType-specific group fields.
4. Execute permission-aware `frappe.get_list` aggregates.
5. Normalize the no-group single-row aggregate response only if Customer/Item/Sales Order currently use compatible semantics.
6. Normalize grouped aggregate rows only if existing output contracts can remain byte-for-byte / structurally compatible.

---

## 8. What Must Remain DocType-Specific

Keep the following in the DocType-specific service/contract unless inspection proves they are genuinely generic without weakening policy:

- allowed fields,
- allowed filters,
- filter-to-field mappings,
- numeric range filters,
- allowed group-by fields,
- allowed metrics,
- default metrics,
- metric aliases,
- currency semantics,
- Sales Order-specific child row behavior,
- Sales Order Item-specific metrics,
- distinct Sales Order counting,
- business validation messages,
- public input models,
- public output models,
- error codes/contracts.

Do not pass arbitrary DocTypes, fields, metrics, or group-by values into the shared engine from MCP input.

The DocType-specific layer must validate and control what reaches the shared internal helper.

---

## 9. Sales Order Item Boundary

`query_sales_order_items` currently supports row retrieval plus optional metrics.

Do not redesign that public tool in this task.

Inspect its internal aggregate implementation.

If ordinary Sales Order Item aggregate mechanics can safely reuse the shared helper without changing behavior, reuse it.

However:

- do not split the public tool,
- do not change its request schema,
- do not change its response schema,
- do not remove typed Query Builder distinct counting,
- do not force special child-table logic into the generic engine.

If reuse would make the shared abstraction awkward or change semantics, leave the special Sales Order Item path local.

The goal is good internal reuse, not maximum abstraction.

---

## 10. Allowed Changes

The agent may change only files required for this internal refactor, including as necessary:

```text
mcp_erpnext/services/common/*
mcp_erpnext/services/masters/customer_read.py
mcp_erpnext/services/masters/item_read.py
mcp_erpnext/services/selling/sales_order_read.py
mcp_erpnext/tests/test_customer_read.py
mcp_erpnext/tests/test_item_read.py
mcp_erpnext/tests/test_sales_order_read.py
```

Actual test filenames must be confirmed from the repository before editing.

A new focused common aggregate test module may be added if useful.

Minimal import changes elsewhere are allowed only when required by the refactor.

---

## 11. Files / Areas Not to Change

Do not change unless a test/import update is strictly required by the internal refactor:

- MCP public tool names,
- tool registry keys,
- Sales profile public inventory,
- Customer public contracts,
- Item public contracts,
- Sales Order public contracts,
- Quotation implementation,
- Sales Invoice implementation,
- Purchase Order implementation,
- write/create/update/submit/cancel/delete flows,
- approval flow,
- identity/authentication architecture,
- shared-secret behavior,
- India Compliance behavior,
- customer GST work,
- print/PDF/email features,
- LangGraph/LibreChat/client orchestration,
- global config architecture,
- runtime metadata exposure policy.

No new public MCP capabilities should appear after Task 31.

---

## 12. Implementation Steps

### Step 1 — Inspect current tree

Before editing, inspect:

- current git status,
- existing unrelated/in-progress changes,
- Customer aggregate implementation,
- Item aggregate implementation,
- Sales Order aggregate implementation,
- Sales Order Item metric implementation,
- `services/common/`,
- relevant tests.

Document any pre-existing working-tree changes and preserve them.

### Step 2 — Identify duplicated mechanics

Write down the exact duplicated behaviors across the three aggregate implementations.

Separate:

```text
generic mechanics
```

from:

```text
DocType-specific policy
```

Do not start by moving code blindly.

### Step 3 — Design the smallest shared internal API

Create the minimum reusable helper surface required by the existing implementations.

Prefer simple functions over a large framework/class hierarchy unless current repository style strongly favors another approach.

Avoid speculative abstraction for future DocTypes.

### Step 4 — Implement shared foundation

Implement the shared internal aggregate mechanics.

Preserve:

- Frappe v16 aggregate syntax,
- permissions,
- aliases,
- filters,
- grouping,
- response semantics,
- existing error behavior.

### Step 5 — Migrate Customer

Refactor `aggregate_customers` to use the shared mechanics.

Do not change its public input/output.

### Step 6 — Migrate Item

Refactor `aggregate_items` to use the shared mechanics.

Do not change its public input/output.

### Step 7 — Migrate Sales Order header aggregates

Refactor ordinary Sales Order header aggregate mechanics to use the shared foundation where appropriate.

Keep Sales Order-specific rules local.

### Step 8 — Evaluate Sales Order Item reuse

Reuse shared mechanics only for the ordinary parts that cleanly fit.

Keep special typed/distinct behavior local.

### Step 9 — Repository-wide raw aggregate syntax audit

Search production Python code for raw aggregate function strings, including patterns equivalent to:

```text
count(
sum(
avg(
min(
max(
```

Pay particular attention to strings passed to:

```text
frappe.get_list
frappe.get_all
frappe.db.get_list
frappe.db.get_all
```

Do not change unrelated legitimate Query Builder/function usage.

The implementation report must state whether any unsupported raw aggregate strings remain.

### Step 10 — Run focused tests

Run focused tests for:

- Customer read/aggregate
- Item read/aggregate
- Sales Order read/aggregate
- any new shared aggregate helper tests

### Step 11 — Run broader test suite

Run the complete `mcp_erpnext/tests` suite.

### Step 12 — Live site verification where available

If the environment has a usable site/database context, perform at least one live service-level or MCP-level aggregate call for each existing public aggregate tool:

```text
aggregate_customers
aggregate_items
aggregate_sales_orders
```

Use safe read-only inputs.

Also verify at least one grouped aggregate and one numeric aggregate such as SUM/AVG if existing test data permits.

If live MCP transport is not running, do not restart services unless explicitly authorized.

In that case:

- run service-level/site-context verification if possible, or
- clearly record that live transport was not verified.

Do not claim live verification if only mocks/in-process registration tests were run.

---

## 13. Acceptance Criteria

Task 31 is complete only when all of the following are true.

### Architecture

- A shared internal aggregate foundation exists or existing common infrastructure has been extended appropriately.
- Customer, Item, and Sales Order reuse it for common mechanics.
- Public tools remain explicit.
- No public generic aggregate tool exists.

### Public compatibility

The following public tool names are unchanged:

```text
aggregate_customers
aggregate_items
aggregate_sales_orders
```

Sales Order read inventory remains:

```text
get_sales_order
query_sales_orders
aggregate_sales_orders
query_sales_order_items
```

No old `search_sales_orders` public registration is reintroduced.

### Contract compatibility

Existing public input/output models and response shapes remain unchanged.

No field allowlist redesign occurs.

No contract/service consolidation occurs.

### Frappe compatibility

- No old raw SQL-style aggregate function string is introduced.
- Standard metrics use Frappe v16-compatible representation.
- Existing typed Query Builder distinct logic remains correct.
- Permission-aware execution remains preserved.

### Behavior compatibility

For equivalent input data, before/after outputs should remain equivalent for:

- count,
- sum,
- avg,
- min,
- max,
- supported grouping,
- filters,
- Sales Order Item metrics.

### Tests

- Focused aggregate/read tests pass.
- Full `mcp_erpnext` test suite passes.
- No unrelated tests are weakened or removed.
- No assertions are changed merely to accommodate an accidental behavior regression.

---

## 14. Required Tests

At minimum preserve or add coverage for:

### Customer

- count only
- grouped count if supported
- existing filters
- invalid metric
- invalid group
- permission-aware path

### Item

- count only
- grouped count if supported
- existing filters
- invalid metric
- invalid group
- permission-aware path

### Sales Order

- count
- SUM
- AVG
- MIN
- MAX
- grouping
- existing date/customer/status filters
- permission-aware path

### Sales Order Item

Where currently supported:

- count
- distinct Sales Order count
- quantity metric
- amount metric
- rate metric
- child filters
- typed distinct expression

### Shared helper

If a new shared helper module is created, add direct tests for its stable generic behavior only where useful.

Do not duplicate every DocType test inside the helper test suite.

---

## 15. Expected Results

After this task:

```text
Customer aggregate
        │
Item aggregate
        │
Sales Order aggregate
        │
        ▼
Shared internal aggregate mechanics
        │
        ▼
Permission-aware Frappe v16 query execution
```

Public surface remains:

```text
aggregate_customers
aggregate_items
aggregate_sales_orders
```

No new public tools are introduced.

Adding Quotation and Sales Invoice aggregate capabilities in later tasks should then reuse this foundation without copying the same COUNT/SUM/AVG/MIN/MAX execution logic again.

---

## 16. Known Limitations / Boundaries

This task intentionally does not:

- implement `query_quotations`,
- implement `aggregate_quotations`,
- implement field-aware Sales Invoice queries,
- implement `aggregate_sales_invoices`,
- implement Purchase Order aggregates,
- implement Employee read tools,
- create one generic public read/query/aggregate tool,
- auto-expose runtime DocType metadata,
- merge all constants into one config,
- merge service allowlists with contract literals,
- rename resolver/discovery `search_*` tools,
- redesign Sales Order Item public behavior,
- change write/lifecycle/approval tools.

Do not expand scope even if nearby improvements are discovered.

Record unrelated findings in the implementation report as recommendations only.

---

## 17. Implementation Report Required

Create an implementation report under the existing project documentation/task/report convention already used by this repository.

The report must include:

1. files inspected,
2. pre-existing working-tree changes,
3. duplicated aggregate mechanics identified,
4. shared helper/module introduced or reused,
5. exact files changed,
6. Customer migration summary,
7. Item migration summary,
8. Sales Order migration summary,
9. Sales Order Item decision and rationale,
10. confirmation that public contracts/tool names did not change,
11. raw aggregate string audit result,
12. focused test commands and results,
13. full test-suite command and result,
14. live site/MCP verification performed or explicit reason it was not performed,
15. limitations,
16. exact recommendation for the next task.

Do not report mocked/in-process checks as live MCP verification.

---

## 18. Exact Next Task

After Task 31 is complete and verified, the next task should be:

# TASK 32 — Quotation Field-Aware Read / Query / Aggregate Capability

Task 32 should inspect the existing Quotation implementation, runtime DocType metadata, current generic reader behavior, and established Customer/Item/Sales Order patterns before designing:

```text
get_quotation
query_quotations
aggregate_quotations
```

It should preserve the existing explicit-public / generic-internal architecture and reuse the shared aggregate foundation created by Task 31.

Do not start Task 32 as part of this task.
