# Task - Sales Invoice to Delivery Note Native Conversion

## 1. Objective

Implement an explicit Sales-profile MCP conversion from a submitted ERPNext Sales Invoice to a Draft Delivery Note.

Add exactly these public tools:

```text
prepare_sales_invoice_to_delivery_note
confirm_sales_invoice_to_delivery_note
```

The public workflow must remain:

```text
Submitted Sales Invoice
        ->
prepare_sales_invoice_to_delivery_note
        ->
native ERPNext Draft Delivery Note preview
        ->
explicit approval token
        ->
confirm_sales_invoice_to_delivery_note
        ->
Draft Delivery Note only
```

The tool must use ERPNext's native Sales Invoice mapper. MCP must not reproduce the Sales Invoice -> Delivery Note mapping rules itself.

The native ERPNext v16 callable is:

```python
erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note(
    source_name,
    target_doc=None,
)
```

The native mapper maps only a submitted Sales Invoice parent and uses native row eligibility, including remaining quantity and existing delivery/source-link state.

Do not submit the created Delivery Note automatically. Submission remains a separate action through the existing generic lifecycle tools.

---

## 2. Why This Task Exists

The current Sales profile already supports:

```text
Sales Order -> Delivery Note
Delivery Note -> Sales Invoice
Sales Order -> Sales Invoice
Standalone Sales Invoice
```

ERPNext also natively supports:

```text
Sales Invoice -> Delivery Note
```

but this conversion is currently missing from `mcp_erpnext`.

The current MCP implementation has:

```text
prepare_sales_order_to_delivery_note
confirm_sales_order_to_delivery_note

prepare_delivery_note_to_sales_invoice
confirm_delivery_note_to_sales_invoice
```

The missing pair is:

```text
prepare_sales_invoice_to_delivery_note
confirm_sales_invoice_to_delivery_note
```

This is a genuine native ERPNext capability gap, not a request for a custom workflow.

---

## 3. Mandatory First Step - Inspect Current Implementation

Before changing production code, inspect the current repository and the installed ERPNext source.

At minimum inspect:

```text
mcp_erpnext/services/selling/sales_order_to_delivery_note.py
mcp_erpnext/contracts/selling/delivery_note.py
mcp_erpnext/tools/selling/delivery_note.py

mcp_erpnext/services/selling/delivery_note_to_sales_invoice.py
mcp_erpnext/contracts/selling/delivery_note_to_sales_invoice.py
mcp_erpnext/tools/selling/delivery_note_to_sales_invoice.py

mcp_erpnext/services/selling/sales_order_to_sales_invoice.py
mcp_erpnext/contracts/selling/sales_order_to_sales_invoice.py
mcp_erpnext/tools/selling/sales_order_to_sales_invoice.py

mcp_erpnext/contracts/registry.py
mcp_erpnext/contracts/selling/__init__.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/remote_operations.py

mcp_erpnext/approvals.py
mcp_erpnext/services/common/fingerprint.py

mcp_erpnext/tests/test_sales_order_to_delivery_note.py
mcp_erpnext/tests/test_delivery_note_to_sales_invoice.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_rest_backend.py

docs/inspect/DELIVERY_NOTE_NATIVE_FLOW_AUDIT.md
docs/inspect/DELIVERY_NOTE_V1_IMPLEMENTATION_REPORT.md
docs/inspect/DELIVERY_NOTE_TO_SALES_INVOICE_IMPLEMENTATION_REPORT.md
docs/TOOLS.md
```

Also inspect the installed/current ERPNext implementation, not only generic documentation:

```text
erpnext/accounts/doctype/sales_invoice/sales_invoice.py
    make_delivery_note

erpnext/accounts/doctype/sales_invoice/sales_invoice.js
    native Create -> Delivery Note availability logic

frappe/model/mapper.py
    get_mapped_doc
```

The installed runtime source is authoritative if it differs from older audit documentation.

Do not begin by inventing a new conversion engine.

---

## 4. Confirmed ERPNext Native Behavior to Preserve

For ERPNext v16, `sales_invoice.make_delivery_note()` maps:

```text
Sales Invoice -> Delivery Note
Sales Invoice Item -> Delivery Note Item
```

Important native child mappings include:

```text
Sales Invoice Item.name   -> Delivery Note Item.si_detail
Sales Invoice.name        -> Delivery Note Item.against_sales_invoice
sales_order               -> against_sales_order
so_detail                 -> so_detail
cost_center               -> cost_center
```

The native mapper calculates target row quantity from the remaining undelivered quantity:

```text
Sales Invoice Item.qty - Sales Invoice Item.delivered_qty
```

The native mapper also excludes rows that are already linked/delivered through conditions such as existing Delivery Note detail, supplier delivery, SCIO detail, or no remaining quantity.

Do not copy these conditions into an MCP-owned mapping implementation.

The MCP service must call the installed native mapper and report the target it actually produces.

---

## 5. Scope

Implement only this business intent:

```text
Existing submitted Sales Invoice
        ->
ERPNext native mapping
        ->
Draft Delivery Note
```

The conversion must be Sales-profile only.

The caller supplies only the exact Sales Invoice identity during prepare.

The caller does not supply target Delivery Note accounting, stock, warehouse, mapper, or child-row internals.

---

## 6. Explicitly Out of Scope

Do not implement any of the following in this task:

```text
standalone Delivery Note creation
Delivery Note return
Sales Invoice return -> Delivery Note
Delivery Note -> Sales Invoice changes
Sales Order -> Delivery Note changes
Sales Order -> Sales Invoice changes
partial child-row selection UI
caller-selected item quantities
caller-selected rates
caller-selected warehouse overrides
caller-selected taxes
caller-selected serial numbers
caller-selected batches
Pick List
Packing Slip
Shipment
Delivery Trip
e-Waybill generation
Payment Entry
Sales Invoice payment
supplier delivery workflow
SCIO workflow
arbitrary mapper kwargs
automatic Delivery Note submit
```

Do not expose raw `target_doc`, `kwargs`, `filtered_children`, `ignore_permissions`, or any equivalent framework/internal mapper arguments to the LLM.

---

## 7. Public Tool Names

Add:

```text
prepare_sales_invoice_to_delivery_note
confirm_sales_invoice_to_delivery_note
```

Do not overload:

```text
prepare_sales_order_to_delivery_note
confirm_sales_order_to_delivery_note
```

and do not turn them into generic source-document conversion tools.

Public tools should remain explicit by business transaction/source type.

---

## 8. File Structure

Use the newer explicit source-to-target naming convention for this new capability.

Prefer adding:

```text
mcp_erpnext/contracts/selling/sales_invoice_to_delivery_note.py
mcp_erpnext/services/selling/sales_invoice_to_delivery_note.py
mcp_erpnext/tools/selling/sales_invoice_to_delivery_note.py
mcp_erpnext/tests/test_sales_invoice_to_delivery_note.py
```

Do not rename the existing historical files:

```text
contracts/selling/delivery_note.py
tools/selling/delivery_note.py
services/selling/sales_order_to_delivery_note.py
```

The old naming can remain for compatibility. New code should use the explicit `sales_invoice_to_delivery_note` name.

---

## 9. Prepare Input Contract

Create a typed public input similar to:

```text
SalesInvoiceToDeliveryNoteInput
```

with exactly:

```text
sales_invoice    required non-empty string
```

No other caller-controlled conversion fields are allowed.

Public contract models must continue to forbid extra fields according to the current project convention.

The schema must reject attempts to send fields such as:

```text
customer
company
items
qty
warehouse
rate
against_sales_invoice
si_detail
against_sales_order
so_detail
posting_date
posting_time
target_doc
kwargs
filtered_children
ignore_permissions
update_stock
```

The source document is authoritative for conversion values.

---

## 10. Confirm Input Contract

Create a typed confirmation input similar to:

```text
SalesInvoiceToDeliveryNoteConfirmInput
```

with exactly:

```text
approval_token
confirm
```

No mutable business fields may be accepted during confirm.

The confirmation request must not be able to change:

```text
sales_invoice
items
quantities
warehouse
customer
company
```

from the approved preview.

---

## 11. Source Loading and Permission Boundary

The service must load the exact requested Sales Invoice with normal Frappe permissions.

Required behavior:

1. authenticated Frappe user is required;
2. load exact `Sales Invoice` by name;
3. if missing, return bounded `SOURCE_NOT_FOUND`;
4. if read permission is denied, return bounded `PERMISSION_DENIED`;
5. source must be submitted (`docstatus == 1`);
6. target `Delivery Note` create permission must be available;
7. no permission bypass is allowed.

Do not hardcode:

```text
site
user
company
customer
warehouse
```

Use the configured/current Frappe site and authenticated user naturally.

---

## 12. Native UI-Equivalent Eligibility Boundary

The installed ERPNext Sales Invoice UI exposes Create -> Delivery Note only for a valid submitted non-return invoice where `update_stock` is not enabled and at least one row has a remaining deliverable quantity under ERPNext's native conditions.

The MCP capability must not intentionally provide a route that contradicts that native business flow.

At minimum, inspect the installed version and enforce or safely surface the native eligibility for:

```text
submitted source
not a return
update_stock != 1
at least one native mappable Delivery Note item
```

Do not duplicate all item-level mapping rules manually. The native mapper remains authoritative for row inclusion and remaining quantity.

If the invoice is not eligible because it already updated stock, return a bounded error such as:

```text
SOURCE_NOT_ELIGIBLE
```

with a safe message explaining that a Sales Invoice with Update Stock already performs the stock delivery path and is not eligible for this separate Delivery Note conversion.

If the mapper returns no items, return:

```text
NO_MAPPABLE_ITEMS
```

Do not insert an empty Delivery Note.

If the installed ERPNext behavior proves a different precise rule, follow installed native behavior and document the difference in the implementation report.

---

## 13. Native Mapper

The implementation must use the installed ERPNext mapper directly:

```python
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note

target = make_delivery_note(
    source.name,
    target_doc=None,
)
```

Use the installed function signature exactly.

Do not call Sales Order's mapper for this capability.

Do not reconstruct the target using `frappe.new_doc("Delivery Note")` plus copied Sales Invoice fields.

Do not manually calculate remaining delivery quantity when native mapping already does it.

Do not manually reconstruct source links.

---

## 14. Required Native Link Preservation

The preview and tests must verify the native target retains the correct Sales Invoice linkage.

For mapped Delivery Note rows, expose bounded source linkage fields useful for review:

```text
against_sales_invoice
si_detail
```

If the Sales Invoice itself originated from a Sales Order and ERPNext maps those references, preserve and preview:

```text
against_sales_order
so_detail
```

Do not fabricate these values.

They must come from the native mapped Delivery Note.

---

## 15. Preview Contract

Create a bounded typed preview similar to the current SO -> DN and DN -> SI conversion previews.

Recommended source section:

```text
source:
    doctype = "Sales Invoice"
    name
    docstatus = 1
    status
    customer
    customer_name
    company
    posting_date
    currency
    update_stock
    is_return
    total_qty
    grand_total
```

Recommended target section:

```text
delivery_note:
    target_doctype = "Delivery Note"
    customer
    customer_name
    company
    posting_date
    posting_time
    currency

    items:
        item_code
        item_name
        qty
        uom
        conversion_factor
        rate
        amount
        warehouse
        against_sales_invoice
        si_detail
        against_sales_order
        so_detail

    packed_item_count
    has_serial_batch_requirements

    totals:
        total_qty
        net_total
        total_taxes_and_charges
        grand_total

    warning
```

The warning should remain stock-aware, similar to the current SO -> DN warning:

```text
Submitting may create stock and, depending on ERPNext configuration and item types, accounting effects.
```

Do not return the complete raw Sales Invoice or Delivery Note JSON.

---

## 16. Dynamic Preview Fields and Fingerprint

Reuse the existing conversion fingerprint strategy.

The current SO -> DN flow ignores native `delivery_note.posting_time` in its fingerprint because that value can change between prepare and confirm even when the business conversion did not change.

Inspect the actual native SI -> DN target and apply the same narrowly justified handling if required.

Expected pattern:

```python
stable_fingerprint(
    preview,
    ignored_paths={("delivery_note", "posting_time")},
)
```

Do not broadly exclude source/target fields from the fingerprint.

The fingerprint must still detect meaningful changes such as:

```text
remaining quantity changed
source state changed
customer/company changed
native mapped rows changed
warehouse changed
source linkage changed
totals changed
```

---

## 17. Prepare Workflow

`prepare_sales_invoice_to_delivery_note` must follow the current established approval pattern:

```text
approvals.prune_expired()
        ->
require authenticated user
        ->
load exact submitted Sales Invoice with read permission
        ->
verify target create permission
        ->
call native Sales Invoice -> Delivery Note mapper
        ->
validate mapped target is Draft
        ->
validate target contains at least one mappable item
        ->
build bounded preview
        ->
compute stable fingerprint
        ->
create shared approval record
        ->
return ready result
```

Use an action name such as:

```text
convert_sales_invoice_to_delivery_note
```

The approval payload should follow the existing conversion pattern and include at least:

```text
source_doctype
source_name
fingerprint
projection
```

Do not insert any Delivery Note during prepare.

---

## 18. Prepare Output

Prepare must return the project's normal approval-shaped output:

```text
status = "ready"
approval_token
expires_in_seconds
preview
interaction = approval directive
```

The approval token is an opaque pending-operation handle.

Do not expose approval-store internals.

---

## 19. Confirm Workflow

`confirm_sales_invoice_to_delivery_note` must follow the established one-shot confirmation flow.

For `confirm = false`:

```text
cancel pending approval
return bounded confirmation-required result
create nothing
```

For `confirm = true`:

```text
require authenticated user
        ->
atomically claim approval for confirm-write
        ->
validate source/action payload
        ->
reload current Sales Invoice
        ->
re-check permissions and eligibility
        ->
call native mapper again
        ->
rebuild current preview
        ->
recompute fingerprint
        ->
compare with approved fingerprint
        ->
insert Delivery Note only if unchanged
```

If the mapped business state changed between prepare and confirm, return:

```text
STALE_CONFIRMATION
```

and create nothing.

This is especially important for changes to `delivered_qty` or source links caused by another Delivery Note between prepare and confirm.

---

## 20. Draft-Only Insert

Only after successful stale-state verification, insert the mapped target using normal Frappe permissions:

```python
target.insert(
    ignore_permissions=False,
    ignore_links=False,
    ignore_mandatory=False,
)
```

Use the current commit/rollback pattern.

Do not call:

```python
target.submit()
```

Successful result must be:

```text
Delivery Note
docstatus = 0
```

Submission remains available separately through:

```text
prepare_document_submit
confirm_document_submit
```

No new Delivery Note-specific submit tool is needed.

---

## 21. Error Mapping

Follow current bounded conversion error behavior.

At minimum handle safely:

```text
SOURCE_NOT_FOUND
SOURCE_NOT_READY
SOURCE_NOT_ELIGIBLE
PERMISSION_DENIED
NO_MAPPABLE_ITEMS
NATIVE_VALIDATION_FAILED
CONVERSION_UNAVAILABLE
STALE_CONFIRMATION
CONFIRMATION_REQUIRED
CONFIRMATION_UNAVAILABLE
CONVERSION_FAILED
```

Do not leak:

```text
raw traceback
SQL
filesystem paths
server internals
full Frappe document dumps
permission internals
```

When a native validation is safe and useful to distinguish, map it to a bounded public error. Otherwise return the project's generic safe conversion message.

---

## 22. Created Result Contract

Create a bounded created result similar to existing conversion results.

Suggested fields:

```text
status = "created"
doctype = "Delivery Note"
delivery_note
Docstatus = 0
source_sales_invoice
customer
company
currency
grand_total
item_count
```

Use the actual project field naming convention. `docstatus` should remain lowercase as in existing result contracts.

Do not return the full inserted Delivery Note document.

---

## 23. Tool Wrapper

Create:

```text
mcp_erpnext/tools/selling/sales_invoice_to_delivery_note.py
```

Use the exact current tool-wrapper conventions:

```text
TypeAdapter
execute_tool_with_context
tool_meta(...)
structured_output=True
typed RootModel output
```

Suggested descriptions:

```text
prepare_sales_invoice_to_delivery_note
Prepare a native Draft Delivery Note preview from a submitted Sales Invoice that still has deliverable quantity.
```

```text
confirm_sales_invoice_to_delivery_note
Create the approved native Draft Delivery Note from the reviewed Sales Invoice conversion.
```

Descriptions must clearly distinguish this tool from:

```text
prepare_sales_order_to_delivery_note
prepare_delivery_note_to_sales_invoice
```

---

## 24. Contract Registry

Update:

```text
mcp_erpnext/contracts/registry.py
```

Register both new tools.

Prepare entry:

```text
Domain: Selling
Operation: PREPARE
Side effect: PREPARE
interaction: APPROVAL
approval_confirm_tool: confirm_sales_invoice_to_delivery_note
```

Confirm entry:

```text
Domain: Selling
Operation: CONFIRM
Side effect: CONFIRM_WRITE
approval_guard: existing trusted pending-operation guard
```

Do not create a parallel metadata registry.

---

## 25. Contracts Package Export

Update:

```text
mcp_erpnext/contracts/selling/__init__.py
```

only as needed to match the current public-contract export convention.

Do not perform unrelated cleanup of old exports.

---

## 26. Sales Tool Registration

Update:

```text
mcp_erpnext/tools/__init__.py
```

so `register_sales_tools()` registers the new pair.

Recommended placement:

```text
Sales Order -> Delivery Note
Sales Invoice -> Delivery Note
Delivery Note -> Sales Invoice
```

Conceptually:

```text
register_delivery_note_tools(mcp)
register_sales_invoice_to_delivery_note_tools(mcp)
register_delivery_note_to_sales_invoice_tools(mcp)
```

Do not move the tools into Accounts or Purchase.

`mcp_erpnext/profiles/sales.py` should continue using the established `register_sales_tools()` entrypoint unless inspection proves a direct profile change is required.

---

## 27. REST / Remote Backend Parity

The current project requires direct and REST backend parity for public tools.

Update:

```text
mcp_erpnext/remote_operations.py
```

Add fixed typed handlers for:

```text
prepare_sales_invoice_to_delivery_note
confirm_sales_invoice_to_delivery_note
```

The REST path must call the same authoritative service functions as direct MCP execution.

Do not add generic caller-selected service/function dispatch.

Unknown operation and invalid payload behavior must remain fail-closed.

---

## 28. Existing Lifecycle Policy

Delivery Note was already added to the Sales lifecycle policy by the existing Delivery Note implementation.

Verify that the created Draft can use existing:

```text
prepare_document_submit
confirm_document_submit
prepare_document_cancel
confirm_document_cancel
prepare_document_delete
confirm_document_delete
```

according to the current Delivery Note lifecycle allowlist.

Do not create new lifecycle tools.

Do not widen generic Delivery Note update/child-add permissions merely for this conversion.

If the existing lifecycle configuration already supports the intended actions, make no lifecycle production-code change.

---

## 29. PDF / Email / Read Behavior

Delivery Note already has:

```text
get_delivery_note
query_delivery_notes
aggregate_delivery_notes
render_document_pdf
prepare_document_email
confirm_document_email
```

Do not create duplicate read/PDF/email capabilities.

The newly created Delivery Note should naturally work with the existing bounded Delivery Note read and shared PDF/email foundations after creation.

Only change those foundations if an actual test proves a missing policy entry caused specifically by this new flow.

---

## 30. Required Contract Tests

Add/update tests to verify:

### Prepare schema

Required input is exactly:

```text
sales_invoice
```

Reject extra fields such as:

```text
items
qty
warehouse
update_stock
target_doc
kwargs
ignore_permissions
```

### Confirm schema

Required input is exactly:

```text
approval_token
confirm
```

Confirm must reject mutable business fields.

### Tool metadata

Verify:

```text
prepare side effect = PREPARE
confirm side effect = CONFIRM_WRITE
prepare approval_confirm_tool = confirm_sales_invoice_to_delivery_note
```

### Contract audit

The full registered Sales inventory must continue to return:

```text
audit_tool_contracts(...) == []
```

---

## 31. Required Service Tests

Create focused tests in:

```text
mcp_erpnext/tests/test_sales_invoice_to_delivery_note.py
```

At minimum cover:

### A. Successful prepare

Submitted Sales Invoice + native mapped Delivery Note returns:

```text
status = ready
source doctype = Sales Invoice
target doctype = Delivery Note
target docstatus = Draft
```

Prepare inserts nothing.

### B. Successful confirm

After approval, confirmation rebuilds the same native target and inserts exactly one Draft Delivery Note.

Verify normal insert flags:

```text
ignore_permissions=False
ignore_links=False
ignore_mandatory=False
```

### C. Source links

Mapped rows preserve native:

```text
against_sales_invoice
si_detail
```

and preserve native Sales Order links when present:

```text
against_sales_order
so_detail
```

### D. Remaining quantity

Preview uses the quantity returned by the native mapper for a partially delivered Sales Invoice. Do not MCP-recalculate or override the target quantity.

### E. No mappable items

Native target with no items returns:

```text
NO_MAPPABLE_ITEMS
```

and creates nothing.

### F. Draft source

A Draft Sales Invoice is rejected as source not ready.

### G. Missing source

Returns bounded source-not-found result.

### H. Source read permission denied

Returns bounded permission error.

### I. Delivery Note create permission denied

Returns bounded permission error before insert.

### J. Return invoice

A Sales Invoice return must not be converted through this normal-delivery capability.

### K. Update Stock invoice

A submitted Sales Invoice with `update_stock = 1` must not be intentionally converted into a second Delivery Note stock-delivery path.

Test the final behavior chosen after inspecting installed ERPNext. Prefer a clear bounded source-not-eligible result if that matches the implementation boundary.

### L. Confirm false

Cancels/rejects the pending action and creates nothing.

### M. Stale source

If current native mapping differs from the approved mapping at confirmation time, return:

```text
STALE_CONFIRMATION
```

and create nothing.

This should include a scenario equivalent to delivered quantity changing between prepare and confirm.

### N. Consumed/replayed approval

A consumed approval must not create a duplicate Delivery Note.

### O. Native mapper validation failure

Return bounded native validation/conversion error without leaking internals.

### P. Insert failure

Rollback and return bounded conversion failure.

### Q. No submit

Verify no `submit()` call occurs.

---

## 32. Registration and Profile Tests

Update current deterministic registration tests.

At minimum:

```text
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_profiles.py
```

Sales profile must include:

```text
prepare_sales_invoice_to_delivery_note
confirm_sales_invoice_to_delivery_note
```

Purchase profile must not include them.

Accounts profile must not include them.

Preserve all existing Sales tools.

Do not remove or rename existing public tools.

---

## 33. REST Backend Tests

Update:

```text
mcp_erpnext/tests/test_rest_backend.py
```

or the current equivalent remote-operation test module.

Verify both new operation names are statically supported with their typed request models and route to the new service.

Test at least:

```text
prepare_sales_invoice_to_delivery_note
confirm_sales_invoice_to_delivery_note
```

Do not claim live HTTP round-trip verification unless it is actually executed.

---

## 34. Regression Tests

Regress at minimum:

```text
Sales Order -> Delivery Note
Delivery Note -> Sales Invoice
Sales Order -> Sales Invoice
Standalone Sales Invoice
Delivery Note read/query/aggregate
Sales Invoice read/query/aggregate
Sales lifecycle
Approval store
Fingerprint helper
Tool contract audit
Sales profile inventory
REST backend operation registry
```

The new conversion must not alter the behavior of existing conversions.

---

## 35. Documentation

Update generated tool documentation according to the existing repository workflow.

Use:

```text
scripts/generate_tool_catalog.py
```

Do not hand-maintain generated catalog sections when the generator owns them.

Update/create only focused documentation required by the existing architecture.

Create:

```text
docs/inspect/SALES_INVOICE_TO_DELIVERY_NOTE_IMPLEMENTATION_REPORT.md
```

The report must include:

```text
1. current MCP implementation inspected
2. installed ERPNext source inspected
3. exact native mapper used
4. source eligibility behavior
5. files changed
6. public input/output contracts
7. preview fields
8. approval and fingerprint behavior
9. direct/REST parity
10. tests executed
11. exact test results
12. remaining limitations
13. live verification status
```

Do not claim live Frappe/MCP/database behavior was verified if only mocked/unit/static tests were executed.

---

## 36. Security and Data Exposure Requirements

The LLM should receive only the information necessary to identify and review the conversion.

Do not expose:

```text
full Sales Invoice JSON
full Delivery Note JSON
raw Item records
raw Customer records
SQL
tracebacks
framework stack internals
server filesystem paths
credentials
shared secrets
arbitrary mapper arguments
permission internals
```

The preview should answer only business-review questions such as:

```text
Which Sales Invoice is being delivered?
Which Customer and Company?
Which items and remaining quantities will be delivered?
Which warehouse did ERPNext map?
What Sales Invoice/Sales Order references will be retained?
What are the mapped totals?
Will the result remain Draft?
```

---

## 37. Native Authority Rule

This task must preserve the project rule:

```text
MCP owns:
- explicit business capability
- typed public contract
- authenticated permission boundary
- bounded preview
- approval
- stale-state protection
- safe public errors
- bounded output

ERPNext owns:
- source-to-target mapping
- remaining quantity calculation
- Sales Invoice item eligibility
- source link mapping
- warehouse/default derivation
- packed item handling
- serial/batch requirements
- stock validations
- Delivery Note validation
- submit-time stock/accounting behavior
```

Do not copy ERPNext business logic into MCP merely to make the service look self-contained.

---

## 38. Allowed Changes

Allowed:

```text
new sales_invoice_to_delivery_note contract module
new sales_invoice_to_delivery_note service module
new sales_invoice_to_delivery_note tool wrapper
contract package exports
contract registry entries
Sales tool registration
remote operation registry entries
focused tests
profile/registration expected inventory updates
generated tool catalog
focused implementation report
```

A very small shared conversion helper extraction is allowed only if the current source clearly contains identical behavior and all existing callers remain behaviorally unchanged.

Do not perform refactoring merely for aesthetics.

---

## 39. Changes Not Allowed

Do not:

```text
rename existing public tools
rename existing SO -> DN files
rewrite existing SO -> DN conversion
rewrite existing DN -> SI conversion
change standalone Sales Invoice creation
change Sales Invoice payment tools
change Delivery Note read/query/aggregate behavior
change Purchase profile
change Accounts profile
add standalone Delivery Note creation
add return workflow
add arbitrary item selection or quantity override
add raw mapper kwargs
bypass Frappe permissions
hardcode site/company/customer/warehouse
copy ERPNext mapper logic
submit the Delivery Note automatically
perform broad architecture cleanup
```

---

## 40. Acceptance Criteria

The task is complete only when all of the following are true.

### AC-01

Sales profile exposes:

```text
prepare_sales_invoice_to_delivery_note
confirm_sales_invoice_to_delivery_note
```

### AC-02

Prepare input contains only exact Sales Invoice identity.

### AC-03

Confirm input contains only approval token and confirm flag.

### AC-04

Only a submitted, eligible Sales Invoice can enter the conversion flow.

### AC-05

A Sales Invoice with `update_stock = 1` is not intentionally allowed to create a second stock-delivery route through this tool.

### AC-06

A return Sales Invoice is not handled by this normal-delivery tool.

### AC-07

The service calls ERPNext's installed native `sales_invoice.make_delivery_note` mapper.

### AC-08

MCP does not manually calculate or override remaining item quantity.

### AC-09

Mapped Delivery Note rows preserve native `against_sales_invoice` and `si_detail` links.

### AC-10

Native Sales Order references are preserved when the mapper supplies them.

### AC-11

Prepare creates no Delivery Note document.

### AC-12

Prepare returns a bounded native target preview and approval token.

### AC-13

Confirm atomically claims the existing approval and remaps from fresh source state.

### AC-14

Meaningful mapping changes produce `STALE_CONFIRMATION` and no insert.

### AC-15

Successful confirm inserts exactly one Draft Delivery Note with normal Frappe permissions.

### AC-16

No automatic submit occurs.

### AC-17

No mappable rows produce a bounded `NO_MAPPABLE_ITEMS` result.

### AC-18

No raw mapper/internal fields are exposed in the public contract.

### AC-19

Direct MCP and REST backend both route through the same service behavior.

### AC-20

Sales tool contract audit returns no errors.

### AC-21

Purchase and Accounts profile inventories remain unchanged.

### AC-22

Existing SO -> DN and DN -> SI tests remain green.

### AC-23

Generated tool catalog is current and its check mode passes.

### AC-24

Implementation report records exact tests and any unverified live/runtime behavior.

---

## 41. Suggested Example

User intent:

```text
Create a Delivery Note from Sales Invoice ACC-SINV-2026-00010.
```

Prepare request:

```json
{
  "sales_invoice": "ACC-SINV-2026-00010"
}
```

Conceptual prepare result:

```text
status: ready
source:
  Sales Invoice: ACC-SINV-2026-00010
  docstatus: Submitted
  update_stock: 0

delivery_note:
  target_doctype: Delivery Note
  customer: <native mapped customer>
  company: <native mapped company>
  items:
    - item_code: ITEM-001
      qty: <native remaining quantity>
      against_sales_invoice: ACC-SINV-2026-00010
      si_detail: <source Sales Invoice Item name>
  docstatus: Draft

approval_token: <opaque token>
```

Confirm request:

```json
{
  "approval_token": "<opaque-token>",
  "confirm": true
}
```

Expected created result:

```text
status: created
doctype: Delivery Note
docstatus: 0
delivery_note: <generated name>
source_sales_invoice: ACC-SINV-2026-00010
```

---

## 42. Required Test Commands

Use the repository's supported environment and existing command style.

At minimum execute focused tests covering:

```text
test_sales_invoice_to_delivery_note
test_sales_order_to_delivery_note
test_delivery_note_to_sales_invoice
test_tool_contracts
test_tool_registration
test_profiles
test_rest_backend
test_approvals
test_fingerprint
```

Also run the tool catalog generator and check mode.

Then run the broader existing test suite if the current environment supports it.

Record exact counts and failures.

Do not describe an unrelated pre-existing failure as caused by this task without evidence from the failing traceback/path.

Do not claim a test passed unless it was actually executed.

---

## 43. Expected Result After This Task

The Sales conversion coverage should become:

```text
Quotation
    -> Sales Order

Sales Order
    -> Sales Invoice

Sales Order
    -> Delivery Note

Sales Invoice
    -> Delivery Note

Delivery Note
    -> Sales Invoice
```

with every write conversion following the same architectural boundary:

```text
explicit typed prepare
    -> native ERPNext mapping
    -> bounded preview
    -> approval
    -> fresh native remap
    -> stale check
    -> Draft-only insert
```

---

## 44. Limitations After This Task

The following remain intentionally unsupported:

```text
standalone Delivery Note creation
Delivery Note returns
Sales Invoice return -> Delivery Note
partial row selection
manual delivery quantity override
manual warehouse override
serial/batch allocation workflow
Packing Slip
Pick List
Shipment
Delivery Trip
special supplier-delivery conversion
SCIO-specific conversion
automatic submit
```

These must be handled as separate business capabilities if required later.

---

## 45. Exact Next Task

After this implementation passes focused and regression tests, the next task is:

```text
Live Sales Invoice -> Delivery Note MCP Verification
```

Perform an authenticated end-to-end test on an explicitly safe test Sales Invoice that is:

```text
Submitted
not a return
Update Stock = 0
has at least one item with remaining deliverable quantity
```

Verify:

```text
prepare_sales_invoice_to_delivery_note
        ->
review native preview and source links
        ->
confirm_sales_invoice_to_delivery_note
        ->
get_delivery_note
        ->
verify Draft document in ERPNext
```

Then, only when explicitly approved for the test record:

```text
prepare_document_submit
        ->
confirm_document_submit
        ->
verify stock/source delivered state
```

Do not begin standalone Delivery Note creation or return-flow implementation until this native Sales Invoice conversion has passed the live verification step.
