# TASK 20 - Item Field-Aware Read / Query Foundation + False-Ambiguity Safety

## Status
NEXT IMPLEMENTATION TASK

## Current source snapshot inspected
This task is based on the current user-provided source snapshot:

```text
mcp_erpnext_2026-09-10T05-01-23Z.zip
```

Do not use conclusions from an older ZIP or an older task draft as the source of truth.
The implementation agent must still inspect the actual working tree before editing because the working tree may be newer than this snapshot.

---

# 1. Scope

Implement a read-only, field-aware Item query foundation inside the existing `mcp_erpnext` sales profile, following the already-working Sales Order read/query architecture and the newly implemented Customer field-aware read/query architecture.

This task must also close the currently observed Item false-ambiguity gap without breaking the existing explicit-selection safety contract.

The immediate production scenario is Quotation creation.

Observed live request:

```text
create a quotation for AEVIAS HEALTHCARE PRIVATE LIMITED customer
with item Web Development Services qty 1 rate 500 using mcp
```

Observed current flow:

```text
resolve_customer("AEVIAS HEALTHCARE PRIVATE LIMITED")
-> resolved

resolve_item("Web Development Services")
-> ambiguous
-> Custom Web Application Development
-> Frappe Custom App Development
-> API Integration Development
```

Business observation from the user:

```text
The requested Item "Web Development Services" does not exist.
If the requested Item does not exist, the controlled Item creation flow should be used.
The model must not treat merely related/weak Item candidates as proof that the requested Item exists.
```

Required high-level outcome:

```text
Exact/usable Item exists
    -> use existing Item reference

True ambiguity between credible existing Items
    -> stop and require explicit selection

Strong spelling correction to one existing Item
    -> preserve the existing safe resolver behavior

Only weak/related candidates for a requested Item that is actually absent
    -> not_found
    -> no misleading candidate selection UI
    -> controlled prepare_item / confirm_item creation branch
```

Do not turn this task into a generic product-search engine, pricing engine, stock analytics engine, or full Item master API.

---

# 2. Objective

After this task, the sales MCP profile must have a deterministic separation between:

```text
A. Item entity resolution
B. Item field-aware reading/querying
C. Item creation
```

Target mental model:

```text
User / Agent
    |
    +--> Existing Item, approximate human wording
    |       -> search_items / resolve_item
    |       -> resolved / true ambiguous / not_found
    |
    +--> Exact Item field question or existence check
    |       -> get_item / query_items / aggregate_items
    |       -> deterministic field-aware read
    |
    +--> Requested exact Item is not present
            -> prepare_item
            -> explicit approval
            -> confirm_item
            -> created Item reference
            -> continue Quotation/Sales Order workflow
```

This task must make `not_found` a real usable state for Item creation decisions instead of allowing weak fuzzy candidates to force an `ambiguous` result.

---

# 3. Inputs / Dependencies

Assume the following current architecture already exists and must be reused rather than rebuilt:

```text
- Sales profile and Purchase profile
- request-scoped Frappe identity/runtime
- explicit typed MCP tool contracts
- contract audit
- generated docs/TOOLS.md
- Customer resolver + Customer creation
- Item resolver + Item creation
- generic explicit candidate selection
- Quotation prepare/confirm flow
- Sales Order prepare/confirm flow
- lifecycle tools
- Sales Order read/query foundation
- Customer field-aware read/query foundation
- PDF/email foundations
```

Current inspected files prove the following patterns exist:

```text
mcp_erpnext/contracts/masters/customer_read.py
mcp_erpnext/services/masters/customer_read.py
mcp_erpnext/tools/masters/customer_read.py
mcp_erpnext/tests/test_customer_read.py

mcp_erpnext/contracts/selling/sales_order_read.py
mcp_erpnext/services/selling/sales_order_read.py
mcp_erpnext/tools/selling/sales_order_read.py
mcp_erpnext/tests/test_sales_order_read.py

mcp_erpnext/config/masters/item.py
mcp_erpnext/contracts/masters/resolution.py
mcp_erpnext/services/masters/item.py
mcp_erpnext/tools/masters/item.py
mcp_erpnext/tools/masters/purchase_item.py
mcp_erpnext/services/common/entity_resolution.py
mcp_erpnext/tests/test_item_service.py
mcp_erpnext/tests/test_entity_selection.py
```

Current Customer implementation report explicitly recommends this Item field-aware read/query foundation as the next candidate when real testing evidence requires it. The live `Web Development Services` case is that evidence.

---

# 4. Mandatory Source Inspection Before Coding

Do not begin by copying this task literally.

Follow this order:

```text
1. Inspect the current working tree.
2. Inspect the completed Customer read/query implementation and report.
3. Inspect the completed Sales Order read/query implementation.
4. Inspect current Item search/resolve/create implementation.
5. Inspect current shared entity-resolution scoring/classification behavior.
6. Inspect the current Task 07B ambiguity contract and tests.
7. Inspect sales and purchase profile registration.
8. Inspect installed Frappe/ERPNext Item metadata and Item source.
9. Reproduce the reported false-ambiguity case at service/test level.
10. Choose the smallest implementation that preserves existing architecture.
11. Only then edit code.
```

Mandatory project files to inspect at minimum:

```text
mcp_erpnext/config/masters/item.py
mcp_erpnext/contracts/masters/resolution.py
mcp_erpnext/services/masters/item.py
mcp_erpnext/tools/masters/item.py
mcp_erpnext/tools/masters/purchase_item.py
mcp_erpnext/services/common/entity_resolution.py
mcp_erpnext/tests/test_item_service.py
mcp_erpnext/tests/test_entity_selection.py
mcp_erpnext/tests/test_interaction_contracts.py

mcp_erpnext/contracts/masters/customer_read.py
mcp_erpnext/services/masters/customer_read.py
mcp_erpnext/tools/masters/customer_read.py
mcp_erpnext/tests/test_customer_read.py

docs/inspect/CUSTOMER_FIELD_AWARE_READ_QUERY_IMPLEMENTATION_REPORT.md

mcp_erpnext/contracts/selling/sales_order_read.py
mcp_erpnext/services/selling/sales_order_read.py
mcp_erpnext/tools/selling/sales_order_read.py
mcp_erpnext/tests/test_sales_order_read.py

mcp_erpnext/contracts/registry.py
mcp_erpnext/contracts/audit.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/profiles/purchase.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_tool_contracts.py
scripts/generate_tool_catalog.py
docs/TOOLS.md

docs/tasks/implementation/07B_GENERIC_AMBIGUOUS_ENTITY_SELECTION_ENFORCEMENT.md
```

Also inspect any newer files that the working tree proves are part of the actual path.

Do not guess helper names, paths, fieldnames, profile behavior, or test commands.

---

# 5. Existing Architecture Decisions That Must Be Preserved

## 5.1 Existing Item resolver is not the Item read/query API

Preserve this distinction:

```text
search_items / resolve_item
--------------------------------
Purpose:
- human-entered existing Item reference
- item code/name discovery
- spelling correction
- true ambiguity handling
- explicit candidate selection

get_item / query_items / aggregate_items
-----------------------------------------
Purpose:
- deterministic exact Item reads
- exact field filters
- field projection
- sorting
- pagination
- deterministic counts/grouping
- exact existence checks
```

Do not replace `search_items` or `resolve_item` with the new query API.

Do not make `query_items` fuzzy.

## 5.2 Item creation remains controlled two-phase creation

Preserve:

```text
prepare_item
-> preview + approval token
-> explicit trusted approval
-> confirm_item
-> insert under normal Frappe permissions
```

Do not create an Item directly from `query_items`, `resolve_item`, Quotation preparation, or a new shortcut tool.

## 5.3 Ambiguous remains terminal

Task 07B remains authoritative:

```text
status == ambiguous
-> do not silently choose the first/highest candidate
-> require explicit selection
-> revalidate the selected exact reference
```

This task must reduce false ambiguity, not weaken true ambiguity safety.

---

# 6. Mandatory Runtime Item Metadata Inspection

Before defining any Item field allowlist, inspect the installed site's merged Item metadata and installed ERPNext source.

At minimum inspect:

```python
meta = frappe.get_meta("Item")
```

Verify actual fieldnames and characteristics for concepts such as:

```text
Item identity
Item Code
Item Name
Item Group
Stock UOM
Disabled
Allow Sales / is_sales_item
Allow Purchase / is_purchase_item
Maintain Stock / is_stock_item
Brand
Description
Sales UOM if relevant
owner
creation
modified
```

These are candidate concepts, not a final allowlist.

Do not invent fields from UI labels.

The installed ERPNext source currently confirms standard Item concepts such as `item_code`, `item_name`, `item_group`, `stock_uom`, `disabled`, and `is_sales_item`, but runtime metadata on the actual site remains the implementation source of truth.

## Required metadata evidence table

The final implementation report must include at least:

```text
fieldname
label
fieldtype
options/link target
standard or custom
fetch_from if any
queryable/list-column status
projection? yes/no
filter? yes/no
sort? yes/no
group? yes/no
reason
```

## Pricing warning

Do not automatically expose pricing fields merely because Item metadata contains them.

In particular, do not treat an Item-level standard rate as the authoritative transaction rate for Quotation/Sales Order creation unless a separate pricing architecture explicitly says so.

The reported user prompt already supplies:

```text
rate = 500
```

This task is about Item existence/read semantics, not pricing policy.

---

# 7. Public Tool Set

Implement the following sales-profile read capability unless current repository conventions prove equivalent names are better:

```text
get_item
query_items
aggregate_items
```

All three must be typed, permission-aware, side-effect-free MCP tools with published output schemas.

Do not create many one-purpose tools such as:

```text
get_disabled_items
get_sales_items
get_items_by_group
find_item_by_name
count_service_items
get_latest_items
```

These are query combinations, not separate MCP capabilities.

---

# 8. Tool A - get_item

## Purpose

Read one exact Item by stable Item reference/name with a safe projection.

Conceptual input:

```text
item: exact Item reference/name
fields?: allowlisted Item fields
```

Examples:

```text
ITEM-001 ka item name kya hai?
ITEM-001 ka stock UOM batao.
ITEM-001 disabled hai kya?
ITEM-001 ka item group batao.
```

Required semantics:

```text
existing + readable
-> status=ok
-> only requested fields

missing
-> status=not_found

exists but current user cannot read
-> typed permission error
```

Use the same exact-document permission pattern already proven by Customer read unless current code provides a better native shared pattern.

Do not return the whole Item document by default.

---

# 9. Tool B - query_items

## Purpose

Provide deterministic field-aware Item filtering and exact existence checks.

This is the primary new tool needed for cases where fuzzy entity resolution is the wrong semantic.

Conceptual filters after runtime verification may include:

```text
name?
item_code?
item_name?
item_group?
stock_uom?
disabled?
is_sales_item?
is_purchase_item?
is_stock_item?
brand?
owner?
created_from?
created_to?
modified_from?
modified_to?

limit?
offset?
sort_by?
sort_order?
fields?
```

Only expose verified fields.

## Exact semantics

Direct field filters must use deterministic exact equality unless a specific typed operator is intentionally added and tested.

Examples:

```text
query_items(item_name="Web Development Services")
```

must mean:

```text
Item.item_name == "Web Development Services"
```

It must NOT mean:

```text
contains Web
contains Development
similar to Services
semantic/fuzzy product search
```

If no exact row exists:

```text
status=ok
items=[]
count=0
```

No unrelated fuzzy candidates may be injected into this result.

## Sales usability filter

Do not blindly bake resolver filters into every Item read.

A field-aware read must be capable of explicitly reading disabled/non-sales Items when the caller asks for them.

For Quotation/Sales Order existence checks, the agent should explicitly request the usable sales conditions verified by runtime metadata, conceptually:

```text
disabled = false
is_sales_item = true
```

The exact filter representation must follow the implemented typed contract.

This preserves the distinction between:

```text
"Does this Item record exist?"
```

and:

```text
"Is this Item currently usable in a sales transaction?"
```

---

# 10. Tool C - aggregate_items

## Purpose

Provide deterministic server-side Item counts/grouping without sending large Item lists to the LLM.

Phase 1 metric:

```text
count
```

Possible grouping concepts after metadata verification:

```text
item_group
brand
disabled
is_sales_item
is_purchase_item
is_stock_item
```

Do not add metrics that require stock ledger, valuation, warehouse, or pricing semantics in this task.

Examples:

```text
How many sales Items are enabled?
How many Items are in Item Group X?
Count disabled Items.
```

Compute counts server-side under normal permissions.

---

# 11. Critical Regression - False Item Ambiguity

This task must explicitly reproduce and fix the current failure class.

## 11.1 Current shared behavior to inspect

The inspected snapshot currently has a shared resolver that:

```text
- finds token-based candidates
- ranks them
- resolves one exact match
- resolves one sufficiently strong winner
- otherwise returns ambiguous whenever candidates remain
```

This means weak candidate presence can become `ambiguous` even when there is no credible exact Item.

Do not assume the working tree is identical. Re-inspect before changing.

## 11.2 Required regression case

Use a focused deterministic test based on the observed case.

Query:

```text
Web Development Services
```

Representative current candidates:

```text
SV-WEBAPP-DEVELOPMENT
Custom Web Application Development

SV-FRAPPE-DEVELOPMENT
Frappe Custom App Development

SV-API-INTEGRATION
API Integration Development
```

The exact requested Item is absent.

Required final public resolver behavior for this case:

```text
resolve_item("Web Development Services")
-> status=not_found
-> doctype=Item
-> query="Web Development Services"
-> candidates=[]
-> no SELECTION interaction
```

And, if `search_items` is used for the same weak-only case, it must not expose a misleading `ambiguous` selection state for those weak candidates.

Preferred public result:

```text
status=not_found
candidates=[]
```

The final implementation must document the exact classification rule used.

## 11.3 Preserve true ambiguity

Do NOT solve the above by changing every fuzzy miss to `not_found`.

The existing Task 07B regression shape must remain safe.

Example:

```text
resolve_item("Development Item")
```

with two or more genuinely competing, near-equivalent candidates must remain:

```text
status=ambiguous
-> explicit candidate selection required
```

The current tests include a `Development Item` ambiguity case. Preserve it unless source inspection proves that the existing test itself is invalid, in which case stop and document why before altering the frozen interaction contract.

## 11.4 Preserve exact resolution

Existing exact references must continue to resolve:

```text
resolve_item("ITEM-001")
-> resolved
-> exact reference
```

## 11.5 Preserve strong spelling correction

A genuinely strong, unambiguous spelling correction that already satisfies the project's safe resolver confidence rules must continue to resolve as `spelling_correction`.

Do not make typo tolerance disappear just to fix weak false positives.

---

# 12. Resolver Change Boundary

The shared resolver is used by more than Item.

Therefore:

```text
Do not casually change services/common/entity_resolution.py.
```

First determine whether the false-ambiguity classification can be fixed safely with:

```text
A. an Item-specific decision layer,
B. a backward-compatible configurable resolver policy,
C. or a truly generic shared classification correction.
```

Choose the smallest option that preserves current behavior for Customer, Supplier, Item, and explicit selection.

If a shared resolver change is chosen, the implementation report must include:

```text
- exact old decision rule
- exact new decision rule
- why the rule is generic rather than Item-specific
- Customer regression result
- Supplier regression result
- sales Item regression result
- purchase Item regression result
- Task 07B ambiguity regression result
```

Do not introduce an unexplained magic threshold.

If a new confidence threshold or margin is necessary, justify it from existing project scoring behavior and concrete regression tests.

Production logic must never hard-code the example Item codes above.

---

# 13. Quotation / Sales Order Create-If-Missing Decision

The goal is not only to add read tools. The final architecture must make the creation branch deterministic.

For a sales document create request containing an Item identity, the agent-facing contract should support this decision flow:

```text
1. Determine whether the input is an exact Item code/name lookup or an approximate discovery request.

2. Exact field/existence intent:
   -> query_items using exact verified field filters
   -> include explicit sales usability filters when creating a sales transaction

3. One usable exact Item:
   -> use exact Item reference

4. More than one exact matching row where the chosen field is not unique:
   -> do not auto-pick
   -> present exact results / require explicit selection

5. No usable exact Item:
   -> if resolver policy is intentionally used for typo correction, only credible resolver states may continue
   -> weak-only false candidates must end as not_found

6. not_found:
   -> prepare_item
   -> ask for any metadata-required missing Item fields
   -> preview
   -> explicit approval
   -> confirm_item
   -> use created Item reference
   -> continue document preparation
```

For the reported user case, the expected business flow is:

```text
AEVIAS HEALTHCARE PRIVATE LIMITED
-> Customer resolves

Web Development Services
-> exact usable Item is not found
-> no misleading weak candidate selection
-> controlled Item creation path
-> after Item creation, continue Quotation preparation with qty 1 and requested rate 500
```

Do not auto-create an Item when `resolve_item` returns true `ambiguous`.

Do not auto-create without the existing explicit Item approval flow.

Do not modify Quotation write safety merely to make this flow shorter.

---

# 14. Tool Description / Agent Selection Boundary

Update public tool descriptions/docstrings/contracts as needed so an LLM can distinguish the tools.

Required semantic descriptions:

```text
search_items
= discover possible existing profile-enabled Items from human-entered approximate text

resolve_item
= resolve an existing profile-enabled Item reference, including safe spelling correction or true ambiguity

get_item
= read selected fields from one exact Item reference

query_items
= deterministic exact Item field filtering and existence checks; not fuzzy matching

aggregate_items
= deterministic Item count/grouping

prepare_item / confirm_item
= controlled Item creation after not_found and required Item input is known
```

Do not describe `search_items`/`resolve_item` as an exact field query API.

Do not describe `query_items` as semantic search.

If LibreChat agent instructions are stored outside this repository, do not patch LibreChat source. Instead place the exact required instruction delta in the final implementation report so it can be applied to the Coordinator/Sales Agent configuration.

---

# 15. Permission and Frappe-Native Query Rules

Preserve the authenticated Frappe user's normal permissions.

Prefer the same native patterns already used by Customer and Sales Order read services:

```text
frappe.get_doc(...)
Document.has_permission("read")
frappe.get_list(..., ignore_permissions=False)
```

For Frappe v16, `frappe.get_list` applies user permissions, while `frappe.get_all` does not.

Do not use:

```text
frappe.get_all
frappe.db.get_all
ignore_permissions=True
Administrator switching
service-user fallback for an authenticated request
raw SQL as a shortcut
```

unless there is a separately reviewed architecture decision.

No read tool may write, commit, submit, cancel, or modify an Item.

---

# 16. Contract Design

Follow the existing Customer read/query architecture.

Recommended new contract file after confirming paths:

```text
mcp_erpnext/contracts/masters/item_read.py
```

Expected concepts:

```text
ItemField
ItemSortField
ItemGroupBy
ItemMetric
ItemFilters
ItemGetInput
ItemQueryInput
ItemAggregateInput
ItemDocument
ItemGetOutput
ItemQueryOutput
ItemAggregateOutput
```

Exact class names may follow the repository's current conventions.

Contract requirements:

```text
- inherit project PublicContractModel behavior
- reject extra/arbitrary fields
- typed Literal field/sort/group values
- bounded positive limit
- non-negative offset
- validated date ranges
- no arbitrary operator strings
- no arbitrary fieldname strings
- no raw filter dictionaries from the model
- no SQL/expression fragments
- typed ok/not_found/error states as appropriate
- structured MCP output schema
```

---

# 17. Service Design

Recommended new service file:

```text
mcp_erpnext/services/masters/item_read.py
```

Keep read/query logic separate from the existing resolver + creation service unless current structure proves another separation is better.

Expected internal responsibilities:

```text
- verified field allowlist
- verified sort allowlist
- verified group allowlist
- typed exact filter builder
- date range helper
- projection helper
- exact get
- field-aware query
- aggregate count/grouping
- permission-safe native Frappe calls
```

Do not pre-generalize Customer and Item into a large generic query framework merely because some helper code looks similar.

Before extracting a shared helper, prove that:

```text
- Customer implementation works
- Item implementation works
- semantics are actually identical
- the abstraction reduces duplication without hiding Doctype-specific rules
```

A few duplicated small helpers are preferable to a premature generic framework.

---

# 18. Tool Wrapper and Profile Registration

Recommended wrapper file:

```text
mcp_erpnext/tools/masters/item_read.py
```

For this task, register the new Item read/query tools in the SALES profile only unless source inspection identifies an already-frozen cross-profile read policy.

Expected sales inventory addition:

```text
get_item
query_items
aggregate_items
```

Do not automatically register these tools in the Purchase profile just because Item is a shared ERPNext master.

The Purchase profile already has its own purchase-enabled `search_items` / `resolve_item` wrappers. Purchase field-aware Item reads should be a deliberate follow-up decision if needed.

Register explicit contracts in:

```text
mcp_erpnext/contracts/registry.py
```

All new tools must pass the existing contract audit and publish typed output schemas.

---

# 19. Files Allowed to Change

Expected new files:

```text
mcp_erpnext/contracts/masters/item_read.py
mcp_erpnext/services/masters/item_read.py
mcp_erpnext/tools/masters/item_read.py
mcp_erpnext/tests/test_item_read.py
```

Expected existing files allowed to change when required:

```text
mcp_erpnext/services/masters/item.py
mcp_erpnext/tools/masters/item.py
mcp_erpnext/config/masters/item.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tests/test_item_service.py
mcp_erpnext/tests/test_entity_selection.py
mcp_erpnext/tests/test_interaction_contracts.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_tool_contracts.py
scripts/generate_tool_catalog.py        only if generator logic genuinely needs a generic change
docs/TOOLS.md                           generated only
```

Conditionally allowed only if inspection proves a shared resolver change is the correct smallest fix:

```text
mcp_erpnext/services/common/entity_resolution.py
shared resolver tests affected by that change
```

If any additional file is changed, explain why in the implementation report.

---

# 20. Files / Areas Not to Change

Do not modify unrelated architecture in this task:

```text
mcp_identity
HTTP authentication contract
shared-secret / verified-user-email identity
approval policy modes
approval storage model
Quotation write contract
Sales Order write contract
Purchase Order write contract
lifecycle engine
PDF foundation
email foundation
Frappe/ERPNext core source
LibreChat source
OAuth/OpenID code
MCP transport selection
sales/purchase process command registry
```

Do not add DocTypes, migrations, patches, new dependencies, bench builds, or frontend assets.

Do not make database records as part of implementation unless an explicitly isolated live verification step requires test data and the user has approved it. Prefer existing records/read-only probes.

---

# 21. Implementation Steps

## Phase A - Inspect and document current behavior

1. Inspect current Item resolver/create code.
2. Inspect Customer read implementation and report.
3. Inspect Sales Order read implementation.
4. Inspect Task 07B ambiguity rules.
5. Inspect sales/purchase profile boundaries.
6. Inspect runtime Item metadata.
7. Reproduce the `Web Development Services` false-ambiguity scoring/classification in a focused test or safe diagnostic.
8. Record why the exact requested Item is absent and why the returned candidates are not an exact match.

Do not edit before this inspection is complete.

## Phase B - Build Item read contracts

1. Define verified Item projection fields.
2. Define exact filter fields.
3. Define sort/group allowlists.
4. Define pagination bounds.
5. Define typed get/query/aggregate inputs and outputs.
6. Reject arbitrary fields/operators.

## Phase C - Build permission-aware Item read service

1. Implement exact Item read.
2. Implement exact field-aware query.
3. Implement count/group aggregate.
4. Use native Frappe permissions.
5. Keep disabled/sales flags caller-controlled for read semantics.

## Phase D - Register Item read tools

1. Add wrappers.
2. Add explicit registry contracts.
3. Register only in the intended profile.
4. Update registration/audit tests.
5. Regenerate tool catalog.

## Phase E - Fix weak false ambiguity

1. Reproduce the exact weak candidate case.
2. Inspect whether the correct smallest fix belongs in Item service or shared resolver.
3. Define/document the exact classification rule.
4. Ensure weak-only noncredible candidate sets become `not_found` with no candidates exposed.
5. Preserve true near-tie ambiguity.
6. Preserve exact match resolution.
7. Preserve strong spelling correction.
8. Preserve Customer/Supplier/Purchase Item behavior.

## Phase F - Verify create-if-missing path

1. Verify Item `not_found` can lead to existing `prepare_item`.
2. Verify missing metadata-required Item fields return `needs_input` rather than guessing.
3. Verify explicit approval is still required.
4. Verify created reference can be reused by Quotation preparation.
5. Do not bypass confirmation.

## Phase G - Full regression and report

1. Run focused tests.
2. Run full test suite.
3. Run contract audit/tool schema checks.
4. Regenerate/check `docs/TOOLS.md`.
5. Run live MCP prompt if environment is available.
6. Create required implementation report.
7. Stop.

---

# 22. Required Focused Tests

## A. Item exact read

Verify:

```text
get_item(exact Item, fields=[...])
-> only requested fields
-> read permission checked
-> no unrelated fields
-> missing Item -> not_found
```

## B. Item exact query

Verify:

```text
query_items(item_name="Web Development Services")
```

uses an exact field filter.

If absent:

```text
status=ok
items=[]
count=0
```

No fuzzy resolver call is allowed inside this query.

## C. Sales usability filtering

Verify the query can explicitly request:

```text
disabled=false
is_sales_item=true
```

Also verify it can intentionally request disabled Items when asked.

The read service must not silently inherit the resolver's active-sales-only filter for every query.

## D. Projection / validation

At minimum reject:

```text
fields=["owner; drop table"]
sort_by="modified desc; delete"
unknown field
unknown group_by
limit above hard maximum
negative offset
invalid date range
```

## E. Aggregate

At minimum verify server-side count under normal permissions.

If grouping is implemented, verify only allowlisted fields are accepted.

## F. Exact reported false-ambiguity regression

Create deterministic candidates equivalent to:

```text
query = "Web Development Services"

Custom Web Application Development
Frappe Custom App Development
API Integration Development
```

Required:

```text
resolve_item -> not_found
candidates=[]
no selection interaction
```

Also verify `search_items` cannot expose the same set as a misleading required selection state when the final classification is `not_found`.

## G. Preserve Task 07B true ambiguity

Existing case concept:

```text
query = "Development Item"
multiple credible/near-tied Development candidates
```

Required:

```text
ambiguous
candidates retained
selection interaction required
no automatic downstream continuation
```

## H. Exact Item resolver regression

Existing exact Item code/name resolution remains `resolved`.

## I. Strong spelling correction regression

Existing strong single spelling correction remains `resolved` with the existing match type.

## J. Customer/Supplier resolver regression

If shared resolver code changed, run and add explicit regressions proving Customer and Supplier behavior is not weakened.

## K. Purchase Item regression

Because the shared Item service also supports purchase-enabled Items, verify purchase-profile `search_items` / `resolve_item` still respect:

```text
disabled != 1
is_purchase_item = 1
normal permissions
```

Do not accidentally apply sales-only filters to Purchase resolution.

## L. Registration and contract audit

Verify:

```text
Sales profile:
- get_item present
- query_items present
- aggregate_items present
- existing Item resolver/create tools still present

Purchase profile:
- new sales Item read tools absent unless an explicit inspected policy says otherwise
- existing purchase Item resolver tools unchanged

All new tools:
- typed input schema
- typed output schema
- READ side effect
- no approval requirement
```

---

# 23. Required Full Regression Tests

Run the repository's actual current test suite with the bench Python environment discovered during inspection.

Use the real repository path and interpreter. Do not guess them from this task file.

Expected pattern:

```bash
<bench-python> -m unittest discover -s apps/mcp_erpnext/mcp_erpnext/tests -p 'test_*.py'
```

Also run the existing tool catalog generator/check:

```bash
<bench-python> apps/mcp_erpnext/scripts/generate_tool_catalog.py
<bench-python> apps/mcp_erpnext/scripts/generate_tool_catalog.py --check
```

Run:

```bash
git diff --check
```

Record exact commands and actual test count in the report.

Do not assume the previous Customer report's test count is still current.

---

# 24. MCP Tool Schema Verification

Inspect the real registered sales-profile tool list after implementation.

Verify these are present:

```text
get_item
query_items
aggregate_items
```

Verify these remain present:

```text
search_items
resolve_item
prepare_item
confirm_item
select_resolved_candidate
prepare_quotation
confirm_quotation
```

Verify the new read tools publish object input/output schemas and pass the existing contract audit.

Verify the Purchase profile inventory remains intentionally isolated.

---

# 25. Live MCP Verification

If an authenticated live sales MCP session is available, test the actual user scenario.

Use the user's reported wording or equivalent:

```text
create a quotation for AEVIAS HEALTHCARE PRIVATE LIMITED customer
with item Web Development Services qty 1 rate 500 using mcp
```

Required outcome when `Web Development Services` is still absent:

```text
- Customer resolves normally.
- The system does not ask the user to choose among unrelated weak Development candidates.
- The Item reaches a deterministic not-found/create decision.
- The existing prepare_item flow is used.
- Missing required Item master fields are requested instead of guessed.
- Item preview is shown.
- Explicit Item creation approval is required.
- Only after Item creation can Quotation preparation continue.
- Quotation still requires its own existing approval flow.
```

Do not claim this passed if the live MCP client was not actually run.

If live agent routing still chooses the wrong MCP tool despite correct tool contracts/descriptions, record that as a client/agent-routing issue and provide the exact Coordinator/Sales Agent instruction delta in the implementation report. Do not patch LibreChat source in this task.

---

# 26. Expected Results

After implementation, examples should behave conceptually as follows.

## Exact Item exists

```text
User:
Create quotation with item ITEM-001.

Resolver/read:
exact existing sales Item

Result:
use existing Item reference
```

## Exact field read

```text
User:
ITEM-001 ka stock UOM kya hai?

Tool:
get_item(item="ITEM-001", fields=["stock_uom"])

Result:
only stock_uom
```

## Exact field query

```text
User:
Web Development Services naam ka Item hai?

Tool:
query_items(item_name="Web Development Services", fields=["name", "item_name"])

Absent result:
items=[]
count=0
```

## False fuzzy candidates

```text
resolve_item("Web Development Services")

Only weak related candidates exist.

Result:
not_found
candidates=[]
```

## True ambiguity

```text
resolve_item("Development Item")

Multiple genuinely competing candidates.

Result:
ambiguous
explicit selection required
```

## Missing Item creation

```text
not_found
-> prepare_item
-> needs_input if metadata requires more fields
-> preview
-> explicit approval
-> confirm_item
-> created Item reference
```

---

# 27. Acceptance Criteria

This task is complete only when all are true:

- [ ] Current working source was inspected before coding.
- [ ] Customer read/query implementation and report were inspected and reused as a pattern.
- [ ] Sales Order read/query implementation was inspected and reused where appropriate.
- [ ] Installed Item runtime metadata/source was inspected before defining allowlists.
- [ ] Metadata evidence table exists in the report.
- [ ] `get_item` is implemented as an exact, permission-aware projected read.
- [ ] `query_items` is implemented with exact typed field filters, safe projection, sorting, and bounded pagination.
- [ ] `aggregate_items` provides deterministic server-side count/grouping within the final allowlist.
- [ ] Arbitrary field names/operators/SQL fragments are rejected.
- [ ] `query_items(item_name="Web Development Services")` can return a clean empty result without fuzzy candidates.
- [ ] The reported weak-candidate `resolve_item("Web Development Services")` case returns `not_found` with no misleading candidates.
- [ ] Weak `not_found` does not emit SELECTION interaction.
- [ ] Existing `Development Item` true ambiguity remains `ambiguous` and requires explicit selection.
- [ ] Exact Item resolution remains working.
- [ ] Strong spelling correction remains working.
- [ ] Existing `prepare_item` / `confirm_item` approval safety remains unchanged.
- [ ] Item creation is never automatic from an ambiguous result.
- [ ] Quotation/Sales Order write safety remains unchanged.
- [ ] Sales Item resolver still applies current sales eligibility filters.
- [ ] Purchase Item resolver still applies current purchase eligibility filters.
- [ ] No `get_all`, permission bypass, Administrator switch, or raw SQL shortcut was introduced.
- [ ] Sales profile contains the intended new Item read tools.
- [ ] Purchase profile remains isolated unless a separately justified existing policy says otherwise.
- [ ] Contract audit passes.
- [ ] Focused tests pass.
- [ ] Full existing unit suite passes.
- [ ] Generated `docs/TOOLS.md` is current and `--check` passes.
- [ ] `git diff --check` passes.
- [ ] Live MCP scenario is verified if environment is available, otherwise explicitly marked NOT VERIFIED.
- [ ] Required implementation report is created.

---

# 28. Known Limitations / Out of Scope

Do not expand this task into:

```text
- stock balance by warehouse
- projected quantity
- bin/stock ledger analytics
- valuation
- Item Price lookup
- Pricing Rule evaluation
- transaction pricing recommendation
- tax template analysis
- serial/batch details
- variants/template creation
- item alternative recommendation
- barcode child-table query
- supplier-item child-table query
- item defaults/accounting tables
- custom-field auto exposure
- cross-company Item policy redesign
- Item update/delete lifecycle redesign
- Purchase-profile field-aware Item query unless separately approved
- generic semantic/vector Item search
```

If any of these becomes necessary, make a separate task.

---

# 29. Required Implementation Report

At completion create:

```text
docs/inspect/ITEM_FIELD_AWARE_READ_QUERY_IMPLEMENTATION_REPORT.md
```

The report must include:

```text
1. Final status: PASS / PARTIAL / FAIL
2. Exact source files inspected
3. Current Frappe / ERPNext versions inspected
4. Item runtime metadata evidence table
5. Final projection/filter/sort/group allowlists
6. Files added/changed
7. Final public contracts for get_item/query_items/aggregate_items
8. Permission behavior
9. Exact old Item false-ambiguity behavior
10. Exact new false-ambiguity classification rule
11. Why Web Development Services now becomes not_found
12. Proof Development Item true ambiguity still remains ambiguous
13. Proof exact and strong-spelling resolution still works
14. Customer/Supplier/Purchase Item regression impact
15. Create-if-missing flow behavior
16. Focused test commands/results
17. Full suite command/result/test count
18. tools/list + contract audit result
19. generated docs check result
20. Live MCP prompt result or explicitly NOT VERIFIED
21. Exact Coordinator/Sales Agent instruction delta if live routing still needs it
22. Known limitations/deferred Item capabilities
23. Safety confirmation: no unintended records/config/core changes
24. Exact next task recommendation
```

Do not claim a live Quotation/Item creation success unless it was actually executed with explicit approvals.

---

# 30. Exact Next Task

After Task 20 is implemented and verified, STOP.

Do not automatically implement Supplier reads or Purchase Item reads.

The exact next task is:

```text
Task 21 - Coordinator/Sales Agent Tool-Selection Routing Audit
```

Scope of Task 21, only after Task 20 results are available:

```text
Verify the real LibreChat Coordinator/Sales Agent consistently chooses:
- exact field-aware reads for exact existence/filter questions,
- entity resolver for approximate existing-entity discovery,
- create tools only after deterministic not_found,
- explicit selection for true ambiguity.
```

If Task 20 live verification already proves this routing is fully correct, Task 21 may close as an audit-only PASS with no code changes.

Do not begin Task 21 inside Task 20.
