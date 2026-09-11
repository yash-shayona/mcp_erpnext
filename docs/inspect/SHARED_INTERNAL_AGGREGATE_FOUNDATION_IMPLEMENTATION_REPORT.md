# Shared Internal Aggregate Foundation

## Scope

Task 31 centralizes reusable aggregate mechanics for the existing explicit
Customer, Item, and Sales Order aggregate services. It does not add a public
generic aggregate tool or implement aggregates for another DocType.

## Current-tree inspection

Inspected:

- `mcp_erpnext/services/common/`
- `mcp_erpnext/services/common/read.py`
- `mcp_erpnext/services/masters/customer_read.py`
- `mcp_erpnext/services/masters/item_read.py`
- `mcp_erpnext/services/selling/sales_order_read.py`
- `mcp_erpnext/contracts/masters/customer_read.py`
- `mcp_erpnext/contracts/masters/item_read.py`
- `mcp_erpnext/contracts/selling/sales_order_read.py`
- `mcp_erpnext/tools/masters/customer_read.py`
- `mcp_erpnext/tools/masters/item_read.py`
- `mcp_erpnext/tools/selling/sales_order_read.py`
- `mcp_erpnext/tests/test_customer_read.py`
- `mcp_erpnext/tests/test_item_read.py`
- `mcp_erpnext/tests/test_sales_order_read.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/sales.py`

The nested `apps/mcp_erpnext` directory is the Git checkout. Before this
implementation, the working tree already contained Task 30 changes in the
Sales Order service, contracts, wrapper, registry, profile/catalog, and
related tests, plus the Task 30 report and Task 30/31 task documents. Those
changes were preserved. The pre-existing Sales Order service changes included
the public `query_sales_orders` naming and the Frappe v16 aggregate dictionary
representation.

## Duplicated mechanics identified

Customer, Item, and Sales Order each independently performed some or all of
the following:

- mapped requested metric names to aggregate field expressions;
- prepended a grouping expression to the selected fields;
- constructed the comma-separated `group_by` and deterministic `order_by`
  expressions;
- called `frappe.get_list` with `ignore_permissions=False`; and
- shaped non-null metric values and the optional public `group_value`.

DocType-specific filters, allowlists, metric names, currency semantics, child
table mappings, and validation messages remain in their owning services.

## Shared foundation

Added `mcp_erpnext/services/common/aggregate.py` with four small internal
helpers:

- `build_aggregate_field()` creates the supported Frappe v16 dictionary form
  for COUNT, SUM, AVG, MIN, and MAX.
- `build_aggregate_fields()` assembles already-allowlisted metric mappings and
  optional group expressions, including a special group alias when needed.
- `execute_aggregate()` forwards the aggregate through the caller's Frappe
  `get_list` seam with `group_by`, matching `order_by`, and
  `ignore_permissions=False`.
- `shape_aggregate_rows()` preserves the common non-null metric/group result
  shape.

The helper accepts a `get_list` callable so each service retains its current
Frappe identity seam and permission context; it does not import or bypass
Frappe permissions itself.

## Service migrations

### Customer

`aggregate_customers` now uses the shared field builder, permission-aware
executor, and common row shaper. Customer metric/group validation and all
Customer filters remain local. Its public response is unchanged.

### Item

`aggregate_items` now uses the same shared mechanics. Item metric/group
validation and filters remain local. Its public response is unchanged.

### Sales Order

`aggregate_sales_orders` now uses the shared field builder, executor, and row
shaper for header aggregates. Sales Order keeps its local monetary policy:
monetary metrics still add `currency` to both selected fields and grouping,
and the public result still reports `currency`.

### Sales Order Item

The ordinary item metric/group assembly and permission-aware execution now use
the shared foundation. The `count_distinct_orders` metric remains a typed
Query Builder expression using `Count(...).distinct()` and is inserted into a
local metric mapping. The child-table field mapping, currency policy, filters,
and public `query_sales_order_items` response remain local and unchanged.

## Public compatibility

No public contracts, registry keys, profile inventory, or tool wrappers were
changed by Task 31. The existing public aggregate tools remain:

```text
aggregate_customers
aggregate_items
aggregate_sales_orders
```

The Sales Order read inventory remains:

```text
get_sales_order
query_sales_orders
aggregate_sales_orders
query_sales_order_items
```

No public generic aggregate tool was added. No contract/service consolidation
or allowlist redesign was introduced.

## Exact Task 31 files changed

- `mcp_erpnext/services/common/aggregate.py` — new shared internal helpers.
- `mcp_erpnext/services/masters/customer_read.py` — Customer migration.
- `mcp_erpnext/services/masters/item_read.py` — Item migration.
- `mcp_erpnext/services/selling/sales_order_read.py` — header/item aggregate
  migration while preserving Sales Order-specific behavior.
- `mcp_erpnext/tests/test_aggregate.py` — focused shared-helper coverage.
- `docs/inspect/SHARED_INTERNAL_AGGREGATE_FOUNDATION_IMPLEMENTATION_REPORT.md`
  — this report.

## Aggregate syntax audit

The production-Python audit found no raw SQL-style aggregate strings such as
`count(...) as ...`, `sum(...) as ...`, `avg(...) as ...`, `min(...) as ...`,
or `max(...) as ...` passed as aggregate field definitions. Standard metrics
use Frappe v16-compatible dictionaries. The only aggregate-function match
remaining is the intentional typed Query Builder `Count(...).distinct()` for
distinct Sales Order counting; unrelated Python built-in `sum`/`min`/`max`
uses are not database aggregate expressions.

## Verification

Focused command:

```bash
PYTHONPATH=. ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_aggregate \
  mcp_erpnext.tests.test_customer_read \
  mcp_erpnext.tests.test_item_read \
  mcp_erpnext.tests.test_sales_order_read
```

Result: `Ran 30 tests ... OK`.

Full suite command:

```bash
PYTHONPATH=. ../../env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
```

Result: `Ran 241 tests ... OK`.

The full run emitted existing warning/error log output from the environment's
MCP authentication and mocked India Compliance test paths; no test failed.
`git diff --check` and targeted `compileall` also completed successfully.

## Live site/MCP verification

Live aggregate calls were attempted against `praveg.localhost` using safe,
read-only inputs for all three public aggregate services. They did not reach
the service because Bench reported `App mcp_erpnext is not installed` for the
site. A direct Frappe site-context import/connect attempt then reached site
initialization but failed while opening the configured
`/home/frappe/logs/database.log` (`FileNotFoundError`). Therefore live
database/service and live MCP transport behavior are **NOT VERIFIED**. No
service, database, cache, or server state was changed.

## Limitations

This task does not add Quotation, Sales Invoice, Purchase Order, Employee, or
generic aggregate capabilities. It does not redesign contracts/configuration,
change identity or approval behavior, or alter any write/lifecycle flow.

## Recommendation for Task 32

Proceed with **TASK 32 — Quotation Field-Aware Read / Query / Aggregate
Capability**. Inspect Quotation source and live metadata first, keep the
explicit-public/generic-internal architecture, and reuse this shared
aggregate foundation for `get_quotation`, `query_quotations`, and
`aggregate_quotations`.
