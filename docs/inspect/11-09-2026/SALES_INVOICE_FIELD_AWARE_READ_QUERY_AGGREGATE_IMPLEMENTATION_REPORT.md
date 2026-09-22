# Sales Invoice Field-Aware Read / Query / Aggregate Implementation Report

## 1. Scope and current-tree evidence

Task 33 was implemented in the nested Git checkout at `apps/mcp_erpnext`.
The checkout already contained unrelated Task 30–32 work and reports, including
Sales Order query naming, the shared aggregate foundation, and Quotation read
capability. Those changes were preserved.

Inspected before editing:

- `mcp_erpnext/services/common/read.py`
- `mcp_erpnext/services/common/aggregate.py`
- `mcp_erpnext/services/selling/sales_invoice.py`
- `mcp_erpnext/services/selling/quotation_read.py`
- `mcp_erpnext/services/selling/sales_order_read.py`
- `mcp_erpnext/contracts/read.py`
- `mcp_erpnext/contracts/selling/quotation_read.py`
- `mcp_erpnext/contracts/selling/sales_order_read.py`
- `mcp_erpnext/tools/read.py`
- `mcp_erpnext/tools/selling/quotation_read.py`
- `mcp_erpnext/tools/selling/sales_order_read.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/sales.py`
- relevant registration, profile, contract, read, aggregate, and quotation tests
- `scripts/generate_tool_catalog.py` and `docs/TOOLS.md`

Before Task 33, `get_sales_invoice` and `search_sales_invoices` were generic
wrappers over `services/common/read.py`. The old exact read returned a compact
summary including child items, while the old search accepted only the common
`party`, `status`, `docstatus`, date range, and limit fields. Sales Invoice
creation and confirmation remained in `services/selling/sales_invoice.py` and
were not mixed into this read implementation.

## 2. ERPNext metadata and accounting semantics

The checked-out source version constants are:

- Frappe `16.33.1` from `apps/frappe/frappe/__init__.py`;
- ERPNext `16.34.2` from `apps/erpnext/erpnext/__init__.py`.

Runtime metadata was attempted with:

```bash
./env/bin/bench --site praveg.localhost execute frappe.get_meta --args '["Sales Invoice"]'
```

It succeeded and returned the Sales Invoice metadata. The installed source
JSON was also inspected at
`apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.json`,
with controller behavior inspected in
`apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py`.

Important confirmed fields include `customer`, `customer_name`, `company`,
`posting_date`, `due_date`, `status`, `docstatus`, `is_return`,
`return_against`, `is_debit_note`, `currency`, `grand_total`, `net_total`,
`outstanding_amount`, `paid_amount`, `base_paid_amount`, `customer_group`,
`territory`, `sales_partner`, `po_no`, `po_date`, `owner`, `creation`, and
`modified`, as well as the selected pricing and total fields in the public
allowlist.

The controller derives status from `docstatus`, due-date/overdue state,
outstanding amount, return state, credit-note linkage, and internal transfer
state. The typed status policy therefore uses the installed values rather than
inventing a parallel status model.

`outstanding_amount` is the stored ERPNext invoice outstanding value and is
used directly for filtering and aggregation. The controller's `set_paid_amount`
calculates `paid_amount` from the invoice's payment rows and resets it for
non-POS returns; it is exposed as a selectable document field but is not
aggregated as total payments received. Payment Entry allocation and Accounts
Receivable reconciliation remain outside this task.

## 3. Public field and behavior policy

The deliberate Sales Invoice field allowlist contains identity, lifecycle,
return/credit-note context, currency/pricing, commercial totals, outstanding
state, selected accounting dimensions, purchase-order reference, stock flag,
and audit fields. Child tables, taxes, payment schedules, advances, packed
items, addresses, terms, print data, pricing-rule internals, and other support
fields remain excluded.

Exact-read default projection:

```text
name, customer, customer_name, posting_date, due_date, docstatus, status,
currency, grand_total, outstanding_amount, is_return, return_against
```

Query default projection:

```text
name, customer, customer_name, posting_date, due_date, status, currency,
grand_total, outstanding_amount
```

Query filters include exact name/customer/customer name, company, status,
docstatus, currency, return/debit-note state and reference, selected pricing
and accounting dimensions, owner, posting-date and due-date ranges, creation
and modified ranges, and signed ranges for grand total, net total, and
outstanding amount. Signed numeric ranges preserve the negative values used by
returns instead of rejecting or rewriting them.

Sort fields are the bounded identity, customer, posting/due date, status,
company/currency, grand-total/outstanding, and audit fields. Every query adds
document-name tie-breaking. Pagination uses the existing limit/offset pattern;
`count` is the number of returned page rows.

Aggregate metrics are:

```text
count
sum_grand_total, avg_grand_total, min_grand_total, max_grand_total
sum_outstanding_amount
sum_net_total
sum_total_qty
```

Grouping is allowlisted to customer/customer name, status, company, currency,
return state, posting/due date, customer group, territory, and docstatus.
Transaction-currency monetary metrics automatically include currency context
and group by currency unless currency is already the requested grouping.
No unlabeled cross-currency monetary total is returned.

Returns and credit notes remain visible and filterable through `is_return`,
`is_debit_note`, `return_against`, status, and stored monetary values. Aggregate
results do not silently sign-flip or hide return rows; negative stored amounts
are preserved.

## 4. Files changed for Task 33

- `mcp_erpnext/contracts/selling/sales_invoice_read.py` — typed field,
  filter, projection, query, aggregate, and output contracts.
- `mcp_erpnext/services/selling/sales_invoice_read.py` — permission-aware
  exact read, query, filter, deterministic sorting, and aggregate service.
- `mcp_erpnext/tools/selling/sales_invoice_read.py` — typed MCP wrappers.
- `mcp_erpnext/contracts/selling/__init__.py` — read-contract exports.
- `mcp_erpnext/contracts/registry.py` — active typed tool declarations.
- `mcp_erpnext/profiles/sales.py` — Sales-profile registration.
- `mcp_erpnext/tools/read.py` — removed the old Sales Invoice generic wrappers;
  Purchase generic read registration remains.
- `mcp_erpnext/tests/test_sales_invoice_read.py` — focused service/contract
  coverage.
- `mcp_erpnext/tests/test_tool_registration.py` — active inventory assertion.
- `mcp_erpnext/tests/test_profiles.py` — Sales-profile assertions.
- `mcp_erpnext/tests/test_tool_contracts.py` — typed read schema assertions.
- `docs/TOOLS.md` — regenerated active catalog.

The implementation reuses `services/common/aggregate.py` from Task 31 for
Frappe v16 dictionary aggregate fields, permission-aware execution, grouping,
and result shaping. No duplicate aggregate engine was added and the common
helper was not changed.

## 5. Result and boundary

The active Sales Invoice read surface is now exactly:

```text
get_sales_invoice
query_sales_invoices
aggregate_sales_invoices
```

The old deterministic `search_sales_invoices` wrapper is absent from active
registration and the generated catalog. Historical task/audit documents may
still mention it as prior architecture. No Sales Invoice Item query or
aggregate tool was added. The Sales Invoice write/approval/lifecycle flow was
not changed.

All reads preserve Frappe identity and permissions:

- exact reads use `frappe.get_doc` and `doc.has_permission("read")`;
- queries use `frappe.get_list(..., ignore_permissions=False)`;
- aggregates use the shared executor, which also forwards
  `ignore_permissions=False`.

## 6. Verification

Focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_sales_invoice_read \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_tool_contracts
```

Result: **26 tests passed**.

Full suite command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ../../env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
```

Result: **258 tests passed**. Existing authentication warnings and the mocked
India Compliance error-log path appeared, but no test failed.

Additional checks:

- `scripts/generate_tool_catalog.py` completed;
- `scripts/generate_tool_catalog.py --check` passed;
- `git diff --check` passed;
- AST parsing of all three new Python modules passed without creating bytecode.

Live service/MCP verification was not completed. The metadata command could
read the Sales Invoice DocType, but `bench --site praveg.localhost list-apps`
failed while connecting to MariaDB with `Can't create TCP/IP socket (1)`, and
the environment's earlier live checks report that `mcp_erpnext` is not
installed on that site. No database, service, cache, or server state was
changed by this task.

The generic `bench version` command was also blocked by an unrelated Git safe
directory error in the installed `india_compliance` app; source version
constants above remain confirmed from the checked-out Frappe/ERPNext code.

## 7. Recommendations

Do not implement the next DocType solely for symmetry. A future scoped task
could add Sales Invoice Item analytics or Payment Entry/Accounts Receivable
capabilities if business requirements justify them, with separate accounting
semantics and currency/permission policy.
