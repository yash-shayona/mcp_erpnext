# MCP ERPNext — Add New Item Row to Existing Draft Document

## Objective

Extend the existing `mcp_erpnext` existing-document lifecycle so a user can add a **new item row** to an already-existing **Draft** transaction through MCP.

Immediate required use case:

```text
Add item SV-UIUX-DESIGN with quantity 2
to Sales Order SAL-ORD-2026-00014.
```

Current behavior already supports updating fields on an **existing child row**, for example:

```text
Existing item:
SV-DEVOPS-DEPLOYMENT

qty: 2 -> 5
rate: 0 -> 500
```

But attempting to add a completely new item row currently fails with:

```text
CHILD_ROW_NOT_FOUND
```

because `prepare_document_update` interprets child-table changes only as edits to an existing row.

This task must add safe **child-row append** support while preserving the existing prepare -> preview -> confirm approval workflow.

---

# Scope

Support adding a new row to the `items` child table of existing Draft transaction documents already allowed by the current MCP profiles.

Target parent DocTypes:

- Quotation
- Sales Order
- Purchase Order

Respect the current profile boundaries.

Examples:

```text
Sales profile
    -> Quotation.items
    -> Sales Order.items
```

```text
Purchase profile
    -> Purchase Order.items
```

The exact profile allowlists must be derived from the current repository configuration/tool registration.

Do not expose arbitrary child-table modification.

---

# Explicitly Out of Scope

Do NOT implement in this task:

- remove/delete child row
- bulk add many arbitrary rows through an unrestricted API
- arbitrary child-table access
- arbitrary DocType access
- submitted-document row addition
- cancelled-document row addition
- automatic cancel/amend
- Sales Invoice
- Payment Entry
- Purchase Invoice
- Purchase Receipt
- Delivery Note
- direct SQL child inserts
- direct `frappe.db` mutation
- `ignore_permissions=True`
- permission bypass
- force-save hacks
- automatic duplicate-row merging

Existing child-row update functionality must remain unchanged.

---

# Mandatory First Step — Inspect Existing Implementation

Before modifying code, inspect the current repository.

Identify:

- `prepare_document_update`
- `confirm_document_update`
- shared lifecycle/update services
- child-row selector logic
- `CHILD_ROW_NOT_FOUND` handling
- current approval-token model
- stale-state/fingerprint checks
- profile allowlists
- metadata/resolver services
- item resolution logic
- transaction create normalization/default logic
- existing error/result schemas
- test conventions

Do not create a second approval system.

Reuse the current mutation lifecycle and confirmation state.

Also inspect the **installed Frappe v16 source** before implementation.

Prefer Frappe's normal document API.

Frappe's document API provides child-table append behavior conceptually through:

```python
doc.append("items", row_values)
```

followed by the normal parent document save path.

However, verify the exact behavior against the project's installed Frappe v16 source before implementing.

Do not copy assumptions from a different Frappe branch/version.

---

# Architecture Requirement

Do not create a separate custom Sales Order-only append engine.

Create/reuse a shared internal child-row add capability.

Conceptually:

```text
MCP Profile
    ↓
Exact Parent Target
    ↓
Profile / DocType / Child Table Allowlist
    ↓
Load Existing Parent
    ↓
Permission + docstatus checks
    ↓
Resolve Item
    ↓
Validate Child Row Metadata / Required Values
    ↓
Prepare New Row
    ↓
Preview
    ↓
User Confirmation
    ↓
Re-fetch + stale-state validation
    ↓
doc.append(...)
    ↓
parent.save()
```

The shared implementation may work for supported transaction types, but it must fail closed outside explicit profile/document/table allowlists.

---

# Tool/API Design

First inspect the repository's current tool naming and lifecycle contract.

Do not blindly create a new public tool if the existing update tool can be extended cleanly.

Two acceptable architectural directions are:

## Option A — Extend Existing Update Mutation Contract

For example, introduce an explicit child operation concept such as:

```text
operation = add_row
```

or equivalent within the existing prepare/confirm lifecycle.

## Option B — Add Focused Prepare Tool

For example conceptually:

```text
prepare_document_child_add
```

and reuse the existing generic confirmation/execution mechanism.

Choose the option that best fits the current repository architecture.

Requirements regardless of tool shape:

- no direct mutation during prepare
- explicit action type must be bound into approval
- exact parent document must be bound into approval
- exact proposed row values must be bound into approval
- confirmation must not be reusable for another document/action/row

Do not create duplicated confirmation logic.

---

# Exact Target Requirement

The parent document must always be identified exactly:

```text
doctype = "Sales Order"
name = "SAL-ORD-2026-00014"
```

Do not support parent mutation through filters such as:

```text
all Sales Orders for Customer X
latest Sales Order
all Draft Sales Orders
```

The agent/client may first use read/search tools to identify the exact target, but the mutation itself must receive the exact parent identity.

---

# Required Add-Row Input

The user must provide or resolve enough information to produce one valid new transaction item row.

At minimum for the immediate use case:

```text
item
qty
```

Example:

```text
item_code = SV-UIUX-DESIGN
qty = 2
```

Additional required/default values must come from:

1. existing MCP transaction-create normalization/default logic, where reusable;
2. Frappe/ERPNext metadata and normal document behavior;
3. explicit user input where the value cannot be derived safely.

Do not invent business values merely to make validation pass.

Examples that may need existing logic/metadata depending on parent DocType:

- delivery/schedule date
- UOM
- conversion factor
- warehouse
- rate
- price list / pricing-derived fields

Reuse the existing create flow wherever it already handles these correctly.

---

# Item Resolution

Do not require the LLM to guess exact item identity.

Reuse existing item search/resolution.

Example:

```text
User:
Add UI/UX Design Service qty 2.

MCP:
search/resolve item
    ↓
SV-UIUX-DESIGN
```

If one exact Item is resolved, continue.

If multiple candidates remain:

```text
return ambiguity
```

Do not append any row until the item is uniquely resolved.

If no item exists:

```text
return not found
```

No mutation.

---

# Draft-Only Rule

This task supports adding new child rows only to:

```text
docstatus = 0
```

Draft documents.

If parent is Submitted:

```text
Result: Rejected

Sales Order SAL-ORD-2026-00014 is Submitted.
Adding a new item row is not supported by this operation.

Changes made: None
```

Do not automatically:

- cancel
- amend
- update after submit through bypasses
- create a new transaction

If parent is Cancelled, reject similarly.

---

# Permission Requirements

The authenticated Frappe user must have normal permission to read and write the parent document.

Use the project's existing Frappe identity/context handling.

Do not use:

```python
ignore_permissions=True
```

Do not bypass User Permissions or document-level restrictions.

The normal parent `save()` path must remain responsible for controller/business validation.

---

# Child Table Allowlist

Do not accept arbitrary values such as:

```text
child_table = anything
```

unless that table is explicitly allowed.

For this task, only the approved transaction item table is intended:

```text
items
```

Validate through metadata that:

- `items` exists on the target DocType
- it is a Table field
- its child DocType is the expected transaction-item DocType
- the current profile permits mutation of this parent/table combination

Fail closed otherwise.

---

# Prepare Flow

Example request:

```text
Add SV-UIUX-DESIGN qty 2
to SAL-ORD-2026-00014.
```

Expected flow:

```text
Load SAL-ORD-2026-00014
        ↓
Verify Sales Order allowed in current profile
        ↓
Verify Draft
        ↓
Verify write permission
        ↓
Resolve SV-UIUX-DESIGN
        ↓
Inspect items metadata
        ↓
Build proposed new child row
        ↓
Run non-mutating validation/preparation
        ↓
Create preview + approval token
```

Prepare must NOT append/save anything.

---

# Preview Requirement

The user must clearly see that this is a **NEW ROW**, not an edit to an existing row.

Example:

```text
Sales Order: SAL-ORD-2026-00014
Status: Draft

Action: ADD ITEM

New item:
Item: SV-UIUX-DESIGN — UI/UX Design Service
Quantity: 2
Rate: <resolved/default/current proposed value if known>

This will add a new item row.

Confirm?
```

Only show useful proposed fields.

Do not dump the full parent document or raw child DocType.

---

# Duplicate Existing Item Handling

Before preparing the append, inspect existing rows for the resolved `item_code`.

If the same Item already exists in one or more rows:

DO NOT silently:

- merge quantities
- update the existing row
- append a duplicate row without making that fact clear

Return an explicit result.

Example:

```text
Item SV-UIUX-DESIGN already exists in this Sales Order.

Existing row:
Qty: 2
Rate: 500

No change was prepared.

Specify whether you want to update the existing row or explicitly add another separate row.
```

If the current ERPNext business configuration explicitly disallows duplicates, respect that native validation.

Do not bypass it.

If duplicate rows are allowed by ERPNext, a separate duplicate row may only be prepared when the user's intent is explicit.

---

# Confirmation Flow

After user confirmation:

```text
approval token
     ↓
verify authenticated user
     ↓
verify MCP profile
     ↓
verify action = add child row
     ↓
verify exact parent
     ↓
re-fetch parent
     ↓
verify still Draft
     ↓
verify write permission again
     ↓
verify stale-state/fingerprint
     ↓
re-check duplicate/conflicting row state
     ↓
append row through native document API
     ↓
parent.save()
```

Use the normal Frappe document save path.

Do not directly insert the child table row into the database.

---

# Native Frappe Save Path

The implementation should follow the installed Frappe document model.

Conceptually:

```python
doc = frappe.get_doc(parent_doctype, parent_name)

doc.check_permission("write")

doc.append("items", validated_row)

doc.save()
```

The exact production implementation must use the repository's existing context/error/transaction abstractions.

The purpose of using the parent Document API is to allow normal:

- child-parent linkage
- controller validation
- ERPNext validation
- hooks
- pricing/business logic where applicable
- persistence behavior

Do not replace the normal document path with SQL.

---

# Validation Failure / Atomicity

If ERPNext rejects the new row or parent save:

- no partial child row should remain persisted
- return a concise structured failure
- preserve normal transaction rollback behavior
- do not retry using bypasses

Example:

```text
Action: Add Item
Document: Sales Order SAL-ORD-2026-00014
Result: Validation failed

Reason:
<concise ERPNext validation message>

Changes made: None
```

---

# Stale Confirmation Safety

Between prepare and confirm another process may modify the parent items.

Reuse the existing lifecycle stale-state protection.

At confirmation, reject the approval if the proposed plan is no longer safe.

Examples:

- parent changed from Draft to Submitted
- target document was deleted
- same item was added by another user
- relevant defaults/context materially changed
- approval belongs to another user/profile

Return:

```text
The document changed after the add-item preview was prepared.

No item was added.

Prepare the action again.
```

---

# Result After Successful Confirmation

Return a compact result.

Example:

```text
Action: Add Item
Document: Sales Order SAL-ORD-2026-00014
Result: Success

Added:
SV-UIUX-DESIGN — UI/UX Design Service
Qty: 2

Document status: Draft
```

Optionally return updated totals if they are already available from the saved document and useful.

Do not dump the entire saved document.

---

# Required Tests

## A1 — Add Item to Draft Sales Order

Existing:

```text
SAL-ORD-2026-00014
items:
- SV-DEVOPS-DEPLOYMENT
```

Prepare:

```text
SV-UIUX-DESIGN
qty = 2
```

Expected:

- preview identifies new row
- no mutation before confirmation

Confirm.

Expected:

- new row exists
- old row remains unchanged
- parent remains Draft
- normal save validations execute

---

## A2 — Existing Row Update Regression

Use current child-row update:

```text
SV-DEVOPS-DEPLOYMENT
qty -> 5
rate -> 500
```

Expected:

- existing behavior still works
- no regression caused by add-row support

---

## A3 — Add Item to Draft Quotation

Expected:

- allowed only through correct sales profile
- new row saved after confirmation

---

## A4 — Add Item to Draft Purchase Order

Expected:

- allowed only through purchase profile
- required/default PO item values handled using existing/native logic
- new row saved after confirmation

---

## A5 — No Confirmation

Prepare add row but do not confirm.

Expected:

- parent unchanged
- row not persisted

---

## A6 — Submitted Parent

Attempt add to Submitted Sales Order.

Expected:

- rejected
- no mutation

---

## A7 — Cancelled Parent

Expected:

- rejected
- no mutation

---

## A8 — Permission Denied

User lacks write permission.

Expected:

- rejected
- no mutation

---

## A9 — Invalid Item

Expected:

- item not found/invalid result
- no mutation

---

## A10 — Ambiguous Item Resolution

Expected:

- candidates returned
- no row prepared

---

## A11 — Duplicate Item Already Exists

Expected:

- do not silently merge
- do not silently append duplicate
- clearly report existing row(s)
- require explicit next intent

---

## A12 — Invalid Child Table

Attempt arbitrary child table.

Expected:

- fail closed
- no mutation

---

## A13 — Profile Escape

Attempt to mutate Purchase Order through a profile that does not allow it.

Expected:

- rejected
- no mutation

---

## A14 — Stale Approval

Prepare add-row action.

Modify parent separately before confirm.

Expected:

- confirmation rejected if state invalidates prepared action
- no unintended row append

---

## A15 — Cross-User Approval

Approval from User A used by User B.

Expected:

- rejected

---

## A16 — Cross-Profile Approval

Approval prepared in one profile used in another.

Expected:

- rejected

---

# Regression Requirements

All existing behavior must continue to pass:

- Customer creation
- Item creation
- Quotation creation
- Sales Order creation
- Purchase Order creation
- document read/retrieve tools
- existing parent-field update
- existing child-row field update
- submit/cancel/delete lifecycle
- search/resolvers
- approval workflow
- profile isolation
- Frappe identity/permissions
- supported MCP transports

---

# Acceptance Criteria

Task is complete only when:

- a new Item row can be added to an existing Draft Sales Order
- `SAL-ORD-2026-00014` can accept `SV-UIUX-DESIGN`, qty `2`, through MCP after confirmation
- adding a row is distinct from updating an existing row
- prepare never mutates data
- confirmation is mandatory
- Item resolution is reused
- parent must be exact
- only allowed `items` tables are mutable
- only supported profile DocTypes are accessible
- Draft-only rule is enforced
- normal Frappe/ERPNext validation executes
- native parent document child append/save path is used
- no direct database child insert is used
- no permission bypass is used
- duplicate existing items are handled explicitly
- stale approvals are rejected
- existing child update behavior remains working
- automated tests pass

---

# End-to-End MCP Verification

After implementation, test this exact conversation through MCP.

## Test 1 — New Item Row

```text
User:
SAL-ORD-2026-00014 me
SV-UIUX-DESIGN item quantity 2 add karo.
```

Expected:

1. get/read exact Sales Order if needed
2. resolve `SV-UIUX-DESIGN`
3. verify parent is Draft
4. prepare **ADD ITEM** preview
5. no data mutation yet
6. ask for confirmation

Then:

```text
User:
Haan, add kar do.
```

Expected:

1. confirm prepared action
2. append new row
3. save through normal Frappe Document path
4. report success
5. original existing rows remain unchanged

## Test 2 — Verify Read

After success:

```text
User:
SAL-ORD-2026-00014 ke items dikhao.
```

Expected output includes both:

```text
SV-DEVOPS-DEPLOYMENT
SV-UIUX-DESIGN
```

with their actual saved quantities/rates.

---

# Documentation

Update only directly relevant MCP/tool documentation.

If the project maintains a tool inventory, add the new add-child-row capability there.

If implementation introduces or changes a reusable **project-specific** command, update `docs/COMMANDS.md`.

Do not add generic Bench/Linux/Docker commands.

---

# Limitations

This task implements only:

```text
ADD new item row
```

It does NOT implement:

```text
REMOVE child row
```

or arbitrary child-table operations.

A remove-row capability, if needed later, should be handled as a separate destructive mutation task with its own confirmation requirements.

---

# Exact Next Task

After automated tests pass:

**MCP Add Child Row End-to-End Verification**

Verify the add-item flow through the actual sales and purchase MCP profiles.

Do not implement child-row removal as part of verification.

---

# Final Agent Report

When finished, report only:

1. files modified/created
2. whether existing update architecture was extended or a focused add-row prepare action was added
3. shared child-row add service
4. MCP tools/contracts changed
5. profile allowlists
6. installed Frappe native APIs/helpers reused
7. item/default validation behavior
8. duplicate-item behavior
9. approval/stale-state protections
10. tests added and results
11. end-to-end MCP test result
12. documentation changes
13. known limitations

Do not claim completion unless automated tests pass.
