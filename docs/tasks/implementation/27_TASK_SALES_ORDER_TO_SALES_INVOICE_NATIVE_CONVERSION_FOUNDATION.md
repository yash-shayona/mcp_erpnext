# Task 27 - Sales Order -> Sales Invoice Native Conversion Foundation

## 0. Task identity

**Project:** `mcp_erpnext`  
**Profile:** `sales`  
**Task type:** Focused implementation task  
**Prerequisite:** Task 26 `SALES_INVOICE_NATIVE_FLOW_AUDIT.md` reviewed and accepted  
**Primary ERPNext target:** ERPNext v16 Sales Order -> Sales Invoice native mapping  
**Public capability added by this task:** exactly two MCP tools

```text
prepare_sales_order_to_sales_invoice
confirm_sales_order_to_sales_invoice
```

This task must implement only source-backed Sales Order -> Sales Invoice conversion. Do not implement standalone Sales Invoice creation, existing Sales Invoice read/search/PDF/email/lifecycle support, Payment Entry, Delivery Note conversion, returns, POS, or generic Sales Invoice editing in this task.

---

# 1. Scope

Implement an MCP conversion workflow that takes one exact submitted ERPNext Sales Order, invokes ERPNext's installed native Sales Order -> Sales Invoice mapper, presents the effective Draft Sales Invoice as a bounded preview, binds that effective state to the existing approval system, re-loads and re-maps the source during confirmation, rejects stale approvals, and inserts the freshly mapped Sales Invoice as **Draft only** under the authenticated Frappe user's normal permissions.

The implementation must reuse the architecture already established by the existing Quotation -> Sales Order native conversion flow when that architecture remains sound. Generic mechanics should be shared internally where appropriate, but the public MCP capability must remain explicit and business-specific.

This task is not permission to refactor unrelated modules or redesign the approval system.

---

# 2. Objective

After this task, a Sales-profile MCP client should be able to perform this controlled workflow:

```text
User asks to invoice a Sales Order
        |
        v
prepare_sales_order_to_sales_invoice
        |
        +-- authenticate current Frappe user
        +-- resolve/validate exact Sales Order reference
        +-- check source read + target create permission
        +-- require submitted source
        +-- call ERPNext native make_sales_invoice(...)
        +-- preserve native remaining-billable quantities
        +-- preserve Sales Order row lineage
        +-- build bounded effective Draft SI preview
        +-- build deterministic business fingerprint
        +-- create existing shared one-shot approval
        v
ready + preview + approval token
        |
        | explicit/trusted approval via existing project policy
        v
confirm_sales_order_to_sales_invoice
        |
        +-- atomically claim existing approval
        +-- recheck user/site/action binding
        +-- recheck permissions
        +-- reload source
        +-- ensure source is still eligible
        +-- call the SAME native mapper again
        +-- rebuild effective projection/fingerprint
        +-- compare against approved state
        +-- reject STALE_CONFIRMATION on material change
        +-- insert freshly mapped SI with all permission/validation bypass flags false
        +-- commit only after successful insert
        v
created Draft Sales Invoice reference
```

The conversion must never reconstruct remaining quantity, taxes, pricing, accounts, payment schedule, GST, stock state, or source lineage in custom MCP logic when ERPNext already owns that behavior.

---

# 3. Inputs and dependencies

## 3.1 Required source input

The public prepare contract should accept one exact Sales Order reference using the project's existing typed reference pattern. Follow the current Quotation -> Sales Order conversion contract unless inspection of the actual implementation proves a necessary difference.

Conceptually:

```text
source:
  doctype: "Sales Order"
  name: "SAL-ORD-..."
```

Do not accept a free-form source document payload.

Do not accept arbitrary target fields or mapper control arguments in V1.

## 3.2 Existing internal dependencies to inspect and reuse

Before editing, inspect the current source for all of these and reuse the established strategy when sound:

```text
mcp_erpnext/tools/selling/quotation_to_sales_order.py
mcp_erpnext/services/selling/quotation_to_sales_order.py
mcp_erpnext/contracts/selling/quotation_to_sales_order.py
mcp_erpnext/contracts/selling/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/observability.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/tests/test_quotation_to_sales_order.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_contracts.py
scripts/generate_tool_catalog.py
docs/TOOLS.md
```

Also inspect any shared interaction/result models currently used by the quotation conversion. Do not create ad-hoc response/status models if the existing interaction contract already represents `ready`, `needs_input`, `blocked`, approval, or safe failures.

## 3.3 Native ERPNext dependency

For the installed ERPNext v16 source audited in Task 26, the native authority is:

```python
erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice(
    source_name,
    target_doc=None,
    args=None,
    ignore_permissions=False,
)
```

Use the installed native callable from the running ERPNext version. Do not copy mapper code into `mcp_erpnext`.

The mapper must run with normal permission behavior. Do not set `ignore_permissions=True`.

---

# 4. Frozen architectural decisions

These decisions are frozen for Task 27.

## 4.1 Explicit public tools

Add exactly:

```text
prepare_sales_order_to_sales_invoice
confirm_sales_order_to_sales_invoice
```

Do not expose a generic `convert_document` tool.

## 4.2 Native mapper is source of truth

ERPNext owns:

- source eligibility enforced by its mapper/controller;
- already-billed quantity calculations;
- returned quantity behavior;
- remaining billable quantity;
- source-to-target item mapping;
- `sales_order` and `so_detail` lineage;
- party/company/currency/default account behavior;
- taxes and totals;
- payment schedule/default terms;
- price/item/account/default resolution;
- serial/batch defaults;
- runtime hooks including installed optional-app `after_mapping` hooks.

MCP must not reproduce these algorithms.

## 4.3 Draft only

`confirm_sales_order_to_sales_invoice` inserts the Sales Invoice as `docstatus = 0` only.

It must not:

- submit the Sales Invoice;
- create GL Entries intentionally;
- create Stock Ledger Entries intentionally;
- create a Payment Entry;
- allocate advances;
- generate or synchronously request e-Invoice/E-Waybill;
- implicitly update stock;
- create a Delivery Note;
- mutate the Sales Order except for whatever normal Draft-insert behavior ERPNext itself legitimately performs.

Submission belongs to Task 28's separately approved lifecycle path.

## 4.4 No target overrides in V1

Do not expose arbitrary target edits such as:

```text
posting_date
company
customer
currency
debit_to
update_stock
is_pos
is_return
is_debit_note
taxes
accounts
payment rows
advances
write-off
loyalty
IRN/e-Waybill fields
item quantity overrides
item rate overrides
filtered_children
skip_item_mapping
```

If a future business case needs controlled overrides, implement it as a later reviewed capability.

## 4.5 Shared approval only

Use the existing shared process-local approval store and `claim_for_confirm_write()` behavior.

Do not:

- add a `confirm=true` shortcut;
- add a public approval-mode argument;
- weaken one-shot semantics;
- allow an approval created for another user/site/action/payload;
- add a second conversion-specific approval store.

## 4.6 Re-map at confirmation

Never persist the exact unsaved object produced during prepare.

Confirmation must reload the source and call the same native mapper again. The freshly mapped target is the only document that may be inserted.

## 4.7 Stale confirmation protection

The approved state must include a deterministic business projection/fingerprint sufficient to detect material changes after prepare, including cases where another Sales Invoice is submitted and changes remaining billable quantity even if relying only on `Sales Order.modified` would be insufficient.

A mismatch must produce the project's safe stale-confirmation result and perform no insert.

## 4.8 ERPNext-only portability

Task 27 must work when India Compliance is not installed.

Do not import India Compliance at module import time and do not make the conversion depend on GST-specific fields existing.

If India Compliance is installed, allow its native ERPNext/Frappe hooks to participate normally through the mapper and final insert lifecycle. Do not duplicate its algorithms.

---

# 5. Allowed changes

The implementation agent may change only the minimum required files after first inspecting the current repository.

Expected additions/changes may include:

```text
mcp_erpnext/contracts/selling/sales_order_to_sales_invoice.py          # new
mcp_erpnext/services/selling/sales_order_to_sales_invoice.py          # new
mcp_erpnext/tools/selling/sales_order_to_sales_invoice.py             # new
mcp_erpnext/contracts/selling/__init__.py                              # register/export models
mcp_erpnext/contracts/registry.py                                      # typed public contract registration
mcp_erpnext/tools/__init__.py                                          # wrapper registration/import
mcp_erpnext/profiles/sales.py                                          # Sales-profile tool registration
mcp_erpnext/tests/test_sales_order_to_sales_invoice.py                 # new focused tests
mcp_erpnext/tests/test_tool_registration.py                            # registration regression
mcp_erpnext/tests/test_profiles.py                                     # profile allowlist regression
mcp_erpnext/tests/test_tool_contracts.py                               # schema/contract regression
docs/TOOLS.md                                                          # generated, not hand-maintained if generator owns it
docs/inspect/SALES_ORDER_TO_SALES_INVOICE_NATIVE_CONVERSION_IMPLEMENTATION_REPORT.md
```

A small existing shared helper may be changed only when the current Quotation -> Sales Order conversion already demonstrates that the behavior is genuinely generic and the change reduces duplication without widening public behavior.

Any shared refactor must be covered by regression tests for the existing Quotation -> Sales Order flow.

---

# 6. Files/components that must not be changed

Unless a directly proven compile/import issue makes a minimal change unavoidable, do not change:

```text
apps/frappe/**
apps/erpnext/**
apps/india_compliance/**
```

Do not change or weaken:

```text
mcp_erpnext/approvals.py                 # semantics/policy remain frozen
mcp_identity/**                          # no identity redesign
shared-secret/user-email HTTP contract
MCP_PROFILE architecture
Purchase-profile business behavior
Customer creation behavior
Item creation behavior
Quotation creation behavior
Sales Order creation behavior
Task 25 Customer GST work
Task 23 Item HSN work
```

Do not add:

- DocTypes;
- migrations;
- fixtures;
- hooks;
- background workers;
- custom GL logic;
- custom stock-ledger logic;
- direct SQL writes;
- generic plugin frameworks;
- India Compliance API clients;
- a standalone Sales Invoice creator;
- Sales Invoice lifecycle/read/PDF/email policies.

Those are outside Task 27.

---

# 7. Required implementation steps

## Step 1 - Inspect the current conversion implementation before writing code

Read the complete existing Quotation -> Sales Order conversion implementation and document which mechanics can be reused unchanged:

- tool wrapper/context execution;
- typed input model;
- output/result model;
- source exact-reference validation;
- permission checks;
- native mapper invocation;
- preview projection;
- approval creation;
- approval action name;
- business fingerprint;
- stale-confirmation handling;
- confirm re-map behavior;
- final `insert()` flags;
- commit/rollback;
- safe error mapping;
- logging/observability;
- tool registry/profile registration;
- generated catalog/tests.

Do not design a parallel approach merely because the target DocType differs.

## Step 2 - Verify the installed ERPNext mapper signature and behavior

Against the actual installed ERPNext source, verify:

```text
make_sales_invoice
get_mapped_doc path
submitted-source requirement
item row filter logic
submitted SI quantity subtraction
returned quantity behavior
sales_order / so_detail mapping
payment schedule behavior
after_mapping execution
permission behavior when ignore_permissions=False
```

The implementation report must cite the actual inspected installed paths/lines.

If the installed source has moved the callable while preserving the public behavior, import the installed callable appropriate to that version rather than hardcoding an obsolete path.

## Step 3 - Define the typed public contract

Create typed request/result schemas consistent with current project conventions.

Prepare should accept only the exact Sales Order reference needed for this conversion.

Confirm should accept only the existing opaque approval token plus whatever fixed confirmation argument the established project contract already requires. Do not widen it.

Register both tools in the typed contract registry and ensure the generated catalog remains deterministic.

## Step 4 - Implement source and permission preflight

Under the authenticated current Frappe user:

1. require non-Guest identity using the existing runtime/context mechanism;
2. require source doctype = `Sales Order`;
3. load/read the exact source with normal permissions;
4. explicitly ensure the authenticated user can read the source;
5. ensure target `Sales Invoice` create permission;
6. verify source `docstatus == 1` before mapping where safely possible;
7. never use Administrator fallback;
8. never use `ignore_permissions=True`.

Draft/cancelled source should return a safe source-not-ready/validation response consistent with existing error semantics rather than an internal traceback.

Closed/on-hold behavior must not be guessed. Preserve native behavior and cover it in focused tests as required by Task 26.

## Step 5 - Call the native mapper during prepare

Call the installed ERPNext Sales Order -> Sales Invoice mapper with bounded/default arguments and normal permissions.

Do not provide unrestricted `args` from the MCP caller.

Do not run `SalesInvoice.validate()` blindly during prepare. Task 26 found full validation is not proven side-effect-free for every branch.

The prepare phase may use only the side-effect-audited mapper/default behavior needed to produce an in-memory Draft target.

## Step 6 - Handle no-mappable-items explicitly

If the native mapped target contains no invoiceable item rows, return a safe business result such as the existing project's blocked/not-applicable shape.

The user-facing meaning should be actionable, for example that the Sales Order has no remaining billable items.

Do not manufacture quantity or include fully billed rows merely to make a target non-empty.

## Step 7 - Build a bounded effective preview

The preview must be useful enough for explicit approval without serializing the entire ERPNext document.

Include a stable subset covering at least:

### Source summary

```text
Sales Order name
source docstatus/status
customer
company
currency
transaction/delivery dates where relevant
billing state / per_billed when available
source totals relevant to understanding the invoice
```

### Source row state required for stale detection

For every relevant Sales Order row, include stable identifiers/state sufficient to explain native billing:

```text
source row name
item_code
UOM / conversion factor as relevant
ordered qty
delivered qty
returned qty
billed qty / equivalent effective state when available
rate / amount
warehouse/project where they materially affect mapping
```

### Generated Sales Invoice summary

```text
customer
company
posting/due date when resolved
currency / price list when relevant
debit_to in the effective target when appropriate for approval visibility
items with:
  item_code
  qty
  uom
  rate
  amount
  sales_order
  so_detail
bounded tax summary
payment schedule summary when present
grand/net/rounded/outstanding-style draft totals as appropriate
```

Do not expose credentials, arbitrary hidden fields, audit fields, raw flags, or unrestricted accounting internals.

## Step 8 - Create a deterministic business fingerprint

Follow the established Quotation -> Sales Order fingerprint strategy but adapt it to Sales Invoice's billing sensitivity.

Fingerprint inputs must cover material state that can alter the mapped target, not just source `modified`.

At minimum bind:

- source identity and submitted state;
- source customer/company/currency;
- relevant source row IDs;
- row quantity/delivery/return/billing state;
- mapped target row lineage (`sales_order`, `so_detail`);
- mapped target quantities/rates/amounts;
- taxes/totals effective for the approval preview;
- payment schedule/default account/address values if they are part of the approved effective target;
- any stable configuration-derived result that materially changes mapping.

Exclude volatile framework timestamps or fields that would create false stale mismatches without changing business meaning.

## Step 9 - Create approval using the existing store

Issue the existing shared one-shot approval only after a valid non-empty effective Draft target is prepared.

The approval must bind:

```text
action
site
current authenticated user
source identity
bounded effective source/target state
fingerprint/digest
```

Do not put a raw Python `Document` instance in approval state.

Use plain serializable data consistent with the current approval store.

## Step 10 - Implement confirmation rechecks

`confirm_sales_order_to_sales_invoice` must:

1. atomically claim the existing approval before the write;
2. reject wrong/expired/replayed/user/site/action-mismatched tokens through existing safe errors;
3. re-resolve current authenticated user;
4. recheck Sales Order read permission;
5. recheck Sales Invoice create permission;
6. reload the source from ERPNext;
7. verify it remains submitted/eligible;
8. call the same native mapper again with the same bounded arguments;
9. ensure the freshly mapped target still has billable items;
10. rebuild the same bounded projection and fingerprint;
11. compare it to the approval-bound state;
12. return `STALE_CONFIRMATION` or the project's established equivalent when material state differs;
13. perform no insert on stale mismatch.

A stale or otherwise failed one-shot confirmation token must not be silently reusable. The client prepares again.

## Step 11 - Insert the freshly mapped Draft with normal Frappe lifecycle

Only after all confirm checks pass:

```python
target.insert(
    ignore_permissions=False,
    ignore_links=False,
    ignore_mandatory=False,
)
```

Use the actual repository's supported signature/style if it differs syntactically, while preserving these semantics.

The document must remain Draft.

Do not call:

```text
submit()
save_submit()
db_set(docstatus=1)
manual GL APIs
stock ledger APIs
Payment Entry creation
India Compliance external API methods
```

Commit only after successful insert. Roll back on failure using the project's existing transaction/error pattern.

## Step 12 - Return a narrow created result

Return the created Draft Sales Invoice reference and a useful bounded summary consistent with current creation/conversion tools.

At minimum identify:

```text
doctype = Sales Invoice
name
status/docstatus = Draft / 0
source Sales Order
customer
company
grand total/currency when safely available
```

Do not claim submission, GL posting, e-Invoice generation, E-Waybill generation, email delivery, payment, or stock posting.

## Step 13 - Register only in the Sales profile

Register both new tools in the existing Sales profile.

They must not appear in Purchase profile.

Do not make Sales Invoice generally eligible for lifecycle/read/PDF/email in this task.

## Step 14 - Update typed registry and generated tool catalog

Update contract metadata and run the project's catalog generator.

Do not manually edit generated catalog content in a way that the generator will later overwrite.

## Step 15 - Add a complete focused test suite

Add tests described in Section 11 below.

Prefer native/project test doubles that preserve real call boundaries rather than deeply mocking away the behavior under test.

Where a unit test cannot safely prove native mapper semantics, cite ERPNext's own installed source/test behavior and add an explicit live verification item.

## Step 16 - Produce the implementation report

Create:

```text
docs/inspect/SALES_ORDER_TO_SALES_INVOICE_NATIVE_CONVERSION_IMPLEMENTATION_REPORT.md
```

The report must include:

- exact files inspected;
- exact files changed;
- architecture reused from Quotation -> Sales Order;
- installed ERPNext mapper path/signature;
- public contract added;
- prepare flow;
- confirm flow;
- preview/fingerprint fields;
- permissions behavior;
- India Compliance behavior when installed;
- ERPNext-only behavior;
- all tests/commands run and observed results;
- any live verification performed;
- any behavior not verified;
- known limitations;
- confirmation that Task 28/29 scope was not implemented;
- exact next task recommendation.

---

# 8. Required interaction/error behavior

Reuse existing safe envelopes and interaction directives.

The implementation must distinguish user-actionable business states from unexpected internal failures where the existing project model supports it.

Expected categories include:

```text
source not found
source permission denied
target create permission denied
source not submitted
no remaining billable items
approval required
confirmation expired
confirmation consumed/replayed
confirmation user/site/action mismatch
stale confirmation
native ERPNext validation failure
unexpected ERP request failure with MCP reference
```

Do not expose:

- Python traceback;
- SQL;
- internal role names unless current safe contract intentionally exposes them;
- secrets/tokens other than the opaque approval token intended for the client;
- GST/e-Invoice credentials;
- implementation paths in ordinary end-user error text.

---

# 9. India Compliance and optional-app requirements

Task 26 confirmed India Compliance hooks can participate in Sales Invoice mapping and lifecycle.

Task 27 must therefore follow these rules:

1. ERPNext core conversion must work with India Compliance absent.
2. Do not import `india_compliance` at module import time.
3. Do not require GST-only fields in the public Task 27 input contract.
4. Do not duplicate GST tax/HSN/place-of-supply/e-Invoice/E-Waybill calculations.
5. Allow normal installed `after_mapping` behavior to run through Frappe/ERPNext.
6. Do not call external GST APIs during MCP prepare.
7. Draft confirmation must not intentionally enqueue e-Invoice/E-Waybill generation.
8. Final `insert()` must still run normal Frappe hooks/validation; do not bypass them.
9. If installed India Compliance validation rejects final insert, surface it through the project's normal safe ERP validation/error mapping; do not catch it and force persistence.

---

# 10. Security requirements

The implementation fails review if any of the following is introduced:

```text
ignore_permissions=True on source mapping or final write
Administrator fallback
direct SQL insert/update for Sales Invoice
client-supplied Frappe user override
client-supplied approval mode
hidden Sales Order creation
hidden Delivery Note creation
implicit submit
implicit Payment Entry
implicit stock update
manual GL write
arbitrary target-field passthrough
raw extra_fields dict
approval replay
cross-profile exposure
GST algorithm/API duplication
```

Authenticated Frappe identity remains the sole business identity.

---

# 11. Tests to run

## 11.1 Focused unit/static tests

At minimum cover all of these scenarios.

### Registration and contract

1. Both new public tools register in Sales profile.
2. Neither tool registers in Purchase profile.
3. Typed registry/schema validates.
4. Tool catalog generation/check passes.
5. Existing Quotation -> Sales Order public contracts remain unchanged.

### Source state

6. Submitted Sales Order can prepare.
7. Draft Sales Order is rejected safely.
8. Cancelled Sales Order is rejected safely.
9. Closed/on-hold behavior matches actual installed native behavior; do not invent a custom policy silently.
10. Missing Sales Order is handled safely.

### Billing behavior

11. Fully billed Sales Order produces no-mappable-items and no approval.
12. Partially billed order maps only native remaining billable quantity.
13. Mixed rows include only rows accepted by native mapping.
14. Submitted prior Sales Invoice quantities are reflected in mapping.
15. Return/redelivery quantity behavior follows native ERPNext result.
16. Unit-price/special mapper branches remain native and are not reimplemented.

### Lineage

17. Every mapped ordinary SI row preserves `sales_order`.
18. Every mapped ordinary SI row preserves `so_detail`.
19. Preview includes source row identity and target lineage.
20. Confirmation fingerprint includes lineage-relevant state.

### Permission

21. Source read denial returns safe permission error.
22. Sales Invoice create denial returns safe permission error.
23. Native mapper is called with permission bypass false/default.
24. Final insert uses `ignore_permissions=False`, `ignore_links=False`, `ignore_mandatory=False`.
25. No Administrator fallback occurs.

### Prepare safety

26. Prepare inserts no Sales Invoice.
27. Prepare submits nothing.
28. Prepare creates no Payment Entry.
29. Prepare intentionally writes no GL Entry.
30. Prepare intentionally writes no Stock Ledger Entry.
31. Prepare does not call external India Compliance APIs.
32. Prepare does not enqueue e-Invoice/E-Waybill generation.
33. Full SalesInvoice `validate()` is not blindly invoked as a generic prepare step.
34. Explicitly cover audited pick-list/serial-batch and zero-advance concerns with either a safe test or a documented guarded boundary.

### Approval

35. Prepare creates approval only after a valid non-empty target exists.
36. Confirm without approval is denied.
37. Wrong action token is denied.
38. Wrong user token is denied.
39. Wrong site token is denied.
40. Expired token is denied.
41. Replayed/consumed token is denied.
42. Approval payload is serializable and contains no live Frappe Document object.

### Stale confirmation

43. Source change after prepare causes stale rejection when material to projection.
44. Another submitted Sales Invoice after prepare changes remaining quantity and causes stale rejection.
45. Return/billing state change after prepare causes stale rejection.
46. Source cancellation after prepare causes safe failure/no insert.
47. Re-map returning no items after prepare causes stale/not-applicable failure/no insert.
48. Stale detection is not based only on `modified`.
49. No insert occurs after stale mismatch.

### Confirmation and persistence

50. Confirm invokes the same native mapper again.
51. Confirm inserts the freshly mapped target, not the prepare object.
52. Successful confirm creates exactly one Draft Sales Invoice.
53. Created SI remains `docstatus=0`.
54. `submit()` is never called by this capability.
55. Commit occurs only after successful insert.
56. Failed insert follows existing rollback/error behavior.
57. Returned result does not claim GL/stock/payment/e-Invoice side effects.

### Optional-app portability

58. ERPNext-only environment imports/registers Task 27 tools without India Compliance.
59. India Compliance-installed environment permits normal native mapping hook behavior.
60. No optional-app module is imported eagerly by Task 27 core module.

### Regression

61. Existing Quotation -> Sales Order tests still pass.
62. Existing Customer, Item, Quotation, Sales Order, lifecycle, read, PDF, email and profile tests still pass.
63. Full `mcp_erpnext/tests` suite passes.

## 11.2 Required project commands

Use the repository's actual environment paths. At minimum run equivalents of:

```text
python -m unittest mcp_erpnext.tests.test_sales_order_to_sales_invoice
python -m unittest mcp_erpnext.tests.test_quotation_to_sales_order
python -m unittest mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_profiles mcp_erpnext.tests.test_tool_contracts
python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
python scripts/generate_tool_catalog.py --check
python -m compileall -q mcp_erpnext
git diff --check
```

If catalog check requires generation first according to the current repository workflow, run the canonical generator command and then the check.

Record exact commands and observed results in the implementation report.

---

# 12. Live verification requirements

Do not perform destructive or production-data testing unless the environment explicitly authorizes it.

If a safe disposable/test Sales Order is available and live verification is authorized, verify at least:

```text
A. submitted unbilled SO -> prepare -> ready preview
B. preview row lineage = sales_order + so_detail
C. approval -> confirm -> exactly one Draft SI
D. created SI is not submitted
E. source partial billing case -> native remaining quantity
F. stale case: billing state changes between prepare and confirm -> no SI created
G. permission-denied user -> no conversion
H. India Compliance-installed site -> mapping/insert uses native hooks without MCP GST duplication
```

If live verification is not authorized or safe test data is unavailable, do not fabricate it. Mark it clearly as `NOT VERIFIED LIVE` in the report.

---

# 13. Acceptance criteria

Task 27 is complete only when all of these are true:

1. `prepare_sales_order_to_sales_invoice` exists and is registered only in Sales profile.
2. `confirm_sales_order_to_sales_invoice` exists and is registered only in Sales profile.
3. Prepare uses ERPNext's installed native SO -> SI mapper.
4. MCP contains no copied remaining-quantity/tax/account/GST algorithm.
5. Only submitted Sales Orders can proceed to a usable prepared conversion.
6. Fully billed/no-item mappings do not produce approvals.
7. Partial billing and returns remain native ERPNext behavior.
8. `sales_order` and `so_detail` lineage is preserved.
9. Preview is bounded but sufficient for approval.
10. Approval is existing shared one-shot, user/site/action/payload bound.
11. Confirm reloads and re-maps source.
12. Material source/billing changes cause stale rejection.
13. Stale protection is stronger than source `modified` alone.
14. Final persistence is a normal permission-enforced `insert()`.
15. Exactly a Draft Sales Invoice is created.
16. No implicit submit occurs.
17. No implicit Payment Entry occurs.
18. No intentional GL/stock ledger operation is called by Task 27.
19. ERPNext-only startup remains supported.
20. India Compliance remains optional/native; no duplicated GST logic is added.
21. Existing Quotation -> Sales Order behavior remains passing.
22. Full regression tests pass.
23. Tool catalog is current.
24. Implementation report is produced with observed evidence.
25. Task 28 and Task 29 functionality is not implemented early.

---

# 14. Expected results

## Prepare success

Conceptual result only; follow the repository's exact typed shape:

```text
status: ready
source:
  doctype: Sales Order
  name: SAL-ORD-...
preview:
  target_doctype: Sales Invoice
  customer: ...
  company: ...
  currency: ...
  items:
    - item_code: ...
      qty: <native remaining billable qty>
      rate: ...
      amount: ...
      sales_order: SAL-ORD-...
      so_detail: <source row name>
  taxes: ...
  payment_schedule: ...
  grand_total: ...
approval_token: <opaque one-shot token>
interaction: <existing approval directive>
```

## Fully billed source

```text
status: blocked / not_applicable according to existing contract
reason: no remaining billable items
approval_token: absent
write: none
```

## Stale confirmation

```text
error/status: STALE_CONFIRMATION or existing canonical equivalent
created_document: none
write: none
next action: prepare again
```

## Confirmation success

```text
created:
  doctype: Sales Invoice
  name: ACC-SINV-... or site's naming series
  docstatus: 0
source:
  Sales Order: SAL-ORD-...
```

Do not hard-code a naming series.

---

# 15. Known limitations / boundaries after Task 27

The following remain intentionally unsupported after this task:

- standalone/direct Sales Invoice creation;
- Sales Invoice read/search through MCP;
- Sales Invoice PDF through MCP;
- Sales Invoice email through MCP;
- Sales Invoice submit/cancel/delete through MCP;
- generic Sales Invoice update;
- Sales Invoice child-row add;
- Delivery Note -> Sales Invoice conversion;
- selected-row/filtered-child conversion controls;
- target quantity/rate override during conversion;
- `update_stock=1` direct workflow;
- POS invoice;
- return/credit note;
- debit note/rate adjustment;
- timesheet/project billing special flows;
- advances/payment allocation;
- Payment Entry creation;
- inter-company invoice;
- subscription/auto-repeat generation;
- explicit e-Invoice/E-Waybill generation tools.

Process-local approval limitations remain as already established by the project; this task does not redesign approval persistence.

---

# 16. Required implementation report questions

Before declaring completion, the agent must answer all of these with evidence:

1. Which exact existing Quotation -> Sales Order patterns were reused?
2. Which exact installed ERPNext mapper was called?
3. Was any native mapper logic copied? Expected answer: no.
4. How is a fully billed Sales Order represented?
5. How are partial billing and returns handled?
6. How are `sales_order` and `so_detail` preserved?
7. What exact fields form the preview/fingerprint?
8. How does confirmation detect another invoice submitted after prepare?
9. Is `modified` the only stale signal? Expected answer: no.
10. Does confirm re-map? Expected answer: yes.
11. Which object is finally inserted? Expected answer: freshly mapped confirm target.
12. What are the exact insert permission flags?
13. Is the resulting SI Draft? Expected answer: yes.
14. Is submit ever called? Expected answer: no.
15. Are GL/stock/payment operations explicitly called by this capability? Expected answer: no.
16. What happens with India Compliance absent?
17. What happens with India Compliance installed?
18. Were external GST APIs invoked during prepare? Expected answer: no.
19. What closed/on-hold behavior was actually observed/tested?
20. What pick-list/serial-batch prepare boundary was proven or retained?
21. Which tests passed, with exact counts/results?
22. Was any live transaction created? If yes, what disposable data; if no, clearly say not verified live.
23. Did Task 27 accidentally expose any Sales Invoice lifecycle/read/standalone tool? Expected answer: no.

---

# 17. Exact next task

After Task 27 implementation and review, do **not** jump directly into standalone creation.

The exact next task is:

```text
Task 28 - Sales Invoice Existing-Document Capabilities and Action-Scoped Lifecycle Policy
```

Task 28 will separately add/freeze:

```text
Sales Invoice read/search
Sales Invoice PDF
Sales Invoice email
Sales Invoice submit
Sales Invoice cancel
Sales Invoice delete
```

with an action-scoped authorization policy so that adding Sales Invoice does **not** implicitly enable generic update or child-add.

Then:

```text
Task 29 - Standalone Sales Invoice Creation Foundation
```

will add:

```text
prepare_sales_invoice
confirm_sales_invoice
```

for bounded direct Draft Sales Invoice creation when ERPNext Selling Settings and Customer policy permit it.

---

# 18. Final task instruction to the coding agent

Implement only this Task 27 after inspecting the current repository and installed ERPNext source. Preserve all frozen architecture and security boundaries. Reuse the existing Quotation -> Sales Order conversion strategy wherever it is sound. Use ERPNext's native Sales Order -> Sales Invoice mapper as the business authority. Keep prepare write-free with respect to Sales Invoice persistence and high-impact accounting/stock/compliance operations. Bind the effective native Draft preview to the existing approval system. On confirm, atomically claim approval, reload and re-map the Sales Order, detect material stale state including changes in billed quantities, then insert exactly one freshly mapped Draft Sales Invoice with normal permissions and native validation. Run focused and full regression tests, regenerate/check the tool catalog, and produce the required implementation report. Do not implement Task 28 or Task 29 in this task.
