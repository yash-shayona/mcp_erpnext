# Task 01 — Synchronize ERPNext MCP Documentation With Current Source

## Objective

Update the existing `mcp_erpnext` documentation so that it accurately represents the **current ERPNext MCP Server implementation**.

The project must be documented as **one reusable ERPNext MCP server** containing domain capabilities such as:

```text
ERPNext MCP Server
├── Masters
│   ├── Customer
│   └── Item
│
└── Selling
    ├── Quotation
    └── Sales Order
```

Do not describe Quotation, Sales Order, Customer, or Item as separate MCP servers.

This task is **documentation-only**.

---

## Why This Task Exists

The source has evolved beyond the original Sales Order V1 implementation, while some documentation still describes the old limited architecture.

The current source contains capabilities for:

- Customer search and resolution
- Customer prepare/confirm creation
- Item search and resolution
- Item prepare/confirm creation
- Sales Order prepare/confirm creation
- Quotation prepare/confirm creation
- permission-aware ERPNext access
- two-phase persistent-write approval
- action/site/user-bound approval state

Documentation must match current source before further MCP development continues.

---

# Scope

Inspect the current source first and then synchronize existing documentation.

Do not infer behavior only from old documentation.

The Python source and current tests are the authority for this task.

---

# Source Files to Inspect First

At minimum inspect:

```text
mcp_erpnext/mcp_server.py

mcp_erpnext/tools/__init__.py

mcp_erpnext/tools/masters/customer.py
mcp_erpnext/tools/masters/item.py

mcp_erpnext/tools/selling/sales_order.py
mcp_erpnext/tools/selling/quotation.py

mcp_erpnext/services/masters/customer.py
mcp_erpnext/services/masters/item.py

mcp_erpnext/services/selling/sales_order.py
mcp_erpnext/services/selling/quotation.py

mcp_erpnext/services/common/

mcp_erpnext/approvals.py
mcp_erpnext/runtime.py

mcp_erpnext/tests/test_tool_registration.py
```

Inspect any directly related files if required to understand the current behavior.

---

# Files Allowed to Change

Only documentation files:

```text
README.md

docs/ERPNext_MCP_ARCHITECTURE.md
docs/CODEX_MCP_SETUP.md
docs/MCP_SALES_ORDER_V1_FROZEN.md
```

Do not modify Python source.

Do not create additional architecture documents unless there is a strong reason.

Prefer updating the existing primary architecture document instead of duplicating information.

---

# Required Documentation Structure

## 1. README.md

Change the project description from a Sales-Order-V1-focused project to a general:

```text
ERPNext MCP Server
```

Explain the high-level architecture:

```text
MCP Client / Agent
        ↓
MCP Transport
        ↓
Domain MCP Tools
        ↓
ERPNext Services
        ↓
Frappe Runtime + Permissions
        ↓
ERPNext
```

Explain that this MCP server is intended to expose **controlled ERPNext capabilities**, not arbitrary ERPNext access.

Document the domain organization:

```text
masters/
    Customer
    Item

selling/
    Quotation
    Sales Order
```

---

# 2. Current MCP Tool Catalog

Verify the exact registered tools from current source.

The expected current catalog is:

```text
search_customers
resolve_customer
prepare_customer
confirm_customer

search_items
resolve_item
prepare_item
confirm_item

prepare_sales_order
confirm_sales_order

prepare_quotation
confirm_quotation
```

Do not blindly copy this list.

Confirm it against:

```text
mcp_erpnext/tools/__init__.py
mcp_erpnext/tests/test_tool_registration.py
```

If current source differs, document the source-verified list.

---

# 3. Explain Tool Categories

Documentation should make the distinction clear.

## Search / Resolution

Examples:

```text
search_customers
resolve_customer

search_items
resolve_item
```

Purpose:

- locate ERPNext records
- respect Frappe permissions
- handle exact match / candidate resolution
- return structured results
- perform no persistent write

## Prepare

Examples:

```text
prepare_customer
prepare_item
prepare_sales_order
prepare_quotation
```

Purpose:

```text
validate input
    ↓
apply ERPNext behavior/defaults where implemented
    ↓
prepare structured preview
    ↓
create approval state
```

Prepare must not perform the final persistent write.

## Confirm

Examples:

```text
confirm_customer
confirm_item
confirm_sales_order
confirm_quotation
```

Purpose:

```text
trusted prepared state
    ↓
explicit approval
    ↓
permission-aware ERPNext write
```

Persistent writes must remain behind the prepare/confirm boundary.

---

# 4. Document the Shared Write Safety Boundary

Explain the shared pattern:

```text
resolve / validate
        ↓
prepare
        ↓
preview
        ↓
explicit approval
        ↓
confirm
        ↓
ERPNext write
```

Clearly document that persistent writes should not be directly exposed as unrestricted generic creation operations.

Where confirmed by source, document that approval state is bound to relevant context such as:

```text
action
site
user
prepared payload
```

Do not document details that current source does not support.

---

# 5. Update ERPNext_MCP_ARCHITECTURE.md

Make:

```text
docs/ERPNext_MCP_ARCHITECTURE.md
```

the primary current architecture reference.

It should explain:

```text
mcp_server.py
    MCP server entrypoint

tools/
    MCP-facing contracts and wrappers

services/
    ERPNext capability implementation

services/common/
    reusable resolution/permission logic

services/masters/
    reusable ERPNext master capabilities

services/selling/
    Selling transaction capabilities

approvals.py
    controlled persistent-write approval boundary

runtime.py
    Frappe site/user runtime context
```

Document the architecture as:

```text
ERPNext MCP Server

├── Master Capabilities
│   ├── Customer
│   └── Item
│
└── Selling Capabilities
    ├── Quotation
    └── Sales Order
```

---

# 6. Important Architectural Clarification

Do not describe:

```text
Customer MCP Server
Item MCP Server
Quotation MCP Server
Sales Order MCP Server
```

as separate servers.

Current architecture is:

```text
ONE ERPNext MCP Server
        ↓
multiple controlled ERPNext domain capabilities
```

Quotation and Sales Order are currently capabilities within the Selling domain.

Customer and Item are reusable master capabilities.

---

# 7. Update Persistent Write Documentation

Document all source-confirmed persistent creation capabilities.

Expected current actions include:

```text
Customer creation
Item creation
Draft Sales Order creation
Draft Quotation creation
```

Each should be described using its corresponding prepare/confirm flow.

Do not imply that Customer or Item creation belongs specifically to Quotation or Sales Order.

They are reusable master capabilities.

Example:

```text
Quotation flow
    ↓
needs Customer
    ↓
Customer master capability can be used

Sales Order flow
    ↓
needs same Customer
    ↓
same Customer master capability can be reused
```

---

# 8. Update CODEX_MCP_SETUP.md

Keep the current local STDIO setup if it matches source.

Use a general MCP server registration name.

Prefer:

```text
erpnext
```

instead of an old capability-specific name such as:

```text
erpnext_sales
```

because this server is not Sales-Order-specific.

Do not change the actual runtime command unless current source/configuration requires it.

---

# 9. Preserve Historical Sales Order V1 Document

Do not rewrite:

```text
docs/MCP_SALES_ORDER_V1_FROZEN.md
```

as if its original scope included all current capabilities.

It is a historical/frozen baseline.

Add a concise notice near the beginning explaining:

```text
This document describes the original Sales Order V1 baseline.

The current ERPNext MCP Server has since expanded with additional reusable
master and Selling capabilities.

Refer to docs/ERPNext_MCP_ARCHITECTURE.md for the current architecture and
tool catalog.
```

Historical details should remain historical.

---

# 10. Runtime / Security Boundaries to Document

Where confirmed by current source, preserve/document:

- STDIO MCP transport
- `MCP_BACKEND=direct`
- configured Frappe site
- configured Frappe user
- Frappe ORM usage
- normal Frappe permission enforcement
- no arbitrary SQL MCP tool
- no unrestricted arbitrary DocType CRUD MCP tool
- process-local approval state if that remains current
- explicit prepare/confirm boundary

Do not expose or inspect secrets.

---

# Do Not Change

Do not modify:

```text
mcp_erpnext/**/*.py

tests/**
pyproject.toml
.env
.env.example
```

unless a documentation reference is factually impossible to correct without first reporting a source inconsistency.

If a source inconsistency is found, report it rather than changing runtime code in this task.

---

# Do Not Run

Do not run:

```text
bench migrate
bench build
bench restart
bench update
bench install-app
```

Do not:

- create Customer records
- create Item records
- create Quotations
- create Sales Orders
- call external APIs
- change ERPNext data
- install packages

Static inspection and safe non-runtime documentation verification only.

---

# Acceptance Criteria

- [ ] Project is documented as one general ERPNext MCP Server.
- [ ] Documentation no longer presents the project primarily as a Sales Order V1 server.
- [ ] Current source-verified MCP tool catalog is documented.
- [ ] Customer reusable master capability is documented.
- [ ] Item reusable master capability is documented.
- [ ] Quotation is documented as a Selling capability.
- [ ] Sales Order is documented as a Selling capability.
- [ ] Customer/Item are not incorrectly nested under Quotation or Sales Order.
- [ ] Prepare/confirm persistent-write boundary is documented consistently.
- [ ] Current permission/runtime architecture is documented accurately.
- [ ] `CODEX_MCP_SETUP.md` uses a general MCP server identity such as `erpnext`.
- [ ] Historical Sales Order V1 document remains clearly historical/frozen.
- [ ] No Python/runtime behavior is changed.
- [ ] No unsupported behavior is documented as verified.

---

# Verification

After editing, compare the documented MCP tool catalog against:

```text
mcp_erpnext/tools/__init__.py
mcp_erpnext/tests/test_tool_registration.py
```

Search documentation for stale wording such as:

```text
V1 Sales Order workflow

current public MCP surface is exactly four tools

only current write action

Customer or Item creation is not supported

erpnext_sales
```

Each occurrence must either:

1. be corrected for the current architecture, or
2. remain only where explicitly identified as historical context.

Also verify that the current architecture can be understood by reading:

```text
README.md
        ↓
docs/ERPNext_MCP_ARCHITECTURE.md
```

without needing to search the entire Python source simply to discover the server's available domains and capabilities.

---

# Expected Result

After this task, a new developer or agent should understand:

```text
What is this project?
        ↓
ERPNext MCP Server

What domains currently exist?
        ↓
Masters + Selling

What reusable capabilities exist?
        ↓
Customer + Item

What Selling capabilities exist?
        ↓
Quotation + Sales Order

How are persistent writes protected?
        ↓
prepare → preview → explicit approval → confirm

Where is current architecture documented?
        ↓
docs/ERPNext_MCP_ARCHITECTURE.md
```

Documentation should make the current source easy to trace and debug.

---

# Known Boundary

This task does **not** determine the minimum ERPNext creation fields for Customer or Item.

It does **not** yet implement metadata-driven field requirements or a new configuration architecture.

It does **not** verify MCP Inspector connectivity.

It does **not** test natural-language Agent behavior.

It does **not** modify Quotation or Sales Order workflows.

---

# Exact Next Task

After this task is completed and verified:

## Task 02 — ERPNext Metadata-Driven Master Creation Contract & Configuration Structure

That task will:

1. inspect actual ERPNext/Frappe metadata for `Customer` and `Item`,
2. determine the true minimum inputs required to create each record,
3. distinguish:
   - mandatory metadata fields,
   - ERPNext/defaulted values,
   - conditional requirements,
   - MCP policy/defaults,
   - optional fields,
4. design a clean configuration structure for changeable MCP behavior,
5. make missing-field responses traceable,
6. avoid duplicating ERPNext metadata as hard-coded MCP truth.

Do not begin Task 02 as part of this task.
