# MCP ERPNext Existing Document Read / Retrieve Tools

## Objective

Add safe read-only MCP capabilities for retrieving existing ERPNext documents and their current state/status.

The immediate missing use case is:

> "Vertex Learning Pvt Ltd ka Sales Order hai, uski status kya hai?"

Current behavior can resolve the Customer, but cannot search/list/read existing Sales Orders. This task must close that gap.

This task is READ-ONLY.

It must not create, update, submit, cancel, delete, or otherwise mutate ERPNext data.

---

# Current Problem

The existing MCP server already has tools such as customer/item search and create preparation flows.

However, for existing transactions, the agent currently cannot reliably answer questions such as:

- Show Sales Orders for Customer X.
- What is the current status of Sales Order SO-0001?
- Does Customer X have any Draft Sales Orders?
- Show recent Quotations for Customer X.
- Get Purchase Order PO-0001.
- What is the docstatus/status of this existing transaction?

The MCP server must expose read-only retrieval capabilities for supported documents.

---

# Supported Scope

Implement retrieval only for DocTypes already supported by the current MCP profiles.

Current target DocTypes:

- Quotation
- Sales Order
- Purchase Order
- Customer
- Item

Respect current profile boundaries.

Do not expose an arbitrary DocType query API.

The exact DocTypes allowed under each MCP profile must be derived from the repository's existing profile configuration/tool registration.

---

# Explicitly Out of Scope

Do NOT implement:

- arbitrary SQL querying
- arbitrary DocType querying
- unrestricted field/filter APIs
- report builder
- Sales Invoice tools
- Payment Entry tools
- Purchase Invoice tools
- Purchase Receipt tools
- Delivery Note tools
- downstream document creation
- write/update/submit/cancel/delete behavior
- bulk export
- raw database access
- `ignore_permissions=True`
- permission bypasses

No data mutation is permitted in this task.

---

# Mandatory First Step — Inspect Existing Architecture

Before implementing anything, inspect the current repository and identify:

- existing `search_customers` implementation
- existing `search_items` implementation
- resolver/search utilities
- Frappe context/identity handling
- MCP profile registration
- current result/error schemas
- current tool naming conventions
- permission checks
- metadata helpers
- test conventions

Reuse existing shared search/read infrastructure where appropriate.

Do not build a second independent query layer if the repository already has reusable helpers.

Also inspect the installed Frappe/ERPNext v16 implementation before adding custom query logic.

Prefer normal Frappe read APIs such as:

- `frappe.get_doc`
- `frappe.get_all` / `frappe.get_list` where appropriate
- permission-aware document reads
- DocType metadata

Use the installed framework/app source as the authoritative behavior for this project.

---

# Architecture Requirement

Use a shared internal read/retrieval service.

Do NOT duplicate the full query logic separately for every DocType.

Conceptually:

```text
MCP Profile Tool
      ↓
Profile DocType Allowlist
      ↓
Shared Read / Search Service
      ↓
Authenticated Frappe User Context
      ↓
Permission Checks
      ↓
Frappe Read APIs
      ↓
Compact Structured Result
```

Profile-level tools may remain explicit for good MCP discoverability, but their implementation should reuse shared internals.

---

# Required Capability 1 — Get Exact Existing Document

Support retrieving an exact existing document using:

```text
doctype
name
```

Example:

```text
Sales Order
SAL-ORD-00015
```

Expected questions:

- "SAL-ORD-00015 ki status kya hai?"
- "QTN-00010 dikhao."
- "PO-00024 ka current state kya hai?"

The result should contain a compact useful summary, not the full raw database document.

---

# Required Capability 2 — Search / List Existing Documents

Support safe list/search retrieval for currently supported transaction DocTypes.

Immediate required examples:

## Sales Order

Search/list by useful business criteria such as:

- customer
- exact/partial document name
- docstatus/state
- current ERPNext status
- transaction/order date
- reasonable recent limit

## Quotation

Useful criteria such as:

- quotation_to / party/customer where relevant
- party name
- exact/partial document name
- docstatus/state
- status
- transaction date
- reasonable recent limit

## Purchase Order

Useful criteria such as:

- supplier
- exact/partial document name
- docstatus/state
- status
- transaction date
- reasonable recent limit

Do not create a generic user-controlled filter language that can query arbitrary fields.

Expose only intentionally supported filters.

---

# Master Retrieval

Customer and Item already have search capabilities.

Inspect whether the existing tools are sufficient.

If exact read/details are missing and are needed for consistent retrieval architecture, add safe exact-read capability for Customer and Item.

Do not duplicate existing search tools unnecessarily.

---

# Sales Order Status Use Case — Must Work

After this task, the following request must be answerable through MCP:

```text
User:
Vertex Learning Pvt Ltd ka Sales Order hai uski status kya hai?
```

Expected MCP flow:

```text
search_customers("Vertex Learning Pvt Ltd")
        ↓
exact customer resolved
        ↓
search/list Sales Orders for that exact customer
        ↓
0 results → clearly say none found
1 result  → return document + current status
many      → return compact list so agent/user can identify the relevant order
```

Example result for multiple orders:

```text
Sales Orders for Vertex Learning Pvt Ltd:

1. SAL-ORD-00015
   Status: Draft
   Docstatus: 0
   Date: 2026-09-01
   Grand Total: ...

2. SAL-ORD-00011
   Status: Completed
   Docstatus: 1
   Date: 2026-08-20
   Grand Total: ...
```

Do not invent statuses.

Read the actual current values from ERPNext.

---

# Status vs Docstatus

Where a transaction has both:

- framework `docstatus`
- ERPNext business `status`

return both where useful.

Example:

```text
Document: SAL-ORD-00015
Docstatus: 1 (Submitted)
Status: To Deliver and Bill
```

Do not treat `docstatus` and business `status` as the same thing.

Use values actually present in the current ERPNext document.

---

# Result Shape

Keep tool results concise and LLM-friendly.

For Sales Order list/search, useful fields may include:

- name
- customer
- transaction_date
- delivery_date where useful
- docstatus
- status
- currency
- grand_total

For Quotation:

- name
- party/customer
- transaction_date
- valid_till where useful
- docstatus
- status
- currency
- grand_total

For Purchase Order:

- name
- supplier
- transaction_date
- schedule_date where useful
- docstatus
- status
- currency
- grand_total

Exact field selection must be verified against the installed ERPNext version.

Do not expose huge child tables in list results.

---

# Exact Document Detail Result

Exact-get may return somewhat more information than list/search.

However, still return a compact business summary.

For transactions, useful detail may include:

- identifying fields
- current `docstatus`
- current business `status`
- dates
- party
- totals
- a compact item summary

If items are returned, include only useful fields such as:

- item_code
- item_name
- qty
- rate
- amount

Do not dump every internal/system field.

---

# Pagination / Limits

Search/list operations must be bounded.

Implement a safe default result limit.

Use the repository's existing conventions if present.

If none exist, choose a conservative default and a hard maximum.

Do not permit unlimited reads.

Return enough information for the user/agent to refine the query.

---

# Ordering

For business list queries, use a deterministic useful order.

Prefer recent documents first unless the existing architecture already establishes another convention.

Do not rely on unspecified database ordering.

---

# Permission Safety

All reads must respect the authenticated Frappe user.

Requirements:

- honor current user permissions
- honor User Permissions where Frappe applies them
- honor document-level access
- never use `ignore_permissions=True`
- never leak inaccessible documents merely because another customer/document name was guessed

If the user cannot read a document, fail safely.

Do not reveal sensitive details from inaccessible documents in an error.

---

# Profile Isolation

The internal service may be generic, but MCP exposure must remain profile-scoped.

Example intent:

```text
sales profile
    → Quotation
    → Sales Order
    → currently allowed sales/master reads

purchase profile
    → Purchase Order
    → currently allowed purchase/master reads
```

The exact allowlist must come from current repository architecture.

Passing another DocType string must not escape the profile boundary.

Fail closed.

---

# Suggested Tool Shape

First inspect current naming conventions.

Do not blindly use these names if the project already follows a different pattern.

A discoverable profile-level design could be:

```text
search_sales_orders
get_sales_order

search_quotations
get_quotation

search_purchase_orders
get_purchase_order
```

Customer/Item exact read tools should only be added if actually useful and not already covered by existing tools.

Internally these tools should reuse a shared read/search service.

Avoid a public tool such as:

```text
query_any_doctype(doctype, filters, fields)
```

That is too broad for the current architecture.

---

# Search Resolution Behavior

If the user supplies a customer/supplier name, reuse existing entity resolution instead of implementing fuzzy matching again inside transaction search.

Example:

```text
"Vertex Learning Pvt Ltd"
      ↓
existing customer resolver/search
      ↓
exact Customer name
      ↓
Sales Order search using exact resolved customer
```

Do not silently guess among ambiguous customer matches.

If multiple customers match, return ambiguity first.

The same principle applies to suppliers where relevant.

---

# Empty / Single / Multiple Results

## No results

Return:

```text
No Sales Orders found for Customer "Vertex Learning Pvt Ltd".
```

No mutation.

## One result

Return the compact document summary directly.

## Multiple results

Return a short list with enough fields to distinguish the documents.

Do not arbitrarily pick one unless the user's query uniquely identifies it.

---

# Error Quality

Errors should be concise and actionable.

Example:

```text
Action: Search Sales Orders
Result: No records found

Customer:
Vertex Learning Pvt Ltd

Changes made: None
```

Permission example:

```text
Action: Get Sales Order
Result: Access denied

The current ERPNext user cannot read this Sales Order.

Changes made: None
```

Do not expose raw tracebacks in normal MCP output.

Preserve detailed diagnostics only through existing internal logging conventions.

---

# Implementation Sequence

## Step 1
Inspect current search/resolver/profile architecture.

## Step 2
Design/reuse a shared permission-aware read/search service.

## Step 3
Implement exact transaction retrieval.

## Step 4
Implement bounded Sales Order search/list retrieval.

## Step 5
Implement bounded Quotation search/list retrieval.

## Step 6
Implement bounded Purchase Order search/list retrieval.

## Step 7
Reuse Customer/Item search and add exact read only if needed.

## Step 8
Expose tools through correct MCP profiles.

## Step 9
Add automated tests.

## Step 10
Update directly relevant MCP/tool documentation.

If implementation introduces or changes a reusable project-specific run/test command, update `docs/COMMANDS.md`.

Do not add generic commands.

---

# Required Tests

## Sales Order

### SO-R1 — Exact Get

Retrieve an existing Sales Order by exact name.

Expected:

- correct document
- correct docstatus
- correct current status
- compact result

### SO-R2 — Search by Customer

Search Sales Orders for one exact resolved Customer.

Expected:

- only matching readable Sales Orders
- deterministic ordering
- bounded result count

### SO-R3 — No Orders

Customer exists but has no Sales Orders.

Expected:

- empty result / clear no-record result
- no error pretending the customer is missing

### SO-R4 — Multiple Orders

Customer has multiple Sales Orders.

Expected:

- return compact list
- do not arbitrarily select one

### SO-R5 — Status Accuracy

Verify returned `docstatus` and ERPNext `status` against the actual database document.

### SO-R6 — Permission Denied

Current user cannot read a Sales Order.

Expected:

- document not exposed
- no permission bypass

---

# Quotation Tests

### Q-R1
Get exact Quotation.

### Q-R2
Search Quotations by resolved customer/party.

### Q-R3
Multiple Quotations return a compact list.

### Q-R4
Permission restrictions are honored.

---

# Purchase Order Tests

### PO-R1
Get exact Purchase Order.

### PO-R2
Search Purchase Orders by Supplier.

### PO-R3
Multiple Purchase Orders return a compact list.

### PO-R4
Permission restrictions are honored.

---

# Profile Isolation Tests

### P-R1

Sales profile cannot use read service to query a DocType outside its allowlist.

### P-R2

Purchase profile cannot escape its allowlist.

### P-R3

Passing an arbitrary DocType name to internal/public parameters fails closed.

---

# Read-Only Safety Tests

### RO-1

Run all search/get tools.

Expected:

- no modified timestamp changes caused by the tool
- no document save
- no submit/cancel/delete
- no approval state required

### RO-2

No tool uses:

```python
ignore_permissions=True
```

for normal reads.

### RO-3

No raw SQL mutation exists.

---

# Regression Tests

Existing functionality must continue working:

- `search_customers`
- `search_items`
- customer creation flow
- item creation flow
- quotation creation flow
- sales order creation flow
- purchase order creation flow
- existing resolver logic
- existing approval mechanism
- MCP identity
- sales profile
- purchase profile
- supported transports

---

# Acceptance Criteria

This task is complete only when:

- an exact Sales Order can be retrieved by name
- Sales Orders can be searched/listed for an exact resolved Customer
- current `docstatus` is returned correctly
- current ERPNext business `status` is returned correctly
- zero/one/multiple Sales Order results are handled correctly
- existing Quotations can be retrieved/searched
- existing Purchase Orders can be retrieved/searched
- Customer/Item existing search behavior is reused rather than duplicated
- read operations respect current Frappe permissions
- profile boundaries are enforced
- result sets are bounded
- output is compact and useful
- no arbitrary DocType query tool is exposed
- no write behavior is introduced
- all automated tests pass
- existing create flows remain unaffected

---

# End-to-End Verification Prompt

After implementation, verify through the actual MCP client with:

```text
Vertex Learning Pvt Ltd ka Sales Order hai uski status abhi kya hai batao using MCP.
```

Expected behavior:

1. resolve `Vertex Learning Pvt Ltd`
2. query existing Sales Orders for that exact Customer
3. if one order exists, report its current status
4. if multiple exist, list them with current status and ask/allow user to identify the relevant order
5. if none exist, clearly say no Sales Orders were found
6. perform no ERPNext mutation

Also verify:

```text
SAL-ORD-00015 ki current status kya hai?
```

and:

```text
Vertex Learning Pvt Ltd ki recent Quotations dikhao.
```

For purchase profile verify an equivalent Purchase Order lookup.

---

# Limitations

This task only adds read/retrieve capabilities for already-supported documents.

It does not implement:

- Sales Invoice
- Payment Entry
- Purchase Invoice
- Purchase Receipt
- arbitrary reporting
- analytics
- write actions

---

# Exact Next Task

After this task passes automated and MCP end-to-end verification, continue with the separately defined:

**Existing Document Lifecycle — Update, Submit, Cancel, Delete**

Do not merge downstream transaction creation into this read/retrieve task.

---

# Final Agent Report

When finished, report:

1. files created/modified
2. shared read/search architecture added/reused
3. MCP tools added
4. profile exposure
5. Frappe APIs/helpers reused
6. fields returned for list vs exact-get
7. permission enforcement
8. result limits/order
9. tests added and results
10. end-to-end MCP verification result
11. documentation changes
12. known limitations

Do not claim completion unless automated tests pass.
