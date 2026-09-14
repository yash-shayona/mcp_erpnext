# Task 43 — Delivery Note → Sales Invoice Native Conversion

## Status

**Implementation task**

This task follows:

- Task 41 — Delivery Note Native Flow Audit
- Task 42 — Delivery Note V1 Implementation Foundation

Task 42 has already added the Sales Order → Draft Delivery Note flow and Delivery Note read/query/aggregate/lifecycle/PDF/email support.

This task adds only the missing **Delivery Note → Draft Sales Invoice** conversion path.

---

# 1. Objective

Implement a safe, typed, approval-gated Delivery Note → Sales Invoice conversion for the Sales profile by calling ERPNext's installed native mapper.

Required flow:

```text
Submitted Delivery Note
    ↓
ERPNext native Delivery Note → Sales Invoice mapper
    ↓
bounded Draft Sales Invoice preview
    ↓
shared approval
    ↓
atomic approval claim
    ↓
fresh Delivery Note reload
    ↓
fresh native remap
    ↓
fresh preview + fingerprint comparison
    ↓
insert Draft Sales Invoice only
```

The conversion must reuse the architecture already proven by the existing:

- Quotation → Sales Order conversion
- Sales Order → Sales Invoice conversion
- Sales Order → Delivery Note conversion

Do not create another mapping framework.

---

# 2. Native ERPNext Authority

Use the installed ERPNext native callable:

```python
erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice(
    source_name,
    target_doc=None,
    args=None,
)
```

The installed Task 41 audit confirmed this callable as the native Delivery Note → Sales Invoice mapper.

Do not reproduce the field map manually.

Do not calculate pending invoice quantity independently.

Do not copy Delivery Note rows into Sales Invoice rows manually.

Do not recalculate returned quantities in MCP.

Do not duplicate ERPNext tax/default/payment-term logic.

ERPNext remains authoritative for:

- Delivery Note source eligibility
- pending billable quantity
- returned quantity
- already invoiced quantity
- item mapping
- Delivery Note row linkage
- Sales Order row linkage
- customer/company/currency consistency
- taxes
- Sales Team
- cost center
- payment terms
- installed-app mapping hooks
- target validation

---

# 3. Scope

## In scope

Implement only:

1. `prepare_delivery_note_to_sales_invoice`
2. `confirm_delivery_note_to_sales_invoice`
3. typed input/output contracts
4. contract registry/tool catalog entries
5. Sales-profile registration
6. direct-backend support
7. fixed typed REST-backend operation support
8. shared approval/fingerprint/stale-state behavior
9. bounded errors
10. unit/static tests
11. authorized target-site verification instructions
12. implementation report/documentation updates

## Explicitly out of scope

Do NOT implement or modify:

- standalone Sales Invoice creation
- Sales Order → Sales Invoice conversion
- Sales Order → Delivery Note conversion
- Delivery Note standalone creation
- Sales Invoice submit/cancel/delete behavior
- Delivery Note submit/cancel/delete behavior
- Delivery Note returns
- Sales Invoice returns / Credit Notes
- Payment Entry
- Accounts profile
- Purchase profile
- stock allocation
- serial/batch allocation
- warehouse selection
- arbitrary child-row selection
- arbitrary quantity override
- arbitrary rate override
- arbitrary tax override
- raw mapper args
- e-Waybill generation
- transporter workflow
- custom workflow configuration
- permission-boundary cleanup/refactor across existing services

The permission/pre-flight cleanup discussed separately is **not part of Task 43**. Do not widen this task into a cross-service permission refactor.

---

# 4. Repository Inspection Before Changes

Before editing, inspect the current post-Task-42 repository and reuse the actual current implementations of:

- Quotation → Sales Order conversion
- Sales Order → Sales Invoice conversion
- Sales Order → Delivery Note conversion
- shared `ApprovalStore`
- `claim_for_confirm_write()`
- fingerprint helpers/projection conventions
- public error/reference handling
- Sales profile registration
- typed contracts
- REST fixed remote operation registry
- direct runtime
- generated `docs/TOOLS.md`

If Task 42 implementation differs materially from the earlier task specification, follow the current proven architecture where it is sound.

Do not blindly copy stale code from an older task file.

---

# 5. Public Prepare Contract

Add:

```text
prepare_delivery_note_to_sales_invoice
```

## Input

Only:

```json
{
  "delivery_note": "MAT-DN-..."
}
```

or the site's actual Delivery Note naming series value.

The public contract must accept only the exact Delivery Note name.

Extra fields must be forbidden.

## Forbidden public inputs

Do not expose:

- customer
- company
- posting date
- due date
- item code
- qty
- rate
- warehouse
- taxes
- accounts
- income account
- cost center
- serial numbers
- batch numbers
- `target_doc`
- mapper `args`
- `filtered_children`
- permission flags
- `ignore_permissions`
- site
- Frappe user
- arbitrary DocType
- arbitrary Python method/import path

---

# 6. Prepare Behavior

The prepare service must:

1. run under the current configured Frappe site/backend context;
2. use the current authenticated Frappe identity;
3. call the installed native Delivery Note → Sales Invoice mapper;
4. use normal Frappe/ERPNext permissions;
5. expose no caller-controlled bypass;
6. require a native-valid source Delivery Note;
7. preserve native row-selection and pending-quantity behavior;
8. build a bounded Sales Invoice preview;
9. return a bounded no-work result when nothing remains to invoice;
10. compute a deterministic material fingerprint;
11. store the approval using the shared site/user/action-bound ApprovalStore;
12. return the standard interaction/approval directive;
13. perform no document insert;
14. perform no submit;
15. perform no GL posting;
16. perform no Payment Ledger posting;
17. perform no stock posting.

---

# 7. Source Readiness

The normal source is a **Submitted Delivery Note**.

The installed mapper requires a submitted source.

Handle at least:

## Draft Delivery Note

Return a bounded source-not-ready/native conversion result.

Do not create a Sales Invoice.

## Submitted Delivery Note with pending billable quantity

Prepare a normal Draft Sales Invoice preview.

## Cancelled Delivery Note

Fail safely through the native/bounded conversion path.

## Fully invoiced Delivery Note

Do not create an empty Sales Invoice.

Return a bounded result such as:

```text
NO_MAPPABLE_ITEMS
```

or an equivalent project-standard code that clearly means there is no remaining invoiceable content.

## Partially invoiced Delivery Note

ERPNext must calculate the remaining invoiceable quantity.

MCP must not calculate:

```text
DN qty - invoiced qty
```

itself.

## Returned quantity

ERPNext's native mapper must remain authoritative for the quantity remaining after submitted Delivery Note returns.

Do not reproduce the return formula in MCP.

## Delivery Note with Sales Order lineage

Preserve the native mapping of:

```text
Delivery Note Item -> Sales Invoice Item
delivery_note
dn_detail
sales_order / against_sales_order lineage
so_detail
```

where ERPNext provides it.

---

# 8. Native Mapper Arguments

Call:

```python
make_sales_invoice(
    source_name=<exact Delivery Note>,
    target_doc=None,
    args=None,
)
```

or the installed-version equivalent verified from the current source.

Do not expose `args` publicly.

If the installed ERPNext version requires a server-owned empty argument object rather than `None`, use a fixed internal value only.

No model/client-supplied mapper option is allowed.

---

# 9. Preview

Return only information necessary for a human/agent to review the Sales Invoice that ERPNext proposes.

At minimum, where available:

- source Delivery Note
- target DocType = Sales Invoice
- customer
- company
- posting date
- due date where natively resolved
- currency
- item rows:
  - item code
  - item name
  - qty
  - UOM
  - rate
  - amount
  - Delivery Note row lineage (`dn_detail`)
  - Delivery Note name
  - Sales Order / SO row lineage when present
- bounded taxes/charges summary where already part of the existing SI preview convention
- net total
- taxes total
- grand total
- outstanding amount only if meaningful on the unsaved native Draft and already part of the current bounded SI convention

Do not return:

- raw Sales Invoice JSON
- arbitrary custom fields
- all metadata
- secrets
- raw account ledgers
- complete GL projections
- Bin/stock state
- raw Stock Ledger state
- complete serial/batch inventories
- internal cache/fingerprint material
- stack traces

---

# 10. Important Stock Boundary

A Delivery Note has already represented the delivery/stock movement when submitted.

The DN → SI conversion must not invent a second stock movement.

Do not force:

```text
update_stock = 1
```

on the mapped Sales Invoice.

Preserve the installed native mapper/default behavior.

Add a regression test proving MCP does not independently enable stock updating or modify stock-related mapping state.

Task 43 creates a Draft Sales Invoice only. Existing Sales Invoice submit behavior remains unchanged.

---

# 11. Rate Preservation / Native-Version Regression

A recent ERPNext v16 issue affected item rates in Delivery Note → Sales Invoice mapping in some v16 releases.

Task 43 must therefore include a regression test using a Delivery Note with multiple rows having different rates.

The test must verify the **installed native mapper result** is preserved by MCP.

Rules:

- do not "fix" native ERPNext rates in MCP;
- do not copy source rates manually;
- do not add an MCP rate-repair algorithm;
- if the installed ERPNext mapper itself produces incorrect rates, record it as an installed ERPNext/version issue in the implementation report and keep MCP behavior native.

The MCP bridge must never silently diverge from ERPNext's native mapping to work around an upstream accounting/commercial bug.

---

# 12. India Compliance / Optional-App Mapping

The Task 41 audit confirmed that installed India Compliance hooks can copy defined e-Waybill-related invoice fields during Delivery Note → Sales Invoice mapping.

Therefore:

- call the native mapper;
- allow normal installed hooks to run;
- do not manually copy India Compliance fields;
- do not require India Compliance to exist;
- do not add e-Waybill generation;
- do not add transporter logic;
- do not expose GST/e-Waybill internals to the LLM unless already part of an existing bounded public contract.

The implementation must remain valid when India Compliance is absent.

---

# 13. Prepare Approval

Reuse the shared ApprovalStore.

The approval must be:

- site-bound
- user-bound
- action-bound
- source-bound
- expiring
- one-shot
- atomically claimable
- fingerprint-protected

Use a deterministic fingerprint of the material bounded conversion preview.

Do not create a Delivery Note-specific approval store.

Do not invent a new approval field such as:

```text
approval_needed
```

Use the existing standard interaction directive/approval contract.

---

# 14. Confirm Contract

Add:

```text
confirm_delivery_note_to_sales_invoice
```

Use the same public confirmation shape as the current approved conversion tools.

Conceptually:

```json
{
  "approval_token": "...",
  "confirm": true
}
```

Do not accept any Sales Invoice business fields during confirmation.

---

# 15. Confirm Behavior

On confirmation:

1. require valid confirmation intent according to the current shared contract;
2. atomically claim the approval;
3. enforce site binding;
4. enforce user binding;
5. enforce action binding;
6. enforce token expiry;
7. enforce one-shot semantics;
8. reload/re-evaluate the source through the authoritative conversion path;
9. call the native Delivery Note → Sales Invoice mapper again;
10. recreate the bounded preview;
11. recompute the fingerprint;
12. compare it with the approved fingerprint;
13. reject stale/materially changed state;
14. insert the Sales Invoice using normal Frappe permissions;
15. keep the target as `docstatus == 0`;
16. never call `submit()`;
17. never create a Payment Entry;
18. never create a Credit Note;
19. never modify/cancel the source Delivery Note.

---

# 16. Stale-State Conditions

The confirmation must fail safely if material state changed after prepare.

Examples include:

- Delivery Note was cancelled;
- Delivery Note was modified in a material way;
- another Sales Invoice consumed some/all pending quantity;
- a submitted return changed the pending quantity;
- native mapper output changed;
- taxes/defaults materially changed;
- mapped totals materially changed;
- mapped rows/qty/rates changed.

Do not try to reconcile an old approval with a new native result.

Require a new prepare/approval.

---

# 17. Confirmation Result

Return only a bounded created-document result such as:

- Sales Invoice name
- DocType
- `docstatus`
- source Delivery Note
- customer
- company
- currency
- bounded totals
- bounded item count/summary
- relevant linkage

Do not return the full Sales Invoice document.

---

# 18. Permissions

Use normal Frappe/ERPNext permission behavior.

No permission bypass may be added.

Forbidden:

- `ignore_permissions=True` in MCP-owned conversion code
- `doc.flags.ignore_permissions`
- Administrator impersonation
- caller-controlled identity
- caller-controlled site
- role-name authorization logic
- custom permission matrices

Important:

The broader permission pre-flight cleanup discussed separately is deferred.

For Task 43:

- preserve compatibility with the current proven conversion-service architecture;
- do not perform a cross-service permission refactor;
- do not introduce additional independent permission business logic;
- ensure the native mapper and final insert run with normal permissions.

Any permission exception exposed publicly must use the current bounded error/reference convention.

---

# 19. Existing Sales Invoice Capabilities

Do NOT reimplement:

- `get_sales_invoice`
- `query_sales_invoices`
- `aggregate_sales_invoices`
- Sales Invoice submit
- Sales Invoice cancel
- Sales Invoice delete
- Sales Invoice PDF
- Sales Invoice email

These already exist.

A Sales Invoice created through Task 43 must automatically work with the existing Sales Invoice capabilities because it is a normal native Draft Sales Invoice.

If an existing policy/registry does not recognize such an SI for reasons unrelated to document identity, fix only the smallest compatibility issue necessary.

---

# 20. Sales Profile Registration

Register only the two new conversion tools in the Sales profile:

```text
prepare_delivery_note_to_sales_invoice
confirm_delivery_note_to_sales_invoice
```

Do not add them to Purchase.

Do not create Accounts profile.

Do not expose them in unrelated profiles.

---

# 21. Direct Backend

Both tools must support the current direct execution path.

Requirements:

- configured site only
- no hard-coded site
- current authenticated Frappe user
- normal Frappe permissions
- same service authority as existing Sales conversions
- same public contract
- same bounded errors
- JSON-safe tool output

---

# 22. REST Backend

Add fixed typed remote operations for both new public tools.

Required flow:

```text
typed MCP wrapper
    ↓
JSON-safe REST arguments
    ↓
existing REST execution boundary
    ↓
fixed operation name
    ↓
remote static registry
    ↓
same authoritative DN → SI service
```

Do not add:

- arbitrary method dispatch
- arbitrary DocType dispatch
- arbitrary import path
- caller-supplied identity
- caller-supplied site
- generic "execute Python method" endpoint

Approval tokens must remain authoritative where the current Task 40/42 REST architecture expects them to live.

Direct and REST success/error contracts must remain equivalent.

---

# 23. Error Handling

Use the current bounded public-error/reference system.

Handle at least:

- source not found
- source not ready
- permission denied
- no remaining invoiceable items
- native mapping validation failure
- approval expired
- approval already used
- approval/action mismatch
- approval user/site mismatch
- stale source / fingerprint mismatch
- target insert validation failure

Do not expose:

- traceback
- SQL
- filesystem path
- Redis/cache internals
- raw native exception dumps
- secret/config values

---

# 24. Required Tests

Add tests covering at least the following.

## A. Registration/contracts

1. both new tools are registered in Sales;
2. neither tool appears in Purchase;
3. no Accounts profile is introduced;
4. prepare accepts only `delivery_note`;
5. confirm accepts only the current approval fields;
6. extra fields fail closed;
7. contract registry/catalog is deterministic.

## B. Prepare

8. submitted permitted DN with pending quantity produces a Draft SI preview;
9. prepare writes no Sales Invoice;
10. prepare submits nothing;
11. prepare creates no GL/Payment Entry/stock movement;
12. Draft DN fails safely;
13. cancelled DN fails safely;
14. fully invoiced DN returns bounded no-mappable behavior;
15. partially invoiced DN maps only native remaining quantity;
16. returned quantity affects mapping only through native ERPNext logic;
17. native Delivery Note linkage is preserved;
18. native Sales Order/SO-row lineage is preserved when present.

## C. Commercial mapping

19. customer/company/currency come from native mapping;
20. taxes/defaults come from native mapping;
21. payment-term/default behavior remains native;
22. multi-item DN with different rates preserves the installed native mapper result;
23. MCP contains no rate-repair algorithm;
24. MCP contains no manual pending-qty formula.

## D. Stock boundary

25. MCP does not force `update_stock=1`;
26. prepare creates no Stock Ledger Entry;
27. confirm Draft insert creates no second delivery/stock transaction;
28. source Delivery Note remains unchanged.

## E. Approval

29. prepare stores shared approval;
30. correct user/site/action may confirm;
31. wrong user fails;
32. wrong site fails;
33. wrong action fails;
34. expired token fails;
35. `confirm=false` writes nothing;
36. repeated token fails;
37. concurrent repeat yields at most one successful write;
38. material source change causes stale rejection;
39. newly submitted SI against the same DN causing pending-qty change causes stale rejection;
40. return-state change causes stale rejection.

## F. Confirm

41. confirm remaps natively;
42. fresh fingerprint is recomputed;
43. successful confirm inserts exactly one Sales Invoice;
44. created Sales Invoice has `docstatus == 0`;
45. confirm never calls `submit()`;
46. confirm does not create Payment Entry;
47. confirm does not cancel/modify DN;
48. created SI contains native `delivery_note` / `dn_detail` lineage.

## G. Optional apps

49. no India Compliance-specific dependency is required by MCP;
50. installed mapping hooks are not suppressed;
51. no e-Waybill generation code is added;
52. no transporter logic is added.

## H. Permissions/security

53. normal native permissions remain enabled;
54. no public permission-bypass field exists;
55. no MCP-owned Administrator impersonation exists;
56. no hard-coded user/site exists;
57. permission errors are bounded.

## I. REST parity

58. prepare has fixed typed REST operation;
59. confirm has fixed typed REST operation;
60. unknown remote operation fails closed;
61. malformed payload fails closed;
62. arbitrary DocType/method/import dispatch remains impossible;
63. direct/REST success shapes conform;
64. direct/REST bounded errors conform.

## J. Regression

65. Task 42 SO → DN tools remain green;
66. existing SO → SI conversion remains green;
67. standalone SI creation remains green;
68. SI read/query/aggregate remains green;
69. SI lifecycle remains green;
70. DN read/query/aggregate/lifecycle remains green;
71. Quotation/SO conversion remains green;
72. shared approval tests remain green;
73. REST tests remain green;
74. Purchase profile remains unchanged.

---

# 25. Live / Target-Site Verification

Where an authorized non-production/throwaway scenario is available, verify:

1. configured site is used; no site is hard-coded;
2. submitted Delivery Note with pending invoiceable quantity exists;
3. prepare returns the expected native Draft SI preview;
4. prepare creates no SI;
5. confirm creates exactly one Draft SI;
6. DN row lineage is present;
7. Sales Order lineage is preserved when applicable;
8. distinct item rates map correctly under the installed ERPNext version;
9. partial invoicing behaves natively;
10. fully invoiced DN is rejected/no-op safely;
11. returned quantity behavior is native;
12. direct backend works;
13. REST backend works if configured;
14. current authenticated user's permissions are honored;
15. India Compliance hooks, if installed/enabled, are allowed to run normally.

If a case cannot be safely tested, mark it **not verified**.

Do not create production transactions merely to satisfy the report.

---

# 26. Acceptance Criteria

Task 43 is complete only when:

1. `prepare_delivery_note_to_sales_invoice` exists;
2. `confirm_delivery_note_to_sales_invoice` exists;
3. only an exact Delivery Note name is accepted for prepare;
4. ERPNext native `delivery_note.make_sales_invoice` is used;
5. no field map is reimplemented in MCP;
6. no pending quantity formula is reimplemented in MCP;
7. no return quantity formula is reimplemented in MCP;
8. prepare writes nothing;
9. confirm uses shared atomic approval;
10. confirm remaps and verifies a fresh fingerprint;
11. confirm inserts Draft Sales Invoice only;
12. no automatic Sales Invoice submit occurs;
13. no Payment Entry is created;
14. no second stock movement is introduced;
15. DN/SI native lineage is preserved;
16. direct backend works;
17. REST backend has fixed typed parity;
18. existing SI read/query/aggregate/lifecycle/PDF/email are reused;
19. Purchase remains unchanged;
20. Accounts remains untouched;
21. no standalone DN/SI redesign is introduced;
22. no permission-boundary global refactor is mixed into this task;
23. existing Sales regressions remain green;
24. implementation report accurately records verified and unverified behavior.

---

# 27. Expected Business Flow After Task 43

For a stock/product business using Delivery Notes:

```text
Quotation
    ↓
Sales Order
    ↓
Delivery Note
    ↓
submit Delivery Note
    ↓
prepare_delivery_note_to_sales_invoice
    ↓
approval
    ↓
confirm_delivery_note_to_sales_invoice
    ↓
Draft Sales Invoice
    ↓
existing generic Sales Invoice submit
    ↓
ERPNext accounting/receivable effects
```

For service/direct-billing businesses, the existing path remains:

```text
Sales Order
    ↓
Sales Invoice
```

Task 43 must not force Delivery Note into every Sales workflow.

---

# 28. Deliverable Report

After implementation, create:

```text
docs/inspect/DELIVERY_NOTE_TO_SALES_INVOICE_IMPLEMENTATION_REPORT.md
```

The report must include:

1. exact files changed;
2. public tools added;
3. exact public contracts;
4. exact installed native callable used;
5. mapper arguments used;
6. bounded preview fields;
7. fingerprint material;
8. approval action/site/user binding;
9. stale-state behavior;
10. permission behavior;
11. direct backend behavior;
12. REST backend behavior;
13. India Compliance/optional-app observations;
14. distinct-rate regression result;
15. partial invoicing result;
16. returned-quantity result;
17. full-invoicing/no-mappable result;
18. tests added;
19. exact test commands run;
20. pass/fail/error counts;
21. live-site checks performed;
22. checks not performed and why;
23. regressions;
24. confirmation that Purchase and Accounts were untouched;
25. confirmation that no site/user was hard-coded;
26. confirmation that no stock, rate, pending-qty, return, or tax repair logic was added to MCP.

Do not claim a test passed if it was not actually executed.

---

# 29. Exact Next Step After Task 43

Do not automatically implement the next feature.

After Task 43, report the resulting full Sales business flow and remaining gaps first.

At that point we can decide whether to:

- close any remaining Sales-domain gap, or
- move to the Accounts profile beginning with the native customer-payment / Payment Entry flow.

That decision is outside Task 43.
