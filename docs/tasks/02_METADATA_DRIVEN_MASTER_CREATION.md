# Task 02 — Metadata-Driven Master Creation Contract & Configuration Structure

## Objective

Make the existing ERPNext MCP Server use the **actual installed ERPNext/Frappe metadata and defaults** when determining the minimum information required to create reusable master records.

This task is limited to the current master capabilities:

```text
Customer
Item
```

The goal is not to add business-specific rules.

The first version must follow this principle:

```text
User supplies only what ERPNext actually needs.

Provided value
    ↓
ERPNext / Frappe default if available
    ↓
MCP policy/default only when intentionally defined
    ↓
Ask the user only for still-missing required values
```

At the same time, move developer-changeable MCP behavior into a clear configuration structure so future changes are easy to trace and do not require searching through service implementation code.

---

# Why This Task Exists

The current Customer and Item services contain useful constants and validation logic directly inside:

```text
mcp_erpnext/services/masters/customer.py
mcp_erpnext/services/masters/item.py
```

Examples include:

```text
filters
search fields
display fields
allowed values
required creation fields
MCP-forced values
```

Some of these values are stable implementation constraints.

Others are configuration/policy and may change later.

More importantly, the MCP server currently contains manually defined creation requirements such as:

```text
Customer:
    customer_name
    customer_type defaulted in service code

Item:
    item_code
    item_group
    stock_uom
```

The MCP server must not maintain a duplicated hard-coded copy of ERPNext mandatory metadata as its own source of truth.

The actual installed Frappe/ERPNext site must remain authoritative for:

```text
required fields
field labels
field types
Select options
DocField defaults
custom fields
Property Setter changes
site-specific metadata
```

---

# Core Architectural Rule

Use three separate sources of behavior.

```text
ERPNext Runtime Metadata
        │
        │ what ERPNext currently requires/defaults
        ↓
Creation Contract Resolver
        │
        │ determine what is still missing
        ↓
Master Service
        │
        │ validate + prepare + confirm
        ↓
ERPNext
```

MCP configuration has a different responsibility:

```text
MCP Configuration
        │
        ├── fields exposed to the capability
        ├── search behavior
        ├── display behavior
        ├── field aliases / mappings
        ├── intentionally forced policy values
        └── controlled capability defaults, if any
```

Do **not** make MCP configuration the authority for ERPNext `reqd` metadata.

---

# Scope

Implement metadata-driven creation requirements for:

```text
Customer
Item
```

Keep existing MCP tool names unchanged:

```text
prepare_customer
confirm_customer

prepare_item
confirm_item
```

Do not modify Quotation or Sales Order orchestration in this task.

Do not add LangGraph or chatbot state management.

---

# Phase 1 — Inspect Actual ERPNext Metadata First

Before changing implementation, inspect the actual installed site metadata for:

```text
Customer
Item
```

Use the configured development/test Frappe site.

Prefer the Frappe runtime APIs used by the installed version, such as:

```python
frappe.get_meta("Customer")
frappe.get_meta("Item")
```

Also inspect how the installed Frappe version applies defaults to a new document.

Reuse existing Frappe utilities before implementing custom default or mandatory-field logic.

The inspection must be read-only.

Do not create or modify ERPNext records.

---

# Required Metadata Classification

For both `Customer` and `Item`, determine and record during implementation:

```text
1. Required by current ERPNext metadata
2. Already populated by ERPNext/Frappe defaults
3. Required but still missing after defaults
4. Optional
5. Conditional / dependent requirement
6. MCP-forced policy value
7. MCP-exposed but optional value
```

The implementation must not assume that upstream ERPNext GitHub metadata is identical to the installed site.

The installed site may contain:

```text
Custom Fields
Property Setters
different defaults
installed-app metadata changes
version-specific differences
```

Therefore runtime metadata is authoritative.

---

# Minimum-Input Rule

For master creation, use this precedence:

```text
1. Explicit user-provided value
        ↓
2. Intentionally defined MCP policy value
        ↓
3. ERPNext/Frappe runtime default
        ↓
4. If field is actually mandatory and still empty:
       return needs_input
        ↓
5. Optional fields remain absent
```

Do not ask the user for optional fields merely because they may be useful.

Do not ask for a required field when ERPNext already provides a valid default.

---

# Example — Customer

If the installed site reports:

```text
customer_name = mandatory
customer_type = mandatory + default Company
```

then this request should be sufficient:

```text
Create customer ABC Industries
```

The MCP server should not unnecessarily ask:

```text
Customer Type?
```

when the installed ERPNext/Frappe default already supplies it.

If the actual site has another mandatory Custom Field with no default, the server should return that field as missing.

---

# Example — Item

If the installed site reports that these remain mandatory without usable defaults:

```text
item_code
item_group
stock_uom
```

then the MCP server should return only those still missing.

If the installed site provides a valid default for one of them, do not ask for it.

---

# Configuration Structure

Use the existing:

```text
mcp_erpnext/config/
```

package.

Create a small domain-based structure:

```text
mcp_erpnext/config/
├── __init__.py
└── masters/
    ├── __init__.py
    ├── customer.py
    └── item.py
```

Do not create a large generic configuration framework.

Keep configuration simple Python constants/data structures that developers can inspect quickly.

---

# Customer Configuration Responsibilities

Move changeable Customer capability behavior into:

```text
mcp_erpnext/config/masters/customer.py
```

Examples of appropriate configuration:

```text
search filters
search fields
display fields
fields accepted by the Customer creation capability
nested input mappings
MCP-specific forced values, if any
capability-specific field aliases
safe optional fields exposed by the MCP contract
```

Do not duplicate the runtime mandatory-field list here.

Do not hard-code:

```text
REQUIRED_FIELDS = [...]
```

as the authoritative ERPNext requirement list.

---

# Item Configuration Responsibilities

Move changeable Item capability behavior into:

```text
mcp_erpnext/config/masters/item.py
```

Examples:

```text
search filters
search fields
display fields
fields accepted by the Item creation capability
reference-field definitions
MCP-specific forced values
```

The current Selling-oriented Item capability intentionally forces:

```text
is_sales_item = 1
```

If this remains required by the current architecture, represent it clearly as an:

```text
MCP policy value
```

not an ERPNext mandatory-field rule.

A developer reading the configuration should immediately be able to answer:

```text
Why is is_sales_item always enabled?
```

without searching through the Item service implementation.

---

# Shared Metadata / Creation Contract Helper

Create one focused shared helper under:

```text
mcp_erpnext/services/common/
```

Suggested name:

```text
creation_contract.py
```

or another clear responsibility-based name.

Do not create a broad utility dumping ground.

Its responsibility should be limited to resolving a creation contract from:

```text
doctype
current input
allowed/exposed capability fields
MCP policy values
ERPNext runtime metadata/defaults
```

It should not perform database writes.

---

# Required Contract Information

The helper should be able to provide enough structured information for the service to determine:

```text
resolved values
still-missing required fields
where resolved values came from
```

For missing fields, return structured information suitable for a future free-form Agent.

Example shape:

```json
{
  "status": "needs_input",
  "missing": [
    "customer.customer_name"
  ],
  "missing_fields": [
    {
      "doctype": "Customer",
      "fieldname": "customer_name",
      "path": "customer.customer_name",
      "label": "Customer Name",
      "fieldtype": "Data",
      "reason": "mandatory",
      "source": "erpnext_metadata"
    }
  ]
}
```

The exact internal implementation may differ, but preserve the existing simple:

```text
missing
```

list for backward compatibility.

Add richer metadata rather than replacing the existing contract.

---

# Traceability Requirement

For values filled automatically, make their source traceable internally.

The implementation should be able to distinguish at least:

```text
user_input
mcp_policy
erpnext_default
```

Example conceptual result:

```text
customer_type
value = Company
source = erpnext_default
```

and:

```text
is_sales_item
value = 1
source = mcp_policy
```

Do not expose unnecessary internal diagnostics to normal end users.

The goal is developer/debugging traceability and deterministic Agent behavior.

---

# ERPNext Defaults

Do not manually copy ERPNext defaults into configuration when the installed Frappe runtime can provide them reliably.

Prefer:

```text
actual new-document/runtime default
```

over:

```text
MCP hard-coded imitation of ERPNext default
```

For example, if `customer_type = Company` is supplied by the actual installed ERPNext metadata/default mechanism, the Customer service should not separately pretend that it owns that default.

---

# Select / Options Validation

When an exposed field is a Select field, prefer the current ERPNext metadata options where appropriate.

Do not maintain a duplicate static option set if runtime metadata provides the authoritative choices.

For example, review the existing static Customer Type handling.

If the current installed `Customer.customer_type` field exposes its options through metadata, use that source rather than maintaining a separate divergent option list.

Preserve safe validation behavior.

---

# Link / Reference Fields

This task should preserve current explicit reference validation for fields such as:

```text
Item.item_group
Item.stock_uom
```

Do not add fuzzy resolution for these link fields yet unless strictly required for the metadata contract.

If a mandatory Link field is missing, report it as missing.

If the user supplies an invalid or inaccessible link value, preserve a controlled `needs_input` or equivalent safe response.

Dedicated natural-language reference resolution can be a later task.

---

# Conditional Mandatory Fields

Inspect whether the relevant metadata contains:

```text
mandatory_depends_on
depends_on
```

or other conditional requirements.

Reuse an existing Frappe utility if the installed version provides a safe server-side way to evaluate mandatory conditions.

Do not implement a custom client-expression interpreter merely for this task.

If a conditional requirement cannot be safely evaluated generically, keep ERPNext's own validation authoritative and document that boundary.

Do not guess.

---

# Customer Service Integration

Refactor:

```text
mcp_erpnext/services/masters/customer.py
```

so that:

1. search/display configuration comes from Customer config where appropriate,
2. creation input is normalized,
3. MCP policy values are applied,
4. ERPNext runtime defaults are applied,
5. actual metadata is inspected,
6. only still-missing required exposed fields return `needs_input`,
7. existing duplicate detection remains,
8. existing permission checks remain,
9. preparation remains write-free,
10. confirmation remains the only persistent write.

Preserve current optional Contact/Address handling unless a metadata-driven change is required.

Do not expand Customer creation into a large CRM onboarding workflow.

---

# Item Service Integration

Refactor:

```text
mcp_erpnext/services/masters/item.py
```

so that:

1. search/display configuration comes from Item config where appropriate,
2. creation input is normalized,
3. `is_sales_item = 1` remains an explicit MCP policy if still required,
4. ERPNext runtime defaults are applied,
5. actual metadata is inspected,
6. only still-missing mandatory exposed fields return `needs_input`,
7. Item Group/UOM validation remains permission-aware,
8. duplicate detection remains,
9. preparation remains write-free,
10. confirmation remains the only persistent write.

Do not add pricing, valuation, taxation, warehouse, accounting, or stock-opening behavior to Item creation.

---

# Backward Compatibility

Do not rename current MCP tools.

Do not break these existing response states unless required by a confirmed bug:

```text
ready
needs_input
duplicate_suspected
permission_denied
created
error
```

Keep the existing:

```text
missing: [...]
```

field when returning missing inputs.

Additional richer fields may be added for future Agent consumption.

Existing Quotation and Sales Order consumers must continue to receive the same reusable Customer/Item references.

---

# Files Allowed to Change

Expected files:

```text
mcp_erpnext/config/__init__.py

mcp_erpnext/config/masters/__init__.py
mcp_erpnext/config/masters/customer.py
mcp_erpnext/config/masters/item.py

mcp_erpnext/services/common/__init__.py
mcp_erpnext/services/common/creation_contract.py

mcp_erpnext/services/masters/customer.py
mcp_erpnext/services/masters/item.py

mcp_erpnext/tests/test_customer_service.py
mcp_erpnext/tests/test_item_service.py
```

If needed for focused shared-helper tests:

```text
mcp_erpnext/tests/test_creation_contract.py
```

Documentation may be updated only where this new behavior changes the current documented architecture:

```text
README.md
docs/ERPNext_MCP_ARCHITECTURE.md
```

Do not modify Selling services unless a test proves a compatibility issue caused directly by this refactor.

---

# Files / Areas Not to Change

Do not change:

```text
mcp_erpnext/services/selling/quotation.py
mcp_erpnext/services/selling/sales_order.py

mcp_erpnext/tools/selling/**
mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/mcp_server.py

chatbot project
LangGraph
OAuth
frontend
```

Do not add new MCP tools in this task.

---

# Permission

You may:

```text
inspect source
inspect installed Frappe/ERPNext metadata read-only
implement the scoped Python/config changes
add/update unit tests
run non-network unit tests
run safe syntax/static checks
```

You may use a read-only Frappe context to inspect:

```text
frappe.get_meta(...)
new-document/default behavior
```

Do not write ERPNext records during metadata inspection.

---

# Do Not Run / Do Not Perform

Do not run:

```text
bench migrate
bench build
bench restart
bench update
bench install-app
```

Do not:

```text
create Customer records
create Item records
create Quotations
create Sales Orders
modify ERPNext data
install packages
call external APIs
change site configuration
change Custom Fields
change Property Setters
```

---

# Required Tests

Add/update unit tests covering at least the following.

## Customer

### 1. User-supplied mandatory value

Given:

```text
customer_name supplied
```

Expected:

```text
customer_name retained
source = user_input internally
```

### 2. ERPNext default satisfies mandatory field

Given a fake/current metadata field that is mandatory and receives an ERPNext default:

Expected:

```text
no unnecessary needs_input
```

### 3. Mandatory field without value/default

Expected:

```text
status = needs_input
missing contains the compatible field path
missing_fields contains structured metadata
```

### 4. Site/custom mandatory field

Simulate metadata containing an additional mandatory exposed field with no default.

Expected:

```text
the field is detected without hard-coding it into the Customer service
```

### 5. Existing duplicate detection

Must continue to pass.

### 6. Existing permission behavior

Must continue to pass.

### 7. Prepare performs no write

Must continue to pass.

### 8. Confirm remains explicit and idempotent

Must continue to pass.

---

## Item

### 1. Metadata-driven required fields

Simulate required Item fields through metadata.

Expected:

```text
only unresolved mandatory values are requested
```

### 2. ERPNext default removes unnecessary prompt

If a mandatory field receives a valid runtime default:

Expected:

```text
field is not returned as missing
```

### 3. MCP policy remains distinct

Expected:

```text
is_sales_item = 1
```

and its origin is treated as:

```text
mcp_policy
```

not:

```text
erpnext_metadata mandatory
```

### 4. Item Group validation

Existing valid/invalid Item Group behavior must remain.

### 5. UOM validation

Existing valid/invalid UOM behavior must remain.

### 6. Duplicate detection

Must continue to pass.

### 7. Prepare performs no write

Must continue to pass.

### 8. Confirm remains explicit and idempotent

Must continue to pass.

---

# Existing Regression Tests

Run the existing non-network test suite.

Use the project's existing test command if documented and valid.

At minimum verify:

```text
test_customer_service
test_item_service
test_quotation_service
test_tool_registration
test_approvals
```

Do not report runtime ERPNext behavior as verified merely because mocked unit tests pass.

---

# Acceptance Criteria

- [ ] Actual installed ERPNext/Frappe metadata is inspected before implementation.
- [ ] Customer and Item mandatory fields are no longer maintained as duplicated MCP truth where runtime metadata can determine them.
- [ ] ERPNext/Frappe defaults are used before asking the user for a mandatory field.
- [ ] User is asked only for mandatory values still unresolved after defaults/policy.
- [ ] Custom/site metadata can affect the missing-field result without editing the service's hard-coded mandatory list.
- [ ] Existing MCP tool names remain unchanged.
- [ ] Existing `missing` response remains backward compatible.
- [ ] Rich missing-field metadata is available for future Agent/free-form conversation.
- [ ] Developer-changeable Customer behavior is organized in `config/masters/customer.py`.
- [ ] Developer-changeable Item behavior is organized in `config/masters/item.py`.
- [ ] ERPNext metadata remains the source of truth for `reqd`/field metadata.
- [ ] MCP policy values are clearly distinguishable from ERPNext defaults.
- [ ] Customer duplicate/permission/approval safety remains intact.
- [ ] Item duplicate/reference/permission/approval safety remains intact.
- [ ] Prepare operations perform no persistent write.
- [ ] Confirm operations remain the only persistent master writes.
- [ ] Quotation/Sales Order service behavior is not redesigned in this task.
- [ ] Non-network regression tests pass.

---

# Developer Traceability Goal

After this task, a developer should be able to answer questions such as:

```text
Why is Customer Type "Company"?
```

by tracing it to:

```text
ERPNext runtime default
```

rather than finding an unexplained hard-coded value in service logic.

Likewise:

```text
Why is Item is_sales_item always enabled?
```

should trace clearly to:

```text
MCP Selling capability policy
```

And:

```text
Why is the Agent asking for this field?
```

should trace to:

```text
actual ERPNext metadata says it is mandatory
and no value/default currently satisfies it
```

---

# Expected Result

The master creation path should conceptually become:

```text
Free-form Agent input later
        ↓
prepare_customer / prepare_item
        ↓
normalize supplied values
        ↓
apply explicit MCP policy
        ↓
load ERPNext runtime metadata/defaults
        ↓
required values still missing?
        │
        ├── yes
        │     ↓
        │  needs_input
        │  + structured field metadata
        │
        └── no
              ↓
          duplicate/reference checks
              ↓
          permission checks
              ↓
          preview
              ↓
          approval token
```

The MCP server remains responsible for ERPNext capability correctness.

A future LangGraph/Agent layer will only manage conversation and state around these deterministic MCP results.

---

# Known Boundaries

This task does not:

```text
add LangGraph
add chatbot state management
add generic arbitrary DocType creation
add fuzzy Item Group resolution
add fuzzy UOM resolution
add Territory resolution
add Customer Group resolution
add pricing logic
add new Selling workflows
perform live ERPNext writes
```

Reference/master lookup ergonomics can be improved later without changing the metadata contract foundation.

---

# Exact Next Task

After this task is implemented and unit-tested:

## Task 03 — ERPNext MCP Quotation Capability Verification With MCP Inspector

Task 03 will use the actual local MCP server directly, without the custom chatbot, to verify:

```text
MCP startup
tool registration
Customer resolution
Item resolution
metadata-driven missing-input behavior
Customer preparation
Item preparation
Quotation preparation
preview correctness
explicit confirmation boundary
Draft Quotation creation on approved test data
idempotent confirmation
permission behavior
```

The MCP Inspector verification must separate:

```text
MCP/server correctness
```

from:

```text
future Agent/LangGraph behavior
```

Do not begin Task 03 as part of this task.
