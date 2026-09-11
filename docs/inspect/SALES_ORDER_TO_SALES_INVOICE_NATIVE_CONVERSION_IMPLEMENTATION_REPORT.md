# Sales Order to Sales Invoice Native Conversion Implementation Report

Date: 2026-09-11  
Task: 27 - Sales Order -> Sales Invoice Native Conversion Foundation  
Project: `mcp_erpnext`  
Profile: `sales`

## Result

Implemented exactly two new Sales-profile MCP tools:

```text
prepare_sales_order_to_sales_invoice
confirm_sales_order_to_sales_invoice
```

The workflow accepts one exact submitted Sales Order, calls ERPNext's
installed native mapper, returns a bounded effective Draft Sales Invoice
preview, binds that projection to the existing one-shot approval store, then
reloads and re-maps the source during confirmation before inserting one Draft
Sales Invoice with normal Frappe permissions.

No Sales Invoice standalone creation, read/search, PDF/email, lifecycle,
Payment Entry, Delivery Note conversion, return, POS, or generic editing
capability was added.

## Files inspected

The existing conversion and governance paths inspected were:

* `mcp_erpnext/contracts/selling/quotation_to_sales_order.py`
* `mcp_erpnext/services/selling/quotation_to_sales_order.py`
* `mcp_erpnext/tools/selling/quotation_to_sales_order.py`
* `mcp_erpnext/contracts/selling/__init__.py`
* `mcp_erpnext/contracts/registry.py`
* `mcp_erpnext/approvals.py`
* `mcp_erpnext/runtime.py`
* `mcp_erpnext/observability.py`
* `mcp_erpnext/profiles/sales.py`
* `mcp_erpnext/tools/__init__.py`
* `mcp_erpnext/tests/test_quotation_to_sales_order.py`
* `mcp_erpnext/tests/test_tool_registration.py`
* `mcp_erpnext/tests/test_profiles.py`
* `mcp_erpnext/tests/test_tool_contracts.py`
* `scripts/generate_tool_catalog.py`
* `apps/erpnext/erpnext/selling/doctype/sales_order/sales_order.py`
* `apps/frappe/frappe/model/mapper.py`
* `docs/inspect/SALES_INVOICE_NATIVE_FLOW_AUDIT.md`

## Files changed

Implementation files:

* `mcp_erpnext/contracts/selling/sales_order_to_sales_invoice.py`
* `mcp_erpnext/services/selling/sales_order_to_sales_invoice.py`
* `mcp_erpnext/tools/selling/sales_order_to_sales_invoice.py`
* `mcp_erpnext/contracts/selling/__init__.py`
* `mcp_erpnext/contracts/registry.py`
* `mcp_erpnext/tools/__init__.py`
* `mcp_erpnext/tests/test_sales_order_to_sales_invoice.py`
* `mcp_erpnext/tests/test_tool_registration.py`
* `mcp_erpnext/tests/test_profiles.py`
* `mcp_erpnext/tests/test_tool_contracts.py`
* `docs/TOOLS.md` (generated)
* this report

`mcp_erpnext/profiles/sales.py` was inspected but did not require a direct
edit: its existing `register_sales_tools()` path is the Sales-only registration
boundary, and the new pair is registered there.

## Existing architecture reused

The implementation follows the Quotation -> Sales Order conversion pattern for:

* typed public input/output models and root-shaped discriminated results;
* thin FastMCP wrappers using `execute_tool_with_context`;
* exact source loading and explicit read/create permission checks;
* lazy native ERPNext mapper import;
* bounded preview projection;
* process-local `approvals.create()` and `claim_for_confirm_write()`;
* action/site/user-bound, single-use confirmation;
* confirmation-time source reload and native re-map;
* stale fingerprint rejection;
* normal `insert()` flags, commit-after-success, rollback-on-failure;
* safe public error envelopes and approval interaction directives.

The Sales Invoice conversion intentionally does not reuse the quotation
conversion's prepare-time `run_method("validate")`. Task 26 documented that
full Sales Invoice validation can mutate unsaved state in some branches; the
native mapper's audited defaulting/projection boundary is used during prepare,
and final insert performs the normal native validation lifecycle.

## Installed ERPNext mapper

The installed ERPNext v16 callable is:

```python
erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice(
    source_name,
    target_doc=None,
    args=None,
    ignore_permissions=False,
)
```

Installed path and lines:
`apps/erpnext/erpnext/selling/doctype/sales_order/sales_order.py:1355-1561`.

The implementation calls it with `target_doc=None`, bounded empty `args={}`,
and `ignore_permissions=False`. The audited native behavior is:

* submitted Sales Invoice quantities are aggregated by `so_detail` at
  `:1388-1404`;
* returns/deliveries and already-billed quantities determine pending quantity
  at `:1350-1352` and `:1406-1413`;
* native target defaults, account resolution, tax/total calculation,
  serial/batch field setup, and company address resolution run at
  `:1421-1442`;
* Sales Order Item `name -> so_detail` and `parent -> sales_order` lineage is
  mapped at `:1522-1528`;
* source docstatus validation and normal mapper permission checks are part of
  `get_mapped_doc` at `:1510-1550`;
* optional native payment-schedule handling runs at `:1555-1559`.

No native quantity, tax, pricing, account, GST, return, stock, or lineage
algorithm was copied into `mcp_erpnext`.

## Prepare flow

1. Resolve the current authenticated Frappe user; Guest is rejected.
2. Load exactly one `Sales Order` with normal permissions.
3. Require source read permission, `docstatus == 1`, and target `Sales Invoice`
   create permission.
4. Call the installed native mapper with permission bypass disabled.
5. Reject a non-Draft mapped target or an empty native item result with a safe
   error and create no approval.
6. Build a bounded source/target projection and SHA-256 fingerprint.
7. Create the existing shared approval containing only serializable source
   identity, projection, and fingerprint data.

The projection includes source status, party/company/currency/dates/totals,
source row names and billing/delivery/return state, mapped invoice customer,
company, dates, currency, price list, debit account, addresses, item amounts
and quantities, `sales_order`, `so_detail`, bounded taxes, payment schedule,
and totals.

## Confirmation flow

Confirmation first calls the shared atomic
`claim_for_confirm_write()` guard. It therefore rejects expired, consumed,
wrong-user, wrong-site, wrong-action, untrusted, or otherwise unavailable
tokens before any write. A declined confirmation consumes/cancels the pending
operation through the existing store.

After claiming, confirmation reloads the exact source, repeats read/create
permission and submitted-source checks, calls the same native mapper again,
requires remaining native item rows, rebuilds the same projection/fingerprint,
and returns `STALE_CONFIRMATION` on mismatch. This detects source changes and
another submitted Sales Invoice changing remaining quantity; `modified` is not
the only stale signal because the mapped target quantity/lineage/totals are in
the projection.

Only the freshly mapped confirmation target is inserted:

```python
target.insert(
    ignore_permissions=False,
    ignore_links=False,
    ignore_mandatory=False,
)
frappe.db.commit()
```

Insert failure rolls back and returns a safe error. The capability never calls
`submit()`, GL APIs, stock-ledger APIs, Payment Entry creation, e-Invoice or
E-Waybill APIs, or Delivery Note creation. The returned document is explicitly
`Sales Invoice` with `docstatus == 0`.

## Permission and optional-app behavior

No Administrator fallback, client user override, approval-mode argument,
`ignore_permissions=True` mapper call, direct SQL write, arbitrary target
field passthrough, or second approval store was introduced.

The new core contract imports no India Compliance module. When India
Compliance is installed, the native Frappe/ERPNext mapper and final insert
remain the hook boundaries, so installed `after_mapping` and normal validation
hooks can participate. When India Compliance is absent, the Task 27 module has
no optional-app import dependency. No external GST API is called during
prepare. The installed audit records India Compliance submit-time enqueue
behavior separately; Task 27 does not submit the Draft.

## Tests and commands

Observed results:

* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest mcp_erpnext.tests.test_sales_order_to_sales_invoice mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_profiles mcp_erpnext.tests.test_tool_contracts` — **24 passed**.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest mcp_erpnext.tests.test_sales_order_to_sales_invoice mcp_erpnext.tests.test_quotation_to_sales_order mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_profiles mcp_erpnext.tests.test_tool_contracts` — **33 passed**.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'` — **219 passed**.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m compileall -q mcp_erpnext` — passed.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py` — completed.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check` — passed.
* `git diff --check` — passed.

The full suite emitted the repository's existing Python 3.14/pydantic settings
warning, expected HTTP-authentication test warnings, and an existing mocked
India Compliance Item log/traceback; all 219 tests still passed.

## Live verification and limitations

No live MCP call, disposable Sales Order, Sales Invoice insert, database
transaction, permission-role test, closed/on-hold runtime test, India
Compliance runtime conversion, or real ERPNext partial-billing/return
transaction was performed. These are **NOT VERIFIED LIVE**. Installed source
inspection and unit doubles verify the call boundaries and stale/approval
logic, but do not substitute for the live verification matrix in Task 27.

The pick-list/serial-batch and zero-advance boundary is retained by not
running full Sales Invoice validation during prepare; final insert remains the
first persistence-time native validation boundary. No claim is made that every
optional ERPNext branch is side-effect-free during mapping beyond the audited
installed source behavior.

Closed/on-hold Sales Order status is not custom-rejected by this capability;
the installed mapper/controller remains authoritative, as required by Task 26.

## Scope confirmation and next task

No Sales Invoice lifecycle/read/PDF/email/standalone creation capability was
exposed, and no Purchase-profile tool was added. Task 28 and Task 29 were not
implemented early.

The exact next task is:

```text
Task 28 - Sales Invoice Existing-Document Capabilities and Action-Scoped Lifecycle Policy
```
