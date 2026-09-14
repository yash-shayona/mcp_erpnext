# Sales Invoice to Delivery Note Native Conversion Report

This implementation adds the Sales-profile pair
`prepare_sales_invoice_to_delivery_note` and
`confirm_sales_invoice_to_delivery_note`.

## 1. Current MCP implementation inspected

The existing Sales Order to Delivery Note, Delivery Note to Sales Invoice, and
Sales Order to Sales Invoice flows were inspected, along with their contracts,
wrappers, approval handling, fingerprint helper, registry, profile
registration, REST operation registry, tests, and generated tool catalog.
They establish the implementation pattern used here: exact source loading,
normal permission checks, native mapping, bounded preview, shared approval,
fresh remapping during confirmation, stale fingerprint protection, and Draft-
only insertion.

## 2. Installed ERPNext source inspected

The installed ERPNext source is authoritative for this checkout. The inspected
files were:

- `erpnext/accounts/doctype/sales_invoice/sales_invoice.py`
- `erpnext/accounts/doctype/sales_invoice/sales_invoice.js`
- `frappe/model/mapper.py`

The installed Desk logic exposes Delivery Note creation only for a submitted
non-return invoice with `update_stock != 1` and an eligible remaining row. The
mapper itself remains authoritative for row-level eligibility.

## 3. Exact native mapper used

The service calls:

```python
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note

target = make_delivery_note(source_name, target_doc=None)
```

No Sales Order mapper, caller-selected mapper arguments, manual remaining-
quantity calculation, or manual source-link reconstruction is used.

## 4. Source eligibility behavior

Preparation and confirmation require an authenticated user, a readable exact
Sales Invoice, a submitted source, and Delivery Note create permission. Return
invoices and invoices with `update_stock = 1` return bounded
`SOURCE_NOT_ELIGIBLE` results. A native mapped target with no items returns
`NO_MAPPABLE_ITEMS`; it is never inserted.

## 5. Files changed

Added:

- `mcp_erpnext/contracts/selling/sales_invoice_to_delivery_note.py`
- `mcp_erpnext/services/selling/sales_invoice_to_delivery_note.py`
- `mcp_erpnext/tools/selling/sales_invoice_to_delivery_note.py`
- `mcp_erpnext/tests/test_sales_invoice_to_delivery_note.py`

Updated:

- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/selling/__init__.py`
- `mcp_erpnext/remote_operations.py`
- `mcp_erpnext/tools/__init__.py`
- focused contract, registration, profile, and REST tests
- generated `docs/TOOLS.md`

No lifecycle, standalone Delivery Note, Purchase, Accounts, existing
conversion, read, PDF, or email implementation was changed.

## 6. Public input/output contracts

Prepare accepts exactly the non-empty `sales_invoice` identity. Confirm accepts
exactly `approval_token` and `confirm`; it cannot change source, rows,
quantities, warehouse, customer, or company. Extra fields are forbidden by the
existing public contract base model.

The output is a typed approval-shaped prepare result or bounded error, and a
typed created Draft Delivery Note result or bounded error. Full ERPNext
documents and mapper internals are not exposed.

## 7. Preview fields

The bounded preview includes source identity/status/customer/company/date/
currency/stock-route flags/totals, and the native target customer/company/date/
currency, mapped item quantity/UOM/rate/amount/warehouse, native
`against_sales_invoice`/`si_detail` links, native Sales Order links when
present, packed-item count, serial/batch requirement summary, totals, and a
stock/accounting submission warning.

## 8. Approval and fingerprint behavior

Prepare stores the source identity, preview projection, and stable fingerprint
in the shared site/user/action-bound ApprovalStore. Confirmation atomically
claims the approval, reloads the source, applies the same eligibility checks,
calls the native mapper again, rebuilds the preview, and compares the
fingerprint before insertion. Native `delivery_note.posting_time` is excluded
from the fingerprint using the established narrow conversion rule; source
state, rows, quantities, links, warehouse, and totals remain fingerprinted.

Successful confirmation inserts with `ignore_permissions=False`,
`ignore_links=False`, and `ignore_mandatory=False`, commits the transaction,
returns `docstatus = 0`, and never calls `submit()`.

## 9. Direct/REST parity

The direct MCP wrapper and fixed REST handlers both call the same service
functions. REST validates the same typed prepare and confirm models and does
not expose generic service/function dispatch.

## 10. Tests executed

Passed:

- focused new, conversion, contract, registration, profile, REST, approval,
  fingerprint, and Sales Invoice read tests: **106 tests, OK**
- full tool catalog generation and `scripts/generate_tool_catalog.py --check`
- `git diff --check`

Full discovery was also executed:

```text
Ran 350 tests
FAILED (failures=1, errors=4)
```

The one failure and four errors are existing unrelated approval-policy and
India Compliance fixture failures in Customer, Item, Purchase Order,
Quotation, and email tests. The new conversion and all named conversion/
registration/REST tests pass.

The first requested test list also named
`mcp_erpnext.tests.test_delivery_note_read`, but that module does not exist in
this checkout. The available Delivery Note read implementation was preserved;
the remaining available regression modules were run successfully.

## 11. Remaining limitations

This remains a normal-delivery conversion only. Return invoices, standalone
Delivery Note creation, manual row/quantity/warehouse overrides,
serial/batch allocation, Pick List, Packing Slip, Shipment, Delivery Trip,
and automatic submit remain unsupported by design.

## 12. Live verification status

No live authenticated MCP/REST call, database insert, queue execution, or
submitted ERPNext Delivery Note verification was performed. The implementation
is verified by source inspection, typed registration, mocked service tests,
REST handler tests, generated catalog checks, and static diff validation.
