# TASK — Sales Order Read / Query / Analytics Foundation

## Status
NEXT IMPLEMENTATION TASK

## Scope
Implement the first **read-only Sales Order intelligence layer** inside the existing `mcp_erpnext` **sales profile**.

This task is intentionally **not** a 100-tool implementation.

The natural-language question list is a requirements catalogue. The MCP layer should expose a small number of generic, typed, permission-aware capabilities that an LLM/agent can combine.

This task also adds a concise-response policy to the LibreChat ERPNext agents:

> **User ne jitna poocha hai, final answer me utna hi dikhana hai.**

Example:

```text
User:
SAL-ORD-2026-00014 ka status kya hai?

Correct:
Status: To Deliver.

Wrong:
Customer..., date..., total..., items..., status..., delivery..., billing...
```

---

# 1. Architecture Decision

Freeze this responsibility split:

```text
User
  |
  v
Coordinator / Sales Agent
  | understands natural language
  | decides filters / requested fields / aggregation
  v
MCP sales read tool
  | typed contract
  | Frappe permission-aware read
  | deterministic filtering / aggregation
  v
ERPNext / Frappe
  |
  v
structured result
  |
  v
Agent
  | presents ONLY requested information
  v
User
```

## MCP owns
- permission-safe ERPNext reads
- exact filters
- sorting
- pagination / limits
- field projection
- deterministic count/sum/average/min/max
- structured result contracts
- explicit error / not-found states
- stable reusable business semantics

## Agent / LLM owns
- natural-language interpretation
- deciding which read tool to call
- converting the user's request into filters / requested fields
- chaining multiple read tools for compound questions
- final conversational formatting
- **answering only what the user asked for**

## Client UI owns
- tables/cards/rendering
- selection controls
- download/open behavior
- chat display

---

# 2. Mandatory Source Inspection Before Coding

Inspect the actual current source first.

At minimum:

```text
mcp_erpnext/
  mcp_server.py
  tool/profile registration
  contracts/
  services/
  resolvers/
  runtime / Frappe context
  tests/
  docs/TOOLS.md
  sales profile registration
```

Also inspect the installed Frappe/ERPNext v16 source for:

```text
Sales Order
Sales Order Item
Sales Team
status
delivery_status
billing_status
per_delivered
per_billed
delivery_date
Sales Person relationship
permission-aware query APIs
```

Do not implement from this task file by guessing actual paths or helper names.

Before writing custom query code, inspect and prefer native Frappe APIs and existing project helpers.

---

# 3. Frappe Query Safety Rule

For user-visible MCP reads, preserve the current authenticated Frappe user's permissions.

Prefer permission-aware Frappe APIs.

Important:

```text
frappe.get_list / frappe.db.get_list
```

applies user permissions.

Do **not** casually use:

```text
frappe.get_all / frappe.db.get_all
```

for these MCP reads because it bypasses permissions.

For more complex joins/aggregates, inspect native Frappe Query Builder / `frappe.get_query(...)` patterns and ensure permissions remain enabled.

Do not solve a difficult query by falling back to raw SQL unless there is no suitable native API and the permission behavior has been explicitly implemented and tested.

---

# 4. Phase 1 Tools

Implement a small generic read capability set.

Recommended public tools:

```text
search_sales_orders
get_sales_order
aggregate_sales_orders
query_sales_order_items
```

Exact names may follow the repository's existing naming conventions, but the semantics should remain.

Do NOT create tools such as:

```text
get_today_sales_orders
get_yesterday_sales_orders
get_open_sales_orders
get_cancelled_sales_orders
get_last_10_sales_orders
get_customer_last_order
get_month_sales_order_count
```

Natural-language variations belong to the agent. The MCP contract should stay generic.

---

# 5. Tool 1 — `search_sales_orders`

## Purpose
Search/list Sales Orders using filters, sorting, projection, and pagination.

This should cover requests such as:

```text
last 10 sales orders
today's orders
orders between dates
orders for customer X
open orders
cancelled orders
orders pending delivery
orders pending billing
orders containing item X
orders above amount X
top 10 highest-value orders
orders for territory X
orders for customer group X
orders for Sales Person X
```

## Conceptual input contract

```text
transaction_date_from?
transaction_date_to?

created_from?
created_to?

delivery_date_from?
delivery_date_to?

customer?
customer_group?
territory?

status?
delivery_status?
billing_status?

docstatus?

item_code?

sales_person?
owner?

min_grand_total?
max_grand_total?

limit?
offset?
sort_by?
sort_order?

fields?
```

### Important semantic distinction

Do not conflate:

```text
owner
```

with:

```text
sales_person
```

`owner` means the Frappe user who created/owns the document.

`sales_person` means ERPNext Sales Person / Sales Team semantics.

If Sales Person requires a child-table join, implement that explicitly and permission-safely.

## Date semantics

Support explicit date fields rather than creating tools for "today", "yesterday", "this month", etc.

Keep these distinct:

```text
transaction_date
creation
delivery_date
```

If the user says "created today", use `creation`.

If the user says "sales orders for 8 September", normally use `transaction_date`.

If wording is materially ambiguous, the agent should ask.

## Field projection

`fields` must use a safe allowlist.

Recommended header allowlist after confirming actual ERPNext fields:

```text
name
transaction_date
customer
customer_name
status
delivery_status
billing_status
delivery_date
currency
grand_total
total_qty
per_delivered
per_billed
customer_group
territory
owner
creation
modified
```

Do not expose arbitrary field names from the model.

## Default projection and minimal projection

The MCP may have a compact technical default, but the **agent should request the minimum fields needed**.

Examples:

```text
"last 10 sales orders batao"
fields = ["name"]

"last 10 sales orders date aur status ke saath"
fields = ["name", "transaction_date", "status"]

"last 10 orders date, customer, amount, status ke saath"
fields = ["name", "transaction_date", "customer_name", "grand_total", "status"]
```

## Limits

Suggested starting point:

```text
default limit = 20
hard max = 100
```

Adapt if an existing project convention already defines limits.

Do not accidentally dump thousands of records into the model.

---

# 6. Tool 2 — `get_sales_order`

## Purpose
Read an exact Sales Order by name/reference with projection.

Examples:

```text
SO-001 ka status kya hai?
SO-001 ka total kitna hai?
SO-001 ki date kya hai?
SO-001 me kaunse items hain?
SO-001 ka discount kya tha?
```

## Conceptual input

```text
sales_order: exact Sales Order reference
fields?: safe header field list
include_items?: boolean
item_fields?: safe item-field list
```

If existing project conventions use `sections`, follow those instead.

## Security

The exact document must be checked under the current authenticated Frappe user's read permission.

Do not switch to Administrator/service-user context.

Do not return the full Sales Order just because the server can access it.

Project only requested fields in the public MCP response.

## Example

User:

```text
SAL-ORD-2026-00014 ka status kya hai?
```

Agent call:

```text
get_sales_order(
  sales_order="SAL-ORD-2026-00014",
  fields=["status"]
)
```

Final answer:

```text
Status: To Deliver.
```

---

# 7. Tool 3 — `aggregate_sales_orders`

## Purpose
Perform deterministic server-side analytics.

Do not fetch hundreds of orders and ask the LLM to calculate totals.

This should cover:

```text
How many Sales Orders today?
How many this month?
Total Sales Order value this month?
Average order value?
Total open order value?
Highest order value?
Lowest order value?
How many cancelled orders?
```

## Conceptual input

Reuse the same filter model where practical.

```text
filters...

metrics: [
  "count",
  "sum_grand_total",
  "avg_grand_total",
  "min_grand_total",
  "max_grand_total",
  "sum_total_qty"
]

group_by?
```

## Grouping

Allow only explicit safe groupings that are implemented/tested, such as:

```text
status
customer
customer_group
territory
transaction_date
```

Do not accept arbitrary SQL/group expressions.

## Output

Return typed numeric values plus currency/context where required.

The LLM should explain the result, not recalculate it.

---

# 8. Tool 4 — `query_sales_order_items`

## Purpose
Read Sales Order Item history in the context of parent Sales Orders.

Needed for questions such as:

```text
What did client X order last time?
What price did client X pay for Item Y last time?
Show price history of Item Y for client X.
Has client X ever ordered Item Y?
When did client X last purchase Item Y?
Show Sales Orders containing Item Y.
Which customers purchased Item Y?
How many units of Item Y were ordered this month?
Recent prices offered for Item Y.
```

## Conceptual input

```text
customer?
item_code?

transaction_date_from?
transaction_date_to?

sales_order?
sales_order_status?

min_qty?
max_qty?

limit?
offset?
sort_by?
sort_order?

fields?
metrics?
group_by?
```

## Safe item projection

Confirm against installed ERPNext source.

Potential public fields:

```text
sales_order
transaction_date
customer
customer_name
item_code
item_name
qty
rate
amount
discount_percentage
discount_amount
delivered_qty
delivery_date
```

Do not assume every field exists.

## Item analytics

Typed metrics may include:

```text
count_rows
count_distinct_orders
sum_qty
sum_amount
min_rate
max_rate
avg_rate
```

If the existing architecture is cleaner with separate item search and item aggregation tools, splitting this tool is allowed only with a concrete contract/testing benefit.

Do not create one tool per question.

---

# 9. Fulfillment / Delivery / Billing

Do not guess ERPNext semantics.

Inspect current ERPNext v16 first.

ERPNext maintains header-level concepts including:

```text
status
delivery_status
billing_status
per_delivered
per_billed
```

and item-level delivery quantities.

For Phase 1:

- expose authoritative existing ERPNext fields where sufficient;
- answer direct questions such as fully/partly delivered or billed;
- only derive pending quantity/value when the formula is confirmed against ERPNext's current own logic.

If reliable pending delivery/billing calculations require a dedicated service, defer them to Phase 2 rather than adding an approximation.

---

# 10. Agent Concise-Answer Policy

Update the appropriate LibreChat agent instructions.

At minimum inspect:

```text
ERPNext Coordinator
ERPNext Sales Order Agent
```

If there is a shared instruction source, prefer one shared reusable policy.

Add behavior equivalent to:

```text
RESPONSE PRECISION POLICY

Answer only the information the user asked for.

Do not dump every field returned by a tool.

- If the user asks only for Sales Order status, return only the status.
- If the user asks only for a date, return only the date.
- If the user asks for the last 10 Sales Orders without requesting columns,
  return the Sales Order IDs/names only.
- If the user asks for IDs with date and status,
  return only ID, date, and status.
- If the user asks for detailed Sales Order information,
  provide only the requested details.
- Do not expose internal tool metadata, resolver metadata, or unrelated ERP fields
  unless needed to resolve ambiguity or explain an error.
- For counts/totals/averages, give the computed result directly.
- Ask a clarification question only when the missing distinction materially changes
  the answer.
```

Do not put this presentation behavior inside ERPNext business services.

---

# 11. Natural-Language Mapping Examples

These are agent behaviors, not separate tools.

## Example A

```text
User:
Show today's sales orders.

Agent:
search_sales_orders(
  transaction_date_from=<today>,
  transaction_date_to=<today>,
  fields=["name"]
)
```

## Example B

```text
User:
Show today's sales orders with customer, amount and status.

Agent:
fields=["name", "customer_name", "grand_total", "currency", "status"]
```

## Example C

```text
User:
How many open Sales Orders does Customer X have?

Agent:
aggregate_sales_orders(
  customer=<resolved exact customer>,
  status=<confirmed ERPNext open semantics>,
  metrics=["count"]
)

Final:
Customer X has 7 open Sales Orders.
```

Do not list the orders unless requested.

## Example D

```text
User:
What was the last price Customer X paid for Item Y?

Agent:
query_sales_order_items(
  customer=<resolved>,
  item_code=<resolved>,
  sort_by=<latest parent transaction date>,
  sort_order="desc",
  limit=1,
  fields=["rate", "currency", "transaction_date", "sales_order"]
)
```

Final answer should primarily answer the price.

## Example E

```text
User:
Show the last 10 Sales Orders.

Agent:
search_sales_orders(
  limit=10,
  sort_by=<latest>,
  sort_order="desc",
  fields=["name"]
)
```

Do not automatically show customer/date/amount/status.

## Example F

```text
User:
Show the last 10 Sales Orders with date, amount and status.

Same tool; only projection changes.
```

---

# 12. Compound Question Behavior

Tools must be composable.

Example:

```text
Find Patel Trading's latest Sales Order,
tell me the price they paid for Item ABC.
```

Expected orchestration:

```text
resolve customer
  ->
search_sales_orders(customer=..., latest, limit=1)
  ->
query_sales_order_items(sales_order=..., item_code=...)
  ->
concise final answer
```

Do not create a giant combination tool for every compound sentence.

---

# 13. Not in This Task

Do NOT implement yet:

```text
PDF generation
PDF download/open
Email send
WhatsApp send
prepare_send
confirm_send
create Sales Order from last Sales Order
write/update/cancel/submit actions
new approval workflows
general BI/report export
```

Existing Sales Order create/update tools must continue working unchanged.

---

# 14. Phase Plan After This Task

## Phase 1 — THIS TASK

```text
Sales Order read/search/get
Sales Order aggregates
Sales Order Item/history queries
minimal field projection
concise agent answers
permission tests
```

## Phase 2

```text
delivery/billing fulfillment intelligence
authoritative pending qty/value
due-this-week / overdue delivery semantics
advanced price/customer/item analytics
```

## Phase 3

```text
PDF generation / retrieval
```

## Phase 4

```text
email / WhatsApp send
prepare -> approval -> confirm side-effect workflow
```

## Phase 5

```text
compound workflows:
latest order -> item price -> PDF -> email
copy items from last order -> prepare new Sales Order
```

---

# 15. Tests

Tests must verify both MCP contracts and Frappe permissions.

## Unit / service tests

```text
exact Sales Order lookup
not found
no read permission
date range
customer filter
status filter
delivery_status filter
billing_status filter
amount range
sort
limit
field projection
invalid requested field
invalid sort field
hard limit
aggregate count
aggregate sum
aggregate average
item history
customer + item history
latest price
zero results
```

## Permission regression

Verify:

```text
User A can read permitted Sales Orders.
User B cannot see Sales Orders outside their Frappe permissions.
```

No query tool may silently switch to Administrator or a service user.

## Negative contract tests

```text
arbitrary field request -> rejected
arbitrary SQL/filter expression -> rejected
invalid metric -> rejected
invalid group_by -> rejected
limit over hard max -> capped or rejected per contract
invalid Sales Order -> structured not_found
```

---

# 16. Conversational Acceptance Prompts

Test through the real LibreChat Sales/Coordinator flow after MCP tests pass.

## Minimal-answer tests

```text
1. SAL-ORD-XXXX ka status kya hai?
Expected: only status.

2. SAL-ORD-XXXX ka total kitna hai?
Expected: only total + currency.

3. SAL-ORD-XXXX ki transaction date kya hai?
Expected: only date.
```

## Projection tests

```text
4. Last 10 Sales Orders batao.
Expected: only 10 Sales Order IDs/names.

5. Last 10 Sales Orders date aur status ke saath batao.
Expected: ID + date + status only.

6. Last 10 Sales Orders customer, date, amount aur status ke saath batao.
Expected: only those requested columns.
```

## Search tests

```text
7. Aaj ke Sales Orders batao.
8. Kal ke Sales Orders batao.
9. Is month ke open Sales Orders batao.
10. Customer X ke last five Sales Orders batao.
11. Item Y wale Sales Orders batao.
```

## Analytics tests

```text
12. Aaj kitne Sales Orders bane?
13. Is month Sales Order ki total value kitni hai?
14. Is month average Sales Order value kitni hai?
15. Customer X ke kitne open Sales Orders hain?
```

Pure aggregate questions must not dump source records.

## History tests

```text
16. Customer X ne Item Y last time kis rate par order kiya?
17. Customer X ne Item Y last kab order kiya?
18. Customer X ke Item Y ke last three rates batao.
19. Customer X ne last Sales Order me kya order kiya tha?
```

---

# 17. Acceptance Criteria

```text
[ ] actual current mcp_erpnext source inspected
[ ] native Frappe/ERPNext source inspected before custom query code
[ ] read tools registered only in sales profile
[ ] no purchase-profile leakage
[ ] search_sales_orders implemented
[ ] get_sales_order implemented
[ ] aggregate_sales_orders implemented
[ ] query_sales_order_items implemented, or justified equivalent split
[ ] public filters are typed/allowlisted
[ ] public fields are allowlisted
[ ] public sort/group/metrics are allowlisted
[ ] user permissions apply to every read path
[ ] no frappe.get_all permission bypass in public MCP reads
[ ] no raw SQL permission bypass
[ ] deterministic aggregates are calculated server-side
[ ] natural-language variations do not become separate tools
[ ] existing Sales Order create/update behavior is unchanged
[ ] Coordinator/Sales Order Agent concise-response policy updated
[ ] "status kya hai?" returns only status end-to-end
[ ] "last 10 Sales Orders" returns only IDs by default
[ ] explicitly requested columns are honored
[ ] unit + integration tests pass
[ ] docs/TOOLS.md or equivalent updated
```

---

# 18. Expected Result

After Phase 1, users should be able to ask many different questions without creating a tool per sentence:

```text
"Show today's orders."
"Show today's orders with amount and status."
"How many orders did Customer X place this year?"
"What is this month's total Sales Order value?"
"What is SO-001's status?"
"What rate did Customer X last pay for Item Y?"
"Show Item Y's recent prices for Customer X."
```

The agent translates these into a small reusable MCP capability set.

The MCP server returns correct, permission-safe structured data.

The agent returns only the information requested.

---

# 19. Limitations

This task does not promise that all 100 natural-language questions are supported.

Questions involving:

```text
authoritative pending billing amount
complex delivery fulfillment
PDF
email
WhatsApp
document creation from history
```

remain later phases unless current source already exposes a safe reusable capability that can be reused without expanding scope.

Do not claim support until an end-to-end test passes.

---

# 20. Completion Report

Return:

## Source inspected
Exact paths.

## Tools added
Exact public names and contracts.

## Frappe APIs used
Explain how read permissions are preserved.

## Supported question categories
Map implemented capability to the original question catalogue.

## Deferred categories
State exact reason.

## Tests
PASS / FAIL matrix.

## Agent instruction changes
Exact agent/config files or LibreChat instructions updated.

## Regression confirmation
Confirm existing create/update/approval behavior was not changed.

## Exact next task

If Phase 1 passes:

```text
Next task:
Sales Order Fulfillment / Delivery / Billing Intelligence Foundation.
```
