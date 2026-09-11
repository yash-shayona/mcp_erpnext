# Sales Order Field-Aware Query Naming Normalization

## Scope

Task 30 was implemented against the current `apps/mcp_erpnext` working tree.
The change normalizes the active field-aware Sales Order multi-record read name
from `search_sales_orders` to `query_sales_orders` without changing query
semantics.

## Current-tree inspection

Inspected:

- `mcp_erpnext/tools/selling/sales_order_read.py`
- `mcp_erpnext/services/selling/sales_order_read.py`
- `mcp_erpnext/contracts/selling/sales_order_read.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/sales.py`
- `mcp_erpnext/tools/__init__.py`
- `mcp_erpnext/tests/test_sales_order_read.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `mcp_erpnext/tests/test_tool_contracts.py`
- `mcp_erpnext/tests/test_profiles.py`
- `scripts/generate_tool_catalog.py`
- `docs/TOOLS.md`
- `docs/architecture/MCP_TOOL_CONTRACT_ARCHITECTURE.md`

The nested app checkout was the Git repository. Before implementation it had
unrelated/in-progress changes in the Sales Order service and service tests;
those changes were preserved.

## Active references changed

- Public wrapper `search_sales_orders` was renamed to `query_sales_orders`.
- The wrapper now uses `SalesOrderQueryInput` and `SalesOrderQueryOutput`.
- `execute_tool_with_context` now records `query_sales_orders`.
- The service function was renamed to `query_sales_orders`.
- Contract classes `SalesOrderSearchInput`, `SalesOrderSearchOk`, and
  `SalesOrderSearchOutput` were renamed to their `SalesOrderQuery*` equivalents.
- The registry key, purpose text, typed input model, and typed output model were
  updated to `query_sales_orders`.
- Sales Order service, registration, profile, and contract tests now verify the
  new name and the absence of the old public name.

No external production consumer hardcoding `search_sales_orders` was found in
the repository-local search. The negative-name assertions in tests are
intentional checks that the old public name is absent.

## Final public surface

The Sales Order read inventory is:

```text
get_sales_order
query_sales_orders
aggregate_sales_orders
query_sales_order_items
```

`search_sales_orders` is not registered and has no active registry contract.
`search_customers`, `search_items`, and other discovery/resolution tools were
not renamed.

## Behavior and architecture preservation

- `SalesOrderQueryInput` has the same filters, projection, sort, pagination, and
  validation fields as the former input class.
- `SalesOrderQueryOutput` preserves the former result shape and page count
  semantics.
- Permission-aware `frappe.get_list(..., ignore_permissions=False)`, child
  filter handling, and distinct handling remain unchanged.
- `_HEADER_FIELDS`, `_ITEM_FIELDS`, `_HEADER_METRICS`, `_ITEM_METRICS`, and
  `DEFAULT_ITEM_FIELDS` were not redesigned or consolidated.
- No central read configuration, aggregate refactor, new DocType query, write
  flow, approval behavior, or alias was introduced.
- The pre-existing working-tree aggregate representation changes were preserved;
  they were not introduced by the naming normalization.

The architecture document now defines `search_*` as discovery/resolution
candidate search, `get_*` as exact reads, `query_*` as deterministic
field-aware multi-record retrieval, and `aggregate_*` as server-side analytics.
Historical Task 15 and other historical task documents retain the former name
as historical evidence.

## Generated catalog

Ran from `apps/mcp_erpnext`:

```bash
/home/frappe/frappe-bench/env/bin/python scripts/generate_tool_catalog.py
/home/frappe/frappe-bench/env/bin/python scripts/generate_tool_catalog.py --check
```

Both commands completed successfully. `docs/TOOLS.md` contains
`query_sales_orders` and does not contain the old catalog entry.

## Tests and contract audit

Focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python -m unittest \
  mcp_erpnext.tests.test_sales_order_read \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_profiles
```

Result: `Ran 24 tests ... OK`.

Broader relevant command:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
```

Result: `Ran 236 tests ... OK`.

The existing contract audit is covered by the registered-inventory tests and
passed in both the focused and broader runs. The broader run emitted existing
warning/error log output from mocked authentication and India-compliance test
paths; it did not fail a test.

## Runtime boundaries

No separate live MCP server process was running in the inspected environment,
so live transport `tools/list` and an authorized ERPNext
`query_sales_orders(limit=1, fields=[...])` call were **NOT VERIFIED LIVE**.
The generated catalog and FastMCP registration tests exercised the local
profile registration and typed schemas statically/in-process.

## Limitations

This task does not implement field-aware Quotation, Sales Invoice, or Purchase
Order queries, shared aggregate internals, allowlist synchronization, or any
write-flow changes.

## Recommendation for Task 31

Proceed with **TASK 31 — Shared Internal Aggregate Foundation**. Inspect and
centralize only reusable internal aggregate mechanics duplicated across
Customer, Item, and Sales Order, while preserving the explicit public tools
`aggregate_customers`, `aggregate_items`, and `aggregate_sales_orders` and the
Frappe v16-supported aggregate representations.
