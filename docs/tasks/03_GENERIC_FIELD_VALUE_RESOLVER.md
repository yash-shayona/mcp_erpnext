# Task 03 — Generic Metadata-Driven Field Value Resolver

## Objective

Add a reusable field-value resolution and validation layer on top of the metadata-driven creation contract completed in Task 02.

Task 02 remains completed and should **not be rerun**. This task extends it.

The resolver must be generic and driven by actual Frappe `DocField` metadata. It must not be hard-coded only for Customer Group, Territory, Item Group, UOM, or any one DocType.

Target flow:

```text
Task 02 Creation Contract
        ↓
DocField metadata
        ↓
Generic Field Value Resolver
        ↓
resolved / needs_selection / invalid_value / not_found
        ↓
prepare_customer / prepare_item
```

---

## Important Rule

Do not create separate resolvers such as:

```text
resolve_customer_group()
resolve_territory()
resolve_item_group()
resolve_uom()
```

when normal Frappe metadata already describes the field behavior.

Instead derive behavior from:

```text
field.fieldtype
field.options
target DocType
runtime Select options
current capability configuration
```

Generic does **not** mean arbitrary ERPNext access. Only fields explicitly exposed by the current MCP capability may be resolved.

---

## Phase 1 — Inspect Frappe Field Types

Before implementation, inspect the **installed Frappe version** and identify its actual supported DocField field types and their behavior.

Do not rely only on memory or upstream docs.

Classify every discovered field type into a behavior family such as:

```text
record/reference resolution
predefined options
scalar text/data
numeric
boolean
date/time
structured/nested
file/specialized
read-only/system-managed
layout/display/no-value
unsupported for current MCP
```

Do not build a giant custom parser for all Frappe field types.

Architecture must support classification of all current field types, while concrete resolver strategies should be implemented only where needed by the currently exposed Customer/Item fields. Unsupported exposed field types must fail explicitly and safely.

---

## Generic Resolver Structure

Prefer a focused shared component such as:

```text
mcp_erpnext/services/common/field_value_resolver.py
```

Reuse the existing common record/candidate resolver from the current source if suitable.

Expected responsibility split:

```text
creation_contract.py
    → determines missing required fields

field_value_resolver.py
    → dispatches behavior by actual fieldtype
    → normalizes / validates / resolves supplied values

existing common resolver
    → permission-aware record candidate lookup
```

Do not duplicate fuzzy/candidate-resolution algorithms.

---

## Mandatory vs Optional Rule

### Mandatory + missing

Task 02 creation contract returns:

```text
needs_input
```

### Mandatory + supplied

Validate/resolve according to fieldtype.

### Optional + not supplied

Skip it.

### Optional + supplied

Still validate/resolve it.

Optional does **not** mean unchecked.

---

## Link Field Behavior

For:

```text
fieldtype = Link
```

derive the target DocType from runtime metadata.

Example:

```text
Customer.customer_group
fieldtype = Link
options = Customer Group
```

Then resolve the supplied value permission-aware against `Customer Group`.

Expected outcomes:

```text
resolved
needs_selection
not_found
permission_denied / inaccessible
```

Rules:

```text
exact accessible match
    → resolved

single deterministic normalized match
    → resolved

multiple plausible matches
    → needs_selection

no match
    → not_found
```

Never silently choose between multiple candidates.

Do not leak records the configured Frappe user cannot access.

---

## Dynamic Link Behavior

If a current/exposed field is `Dynamic Link`, derive its target DocType from the controlling metadata field.

Do not guess the target.

If the controlling value is missing/unresolved, return a controlled missing/unresolved result.

Only implement this path if it can be derived safely from current Frappe metadata.

---

## Select Field Behavior

For:

```text
fieldtype = Select
```

use the current runtime metadata options as the authoritative values.

Do not keep a duplicate static option list when metadata already provides it.

Expected behavior:

```text
exact option
    → resolved

case-normalized exact option
    → canonical option

single deterministic candidate
    → canonical option

multiple plausible options
    → needs_selection

invalid option
    → invalid_value
```

Example:

```text
input: company
metadata options:
    Company
    Individual

result:
    Company
```

---

## Check / Boolean Behavior

Normalize supported canonical values safely.

Examples:

```text
true  → 1
false → 0
1     → 1
0     → 0
```

If `yes/no` support is added, define and test it explicitly.

Do not accept arbitrary ambiguous text.

---

## Scalar / Input Fields

Normal input fields generally do not require candidate resolution.

Examples may include:

```text
Data
Text
Small Text
Long Text
Int
Float
Currency
Percent
JSON
Phone
Color
Barcode
Date
Datetime
Time
```

Verify actual field types from installed Frappe.

Reuse Frappe casting/validation utilities where practical.

MCP should:

```text
normalize
type-check
validate canonical value
```

rather than reimplementing ERPNext business validation.

Natural-language interpretation such as:

```text
"next Friday"
"ten pieces"
```

belongs to a future Agent/LLM layer. MCP should validate canonical values deterministically.

---

## Read-Only / Layout / No-Value Fields

If capability configuration exposes a field that is not valid user creation input, fail safely.

Examples may include layout/display/read-only field types discovered from installed Frappe.

Do not ask users to provide values for UI/layout-only fields.

Return a controlled configuration/unsupported-field result.

---

## Structured / Table Fields

Classify table/nested field types correctly.

Do not build a generic recursive child-document engine in this task unless current Customer/Item exposed contracts actually require it.

Preserve existing focused Customer Contact/Address handling unless a minimal integration change is required.

---

## Generic Field Result Contract

Return structured internal information.

Resolved example:

```json
{
  "status": "resolved",
  "path": "customer.customer_group",
  "fieldname": "customer_group",
  "fieldtype": "Link",
  "input": "commercial",
  "value": "Commercial",
  "source": "user_input",
  "target_doctype": "Customer Group"
}
```

Ambiguous example:

```json
{
  "status": "needs_selection",
  "path": "item.stock_uom",
  "fieldname": "stock_uom",
  "fieldtype": "Link",
  "query": "pcs",
  "target_doctype": "UOM",
  "candidates": [
    {"value": "Piece", "label": "Piece"},
    {"value": "Pieces", "label": "Pieces"}
  ]
}
```

Invalid Select example:

```json
{
  "status": "invalid_value",
  "fieldname": "customer_type",
  "fieldtype": "Select",
  "input": "Other",
  "allowed_values": ["Company", "Individual"]
}
```

Adapt exact schema to current project conventions, but keep it structured for future Agent use.

---

## Aggregate Prepare Behavior

`prepare_customer` and `prepare_item` must be able to return unresolved field information without conversational state.

Example:

```text
customer_name = valid
customer_type = resolved
customer_group = ambiguous
```

Expected:

```text
status = needs_selection
field = customer_group
candidates = [...]
```

The MCP server must not store the fact that the user is "in a conversation". That belongs to the future LangGraph/Agent layer.

---

## Configuration Integration

Reuse Task 02 configuration:

```text
mcp_erpnext/config/masters/customer.py
mcp_erpnext/config/masters/item.py
```

Configuration determines:

```text
which fields are exposed
which values are MCP policy
candidate/search limits
safe capability boundaries
```

Metadata determines:

```text
fieldtype
Select options
Link target
labels
required metadata
```

Do not add `allow_any_field` or arbitrary DocType resolution.

---

## Current Customer Verification

Inspect current exposed Customer fields and test applicable behavior, especially fields such as:

```text
customer_type
customer_group
territory
```

only if they remain exposed/current.

Verify:

```text
optional missing → skip
optional supplied valid → resolve
optional supplied ambiguous → needs_selection
optional supplied invalid → fail safely
```

---

## Current Item Verification

Inspect current Item metadata/config and test applicable fields such as:

```text
item_code
item_group
stock_uom
is_sales_item
```

Expected:

```text
item_group → generic Link resolution
stock_uom → generic Link resolution
is_sales_item → MCP policy + Check normalization
item_code → scalar validation
```

Do not assume field types without metadata inspection.

---

## Permissions

All record resolution must use the configured Frappe user and normal permissions.

Do not use:

```text
ignore_permissions=True
```

for lookup/resolution.

Inaccessible candidates must not be returned.

---

## Files Allowed to Change

Inspect the current Task 02 implementation first.

Expected areas:

```text
mcp_erpnext/services/common/
mcp_erpnext/services/masters/customer.py
mcp_erpnext/services/masters/item.py

mcp_erpnext/config/masters/customer.py
mcp_erpnext/config/masters/item.py

mcp_erpnext/tests/
```

A focused new file is allowed:

```text
mcp_erpnext/services/common/field_value_resolver.py
```

If equivalent infrastructure already exists, extend it instead of duplicating it.

Documentation may be updated only where needed:

```text
README.md
docs/ERPNext_MCP_ARCHITECTURE.md
```

---

## Do Not Change

Do not redesign:

```text
Quotation service
Sales Order service
approval-token architecture
MCP transport
chatbot
OAuth
LangGraph
frontend
```

Do not add:

```text
generic arbitrary DocType CRUD
search_any_doctype
resolve_any_doctype
```

Do not create separate MCP tools for every Link field.

---

## Permission

You may:

```text
inspect installed Frappe source/metadata
implement scoped resolver code
update Customer/Item integration
add/update unit tests
run non-network unit tests
run safe syntax/static checks
```

Do not create or modify ERPNext records.

Do not run builds, migrations, restarts, installs, or external calls.

---

## Required Tests

### Field-Type Classification

- actual installed field types inspected
- current exposed field types mapped to a defined strategy/category
- unsupported exposed type fails safely

### Select

- exact option
- normalized exact option
- invalid option
- ambiguous candidate behavior
- options sourced from metadata

### Link

- exact accessible match
- unique normalized candidate
- multiple candidates → `needs_selection`
- no candidate → `not_found`
- inaccessible candidate not leaked
- target DocType derived from metadata

### Optional Link/Select

- absent optional field skipped
- supplied optional field still validated

### Check

- valid boolean normalization
- invalid value rejected
- `is_sales_item` remains traceable as MCP policy

### Scalar

- valid typed values accepted
- invalid typed values rejected safely
- Frappe utilities reused where appropriate

### Customer Regression

- Task 02 missing-field behavior still passes
- duplicate detection still passes
- prepare remains write-free
- confirm behavior unchanged

### Item Regression

- Task 02 missing-field behavior still passes
- Item Group/UOM use generic field resolution
- duplicate detection still passes
- prepare remains write-free
- confirm behavior unchanged

---

## Acceptance Criteria

- [ ] Installed Frappe field-type catalog is inspected.
- [ ] Every discovered field type is classified.
- [ ] Resolver architecture is generic and metadata-driven.
- [ ] Link targets come from metadata.
- [ ] Select options come from metadata.
- [ ] Optional supplied fields are validated.
- [ ] Multiple candidates are never silently guessed.
- [ ] Permission-inaccessible candidates are not leaked.
- [ ] Scalar fields use validation/normalization instead of candidate lookup.
- [ ] Unsupported exposed field types fail explicitly.
- [ ] No Customer-Group/UOM-specific resolver duplication is introduced.
- [ ] Existing Customer/Item prepare-confirm safety remains unchanged.
- [ ] No arbitrary DocType MCP access is introduced.
- [ ] No conversational state is added to MCP.
- [ ] Regression tests pass.

---

## Expected Result

```text
Customer / Item input
        ↓
Task 02 creation contract
        ↓
runtime DocField metadata
        ↓
Task 03 field-value resolver
        ↓
canonical ERPNext value
        OR
needs_selection
        OR
invalid_value
        OR
not_found
        ↓
prepare preview
```

---

## Known Boundaries

This task does not:

- add LangGraph,
- add chatbot state,
- automatically create missing linked masters,
- add arbitrary ERPNext CRUD,
- redesign generic child-table creation,
- integrate generic resolution into Quotation/Sales Order fields,
- perform live ERPNext writes.

---

## Exact Next Task

**Task 04 — ERPNext MCP Quotation Capability Verification With MCP Inspector**

Task 04 will verify the completed Task 02 + Task 03 foundation directly against the local MCP server.

Do not begin Task 04 in this task.
