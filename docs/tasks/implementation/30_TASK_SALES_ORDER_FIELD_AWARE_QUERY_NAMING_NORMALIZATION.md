# TASK 30 — Sales Order Field-Aware Query Naming Normalization

**Project:** `mcp_erpnext`  
**Profile:** `sales`  
**Task type:** Focused compatibility-aware naming cleanup  
**Status:** Ready for coding agent  
**Input snapshot inspected:** `mcp_erpnext_2026-09-11T10-50-54Z.zip`  
**Depends on:** Existing Customer/Item field-aware read foundations and existing Sales Order read/query/analytics implementation

---

## 1. Scope

Normalize the existing **field-aware Sales Order multi-record read tool** from:

```text
search_sales_orders
```

to:

```text
query_sales_orders
```

This is a naming normalization only.

The existing Sales Order capability already behaves as a field-aware query tool:

- typed filters;
- allowlisted field projection;
- sorting;
- pagination;
- child-related filters where already supported;
- permission-aware Frappe reads.

Do **not** redesign or expand that behavior in this task.

The public read naming convention after this task must be conceptually:

```text
get_<doctype>        -> exact known document / selected details
query_<doctype>s     -> field-aware filtered multi-record query
aggregate_<doctype>s -> server-side analytics/count/sum/avg/min/max/grouping
```

For Sales Order specifically:

```text
get_sales_order
query_sales_orders
aggregate_sales_orders
query_sales_order_items
```

---

## 2. Objective

Make the Sales Order field-aware read naming consistent with the already implemented master read capabilities:

```text
get_customer
query_customers
aggregate_customers

get_item
query_items
aggregate_items
```

The task must remove the misleading public name `search_sales_orders` because, in the current architecture, `search_*` is primarily used for fuzzy/discovery/resolution-style tools such as:

```text
search_customers
search_items
search_suppliers
```

Those search tools are intentionally different from field-aware deterministic query tools.

The final Sales Order naming must clearly communicate that it belongs to the `query_*` family.

---

## 3. Frozen naming semantics

### 3.1 `search_*`

Use `search_*` for discovery/resolution-oriented candidate search when that capability exists.

Examples already present:

```text
search_customers
search_items
search_suppliers
```

These tools may support fuzzy/user-text-oriented discovery and feed resolver workflows.

Do **not** rename these tools in this task.

### 3.2 `get_*`

Use `get_*` when the caller knows the exact document/reference and wants selected details.

Examples:

```text
get_customer
get_item
get_sales_order
```

### 3.3 `query_*`

Use `query_*` for deterministic field-aware multi-record data retrieval with explicit filters, projection, sorting and pagination.

Examples:

```text
query_customers
query_items
query_sales_orders
```

### 3.4 `aggregate_*`

Use `aggregate_*` for deterministic server-side analytics.

Examples:

```text
aggregate_customers
aggregate_items
aggregate_sales_orders
```

Pure aggregate questions must not fetch a page of source rows merely for the LLM to calculate the result.

---

## 4. Important future naming rule

This task does **not** implement field-aware Quotation, Sales Invoice or Purchase Order queries.

However, when those DocTypes receive the same field-aware capability in later tasks, use the same naming convention:

```text
get_quotation
query_quotations
aggregate_quotations

get_sales_invoice
query_sales_invoices
aggregate_sales_invoices

get_purchase_order
query_purchase_orders
aggregate_purchase_orders
```

Only implement a public aggregate capability when the DocType/business use case actually requires it.

Do not create arbitrary generic public tools such as:

```text
query_document
generic_query
aggregate_document
aggregate_any_doctype
```

Genericity belongs in internal mechanics, not in an unrestricted public MCP surface.

---

## 5. Confirmed current implementation from the inspected snapshot

The inspected repository currently contains:

```text
mcp_erpnext/tools/selling/sales_order_read.py
    def get_sales_order(...)
    def search_sales_orders(...)
    def aggregate_sales_orders(...)
    def query_sales_order_items(...)

mcp_erpnext/services/selling/sales_order_read.py
    def get_sales_order(...)
    def search_sales_orders(...)
    def aggregate_sales_orders(...)
    def query_sales_order_items(...)

mcp_erpnext/contracts/selling/sales_order_read.py
    SalesOrderSearchInput
    SalesOrderSearchOutput
    SalesOrderSearchOk
    ...
```

The public contract registry currently registers:

```text
search_sales_orders
```

The generated tool catalog currently lists:

```text
search_sales_orders
```

The Sales profile registration currently obtains this tool through:

```text
register_sales_order_read_tools
```

The current public functionality must be preserved while the naming is normalized.

---

## 6. Mandatory inspection before coding

Before editing, inspect the **current working tree**, not only this task file or the supplied ZIP snapshot.

At minimum inspect:

```text
mcp_erpnext/tools/selling/sales_order_read.py
mcp_erpnext/services/selling/sales_order_read.py
mcp_erpnext/contracts/selling/sales_order_read.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py

mcp_erpnext/tests/test_sales_order_read.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_profiles.py

scripts/generate_tool_catalog.py
docs/TOOLS.md
docs/architecture/MCP_TOOL_CONTRACT_ARCHITECTURE.md
```

Also search the current repository for all references to:

```text
search_sales_orders
SalesOrderSearchInput
SalesOrderSearchOutput
SalesOrderSearchOk
```

Do not assume the inspected ZIP is newer than the coding agent's working tree.

Preserve any newer unrelated user changes.

---

## 7. Allowed changes

This task may change only what is necessary to normalize the Sales Order field-aware query naming and keep contracts/tests/docs consistent.

Expected production changes include:

```text
mcp_erpnext/tools/selling/sales_order_read.py
mcp_erpnext/services/selling/sales_order_read.py
mcp_erpnext/contracts/selling/sales_order_read.py
mcp_erpnext/contracts/registry.py
```

Expected test changes include the relevant references in:

```text
mcp_erpnext/tests/test_sales_order_read.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_profiles.py
```

Update current generated/current architecture documentation where necessary:

```text
docs/TOOLS.md
# regenerate via scripts/generate_tool_catalog.py; do not hand-edit generated catalog

docs/architecture/MCP_TOOL_CONTRACT_ARCHITECTURE.md
# only the current naming/family explanation that is now inaccurate
```

Create an implementation report at:

```text
docs/inspect/SALES_ORDER_FIELD_AWARE_QUERY_NAMING_NORMALIZATION_IMPLEMENTATION_REPORT.md
```

---

## 8. Files/components not to change conceptually

Do **not** modify the following architecture in this task:

### 8.1 Do not centralize read configuration

Do not merge or relocate the existing per-DocType contract/service allowlists merely to remove duplication.

Keep the current separation of concerns as-is.

For example, do not redesign:

```text
CustomerField / service _FIELDS
ItemField / service _FIELDS
SalesOrderHeaderField / service _HEADER_FIELDS
```

A future invariant/sync improvement may be considered separately, but it is **not authorized here**.

### 8.2 Do not create one central read config

Do not introduce a new universal configuration file that automatically exposes fields for every DocType.

The current explicit public contract + service allowlist structure remains valid.

### 8.3 Do not change output projections

Do not add, remove or reorder supported Sales Order fields solely because this task touches the contract names.

Preserve existing:

```text
_HEADER_FIELDS
_ITEM_FIELDS
DEFAULT_ITEM_FIELDS
sort fields
filter fields
group fields
metrics
```

unless a current-tree compile/test break proves a mechanical rename is required.

### 8.4 Do not refactor aggregate internals

Do not extract a shared aggregate engine in Task 30.

That is the exact next task after this naming normalization.

### 8.5 Do not implement Quotation/Sales Invoice field-aware reads

Do not add:

```text
query_quotations
aggregate_quotations
query_sales_invoices
aggregate_sales_invoices
```

in Task 30.

### 8.6 Do not rename generic compact read tools yet

Existing compact generic tools such as:

```text
search_quotations
search_sales_invoices
search_purchase_orders
```

remain untouched in this task.

They should be replaced/normalized only when that DocType receives its focused field-aware read/query capability.

### 8.7 Do not touch write flows

Do not modify:

```text
prepare_sales_order
confirm_sales_order
prepare_quotation
confirm_quotation
prepare_sales_invoice
confirm_sales_invoice
lifecycle tools
conversion tools
PDF/email tools
approval behavior
identity behavior
```

---

## 9. Required production rename

Rename the field-aware Sales Order query function throughout the active implementation:

```text
search_sales_orders
    -> query_sales_orders
```

This applies to the public MCP wrapper and the corresponding service function.

Conceptually:

```python
def query_sales_orders(...):
    ...
```

and:

```python
def query_sales_orders(criteria: dict[str, Any]) -> dict[str, Any]:
    ...
```

Update `execute_tool_with_context(...)` so observability/audit uses:

```text
query_sales_orders
```

not the old name.

---

## 10. Required contract naming normalization

For consistency with Customer and Item, rename the Sales Order field-aware query contract classes where they still use `Search` terminology.

Expected direction:

```text
SalesOrderSearchInput
    -> SalesOrderQueryInput

SalesOrderSearchOk
    -> SalesOrderQueryOk

SalesOrderSearchOutput
    -> SalesOrderQueryOutput
```

Do not change their field schemas or semantics as part of this rename.

If the current working tree contains additional `SalesOrderSearch*` classes tied only to this same field-aware query capability, normalize them consistently.

Do not mechanically rename unrelated search/discovery contracts.

---

## 11. Public registry change

Change the active public contract registry key from:

```text
search_sales_orders
```

to:

```text
query_sales_orders
```

The purpose text should describe a **query**, consistent with Customer and Item, for example conceptually:

```text
Query permitted Sales Orders using typed filters, projection, sorting, and pagination.
```

Keep:

```text
Domain: Selling
Operation: SEARCH
SideEffectClass: READ
approval_required: False
```

unless the repository's current enum architecture has changed.

The internal operation enum may remain `SEARCH`; this task is about the public MCP capability naming/semantics, not renaming internal enums across the entire codebase.

---

## 12. Registration rule

The final Sales-profile MCP inventory must register:

```text
get_sales_order
query_sales_orders
aggregate_sales_orders
query_sales_order_items
```

and must **not** register:

```text
search_sales_orders
```

Do not register both names as duplicate public aliases.

Reason: the goal is a clean, predictable public naming convention, not permanent compatibility clutter.

If inspection reveals a genuine external production consumer that hardcodes `search_sales_orders`, do not silently add an alias. Record the dependency in the implementation report and preserve the user's requested clean target unless repository-local architecture explicitly requires a deprecation mechanism.

---

## 13. Behavior that must remain identical

The rename must not change existing query semantics.

Preserve the current Sales Order query's behavior for:

```text
transaction_date_from
transaction_date_to
created_from
created_to
delivery_date_from
delivery_date_to
customer
customer_group
territory
status
delivery_status
billing_status
docstatus
item_code
sales_person
owner
currency
min_grand_total
max_grand_total
limit
offset
sort_by
sort_order
fields
```

Preserve:

```text
field projection
bounded pagination
sort behavior
distinct handling for child-related filters
permission-aware frappe.get_list(... ignore_permissions=False)
result count = returned page length
```

Do not convert page `count` into a database aggregate count.

Database aggregate questions remain the job of:

```text
aggregate_sales_orders
```

---

## 14. Existing output/constant architecture must remain as-is

The user's intended architecture is already valid:

```text
public contract allowlist
+
service constants / explicit implementation policy
```

The task must preserve the current explicit Sales Order constants, including the equivalent current-tree definitions of:

```text
_HEADER_FIELDS
_ITEM_FIELDS
_HEADER_METRICS
_ITEM_METRICS
DEFAULT_ITEM_FIELDS
```

Do not move them into Customer/Item config modules.

Do not create a single global read-config registry.

Do not auto-expose fields merely because runtime DocType metadata contains them.

Future new fields must continue to require an intentional MCP contract/service change.

---

## 15. Architecture documentation update

The current architecture document contains older examples that imply:

```text
search_sales_orders
```

belongs to the same family as fuzzy `search_customers` / `search_items`.

Update the current architecture guidance narrowly so future tasks understand the difference:

```text
search_*     = discovery/resolution candidate search
get_*        = exact document read
query_*      = deterministic field-aware multi-record query
aggregate_*  = deterministic server-side analytics
```

Do not rewrite historical implementation task files solely to replace the old name.

For example, preserve historical evidence in:

```text
docs/tasks/implementation/15_TASK_SALES_ORDER_READ_QUERY_ANALYTICS_FOUNDATION.md
```

unless a current project convention explicitly marks task files as mutable living specs.

The implementation report should state that Task 15 used the historical name and Task 30 normalized the active public contract.

---

## 16. Generated tool catalog

`docs/TOOLS.md` is generated by:

```text
scripts/generate_tool_catalog.py
```

Do not manually edit the generated catalog as the primary change.

After code/registry changes, regenerate it using the repository's supported environment.

The generated Sales profile must contain:

```text
query_sales_orders
```

and must not contain:

```text
search_sales_orders
```

---

## 17. Repository-wide stale-reference audit

After implementation, run a repository search for:

```text
search_sales_orders
```

Classify any remaining match.

Allowed remaining references should only be intentional historical records, such as frozen historical task documentation, if the repository treats them as immutable history.

No active production code, current generated catalog, current architecture guidance or active tests may continue using the old public name.

Also search for active stale class names:

```text
SalesOrderSearchInput
SalesOrderSearchOutput
SalesOrderSearchOk
```

No active production/test import should remain if the classes were renamed under this task.

---

## 18. Tests to update/add

### 18.1 Service tests

Update Sales Order read service tests to call:

```text
query_sales_orders
```

Preserve all existing behavior assertions.

At minimum retain verification for:

- permission-aware reads;
- filter construction;
- projection;
- sort;
- offset/limit;
- child-related distinct behavior if already covered;
- empty result behavior.

### 18.2 Tool registration

Update the expected Sales inventory:

```text
search_sales_orders
    -> query_sales_orders
```

Assert the old name is absent.

### 18.3 Profile tests

Explicitly assert in the Sales profile:

```text
query_sales_orders in names
search_sales_orders not in names
```

Purchase profile must not gain the Sales Order query tool.

### 18.4 Contract tests

Verify `query_sales_orders` publishes the same explicit typed input/output schema that the old tool published, aside from renamed model titles where applicable.

Check that unsupported fields remain absent from public schemas.

### 18.5 Tool contract audit

The existing contract audit must remain clean.

---

## 19. Required test commands

Use the current bench/app environment and inspect the repository's normal test conventions first.

At minimum run the focused equivalent of:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python -m unittest \
  mcp_erpnext.tests.test_sales_order_read \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_profiles
```

Then run the broader relevant unit suite if practical.

Regenerate the catalog:

```bash
/home/frappe/frappe-bench/env/bin/python scripts/generate_tool_catalog.py
```

and verify it is current:

```bash
/home/frappe/frappe-bench/env/bin/python scripts/generate_tool_catalog.py --check
```

Adapt paths only if the current environment differs.

Do not claim commands passed unless they were actually run successfully.

---

## 20. MCP runtime verification

If a runnable local MCP Sales profile is available, inspect `tools/list` after implementation.

Expected inventory condition:

```text
query_sales_orders       PRESENT
search_sales_orders      ABSENT
get_sales_order          PRESENT
aggregate_sales_orders   PRESENT
query_sales_order_items  PRESENT
```

Then perform at least one harmless read-only `query_sales_orders` call against an authorized site if practical.

Example intent:

```text
query_sales_orders(limit=1, fields=["name", "customer", "transaction_date"])
```

Verify:

- tool can be invoked under the new name;
- output schema remains valid;
- projection works;
- permissions remain active;
- no document is modified.

If live MCP/site verification is unavailable, clearly mark it `NOT VERIFIED LIVE` in the report.

---

## 21. Acceptance criteria

Task 30 is complete only when all applicable items are true:

- [ ] Active public tool is named `query_sales_orders`.
- [ ] Active public tool `search_sales_orders` no longer exists.
- [ ] Service function uses `query_sales_orders` naming.
- [ ] Field-aware Sales Order query contract classes use `Query` naming consistently where applicable.
- [ ] Registry contains `query_sales_orders` and no active `search_sales_orders` contract.
- [ ] `execute_tool_with_context` records the new tool name.
- [ ] Tool registration preserves tool count; this is one rename, not an additional capability.
- [ ] Existing Sales Order query input fields are unchanged.
- [ ] Existing Sales Order query output behavior is unchanged.
- [ ] Existing `_HEADER_FIELDS`, `_ITEM_FIELDS`, metrics and other service constants are not redesigned.
- [ ] No central read config is introduced.
- [ ] No contract/service allowlist consolidation from the previously discussed optional improvement is implemented.
- [ ] `search_customers`, `search_items` and other resolver/discovery search tools remain unchanged.
- [ ] `query_customers` and `query_items` remain unchanged.
- [ ] `aggregate_sales_orders` remains unchanged behaviorally.
- [ ] Quotation/Sales Invoice/Purchase Order field-aware capabilities are not implemented here.
- [ ] Current architecture docs explain search/get/query/aggregate naming semantics clearly.
- [ ] Generated `docs/TOOLS.md` is regenerated and passes `--check`.
- [ ] Focused tests pass.
- [ ] Contract audit passes.
- [ ] Live MCP verification is performed or explicitly reported as not performed.
- [ ] An implementation report is created.

---

## 22. Expected results

After Task 30, the Sales Order read surface should be mentally obvious:

```text
User knows exact SO
    -> get_sales_order

User asks for SO records using business filters
    -> query_sales_orders

User asks count / total / average / grouped analytics
    -> aggregate_sales_orders

User asks item-line history / item-level metrics
    -> query_sales_order_items
```

Examples:

```text
"Give me SAL-ORD-2026-00014 details"
    -> get_sales_order

"Show last 10 Sales Orders for Customer X"
    -> query_sales_orders

"How many Sales Orders did Customer X have this month?"
    -> aggregate_sales_orders(metrics=["count"], ...)

"How much of Item X was ordered?"
    -> query_sales_order_items(... metrics=["sum_qty"] ...)
```

No redundant one-question-one-tool proliferation should be introduced.

---

## 23. Known limitations / boundaries

This task intentionally does not solve:

```text
shared aggregate implementation duplication
Quotation field-aware read/query/aggregate
Sales Invoice field-aware read/query/aggregate
Purchase Order field-aware read/query/aggregate
Employee/HR read analytics
field allowlist contract/service sync automation
runtime metadata-driven public field exposure
Sales Order Item query/aggregate split redesign
```

These are separate architectural decisions/tasks.

The current separation of public contract allowlists and service constants remains intentionally unchanged.

---

## 24. Implementation report requirements

Create:

```text
docs/inspect/SALES_ORDER_FIELD_AWARE_QUERY_NAMING_NORMALIZATION_IMPLEMENTATION_REPORT.md
```

The report must include:

1. current-tree files inspected;
2. every active code reference changed;
3. final public tool name;
4. whether contract classes were normalized from `Search` to `Query`;
5. confirmation that query input/output behavior did not change;
6. confirmation that output field constants/allowlists did not change;
7. confirmation that no central config/refactor was introduced;
8. remaining intentional historical `search_sales_orders` references, if any;
9. generated tool catalog result;
10. focused tests run and exact results;
11. contract audit result;
12. MCP `tools/list` result if run;
13. live read result if run;
14. limitations;
15. exact recommendation for Task 31.

---

## 25. Exact next task after Task 30

After Task 30 is implemented and verified, stop.

The exact next task is:

```text
TASK 31 — Shared Internal Aggregate Foundation
```

Task 31 should inspect and centralize only the **reusable internal aggregate mechanics** currently duplicated across:

```text
Customer
Item
Sales Order
```

while preserving explicit public tools:

```text
aggregate_customers
aggregate_items
aggregate_sales_orders
```

Task 31 must **not** introduce a generic public `aggregate_document` tool.

It must preserve the Frappe v16-supported aggregate representation, for example dictionary aggregate fields such as:

```python
{"COUNT": "*", "as": "count"}
{"SUM": "grand_total", "as": "sum_grand_total"}
```

and preserve typed Query Builder handling for special expressions such as distinct counting where needed.

Only after Task 31 is implemented and verified should the project proceed to focused field-aware Quotation and Sales Invoice read/query/aggregate tasks.

---

# Final frozen result of Task 30

```text
PUBLIC READ NAMING

Discovery/resolution search
    search_customers
    search_items
    search_suppliers

Exact document read
    get_customer
    get_item
    get_sales_order
    get_quotation             # existing compact implementation for now
    get_sales_invoice         # existing compact implementation for now

Field-aware query
    query_customers
    query_items
    query_sales_orders

Server analytics
    aggregate_customers
    aggregate_items
    aggregate_sales_orders

Child-line query
    query_sales_order_items
```

The public naming is normalized without changing the current field/output configuration architecture.
