# Confirmed Sales Business-Rule Duplication Removal

Date: 2026-09-12  
Task: 37 - Remove Confirmed Sales Business-Rule Duplication  
Project: `mcp_erpnext`

## 1. Result

Removed the two confirmed MCP copies of ERPNext business rules:

- standalone Sales Invoice preparation no longer reads Selling Settings or
  Customer exception fields to reconstruct prerequisite policy;
- Quotation preparation no longer compares `valid_till` and `transaction_date`
  itself.

MCP still owns typed input normalization, permission-aware entity resolution,
bounded previews, approvals, stale confirmation, and safe public response
shaping. Final persistence remains a normal Frappe insert with permissions and
native validation enabled.

## 2. Native authority and prepare safety

The installed ERPNext source is version `16.34.2`; Frappe is `16.33.1`.

For Sales Invoice, `SalesInvoice.validate()` calls `so_dn_required()` only when
the invoice is not POS or a debit note. The native `so_dn_required()` method
reads Selling Settings and Customer exceptions, then checks each unsaved item
for its native `sales_order` or `delivery_note` link. It returns without work
for returns; the native validation caller excludes POS/debit-note documents,
and the helper itself honors the relevant `is_pos`/`update_stock` item checks.
The public service fixes those mode flags to the standalone non-POS,
non-return Draft workflow and calls this narrow controller seam after native
defaults and calculations. It does not call broad Sales Invoice validation
during prepare because that path also executes the installed India Compliance
and other document hooks.

For Quotation, preparation calls the native controller `doc.validate()` seam.
It reaches ERPNext `Quotation.validate_valid_till()`, which owns the
`valid_till` ordering comparison. The MCP-side comparison was removed. The
direct controller call avoids Frappe's generic `run_method()` dispatch of
configured document-event webhooks and server scripts. Source inspection of
the installed Quotation and India Compliance validation bodies found no
Quotation insert, queue, notification, or external integration; they only
resolve/update the unsaved document state. Final insert remains the
authoritative document-event and persistence boundary.

## 3. Public error behavior

Native Sales Invoice prerequisite failures are classified from the native
exception only to select the existing bounded MCP codes:
`SALES_ORDER_REQUIRED` or `DELIVERY_NOTE_REQUIRED`. The native message and item
identifier are not returned. Other native prerequisite validation failures use
`NATIVE_VALIDATION_FAILED` with a client-neutral message.

Native Quotation validation failures are mapped to
`NATIVE_VALIDATION_FAILED`; traceback and native validation text are not
returned. No approval token is created after either native rejection.

## 4. Files changed for this task

- `mcp_erpnext/services/selling/sales_invoice.py`
- `mcp_erpnext/services/selling/quotation.py`
- `mcp_erpnext/tests/test_sales_invoice.py`
- `mcp_erpnext/tests/test_quotation_service.py`
- this report

No contracts, wrappers, profiles, registries, approval storage, lifecycle
policy, Purchase code, database schema, Frappe core, ERPNext core, or India
Compliance code was changed.

## 5. Regression coverage

Focused tests cover:

- native Sales Invoice prerequisite invocation and non-persisting prepare;
- bounded Sales Order and Delivery Note prerequisite results;
- native failure during confirmation without insert;
- bounded unknown native validation failure;
- Quotation after-date, same-date, and before-date behavior;
- proof that the Quotation before-date decision comes from the native seam;
- final Draft insertion and existing permission/approval behavior.

The installed source was also checked for Sales Invoice return/POS/item-level
prerequisite behavior. The public standalone Sales Invoice contract fixes POS,
return, debit-note, and update-stock flags to the non-POS, non-return Draft
workflow, so those modes are not model-facing inputs.

## 6. Verification

Focused tests passed:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_sales_invoice \
  mcp_erpnext.tests.test_quotation_service
```

Result: 25 tests passed.

The full app suite also passed:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
```

Result: 271 tests passed. The run emitted the existing Python 3.14/pydantic
settings warning, HTTP authentication test warnings, and the existing mocked
India Compliance Item diagnostic; all tests passed.

Additional checks passed:

- AST parsing of the changed services/tests;
- `scripts/generate_tool_catalog.py --check`;
- `git diff --check`.

## 7. Known boundaries

No live MCP call or database write was performed. Actual India Compliance hook
execution and live Sales Invoice/Quotation creation remain runtime verification
boundaries. Approval state remains process-local as in the existing design.
