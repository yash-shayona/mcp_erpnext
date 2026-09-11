# Quotation Field-Aware Read / Query / Aggregate Implementation Report

## 1. Scope and result

Task 32 upgrades the Sales-profile Quotation header read surface to:

```text
get_quotation
query_quotations
aggregate_quotations
```

The former deterministic public `search_quotations` registration was removed.
No Quotation Item query or aggregate tool was added.

## 2. Files inspected

The implementation inspection covered:

- `mcp_erpnext/services/common/read.py`
- `mcp_erpnext/services/common/aggregate.py`
- `mcp_erpnext/services/selling/quotation.py`
- `mcp_erpnext/services/selling/sales_order_read.py`
- `mcp_erpnext/services/masters/customer_read.py`
- `mcp_erpnext/services/masters/item_read.py`
- the corresponding Customer, Item, Sales Order, and generic existing-document contracts and wrappers;
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/sales.py`
- `mcp_erpnext/tests/`
- `scripts/generate_tool_catalog.py`
- `docs/TOOLS.md` and active contract architecture documentation.

The previous Quotation read implementation was in `services/common/read.py`.
Both `get_quotation` and `search_quotations` were thin wrappers over its
generic compact document reader. Exact reads returned a generic summary and
the compact reader included selected child items; list reads used fixed fields,
Customer-only quotation filtering, a fixed date/name sort, and a bounded limit.

## 3. Working-tree context

The Bench root is not a Git checkout. The Git checkout is
`apps/mcp_erpnext`, on branch `master`.

Before this task, the checkout already contained unrelated/in-scope prior-task
changes for Sales Order naming normalization, the shared aggregate foundation,
Customer/Item reads, and their tests/docs. Those changes were preserved. The
initial dirty tree also contained the Task 30, Task 31, and Task 32 task/report
documents and the files changed by Tasks 30/31. This report does not attribute
those pre-existing changes to Task 32.

## 4. ERPNext/Frappe source and metadata inspection

The installed source reports:

- Frappe `16.33.1` from `apps/frappe/frappe/__init__.py`;
- ERPNext `16.34.2` from `apps/erpnext/erpnext/__init__.py`.

The installed ERPNext fallback metadata was inspected in
`apps/erpnext/erpnext/selling/doctype/quotation/quotation.json` and the
controller in `quotation.py`. Confirmed header fields include:
`quotation_to`, `party_name`, `customer_name`, `transaction_date`, `valid_till`,
`order_type`, `company`, `currency`, `conversion_rate`, `selling_price_list`,
`price_list_currency`, `total_qty`, `base_total`, `base_net_total`, `total`,
`net_total`, `base_total_taxes_and_charges`, `total_taxes_and_charges`,
`base_grand_total`, `grand_total`, `additional_discount_percentage`,
`discount_amount`, `referral_sales_partner`, `customer_group`, `territory`,
and `status`. `docstatus` is the standard Frappe document field.

Runtime metadata was not available. The read-only command
`./env/bin/bench --site praveg.localhost execute frappe.get_meta --args '["Quotation"]'`
reached the Bench/Frappe execution path but failed while opening the database
socket with `MySQLdb.OperationalError: (2004, "Can't create TCP/IP socket (1)")`.
The allowlists therefore use the installed ERPNext source/JSON fallback; no
runtime field was auto-exposed.

## 5. Public Quotation field policy

The deliberately allowlisted output fields are:

```text
name, quotation_to, party_name, customer_name,
transaction_date, valid_till, order_type, company, docstatus, status,
currency, conversion_rate, selling_price_list, price_list_currency, total_qty,
base_total, base_net_total, total, net_total, base_grand_total, grand_total,
base_total_taxes_and_charges, total_taxes_and_charges,
additional_discount_percentage, discount_amount, referral_sales_partner,
customer_group, territory, owner, creation, modified
```

These cover identity, dates, lifecycle, commercial totals and context, and
the established audit fields. Large text, child tables, address/contact
display fields, tax-breakup text, pricing-rule internals, print settings,
workflow-support fields, and other low-value/internal fields remain excluded.

The default exact-read projection is:

```text
name, quotation_to, party_name, customer_name, transaction_date, valid_till,
docstatus, status, currency, grand_total
```

The default query projection is the bounded business-list projection:

```text
name, party_name, customer_name, transaction_date, valid_till, status,
currency, grand_total
```

## 6. Query filters and sorting

`query_quotations` supports allowlisted exact header filters for party identity,
party type, customer display name, status/docstatus, company, order type,
currency/price-list context, sales partner, customer group, territory, owner,
and exact quotation name. It also supports transaction-date, valid-till,
creation, and modified ranges plus grand-total, net-total, and total-quantity
minimum/maximum ranges.

The same `_filters()` service helper is used by `query_quotations` and
`aggregate_quotations`, so shared filters have the same meaning. DateTime
upper bounds for `creation` and `modified` use an exclusive next-day endpoint
to include the complete requested end date.

Allowlisted sort fields are name, party/customer display identity, transaction
date, valid-till, order type, status, company, grand total, net total, total
quantity, creation, and modified. Every sort adds `name` in the requested
direction as a deterministic tie-breaker. Query `count` is the number of rows
returned in the requested page.

## 7. Aggregate policy and currency behavior

The approved metrics are:

```text
count
sum_grand_total
avg_grand_total
min_grand_total
max_grand_total
sum_net_total
sum_total_qty
```

Approved group fields are `quotation_to`, `party_name`, `customer_name`,
`status`, `company`, `currency`, `order_type`, `customer_group`, `territory`,
and `transaction_date`.

Monetary metrics use the transaction-currency fields and automatically include
`currency` in the aggregate grouping unless the caller already groups by
currency. This prevents an unlabeled cross-currency monetary total. A caller
may also filter to a specific currency using the shared `currency` filter.

Metric field construction, grouping assembly, permission-aware execution, and
result shaping reuse `services/common/aggregate.py`. Standard metrics use the
Frappe v16 dictionary representation; no raw SQL-style aggregate strings were
introduced.

## 8. Implementation details and changed files

Task 32 added:

- `mcp_erpnext/contracts/selling/quotation_read.py` — typed field, filter,
  query, aggregate, and output contracts;
- `mcp_erpnext/services/selling/quotation_read.py` — Quotation-specific
  allowlists, shared filter semantics, exact read, query, and aggregate logic;
- `mcp_erpnext/tools/selling/quotation_read.py` — thin typed MCP wrappers;
- `mcp_erpnext/tests/test_quotation_read.py` — focused service/contract tests.

Task 32 updated:

- `mcp_erpnext/contracts/registry.py`;
- `mcp_erpnext/contracts/selling/__init__.py`;
- `mcp_erpnext/profiles/sales.py`;
- `mcp_erpnext/tools/read.py` to remove the old Quotation registrations;
- `mcp_erpnext/tests/test_tool_registration.py`;
- `mcp_erpnext/tests/test_profiles.py`;
- `mcp_erpnext/tests/test_tool_contracts.py`;
- `docs/TOOLS.md`, generated from the registered inventory;
- `docs/architecture/MCP_TOOL_CONTRACT_ARCHITECTURE.md` to remove the
  quotation capability from the future-tool examples.

`services/common/aggregate.py` was not changed by Task 32; it is reused as
required by Task 31.

`get_quotation` now uses `frappe.get_doc("Quotation", name)` followed by the
document's `has_permission("read")` check and returns only the requested
allowlisted projection. `query_quotations` uses permission-aware
`frappe.get_list(..., ignore_permissions=False)` with typed projection,
filters, deterministic ordering, and pagination. `aggregate_quotations` uses
the same permission-aware list seam through the shared aggregate executor.

## 9. Registration and boundaries

The active Sales profile now contains all three new names:

```text
get_quotation
query_quotations
aggregate_quotations
```

`search_quotations` is absent from active registration and generated catalog.
No public generic document tool was introduced, and no `query_quotation_items`
or `aggregate_quotation_items` tool was added.

## 10. Verification

Focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_quotation_read \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_tool_contracts
```

Result: **26 tests passed**.

Catalog and whitespace verification:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
git diff --check
```

Result: catalog generation/check and `git diff --check` passed. The generator
emitted the existing Python 3.14 `sys.prefix` warning and an existing
Pydantic `lifespan` incomplete-forward-reference warning; neither failed the
commands.

Full regression verification:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
```

Result: **249 tests passed**. The suite also emitted the expected existing
HTTP-auth warning and the logged Item HSN failure-path exception used by its
regression test; the process exited successfully.

The implementation uses the source-level fallback for metadata. Authenticated
live Quotation reads and aggregates were not verified because the target site's
database socket was unavailable, so this report makes no live-data or live
permission claim.

## 11. Limitations and next task

This task does not implement Quotation Item analytics, Sales Invoice
field-aware reads, Purchase Order aggregates, write/lifecycle changes,
conversion changes, approval changes, or runtime-metadata-driven exposure.

The exact next task is Task 33: inspect and implement the Sales Invoice
field-aware `get_sales_invoice`, `query_sales_invoices`, and
`aggregate_sales_invoices` capability, reusing the shared aggregate foundation
and applying accounting-specific field and currency semantics.
