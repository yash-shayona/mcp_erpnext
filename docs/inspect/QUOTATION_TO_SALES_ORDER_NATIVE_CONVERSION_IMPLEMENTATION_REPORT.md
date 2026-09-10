# Quotation to Sales Order Native Conversion Foundation

## A. Existing implementation inspected

Before implementation, the following current-tree files and functions were inspected:

- `mcp_erpnext/services/selling/quotation.py`: standalone Quotation prepare/confirm.
- `mcp_erpnext/services/selling/sales_order.py`: standalone Sales Order prepare/confirm.
- `mcp_erpnext/tools/selling/quotation.py` and `sales_order.py`: existing typed and frozen-legacy wrapper patterns.
- `mcp_erpnext/contracts/selling/quotation.py`: typed preview, approval, and confirmation contracts.
- `mcp_erpnext/contracts/registry.py` and `contracts/audit.py`: contract metadata and audit invariants.
- `mcp_erpnext/contracts/interaction.py`: shared `InteractionDirective` and `approval_directive()`.
- `mcp_erpnext/approvals.py`: action/site/user/payload-bound approval claims and single-use consumption.
- `mcp_erpnext/services/common/lifecycle.py`: stale revalidation and normal-permission persistence pattern.
- `mcp_erpnext/services/common/read.py` and `tools/read.py`: exact permitted existing-document reads.
- `mcp_erpnext/profiles/sales.py`, `profiles/purchase.py`, and `tools/__init__.py`: deterministic profile registration.
- Existing tests for Quotation, approvals, profiles, registration, contracts, and Task 20 Item reads.

The new capability is pair-specific. It does not alter standalone Sales Order creation or generic lifecycle semantics.

## B. Installed official source evidence

The installed source is ERPNext `16.34.2` with Frappe `16.33.1`.

The implementation uses `erpnext.selling.doctype.quotation.quotation.make_sales_order(source_name)`. In the installed ERPNext source:

- `make_sales_order()` checks `Selling Settings.allow_sales_order_creation_for_expired_quotation` and blocks expired quotations when the setting is disabled.
- It delegates to `_make_sales_order()`; the conversion service therefore does not recreate or contradict ERPNext's expiry policy.
- `_make_sales_order()` calls `_make_customer()`. Customer quotations load the existing Customer; Lead and Prospect paths can create a Customer when no existing Customer is found. The service checks `quotation_to == "Customer"` before invoking this native path, preventing prepare-time master creation for unsupported party types.
- The mapped parent uses `validation: {"docstatus": ["=", 1]}`, preserving the Submitted-source requirement.
- `Quotation Item` maps to `Sales Order Item` with `field_map: {"parent": "prevdoc_docname", "name": "quotation_item"}`.
- `get_ordered_items()` reads submitted Quotation Item rows with positive `ordered_qty`; `update_item()` subtracts ordered quantity from source `stock_qty` and derives the target quantity from the remaining stock quantity and conversion factor.
- The native row condition excludes exhausted rows and, without explicit selected rows, excludes alternative rows according to ERPNext's own rules. The MCP service does not implement custom quantity or alternative selection logic.
- Native mapping invokes target `set_missing_values()` and `calculate_taxes_and_totals()`, and the service previews the resulting mapped values rather than reconstructing them from Customer/Item inputs.

In installed Frappe `frappe.model.mapper.get_mapped_doc()` with `ignore_permissions=False`:

- The new target document receives a create permission check.
- The source document receives a read permission check.
- Strict user-permission mode can apply a final target create check as well.

The conversion never passes `ignore_permissions=True`; final persistence uses `insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)` and leaves the target Draft.

## C. Final public contract

`prepare_quotation_to_sales_order` accepts exactly:

```json
{"quotation": "SAL-QTN-..."}
```

The exact name is typed as a non-empty string. It accepts no Customer, Item, target document, quantity, rate, price-list, tax, terms, status, or doctype overrides.

The successful result is a typed `ready` result containing `approval_token`, `expires_in_seconds`, a bounded `preview`, and the shared `InteractionDirective` with `kind = APPROVAL`. The preview contains the exact source Quotation identity and native Sales Order header, item lineage/economics, taxes, totals, and terms.

Prepare failures use the shared safe `ToolError` envelope. Important business codes include `SOURCE_NOT_FOUND`, `SOURCE_NOT_READY`, `UNSUPPORTED_QUOTATION_PARTY`, `NO_MAPPABLE_ITEMS`, `PERMISSION_DENIED`, and `CONVERSION_UNAVAILABLE`.

`confirm_quotation_to_sales_order` accepts only `approval_token` and `confirm`. Success returns `created`, the Sales Order name, `docstatus = 0`, the source Quotation name, and `idempotent = false`. Confirmation failures use the same safe error envelope and shared approval failure states.

## D. Prepare write-safety evidence

The service loads the exact Quotation, checks read permission, requires `docstatus == 1`, requires `quotation_to == "Customer"`, and only then calls the native mapper. Therefore Lead, Prospect, CRM Deal, and other party types return `UNSUPPORTED_QUOTATION_PARTY` without entering ERPNext's `_make_customer()` creation paths. No Customer creation, Sales Order insertion, submission, or approval token occurs in those cases.

## E. Native mapping evidence

The service stores only the source name and a server-owned fingerprint in the approval payload. The public preview is derived from the native mapped target and is bounded to business fields.

For a native mapped result equivalent to:

```text
Quotation SAL-QTN-0001
  Customer: CUST-001
  Quotation Item: QTN-ITEM-001
  qty: 2
  rate: 500

Sales Order preview
  customer: CUST-001
  item qty: 2
  item rate: 500
  quotation_item: QTN-ITEM-001
  prevdoc_docname: SAL-QTN-0001
```

the MCP preview and confirmed Draft use those native values. No standalone Sales Order preparation or Item price-list lookup is involved, so a source rate is not replaced by an unrelated default price.

## F. Stale-state strategy

Prepare maps the current source and computes a SHA-256 fingerprint over:

- source doctype/name, docstatus, party type/name, status, company, currency, transaction date, and validity date;
- mapped Sales Order customer, customer name, company, transaction date, delivery date, currency, selling price list, Terms and Conditions reference, and terms;
- every mapped item preview field: item code/name, quantity, UOM, rate, discounts, amounts, warehouse, delivery date, and native `quotation_item`/`prevdoc_docname` links;
- every mapped tax preview field and all mapped totals;
- mapped sales-team business values and payment-schedule business values.

Confirm atomically claims the existing action-specific approval, reloads and rechecks the source, calls the same native public mapper again, recomputes the fingerprint, and inserts only when the fingerprint matches. A mismatch or current ineligibility returns `STALE_CONFIRMATION` and does not insert. This catches downstream ordered-quantity changes that a Quotation `modified` timestamp alone would not necessarily detect.

## G. Permission behavior

The source read and target create checks run under the authenticated request-scoped Frappe user. Native mapper checks remain enabled, and final insert uses normal Frappe permissions and hooks. Public permission failures contain only a generic safe message; role names and internal permission mechanics are not exposed.

## H. Tests run

- `../../env/bin/python -m unittest mcp_erpnext.tests.test_quotation_to_sales_order mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_tool_contracts mcp_erpnext.tests.test_profiles` — 22 tests passed.
- `../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'` — 194 tests passed.
- `../../env/bin/python scripts/generate_tool_catalog.py` — completed successfully.
- `../../env/bin/python -m compileall -q mcp_erpnext` — completed successfully.
- `git diff --check` — no whitespace errors.

The test process emitted the existing Python 3.14 `IncompleteFieldDefinitionWarning` for the unresolved `lifespan` setting annotation. It did not fail the tests.

## I. Manual verification

No live MCP handshake, authenticated local ERPNext conversion, disposable document creation, PDF/client verification, or production operation was run in this task. The existing local runtime warning/blocker around the `lifespan` annotation remains a separate live HTTP verification concern.

## J. Files changed for this task

- `mcp_erpnext/contracts/selling/quotation_to_sales_order.py`
- `mcp_erpnext/services/selling/quotation_to_sales_order.py`
- `mcp_erpnext/tools/selling/quotation_to_sales_order.py`
- `mcp_erpnext/contracts/selling/__init__.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/tools/__init__.py`
- `mcp_erpnext/tests/test_quotation_to_sales_order.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `mcp_erpnext/tests/test_profiles.py`
- `docs/TOOLS.md` (generated)
- `docs/inspect/QUOTATION_TO_SALES_ORDER_NATIVE_CONVERSION_IMPLEMENTATION_REPORT.md`

Pre-existing Task 20 worktree changes were preserved and were not refactored.

## K. Known limitations

- V1 supports Customer Quotations only.
- No selected-row or alternative-item UI orchestration is added.
- The conversion creates a Draft Sales Order only; it does not submit the Quotation or Sales Order.
- Approval state remains process-local, so prepare and confirm must use the same MCP process.
- No downstream Sales Order to Sales Invoice conversion is included.
- Live authenticated ERPNext/HTTP verification remains outstanding.

## L. Exact next task recommendation

After live verification of this conversion on disposable documents, the next evidence-based capability candidate is Sales Order to Sales Invoice native conversion. It should be selected only after testing confirms no more immediate prerequisite or native-mapper gap.
