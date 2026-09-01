# 07C Precheck — MCP Client-Agnostic Architecture Audit

## Task Type

**Inspection / architecture audit only.**

Do **not** implement fixes in this task.

This task exists to verify that the current `mcp_erpnext` implementation produced by Task 07A and Task 07B is genuinely **MCP client-agnostic**, rather than accidentally coupled to LibreChat.

The result of this audit will decide whether the project may proceed directly to:

```text
Task 07C — Generic Explicit User Approval / Confirm Tool Safety
```

or whether a focused client-decoupling cleanup is required first.

---

# 1. Core Question

Answer this question from the **actual current repository**, not from task documents alone:

> If LibreChat is removed tomorrow, can the same `mcp_erpnext` MCP server, public tool contracts, resolver behavior, services, and ERPNext business logic continue to work with another standards-compliant MCP client without redesigning the core server?

Examples of alternative consumers may include:

```text
MCP Inspector
VS Code / Codex MCP client
another generic MCP client
a future LangGraph/custom chatbot using an MCP client adapter
another future UI/client
```

Client-specific authentication/identity adapters are allowed to differ.

The **business MCP tool layer must not depend on LibreChat**.

---

# 2. Expected Architecture

The intended boundary is:

```text
                   CLIENTS
        ┌────────────┼─────────────┐
        │            │             │
    LibreChat    MCP Inspector   Future Client
        │            │             │
        └────────────┼─────────────┘
                     ↓
              MCP TRANSPORT
          stdio / streamable-http
                     ↓
          CLIENT/IDENTITY ADAPTER
              when required
                     ↓
           MCP PUBLIC TOOL LAYER
          typed input contracts
          typed output contracts
          tool descriptions
          side-effect metadata
                     ↓
              THIN WRAPPERS
                     ↓
             DOMAIN SERVICES
       Customer / Item / Quotation /
        Sales Order / future domains
                     ↓
             FRAPPE / ERPNEXT
```

LibreChat-specific knowledge is acceptable only in a clearly isolated adapter/integration layer where it is actually required.

It must not leak into generic business contracts or domain services.

---

# 3. Audit Mode — No Changes

## Allowed

You may:

```text
read source files
inspect git status/history if useful
grep/search the repository
inspect installed package versions
inspect generated MCP schemas
run read-only/safe tests
run MCP tools/list through a safe local mechanism
run static checks
inspect documentation
```

## Forbidden

Do not:

```text
edit source code
edit docs
create new files in the repository
apply patches
run migrations
modify Frappe records
create Customer/Item/Quotation/Sales Order documents
change LibreChat
change environment configuration
rotate secrets
commit anything
```

If you need scratch output, use terminal/stdout or a temporary location outside the repository and clean it afterward.

---

# 4. Mandatory Repository Inspection

Inspect the actual current repository structure first.

At minimum locate and inspect the equivalents of:

```text
README.md
pyproject.toml / package metadata

mcp_erpnext/mcp_server.py
mcp_erpnext/settings.py
mcp_erpnext/runtime.py
mcp_erpnext/identity.py
mcp_erpnext/transport_identity.py
mcp_erpnext/http_transport.py

mcp_erpnext/contracts/**
mcp_erpnext/resolvers/**
mcp_erpnext/services/**
mcp_erpnext/approvals.py or equivalent

tests/**

docs/architecture/**
docs/TOOLS.md
AGENTS.md / docs/ai/* / CONTRIBUTING.md if present
```

Do not assume these exact paths exist.

Report the real paths discovered.

---

# 5. Repository-Wide LibreChat Coupling Search

Search the entire repository for at least:

```text
LibreChat
librechat
X-LibreChat
X-LibreChat-User-ID
LIBRECHAT
conversation_id
message_id
assistant_id
```

Also search for any other client-specific names discovered during inspection.

For **every meaningful occurrence**, classify it as one of:

```text
ACCEPTABLE_ADAPTER_COUPLING
ACCEPTABLE_DOCUMENTATION
TEST_ONLY
QUESTIONABLE_COUPLING
CORE_LAYER_VIOLATION
```

Do not simply count matches.

Explain why each meaningful category is acceptable or problematic.

---

# 6. Public MCP Contract Audit

Inspect the Task 07A implementation.

Determine whether public input/output contracts are defined as **MCP/domain contracts**, not LibreChat payloads.

## Verify

Public tool contracts should contain business/MCP fields such as:

```text
Customer reference
Item reference
qty
query
candidate
approval token/handle
valid_till
business fields
```

They should **not** contain client-specific fields such as:

```text
librechat_user_id
conversation_id
LibreChat message ID
LibreChat assistant ID
LibreChat UI selection state
OpenAI tool-call ID
GPT/model name
client-specific role/run_as fields
HTTP auth header
Frappe user supplied by the model
```

### Inspect specifically

```text
Customer contracts
Item contracts
Quotation contracts
Sales Order contracts if typed
generic resolution contracts
error/output contracts
side-effect metadata
```

Report any generic `Any`, `dict[str, Any]`, or `list[dict[str, Any]]` still exposed publicly and state whether each use is justified.

---

# 7. Actual `tools/list` / Generated Schema Audit

Do not rely only on Python type annotations.

Inspect what an MCP client **actually receives**.

Use the safest available local method to inspect MCP `tools/list`, preferably using the current server in a non-writing mode.

At minimum verify several representative tools:

```text
search_customers
resolve_customer
search_items
resolve_item
prepare_quotation
confirm_quotation
prepare_sales_order
confirm_sales_order
```

Use actual registered names if they differ.

## Verify

The generated schema:

```text
is valid MCP-visible schema
does not mention LibreChat
does not expose request identity
does not expose auth headers
contains the typed nested structures from 07A
contains the generic ambiguity contracts from 07B where supported
is usable independent of the LibreChat UI
```

If output schemas are supported by the installed SDK, inspect them too.

If the SDK does not expose output schemas through `tools/list`, report that exact limitation separately.

---

# 8. Tool Registration Audit

Inspect how tools are registered.

Answer:

```text
Is there one shared MCP tool registry/server?
Do stdio and streamable-http expose the same business tools?
Are tool definitions duplicated separately for LibreChat?
Does HTTP create a different business-tool implementation?
Does stdio use the same wrappers/services?
```

Preferred:

```text
one MCP server/tool registry
        ↓
stdio transport
or
streamable-http transport
```

Problematic:

```text
LibreChat tools implementation
+
separate generic MCP tools implementation
```

unless there is a strong justified reason.

---

# 9. Transport Audit

Inspect transport-specific code.

Determine whether:

```text
stdio
streamable-http
```

are transport choices around the same core server.

Report any business logic embedded directly into the HTTP transport.

HTTP transport may reasonably handle:

```text
Host protection
Bearer authentication
request lifecycle
request-scoped identity extraction
headers
Frappe context setup/cleanup
```

It should not implement:

```text
Quotation business rules
Item matching rules
Customer creation rules
Sales Order business logic
tool input shape conversion specific to LibreChat
```

---

# 10. Identity Architecture Audit

This is especially important.

Inspect the current identity modes and request-scoped identity flow.

Answer:

1. Is LibreChat identity isolated from generic MCP business logic?
2. Does the server retain a non-LibreChat path such as service/stdio identity where intended?
3. Are headers read only in the HTTP/request adapter?
4. Is authenticated Frappe identity established before the business service call?
5. Do domain services know that the caller was LibreChat?
6. Can another future client provide identity through another adapter without rewriting Customer/Item/Quotation/Sales Order services?

## Public schema safety

Confirm these are **not model-visible tool arguments**:

```text
frappe_user
librechat_user_id
authorization
bearer secret
role
run_as
session cookie
request headers
```

---

# 11. Service Layer Audit

Inspect domain services, especially:

```text
Customer
Item
Quotation
Sales Order
generic resolver/link resolver
```

Search for LibreChat/client-specific imports and terminology.

For each service answer:

```text
Does it accept domain/business data?
Does it receive runtime identity indirectly through Frappe context?
Does it import LibreChat-specific code?
Does it inspect HTTP headers?
Does it know transport type?
Does it format output specifically for LibreChat UI?
```

Target:

```text
service layer = client unaware
```

Any client-specific service dependency is a high-priority finding.

---

# 12. 07B Resolver / Ambiguity Audit

Verify Task 07B is also client-agnostic.

The resolver should expose semantic states:

```text
resolved
ambiguous
not_found
error
```

and structured candidates.

It must not rely on:

```text
LibreChat radio buttons
LibreChat component IDs
LibreChat conversation state
OpenAI-specific tool-call state
a particular frontend rendering
```

A generic MCP client should be able to:

```text
receive ambiguous candidates
present them however it wants
submit/revalidate an explicit selection
continue
```

Report exactly how this currently works.

---

# 13. Error Contract Audit

Inspect error structures.

Verify errors are domain/MCP-safe and not client-specific.

Good concepts:

```text
status
code
message
reference
retryable
```

Check whether error payloads contain:

```text
LibreChat-specific instructions
UI markup
HTTP-only implementation details
stack traces
filesystem paths
auth secrets
session IDs
```

Report any violations.

---

# 14. Approval Layer Precheck

Do **not** implement Task 07C.

Only inspect the current approval layer enough to answer:

```text
Is approval state/domain logic currently generic?
Does it contain LibreChat assumptions?
Would adding a future trusted approval adapter be possible without rewriting prepare/confirm domain services?
```

This audit should identify what Task 07C must preserve.

Do not redesign approval in this task.

---

# 15. Tests Audit

Inspect current tests from Task 07A and 07B.

Determine whether tests validate the generic MCP behavior or only LibreChat behavior.

Good:

```text
typed schema tests
tools/list tests
resolver state tests
service tests
identity isolation tests
stdio regression tests
HTTP regression tests
```

Potential problem:

```text
core contract tests require LibreChat-specific fixtures for no architectural reason
```

Run safe existing relevant tests where practical.

Do not create ERPNext business records.

Report commands and results.

---

# 16. Documentation Audit

Inspect:

```text
README.md
MCP tool contract architecture docs
docs/TOOLS.md
identity/HTTP docs
AGENTS.md
```

Check wording carefully.

## README should ideally communicate

```text
mcp_erpnext is an ERPNext MCP server
LibreChat is one supported HTTP client/integration
stdio remains usable for local/generic MCP clients where configured
business tools are client-independent
```

Problematic wording:

```text
mcp_erpnext exists only for LibreChat
all MCP contracts described as LibreChat contracts
tool schemas documented as LibreChat payload formats
```

Report outdated or misleading documentation separately from runtime coupling.

Do not edit it.

---

# 17. Tool Catalog Scalability Audit

Check Task 07A tool documentation architecture.

Answer:

```text
Is README manually listing full schemas for every tool?
Is docs/TOOLS.md used as the detailed catalog?
Is tools/list the authoritative machine-readable schema?
Is docs/TOOLS.md generated/checked from real contracts where implemented?
Will adding 100 tools require manually duplicating 100 full schemas in README?
```

Desired:

```text
README       -> overview/capabilities
docs/TOOLS   -> detailed human catalog
tools/list   -> machine-readable source of truth
```

---

# 18. Dependency Direction Audit

Identify the real dependency direction.

Desired:

```text
contracts
   ↓
wrappers
   ↓
services
   ↓
Frappe/ERPNext
```

with:

```text
HTTP/LibreChat adapter
        ↓
runtime identity/context
        ↓
same wrappers/services
```

Flag inversion such as:

```text
services import LibreChat adapter
contracts import HTTP transport
resolver imports LibreChat code
core MCP server imports UI models unnecessarily
```

Provide actual import/file evidence.

---

# 19. Client Replacement Thought Experiment

Based only on inspected source, perform this concrete architecture test:

## Scenario

Tomorrow LibreChat is removed.

A new MCP client connects through:

```text
stdio
```

or a future compatible authenticated transport adapter.

Answer exactly:

### What can remain unchanged?

List files/components such as:

```text
contracts
tool definitions
services
resolvers
business validation
ERPNext permission behavior
tool schemas
tests
```

only if source evidence supports it.

### What must be replaced/configured?

Expected candidates:

```text
LibreChat user mapping adapter
LibreChat-specific headers
LibreChat deployment docs
client-specific approval adapter in future
```

### What unexpectedly breaks?

List any core dependency that proves coupling.

This section is mandatory.

---

# 20. Portability Matrix

Produce a matrix based on actual source:

| Component | LibreChat | MCP Inspector / stdio | VS Code/Codex MCP | Future MCP client | Client-specific? |
|---|---|---|---|---|---|
| Tool contracts | ? | ? | ? | ? | ? |
| Domain services | ? | ? | ? | ? | ? |
| Resolver contracts | ? | ? | ? | ? | ? |
| stdio transport | N/A/? | ? | ? | ? | ? |
| HTTP transport | ? | N/A/? | ? | ? | ? |
| Identity adapter | ? | ? | ? | ? | Expected |
| Approval adapter | ? | ? | ? | ? | To be designed |
| ERPNext permissions | ? | ? | ? | ? | No |

Do not fill from assumptions.

Use evidence.

---

# 21. Finding Severity

Classify every architecture issue:

```text
P0 — security/correctness blocker
P1 — core client-coupling; fix before 07C
P2 — minor coupling/maintainability issue; focused cleanup recommended
P3 — docs/test wording only; runtime architecture remains generic
INFO — acceptable client-specific adapter behavior
```

---

# 22. Final Verdict

Return exactly one primary verdict:

## A — FULLY CLIENT-AGNOSTIC

Use only if:

```text
core public MCP contracts are generic
domain services are client-unaware
07B resolver behavior is generic
stdio/HTTP share the same core tool layer
LibreChat identity is isolated in adapter/runtime code
another MCP client can reuse the core without redesign
no P0/P1 client-coupling finding exists
```

Result:

```text
PROCEED TO TASK 07C
```

---

## B — MOSTLY CLIENT-AGNOSTIC, SMALL CLEANUP REQUIRED

Use if:

```text
core architecture is correct
but a few P2 or limited P1 coupling issues should be corrected before freezing
```

Result:

```text
DO NOT IMPLEMENT FIXES
REPORT A FOCUSED CLEANUP SCOPE
WAIT FOR APPROVAL
```

---

## C — LIBRECHAT-COUPLED CORE

Use if:

```text
contracts/services/resolvers/business tools fundamentally depend on LibreChat
or another client would require rewriting the core MCP layer
```

Result:

```text
DO NOT PROCEED TO 07C
REPORT ARCHITECTURE CORRECTION REQUIRED
```

---

# 23. Required Evidence Standard

Every non-trivial finding must cite actual repository evidence.

Use:

```text
file path
class/function/tool name
relevant behavior
short code excerpt only where useful
```

Prefer line numbers if your environment provides reliable line numbers.

Do not base the verdict merely on:

```text
task documents
comments
README claims
intended architecture
```

Runtime/source implementation is authoritative.

---

# 24. Required Completion Report Format

Return the report in this exact order.

## 1. Executive Verdict

```text
Verdict: A / B / C
Proceed to 07C: YES / NO
One-paragraph reason
```

## 2. Repository Structure Inspected

List exact relevant files/directories found.

## 3. Installed Runtime / SDK Facts

Report:

```text
Python version if relevant
MCP SDK version
Pydantic version
Frappe/ERPNext version if directly available
configured transports discovered
identity modes discovered
```

## 4. MCP Public Contract Findings

Input/output contract evidence.

## 5. Actual tools/list Findings

Report actual generated schema observations.

## 6. Tool Registry / Transport Findings

Shared registry vs duplicated client-specific implementation.

## 7. Identity Boundary Findings

Exact LibreChat-specific boundary.

## 8. Service Layer Findings

Customer, Item, Quotation, Sales Order.

## 9. Resolver / 07B Findings

Client independence of ambiguity/selection handling.

## 10. Approval Precheck Findings

Inspection only.

## 11. Repository-Wide LibreChat Reference Classification

Summarize all meaningful references by:

```text
acceptable adapter
acceptable docs
test-only
questionable
core violation
```

## 12. Documentation / README Findings

Especially whether LibreChat is described as a client vs the core architecture.

## 13. Tool Catalog Scalability Findings

README vs docs/TOOLS.md vs tools/list.

## 14. Tests Run

For each:

```text
command
result
pass/fail
whether any write was possible
```

## 15. Client Replacement Thought Experiment

```text
Remove LibreChat tomorrow:
UNCHANGED:
...

REPLACE/CONFIGURE:
...

BREAKS:
...
```

## 16. Portability Matrix

Fill the matrix requested above.

## 17. Findings by Severity

```text
P0:
P1:
P2:
P3:
INFO:
```

Use `None` where appropriate.

## 18. Exact Recommendation

If A:

```text
Proceed to Task 07C unchanged.
```

If B/C:

Describe the **smallest focused correction scope**, but do not implement it.

Include:

```text
files likely involved
what boundary must change
what must remain unchanged
acceptance criteria for the correction
```

## 19. Confirmation

Explicitly confirm:

```text
No repository files were modified.
No Frappe/ERPNext business documents were created.
No LibreChat changes were made.
No Task 07C approval implementation was started.
```

---

# 25. Acceptance Criteria For This Audit

The audit is complete only when:

```text
[ ] actual source was inspected
[ ] repository-wide LibreChat coupling search was performed
[ ] public input/output contracts were inspected
[ ] actual MCP tools/list schema was inspected where locally possible
[ ] shared tool registry/transport architecture was verified
[ ] runtime identity boundary was verified
[ ] Customer/Item/Quotation/Sales Order services were inspected
[ ] 07B resolver behavior was inspected
[ ] approval layer was inspected only as a precheck
[ ] tests/docs were inspected
[ ] LibreChat-removal thought experiment was completed
[ ] portability matrix was completed
[ ] A/B/C verdict was given
[ ] findings contain source evidence
[ ] no code/docs/config were changed
[ ] no ERPNext business records were created
```

---

# 26. Limitations

If any inspection cannot be completed because of:

```text
missing runtime service
missing environment variable
MCP server cannot safely start
Frappe site unavailable
dependency unavailable
```

do not guess.

State:

```text
NOT VERIFIED
```

and explain exactly why.

Separate source-confirmed conclusions from runtime-unverified conclusions.

---

# 27. Exact Next Step

Do not implement any next task.

Return only the audit report.

The report will be reviewed externally.

Possible next action after review:

```text
Verdict A
    -> Task 07C

Verdict B
    -> focused client-decoupling cleanup task
    -> re-audit
    -> Task 07C

Verdict C
    -> architecture correction task
    -> re-audit
    -> Task 07C
```
