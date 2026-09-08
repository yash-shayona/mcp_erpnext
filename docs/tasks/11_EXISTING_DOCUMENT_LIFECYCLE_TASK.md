# MCP ERPNext Existing Document Lifecycle — Update, Submit, Cancel, Delete

## Objective

Extend the existing `mcp_erpnext` MCP server beyond Draft creation so already-supported ERPNext documents can safely be:

1. Updated
2. Submitted
3. Cancelled
4. Deleted

Reuse the existing MCP architecture, identity/permission context, metadata/resolver foundation, profile separation, validation layer, and prepare/confirmation/approval workflow.

This task completes lifecycle operations for the currently supported document types only.

---

# Current Supported Scope

Lifecycle operations apply only where relevant to the DocTypes already supported by the existing MCP profiles.

Current target DocTypes:

- Quotation
- Sales Order
- Purchase Order
- Customer
- Item

Respect the existing MCP profile boundaries.

Do not expand a profile's DocType access merely because the shared lifecycle service supports that DocType.

Derive the exact allowed DocTypes for each profile from the repository's current configuration/tool registration.

---

# Explicitly Out of Scope

Do NOT implement:

- Sales Invoice creation/update/submit/cancel/delete
- Payment Entry
- Purchase Receipt
- Purchase Invoice
- Delivery Note
- next-document generation
- amendments
- workflow redesign
- bulk update
- bulk delete
- filter/where-condition delete
- force delete
- automatic cascade delete
- automatic unlinking of business documents
- direct SQL mutation
- `ignore_permissions=True`
- `force=True`
- arbitrary DocType access

Do not modify LibreChat.

Do not redesign MCP identity or transport.

---

# Mandatory First Step — Inspect Existing Implementation

Before writing code, inspect the current repository.

Determine:

- existing create/prepare/confirm architecture
- current approval-state implementation
- current confirmation token/payload model
- metadata services
- resolver services
- validation services
- Frappe context handling
- profile registration
- error/result schemas
- test conventions
- currently installed Frappe version/source

Do not create a second parallel approval system.

Reuse the existing prepare → preview → confirm pattern.

Also inspect the **installed Frappe v16 implementation** before writing custom lifecycle logic.

Prefer native Frappe APIs/helpers wherever available.

Relevant framework areas include:

- `Document.save`
- `Document.submit`
- `Document.cancel`
- `Document.delete` / `frappe.delete_doc`
- DocType metadata / `is_submittable`
- permission APIs
- update-after-submit validation
- static and dynamic link checking
- submitted linked-document discovery

Do not assume that functionality present on Frappe `develop` exists in the installed v16 version.

Installed source is authoritative for this project.

---

# Architecture Requirement

Do NOT create five separate lifecycle implementations such as:

- custom Quotation update engine
- custom Sales Order update engine
- custom Purchase Order update engine
- custom Customer update engine
- custom Item update engine

Create/reuse a shared lifecycle layer.

Conceptually:

```text
MCP Profile Tool
      ↓
Profile DocType Allowlist
      ↓
Shared Lifecycle Service
      ↓
Identity / Permission
      ↓
Metadata / Validation
      ↓
Prepare Action
      ↓
Approval / Confirmation
      ↓
Revalidate
      ↓
Native Frappe Document API
```

Profile-specific MCP exposure should remain thin.

---

# Safety Principle

Every mutation must target an **exact document identity**:

```text
doctype
name
```

Example:

```text
doctype = "Sales Order"
name = "SAL-ORD-00015"
```

Never accept destructive execution based only on:

```text
customer = ABC
status = Draft
date < ...
all quotations
all old orders
```

No bulk mutation in this task.

---

# Part A — Existing Document Update

Implement safe updates to an existing supported document.

Example user requests:

```text
Add "Urgent delivery" to the remarks of SAL-ORD-00015.
```

```text
Change the quantity in this draft Sales Order from 2 to 5.
```

```text
Change the delivery date on this Quotation.
```

## Update Flow

```text
Exact document
      ↓
Load current document
      ↓
Profile allowlist
      ↓
Read/write permission
      ↓
Inspect docstatus
      ↓
Validate requested fields
      ↓
Resolve values where required
      ↓
Prepare change set
      ↓
Show OLD → NEW preview
      ↓
User confirmation
      ↓
Re-fetch + revalidate
      ↓
Native save
```

## Update Preview

The preview must make the change obvious.

Example:

```text
Sales Order: SAL-ORD-00015
Status: Draft

Proposed changes:

Field       Current value        New value
------------------------------------------------
Remarks     Empty                Urgent delivery

Action: UPDATE

Confirm?
```

For child-table updates:

```text
Sales Order: SAL-ORD-00015

Item:
SV-FRAPPE-DEVELOPMENT

Quantity:
2 → 5
```

Do not return an enormous raw document dump.

Show only useful identifying information and proposed changes.

## Update Validation

At minimum validate:

- DocType is allowed by current MCP profile
- document exists
- authenticated Frappe user can read/write it
- field exists
- field is actually writable
- field type is valid
- Link values are valid
- Select values are valid
- required relationships remain valid
- requested child row can be uniquely identified
- current docstatus allows the requested modification

Reuse the metadata/resolver/field validation foundation already implemented in the repository.

## Never Update System-Controlled Fields Directly

Generic update must reject direct mutation of framework/system fields such as:

- `name`
- `owner`
- `creation`
- `modified`
- `modified_by`
- `docstatus`
- `idx`
- parent metadata fields
- other framework-controlled fields

`docstatus` changes must happen only through submit/cancel APIs implemented below.

## Draft Updates

For Draft documents, use the normal Frappe document save path.

Do not use direct database writes to bypass:

- controller validation
- hooks
- permissions
- ERPNext business validation

## Submitted Document Updates

Do NOT automatically cancel/amend a submitted document because the user requested an update.

Use the installed Frappe framework's normal submitted-document validation.

If the requested field/change is legitimately allowed after submit by Frappe/ERPNext, allow the normal framework path to handle it.

Otherwise return a clean result such as:

```text
Sales Order SAL-ORD-00015 is Submitted.

The requested field cannot be modified after submission.

No changes were made.
```

Do not bypass this using `db_set`, SQL, permission flags, or internal hacks.

## Cancelled Document Updates

Normal update of a Cancelled transaction should be rejected.

Do not automatically create an amendment in this task.

Amendment support is out of scope.

## Child Table Updates

Support safe modification of an existing child row when the user's request identifies it unambiguously.

Examples:

- quantity
- rate where ERPNext permits it
- delivery date
- other normal editable row fields

Use stable row identity where available.

If identifying an item produces multiple possible child rows, return ambiguity rather than updating the wrong row.

Do not silently update every matching row.

Do not implement arbitrary raw child-table replacement.

---

# Part B — Submit Existing Document

Submit applies only to genuinely submittable DocTypes.

Expected current applicability:

```text
Quotation       → applicable
Sales Order     → applicable
Purchase Order  → applicable

Customer        → not applicable
Item            → not applicable
```

Do not hardcode this assumption if metadata can answer it.

Use current DocType metadata such as the framework's `is_submittable` information.

## Submit Flow

```text
Exact document
      ↓
Load document
      ↓
Profile allowed?
      ↓
Is submittable?
      ↓
docstatus == Draft?
      ↓
Submit permission?
      ↓
Prepare submit preview
      ↓
User confirmation
      ↓
Re-fetch
      ↓
Revalidate state
      ↓
Native doc.submit()
```

Example preview:

```text
Sales Order: SAL-ORD-00015
Current status: Draft
Action: SUBMIT

After submission, normal editing will be restricted.

Confirm submit?
```

## Submit Rules

Do not:

- directly set `docstatus = 1`
- bypass submit permissions
- skip ERPNext validation
- skip controller hooks
- bypass configured workflow/business validation

Use the native document submission path.

If ERPNext validation rejects submission, preserve the transaction and return a concise structured explanation.

## Submit Invalid State Handling

Examples:

Already submitted:

```text
Sales Order SAL-ORD-00015 is already Submitted.
No action performed.
```

Cancelled:

```text
Sales Order SAL-ORD-00015 is Cancelled and cannot be submitted directly.
No action performed.
```

Non-submittable:

```text
Customer ABC is not a submittable DocType.
No action performed.
```

---

# Part C — Cancel Existing Document

Cancel is a destructive/state-changing operation and requires confirmation.

Only Submitted submittable documents can normally be cancelled.

## Cancel Flow

```text
Exact target
     ↓
Load document
     ↓
Check profile
     ↓
Check docstatus
     ↓
Check cancel permission
     ↓
Inspect cancellation blockers / linked submitted docs
     ↓
Prepare preview
     ↓
Confirmation
     ↓
Revalidate
     ↓
Native doc.cancel()
```

Example:

```text
Sales Order: SAL-ORD-00015
Current status: Submitted
Action: CANCEL

Confirm cancellation?
```

## Linked Documents During Cancel

Inspect installed Frappe's native linked-document/cancellation behavior first.

If another submitted document prevents cancellation:

DO NOT silently cancel that other document.

Return the exact blocker.

Example:

```text
Cannot cancel Sales Order SAL-ORD-00015.

Blocking submitted document:

Sales Invoice: ACC-SINV-00020

No documents were changed.
```

This is especially important because Sales Invoice lifecycle actions are outside the scope of this task.

Do not expand scope by cancelling unsupported downstream documents.

The user can explicitly request lifecycle actions for another supported document separately.

---

# Part D — Delete Existing Document

Delete is the highest-risk action in this task.

Deletion ALWAYS requires preparation + explicit confirmation.

There is no direct unconfirmed delete path.

# Exact-Target Delete Only

Allowed concept:

```text
Delete Sales Order SAL-ORD-00015.
```

Not allowed:

```text
Delete all Sales Orders for ABC.
```

Not allowed:

```text
Delete all Draft Quotations.
```

Not allowed:

```text
Delete orders older than 30 days.
```

No filter-based or bulk deletion endpoint/tool should be created.

## Delete Preflight

Before asking for confirmation determine:

1. exact target exists
2. user has required permission
3. target docstatus
4. whether DocType is submittable
5. static Link blockers
6. Dynamic Link blockers
7. submitted cancellation blockers where applicable
8. whether deletion is currently possible through normal Frappe behavior

Use native Frappe link-discovery mechanisms where available in the installed version.

Do not invent a custom SQL graph walker if Frappe already provides appropriate APIs/helpers.

## Case 1 — Draft / Non-Submitted Document With No Blockers

Preview:

```text
Sales Order: SAL-ORD-00015
Status: Draft

Action: DELETE

This will delete this exact document.

Confirm delete?
```

After confirmation use the normal Frappe deletion path.

## Case 2 — Submitted Target

A submitted target must NOT be directly deleted.

If the exact target itself can safely be cancelled and then deleted, prepare one explicit plan:

```text
Sales Order: SAL-ORD-00015
Status: Submitted

Required actions:

1. Cancel Sales Order SAL-ORD-00015
2. Delete Sales Order SAL-ORD-00015

No other documents will be modified.

Confirm these actions?
```

Only after confirmation:

```text
cancel target
     ↓
verify target is Cancelled
     ↓
re-check delete blockers
     ↓
delete target
```

This is allowed because both actions concern the exact same document the user requested to delete.

If cancellation or deletion becomes blocked after confirmation, stop safely.

Do not force through the failure.

## Case 3 — Linked / Dependent Documents Exist

This is critical.

If deleting the target would require modifying, cancelling, unlinking, or deleting another business document:

STOP.

Do not automatically cascade.

Example:

```text
Cannot currently delete Quotation QTN-00010.

Blocking document:

Sales Order: SAL-ORD-00015

No documents were changed.

The linked Sales Order must be handled explicitly before this Quotation can be deleted.
```

The MCP must not silently:

- delete SAL-ORD-00015
- cancel SAL-ORD-00015
- clear its Quotation reference
- mutate its Link field
- use force delete

This preserves the rule:

> Only modify/delete the document the user explicitly requested.

## No Automatic Business Unlinking

Do not make a generic feature that clears Link fields from other business documents just to make deletion succeed.

Use Frappe's normal deletion behavior.

Framework-owned cleanup that Frappe itself performs as part of a normal successful `delete_doc` is fine.

Custom business-document unlinking is not.

## Customer and Item Delete Safety

Customer and Item may be referenced by many business documents.

If Frappe reports blocking business references:

return the blockers.

Do not cascade-delete or modify Quotations, Sales Orders, Purchase Orders, invoices, etc. merely to delete the Customer or Item.

Example:

```text
Cannot delete Customer ABC.

Blocking references were found.

No records were modified.
```

## Forbidden Delete Bypasses

Lifecycle code must never use these merely to make a requested deletion succeed:

```python
force=True
ignore_permissions=True
```

Do not use direct:

```python
frappe.db.delete(...)
```

or raw SQL for normal lifecycle deletion.

Use standard document deletion APIs so framework hooks, permissions and link validation remain active.

---

# Confirmation / Approval Requirements

Reuse the project's existing approval mechanism.

Do not create another confirmation store.

Mutating actions requiring confirmation:

- Update
- Submit
- Cancel
- Delete
- Submitted target Cancel + Delete plan

The prepare response must include enough information for the user to understand exactly what will change.

# Confirmation Must Be Bound to Exact Action

Approval must be tied to at least:

- authenticated user
- MCP profile
- action
- DocType
- document name
- proposed changes/action plan
- relevant current document state

Do not allow:

```text
prepare delete SO-001
```

followed by the same approval being reused for:

```text
delete SO-002
```

# Stale Confirmation Protection

Between prepare and confirmation, another user/process may modify the document.

Before execution:

1. re-fetch the document
2. verify it still exists
3. verify expected docstatus
4. verify permissions again
5. verify relevant source state has not materially changed
6. re-check links for cancel/delete
7. reject stale approval if the original plan is no longer valid

Example:

```text
The document changed after the preview was prepared.

No action was performed.

Please prepare the action again.
```

Do not execute an outdated destructive plan.

Reuse an existing repository fingerprint/version mechanism if one already exists.

# Atomicity

For a multi-step operation on the same target, especially:

```text
Cancel target
Delete target
```

avoid leaving a half-completed state because step 2 failed unexpectedly.

First inspect whether installed Frappe provides a native transaction/helper pattern suitable for this operation.

Use normal Frappe transaction behavior and rollback safely on failure.

Do not commit midway merely to simplify implementation.

---

# MCP Tool Design

Do not expose one tool per DocType unless the existing architecture specifically requires it.

Prefer operation-level shared lifecycle capability with profile-scoped DocType allowlists.

Conceptually:

```text
prepare update
prepare submit
prepare cancel
prepare delete
```

plus the repository's existing confirmation/execution mechanism.

However:

**follow the current repository's established tool naming and approval pattern rather than blindly introducing these exact names.**

If the repository already has a generic confirmation executor, extend it.

If it uses operation-specific confirmation tools, stay consistent.

Avoid duplicate lifecycle engines.

# Profile Isolation

The shared service can be generic internally.

The MCP profile must still control what the agent can access.

Example concept:

```text
sales profile
    → only current sales/master lifecycle scope

purchase profile
    → only current purchase/master lifecycle scope
```

Do not allow a generic lifecycle input to escape the profile allowlist.

A user must not obtain arbitrary Frappe DocType mutation merely by passing another DocType string.

Fail closed.

# Error Response Quality

Errors should be short and actionable.

Preferred format:

```text
Action: Delete
Document: Sales Order SAL-ORD-00015
Result: Blocked

Reason:
Linked submitted document exists:
Sales Invoice ACC-SINV-00020

Changes made: None
```

Do not dump large tracebacks or internal implementation details into normal MCP output.

Preserve detailed diagnostics in appropriate internal logging if the repository already has that pattern.

---

# Implementation Sequence

## Step 1
Inspect existing lifecycle/approval/profile architecture and installed Frappe native APIs.

## Step 2
Build/reuse shared document loading + exact-target validation.

## Step 3
Implement Update prepare + confirmation execution.

## Step 4
Implement Submit prepare + confirmation execution.

## Step 5
Implement Cancel preflight + confirmation execution.

## Step 6
Implement Delete preflight + confirmation execution.

## Step 7
Add stale-confirmation/state revalidation.

## Step 8
Expose capabilities through the correct MCP profiles.

## Step 9
Add automated tests.

## Step 10
Update only directly relevant documentation.

If this work introduces or changes a reusable project-specific run/start/test command, update `docs/COMMANDS.md` according to the project's command-registry rule.

Do not add generic commands.

---

# Required Tests

## Update Tests

### Test U1 — Parent Field Update
Create/use Draft Sales Order.

Change remarks.

Expected:

```text
prepare
→ correct old/new preview
→ no mutation before confirmation
→ confirm
→ saved successfully
```

### Test U2 — Child Row Update
Change quantity on one uniquely identified existing row.

Expected:

- only correct row changes
- no unrelated row changes

### Test U3 — Ambiguous Child Row
Two rows make requested target ambiguous.

Expected:

- no mutation
- ambiguity returned

### Test U4 — Invalid Field
Expected:

- rejected
- no mutation

### Test U5 — Submitted Forbidden Field
Expected:

- native submitted-document restriction respected
- no bypass
- no mutation

### Test U6 — Permission Denied
Expected:

- denied
- no mutation

## Submit Tests

### Test S1
Draft Quotation → Submit.

Expected:

```text
0 → 1
```

only after confirmation.

### Test S2
Draft Sales Order → Submit.

### Test S3
Draft Purchase Order → Submit.

### Test S4
Submit Customer.

Expected:

```text
rejected as non-submittable
```

### Test S5
Already Submitted transaction.

Expected:

- no mutation
- clear result

## Cancel Tests

### Test C1
Submitted supported transaction → Cancel.

Expected:

```text
1 → 2
```

only after confirmation.

### Test C2
Draft transaction → Cancel.

Expected:

- rejected
- no mutation

### Test C3
Submitted target with downstream submitted blocker.

Expected:

- blocker shown
- blocker not automatically cancelled
- target unchanged

## Delete Tests

### Test D1 — Draft No Links
Exact Draft Quotation with no blockers.

Expected:

- prepare only previews
- confirm deletes exact target

### Test D2 — No Confirmation
Expected:

- document remains

### Test D3 — Submitted No External Blocker
Expected prepare plan:

```text
Cancel target
Delete target
```

After confirmation:

- exact target cancelled/deleted
- no unrelated documents changed

### Test D4 — Linked Document
Target has blocking business Link.

Expected:

- deletion blocked
- exact blocking DocType/name reported where user can read it
- linked record not modified
- target not deleted

### Test D5 — Customer With Business References
Expected:

- blocked
- no cascade

### Test D6 — Item With Business References
Expected:

- blocked
- no cascade

### Test D7 — Bulk Delete Attempt
Input equivalent to:

```text
delete all Draft Sales Orders
```

Expected:

- lifecycle mutation tool cannot execute filter/bulk deletion

### Test D8 — Permission Denied
Expected:

- no deletion

### Test D9 — Submitted Target With Unsupported Downstream Doc
Example downstream Sales Invoice.

Expected:

- blocker reported
- Sales Invoice untouched
- target untouched

## Approval Safety Tests

### Test A1 — Prepare Does Not Mutate
For every action:

```text
prepare
```

must not change ERPNext data.

### Test A2 — Approval Bound to Target
Approval prepared for:

```text
Sales Order SO-001
```

must not work for:

```text
Sales Order SO-002
```

### Test A3 — Approval Bound to Action
Update approval must not authorize Delete.

### Test A4 — Stale State
Prepare action.

Modify target separately before confirmation.

Expected:

- confirmation rejected as stale
- action must be prepared again

### Test A5 — Cross-User
One authenticated user's approval must not authorize another user's action.

### Test A6 — Cross-Profile
Approval prepared under one MCP profile must not escape profile restrictions.

---

# Regression Tests

Existing flows must continue working:

- Customer Draft creation
- Item Draft creation
- Quotation Draft creation
- Sales Order Draft creation
- Purchase Order Draft creation
- search/resolution
- metadata validation
- approval workflow
- MCP identity
- sales profile
- purchase profile
- stdio transport if currently supported
- streamable-http transport if currently supported

No regression to existing create flow.

---

# Acceptance Criteria

The task is complete only when:

- existing Draft documents can be safely updated
- child-row update works for an unambiguous existing row
- Quotation can be submitted/cancelled
- Sales Order can be submitted/cancelled
- Purchase Order can be submitted/cancelled
- Customer/Item correctly reject Submit/Cancel
- exact documents can be deleted after confirmation
- submitted target deletion correctly handles Cancel → Delete for the same target
- linked business documents block destructive actions instead of being silently altered
- no bulk/filter delete exists
- no automatic cascade delete exists
- no generic business unlink exists
- no `force=True` lifecycle bypass exists
- no `ignore_permissions=True` lifecycle bypass exists
- normal Frappe validation/hooks run
- current user's Frappe permissions are honored
- profile boundaries are honored
- prepare actions never mutate data
- confirmation is bound to exact target/action/user
- stale confirmation is rejected
- existing create flows still pass

---

# Expected Result

After implementation the following conversations should be possible.

## Update

```text
User:
Add "Urgent delivery" to remarks in SAL-ORD-00015.

Assistant:
Shows exact change preview.

User:
Confirm.

Result:
Only SAL-ORD-00015 is updated.
```

## Submit

```text
User:
Submit SAL-ORD-00015.

Assistant:
Shows Draft → Submitted preview.

User:
Confirm.

Result:
Sales Order submitted.
```

## Delete Draft

```text
User:
Delete QTN-00010.

Assistant:
Shows delete confirmation.

User:
Confirm.

Result:
Only QTN-00010 deleted.
```

## Delete Submitted

```text
User:
Delete SAL-ORD-00015.

Assistant:
Sales Order is Submitted.

Required actions:
1. Cancel SAL-ORD-00015
2. Delete SAL-ORD-00015

Confirm?

User:
Confirm.

Result:
Exact Sales Order cancelled and deleted.
```

## Delete With Dependency

```text
User:
Delete SAL-ORD-00015.

Assistant:
Cannot currently delete SAL-ORD-00015.

Blocking document:
Sales Invoice ACC-SINV-00020

No documents were changed.
```

That is correct behavior for this phase.

---

# Limitations

This phase intentionally does not attempt to complete the whole ERPNext sales/purchase lifecycle.

It only completes lifecycle operations for already-supported documents.

Do not add downstream transactions just because they are encountered as linked documents.

---

# Exact Next Task

After this implementation passes automated tests, the next task is:

**MCP Existing Document Lifecycle End-to-End Verification**

Verify Update → Submit → Cancel → Delete through the actual MCP client/Inspector and both `sales` and `purchase` profiles.

Do not begin Sales Invoice, Payment Entry, Purchase Receipt, or Purchase Invoice implementation as part of that verification.

---

# Final Agent Report

When finished, report only:

1. files created/modified
2. shared lifecycle architecture added/reused
3. MCP tools/actions added
4. profile exposure
5. installed Frappe native APIs/helpers reused
6. update behavior implemented
7. submit/cancel behavior implemented
8. delete/link-blocker behavior implemented
9. approval/stale-state protections
10. tests added and results
11. documentation changes
12. any known limitations

Do not claim completion unless the automated tests pass.
