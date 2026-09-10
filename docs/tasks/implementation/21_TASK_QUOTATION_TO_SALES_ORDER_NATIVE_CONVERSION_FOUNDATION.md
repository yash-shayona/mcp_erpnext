# TASK 21 — Quotation → Sales Order Native Conversion Foundation

## Status
NEXT IMPLEMENTATION TASK

## Objective
Implement a **first-class, source-aware ERPNext Quotation → Sales Order conversion capability** in the existing `mcp_erpnext` **sales profile**.

The capability must convert an eligible **Submitted Customer Quotation** into a **Draft Sales Order** by reusing ERPNext v16's native Quotation → Sales Order mapping behavior.

This task exists because the current MCP can:

```text
create/read/submit Quotation       YES
create standalone Sales Order      YES

but

convert Quotation -> Sales Order   NO
```

The observed failure pattern is:

```text
get_quotation
-> agent copies customer/item/qty/rate into prepare_sales_order
-> prepare_sales_order behaves as a standalone Sales Order create
-> source Quotation lineage is lost
-> source submission eligibility is not enforced by the Sales Order create tool
-> ERPNext pricing/defaults can recalculate values differently
-> result is NOT a true Quotation conversion
```

The new capability must close exactly that gap.

---

# 1. Frozen Architecture Decisions for This Task

The following decisions are already agreed for the project and must be treated as constraints.

## 1.1 Public MCP surface is ERPNext capability-oriented

Do **not** build a public generic conversion tool such as:

```text
convert_document(source_doctype, source_name, target_doctype)
prepare_document_conversion(...)
```

The public tools for this task must be explicit to this business transition:

```text
prepare_quotation_to_sales_order
confirm_quotation_to_sales_order
```

The reason is that ERPNext document conversions are pair-specific business mappings, not generic DocType copies.

## 1.2 Genericity belongs mainly in internal mechanics

It is acceptable to reuse or later extract shared internal helpers for:

```text
approval storage
permission-safe execution
preview serialization
stale-state/fingerprint checking
public error normalization
observability
```

But do **not** invent a generalized conversion framework before this first concrete conversion is implemented and tested.

Implement Quotation → Sales Order first. Extract a shared conversion engine only later if multiple real conversion flows prove the same mechanics.

## 1.3 Submission remains a separate generic lifecycle capability

This conversion task must **not** auto-submit a Draft Quotation.

Current lifecycle tools remain responsible for document submission:

```text
prepare_document_submit
confirm_document_submit
```

Therefore:

```text
Draft Quotation
-> prepare_quotation_to_sales_order
-> MUST NOT silently submit
-> MUST NOT create Sales Order
```

A future Agent/LangGraph workflow may sequence:

```text
Draft Quotation
-> SUBMIT_QUOTATION node
-> generic submit tools
-> Submitted Quotation
-> CONVERT_QUOTATION_TO_SO node
-> conversion tools from this task
```

Workflow orchestration is outside this task.

## 1.4 `prepare_sales_order` remains standalone creation

Do not change the meaning of the existing:

```text
prepare_sales_order
confirm_sales_order
```

They remain the capability for creating a new standalone Sales Order from explicit Customer/Item input.

Do not overload them with a `quotation` argument.

Do not make them conditionally behave like conversion tools.

## 1.5 Conversion confirmation creates Draft only

Successful conversion must end at:

```text
Sales Order docstatus = 0
```

Do not submit the resulting Sales Order in the same confirmation.

The generic lifecycle submit capability remains a separate later action.

---

# 2. Existing Implementation Is the First Source of Truth

Before editing code, inspect the actual current working tree.

The provided snapshot used to write this task may be behind the latest Task 20 implementation, so **do not overwrite or revert newer work**.

Follow this order:

```text
1. Inspect current working tree and git diff/status
2. Inspect existing Quotation prepare/confirm implementation
3. Inspect existing standalone Sales Order prepare/confirm implementation
4. Inspect approval store and approval-mode behavior
5. Inspect tool contract registry/audit and interaction contracts
6. Inspect sales profile registration and tool ordering tests
7. Inspect generic lifecycle submit capability
8. Inspect current read tools for Quotation/Sales Order
9. Inspect installed ERPNext v16 native Quotation -> Sales Order mapper
10. Inspect installed Frappe v16 get_mapped_doc permission behavior
11. Only then design the smallest implementation
```

Do not guess current file names or current contracts if Task 20 or later local work has changed them.

### Mandatory project files to inspect

At minimum inspect the current equivalents of:

```text
mcp_erpnext/services/selling/quotation.py
mcp_erpnext/services/selling/sales_order.py
mcp_erpnext/tools/selling/quotation.py
mcp_erpnext/tools/selling/sales_order.py
mcp_erpnext/contracts/selling/quotation.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/contracts/audit.py
mcp_erpnext/contracts/interaction.py
mcp_erpnext/approvals.py
mcp_erpnext/observability.py
mcp_erpnext/services/common/lifecycle.py
mcp_erpnext/tools/lifecycle.py
mcp_erpnext/services/common/read.py
mcp_erpnext/tools/read.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/tests/test_quotation_service.py
mcp_erpnext/tests/test_approvals.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_tool_contracts.py
scripts/generate_tool_catalog.py
docs/TOOLS.md
```

Also inspect all files added or changed by Task 20 that touch registration/contracts/tool inventory.

---

# 3. Mandatory Official ERPNext/Frappe Source Inspection

This task must be grounded in the **installed ERPNext/Frappe v16 source** before implementation.

Do not reimplement conversion from memory.

## 3.1 ERPNext Quotation mapper

Inspect the installed equivalent of:

```text
erpnext/selling/doctype/quotation/quotation.py
```

Specifically inspect:

```text
make_sales_order
_make_sales_order
_make_customer
get_ordered_items
```

Verify the exact installed behavior before coding.

At the time this task was written, ERPNext v16 behavior includes these important rules:

```text
make_sales_order(...)
-> checks Selling Settings for expired Quotation conversion
-> rejects expired Quotation unless setting permits it
-> delegates to native mapper

native Quotation -> Sales Order mapping
-> validates Quotation docstatus == 1
-> maps Quotation Item -> Sales Order Item
-> maps Quotation Item.name -> Sales Order Item.quotation_item
-> maps Quotation Item.parent -> Sales Order Item.prevdoc_docname
-> maps taxes
-> maps sales team
-> calculates remaining/mappable quantity
-> excludes already-ordered quantity according to native rules
-> handles alternative-item selection rules
-> applies target missing values and total calculation
```

Do not assume these details if the installed v16 source differs.

## 3.2 Frappe mapped-document permissions

Inspect the installed equivalent of:

```text
frappe/model/mapper.py
```

Specifically `get_mapped_doc`.

Confirm that with `ignore_permissions=False`, the native mapping path applies source-read and target-create permission checks according to the installed version.

### Hard rule

Do not pass:

```text
ignore_permissions=True
```

for the MCP conversion path.

Do not bypass Frappe permissions to make tests pass.

---

# 4. Critical Prepare-Phase Write Safety

`prepare_quotation_to_sales_order` must be a **non-persistent operation**.

This is a hard requirement.

The task writer's ERPNext v16 inspection found an important native behavior:

```text
_make_customer(source_name, ...)
```

may create a Customer when the source Quotation is for a Lead or Prospect and no Customer exists.

That means blindly calling the native mapper for every Quotation could make the **prepare phase write data**.

That is not allowed.

## V1 source-party restriction

For this task, support only:

```text
Quotation.quotation_to == "Customer"
```

The conversion tool must check the source party type **before** calling any native mapping function that could create another master.

If the Quotation is for:

```text
Lead
Prospect
CRM Deal
or another unsupported party type
```

return a safe non-writing result/error.

Do not auto-create a Customer.

Do not call `prepare_customer`/`confirm_customer` automatically.

Do not add a Lead/Prospect conversion workflow in this task.

### Acceptance requirement

A unit/integration test must prove:

```text
prepare_quotation_to_sales_order
on a non-Customer Quotation
-> does not insert Customer
-> does not insert Sales Order
-> does not create approval token
```

---

# 5. Public Tool A — `prepare_quotation_to_sales_order`

## Purpose

Prepare an ERPNext-native mapped **Draft Sales Order preview** from one exact eligible Submitted Customer Quotation, without writing the target document.

## Public input

Keep V1 deliberately small and source-driven.

Conceptually:

```text
quotation: exact Quotation document name
```

Use the project's typed reference/string contract conventions after inspecting the current contract layer.

### Do NOT accept V1 overrides for

```text
customer
company
items
qty
rate
price list
taxes
terms
currency
quotation status
source doctype
target doctype
```

The conversion should derive target data from the source through ERPNext's mapper.

If the user wants a different Customer/rate/items independent from the source, that is a standalone Sales Order creation/update concern, not this conversion.

## Exact-source behavior

`quotation` is an exact ERPNext document identifier.

Do not fuzzy-search it.

Do not silently select a different Quotation.

If natural-language lookup is required later, the Agent can use existing Quotation read/search tools first and then call this conversion tool with the exact name.

---

# 6. Prepare Eligibility Rules

Before producing an approval token, the service must prove all relevant eligibility conditions.

At minimum:

## 6.1 Authentication

Use the existing request-scoped authenticated Frappe user pattern.

No Guest fallback.

No service-user permission bypass.

## 6.2 Exact source exists and is readable

The current user must be able to read the exact Quotation.

Do not use permission-bypassing reads.

## 6.3 Source must be Submitted

Required:

```text
Quotation.docstatus == 1
```

Draft source:

```text
status/error indicating source is not ready for conversion
NO approval token
NO auto-submit
NO Sales Order write
```

Cancelled source:

```text
NO conversion
```

## 6.4 Source must be Customer-based

Required for V1:

```text
quotation_to == "Customer"
```

See Prepare-Phase Write Safety above.

## 6.5 Target Sales Order create must be permitted

Use existing Frappe/native mapper permission enforcement.

If an additional explicit pre-check is useful for clearer control flow, it may be used, but do not weaken native enforcement.

## 6.6 Expired Quotation behavior must remain ERPNext-native

Do not invent an MCP rule such as:

```text
expired quotation is always blocked
```

Use the **public ERPNext `make_sales_order` path** or an installed-version-equivalent path that preserves the Selling Setting controlling Sales Order creation from expired Quotations.

Preferred direction after installed-source verification:

```text
erpnext.selling.doctype.quotation.quotation.make_sales_order(source_name)
```

Do not call `_make_sales_order` merely to skip ERPNext's expiry policy.

If installed source proves a different public function is canonical, use that and document why.

## 6.7 There must be at least one mappable target item

The native mapper may exclude already-ordered rows / exhausted quantities.

Do not create an empty Sales Order.

If the mapped document has no valid target item rows:

```text
NO approval token
NO write
safe business error/result
```

Do not manufacture quantities.

---

# 7. Native Mapping Must Be the Source of Target Commercial Data

The previous bad flow manually reconstructed a Sales Order and caused a Quotation rate of `500` to become a Sales Order rate of `30000`.

This task must specifically prevent that class of error.

Do **not** do this:

```text
read Quotation
-> copy customer
-> copy item_code
-> copy qty
-> call standalone prepare_sales_order
```

Do **not** manually rebuild the target from a guessed subset of source fields.

Use the ERPNext native mapping result as the target Draft document.

The mapped target should preserve whatever the installed ERPNext mapper legitimately carries/calculates, including where applicable:

```text
customer
customer_name
company
currency
selling price list
item rows
remaining qty
rates
discounts
amounts
taxes
terms
sales team
payment schedule behavior
quotation row lineage
other native mapped/defaulted commercial values
```

Do not hardcode field copies when the native mapper already owns them.

---

# 8. Required Lineage Preservation

The target preview and final Draft Sales Order must preserve native source linkage.

At minimum verify the installed mapper's equivalent of:

```text
Quotation Item.name
-> Sales Order Item.quotation_item

Quotation Item.parent
-> Sales Order Item.prevdoc_docname
```

This lineage is one of the reasons this capability must not be implemented as standalone Sales Order reconstruction.

### Required success assertion

For every converted target item row that came from a Quotation row, verify the expected source row/document link fields are populated according to native ERPNext behavior.

Do not invent a custom `source_quotation` field.

Use ERPNext's native target fields.

---

# 9. Preview Contract

Return a bounded, typed, business-focused preview.

Do not expose the entire raw `doc.as_dict()` publicly.

The public preview should include enough data for the user/agent to verify the conversion before confirmation.

At minimum, after actual metadata/source inspection, include the safe equivalents of:

```text
source:
  quotation name

sales_order preview:
  customer
  customer_name
  company
  transaction_date
  delivery_date if populated
  currency
  selling_price_list

items:
  item_code
  item_name
  qty
  uom
  rate
  discount_percentage if meaningful
  discount_amount if meaningful
  amount
  net_amount if meaningful
  warehouse if meaningful
  delivery_date if meaningful
  quotation_item
  prevdoc_docname

taxes:
  charge_type
  account_head
  rate
  tax_amount
  total

totals:
  net_total
  total_taxes_and_charges
  additional_discount_percentage
  discount_amount
  grand_total

commercial context:
  tc_name if present
  terms if present
```

Do not add fields merely because they exist in metadata.

Use current project preview conventions where possible.

---

# 10. Typed Public Contracts

This is a new post-contract-foundation tool and must **not** be added as frozen legacy/untyped behavior.

Create explicit typed input/output contracts following the current architecture.

Suggested file after current-tree inspection:

```text
mcp_erpnext/contracts/selling/quotation_to_sales_order.py
```

or another clearly pair-specific path consistent with the current tree.

## Prepare result states

Do not start a global workflow-outcome refactor in this task.

Use the smallest typed result family consistent with the project's current patterns.

Expected concepts:

```text
ready
error / not-ready source
```

If `needs_input` is not actually possible with a source-only V1 conversion, do not add it just for symmetry.

A successful prepare result must include:

```text
status = ready
approval_token
expires_in_seconds
source quotation identity
preview
interaction = shared APPROVAL directive
```

### Approval interaction

Reuse the existing shared `InteractionDirective` / approval directive.

Do not invent client-specific fields such as:

```text
librechat_button
vscode_prompt
chatgpt_confirmation
```

## Safe authorization failure for this new capability

Do not expose internal role/permission mechanics in newly designed public output.

For this task, if the current user cannot perform a required read/create action, return the project's safe error envelope with a generic user/model-safe code/message such as the current architecture supports.

Do not return fields such as:

```text
missing Submit permission
required_role = Sales Manager
Role Permission Manager details
user role list
```

Detailed authorization diagnostics belong in internal observability/logging.

Do **not** refactor all existing tools' permission responses in Task 21; keep this requirement local to the new conversion capability unless a tiny shared helper change is clearly required.

---

# 11. Approval Action Identity

The conversion must have its own action identity.

Do not reuse:

```text
create_sales_order
create_quotation
```

Use a pair-specific internal action such as:

```text
convert_quotation_to_sales_order
```

or the current project's equivalent naming convention.

This guarantees that a token prepared for standalone Sales Order creation cannot confirm a Quotation conversion and vice versa.

---

# 12. Approval Payload Must Be Server-Owned

The model/client must never send the target mapped document back as trusted confirmation data.

The prepare phase should store private server-side conversion state in the existing approval store.

Conceptually the private payload may contain:

```text
source doctype/name
mapped target safe server-owned data
conversion fingerprint/snapshot
any minimal revalidation metadata
```

The only model-visible handle needed for confirmation is the opaque approval token plus the existing `confirm` boolean contract.

Do not expose an editable raw target payload and accept it back during confirm.

---

# 13. Stale-State Protection Is Mandatory

A valid approval token only proves that the prepared payload itself has not been tampered with.

It does **not** prove that ERPNext business state is unchanged since prepare.

Between prepare and confirm, examples of relevant state changes include:

```text
Quotation cancelled/amended
Quotation eligibility changes
Selling Settings expiry policy changes
Customer/company commercial defaults change
price/tax/default data changes
another Sales Order changes native remaining/mappable quantity
mapped target calculation changes
```

Therefore confirm must revalidate the conversion against **current ERPNext state** before inserting.

## Required strategy

Use a robust strategy consistent with current architecture, preferably:

```text
prepare:
  native-map current Quotation
  build canonical conversion snapshot/fingerprint
  store server-side

confirm:
  claim guarded token
  re-check source state/permissions
  native-map again using the same supported conversion mode
  build current canonical snapshot/fingerprint
  compare with prepared fingerprint

  if different:
      do not insert
      return stale/preparation-changed error
      require prepare again

  if identical:
      insert the freshly revalidated mapped Draft
```

A simple `Quotation.modified` comparison alone is **not sufficient** if source mappability can change because of downstream documents without modifying the Quotation record itself.

## Fingerprint scope

Do not fingerprint arbitrary volatile runtime values.

Choose a canonical stable representation that covers conversion-critical business state.

At minimum it must detect changes in:

```text
source identity/eligibility
customer/company/currency context
mapped item set
source row links
qty
rate/discount/amount
mapped taxes
important totals
terms/payment context where it affects the mapped target
```

Document the exact fingerprint scope in the implementation report.

---

# 14. Public Tool B — `confirm_quotation_to_sales_order`

## Purpose

After the existing MCP approval guard is satisfied, create the **revalidated ERPNext-native mapped Draft Sales Order**.

Conceptual public input:

```text
approval_token: opaque token
confirm: boolean
```

Follow the existing confirmation contract pattern.

## Required behavior

### `confirm == false`

Consume/cancel the matching pending conversion according to existing approval behavior.

Do not write.

### `confirm == true`

Use:

```text
approvals.claim_for_confirm_write(...)
```

or the exact current shared guard.

Preserve existing configured approval modes.

Do not create a new approval bypass.

### On success

Insert exactly one mapped Sales Order with normal Frappe permissions.

Do not submit it.

Expected response concept:

```text
status = created
sales_order = SAL-ORD-...
docstatus = 0
source_quotation = SAL-QTN-...
idempotent / equivalent existing field if current project uses it
```

Do not claim the Quotation itself was submitted by this tool.

---

# 15. Persistence Rules

On successful confirmation:

```text
mapped Sales Order.insert()
```

or the idiomatic installed equivalent should run with normal permissions.

Do not use:

```text
ignore_permissions=True
flags.ignore_permissions = True
frappe.db.sql insert/update
manual child-row database writes
```

Do not call `doc.submit()`.

Let ERPNext/Frappe validation/controller hooks run normally.

If India Compliance or other installed official app hooks participate in normal Sales Order insert/validation, they must not be bypassed.

---

# 16. Transaction / Error Handling

Follow the existing runtime transaction boundary.

Do not add manual commits inside the service unless the current architecture explicitly requires them.

On mapper/validation/insert error:

```text
no partial target document should remain committed
```

Normalize public errors through the current safe public error/observability helpers.

Preserve an internal error reference for diagnostics.

Do not leak traceback, SQL, file paths, user roles, secrets, tokens, or permission internals in public output.

---

# 17. No Duplicate Confirmation

The existing approval store's one-time consumption behavior must apply.

Tests must prove:

```text
same conversion token confirmed twice
-> only first permitted confirmation can write
-> second attempt returns consumed/unavailable equivalent
-> no second Sales Order is created by the same token
```

Also verify mismatched:

```text
site
user
action
```

cannot use the token.

---

# 18. Native Partial/Already-Ordered Behavior

Do not invent custom quantity math.

ERPNext's mapper already accounts for native ordered/mapped quantities.

The new MCP conversion must preserve this behavior.

## Required cases to test/inspect

### Fresh submitted Quotation

```text
all normally mappable non-alternative rows
-> mapped with full eligible quantity
```

### Partially ordered Quotation

If installed ERPNext native mapping returns remaining quantity:

```text
MCP preview must show that native remaining quantity
```

Do not restore original full quantity manually.

### Fully ordered/no mappable rows

```text
no empty Sales Order creation
no approval token
safe no-mappable-items outcome/error
```

### Alternative items

Do not build a custom alternative-item selector in this task.

With no explicit selected rows, preserve the installed native mapper's default behavior.

If the current native mapping requires explicit selection for a scenario not representable in V1, return a safe unsupported/needs-selection outcome and document it rather than guessing.

Do not expand Task 21 into a generic selected-child mapping framework.

---

# 19. Expired Quotation Test Matrix

Inspect the installed Selling Settings field used by the v16 mapper.

Then test both policy states if practical.

## Setting blocks expired conversion

Expected:

```text
expired Submitted Quotation
-> prepare fails safely
-> no approval token
-> no Sales Order
```

## Setting allows expired conversion

Expected:

```text
expired Submitted Quotation
-> native mapper may proceed if all other rules pass
-> MCP must not add a contradictory hardcoded block
```

This verifies that the MCP is using ERPNext's business policy rather than recreating it.

---

# 20. Rate Preservation Regression Test

Add a direct regression for the real issue that exposed this gap.

Create/prepare a Submitted Customer Quotation whose line has a known rate that differs from the Item's normal price list rate.

Conceptual fixture:

```text
Quotation item rate = 500
Item price list rate = 30000
```

Then:

```text
prepare_quotation_to_sales_order
```

must produce the **same result as ERPNext's native mapper**.

If native mapper preserves the Quotation rate in the installed version, assert:

```text
Sales Order preview rate = 500
```

and after confirmation:

```text
created Sales Order rate = 500
```

Do not merely assert a hardcoded `500`; compare the MCP result to the native ERPNext mapping behavior so the test remains source-grounded.

Also assert native quotation linkage fields are present.

---

# 21. Prepare Must Not Mutate Database

Add explicit tests proving prepare is read/non-persistent.

At minimum after `prepare_quotation_to_sales_order`:

```text
Sales Order count unchanged
Quotation docstatus unchanged
Quotation data unchanged
Customer count unchanged
no doc.insert called for target
no doc.submit called
```

Where feasible also verify no unexpected `db_set`/save operation from MCP code.

For supported Customer Quotations, native mapping may create an in-memory target document; that is fine.

The hard boundary is **no persistent write during prepare**.

---

# 22. Contract Registry / Tool Metadata

Add both new tools to the current explicit tool contract registry.

Expected classification after inspecting current enums:

```text
prepare_quotation_to_sales_order
  domain: Selling
  operation: PREPARE
  side effect: PREPARE
  explicit input model
  explicit output model
  interaction: APPROVAL
  approval_confirm_tool: confirm_quotation_to_sales_order

confirm_quotation_to_sales_order
  domain: Selling
  operation: CONFIRM
  side effect: CONFIRM_WRITE
  explicit input model
  explicit output model
  approval_guard: existing trusted pending-operation guard
```

Do not add these names to the frozen legacy inventory.

The contract audit must pass with no exceptions added just for this tool.

---

# 23. Sales Profile Registration

Register the new conversion capability only in the **sales** profile.

Expected:

```text
MCP_PROFILE=sales
-> prepare_quotation_to_sales_order present
-> confirm_quotation_to_sales_order present

MCP_PROFILE=purchase
-> both absent
```

Do not expose them in purchase profile.

Do not change profile architecture.

Keep registration deterministic and update exact tool inventory tests accordingly.

Preserve all Task 20 tools already present in the current working tree.

---

# 24. Suggested File Structure

The implementation should follow the existing architecture, not this exact file list if the current tree has evolved.

Preferred pair-specific structure:

```text
mcp_erpnext/contracts/selling/quotation_to_sales_order.py
mcp_erpnext/services/selling/quotation_to_sales_order.py
mcp_erpnext/tools/selling/quotation_to_sales_order.py
mcp_erpnext/tests/test_quotation_to_sales_order.py
```

Then minimal registration/export edits in current equivalents of:

```text
mcp_erpnext/contracts/selling/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_approvals.py
mcp_erpnext/observability.py   only if current metrics/classification requires it
```

Do not put conversion business logic inside tool wrapper files.

Do not put MCP/Context objects inside service-layer business logic.

---

# 25. Files/Components Allowed to Change

Only after inspection, modify the minimum required equivalents of:

```text
contracts/selling/*
services/selling/*
tools/selling/*
contracts/registry.py
contracts/audit.py only if a general existing invariant genuinely needs extension
profiles/sales.py
tools/__init__.py
tests for this capability / registration / contracts / approval
docs/TOOLS.md via existing generator
docs/inspect/* implementation report
```

Small shared helper changes are allowed only when they clearly reuse an existing project mechanic and do not broaden scope.

---

# 26. Files/Components NOT to Change Unless Proven Necessary

Do not modify unrelated architecture merely to complete this task.

In particular do not change without a documented reason:

```text
mcp_identity app
HTTP identity contract
LibreChat OAuth/OpenID work
transport auth
MCP_PROFILE model
purchase profile business behavior
Customer/Item resolver semantics
Task 20 Item read/query behavior
standalone Quotation creation semantics
standalone Sales Order creation semantics
generic submit/cancel/delete meaning
PDF foundation
Email foundation
command registry
Frappe/ERPNext core source
India Compliance source
```

Do not patch ERPNext's `quotation.py`.

Call/reuse it.

---

# 27. Explicit Non-Goals

Task 21 does **not** implement:

```text
Agent/LangGraph workflow
Draft Quotation auto-submit
Sales Order auto-submit
Quotation -> Sales Invoice
Sales Order -> Sales Invoice
Sales Order -> Delivery Note
Supplier Quotation -> Purchase Order
Purchase Order -> Purchase Invoice
generic conversion framework
selected-row UI
Lead/Prospect -> Customer creation orchestration
Sales Order business-specific update refactor
safe-permission-output refactor for every existing tool
ERPNext workflow approval engine
```

Do not expand the task into any of these.

---

# 28. Required Unit Tests

Add focused automated tests for the new service/contracts/tools.

At minimum cover:

## Prepare success

```text
submitted Customer Quotation
read/create permitted
native mapper returns valid Sales Order
-> status ready
-> approval token returned
-> approval interaction returned
-> no database write
-> preview contains source quotation
-> mapped item lineage visible
-> mapped economics match native mapper
```

## Draft source rejected

```text
docstatus = 0
-> no token
-> no mapper/write that auto-submits
-> safe source-not-ready result
```

## Cancelled source rejected

```text
docstatus = 2
-> no token
-> no write
```

## Unsupported party type blocked before mapper side effect

```text
quotation_to = Lead/Prospect/etc.
-> no Customer insert
-> no Sales Order insert
-> no token
```

## Expired policy behavior

Both setting states as described above.

## No mappable items

```text
native result has no eligible target rows
-> no token
-> no empty Sales Order
```

## Rate/native mapping regression

Known source rate different from default price list rate.

Assert MCP preview/final target matches native mapping result.

## Source lineage

Assert `quotation_item` / `prevdoc_docname` or installed equivalents.

## Approval mismatch

Token cannot be used by:

```text
wrong action
wrong user
wrong site
```

## Confirmation declined

```text
confirm=false
-> no write
-> token consumed/cancelled per current behavior
```

## Confirmation replay

```text
same token confirmed twice
-> only one target write maximum
```

## Trusted approval mode

Preserve existing `TRUSTED_APPROVAL_UNAVAILABLE` behavior when configured and no trusted human event exists.

## Agent-delegated/local test mode

If existing test configuration uses agent-delegated approval, ensure successful confirm remains testable without weakening production mode.

## Stale mapping

Change conversion-relevant state between prepare and confirm.

Expected:

```text
confirm does not insert
stale/prepared-operation-changed result
new prepare required
```

## Contract validation

Invalid/missing exact quotation reference rejected by typed schema.

No arbitrary target document object accepted.

---

# 29. Required Registration / Architecture Tests

Update or add tests proving:

```text
sales profile includes both conversion tools
purchase profile excludes them
all registered tools exist in contract registry
contract audit returns []
new tools are non-legacy typed contracts
prepare advertises APPROVAL interaction
confirm advertises existing approval guard
no runtime-only fields are model-visible
```

If current Task 20 changed expected tool order, base assertions on the current tree and preserve those additions.

---

# 30. Required Runtime/Integration Verification

After unit tests pass, verify against a real local ERPNext v16 site if available.

Use disposable test documents.

Recommended manual flow:

```text
1. Create or choose Customer
2. Create/choose Item with known normal price
3. Create Draft Quotation with intentionally different explicit rate
4. Submit Quotation using existing lifecycle flow / ERPNext UI
5. Call get_quotation and record source values
6. Call prepare_quotation_to_sales_order
7. Verify preview:
   - source Quotation exact
   - customer/company correct
   - item qty correct
   - rate follows native mapper/source behavior
   - taxes/totals correct
   - quotation_item / prevdoc_docname mapped
8. Verify no Sales Order exists yet from prepare
9. Complete trusted approval according to current configured mode
10. Call confirm_quotation_to_sales_order
11. Verify exactly one Draft Sales Order created
12. Verify docstatus = 0
13. Verify Quotation remains Submitted
14. Verify Sales Order item links back to Quotation row/document
15. Verify target economics match prepared preview
```

Also manually test:

```text
Draft Quotation -> conversion blocked
Expired Quotation -> respects Selling Settings
Fully ordered Quotation -> no empty target
```

Do not test against important production records.

---

# 31. Documentation Update

Run the existing tool catalog generator after implementation.

Update generated/current documentation so the sales profile clearly distinguishes:

```text
prepare_sales_order
  = standalone Sales Order creation

prepare_quotation_to_sales_order
  = source-aware native Quotation conversion
```

Tool descriptions must be explicit enough that an MCP client/model does not confuse them.

Suggested descriptions:

```text
prepare_quotation_to_sales_order:
Prepare a Draft Sales Order preview from an eligible Submitted Customer Quotation using ERPNext's native mapping rules. Does not submit the Quotation or write the Sales Order.

confirm_quotation_to_sales_order:
Create the reviewed Draft Sales Order from the prepared Quotation conversion after the configured approval guard succeeds.
```

Use current documentation conventions rather than copying these words blindly.

---

# 32. Required Implementation Report

At the end, create:

```text
docs/inspect/QUOTATION_TO_SALES_ORDER_NATIVE_CONVERSION_IMPLEMENTATION_REPORT.md
```

The report must include:

## A. Existing implementation inspected

List exact project files/functions inspected before coding.

## B. Installed official source evidence

Record exact installed Frappe/ERPNext versions and exact native functions used.

At minimum explain findings for:

```text
Quotation submission validation
expired quotation policy
Customer/Lead/Prospect behavior
native row mapping
remaining ordered quantity logic
quotation_item linkage
prevdoc_docname linkage
Frappe mapper permission checks
```

## C. Final public contract

Document exact schemas/statuses for:

```text
prepare_quotation_to_sales_order
confirm_quotation_to_sales_order
```

## D. Prepare write-safety evidence

Explain how V1 prevents Lead/Prospect native auto-Customer creation during prepare.

## E. Native mapping evidence

Show one before/after example:

```text
Quotation
-> mapped Sales Order preview
```

Include item rate/qty/lineage/totals.

## F. Stale-state strategy

Document exactly what is fingerprinted/revalidated and why `modified` alone was not considered sufficient if applicable.

## G. Permission behavior

Document that normal Frappe permissions are preserved and that internal authorization details are not exposed unnecessarily by the new tool.

## H. Tests run

List commands and results.

## I. Manual verification

Document the exact local test flow and created disposable document names, if run.

## J. Files changed

Exact list.

## K. Known limitations

At minimum include any still-applicable V1 limitations such as:

```text
Customer Quotations only
no selected-row/alternative UI orchestration
no auto-submit
no downstream SO -> SI conversion yet
```

## L. Exact next task recommendation

Do not automatically implement the next task.

Recommend the next evidence-based gap only after this conversion is tested.

Likely candidate may be:

```text
Sales Order -> Sales Invoice native conversion
```

but do not assume it is next if testing exposes a more immediate prerequisite.

---

# 33. Test Commands

Use the project's actual environment and current test conventions.

At minimum run the focused tests plus full MCP app test suite if practical.

Conceptually:

```text
focused conversion tests
contract/tool registration tests
approval tests
profile tests
existing Quotation tests
existing Sales Order tests
existing lifecycle tests
full mcp_erpnext test suite
```

Do not run destructive production operations.

Do not use `bench migrate`, builds, yarn, or unrelated bench operations unless inspection proves they are required for this Python-only change.

---

# 34. Acceptance Criteria

Task 21 is complete only when all of the following are true.

- [ ] `prepare_quotation_to_sales_order` exists in sales profile.
- [ ] `confirm_quotation_to_sales_order` exists in sales profile.
- [ ] Neither conversion tool exists in purchase profile.
- [ ] Both tools have explicit typed non-legacy contracts.
- [ ] Prepare accepts one exact source Quotation reference, not arbitrary target fields.
- [ ] Prepare performs no persistent write.
- [ ] V1 blocks non-Customer Quotations before any native auto-Customer creation path.
- [ ] Draft Quotation is not auto-submitted.
- [ ] Cancelled Quotation is not convertible.
- [ ] Submitted-state requirement is preserved from ERPNext native mapper.
- [ ] Expired Quotation behavior respects installed ERPNext Selling Settings.
- [ ] Native ERPNext Quotation -> Sales Order mapper is reused.
- [ ] `ignore_permissions=True` is not used.
- [ ] Target Customer/Company/Items/Rates/Taxes/Terms follow native mapping behavior.
- [ ] Quotation item/source lineage fields are preserved.
- [ ] No empty Sales Order can be prepared/created when no rows are mappable.
- [ ] Prepare returns bounded business preview, not raw full document payload.
- [ ] Approval state stays private/server-owned.
- [ ] Conversion uses its own approval action identity.
- [ ] Existing approval mode enforcement remains intact.
- [ ] Confirm revalidates current ERPNext conversion state.
- [ ] Relevant state drift causes stale failure/re-prepare rather than silent changed write.
- [ ] Successful confirm creates exactly one Draft Sales Order.
- [ ] Successful confirm does not submit Sales Order.
- [ ] Same token cannot create duplicate Sales Orders.
- [ ] Standalone `prepare_sales_order` / `confirm_sales_order` behavior remains unchanged.
- [ ] Generic document submit/cancel/delete behavior remains unchanged.
- [ ] Existing Task 20 additions remain intact.
- [ ] Contract audit passes.
- [ ] Profile/registration tests pass.
- [ ] Regression test proves prior `500 -> 30000` reconstruction failure is eliminated by using native mapping behavior.
- [ ] `docs/TOOLS.md` regenerated/updated.
- [ ] Implementation report created.
- [ ] No unrelated refactor is included.

---

# 35. Expected Result

After Task 21, the MCP should support this distinction correctly:

```text
User intent:
"Create a new Sales Order for customer X"

-> prepare_sales_order
-> standalone creation


User intent:
"Convert submitted Quotation SAL-QTN-2026-00008 to Sales Order"

-> prepare_quotation_to_sales_order
-> ERPNext native source mapping
-> preview with source lineage and source economics
-> approval
-> confirm_quotation_to_sales_order
-> linked Draft Sales Order
```

And this must be rejected safely:

```text
"Convert Draft Quotation ..."

-> no auto-submit
-> no Sales Order
-> source is not yet eligible
```

The MCP server therefore gains the missing **conversion capability**, while workflow sequencing remains available for a future Agent/LangGraph layer.

---

# 36. Exact Next Task After Completion

Do **not** implement another conversion automatically.

Complete Task 21, test it end-to-end, and produce the implementation report first.

Then review the report and real usage results.

If no prerequisite gap appears, the likely next task is:

```text
TASK 22 — Sales Order → Sales Invoice Native Conversion Foundation
```

That next task must again inspect ERPNext's native Sales Order → Sales Invoice mapper and its specific billed/remaining quantity rules before implementation.

