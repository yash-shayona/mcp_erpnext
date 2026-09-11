# Task 29 — Standalone Sales Invoice Creation Foundation

**Project:** `mcp_erpnext`  
**Profile:** `sales`  
**Task type:** Focused implementation  
**Status:** Ready for coding agent  
**Depends on:** Task 26 audit, Task 27 SO → SI native conversion, Task 28 existing Sales Invoice capabilities/action-scoped lifecycle policy

---

## 1. Scope

Implement **standalone/direct Draft Sales Invoice creation** as a first-class Sales-profile MCP capability.

This task must add exactly these public business tools:

```text
prepare_sales_invoice
confirm_sales_invoice
```

This is the **no-source-document** path:

```text
Customer + bounded items
        ↓
native Sales Invoice new-document/default logic
        ↓
native direct-invoice policy checks
        ↓
bounded effective Draft preview
        ↓
shared approval
        ↓
confirm re-build/re-check
        ↓
normal Draft Sales Invoice insert
```

This task must **not** convert from a Sales Order or Delivery Note and must not create either source document implicitly.

The previously implemented source-backed conversion remains separate:

```text
prepare_sales_order_to_sales_invoice
confirm_sales_order_to_sales_invoice
```

Do not merge or overload the two flows.

---

## 2. Objective

Provide a safe standalone Sales Invoice creation workflow that:

1. works under the authenticated Frappe user;
2. resolves Customer and Item inputs through existing MCP resolver conventions;
3. creates a fresh unsaved `Sales Invoice` using native Frappe/ERPNext document APIs;
4. lets ERPNext resolve customer/company/address/contact/price-list/account/item/tax defaults;
5. respects native Sales Order / Delivery Note requirement policy;
6. produces a bounded, user-reviewable effective Draft preview;
7. binds the exact prepared effective state to the existing shared one-shot approval mechanism;
8. re-builds and re-checks the effective target during confirmation;
9. rejects stale confirmation when relevant source/default/configuration state changed;
10. inserts **Draft only** with normal Frappe permissions and native validation/hooks;
11. remains portable when India Compliance is not installed;
12. preserves Task 27 and Task 28 behavior unchanged.

ERPNext/Frappe/installed apps remain the final authority for accounting, tax, GST, pricing, permissions, validation and lifecycle behavior.

---

## 3. Mandatory inspection before implementation

Before changing code, inspect the **current repository as it exists after Tasks 27 and 28**.

Do not implement from this task file alone.

At minimum inspect:

```text
mcp_erpnext/tools/selling/quotation.py
mcp_erpnext/services/selling/quotation.py
mcp_erpnext/contracts/selling/quotation.py

mcp_erpnext/tools/selling/sales_order.py
mcp_erpnext/services/selling/sales_order.py
mcp_erpnext/contracts/selling/sales_order.py

mcp_erpnext/tools/selling/sales_order_to_sales_invoice.py
mcp_erpnext/services/selling/sales_order_to_sales_invoice.py
mcp_erpnext/contracts/selling/sales_order_to_sales_invoice.py

mcp_erpnext/services/common/creation_contract.py
mcp_erpnext/services/common/field_value_resolver.py
mcp_erpnext/services/common/entity_resolution.py

mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/observability.py

mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/contracts/registry.py

mcp_erpnext/tests/test_quotation_service.py        # or actual current filename
mcp_erpnext/tests/test_sales_order_service.py     # or actual current filename
mcp_erpnext/tests/test_sales_order_to_sales_invoice.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_tool_contracts.py

docs/inspect/SALES_INVOICE_NATIVE_FLOW_AUDIT.md
docs/inspect/SALES_ORDER_TO_SALES_INVOICE_NATIVE_CONVERSION_IMPLEMENTATION_REPORT.md
docs/inspect/SALES_INVOICE_EXISTING_DOCUMENT_CAPABILITIES_IMPLEMENTATION_REPORT.md
```

Also inspect the installed Frappe/ERPNext source actually present in the bench, especially:

```text
apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py
apps/erpnext/erpnext/controllers/selling_controller.py
apps/erpnext/erpnext/controllers/accounts_controller.py
apps/frappe/frappe/model/document.py
```

Inspect runtime `Sales Invoice` and `Sales Invoice Item` metadata through normal read-only Frappe APIs if the test site is available.

If India Compliance is installed on the inspected site, inspect only its relevant native Sales Invoice hooks/fields and preserve optional-app isolation. Do not make India Compliance a hard import dependency.

### Inspection rule

If the current Quotation or Sales Order creation implementation already contains a sound reusable pattern for:

- resolver interaction;
- runtime metadata/default handling;
- item input normalization;
- quantity/rate handling;
- preview construction;
- approvals;
- stale detection;
- typed interaction directives;
- error envelopes;

reuse that strategy.

Do not invent a parallel generic framework unless the existing architecture demonstrably cannot support the Sales Invoice requirements.

Document any deliberate deviation in the implementation report.

---

## 4. Frozen public capability

Add exactly:

```text
prepare_sales_invoice
confirm_sales_invoice
```

### Do not add in this task

Do not add:

```text
create_sales_invoice
make_sales_invoice
submit_sales_invoice
cancel_sales_invoice
delete_sales_invoice
update_sales_invoice
add_sales_invoice_item
prepare_sales_invoice_payment
confirm_sales_invoice_payment
create_payment_entry
prepare_credit_note
prepare_debit_note
```

Existing shared lifecycle tools from Task 28 remain the only submit/cancel/delete path.

---

## 5. Standalone versus source-backed semantics

The new capability represents a genuine direct invoice.

### Allowed

```text
Customer
+ Items
+ bounded optional commercial inputs
→ Draft Sales Invoice
```

### Forbidden

Do not silently do:

```text
Customer + Items
→ hidden Sales Order
→ Sales Invoice
```

Do not silently do:

```text
Customer + Items
→ hidden Delivery Note
→ Sales Invoice
```

If ERPNext policy requires a Sales Order or Delivery Note and the Customer is not exempt, return a structured prerequisite/blocking result.

The MCP must not create the missing prerequisite automatically in this task.

---

## 6. V1 feature boundary

### In scope

The initial standalone capability is limited to a normal customer sales invoice with:

```text
is_pos = 0
is_return = 0
is_debit_note = 0
update_stock = 0
docstatus = 0
```

Support only the ordinary direct-invoice path whose final result is a Draft.

The implementation may support stock Items **without stock movement** only if focused installed-native tests prove that the ordinary `update_stock=0` path works safely with the selected contract and account/default behavior.

### Out of scope

Reject or do not expose:

- `update_stock=1`;
- POS;
- Return / Credit Note;
- Debit Note / rate adjustment;
- Payment Entry creation;
- payments child table;
- advance allocation;
- write-off inputs;
- loyalty redemption;
- timesheet billing;
- project billing if it introduces separate project-billing semantics;
- subscription / Auto Repeat;
- consolidated invoice;
- inter-company invoice;
- recurring generation;
- asset sale special cases;
- Delivery Note → Sales Invoice conversion;
- selected-source-row mapping;
- arbitrary accounting overrides;
- arbitrary GST/e-Invoice/e-Waybill fields;
- implicit submit;
- implicit email;
- implicit PDF generation;
- implicit payment.

If one of these is requested, return an existing safe unsupported/validation-style response consistent with current project conventions; do not silently ignore business-significant input.

---

## 7. Proposed bounded input contract

The coding agent must inspect the current Quotation/Sales Order typed contracts first and reuse established shapes where sound.

The standalone Sales Invoice request should remain explicit and narrow.

Conceptual shape:

```text
customer          required
items             required, non-empty
company           optional
posting_date      optional
selling_price_list optional
customer_address  optional
shipping_address_name optional only if native SI path and current contract justify it
contact_person    optional
```

Each item should conceptually support:

```text
item              required resolved Item reference
qty               required positive quantity
rate              optional only under the reviewed override policy below
```

Do not treat this conceptual list as permission to expose arbitrary fields.

### Customer

Required.

Use the existing Customer resolver/selection pattern.

Must be:

- exact/resolved before preparation can become ready;
- permission-readable by the authenticated user;
- valid under native Sales Invoice customer validation.

Do not accept a raw arbitrary linked name without using the established resolver/reference semantics unless that is already the frozen project pattern.

### Items

Required and non-empty.

Use the existing Item resolver/selection semantics.

Each item must have:

- resolved Item identity;
- positive quantity;
- sales-appropriate eligibility consistent with existing Sales-profile item resolution.

Do not duplicate ERPNext item master/tax/account logic.

### Rate policy

Inspect the current Quotation and Sales Order creation behavior.

If those tools already expose a bounded explicit rate override safely, reuse the same business semantics for standalone Sales Invoice.

Preferred V1 rule:

```text
rate omitted
  → let native ERPNext item/price-list/customer logic derive rate

rate explicitly supplied
  → preserve it only through an explicit typed field
  → include it in preview/approval
  → never silently replace it with another value without showing the effective result
```

If existing architecture shows that a supplied rate cannot be preserved safely through native defaulting without custom duplication, leave explicit rate out of V1 and document the limitation instead of inventing a workaround.

Do not accept `base_rate`, `net_rate`, `amount`, `net_amount` or calculated totals as public inputs.

### Company

Optional only if existing architecture can resolve it safely.

If omitted:

- use native/default company behavior;
- make the effective company visible in preview.

If supplied:

- validate through runtime metadata/link resolution;
- require normal read/link permission;
- do not allow company switching to bypass Customer/account/configuration restrictions.

### Posting date

Optional bounded date.

If omitted, native/default date applies.

If supplied, preserve the requested date but let native fiscal/accounting validation remain authoritative.

Do not accept posting-time bypass flags.

### Price List

Optional only through a typed `Price List` reference.

If omitted, native customer/company/default price list logic should decide.

Do not copy pricing rules or price-list algorithms into MCP.

### Address/contact fields

Optional only if they map to ordinary native Sales Invoice link fields and the existing resolver approach can validate them safely.

Native customer/address/contact defaults should handle omissions.

Do not copy address/GST normalization rules.

---

## 8. Explicit forbidden public fields

Do not expose arbitrary `extra_fields`.

Do not accept direct user input for:

```text
name
docstatus
owner
creation
modified
modified_by

debit_to
party_account_currency
conversion_rate unless separately proven necessary
plc_conversion_rate unless separately proven necessary

total
net_total
grand_total
rounded_total
base_total
base_net_total
base_grand_total
outstanding_amount

taxes arbitrary raw rows
income account arbitrary raw rows
cost center arbitrary override
accounting dimension arbitrary passthrough

update_stock
is_pos
is_return
is_debit_note
return_against

payments
advances
write_off_amount
write_off_account

irn
ewaybill
einvoice_status
e_invoice_status
e_waybill_status
gst_breakup_table
company_gstin
billing_address_gstin
gst_category when native/fetched
GST calculated/read-only values

sales_order
so_detail
delivery_note
dn_detail
```

Source-lineage fields are invalid in standalone creation because there is no source transaction.

If runtime metadata contains additional custom fields, they must not automatically become public writable inputs.

---

## 9. Native direct-invoice policy preflight

Before creating an approval, perform a **read-only, bounded preflight** of the native direct-invoice prerequisite policy.

Installed audit identified the native policy in `SalesInvoice.so_dn_required()`.

The implementation must re-inspect the installed method before coding and follow the installed behavior.

Conceptually:

```text
Selling Settings.so_required
Selling Settings.dn_required
Customer.so_required exception
Customer.dn_required exception
```

### Required behavior

If native policy allows a direct invoice:

```text
continue preparation
```

If Sales Order is required and the Customer is not exempt:

```text
return structured blocked / needs-prerequisite result
```

If Delivery Note is required and the Customer is not exempt:

```text
return structured blocked / needs-prerequisite result
```

The result should be actionable, e.g. explain that the configured ERPNext policy requires the prerequisite document.

Do not expose internal role/permission details.

### Critical rule

The preflight is guidance only.

Final `Sales Invoice.insert()` remains authoritative and must still run native ERPNext validation.

Do not implement the native setting rule as a bypass.

Do not force POS/debit-note/return flags to exploit native exceptions.

---

## 10. Native unsaved Sales Invoice construction

The direct path must start from native document construction:

```python
frappe.new_doc("Sales Invoice")
```

Then populate only the approved bounded inputs.

Use native ERPNext methods for effective defaults/calculations.

The installed audit identified this conceptual flow:

```text
frappe.new_doc("Sales Invoice")
  -> set bounded Customer/company/date/item inputs
  -> append bounded Sales Invoice Item rows
  -> SalesInvoice.set_missing_values()
  -> calculate_taxes_and_totals()
  -> bounded preview
```

Re-inspect the installed controller and use the smallest native method sequence that reproduces ordinary Draft creation behavior without inserting.

### Do not

- manually calculate GST;
- manually calculate taxes;
- manually derive debit account;
- manually derive income account;
- manually calculate price-list rates unless an existing ERPNext helper is the source;
- manually build GL entries;
- call submit;
- call DB insert during prepare;
- call `db_set`;
- call direct SQL writes;
- use `ignore_permissions=True`;
- run as Administrator.

---

## 11. Prepare-time side-effect boundary

`prepare_sales_invoice` must remain non-persisting.

It must not:

- insert Sales Invoice;
- insert child business records;
- submit;
- write GL;
- write Stock Ledger;
- create Payment Entry;
- create Delivery Note/Sales Order;
- enqueue email;
- enqueue e-Invoice/e-Waybill generation;
- call external GST APIs;
- create File records;
- create serial/batch bundles;
- mutate unrelated business documents.

The Task 26 audit already established that full Sales Invoice validation is not universally safe as an unconditional prepare operation.

Therefore:

- do **not** blindly call full `SalesInvoice.validate()` during prepare;
- use the audited/native unsaved defaulting/calculation boundary;
- if a newly discovered method can mutate DB state or create linked records, do not use it in prepare;
- document any prepare-time native method and its side-effect reasoning in the implementation report.

Final insert at confirmation is the first persistence-time native validation boundary.

---

## 12. Effective preview

Preparation must show the user the values that matter before approval.

At minimum, where present:

### Header

```text
doctype = Sales Invoice
docstatus = 0
customer
customer_name
company
posting_date
due_date
currency
selling_price_list
contact_person
customer_address
shipping_address_name
debit_to (effective output only, not public arbitrary input)
```

### Items

For each item:

```text
item_code
item_name
description only if already part of bounded current preview convention
qty
stock_uom / uom as appropriate
conversion_factor
rate
amount
net_rate
net_amount
warehouse if native/default result is relevant
income_account as bounded effective output if needed for review, never arbitrary input
```

### Tax / totals

Bounded tax summary:

```text
tax/account label where safe
rate
tax_amount
total
net_total
total_taxes_and_charges
grand_total
rounded_total
```

### Payment schedule

If native defaults create a payment schedule, expose a bounded summary:

```text
due_date
invoice_portion/payment_amount as applicable
```

Do not serialize the entire Frappe document.

Do not expose secrets, integration credentials, hidden internal flags, arbitrary custom fields, full account internals, or raw child object state.

---

## 13. Approval payload

Reuse the existing shared approval store.

Do not create a second Sales Invoice approval mechanism.

Approval must be bound to:

- action;
- site;
- authenticated user;
- normalized bounded request;
- effective target projection;
- stable fingerprint/digest;
- any bounded configuration/prerequisite state needed to detect stale confirmation.

Do not add a public `approval_mode` argument.

Do not trust a client boolean as human authorization beyond the existing project approval contract.

---

## 14. Stale-confirmation strategy

Standalone SI does not have an upstream Sales Order fingerprint, but the effective Draft can still become stale because relevant masters/settings/defaults can change.

At prepare, create a stable bounded projection/digest.

At confirm:

1. atomically claim the one-shot approval using the existing approval store;
2. recheck current authenticated user context;
3. recheck Sales Invoice create permission;
4. re-resolve/revalidate the exact approved Customer and Item references using the same semantics;
5. re-read the direct-invoice prerequisite settings/customer exceptions;
6. rebuild a fresh unsaved Sales Invoice from the **approved bounded business request**;
7. rerun the same native defaulting/calculation sequence;
8. rebuild the same bounded projection/fingerprint;
9. compare with approved state;
10. return `STALE_CONFIRMATION` using current project conventions if the material effective result changed;
11. insert only the freshly rebuilt target when the fingerprint matches.

Examples of changes that should be able to invalidate confirmation when they materially affect the invoice:

- Customer disabled/permission change;
- Item disabled or no longer eligible;
- Company/default change;
- Selling Settings SO/DN requirement change;
- Customer exception change;
- price/rate/default change;
- tax/template/default-account change;
- currency/price-list/default change;
- address/contact default change when part of the effective approval;
- totals/payment schedule change.

Do not fingerprint volatile framework timestamps or irrelevant metadata.

---

## 15. Confirmation write

Only confirmation may persist.

Use normal Frappe document insertion:

```python
target.insert(
    ignore_permissions=False,
    ignore_links=False,
    ignore_mandatory=False,
)
```

Then:

```python
frappe.db.commit()
```

only after successful insert.

On failure:

- rollback using existing project conventions;
- return the safe public error envelope;
- do not expose stack trace, SQL, GST API details, credentials or internal accounting data.

The returned document must be:

```text
doctype = Sales Invoice
docstatus = 0
```

### Confirmation must not

- call `submit()`;
- create GL entries directly;
- create stock ledger entries directly;
- set `update_stock=1`;
- create Payment Entry;
- send email;
- generate external e-Invoice/E-Waybill;
- create Sales Order/Delivery Note;
- perform cascade actions.

A user who wants submission must use the Task 28 shared lifecycle approval flow afterwards.

---

## 16. Permissions and identity

Preserve the existing authenticated Frappe identity model.

Required checks include, as applicable:

- Sales Invoice create permission;
- Customer read/link visibility;
- Item read/link visibility;
- Company / Price List / Address / Contact link visibility;
- normal Frappe Link validation;
- runtime document validation.

Never use:

- Administrator fallback;
- client-provided Frappe user override;
- direct SQL writes;
- `ignore_permissions=True`;
- `ignore_links=True`;
- `ignore_mandatory=True`;
- permission-blind `frappe.get_all` for business-visible resolution.

Use existing permission-aware resolver/list helpers wherever sound.

---

## 17. India Compliance behavior

The core standalone Sales Invoice module must not import India Compliance at module import time.

### When India Compliance is absent

The capability must continue to work using ERPNext-only:

- metadata;
- Sales Invoice controller;
- standard tax/account defaults;
- Frappe permissions.

No GST/e-Invoice/E-Waybill field must be assumed to exist.

### When India Compliance is installed

Native Frappe hooks and runtime metadata remain authoritative.

Do not copy:

- GST validation algorithms;
- HSN validation rules;
- GSTIN logic;
- e-Invoice rules;
- E-Waybill rules;
- GST tax account logic;
- GST API clients.

Prepare must not call external compliance APIs or enqueue compliance generation.

If implementation inspection proves a small read-only preflight is needed to collect a safely knowable required input before approval, isolate it lazily and keep it advisory; do not turn it into a general integration framework.

Final normal insert must run installed validation/hooks.

Remember: e-Invoice/E-Waybill generation belongs to submit-time native behavior, not Draft creation.

---

## 18. Interaction / resolver behavior

Reuse existing typed interaction contracts.

Expected high-level states should follow current project conventions, for example:

```text
needs_input
needs_selection / ambiguous
blocked / prerequisite required
ready
created
error
```

Do not invent new ad-hoc response envelopes if an existing `InteractionDirective` / typed union already represents the situation.

Examples:

### Missing customer

```text
needs_input
field = customer
```

### Ambiguous customer

Use existing candidate selection behavior.

### Missing items

```text
needs_input
field = items
```

### Ambiguous item

Use existing Item resolver/candidate selection.

### SO required

Return a structured prerequisite/block result explaining that ERPNext configuration requires a Sales Order before a direct Sales Invoice.

### DN required

Return a structured prerequisite/block result explaining that ERPNext configuration requires a Delivery Note before a direct Sales Invoice.

Do not automatically launch another business tool from the server.

The client/agent may decide the next workflow.

---

## 19. Tool registration

The tools must exist only in the Sales profile.

Update the current registration path consistently with the existing architecture.

Likely affected registration areas, subject to current inspection:

```text
mcp_erpnext/tools/selling/sales_invoice.py
mcp_erpnext/services/selling/sales_invoice.py
mcp_erpnext/contracts/selling/sales_invoice.py

mcp_erpnext/contracts/selling/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py only if current registration pattern requires it
docs/TOOLS.md generated through the existing generator
```

Do not register these tools in `purchase`.

Do not weaken Task 28 lifecycle action policy.

---

## 20. Allowed changes

After inspection, changes are allowed only where necessary for this capability, typically:

```text
mcp_erpnext/contracts/selling/sales_invoice.py
mcp_erpnext/services/selling/sales_invoice.py
mcp_erpnext/tools/selling/sales_invoice.py

mcp_erpnext/contracts/selling/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py  # only if needed by existing registration architecture

mcp_erpnext/tests/test_sales_invoice.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_contracts.py

docs/TOOLS.md               # generated, not hand-edited if generator owns it
docs/inspect/STANDALONE_SALES_INVOICE_IMPLEMENTATION_REPORT.md
```

If a shared helper must change, first prove why the existing helper is insufficient and add regression coverage for every existing caller.

---

## 21. Must remain untouched unless a demonstrated blocker requires a minimal compatible change

Do not refactor unrelated architecture.

Preserve:

```text
Task 27 SO -> SI conversion behavior
Task 28 Sales Invoice read/search/PDF/email behavior
Task 28 action-scoped submit/cancel/delete behavior
Task 28 Sales Invoice update = deny
Task 28 Sales Invoice child_add = deny

Customer creation/GST work
Item creation/HSN work
Quotation behavior
Sales Order creation behavior
Quotation -> Sales Order conversion behavior
Purchase profile behavior
generic PDF/email semantics
mcp_identity behavior
approval trust model
```

Do not edit ERPNext, Frappe or India Compliance source.

Do not modify site records, settings or production data merely to make tests pass.

---

## 22. Required unit/static test matrix

Add focused tests for at least the following.

### A. Registration/profile

1. `prepare_sales_invoice` is registered in Sales.
2. `confirm_sales_invoice` is registered in Sales.
3. Neither is registered in Purchase.
4. Existing tool catalog/contracts remain valid.

### B. Basic prepare

5. Valid Customer + one valid Item + qty prepares a Draft preview.
6. Multiple valid Items prepare correctly.
7. Missing Customer returns structured input requirement.
8. Missing/empty Items returns structured input requirement.
9. Missing qty returns structured input requirement if current contract requires explicit qty.
10. qty <= 0 is rejected safely.
11. Customer ambiguity uses existing selection semantics.
12. Item ambiguity uses existing selection semantics.
13. Customer not found follows existing resolver/creation-branch policy; do not auto-create unless that behavior is already explicitly part of the calling workflow.
14. Item not found follows existing resolver/creation-branch policy.

### C. Native defaults

15. Omitted company uses native/default company and shows effective result.
16. Omitted posting date uses native/default date.
17. Omitted price list uses native Customer/company/default logic.
18. Native customer/contact/address defaults appear in bounded preview.
19. Native debit account is resolved and is output-only.
20. Native tax/total calculation is used; MCP does not recalculate.
21. Native payment schedule, when applicable, is reflected in preview.

### D. Rate behavior

22. Omitted rate follows native pricing/default logic.
23. If explicit rate is supported, supplied rate is approval-bound and effective value is previewed.
24. If native logic changes a supplied rate, the user sees the effective prepared value; no silent mismatch.
25. Calculated amount/total fields cannot be supplied directly.

### E. Direct-invoice prerequisite policy

26. `so_required=No`, `dn_required=No` allows ordinary direct preparation subject to other validation.
27. `so_required=Yes` + Customer non-exempt returns prerequisite/block result.
28. `so_required=Yes` + native Customer exception follows installed native policy.
29. `dn_required=Yes` + Customer non-exempt returns prerequisite/block result.
30. `dn_required=Yes` + native Customer exception follows installed native policy.
31. MCP does not create hidden SO/DN.
32. POS/return/debit-note flags cannot be used to bypass the prerequisite check.

### F. Forbidden V1 variants

33. `update_stock=1` is rejected/not accepted.
34. POS is rejected/not accepted.
35. return/credit note inputs are rejected/not accepted.
36. debit-note inputs are rejected/not accepted.
37. payments/advance/write-off inputs are rejected/not accepted.
38. arbitrary source lineage (`sales_order`, `so_detail`, `delivery_note`, `dn_detail`) is rejected/not accepted.
39. arbitrary `extra_fields` is not available.
40. read-only/calculated/GST integration fields cannot be passed through.

### G. Prepare safety

41. Prepare does not insert Sales Invoice.
42. Prepare does not call submit.
43. Prepare does not commit a business write.
44. Prepare does not create Payment Entry.
45. Prepare does not create Sales Order/Delivery Note.
46. Prepare does not write GL.
47. Prepare does not write Stock Ledger.
48. Prepare does not enqueue email.
49. Prepare does not enqueue e-Invoice/E-Waybill.
50. Prepare does not call external GST APIs.
51. Full unsafe Sales Invoice validation is not called unconditionally during prepare.

### H. Approval/security

52. Ready prepare creates the existing shared approval.
53. Confirmation without valid approval is denied.
54. Wrong user is denied.
55. Wrong site is denied.
56. Wrong action is denied.
57. Expired approval is denied.
58. Replayed/consumed approval is denied.
59. Explicit decline follows existing cancellation semantics.
60. No public approval-mode override is accepted.

### I. Stale confirmation

61. Unchanged effective state confirms successfully.
62. Customer material state/default change causing effective invoice change returns stale confirmation.
63. Item material state/default/rate change causing effective invoice change returns stale confirmation.
64. Selling Settings SO/DN policy change returns stale/prerequisite result without insert.
65. Customer prerequisite exception change is detected.
66. Tax/default/account/price change affecting projection is detected.
67. Irrelevant volatile timestamps alone do not create false stale confirmation.

### J. Confirmation write

68. Confirm rebuilds the target rather than inserting arbitrary client payload.
69. Final insert uses:
   - `ignore_permissions=False`
   - `ignore_links=False`
   - `ignore_mandatory=False`
70. Confirm creates Draft only (`docstatus == 0`).
71. Confirm never calls submit.
72. Insert failure rolls back and returns safe public error.
73. Successful insert commits exactly once according to current project conventions.

### K. Optional app portability

74. ERPNext-only import path works without India Compliance installed/imported.
75. India Compliance-installed runtime does not require a hard module import.
76. Native installed hooks remain available at final insert.
77. No copied GST/HSN/e-Invoice/E-Waybill algorithm appears in MCP.

### L. Regression

78. Task 27 SO → SI conversion tests remain green.
79. Task 28 Sales Invoice read/PDF/email/lifecycle tests remain green.
80. Sales Invoice generic update remains denied.
81. Sales Invoice child-add remains denied.
82. Quotation/Sales Order/Customer/Item behavior remains unchanged.
83. Purchase profile remains isolated.

---

## 23. Live verification

If the environment permits safe disposable test data and live writes are explicitly authorized, verify after unit tests with dedicated test documents.

Do not use production business records.

Minimum useful live matrix:

### Direct allowed

- Customer permitted for direct invoice;
- Selling Settings allow direct invoice;
- one ordinary sales Item;
- prepare;
- inspect preview;
- confirm;
- verify a Draft Sales Invoice exists;
- verify no GL Entry from Draft;
- verify no Stock Ledger Entry from Draft;
- verify no Payment Entry;
- verify no automatic submit.

### Direct blocked by Sales Order requirement

- read current settings first;
- use an isolated test configuration/fixture only if allowed;
- verify safe prerequisite result;
- verify no Sales Invoice created;
- verify no hidden Sales Order created.

### Direct blocked by Delivery Note requirement

Same expectations as above.

### Partial native/default checks

Where safely feasible verify:

- Customer default address/contact;
- price list/rate;
- taxes;
- debit account;
- due date/payment terms;
- India Compliance fields/default hooks if installed.

### Optional-app portability

If an ERPNext-only site exists, verify module/tool registration and ordinary prepare path there without importing India Compliance.

If live tests are not authorized or suitable fixtures are unavailable, report them explicitly as **NOT VERIFIED LIVE**. Do not simulate a live success claim.

---

## 24. Acceptance criteria

Task 29 is complete only when all of the following are true:

1. Exactly two new standalone creation tools exist:
   ```text
   prepare_sales_invoice
   confirm_sales_invoice
   ```
2. They are available only in Sales profile.
3. The flow creates a genuine direct Draft Sales Invoice without hidden source documents.
4. Customer and Item resolution reuse existing project semantics.
5. Native ERPNext defaults/calculation drive company/customer/address/contact/price/account/tax/totals behavior.
6. SO/DN prerequisite policy is respected and never bypassed.
7. V1 fixes `update_stock=0`, non-POS, non-return, non-debit-note semantics.
8. No arbitrary `extra_fields` or accounting/GST passthrough exists.
9. Prepare performs no business persistence.
10. Existing shared approval store is reused.
11. Confirm rebuilds/rechecks effective state and detects material staleness.
12. Final insert uses normal Frappe permissions and validation.
13. Final result is Draft only.
14. No Payment Entry, GL direct write, stock direct write, email or external compliance generation is introduced.
15. India Compliance remains optional and native.
16. Task 27 is unchanged/regression-green.
17. Task 28 is unchanged/regression-green.
18. Generic Sales Invoice update remains denied.
19. Generic Sales Invoice child-add remains denied.
20. Purchase profile remains isolated.
21. Focused and full regression suites pass.
22. Tool catalog generation/check passes.
23. `compileall` and `git diff --check` pass.
24. A complete implementation report is produced.

---

## 25. Expected test result

At minimum expect:

```text
focused standalone Sales Invoice tests: PASS
Task 27 conversion regression: PASS
Task 28 existing SI capability regression: PASS
full mcp_erpnext test suite: PASS
compileall: PASS
tool catalog generate/check: PASS
git diff --check: PASS
```

Do not hard-code an expected test count because the repository test count may legitimately increase during this task.

---

## 26. Implementation report required

Create:

```text
docs/inspect/STANDALONE_SALES_INVOICE_IMPLEMENTATION_REPORT.md
```

The report must include:

1. exact result;
2. existing architecture inspected;
3. installed ERPNext/Frappe source inspected;
4. files changed;
5. public contracts added;
6. exact input contract;
7. Customer/Item resolver behavior;
8. rate policy chosen and why;
9. native defaulting/calculation sequence used;
10. SO/DN prerequisite implementation;
11. prepare-side-effect analysis;
12. approval payload/fingerprint strategy;
13. stale-confirmation behavior;
14. final insert behavior and flags;
15. permissions/security;
16. India Compliance optional-app behavior;
17. ERPNext-only behavior;
18. tests/commands run with exact observed results;
19. live verification performed or explicitly NOT VERIFIED LIVE;
20. limitations;
21. confirmation that Task 27 and Task 28 were not weakened;
22. exact next task recommendation based on evidence.

Do not claim live ERPNext behavior if only mocks/unit tests ran.

---

## 27. Known limitations intentionally retained

After this task, the following remain separate future capabilities:

```text
Sales Invoice draft update/edit
Sales Invoice item-row mutation
Delivery Note -> Sales Invoice conversion
update_stock=1 direct invoice
POS Invoice workflow
Credit Note / Return
Debit Note
Payment Entry / payment allocation
advance allocation
Timesheet billing
Project billing
inter-company invoice
recurring/subscription invoice
explicit e-Invoice / E-Waybill operational tools
```

These are not bugs in Task 29.

They are deliberately excluded because they have materially different accounting, stock, source-lineage, payment or compliance semantics.

---

## 28. Exact next task

Do **not** pre-implement the next feature.

After Task 29, stop and return the implementation report.

The next task must be chosen only after reviewing that report and any live verification evidence.

Likely future candidates may include:

```text
Payment Entry / Accounts profile foundation
Sales Invoice bounded draft-edit capability
Delivery Note -> Sales Invoice native conversion
Credit Note / Return native workflow
```

None is authorized by Task 29.

---

# Final frozen design

```text
Sales profile

Customer / Item
      │
      ├────────────────────────────────────┐
      │                                    │
      ▼                                    ▼
Quotation                           Standalone SI
      │                            Customer + Items
      ▼                                    │
Sales Order                                │
      │                                    │
      └── native SO -> SI ───────┐         │
                                 ▼         ▼
                              Draft Sales Invoice
                                      │
                         Task 28 shared operations
                         read / PDF / email
                         submit / cancel / delete
                                      │
                      generic update/child-add DENIED
```

Core ownership remains:

```text
ERPNext / Frappe / installed apps
  own:
    pricing
    taxes
    GST
    accounts
    defaults
    validation
    permissions
    stock/accounting lifecycle effects

MCP
  owns:
    bounded public inputs
    resolver interactions
    safe prerequisite guidance
    non-persisting preview
    approval binding
    stale confirmation
    safe error reporting
```

That boundary must not be weakened.
