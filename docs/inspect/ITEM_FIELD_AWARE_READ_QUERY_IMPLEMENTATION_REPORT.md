# Item Field-Aware Read / Query Implementation Report

## 1. Final status

**PARTIAL** — the sales-only Item read/query foundation, resolver regression
coverage, contract audit, profile isolation, generated catalog, and full local
unit suite pass. An authenticated live MCP conversation and live Item creation
flow were not run, so the reported Quotation scenario is explicitly **NOT
VERIFIED** end to end.

## 2. Exact source files inspected

- `docs/tasks/implementation/20_TASK_ITEM_FIELD_AWARE_READ_QUERY_FOUNDATION.md`
- `docs/tasks/implementation/07B_GENERIC_AMBIGUOUS_ENTITY_SELECTION_ENFORCEMENT.md`
- `docs/inspect/CUSTOMER_FIELD_AWARE_READ_QUERY_IMPLEMENTATION_REPORT.md`
- `mcp_erpnext/config/masters/item.py`
- `mcp_erpnext/contracts/masters/resolution.py`
- `mcp_erpnext/services/masters/item.py`
- `mcp_erpnext/tools/masters/item.py`
- `mcp_erpnext/tools/masters/purchase_item.py`
- `mcp_erpnext/services/common/entity_resolution.py`
- Item, Customer, Sales Order read contracts, services, wrappers, and tests
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/audit.py`
- `mcp_erpnext/profiles/sales.py` and `mcp_erpnext/profiles/purchase.py`
- `mcp_erpnext/tools/__init__.py`
- profile, registration, interaction, Item-service, and contract tests
- `scripts/generate_tool_catalog.py` and generated `docs/TOOLS.md`
- `apps/erpnext/erpnext/stock/doctype/item/item.json`
- `apps/erpnext/erpnext/stock/doctype/item/item.py`
- merged site metadata from `frappe.get_meta("Item")` on `praveg.localhost`

## 3. Current Frappe / ERPNext versions inspected

The checked-out package declarations report Frappe `16.33.1` and ERPNext
`16.34.2` from `apps/frappe/frappe/__init__.py` and
`apps/erpnext/erpnext/__init__.py`.

`bench version` itself could not complete because an unrelated
`india_compliance` repository was rejected by Git's safe-directory check. This
did not prevent the package-version inspection or the read-only Item metadata
inspection.

## 4. Item runtime metadata evidence

The merged `Item` metadata was inspected read-only with:

```bash
./env/bin/bench --site praveg.localhost execute frappe.get_meta --args '["Item"]'
```

The selected fields below are standard (`custom=0`) Item fields. `name`,
`owner`, `creation`, and `modified` are Frappe system columns rather than
entries in `meta.fields`.

| fieldname | label | fieldtype | options/link target | standard or custom | fetch_from if any | queryable/list-column status | projection | filter | sort | group | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `name` | Name | system column | — | standard | — | yes | yes | yes | yes | no | Stable exact Item reference. |
| `item_code` | Item Code | Data | — | standard | — | yes, unique | yes | yes | yes | no | ERPNext Item identity and exact lookup. |
| `item_name` | Item Name | Data | — | standard | — | yes, search-indexed | yes | yes | yes | no | Human-readable exact Item-name lookup. |
| `item_group` | Item Group | Link | Item Group | standard | — | yes, list/filter | yes | yes | yes | yes | Deterministic classification and grouping. |
| `stock_uom` | Default Unit of Measure | Link | UOM | standard | — | yes, list | yes | yes | no | Safe Item unit read and exact filter. |
| `disabled` | Disabled | Check | — | standard | — | yes, search-indexed | yes | yes | yes | yes | Caller-controlled active/disabled semantics. |
| `is_sales_item` | Allow Sales | Check | — | standard | — | yes, list | yes | yes | no | Explicit sales usability filter. |
| `is_purchase_item` | Allow Purchase | Check | — | standard | — | yes | yes | yes | no | Explicit purchase capability read/filter. |
| `is_stock_item` | Maintain Stock | Check | — | standard | — | yes | yes | yes | yes | Distinguish stock and service Items. |
| `brand` | Brand | Link | Brand | standard | — | yes | yes | yes | no | Safe classification and grouping. |
| `description` | Description | Text Editor | — | standard | — | yes, stored field | yes | no | no | no | Descriptive projection only when requested. |
| `sales_uom` | Default Sales Unit of Measure | Link | UOM | standard | — | yes | yes | no | no | Safe sales configuration read. |
| `owner` | Owner | system column | User | standard | — | yes | yes | no | no | Permission-scoped ownership projection/filter. |
| `creation` | Creation | system column | DateTime | standard | — | yes | yes | date range | no | Date range and recency sort. |
| `modified` | Modified | system column | DateTime | standard | — | yes | yes | date range | no | Date range and recency sort. |
| `standard_rate` | Standard Selling Rate | Currency | — | standard | — | yes | no | no | no | Excluded: not authoritative transaction pricing. |

The runtime metadata also confirms `item_group` points to a leaf-filtered Item
Group, `stock_uom` and `sales_uom` point to UOM, and `brand` points to Brand.
No custom Item field was added or auto-exposed.

## 5. Final allowlists

- Projection: `name`, `item_code`, `item_name`, `item_group`, `stock_uom`,
  `disabled`, `is_sales_item`, `is_purchase_item`, `is_stock_item`, `brand`,
  `description`, `sales_uom`, `owner`, `creation`, `modified`.
- Exact filters: `name`, `item_code`, `item_name`, `item_group`, `stock_uom`,
  `brand`, `owner`, `disabled`, `is_sales_item`, `is_purchase_item`,
  `is_stock_item`, plus `created_from`/`created_to` and
  `modified_from`/`modified_to` date ranges.
- Sort: `name`, `item_code`, `item_name`, `item_group`, `disabled`,
  `creation`, `modified`, with a deterministic `name` tie-breaker.
- Group: `item_group`, `brand`, `disabled`, `is_sales_item`,
  `is_purchase_item`, `is_stock_item`.
- Metric: `count` only.
- Pagination: default `20`, maximum `100`, non-negative offset.

`standard_rate`, stock balances, valuation, pricing, child tables, and arbitrary
custom fields are not exposed.

## 6. Files added/changed

Added:

- `mcp_erpnext/contracts/masters/item_read.py`
- `mcp_erpnext/services/masters/item_read.py`
- `mcp_erpnext/tools/masters/item_read.py`
- `mcp_erpnext/tests/test_item_read.py`
- this report

Changed:

- `mcp_erpnext/config/masters/item.py`
- `mcp_erpnext/services/masters/item.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/sales.py`
- Item, profile, registration, and contract tests
- generated `docs/TOOLS.md`

The existing Customer Task 19 changes and all unrelated user changes were
preserved. No additional file outside the task's allowed areas was changed.

## 7. Final public contracts

- `get_item(item, fields?)` — exact Item reference read with a default
  `name`-only projection; returns `ok`, `not_found`, or typed `error`.
- `query_items(...)` — exact equality filters, allowlisted projection,
  deterministic sorting, bounded pagination, and `ok` results with page count.
  It does not call the fuzzy resolver.
- `aggregate_items(...)` — server-side `count`, optionally grouped by one
  allowlisted Item field.

All three are explicit typed contracts with object input/output schemas,
`READ` side-effect metadata, and no approval requirement.

## 8. Permission behavior

- Exact reads use `frappe.get_doc("Item", name)` followed by
  `doc.has_permission("read")`.
- Queries and aggregates use `frappe.get_list(..., ignore_permissions=False)`.
- Boolean filters are converted to native `0`/`1` equality filters.
- The query service does not silently add the resolver's active-sales filter;
  callers must explicitly request `disabled=false` and `is_sales_item=true`
  when checking sales usability.
- No `get_all`, Administrator switching, permission bypass, raw SQL, or model-
  supplied filter/operator dictionary was introduced.

## 9. Old and new Item false-ambiguity behavior

The old path called the shared resolver after token-based candidate discovery.
After exact matching and the existing strong-spelling rule failed, any
remaining candidates were returned as `ambiguous`. For the observed
`Web Development Services` candidate set, the ranked scores were:

```text
Custom Web Application Development   0.677
Frappe Custom App Development        0.561
API Integration Development          0.499
```

The new path keeps the shared resolver unchanged and adds an Item-only
classification layer after it. The exact rule is:

```text
if shared result is ambiguous
and there is not more than one exact candidate
and every ranked candidate score is below 0.69:
    return not_found with candidates=[]
otherwise:
    preserve the shared result
```

The `0.69` floor is documented in `config/masters/item.py` and calibrated from
the existing resolver's concrete scores: the observed weak-only set tops out
at `0.677`, while the frozen `Development Item` ambiguity test tops out at
`0.693`. Exact matches and the shared strong spelling-correction path are
evaluated before this floor. This is intentionally not a shared Customer,
Supplier, or Purchase policy change.

Therefore `resolve_item("Web Development Services")` and the corresponding
`search_items` result become `not_found` with empty candidates and cannot emit
selection UI. The controlled `prepare_item` / `confirm_item` path remains the
only creation path.

## 10. Resolver regression proof

Focused tests pass for:

- `Web Development Services` weak-only candidates -> `not_found`, empty
  candidates, and no misleading search selection state.
- `Development Item` two near-tied candidates -> `ambiguous` with candidates
  retained.
- Exact Item reference -> `resolved` with `match_type="exact"`.
- Strong single correction -> `resolved` with
  `match_type="spelling_correction"`.
- Purchase Item search and resolution continue to pass
  `disabled != 1` plus `is_purchase_item = 1` filters.

Customer and Supplier do not use the Item-specific classification layer, so
their shared resolver behavior is unchanged. Existing Customer resolver tests
and the Task 07B shared ambiguity test pass in the full suite.

## 11. Create-if-missing behavior

The new read tools only establish deterministic existence/read results. They
do not create Items. A `not_found` Item can continue through the existing
controlled flow:

```text
not_found -> prepare_item -> needs_input or ready preview
          -> explicit trusted approval -> confirm_item
          -> created Item reference -> continue Quotation preparation
```

Metadata-required fields still produce `needs_input`; approval storage,
confirmation guards, duplicate checks, and Quotation approval were not changed.
No automatic creation was added for `ambiguous` results.

## 12. Verification commands and results

Focused tests:

```bash
./env/bin/python -m unittest \
  apps.mcp_erpnext.mcp_erpnext.tests.test_item_read \
  apps.mcp_erpnext.mcp_erpnext.tests.test_item_service \
  apps.mcp_erpnext.mcp_erpnext.tests.test_entity_selection \
  apps.mcp_erpnext.mcp_erpnext.tests.test_profiles \
  apps.mcp_erpnext.mcp_erpnext.tests.test_tool_registration \
  apps.mcp_erpnext.mcp_erpnext.tests.test_tool_contracts \
  apps.mcp_erpnext.mcp_erpnext.tests.test_interaction_contracts
```

Result: **51 tests passed**.

Full suite:

```bash
./env/bin/python -m unittest discover \
  -s apps/mcp_erpnext/mcp_erpnext/tests -p 'test_*.py'
```

Result: **186 tests passed**. The run emitted the existing Pydantic/FastMCP
`lifespan` incomplete-forward-reference warning and expected HTTP-auth test
warnings; there were no failures.

Catalog and diff checks:

```bash
./env/bin/python apps/mcp_erpnext/scripts/generate_tool_catalog.py
./env/bin/python apps/mcp_erpnext/scripts/generate_tool_catalog.py --check
git diff --check
```

All completed successfully.

## 13. Tool inventory and contract audit

Static `create_mcp(...).list_tools()` inspection reported:

- Sales: **38 tools**. `get_item`, `query_items`, and `aggregate_items` are
  present with object input/output schemas. `audit_tool_contracts(...)` returned
  `[]`.
- Purchase: **21 tools**. All three new Item read tools are absent;
  purchase-enabled `search_items` / `resolve_item` remain present.
  `audit_tool_contracts(...)` returned `[]`.

The generated `docs/TOOLS.md` contains all three new sales contracts and their
`READ` classification.

## 14. Live MCP prompt result

**NOT VERIFIED.** No authenticated Streamable HTTP or stdio MCP client session
was started, and no live Quotation/Item approval was executed. The runtime
metadata inspection and deterministic service tests do not prove authenticated
transport, agent tool routing, persistence, PDF/pricing behavior, or the full
Quotation conversation.

The exact live prompt to verify later is:

```text
create a quotation for AEVIAS HEALTHCARE PRIVATE LIMITED customer
with item Web Development Services qty 1 rate 500 using mcp
```

No Coordinator/Sales Agent instruction delta is claimed because live routing
was not exercised.

## 15. Known limitations and deferred capabilities

This task does not add stock/warehouse or valuation analytics, Item Price or
Pricing Rule lookup, transaction pricing, taxes, serial/batch information,
barcode/supplier child-table queries, variant/template creation, custom-field
auto-exposure, Item update/delete lifecycle, semantic/vector search, or
Purchase-profile field-aware Item reads.

## 16. Safety confirmation

No database records were created, updated, submitted, cancelled, or deleted.
No migration, build, restart, dependency, identity, approval-policy, HTTP
transport, LibreChat, Frappe core, or ERPNext core change was made. The only
runtime operation was read-only metadata inspection; all behavior verification
was local unit/schema testing.

## 17. Exact next task recommendation

Stop after this task. The exact next task is **Task 21 - Coordinator/Sales Agent
Tool-Selection Routing Audit**. Do not implement Supplier reads or Purchase
Item field-aware reads as part of Task 20.
