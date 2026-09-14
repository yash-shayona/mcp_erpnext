# Task 42 — Delivery Note V1 Implementation Foundation (Sales Only)

## Status

**Implementation task**

This task follows the completed inspection report:

- `docs/inspect/DELIVERY_NOTE_NATIVE_FLOW_AUDIT.md`

The audit established that Delivery Note is a missing Sales-domain capability, but not a universal selling step. ERPNext must remain the workflow authority. Do not add a custom `BUSINESS_TYPE`, `USES_DELIVERY_NOTE`, or client-specific selling workflow switch.

---

# 1. Objective

Implement the first safe, production-oriented Delivery Note capability in `mcp_erpnext`, limited to the **Sales profile**, by reusing the existing ERPNext-native mapping, approval, read/query/aggregate, lifecycle, PDF/email, and direct/REST foundations.

The primary creation path in this task is:

```text
Submitted Sales Order
    ↓
ERPNext native sales_order.make_delivery_note(...)
    ↓
bounded Draft Delivery Note preview
    ↓
shared approval
    ↓
atomic approval claim
    ↓
fresh source reload + fresh native remap + fingerprint verification
    ↓
insert Draft Delivery Note only
```

This task must NOT submit the newly created Delivery Note automatically.

The implementation must remain generic across service businesses, stock-product businesses, and mixed businesses by letting ERPNext configuration, document state, Customer exceptions, Item metadata, warehouse/stock rules, and native validation decide whether a Delivery Note is valid or required.

---

# 2. Scope

## In scope

Implement all of the following:

1. `prepare_sales_order_to_delivery_note`
2. `confirm_sales_order_to_delivery_note`
3. `get_delivery_note`
4. `query_delivery_notes`
5. `aggregate_delivery_notes`
6. Add `Delivery Note` to the Sales-profile generic lifecycle allowlists for:
   - submit
   - cancel
   - delete
7. Add `Delivery Note` to the existing Sales generic PDF policy.
8. Add `Delivery Note` to the existing Sales generic email policy.
9. Add direct-backend support for every new public operation.
10. Add REST-backend support for every new public operation using fixed typed remote-operation handlers.
11. Add/update explicit typed contracts and tool catalog/registry entries.
12. Add static/unit tests plus target-site verification instructions.
13. Update architecture/tool documentation required by the repository's existing documentation convention.

## Explicitly out of scope

Do NOT implement any of the following in Task 42:

- standalone Delivery Note creation
- Delivery Note → Sales Invoice conversion
- Delivery Note returns
- partial child-row selection UX
- public exposure of native mapper flags
- `filtered_children`
- `for_reserved_stock`
- custom warehouse allocation logic
- automatic serial-number allocation
- automatic batch allocation
- arbitrary quantity overrides during SO → DN conversion
- arbitrary rate overrides during SO → DN conversion
- arbitrary tax overrides during SO → DN conversion
- Pick List creation
- Packing Slip creation
- Delivery Trip creation
- Shipment creation
- e-Waybill generation
- transporter workflows
- Accounts profile
- Payment Entry
- Purchase-profile changes
- custom product/service workflow configuration
- a global `BUSINESS_TYPE`
- `USES_DELIVERY_NOTE`
- any client-specific Quotation/SO/DN/SI workflow switch

---

# 3. Inputs / Repository Baseline

Use the current repository implementation as the primary MCP architecture reference.

Before changing code, inspect and reuse the current patterns for:

- Quotation → Sales Order native conversion
- Sales Order → Sales Invoice native conversion
- standalone Sales Invoice service
- Sales read/query/aggregate services
- `ApprovalStore`
- `claim_for_confirm_write()`
- lifecycle service and action allowlists
- generic PDF service
- generic email service
- typed contracts and contract registry/catalog
- Sales profile registration
- direct runtime execution
- Task 40 REST backend
- fixed REST remote operation registry
- existing public error/reference handling

Do not invent a second implementation pattern when an existing current pattern already solves the same concern.

---

# 4. ERPNext Native Authority

The SO → DN conversion must use the installed ERPNext native callable:

```python
erpnext.selling.doctype.sales_order.sales_order.make_delivery_note(
    source_name,
    target_doc=None,
    kwargs=None,
)
```

For the normal Task 42 path:

- pass the exact Sales Order name
- use `target_doc=None`
- do not expose raw `kwargs` to the LLM/client
- use only a fixed/empty server-owned argument object if required by the installed version
- do not pass caller-controlled permission bypasses
- do not reimplement ERPNext's row eligibility logic
- do not independently calculate deliverable quantities
- do not independently classify service rows as "non-deliverable"
- do not independently recreate taxes, Sales Team, packed items, warehouse defaults, remaining quantities, or cost-center logic

ERPNext native mapping and normal controller/defaulting/validation remain authoritative.

---

# 5. Public Tool Contracts

## 5.1 `prepare_sales_order_to_delivery_note`

### Required public input

Only:

```json
{
  "sales_order": "SAL-ORD-..."
}
```

No other business fields are allowed.

Reject unknown/extra input fields using the project's current typed-contract behavior.

### Forbidden public inputs

Do not expose:

- customer
- company
- item
- item_code
- qty
- rate
- warehouse
- taxes
- serial numbers
- batches
- mapper flags
- `target_doc`
- `filtered_children`
- `for_reserved_stock`
- `skip_item_mapping`
- `ignore_pricing_rule`
- permission bypass flags
- site
- Frappe user
- authenticated identity
- arbitrary DocType
- arbitrary method/import path

### Prepare behavior

The service must:

1. Resolve the current configured site through the existing runtime/backend configuration.
2. Use the current authenticated Frappe user/principal.
3. Load the exact Sales Order.
4. Require source Sales Order read permission.
5. Require Delivery Note create permission.
6. Reject an obviously non-ready source using a bounded MCP result where the existing architecture supports prechecks.
7. Call the ERPNext native SO → DN mapper with normal permissions.
8. Run only the native Draft defaulting/validation necessary to produce a trustworthy preview, following existing conversion-service conventions.
9. If the native mapped target contains no item rows, return a bounded result such as:
   - `NO_MAPPABLE_ITEMS`
10. Build a deterministic bounded preview.
11. Compute/store the deterministic approval fingerprint using the shared ApprovalStore.
12. Bind approval to:
   - configured site
   - authenticated user
   - action
   - exact source
   - material preview/fingerprint
13. Return the standard `InteractionDirective`.
14. Write no Delivery Note.
15. Write no Stock Ledger Entry.
16. Write no GL Entry.
17. Submit nothing.

### Minimum bounded preview

The preview should include only review-relevant data, such as:

- source Sales Order name
- source status/docstatus
- target DocType = Delivery Note
- customer
- company
- posting date/time where materially resolved
- currency
- commercial totals required for review
- mapped item rows:
  - item code
  - item name where already available
  - qty
  - UOM
  - rate
  - amount
  - warehouse
  - Sales Order row lineage (`so_detail` / source-row identity)
  - `against_sales_order`
- bounded Product Bundle / packed-item indicator or concise summary
- bounded serial/batch requirement/assignment indicator where permitted
- a clear warning that submit can create stock effects and, depending on ERPNext configuration/item types, accounting effects

Do NOT return:

- raw Delivery Note JSON
- arbitrary custom fields
- valuation rates
- complete Bin state
- raw SRE records
- complete serial-number inventory
- complete batch inventory
- ledger rows
- raw cache data
- secrets
- tracebacks
- arbitrary metadata

---

# 6. Confirm Contract

## 6.1 `confirm_sales_order_to_delivery_note`

### Required public input

Follow the repository's current approval-confirm contract.

Conceptually it must contain only:

- opaque approval token
- boolean confirmation/execution intent

Do not allow target-field mutation during confirm.

### Confirm behavior

The service must:

1. Validate normal confirmation semantics.
2. Atomically claim the approval using the shared `claim_for_confirm_write()` path.
3. Enforce site binding.
4. Enforce user binding.
5. Enforce action binding.
6. Enforce expiry.
7. Enforce one-shot use.
8. Reload the source Sales Order.
9. Re-run the native SO → DN mapper.
10. Recreate the bounded material preview.
11. Recompute the fingerprint.
12. Compare it to the approved fingerprint.
13. Reject stale/materially changed state.
14. Insert using normal Frappe permissions.
15. Keep every permission-bypass mechanism false/unset.
16. Create **Draft Delivery Note only**.
17. Never call `submit()`.
18. Never create or submit a downstream Sales Invoice.
19. Return a bounded result.

### Confirm result

Return only review/useful fields, for example:

- Delivery Note name
- DocType
- `docstatus`
- source Sales Order
- customer
- company
- currency
- bounded totals
- item count / bounded summary
- status needed by the caller

Do not return the entire Frappe document.

---

# 7. Source Eligibility and Native Behavior

The implementation must preserve native ERPNext behavior for at least these source cases:

## Submitted Sales Order

Eligible subject to:

- mapper row conditions
- permissions
- native controller/defaulting/validation

## Draft Sales Order

Return a safe bounded not-ready result. Do not attempt to manufacture a Delivery Note.

## Cancelled Sales Order

Fail safely through bounded source/native conversion handling.

## Closed / On Hold Sales Order

Do not invent an MCP-specific business rule beyond a safe obvious precheck.

Native ERPNext validation remains final authority.

## Fully delivered Sales Order / no remaining mappable rows

Return:

```text
NO_MAPPABLE_ITEMS
```

or the repository's equivalent bounded typed result.

Do not insert an empty Delivery Note.

## Partial delivery

Use the native mapper's remaining-quantity result.

Do not independently calculate or override it.

## Drop-ship / supplier-delivered rows

Let the native mapper exclude them.

Do not manufacture Delivery Note rows.

## Product Bundle

Preserve native mapper + packing-list behavior.

Return only a bounded parent/component summary where needed.

---

# 8. Service, Stock, and Mixed Items

Do not add a custom service/product heuristic.

The native target may contain:

- stock items
- non-stock/service items
- mixed rows
- packed stock components
- fixed-asset-sensitive rows

The MCP must report the target produced by ERPNext rather than filtering rows based on MCP assumptions.

For preview purposes:

- stock rows should visibly show warehouse where present
- non-stock rows should not cause MCP to invent warehouse requirements
- mixed documents must remain mixed when ERPNext maps them
- submit effects must be described as native ERPNext effects, not predicted ledger rows

---

# 9. Warehouse / Serial / Batch / Reservation Rules

Task 42 must not implement an allocation engine.

Preserve native ERPNext validation for:

- warehouse requirement
- warehouse/company compatibility
- disabled warehouses
- available stock / negative stock rules
- Stock Reservation behavior
- Serial and Batch Bundle behavior
- serial-number validation
- batch validation
- quality inspection
- immutable ledger constraints
- installed-app hooks

Do not expose:

- unbounded warehouse inventory
- unbounded serial-number lists
- unbounded batch lists
- raw reservation rows
- arbitrary `for_reserved_stock`

When serial/batch selection is required but unresolved, return a safe bounded result/validation consistent with current MCP error handling.

---

# 10. Delivery Note Read Capability

Implement:

```text
get_delivery_note
```

using the current field-aware Sales read pattern.

Requirements:

- exact Delivery Note name
- explicit allowed projection
- Frappe read permission enforced
- bounded child rows
- no raw document return
- no arbitrary custom/system fields
- no secrets/internal fields
- no SQL/raw query input

Create a Delivery Note-local read field policy.

Do not extend the legacy fixed-summary read path if the current Sales pattern has already replaced it.

---

# 11. Delivery Note Query Capability

Implement:

```text
query_delivery_notes
```

using the same current Sales field-aware query foundation.

Requirements:

- typed allowlisted filters
- typed allowlisted fields
- typed allowlisted sort
- bounded limit
- permission-aware `frappe.get_list(..., ignore_permissions=False)` or the repository's current equivalent
- deterministic safe behavior
- no SQL input
- no arbitrary filter-expression escape hatch
- no arbitrary field projection
- no unbounded result set

The implementation should be parallel to the existing current Sales DocType query services rather than introducing a new generic query engine.

---

# 12. Delivery Note Aggregate Capability

Implement:

```text
aggregate_delivery_notes
```

using the existing shared aggregate foundation.

Requirements:

- allow only supported metrics
- allow only supported fields
- allow only supported grouping
- use the repository's current Frappe v16 dictionary-expression convention
- enforce read permissions
- fail closed on unsupported metric/field/grouping
- avoid raw aggregate or SQL expressions
- preserve the existing aggregate response contract

At minimum, support only what the current shared Sales aggregate model safely supports, such as controlled `count` and approved `sum` operations.

Do not widen aggregate semantics just for Delivery Note.

---

# 13. Generic Lifecycle Integration

Add `Delivery Note` to Sales lifecycle policy for:

```text
submit
cancel
delete
```

only.

Do NOT add Delivery Note to generic:

- arbitrary update
- child-row add
- child-row update
- field mutation

## Submit

Use existing lifecycle approval semantics.

Native `doc.submit()` remains authoritative.

The operator must receive an adequate bounded preview/warning that submit may affect:

- Sales Order delivered state
- stock reservations
- serial/batch state
- Stock Ledger
- packed stock
- Pick List state
- future stock reposting
- possibly GL/accounting depending on ERPNext configuration/item behavior

Do not precompute or promise exact GL rows.

## Cancel

Use native `doc.cancel()`.

Do not bypass downstream-document checks.

If a submitted linked Sales Invoice or other native blocker exists, surface a bounded native business error.

Do not auto-cancel downstream documents.

## Delete

Use existing Frappe linked-document-aware delete logic.

Do not cascade delete:

- Sales Invoice
- return documents
- Packing Slip
- Shipment
- Delivery Trip
- downstream stock/accounting records

Respect the project's existing cancel-before-delete and linked-document policies.

---

# 14. Generic PDF Integration

Extend the existing generic PDF capability/policy to Delivery Note.

Requirements:

- Sales profile only
- exact Delivery Note target
- normal read/print permission
- native ERPNext/Frappe print format selection
- no raw HTML input
- no raw CSS input
- no raw Jinja template input
- no LLM-supplied print implementation

Reuse the existing generic PDF service rather than creating a Delivery Note-specific PDF engine.

---

# 15. Generic Email Integration

Extend the existing generic email capability/policy to Delivery Note.

Requirements:

- Sales profile only
- exact Delivery Note target
- existing prepare/confirm email flow
- existing approval semantics
- existing recipient rules
- read/email permission checks
- existing queued-mail behavior
- no raw HTML/CSS/Jinja contract
- no arbitrary automatic recipient discovery outside existing bounded rules

Do not create a Delivery Note-specific mail subsystem.

---

# 16. Sales Profile Registration

Register Delivery Note only in the **Sales** profile.

Update all required explicit registries/catalogs consistently.

Do not add Delivery Note to Purchase.

Do not introduce Accounts profile in this task.

Expected high-level Sales profile coverage after Task 42:

```text
Customer
Item
Quotation
Sales Order
Delivery Note
Sales Invoice
```

Delivery Note should participate only in the capabilities implemented in this task.

---

# 17. Direct Backend Requirements

All Delivery Note operations must work through the existing direct backend and normal authenticated Frappe execution context.

Requirements:

- configured `MCP_FRAPPE_SITE`
- no hard-coded site name
- no `yob.localhost`
- no fixed production/test site in code
- stdio identity must use the repository's existing configured user flow
- streamable HTTP identity must use the existing verified request identity flow
- no user fallback where current architecture forbids one
- no Administrator impersonation
- no permission bypass

Do not add a parallel runtime.

---

# 18. REST Backend Requirements

Task 40 REST architecture must receive equivalent Delivery Note support.

For every new public Delivery Note operation:

1. typed MCP wrapper produces JSON-safe REST arguments
2. `execute_tool_with_context(rest_arguments)` or current equivalent uses the fixed REST backend path
3. remote endpoint uses the static typed remote-operation registry
4. remote endpoint calls the same authoritative service logic
5. unknown operations fail closed
6. malformed payloads fail closed
7. arbitrary DocType dispatch remains impossible
8. arbitrary Python import/method dispatch remains impossible
9. caller cannot supply the remote identity
10. caller cannot supply a site override
11. approval tokens remain owned and validated by the authoritative remote side according to the current Task 40 architecture

Direct and REST must expose equivalent public contracts and bounded errors.

---

# 19. Approval Security Requirements

Reuse the shared ApprovalStore exactly.

Do not create a Delivery Note-specific approval store.

Required properties:

- site-bound
- user-bound
- action-bound
- expiring
- one-shot
- atomic claim
- stale-state detection
- deterministic fingerprint
- no approval-token reuse
- no token transfer across user/site/action
- `confirm=true` is execution intent, not an approval grant

Add concurrency/replay tests around confirmation.

---

# 20. Permission Requirements

At minimum:

## Prepare conversion

Require:

- Sales Order read
- Delivery Note create

Then rely on native mapping/defaulting/validation and normal Frappe permission checks for linked business objects.

## Confirm conversion

Recheck/reapply the normal authoritative permission path before insert.

## Read/query/aggregate

Require normal Delivery Note read permission.

## Submit/cancel/delete

Reuse current lifecycle permission semantics.

## PDF/email

Reuse existing permission checks.

Forbidden:

- `ignore_permissions=True` in MCP-owned Delivery Note code
- `doc.flags.ignore_permissions`
- caller-controlled permission flags
- Administrator impersonation
- role hard-coding that bypasses Frappe permission APIs

If the ERPNext public mapper internally uses a narrowly scoped framework/native permission behavior, do not copy that behavior into MCP code and do not expose it as a public control.

---

# 21. Runtime Metadata and Site-Specific Behavior

The audit did not claim that static ERPNext JSON metadata represents every target deployment.

Task 42 tests/verification must account for runtime metadata and configured-site behavior for at least:

- Delivery Note
- Delivery Note Item
- Sales Order
- Sales Order Item
- Sales Invoice
- Sales Invoice Item
- Customer
- Item
- Warehouse

Do not hard-code assumptions that runtime custom fields/property setters cannot change.

Do not access a site other than the configured target site.

No site name may be hard-coded anywhere in implementation or tests except clearly isolated test fixtures that do not affect production behavior.

---

# 22. India Compliance / Optional Apps

The current Bench has India Compliance installed, but the MCP must remain optional-app neutral.

Requirements:

- let standard Frappe/ERPNext hooks execute normally
- do not suppress India Compliance hooks
- do not manually reproduce India Compliance Delivery Note logic
- do not add e-Waybill generation in Task 42
- do not add transporter APIs in Task 42
- do not require GST/e-Waybill fields from the LLM unless native ERPNext validation for the actual configured site requires information through a future explicitly designed capability
- do not assume India Compliance exists on every deployment

Installed apps and site configuration remain runtime concerns.

---

# 23. Error Handling / Data Minimization

Use the current `public_error` / internal reference pattern.

Public responses may expose bounded semantic errors such as:

- source not ready
- permission denied
- no mappable items
- approval expired
- approval mismatch
- approval already used
- stale approval / source changed
- target validation failed
- linked document prevents cancel/delete
- native stock/warehouse/serial/batch requirement

Do not expose:

- Python tracebacks
- SQL
- filesystem paths
- Redis/cache internals
- secrets
- full native exception dumps
- arbitrary ERPNext document serialization
- complete ledger state
- full stock/Bin state
- unbounded serial/batch data

Preserve an internal correlation/reference ID according to the existing observability pattern.

---

# 24. Implementation Steps

Follow this order.

## Step 1 — Reinspect existing implementation

Before editing, inspect the current implementations of:

- Quotation → Sales Order
- Sales Order → Sales Invoice
- Sales Invoice service
- Sales read/query/aggregate
- lifecycle
- PDF
- email
- approval store
- profile registration
- contracts
- REST registry/handlers

Record any material pattern differences from the audit before deciding how to implement Delivery Note.

Do not blindly copy stale patterns.

## Step 2 — Add typed Delivery Note contracts

Add explicit models/contracts for:

- prepare SO → DN
- confirm SO → DN
- get DN
- query DN
- aggregate DN
- corresponding outputs

Keep extra fields forbidden according to current convention.

## Step 3 — Implement SO → DN service

Create the Delivery Note conversion service using the ERPNext native mapper.

Implement:

- permission-safe source loading
- target create permission
- source readiness handling
- native mapping
- bounded validation/defaulting
- `NO_MAPPABLE_ITEMS`
- preview projection
- deterministic fingerprint
- shared approval storage
- safe error mapping

## Step 4 — Implement confirm path

Implement:

- atomic approval claim
- source reload
- native remap
- fresh preview/fingerprint
- stale detection
- normal-permission Draft insert
- bounded result

No submit.

## Step 5 — Implement read

Add Delivery Note-local field policy and `get_delivery_note`.

## Step 6 — Implement query

Add `query_delivery_notes` on the current Sales query foundation.

## Step 7 — Implement aggregate

Add `aggregate_delivery_notes` on the shared aggregate foundation.

## Step 8 — Lifecycle allowlists

Add Delivery Note only to:

- submit
- cancel
- delete

Update any profile/doc/action policies required by the current architecture.

## Step 9 — PDF/email policies

Add Delivery Note to the shared Sales generic PDF/email policy.

## Step 10 — Sales tool/profile registration

Register all explicit public Delivery Note capabilities in the Sales profile/catalog.

Purchase remains unchanged.

## Step 11 — REST parity

Add a fixed typed REST operation for every new public operation.

Do not add generic dispatch.

## Step 12 — Tests

Implement all required tests in Section 26.

## Step 13 — Documentation

Regenerate/update current tool catalog and architecture documentation according to repository conventions.

Document the deliberate V1 omissions.

---

# 25. Allowed Changes

Changes are allowed only where necessary for the above scope, including existing equivalents of:

- `mcp_erpnext/tools/selling/...`
- `mcp_erpnext/services/selling/...`
- Sales read/query policies/services
- typed contracts
- contract registry/catalog
- `mcp_erpnext/profiles/sales.py`
- lifecycle policy/allowlists
- generic PDF/email DocType policy
- REST typed operation registry/handlers
- tests
- repository documentation generated/maintained for public tools

Refactor shared code only when:

1. Delivery Note exposes a real duplication/problem,
2. existing behavior remains compatible,
3. tests prove no regression,
4. the refactor does not widen Task 42 into unrelated cleanup.

---

# 26. Required Test Matrix

Implement unit/static tests and preserve existing regression tests.

At minimum test all of the following.

## A. Registration / profile

1. Delivery Note tools appear only in Sales.
2. Purchase profile remains unchanged.
3. Accounts profile is not introduced.
4. Tool names/contracts are deterministic.
5. Extra contract fields fail closed.

## B. SO → DN prepare

6. Submitted permitted SO maps to a Draft DN preview.
7. Prepare performs no insert.
8. Prepare performs no submit.
9. Prepare creates no stock/GL data.
10. Draft SO returns bounded not-ready behavior.
11. Cancelled SO fails safely.
12. Closed/On Hold behavior remains native/bounded.
13. Fully delivered/no remaining rows returns `NO_MAPPABLE_ITEMS`.
14. Partial delivery uses native remaining quantity.
15. Drop-ship/supplier-delivered rows remain excluded by native mapping.
16. Product Bundle behavior is preserved.
17. Stock-only mapping remains native.
18. Service-only mapping remains native.
19. Mixed stock/service mapping remains native.
20. No MCP service/product heuristic filters the target.

## C. Warehouse / stock-sensitive validation

21. Missing/default warehouse behavior remains native.
22. Warehouse mismatch/disabled behavior remains native.
23. Reservation mismatch remains native/bounded.
24. Serial/batch requirement remains native/bounded.
25. Quality/stock validation remains native/bounded.
26. No raw inventory is exposed.

## D. Permissions

27. Source SO read denial fails closed.
28. Delivery Note create denial fails closed.
29. Mapper receives no public permission-bypass flag.
30. No Administrator impersonation occurs.

## E. Approval

31. Prepare stores shared approval.
32. Correct user/site/action can confirm.
33. Wrong user fails.
34. Wrong site fails.
35. Wrong action fails.
36. Expired token fails.
37. `confirm=false` does not write.
38. Repeated token use fails.
39. Concurrent repeated confirmation results in at most one successful write.
40. Material source change after prepare causes stale/fingerprint rejection.

## F. Confirm

41. Fresh remap occurs.
42. Fresh fingerprint is compared.
43. Successful confirm inserts exactly one Draft Delivery Note.
44. Result `docstatus == 0`.
45. `against_sales_order` is preserved.
46. `so_detail` lineage is preserved.
47. Confirm does not submit.
48. Confirm does not create Sales Invoice.

## G. Read/query/aggregate

49. `get_delivery_note` enforces read permission.
50. Unsupported read fields fail closed.
51. Child rows are bounded.
52. `query_delivery_notes` enforces read permission.
53. unsupported filter/sort/projection fails closed.
54. query result limit is bounded.
55. `aggregate_delivery_notes` uses shared aggregate engine.
56. unsupported metric/group/field fails closed.
57. Frappe v16 dict aggregate syntax is preserved.
58. no raw SQL input exists.

## H. Lifecycle

59. Delivery Note submit is allowed only through existing generic lifecycle.
60. Submit requires existing approval semantics.
61. Native submit is called.
62. Cancel requires existing approval semantics.
63. Native cancel is called.
64. Linked submitted Sales Invoice prevents cancel according to native behavior.
65. Delete uses linked-document-safe Frappe behavior.
66. No downstream document is auto-cancelled/deleted.
67. Delivery Note is NOT enabled for generic arbitrary update.
68. Delivery Note is NOT enabled for generic child mutation.

## I. PDF/email

69. Generic PDF accepts Delivery Note under Sales policy.
70. PDF uses native print behavior.
71. PDF does not accept HTML/CSS/Jinja implementation input.
72. Generic email accepts Delivery Note under Sales policy.
73. Email uses existing prepare/confirm/queue behavior.
74. No new Delivery Note-specific email engine exists.

## J. REST parity

75. Every new public DN wrapper produces typed JSON-safe REST arguments.
76. Every DN public operation has a fixed remote registry entry.
77. Unknown operation fails closed.
78. malformed payload fails closed.
79. arbitrary DocType/method/import-path dispatch remains impossible.
80. direct and REST public success shapes conform.
81. direct and REST bounded error semantics conform.
82. REST approval remains authoritative on the remote side under current architecture.

## K. Regression

83. Quotation create/read/query/aggregate/conversion tests remain green.
84. Sales Order create/read/query/aggregate/lifecycle tests remain green.
85. Sales Invoice create/read/query/aggregate/lifecycle tests remain green.
86. existing SO → SI conversion remains green.
87. existing `DELIVERY_NOTE_REQUIRED` behavior remains green.
88. Customer tests remain green.
89. Item tests remain green.
90. shared ApprovalStore tests remain green.
91. Task 40 REST tests remain green.
92. Purchase profile/tests remain green.

---

# 27. Target-Site Verification

In addition to unit/static tests, provide a verification report/checklist for an explicitly authorized test site.

Do not mutate production data.

Verify at least:

- configured site is taken from config, not hard-coded
- current installed ERPNext version
- runtime Delivery Note metadata
- runtime Delivery Note Item metadata
- active Selling Settings relevant to SO/DN
- current user's permissions
- Delivery Note create permission
- one authorized submitted Sales Order with remaining deliverable rows
- one partial-delivery scenario if safely available
- warehouse behavior
- one stock-item scenario if safely available
- one service/mixed scenario if safely available
- REST remote API principal behavior when REST backend is configured
- India Compliance presence/absence is treated as runtime state

If a live scenario is unavailable, document it as **not verified**. Do not manufacture production records merely to make the report appear complete unless the test environment explicitly authorizes throwaway records.

---

# 28. Acceptance Criteria

Task 42 is complete only when all of the following are true:

1. Sales profile exposes SO → Draft DN conversion.
2. Conversion uses ERPNext native `make_delivery_note`.
3. Public input is only the exact Sales Order identity plus normal approval confirmation inputs.
4. Prepare performs no write.
5. Confirm inserts Draft only.
6. No automatic submit occurs.
7. Shared site/user/action-bound one-shot approval is reused.
8. Fresh remap + fingerprint stale-state protection exists.
9. Permission bypass is not introduced.
10. `get_delivery_note` exists with bounded field policy.
11. `query_delivery_notes` exists using current field-aware Sales architecture.
12. `aggregate_delivery_notes` exists using the shared aggregate service.
13. Delivery Note is added to Sales lifecycle only for submit/cancel/delete.
14. Delivery Note is supported by generic PDF/email.
15. Direct backend works.
16. REST backend has equivalent fixed typed operations.
17. Purchase is unchanged.
18. Accounts is untouched.
19. No standalone DN exists.
20. No DN → SI tool exists yet.
21. No return-DN capability exists.
22. No custom service/product or workflow configuration exists.
23. Existing Sales and Purchase regressions remain green.
24. Tool/catalog/docs accurately describe V1 limitations.

---

# 29. Expected Result

After Task 42, the generic Sales profile should safely support:

```text
Customer
   ↓
Quotation
   ↓
Sales Order
   ↓
prepare_sales_order_to_delivery_note
   ↓
human/agent approval
   ↓
confirm_sales_order_to_delivery_note
   ↓
Draft Delivery Note
   ↓
generic lifecycle submit
```

and it should also support:

```text
get_delivery_note
query_delivery_notes
aggregate_delivery_notes
generic PDF
generic email
generic submit/cancel/delete
```

The implementation must remain valid for different client businesses without requiring a custom product/service workflow mode.

The server must still let ERPNext decide whether a Delivery Note is actually required or valid in the current transaction.

---

# 30. Limitations After Task 42

The following gaps are intentional after completion:

- cannot create a standalone Delivery Note
- cannot convert Delivery Note → Sales Invoice yet
- cannot create return Delivery Note
- cannot expose child-row selection during SO mapping
- cannot allocate serial/batch inventory itself
- cannot create Pick List/Packing Slip/Shipment/Delivery Trip
- cannot generate e-Waybill through MCP
- Accounts/Payment Entry not started yet

These are not Task 42 defects.

---

# 31. Deliverable Report

After implementation, create:

```text
docs/inspect/DELIVERY_NOTE_V1_IMPLEMENTATION_REPORT.md
```

The report must contain:

1. exact files changed
2. public tools added
3. exact public contracts
4. native ERPNext callables used
5. approval/fingerprint behavior
6. permissions behavior
7. direct-backend behavior
8. REST-backend behavior
9. read/query/aggregate field policies
10. lifecycle changes
11. PDF/email policy changes
12. all tests added
13. test execution results
14. live-site checks performed
15. checks not performed and why
16. India Compliance observations
17. known limitations
18. regression results
19. confirmation that Purchase and Accounts were untouched
20. confirmation that no site name was hard-coded

Do not claim verification for anything that was not actually tested.

---

# 32. Exact Next Task

If Task 42 passes its acceptance criteria, the next task is frozen as:

## Task 43 — Delivery Note → Sales Invoice Native Conversion

Task 43 should implement the native:

```python
erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice(...)
```

flow using the same proven pattern:

```text
prepare
→ shared approval
→ atomic claim
→ fresh DN reload
→ fresh native remap
→ fingerprint comparison
→ Draft Sales Invoice insert only
```

Task 43 must remain a separate task because DN → SI introduces its own:

- pending invoiced quantity rules
- returned quantity handling
- already-invoiced handling
- DN row lineage
- native mapping hooks, including optional installed-app behavior

Do not implement Task 43 inside Task 42.
