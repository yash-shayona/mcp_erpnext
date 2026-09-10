# Customer Field-Aware Read / Query Implementation Report

## 1. Final status

**PARTIAL** — the read/query foundation, focused tests, full regression suite,
native Frappe query checks, registered schemas, and contract audit pass. Live
MCP conversational prompts were not run because no authenticated MCP client
session was started; they are explicitly **NOT VERIFIED** below.

## 2. Source files inspected

- `mcp_erpnext/contracts/selling/sales_order_read.py`
- `mcp_erpnext/services/selling/sales_order_read.py`
- `mcp_erpnext/tools/selling/sales_order_read.py`
- `mcp_erpnext/tests/test_sales_order_read.py`
- `mcp_erpnext/config/masters/customer.py`
- `mcp_erpnext/contracts/masters/resolution.py`
- `mcp_erpnext/services/masters/customer.py`
- `mcp_erpnext/services/common/entity_resolution.py`
- `mcp_erpnext/tools/masters/customer.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/audit.py`
- `mcp_erpnext/profiles/sales.py` and `mcp_erpnext/profiles/purchase.py`
- `mcp_erpnext/tools/__init__.py`
- profile, registration, contract, and Sales Order read tests
- `scripts/generate_tool_catalog.py` and generated `docs/TOOLS.md`
- ERPNext Customer DocType source and merged site metadata
- Frappe v16 query-builder validation and native aggregation examples

## 3. Installed version inspected

The inspected bench checkout reports Frappe `v16.33.1` and ERPNext `v16.34.2`.
Merged metadata was inspected read-only on `praveg.localhost` with:

```bash
./env/bin/bench --site praveg.localhost execute frappe.get_meta --args '["Customer"]'
```

## 4. Customer metadata evidence

The merged `Customer` metadata contains no selected custom fields. The
following standard fields were verified in the runtime metadata and the
installed ERPNext source. `name`, `owner`, `creation`, and `modified` are
Frappe system columns rather than entries in `meta.fields`.

| fieldname | label | fieldtype | options/link target | standard/custom | fetch_from | queryable/list-column | projection | filter | sort | group | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `name` | Name | system column | — | standard | — | yes | yes | yes | yes | no | Exact Customer identity and stable tie-breaker. |
| `customer_name` | Customer Name | Data | — | standard | — | yes | yes | yes | yes | no | Human-readable identity and exact name filter. |
| `customer_type` | Customer Type | Select | Company / Individual / Partnership | standard | — | yes | yes | yes | yes | yes | Verified business classification. |
| `customer_group` | Customer Group | Link | Customer Group | standard | — | yes | yes | yes | yes | yes | Required group filtering and grouping. |
| `territory` | Territory | Link | Territory | standard | — | yes | yes | yes | yes | yes | Required territory filtering and grouping. |
| `email_id` | Email Id | Read Only | Email | standard | `customer_primary_contact.email_id` | yes | yes | yes | no | Deterministic structured email lookup; native projection/filter succeeded. |
| `mobile_no` | Mobile No | Read Only | Mobile | standard | `customer_primary_contact.mobile_no` | yes | yes | yes | no | Deterministic structured mobile lookup; native projection is supported. |
| `tax_id` | Tax ID | Data | — | standard | — | yes | yes | yes | no | Verified standard tax identifier without assuming site GST fields. |
| `disabled` | Disabled | Check | — | standard | — | yes | yes | yes | yes | Explicit active/disabled reads; no resolver-only active filter. |
| `is_frozen` | Is Frozen | Check | — | standard | — | yes | yes | no | yes | Explicit account-freeze grouping/read. |
| `account_manager` | Account Manager | Link | User | standard | — | yes | yes | yes | no | Explicit owner-of-account filtering. |
| `default_currency` | Billing Currency | Link | Currency | standard | — | yes | yes | no | no | Safe compact Customer default useful for reads. |
| `default_price_list` | Default Price List | Link | Price List | standard | — | yes | yes | no | no | Safe compact Customer default useful for reads. |
| `owner` | Owner | system column | User | standard | — | yes | yes | yes | no | Explicit Frappe record-owner filter/projection. |
| `creation` | Creation | system column | DateTime | standard | — | yes | yes | yes | no | Date-range and latest-record queries. |
| `modified` | Modified | system column | DateTime | standard | — | yes | yes | yes | no | Date-range and freshness queries. |

The full exposed projection was executed through native
`frappe.get_list(..., ignore_permissions=False)`. The exact email filter for
`customer@example.com` returned no rows without error. A grouped
Customer count also succeeded after using Frappe's native dict aggregate form.

## 5. Final allowlists

- Projection: `name`, `customer_name`, `customer_type`, `customer_group`,
  `territory`, `email_id`, `mobile_no`, `tax_id`, `disabled`, `is_frozen`,
  `account_manager`, `default_currency`, `default_price_list`, `owner`,
  `creation`, `modified`.
- Exact filters: all direct fields above except `is_frozen`, plus explicit
  `created_from`, `created_to`, `modified_from`, and `modified_to` ranges.
- Sort: `name`, `customer_name`, `customer_type`, `customer_group`,
  `territory`, `disabled`, `creation`, `modified`.
- Group: `customer_group`, `territory`, `customer_type`, `disabled`.
- Metric: `count` only.
- Pagination: default `20`, maximum `100`, non-negative offset.

The public Pydantic `Literal` values and the service-side allowlists are fixed;
arbitrary field names, operators, SQL fragments, and expressions are not
accepted.

## 6. Files added/changed

Added:

- `mcp_erpnext/contracts/masters/customer_read.py`
- `mcp_erpnext/services/masters/customer_read.py`
- `mcp_erpnext/tools/masters/customer_read.py`
- `mcp_erpnext/tests/test_customer_read.py`
- this report

Changed:

- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/sales.py`
- `mcp_erpnext/services/masters/customer.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- generated `docs/TOOLS.md`

The task document was not modified. Sales Order, Quotation, Purchase Order,
lifecycle, approval, identity, PDF, email, Item, and Supplier implementations
were not changed.

## 7. Final MCP public tool contracts

- `get_customer(customer, fields?)` — exact permission-aware read with compact
  allowlisted projection; `ok`, `not_found`, or typed `error`.
- `query_customers(...)` — exact field filters, projection, bounded pagination,
  deterministic sorting, and `ok` results with count.
- `aggregate_customers(metrics?, ..., group_by?)` — server-side `count`,
  optionally grouped by the four allowlisted fields.

All three are explicit typed non-legacy contracts with published output
schemas and `READ` side-effect metadata.

## 8. Resolver separation

`search_customers` and `resolve_customer` still call the existing
name-oriented resolver with `name`/`customer_name` search fields. The new
`query_customers` path uses exact field equality and is registered only by the
Sales profile. Customer read tools are absent from the Purchase profile.

## 9. Email regression handling

The first incorrect point was Customer name resolution receiving a structured
email. The Customer service now detects only an obvious email-shaped value and
returns `CUSTOMER_STRUCTURED_QUERY_REQUIRED` before calling
`find_candidates`/`resolve_candidate`. The response directs the caller to
`query_customers(email_id=...)`. No shared resolver, Item resolver, or Supplier
resolver was changed, and no email/mobile/tax field was added to fuzzy search.

`query_customers(email_id="customer@example.com")` produces a
native equality filter and, when absent, returns `status=ok`, an empty list,
and `count=0`; it cannot return the unrelated `Components` candidates.

## 10. Permission behavior

- Exact reads use `frappe.get_doc` followed by `doc.has_permission("read")`.
- Lists and aggregates use `frappe.get_list(..., ignore_permissions=False)`.
- No `get_all`, Administrator switch, permission bypass, direct SQL, or raw
  model-provided filter dictionary was introduced.
- The query path does not silently add the resolver's `disabled != 1` filter;
  disabled Customers can be requested explicitly.

## 11. Verification results

Focused and related tests:

```bash
./env/bin/python -m unittest \
  apps.mcp_erpnext.mcp_erpnext.tests.test_customer_read \
  apps.mcp_erpnext.mcp_erpnext.tests.test_sales_order_read \
  apps.mcp_erpnext.mcp_erpnext.tests.test_profiles \
  apps.mcp_erpnext.mcp_erpnext.tests.test_tool_registration \
  apps.mcp_erpnext.mcp_erpnext.tests.test_tool_contracts
```

Result: **30 tests passed** in the final focused run.

Full suite:

```bash
./env/bin/python -m unittest discover \
  -s apps/mcp_erpnext/mcp_erpnext/tests -p 'test_*.py'
```

Result: **173 tests passed**. The run emitted the existing FastMCP/Pydantic
`lifespan` incomplete-forward-reference warning and expected HTTP-auth test
warnings; there were no test failures.

Catalog:

```bash
./env/bin/python apps/mcp_erpnext/scripts/generate_tool_catalog.py
./env/bin/python apps/mcp_erpnext/scripts/generate_tool_catalog.py --check
```

Generation completed and the final `--check` passed. `git diff --check` also
passed.

## 12. Registered schema and audit result

Static registered `tools/list` inspection through `create_mcp(...).list_tools()`
reported:

- Sales: 35 tools; `get_customer`, `query_customers`, and
  `aggregate_customers` are present with object input/output schemas;
  `search_customers` and `resolve_customer` remain present. Audit result: `[]`.
- Purchase: 21 tools; Customer read tools are absent. Audit result: `[]`.

## 13. Live MCP prompt results

**NOT VERIFIED.** No authenticated MCP client session was started, so the
Hindi email prompt and the exact-read/resolver prompts were not executed over
MCP. The read-only bench probes verified the underlying Frappe metadata and
native query paths, not end-to-end MCP identity/transport behavior.

## 14. Limitations and deferred work

This foundation does not expose arbitrary custom fields, linked Contact or
Address rows, Customer 360 analytics, transaction history, CRM relationships,
child-table querying, or Customer writes. `email_id` and `mobile_no` are
denormalized read-only fetch fields; the query reads their stored Customer
values and does not join Contact rows.

## 15. Safety confirmation

No database records were created or changed. No migration, build, restart,
approval-policy, identity, or dependency operation was run. The bench metadata
and query probes were read-only.

## 16. Exact next task recommendation

Stop after this task. Choose **Item Field-Aware Read / Query Foundation** next
only if actual testing evidence requires it. Before that task, compare the
working Customer and Sales Order implementations and extract a common helper
only if both implementations prove the abstraction is stable; do not
pre-generalize this Customer foundation.
