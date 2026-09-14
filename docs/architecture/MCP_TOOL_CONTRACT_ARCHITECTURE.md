# MCP Tool Contract Architecture Standard

## Status

Project-level architecture standard for `mcp_erpnext`.

This document is intentionally **not Quotation-specific**. It defines how every current and future public MCP tool should expose its contract to LibreChat, OpenAI-compatible clients, MCP Inspector, coordinator agents, and any future MCP client.

Quotation is the first migration target because it exposed the current schema weakness in a real LibreChat conversation.

---

## 1. Problem This Standard Solves

A public MCP tool is an API contract.

If a tool exposes generic inputs such as:

```python
items: list[dict[str, Any]]
```

the model/client must guess keys, nesting, valid values, and required fields.

That produces fragile calls such as:

```json
{
  "item_code": "SV-FRAPPE-DEVELOPMENT",
  "quantity": 2
}
```

when the service actually requires:

```json
{
  "item": {
    "doctype": "Item",
    "name": "SV-FRAPPE-DEVELOPMENT"
  },
  "qty": 2
}
```

The fix must therefore be architectural:

> Every public MCP tool must have an explicit, stable, testable input and output contract.

Do not solve this only for Quotation.

---

## 2. Target Layering

```text
LibreChat / MCP Inspector / future Agent Client
                    |
                    v
          MCP Public Tool Contract
          - exact tool name
          - description
          - typed input schema
          - typed output schema
          - side-effect classification
                    |
                    v
             Thin MCP Wrapper
          - request Context only
          - identity is runtime-only
          - typed model -> service payload
          - service result -> typed result
                    |
                    v
             Domain Service Layer
          - Customer
          - Item
          - Quotation
          - Sales Order
          - Sales Invoice
          - Payment Entry
          - Stock
          - Accounting
          - future domains
                    |
                    v
             ERPNext / Frappe
          - real permissions
          - validation
          - business rules
```

The public schema belongs at the MCP boundary.

ERPNext/Frappe services remain authoritative for business behavior.

---

## 3. Contract Families

Every tool should belong to a clear operation family.

### 3.1 Search tools

Examples:

```text
search_customers
search_items
future: search_invoices
```

Typical input:

```text
query
optional filters/limits only when intentionally supported
```

Typical output:

```text
status
doctype/resource type
query
candidates[]
```

Search remains read-only.

---

### 3.2 Query tools

Examples:

```text
query_customers
query_items
query_sales_orders
query_quotations
```

Use `query_*` for deterministic, field-aware multi-record retrieval with explicit
filters, field projection, sorting, and pagination. Query tools remain read-only
and are distinct from fuzzy/discovery-oriented `search_*` tools.

---

### 3.3 Aggregate tools

Examples:

```text
aggregate_customers
aggregate_items
aggregate_sales_orders
aggregate_quotations
```

Use `aggregate_*` for deterministic server-side analytics such as counts,
sums, averages, minimums, maximums, and grouping. Aggregate tools must not
fetch a source page merely for a client or model to calculate the result.

---

### 3.4 Exact read tools

Examples:

```text
get_customer
get_item
get_sales_order
get_quotation
```

Use `get_*` when the caller knows the exact document or reference and wants
selected details. Exact reads remain permission-aware and read-only.

---

### 3.5 Resolve tools

Examples:

```text
resolve_customer
resolve_item
future: resolve_warehouse
future: resolve_sales_order
```

Input is user/query text.

Output must distinguish deterministic states such as:

```text
resolved
ambiguous
not_found
error
```

A resolved response should return a typed ERP reference.

An ambiguous response must return typed candidates.

The output contract must never silently convert ambiguity into an arbitrary selection.

---

### 3.6 Prepare tools

Examples:

```text
prepare_customer
prepare_item
prepare_quotation
prepare_sales_order
future: prepare_sales_invoice
future: prepare_payment_entry
```

Prepare tools receive already-resolved references where required.

Prepare must remain non-persistent unless the specific architecture explicitly defines otherwise.

Typical output:

```text
status
preview
approval_token / confirmation handle when applicable
missing/validation details when applicable
```

A prepare tool must not accept a vague public structure merely because the internal service uses dictionaries.

---

### 3.7 Confirm tools

Examples:

```text
confirm_customer
confirm_item
confirm_quotation
confirm_sales_order
future: confirm_sales_invoice
future: confirm_payment_entry
```

Confirm is the write boundary.

Typical input:

```text
approval_token
confirm
```

Typical output:

```text
created / cancelled / error
doctype
name
reference
```

The exact explicit-user-approval enforcement mechanism is handled by the dedicated approval-safety task, but every confirm tool must be classified as write-capable in the contract metadata/docs.

---

## 4. Input Contract Rules

For public MCP arguments:

### Required

Use explicit typed fields for:

```text
objects
nested objects
arrays
enums
literal DocType values
quantities
dates
booleans
identifiers
resolved references
```

Example:

```python
class CustomerReference(BaseModel):
    doctype: Literal["Customer"]
    name: str

class ItemReference(BaseModel):
    doctype: Literal["Item"]
    name: str

class QuotationItemInput(BaseModel):
    item: ItemReference
    qty: PositiveNumber
```

### Public-boundary rule

Avoid these at the MCP public boundary unless a field is genuinely dynamic and the reason is documented:

```python
Any
dict[str, Any]
list[dict[str, Any]]
object
untyped kwargs
```

Internal services may continue to use dictionaries where appropriate.

The wrapper converts the typed public contract into the existing internal format.

### Hidden runtime context

Never expose these as model/tool arguments:

```text
frappe_user
frappe_session
librechat_user_id
authorization header
shared bearer secret
role
run_as
site credentials
request context
```

Runtime identity remains request-scoped and server-controlled.

---

## 5. Resolved Reference Standard

Use explicit domain references.

Conceptual examples:

```python
class CustomerReference(BaseModel):
    doctype: Literal["Customer"]
    name: str

class ItemReference(BaseModel):
    doctype: Literal["Item"]
    name: str

class WarehouseReference(BaseModel):
    doctype: Literal["Warehouse"]
    name: str
```

Do not use one unrestricted reference such as:

```python
doctype: str
name: str
```

when the tool requires a specific DocType.

The literal type is part of the contract.

Shared implementation may use reusable generic/base helpers only if the generated MCP schema remains specific and clear.

---

## 6. Output Contract Rules

Input schemas alone are not enough.

Every public tool should also have an explicit output model/contract.

Examples of stable output concepts:

```text
SearchResult
ResolveResolvedResult
ResolveAmbiguousResult
ResolveNotFoundResult
PrepareReadyResult
CreatedResult
ToolError
```

Do not force every tool into one giant universal response object.

Use small shared envelopes where semantics are genuinely shared.

### Stable error envelope

Existing project behavior should be preserved, conceptually:

```json
{
  "status": "error",
  "code": "INVALID_QUOTATION_DETAILS",
  "message": "Human-readable safe message.",
  "reference": "MCP-ERR-...",
  "retryable": false
}
```

Rules:

```text
code      = stable machine-readable code
message   = safe user/model-facing explanation
reference = correlation/reference ID
retryable = whether retrying can reasonably succeed
```

Do not expose stack traces, secrets, internal credentials, auth headers, or database details.

### MCP SDK capability

Before implementing output-schema publication, inspect the currently installed MCP SDK/Pydantic versions.

If the installed SDK supports publishing an output schema/structured result from return annotations/models:

```text
use it
test it through tools/list / Inspector
```

If it does not:

```text
keep a typed internal/public return model
serialize without changing existing payload semantics
document the SDK limitation
test the returned structure
do not invent a non-standard protocol extension
```

---

## 7. Side-Effect Classification

Every tool must be classified for humans and future orchestration:

```text
READ
RESOLVE
PREPARE
CONFIRM_WRITE
```

Typical rule:

```text
search_*   -> READ
resolve_*  -> RESOLVE
prepare_*  -> PREPARE
confirm_*  -> CONFIRM_WRITE
```

This classification is metadata/documentation, not a substitute for permission checks or explicit approval enforcement.

Frappe remains authoritative for user permissions.

---

## 8. Single Source of Truth

Do not manually maintain the same schema in multiple places.

Target:

```text
typed Python tool models/signature
        |
        +----> MCP tools/list schema
        |
        +----> automated contract tests
        |
        +----> generated docs/TOOLS.md
```

README should not contain 100 manually maintained tool schemas.

Use:

```text
README.md
    -> overview + capability groups + link

docs/TOOLS.md
    -> generated/maintained complete catalog

MCP tools/list
    -> authoritative machine-readable public schema
```

---

## 9. Tool Contract Documentation

For each tool, generated/human catalog should show at least:

```text
Tool name
Domain
Operation family
Read/write classification
Purpose
Input model/schema
Output model/schema/statuses
Approval requirement
Important preconditions
```

Example summary row:

| Tool | Domain | Operation | Side effect | Approval |
|---|---|---|---|---|
| `prepare_quotation` | Selling | Prepare | Non-persistent | No final write |
| `confirm_quotation` | Selling | Confirm | ERPNext write | Required |

The complete field schema should come from the actual typed contract, not be hand-copied into README.

---

## 10. Automated Contract Guard

Add an automated contract audit so future tools cannot quietly repeat the same mistake.

The exact implementation must be adapted to the installed MCP SDK, but the test/policy must verify as much as the SDK exposes:

```text
registered public tool has a description
registered public tool has explicit input schema
nested public objects are typed
required fields are visible
literal/enums are visible where applicable
hidden runtime Context is not model-visible
output contract exists in code
outputSchema is visible when SDK supports it
tool side-effect classification exists
documentation catalog is not stale
```

### Legacy migration

Do not turn this task into a risky rewrite of every current tool.

At foundation time:

1. Audit all currently registered tools.
2. Record which already comply.
3. Freeze any genuine legacy exceptions.
4. Fully migrate Quotation first.
5. New tools added after this standard must not create new legacy exceptions.
6. Existing legacy tools are migrated through focused later tasks.

A legacy-exception list must never become the easy path for new tools.

---

## 11. Future Tool Definition of Done

A future MCP tool is **not complete** until all of these are true:

```text
[ ] domain/service responsibility is clear
[ ] operation family is clear
[ ] explicit input contract exists
[ ] explicit output contract exists
[ ] hidden runtime context is not public
[ ] side-effect class is declared
[ ] permission behavior remains Frappe-controlled
[ ] prepare/confirm boundary is respected if writing
[ ] public schema test passes
[ ] success/error contract tests pass
[ ] docs/TOOLS.md is regenerated/checked
[ ] relevant domain/project docs are updated
[ ] no secret/config values are committed
```

---

## 12. Agent / Project Documentation Rule

The project agent instructions should reference this standard.

When any agent adds or changes an MCP tool, it must:

```text
1. read this contract standard
2. inspect the existing domain service
3. create/update typed input model
4. create/update typed output model
5. keep wrapper thin
6. add/update contract tests
7. update generated tool catalog
8. update only relevant domain docs
9. run regressions
10. report exact tools/list schema changes
```

This makes contract maintenance part of the normal project workflow rather than something remembered only after an LLM fails.

---

## 13. Quotation as First Adopter

The first concrete migration is `prepare_quotation`.

Required public input concept:

```json
{
  "customer": {
    "doctype": "Customer",
    "name": "GreenLeaf Foods Pvt Ltd"
  },
  "items": [
    {
      "item": {
        "doctype": "Item",
        "name": "SV-FRAPPE-DEVELOPMENT"
      },
      "qty": 2
    }
  ]
}
```

`valid_till` must preserve the current service/business behavior after source inspection.

The implementation must also type the existing `prepare_quotation` output without changing the service semantics.

Quotation is not allowed to introduce a one-off schema pattern that future tools cannot reuse.

---

## 14. What This Standard Does Not Solve By Itself

These remain dedicated tasks:

```text
Ambiguous candidate selection enforcement
Explicit user approval / confirm-tool safety
Coordinator/sub-agent orchestration
Tool exposure by agent/domain
Sales Invoice / Payment Entry workflows
```

The contract architecture should support those future tasks without prematurely implementing them.

---

## 15. Long-Term Target

```text
100+ ERPNext MCP tools
        |
        v
same contract rules
same automated audit
same generated catalog
same service boundary
same permission model
```

The number of tools may grow.

The README, public schema quality, and agent behavior should not become harder to maintain simply because the catalog grows.
