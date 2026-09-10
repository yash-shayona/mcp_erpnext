# Task 04 — ERPNext MCP Quotation Capability Verification With MCP Inspector

## Objective

Verify the current ERPNext MCP Server directly with MCP Inspector, without depending on the custom chatbot, LangGraph, or browser workflow.

The verification target is the current **Quotation capability path inside the single ERPNext MCP Server**.

Target flow:

```text
MCP transport
    ↓
tool registration
    ↓
Customer / Item resolution
    ↓
Task 02 metadata-driven creation contract
    ↓
Task 03 generic field-value resolution
    ↓
Quotation preparation
    ↓
explicit confirmation boundary
    ↓
Draft Quotation creation
```

The goal is to prove MCP/server correctness independently from future Agent behavior.

---

## Prerequisites

Task 01 completed:

```text
documentation synchronized
```

Task 02 completed:

```text
metadata-driven Customer/Item creation contract
configuration structure
```

Task 03 completed:

```text
generic metadata-driven field-value resolution/validation
```

Inspect current source before running tests. Do not assume old schemas or tool names if source changed.

---

## Scope

Use MCP Inspector against the local STDIO MCP server.

Primary functional focus:

```text
Customer
Item
Quotation
```

Sales Order may remain registered but is not the main verification target.

---

## Verification Order

Run in this order:

```text
1. MCP server startup
2. Tool catalog
3. Customer resolution
4. Item resolution
5. Metadata/default behavior
6. Field-value resolution
7. Customer/Item prepare behavior
8. Quotation prepare
9. Explicit Quotation confirmation
10. Idempotency / permissions / controlled errors
```

Do not jump directly to final document creation.

---

## Environment Safety

Use a local/development site and a realistic test Frappe user.

Expected runtime environment remains conceptually:

```text
MCP_BACKEND=direct
MCP_FRAPPE_SITE=<test site>
MCP_FRAPPE_USER=<test user>
```

Use current source/config as authority for exact variable names.

Do not expose secrets in logs, screenshots, reports, or chat.

---

## MCP Server Command

Confirm current source first.

Expected entrypoint is conceptually:

```text
<FRAPPE_BENCH>/env/bin/python -m mcp_erpnext.mcp_server
```

Expected working directory:

```text
<FRAPPE_BENCH>/sites
```

Do not modify server architecture merely to make Inspector connect.

---

## MCP Inspector Setup

Use the official/current MCP Inspector workflow already supported by the environment.

If Inspector or its runtime is not already available, do not install packages without permission.

First check:

```text
Node/runtime availability
npx availability
current Inspector command
```

Typical STDIO invocation may look like:

```bash
cd /home/frappe/frappe-bench/sites

export MCP_BACKEND=direct
export MCP_FRAPPE_SITE=<test-site>
export MCP_FRAPPE_USER=<test-user>

npx -y @modelcontextprotocol/inspector /home/frappe/frappe-bench/env/bin/python -m mcp_erpnext.mcp_server
```

Treat this as an example and confirm against the current environment.

---

# Phase 1 — Server Startup

Verify:

```text
MCP process starts
STDIO handshake succeeds
Inspector connects
no unexpected traceback
```

Record:

```text
PASS / FAIL
```

If startup fails, stop and diagnose startup before testing tools.

---

# Phase 2 — Tool Catalog

List MCP tools in Inspector.

Compare against:

```text
mcp_erpnext/tools/__init__.py
mcp_erpnext/tests/test_tool_registration.py
```

Verify current:

```text
tool names
descriptions
input schemas
required parameters
```

The previously expected catalog includes:

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

Do not mark this list correct unless current source still matches it.

---

# Phase 3 — Customer Resolution

Use safe existing Customer records.

Test:

## Exact

Expected:

```text
resolved
```

## Case/normalization variation

Expected:

```text
canonical Customer
```

or the current deterministic selection state.

## Typo / candidate query

Expected:

```text
single safe resolution
OR
needs_selection
```

according to current policy.

## Ambiguous

Expected:

```text
needs_selection
```

with structured candidates.

Do not allow silent guessing.

## Missing

Expected current equivalent of:

```text
needs_customer_creation
```

## Permission behavior

If suitable test data exists, verify inaccessible Customer records are not leaked.

---

# Phase 4 — Item Resolution

Repeat for Item:

```text
exact
case/normalization
candidate resolution
ambiguous
missing
permission behavior
```

Verify any current sales-item filtering against current source/config.

---

# Phase 5 — Task 02 Metadata-Driven Missing Fields

## Customer

Call `prepare_customer` with the smallest practical input.

Example:

```json
{
  "customer": {
    "customer_name": "MCP TEST CUSTOMER <unique suffix>"
  }
}
```

Do not confirm/create yet.

Verify:

```text
runtime defaults applied
optional fields not requested
only still-missing mandatory fields returned
structured missing-field metadata present
custom/site mandatory fields detected if applicable
```

## Item

Call `prepare_item` with intentionally incomplete input.

Verify:

```text
only unresolved actual mandatory fields requested
runtime defaults prevent unnecessary prompts
MCP policy values remain distinct
```

---

# Phase 6 — Task 03 Field Resolution

Inspect actual exposed Customer/Item fields and test applicable types.

At minimum, where currently exposed:

```text
Select
Link
scalar
Check/policy
```

---

## Select Verification

Use an actual exposed Select field, for example `Customer.customer_type` if still applicable.

Test:

```text
exact canonical option
case-normalized option
invalid option
```

Expected:

```text
canonical option returned
invalid option rejected safely
options sourced from runtime metadata
```

---

## Link Verification

Use actual exposed Link fields.

Possible examples may include:

```text
Customer.customer_group
Customer.territory
Item.item_group
Item.stock_uom
```

Inspect current config first.

Test:

```text
exact linked record
normalized/case variation
ambiguous query if test data allows
nonexistent query
```

Expected:

```text
resolved
needs_selection
not_found
```

as appropriate.

Verify lookup respects the configured Frappe user's permissions.

---

## Optional Link / Select Verification

For an optional exposed field:

```text
not supplied
    → no unnecessary needs_input
```

Then provide an invalid value:

```text
supplied invalid optional field
    → must still be validated
```

Optional does not mean unchecked.

---

# Phase 7 — Customer / Item Prepare Safety

For both:

```text
prepare_customer
prepare_item
```

verify:

```text
preview/ready state can be returned
approval state/token is created as designed
NO ERPNext master record is inserted during prepare
```

Use read-only ERPNext verification to confirm no record exists after prepare.

Do not call confirm merely to prove preparation.

---

# Phase 8 — Quotation Prepare

For the first Quotation test use:

```text
existing accessible Customer
existing accessible Item
```

Do not combine missing-master creation with the first Quotation test.

Use the smallest valid payload shown by Inspector/current schema.

Conceptually:

```json
{
  "customer": {
    "doctype": "Customer",
    "name": "<existing-customer>"
  },
  "items": [
    {
      "item": {
        "doctype": "Item",
        "name": "<existing-item>"
      },
      "qty": 2
    }
  ],
  "valid_till": "<valid date>",
  "company": "<test company>"
}
```

Adapt this to the current source schema.

---

## Quotation Prepare Expected Result

Verify:

```text
status = ready
structured preview returned
approval state/token returned
```

Inspect only source-supported fields such as:

```text
customer
company
transaction date
valid till
currency
price list
items
qty
rate
discount
taxes
net total
grand total
terms
```

Most importantly verify:

```text
NO Quotation was inserted
```

after `prepare_quotation`.

ERPNext remains authoritative for rates, taxes, defaults, and totals.

---

# Phase 9 — Explicit Confirmation

This phase performs a real ERPNext write.

Do not execute unless:

```text
the site is confirmed safe for test writes
AND
explicit permission to create test records has been granted
```

If permission is not granted, stop after successful prepare and report:

```text
NOT RUN — write permission not granted
```

If permission is granted:

```text
confirm_quotation
```

using the exact approval state/token returned by preparation.

Expected:

```text
status = created
document reference returned
docstatus = 0
```

Verify in ERPNext:

```text
exactly one Draft Quotation exists
```

Do not submit it or move it to Sent/Accepted.

---

# Phase 10 — Idempotency and Approval Safety

If current source supports idempotent confirmation, repeat the same confirmation.

Expected:

```text
same document reference
no duplicate Quotation
```

Where supported, verify controlled failures for:

```text
invalid approval token/state
expired approval
wrong action
different user
different site
modified prepared payload
confirm=false
```

Do not weaken safety checks to make tests pass.

---

# Missing Customer Scenario

After the existing-master Quotation path passes, verify the MCP primitives needed by a future Agent:

```text
resolve_customer
    ↓
missing
    ↓
prepare_customer
    ↓
metadata-driven missing fields
    ↓
field-value resolution
    ↓
Customer preview
```

Do not add LangGraph or conversation state.

Customer creation itself requires explicit write permission.

---

# Missing Item Scenario

Likewise verify:

```text
resolve_item
    ↓
missing
    ↓
prepare_item
    ↓
metadata-driven missing fields
    ↓
field-value resolution
    ↓
Item preview
```

No chatbot or LangGraph is involved.

---

# Error / Permission Verification

Trigger safe controlled cases where practical:

```text
invalid Customer
invalid Item
invalid Link value
invalid Select value
missing mandatory value
permission denial
invalid approval
```

Verify MCP output does not expose:

```text
secrets
raw credentials
unsafe tracebacks
internal sensitive values
```

---

# Verification Report

Create:

```text
docs/tests/MCP_QUOTATION_INSPECTOR_VERIFICATION.md
```

if consistent with the repository structure.

Use honest states:

```text
PASS
FAIL
NOT RUN
BLOCKED
```

Suggested report table:

```text
Test                                  Result
---------------------------------------------
MCP startup                           PASS
Tool registration                    PASS
Customer exact resolution            PASS
Customer ambiguity                   PASS
Item exact resolution                PASS
Metadata-driven missing fields       PASS
Select resolution                    PASS
Link resolution                      PASS
Optional-field validation            PASS
Customer prepare no-write            PASS
Item prepare no-write                PASS
Quotation prepare                    PASS
Quotation prepare no-write           PASS
Quotation confirmation               NOT RUN / PASS
Quotation idempotency                NOT RUN / PASS
Permission behavior                  PASS / BLOCKED
```

Never mark an unexecuted test as PASS.

---

# Files Allowed to Change

Prefer no runtime source changes.

Allowed:

```text
docs/tests/MCP_QUOTATION_INSPECTOR_VERIFICATION.md
```

If a defect is found:

```text
document it
identify exact source location
stop
propose a separate focused fix task
```

Do not silently implement unrelated fixes during verification.

---

# Do Not Change

Do not redesign:

```text
MCP architecture
Task 02 creation contract
Task 03 field resolver
Quotation service
approval architecture
chatbot
LangGraph
OAuth
frontend
```

---

# Do Not Run Without Permission

Do not run:

```text
bench migrate
bench build
bench restart
bench update
bench install-app
```

Do not install packages without permission.

Do not create ERPNext records unless explicit test-write permission is granted.

---

# Acceptance Criteria

- [ ] MCP server connects to Inspector.
- [ ] Current tool catalog is verified.
- [ ] Customer resolution is runtime-tested.
- [ ] Item resolution is runtime-tested.
- [ ] Task 02 metadata/default behavior is runtime-tested.
- [ ] Task 03 Select/Link/scalar behavior is runtime-tested where exposed.
- [ ] Optional supplied Link/Select values are validated.
- [ ] Ambiguous values are never silently guessed.
- [ ] Permission-aware candidate behavior is verified where possible.
- [ ] Customer prepare performs no write.
- [ ] Item prepare performs no write.
- [ ] Quotation prepare returns a structured preview.
- [ ] Quotation prepare performs no write.
- [ ] If write permission is granted, exactly one Draft Quotation is created.
- [ ] If supported, repeated confirmation is idempotent.
- [ ] Results are recorded honestly.
- [ ] No chatbot/LangGraph dependency is required.

---

# Expected Result

After this task we should know whether this server path is genuinely working:

```text
Customer / Item resolution
        ↓
metadata-driven contract
        ↓
generic field resolver
        ↓
Quotation preview
        ↓
explicit approval
        ↓
Draft Quotation
```

If this passes, future Agent work can focus on:

```text
conversation state
parent/subtask state
interrupt/resume
free-form interaction
tool orchestration
```

instead of debugging basic MCP functionality simultaneously.

---

# Exact Next Task

**Task 05 — MCP-Aware Agent Host Natural-Language Verification**

Connect an existing MCP-capable Agent host directly to the verified local ERPNext MCP server and test natural-language tool discovery/orchestration before building the custom LangGraph layer.
