# TASK 19 — Customer Field-Aware Read / Query Foundation

## Status
NEXT IMPLEMENTATION TASK

## Objective
Implement a **read-only, field-aware Customer query foundation** inside the existing `mcp_erpnext` **sales profile**, using the already-implemented Sales Order read/query layer as the primary project pattern.

This task must solve the currently observed Customer lookup failure where a structured value such as an email address is sent to the fuzzy Customer name resolver and produces unrelated candidates.

Observed regression example:

```text
User:
Find the customer whose email is customer@example.com

Current wrong behavior:
search_customers("customer@example.com")
-> tokenises the free-text query
-> `com` can match names such as "... Components ..."
-> unrelated Customer candidates can be returned
-> the agent may incorrectly present those candidates as email matches
```

The correct architecture is **not** to make the fuzzy resolver search every Customer field. Instead, preserve entity resolution for names and add a separate deterministic Customer read/query capability for actual fields.

---

# 1. Frozen Architecture Decision

Preserve this distinction:

```text
Customer entity/name resolution
--------------------------------
search_customers
resolve_customer

Purpose:
- human-entered Customer name/reference
- spelling correction
- ambiguity handling
- explicit candidate selection

Examples:
"Shankus"
"Sunrise Auto"
"Vertex Learning"


Customer read/query intelligence
--------------------------------
get_customer
query_customers
aggregate_customers

Purpose:
- exact Customer document read
- field-aware filters
- field projection
- sorting
- pagination
- deterministic counts/grouping

Examples:
"customer whose email_id is ..."
"customers in territory X"
"disabled customers"
"customers created this month"
"show name, email and territory"
```

Do **not** merge these two responsibilities into one fuzzy search path.

Do **not** replace the existing `search_customers` / `resolve_customer` workflow.

---

# 2. Existing Implementation Is the First Source of Truth

Before designing or coding anything, inspect the current implementation in the working tree.

The agent must follow this order:

```text
1. Inspect existing mcp_erpnext implementation
2. Inspect existing shared helpers / contracts / registration
3. Inspect current Sales Order read/query implementation
4. Inspect current Customer resolver + creation implementation
5. Inspect installed Frappe / ERPNext v16 metadata and native query APIs
6. Decide the smallest implementation that reuses the established pattern
7. Only then edit code
```

Do not start from this task file's examples and guess field names, helper names, file locations, or Frappe behavior.

### Mandatory `mcp_erpnext` files to inspect

At minimum:

```text
mcp_erpnext/contracts/selling/sales_order_read.py
mcp_erpnext/services/selling/sales_order_read.py
mcp_erpnext/tools/selling/sales_order_read.py
mcp_erpnext/tests/test_sales_order_read.py

mcp_erpnext/config/masters/customer.py
mcp_erpnext/contracts/masters/resolution.py
mcp_erpnext/services/masters/customer.py
mcp_erpnext/services/common/entity_resolution.py
mcp_erpnext/tools/masters/customer.py
mcp_erpnext/tests/test_customer_service.py

mcp_erpnext/contracts/registry.py
mcp_erpnext/contracts/audit.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_tool_contracts.py

scripts/generate_tool_catalog.py
docs/TOOLS.md
```

Also inspect any additional file that the current working tree proves is part of the actual registration/runtime path.

### Existing strategy to reuse

The current Sales Order read/query foundation already uses:

- typed Pydantic public inputs/outputs;
- a fixed safe field allowlist;
- a fixed safe sort allowlist;
- typed filter semantics;
- permission-aware Frappe reads;
- `ignore_permissions=False`;
- server-side projection;
- bounded pagination;
- server-side aggregation;
- explicit public tool contracts in `contracts/registry.py`;
- profile registration tests;
- generated `docs/TOOLS.md`.

Customer read/query should belong to the **same architecture family** unless source inspection proves that a Customer-specific difference requires a documented exception.

---

# 3. Mandatory Runtime Metadata Inspection Before Field Design

The final Customer field arrays / Pydantic `Literal[...]` values must **not** be invented from memory, labels, this task file, or natural-language examples.

Inspect the installed site's actual Customer metadata first, using Frappe-native metadata APIs and/or the installed ERPNext source.

At minimum inspect:

```python
meta = frappe.get_meta("Customer")
```

and the relevant metadata needed to distinguish:

- actual fieldname;
- fieldtype;
- Link target/options;
- hidden/read-only behavior;
- `fetch_from` behavior;
- virtual vs database-backed field behavior;
- standard/default fields;
- custom fields / property setters on the installed site.

For database-backed listing/filtering/sorting, also confirm that the chosen field is actually queryable by the native Frappe list/query path. Do not assume that merely appearing in metadata means it is a safe database filter/sort field.

### Required metadata evidence table

Before implementation, create an inspection table in the final implementation report with at least:

```text
fieldname
label
fieldtype
options/link target
standard or custom
fetch_from (if any)
queryable/list-column status
chosen for projection? yes/no
chosen for filter? yes/no
chosen for sorting? yes/no
chosen for grouping? yes/no
reason
```

### Candidate fields are NOT a final allowlist

During inspection, likely relevant concepts include:

```text
Customer identity/name
Customer Group
Territory
Customer Type
primary email
primary mobile
Tax ID
Disabled / Frozen state
Account Manager
Currency / Price List if useful
creation / modified / owner
```

These are requirement concepts only.

The implementation must use the **actual verified fieldnames** from the installed metadata.

For example, if installed metadata confirms fields such as `email_id` or `mobile_no`, the MCP query should use those actual fieldnames rather than inventing `email` or `mobile` as database fields.

Site-specific fields such as GST-related fields must not be assumed. Expose them only if the current deployment policy and runtime metadata make that safe and deterministic. Otherwise defer them and document the limitation.

---

# 4. Field Exposure Rule

Use the same principle as the Sales Order read foundation:

```text
actual installed metadata / source
            +
MCP safe business policy
            =
fixed public read/query allowlist
```

Do **not** do either of these:

```text
Expose every Customer field automatically from meta            X
Accept arbitrary field names supplied by the LLM              X
```

The public MCP schema must remain small, typed, stable, and auditable.

### Runtime metadata role

Runtime metadata is authoritative for discovering and verifying actual fields.

Do not add a completely new dynamic-schema architecture just for Customer if the current Sales Order implementation does not use one.

The expected strategy for this task is:

```text
inspect actual metadata
-> choose safe useful fields
-> freeze typed allowlists
-> query only those fields
```

If inspection proves a site-specific field requires runtime conditional handling, implement that narrowly and document why it cannot safely follow the static Sales Order pattern.

---

# 5. Public Tool Set

Implement a small reusable Customer read capability, not one tool per natural-language question.

## Tool A — `get_customer`

### Purpose
Read one exact Customer document by its exact ERPNext Customer name/reference, with safe field projection.

Conceptual input:

```text
customer: exact Customer document name
fields?: safe verified Customer field list
```

Expected behavior:

- exact document only;
- no fuzzy fallback;
- current authenticated user's read permission;
- only requested/allowlisted fields in output;
- `not_found` when the exact Customer does not exist or is not visible according to the established permission-safe pattern;
- no create/update side effect.

Follow `get_sales_order` structure where applicable.

---

## Tool B — `query_customers`

### Purpose
List/filter Customers using deterministic field-aware filters, sorting, projection, and pagination.

This is the capability that should answer questions such as:

```text
Find the customer whose email is X.
Show customers in Customer Group X.
Show customers in Territory X.
Show disabled customers.
Show customers created this month.
Show the latest 10 customers.
Show customer name and email only.
Show customers owned by user X, if owner is explicitly included after inspection.
```

### Filter contract

Derive the final filter input fields only after metadata inspection.

Follow the Sales Order pattern:

- actual ERPNext field names for direct equality filters where practical;
- explicit date-range convenience parameters may map to actual fields such as `creation` / `modified`, matching the existing Sales Order pattern;
- no arbitrary filter dictionaries from the model;
- no arbitrary operators from the model;
- no raw SQL fragments;
- no model-supplied field expressions.

### Exact semantics for structured identifiers

Email/mobile/tax-style identifiers must use deterministic field filters once those fields are verified.

Example after metadata verification:

```text
query_customers(email_id="customer@example.com")
```

must become an exact field comparison against the verified Customer field.

It must **not** become:

```text
free-text token search
LIKE "%<email-local-part>%"
LIKE "%<email-domain>%"
LIKE "%com%"
```

and it must never fall back to unrelated Customer-name candidates.

### Active/disabled behavior

The existing name resolver intentionally uses:

```text
disabled != 1
```

for active Customer resolution.

Do **not** blindly copy that resolver filter into `query_customers`, because field-aware read requests must be able to ask for disabled Customers.

`query_customers` should apply a disabled/active filter only when the public query explicitly requests it, unless source inspection proves an existing project policy that requires otherwise.

### Pagination

Follow the current Sales Order convention unless inspection finds a shared project constant:

```text
default limit: 20
hard maximum: 100
offset >= 0
```

Do not return thousands of Customer records by default.

### Projection

`fields` must be a typed allowlist of actual verified Customer fields.

Default projection should be compact. The agent should request only what the user asked for.

---

## Tool C — `aggregate_customers`

### Purpose
Provide deterministic server-side Customer counts/grouping without fetching large record sets into the LLM.

Minimum useful metric:

```text
count
```

Potential groupings must be chosen only from verified safe Customer fields after inspection, for example business concepts such as:

```text
Customer Group
Territory
Customer Type
Disabled state
```

Do not copy Sales Order monetary metrics because they do not belong to Customer.

Do not accept arbitrary SQL/group-by expressions.

If source inspection shows that a separate aggregate tool adds no real capability beyond an already-existing safe project mechanism, document that evidence before omitting it. Do not silently drop it.

---

# 6. Preserve Existing `search_customers` Resolver Semantics

`search_customers` and `resolve_customer` remain **name/entity resolution tools**.

Current configured fields:

```text
name
customer_name
```

Do not solve the current email issue by adding email/mobile/tax fields into the existing fuzzy `SEARCH_FIELDS` tuple.

That would preserve tokenised fuzzy matching and can create false positives for structured values.

### Tool description hardening

Update public descriptions/docstrings/contracts as needed so the tool-selection boundary is explicit:

```text
search_customers
= Customer name/reference discovery and ambiguity resolution
= NOT email/mobile/tax/field filtering

query_customers
= field-aware deterministic Customer record query
```

### Regression safety for email-shaped input

The server must not reproduce the current `.com -> Components` false-positive path.

At minimum, protect obvious email-shaped input at the Customer resolver boundary.

Preferred narrow behavior:

```text
search_customers("someone@example.com")
resolve_customer("someone@example.com")

-> typed error such as CUSTOMER_STRUCTURED_QUERY_REQUIRED
-> message directs the caller to `query_customers` with the verified email field
-> no fuzzy Customer candidates
```

Keep this guard Customer-specific unless evidence proves that the shared resolver itself should change.

**Do not modify `services/common/entity_resolution.py` just to fix this one Customer case.**

If a shared resolver change is genuinely required, stop first, document the exact cross-Doctype impact (Customer, Item, Supplier, etc.), and only proceed if the change is demonstrably safe with regression tests for every affected resolver.

Do not invent a broad phone/GST identifier classifier without concrete requirements and test cases.

---

# 7. Frappe-Native Query and Permission Rules

Preserve the authenticated Frappe user's permissions.

Prefer the same native patterns already used by Sales Order read/query:

```text
frappe.get_doc(...)
Document.has_permission("read")
frappe.get_list(..., ignore_permissions=False)
Frappe Query Builder only if actually needed
```

Do not use:

```text
frappe.get_all / frappe.db.get_all
ignore_permissions=True
Administrator switching
service-user fallback for authenticated HTTP requests
raw SQL to avoid a native query limitation
```

unless there is a separate reviewed architecture decision.

For this Customer foundation, simple Customer header fields should normally be handled by `frappe.get_list` rather than a custom SQL path.

---

# 8. Contract Design

Follow the existing typed Sales Order read contracts.

Recommended new file after confirming current structure:

```text
mcp_erpnext/contracts/masters/customer_read.py
```

Expected contract concepts:

```text
CustomerField
CustomerSortField
CustomerGroupBy
CustomerMetric
CustomerFilters
CustomerGetInput
CustomerQueryInput
CustomerAggregateInput
Customer output models
```

The exact names may follow existing repository naming conventions discovered during inspection.

### Contract requirements

- `extra="forbid"` behavior inherited from the project's public contract base;
- typed `Literal[...]` field/sort/group values;
- bounded limit/offset;
- validated date ranges;
- no user-provided arbitrary operators;
- no arbitrary fieldname strings;
- no arbitrary SQL or expressions;
- typed `ok` / `not_found` / `error` states as appropriate;
- structured MCP output schema.

---

# 9. Service Design

Recommended separation after confirming current paths:

```text
mcp_erpnext/services/masters/customer_read.py
```

Do not turn `services/masters/customer.py` into one giant resolver + creation + read/query module unless the current repository structure clearly prefers that.

The read service should contain only read/query business logic.

Reuse the established Sales Order implementation pattern where appropriate:

```text
allowlisted field set
filter builder
range helper
projection helper
exact get
field-aware query
aggregate query
```

Do not copy Sales Order-specific status/amount/item logic into Customer.

If a truly generic helper can be reused without changing behavior, use it. Do not create a broad abstraction merely to remove a few duplicated lines.

---

# 10. Tool Wrapper and Profile Registration

Recommended wrapper location after inspection:

```text
mcp_erpnext/tools/masters/customer_read.py
```

Register the new tools only in the **sales profile** for this task.

Expected public inventory addition:

```text
get_customer
query_customers
aggregate_customers
```

Preserve all existing sales tools.

Do not add these tools to the purchase profile unless a separate architecture decision explicitly makes Customer a shared cross-profile capability.

Register explicit contracts in:

```text
mcp_erpnext/contracts/registry.py
```

New tools must be fully typed/non-legacy and pass the existing contract audit.

---

# 11. Files Allowed to Change

After mandatory inspection, expected implementation changes are limited to Customer read/query and necessary registration/tests/docs.

Likely new files:

```text
mcp_erpnext/contracts/masters/customer_read.py
mcp_erpnext/services/masters/customer_read.py
mcp_erpnext/tools/masters/customer_read.py
mcp_erpnext/tests/test_customer_read.py
```

Likely existing files allowed to change:

```text
mcp_erpnext/services/masters/customer.py
mcp_erpnext/tools/masters/customer.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tests/test_customer_service.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_tool_contracts.py
scripts/generate_tool_catalog.py        only if current generator requires a generic change
docs/TOOLS.md                           generated, not hand-edited
```

If inspection proves another existing file is required, it may be changed only when the implementation report explains why.

---

# 12. Files / Areas Not to Change

Do not modify unrelated workflows.

At minimum, keep these untouched unless a concrete failing dependency proves otherwise:

```text
Sales Order create/prepare/confirm logic
Quotation create/prepare/confirm logic
Purchase Order logic
lifecycle update/submit/cancel/delete
approval policy and trusted approval state
HTTP identity / mcp_identity behavior
PDF foundation
email foundation, if present in the working tree
Item resolver behavior
Supplier resolver behavior
```

Do not refactor the Sales Order read/query implementation merely because Customer is being added.

Do not redesign `services/common/entity_resolution.py` as part of this task unless the mandatory stop-and-review condition in Section 6 is met.

---

# 13. Required Unit / Contract Tests

Add focused tests that mirror the existing Sales Order read test style.

## A. Metadata/field policy evidence

The implementation report must prove every exposed Customer field was verified against installed metadata/source.

The automated suite must at least prove arbitrary field/sort/group input is rejected by the typed contract.

Examples:

```text
fields=["owner; drop table"]             -> validation failure
sort_by="creation desc; delete"         -> validation failure
unknown field                            -> validation failure
limit > hard maximum                     -> validation failure
invalid date range                       -> validation failure
```

## B. Exact Customer read

```text
get_customer(exact reference, fields=[...])
-> only requested fields
-> no unrelated fields
-> read permission checked
-> not_found handled
```

## C. Field-aware query

Verify:

```text
ignore_permissions=False
only allowlisted fields are requested
only allowlisted sort fields are used
limit/offset are bounded
creation/modified ranges map to actual fields correctly
exact direct filters use equality rather than fuzzy matching
```

## D. Email regression — mandatory

Use the exact regression shape:

```text
customer@example.com
```

Required test behavior:

```text
query_customers(<verified email field>=that value)
-> exact field filter
-> if no row exists: status=ok, customers=[], count=0
-> must not return Sunrise Auto Components Ltd
-> must not return Sunrise Auto Components Pvt Ltd
```

Also test:

```text
search_customers("customer@example.com")
```

must not reach the old tokenised fuzzy path that allows `com` to match `Components`.

Expected terminal result is the new typed structured-query-required error, or another equally deterministic safe result documented before implementation.

## E. Existing name resolver regression

Existing valid behavior must remain:

```text
search_customers("Sunrise Auto")
-> normal resolver candidate behavior

resolve_customer(<valid name query>)
-> existing resolved/ambiguous/not_found semantics
```

Do not break Customer selection workflows used by Quotation/Sales Order creation.

## F. Disabled Customer behavior

Prove that structured query can explicitly request disabled Customers and does not silently inherit the resolver's active-only filter.

## G. Aggregate behavior

At minimum:

```text
count
```

must be computed server-side under normal permissions.

If grouping is implemented, verify only the final inspected allowlist is accepted.

## H. Registration/audit

Update and pass tests for:

```text
sales profile tool list
purchase profile isolation
static registration order/inventory
contract audit
output schema exposure
```

---

# 14. Required Full Regression Tests

After focused tests pass, run the full existing test suite using the project's actual bench Python environment.

Follow the current repository/test environment rather than guessing the interpreter path.

Expected pattern in the current app is equivalent to:

```bash
<bench-python> -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
```

Then regenerate/check the tool catalog using the existing script:

```bash
<bench-python> scripts/generate_tool_catalog.py
<bench-python> scripts/generate_tool_catalog.py --check
```

Do not hand-edit generated `docs/TOOLS.md`.

Record the exact commands, test count, and result in the implementation report.

---

# 15. Required MCP Tool Schema Verification

After implementation, inspect the actual registered sales-profile `tools/list` schema.

Verify:

```text
get_customer
query_customers
aggregate_customers
```

are present with typed input/output schemas.

Verify:

```text
search_customers
resolve_customer
```

remain present and preserve their entity-resolution contract.

Verify the purchase profile did not gain Customer read tools accidentally.

---

# 16. Live Test Prompts

Run these against the live sales MCP profile if the environment is available.

Use actual existing Customer values where required.

## Mandatory regression

```text
muje esa customer find karo do jiska email customer@example.com hai
```

If the email does not exist, expected final behavior:

```text
Is email address se koi customer nahi mila.
```

No unrelated Sunrise Customer candidate may be presented as an email match.

## Field-aware query examples

```text
Show disabled customers.
Show customers in <existing territory>.
Show customers in <existing customer group>.
Show the latest 10 customers.
Show only customer name and email for the latest 10 customers.
Show customers created this month.
How many customers are in <existing customer group>?
```

## Exact read examples

```text
Show the email of <exact customer>.
Show the territory of <exact customer>.
Show only customer name, group and territory for <exact customer>.
```

## Resolver regression examples

```text
Find customer Sunrise Auto.
Find customer Shankus.
```

Resolver behavior must remain name-oriented and ambiguity-safe.

---

# 17. Response Precision Rule

Preserve the same presentation principle introduced with Sales Order reads:

> User asked for only email -> return only email/result.
> User asked for names only -> return names only.
> User asked for count -> return the count, not the entire Customer rows.

This is agent presentation behavior; do not put conversational formatting into the Customer service layer.

The MCP service should return structured data only.

---

# 18. Acceptance Criteria

This task is complete only when all of the following are true:

- [ ] Current source was inspected before coding.
- [ ] Installed Customer metadata/source was inspected before defining field arrays.
- [ ] Final public Customer fields are actual verified fieldnames, not guessed labels.
- [ ] Arbitrary model-supplied field names are impossible.
- [ ] `search_customers` remains a name/entity resolver.
- [ ] `resolve_customer` remains a name/entity resolver.
- [ ] Obvious email-shaped input cannot produce fuzzy name candidates such as `Components` via the `com` token.
- [ ] `get_customer` provides permission-aware exact Customer reads with projection.
- [ ] `query_customers` provides typed field-aware filtering, projection, sorting, pagination.
- [ ] Structured identifier filters use deterministic exact semantics.
- [ ] Disabled Customers can be queried explicitly.
- [ ] `aggregate_customers` provides deterministic server-side count/grouping within the final safe contract.
- [ ] No `get_all`, permission bypass, Administrator switch, or raw SQL shortcut was introduced.
- [ ] Sales Order read/query behavior remains unchanged.
- [ ] Customer create/resolution/selection workflows remain unchanged except the deliberate structured-query safety guard.
- [ ] Purchase profile remains isolated.
- [ ] Contract audit passes.
- [ ] Full existing unit test suite passes.
- [ ] Generated `docs/TOOLS.md` is current.
- [ ] Live email regression is verified if a live site is available; otherwise marked `NOT VERIFIED`, never guessed.
- [ ] Final implementation report is created under `docs/inspect/`.

---

# 19. Required Implementation Report

At task completion create:

```text
docs/inspect/CUSTOMER_FIELD_AWARE_READ_QUERY_IMPLEMENTATION_REPORT.md
```

The report must include:

```text
1. Final status: PASS / PARTIAL / FAIL
2. Exact source files inspected
3. Installed Frappe / ERPNext version inspected
4. Customer metadata evidence table
5. Final exposed field/filter/sort/group allowlists and why each was chosen
6. Files added/changed
7. Final MCP public tool contracts
8. How existing search_customers remains separate from query_customers
9. Exact root-cause handling for the email -> `.com` -> Components regression
10. Permission behavior
11. Static/focused test results
12. Full regression test result and exact command
13. tools/list / contract audit result
14. Live MCP prompt results, or explicitly NOT VERIFIED
15. Known limitations / deferred Customer relationships
16. Safety confirmation
17. Exact next task recommendation
```

Do not claim live success for anything that was not actually executed.

---

# 20. Out of Scope / Deferred

Do not expand this task into a complete Customer 360 implementation.

Defer unless an existing required test proves otherwise:

```text
all linked Contact rows
all linked Address rows
Customer credit analytics
Sales Order history inside Customer tool
Invoice / Payment history
communication/email timeline
CRM Lead/Deal relationships
arbitrary child-table query engine
custom-field auto-exposure
cross-profile Customer sharing
write/update Customer behavior
```

Those should be separate focused tasks if later required.

---

# 21. Exact Next Task After This One

After this task is implemented and verified, stop.

Do not automatically generalize the engine to Item/Supplier.

The next task should be chosen from actual testing evidence.

If Item/Supplier field-aware questions are then required, the next candidate is:

```text
Item Field-Aware Read / Query Foundation
```

Before that task, inspect whether the Customer + Sales Order implementations now contain a genuinely reusable read-query helper. Extract a common helper only when two or more working implementations prove the abstraction is stable; do not pre-abstract Customer in this task.
