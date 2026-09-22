# 02 — MCP-Level Tool Routing, Description & Server Instruction Governance V1 — Implementation Task

## Series

`mcp_tool_governance`

This is Task **02** in the MCP-wide governance series.

Prerequisite completed:

- `01_MCP_LEVEL_PROTOCOL_METADATA_FOUNDATION_V1_IMPLEMENTATION_TASK.md`
- `01_MCP_LEVEL_PROTOCOL_METADATA_FOUNDATION_V1_IMPLEMENTATION_REPORT.md`

Task 01 established governed standard MCP annotations across the complete public tool surface. Task 02 must build on that foundation without undoing or bypassing it.

---

# 1. Scope

This is a **whole-MCP / all-profile / all-public-tool** task.

It is **not** limited to:

- Quotation
- Customer
- Item
- Supplier
- Sales
- one observed ChatGPT Desktop prompt
- one resolver/search/query problem

The user-visible `resolve -> search -> query` over-calling seen during Quotation creation is only one example of a broader MCP tool-routing and tool-purpose clarity problem.

The implementation must govern the complete public MCP surface across:

- Sales profile
- Purchase profile
- Accounts profile
- all currently exposed public tools
- all operation families represented by the current `ToolContract` registry

Current post-Task-01 expected coverage baseline from the accepted report:

- Sales: 66 tools
- Purchase: 21 tools
- Accounts: 19 tools
- Unique public tools / `TOOL_CONTRACTS`: 85 / 85

Before editing, verify these counts against the actual post-Task-01 source rather than treating the numbers above as immutable constants.

---

# 2. Objective

Create a coherent MCP-wide routing and tool-description governance layer so an LLM can reliably understand:

1. what each tool family is for;
2. when a tool should be preferred;
3. when a similar tool should **not** be called;
4. what result states are terminal;
5. when a follow-up tool call is appropriate;
6. how prepare/confirm workflows should be sequenced;
7. how exact-reference retrieval differs from natural-language resolution, discovery search, structured query, and aggregation;
8. how the same rules apply consistently across Sales, Purchase, and Accounts.

The implementation must reduce unnecessary tool chains such as:

```text
resolve_customer
-> search_customers
-> query_customers
```

when the resolver already produced a terminal result.

It must also prevent description drift as new tools are added later.

This task is about **model guidance and routing semantics**, not MCP host approval configuration.

---

# 3. Inputs / Source of Truth

Before changing code, inspect the actual post-Task-01 implementation, especially:

- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/audit.py`
- `mcp_erpnext/contracts/__init__.py`
- `mcp_erpnext/tools/registration.py`
- `mcp_erpnext/tools/__init__.py`
- `mcp_erpnext/mcp_server.py`
- all profile modules
- all public tool registration modules
- current `ToolContract` fields
- current tool descriptions
- current MCP server `instructions`
- generated `docs/TOOLS.md`
- `scripts/generate_tool_catalog.py`
- current tool-registration and contract tests
- Task 01 implementation/report

Do not assume the pre-Task-01 source shape if Task 01 changed registration structure.

Reuse the existing governed registration/contract architecture where sound.

---

# 4. Allowed Changes

Allowed:

- MCP server `instructions`
- public tool descriptions
- contract-level routing/purpose metadata if required
- centralized helpers that derive/validate routing guidance
- registration helpers where needed to inject governed descriptions
- documentation generator
- tool catalog documentation
- tests for descriptions, routing metadata, server instructions, and governance
- architecture documentation directly related to tool-routing semantics

Not allowed in this task:

- changing ERPNext business logic
- changing resolver ranking algorithms
- changing permission rules
- changing public tool names
- changing typed tool input/output schemas unless an existing description is factually inconsistent and a schema defect is separately reported
- changing profile membership
- changing approval-token mechanics
- changing Task-01 MCP annotation semantics
- changing host/client `config.toml`
- changing MCP SDK major version
- adding/removing capabilities merely to improve routing
- introducing a Skill as a substitute for correct server metadata
- hiding tools as the first solution to unclear descriptions

If a true business-logic or API-contract defect is found, document it separately rather than silently mixing it into this task.

---

# 5. Core Design Requirement — Global Tool-Role Taxonomy

Establish and document a single MCP-wide semantic taxonomy for tool families.

At minimum cover the following families wherever they exist:

```text
resolve
select resolved candidate
get
search
query
aggregate
prepare
confirm
create/convert preparation
lifecycle preparation/confirmation
render
email preparation/confirmation
read/reference helpers
```

The exact implementation may use existing `operation` fields or add a small centrally governed role/purpose layer.

Do not create unrelated profile-specific routing policy tables if the rule is generic across the MCP.

Profile/domain-specific exceptions are allowed only when the underlying semantics genuinely differ.

---

# 6. Canonical Routing Semantics

The final implementation must encode semantics equivalent to the following.

## 6.1 `resolve_*`

Purpose:

Use for a user-supplied natural-language business reference when a workflow needs one specific permitted entity/document.

Examples:

- customer name/reference
- item name/reference
- supplier reference
- other resolvable master/document references represented in the current MCP

Required behavior guidance:

- `resolve_*` is the **primary lookup** for natural-language references inside transactional workflows.
- Call it once for the same unresolved reference unless new user information materially changes the reference.
- A successful unique resolution is terminal for lookup.
- Do not follow a successful resolution with `search_*` or `query_*` merely to verify it.
- An ambiguity result must use its returned candidates/selection workflow rather than initiating unrelated duplicate discovery.
- A terminal `not_found` must not be bypassed by calling `query_*` to invent or silently choose a substitute.
- If the user explicitly asks for alternatives after a not-found state, then discovery/search may be appropriate.

Do not alter the actual resolver result-state implementation in this task.

## 6.2 `select_resolved_candidate`

Purpose:

Continue an existing ambiguity-resolution flow using a candidate/reference already returned by the resolver.

Guidance:

- use only after an ambiguity result;
- do not restart search/query if the candidate set is already sufficient;
- do not use as a general get/search tool.

## 6.3 `get_*`

Purpose:

Retrieve one known entity/document when the exact stable reference/name is already known.

Guidance:

- prefer over resolver/search/query when the canonical document name/reference is already available;
- do not use to perform fuzzy discovery;
- do not use query merely to re-fetch one exact document if `get_*` already provides the required view.

## 6.4 `search_*`

Purpose:

Human-oriented discovery/browsing of candidate records when the user wants to find, browse, compare, or inspect possible matches.

Guidance:

- use when candidate discovery is the user’s intent;
- use after resolver `not_found` only when the user asks for alternatives/discovery;
- do not use as routine verification after `resolve_*`;
- do not use when exact structured filtering is the real request and `query_*` is designed for it.

## 6.5 `query_*`

Purpose:

Structured filtering/projection/sorting/pagination over records.

Guidance:

- use for explicit structured list/report/filter requests;
- do not use as a fuzzy resolver fallback;
- do not call after a successful resolver merely to verify identity;
- do not use for aggregate questions where a dedicated aggregate tool exists.

## 6.6 `aggregate_*`

Purpose:

Server-side aggregate/count/sum/group-type questions supported by the tool contract.

Guidance:

- prefer aggregate tools for aggregate questions instead of retrieving many rows through `query_*` and aggregating in the model;
- do not use for document retrieval or fuzzy discovery.

## 6.7 `prepare_*`

Purpose:

Validate, normalize, and prepare a consequential operation and return the preview/prepared state/token required by the existing approval architecture.

Guidance:

- use after required references/inputs are resolved;
- do not call `confirm_*` before a successful corresponding prepare flow where the existing architecture requires it;
- treat returned preview/prepared state as the authoritative next-step context;
- do not repeatedly prepare identical payloads without a reason;
- preserve current non-read-only MCP annotation semantics from Task 01.

## 6.8 `confirm_*`

Purpose:

Execute the already prepared consequential operation using the existing approval/prepared-operation contract.

Guidance:

- never use as a discovery/read tool;
- only call after the corresponding prepare state is valid;
- do not bypass preview/approval rules;
- preserve current approval/security behavior.

## 6.9 Lifecycle tools

For update/child-add/submit/cancel/delete:

Clearly distinguish:

```text
prepare lifecycle action
-> preview / prepared state
-> confirm lifecycle action
```

The description must make the sequence and consequences obvious.

Do not change lifecycle business rules.

## 6.10 Conversion tools

For conversion workflows such as transaction-to-transaction conversions:

- make source-document requirements explicit;
- distinguish prepare vs confirm;
- do not imply that conversion is a generic create tool;
- do not add hidden conversion behavior.

## 6.11 Render/PDF tools

Clearly state:

- whether the tool is read/render only;
- what exact reference is required;
- whether it returns content/artifact metadata;
- that it should not be used to discover the document.

## 6.12 Email tools

Clearly distinguish:

```text
prepare email
-> preview/attachment/recipient preparation

confirm email
-> queue/send external communication
```

Keep Task-01 `openWorldHint` semantics intact.

---

# 7. MCP Server Instructions

The current server-level `instructions` must be upgraded from narrow response-precision guidance into a concise MCP-wide operating policy.

Do not turn server instructions into a huge duplicated manual.

The server instructions should contain only cross-tool rules that materially improve routing.

At minimum include:

1. exact known reference -> `get_*`;
2. natural-language transactional reference -> `resolve_*`;
3. explicit browse/discovery -> `search_*`;
4. structured filtering/listing -> `query_*`;
5. aggregate question -> `aggregate_*`;
6. successful resolver result is terminal for lookup;
7. resolver ambiguity -> use returned candidates/selection flow;
8. resolver not-found -> do not silently substitute via query; ask or search only when user requests alternatives;
9. consequential operations follow `prepare -> preview/approval -> confirm`;
10. do not duplicate semantically equivalent calls merely for verification;
11. reuse identifiers/results already obtained earlier in the same workflow;
12. domain/profile boundaries must be respected.

Retain the useful existing response-precision instruction if it remains compatible.

Server instructions must remain client-agnostic. Do not mention ChatGPT-only UI controls.

---

# 8. Tool Description Standard

Create a consistent description style for every public tool.

Each description should answer, as compactly as possible:

1. **What does this tool do?**
2. **When should the model use it?**
3. **When should it not use it, especially versus similar tools?**
4. **What important prerequisite/result-state rule matters?**

Do not write huge descriptions that waste context.

Prefer compact, operational wording.

Example pattern only:

```text
PRIMARY lookup for a natural-language Customer reference in transactional
workflows. Returns resolved, ambiguous, or not-found state. A resolved
result is terminal; do not follow it with search/query merely to verify.
```

Do not blindly copy that wording to unrelated tools.

---

# 9. Centralized Governance

Do not rely on manual review of 85 descriptions forever.

After inspecting current architecture, implement the lightest central governance that prevents drift.

Acceptable approaches include:

- contract-level purpose/routing metadata;
- operation-family policy helpers;
- governed description builders for repetitive families;
- audit functions that require required routing metadata;
- tests that validate descriptions against family rules.

Do **not** over-engineer a full DSL unless current code actually benefits from it.

The implementation should preserve explicit descriptions where domain-specific wording matters while centralizing generic semantics where practical.

---

# 10. Resolver Terminal-State Governance

This is a critical acceptance area.

For each resolver family in the current public surface:

- inspect actual result states;
- document which states are terminal;
- ensure tool descriptions and server instructions use the real state names;
- do not invent generic state names if implementations differ.

The model guidance must ensure that:

```text
resolved
```

does not lead to redundant search/query verification.

For ambiguity:

```text
ambiguous
-> use supplied candidates / selection mechanism
```

not:

```text
ambiguous
-> unrelated search
-> unrelated query
```

For not found:

```text
not_found
-> ask user / explicit alternative-discovery path
```

not silent substitution.

---

# 11. Cross-Profile Consistency

Audit the same operation family across Sales, Purchase, and Accounts.

If two tools have the same semantic role, their descriptions should follow the same routing principles.

Examples:

- customer/supplier/item/entity resolution
- sales/purchase/account document reads
- query/list tools
- aggregate tools
- prepare/confirm patterns
- Payment Entry/accounting prepares/confirms

Do not let Sales receive rich routing descriptions while Purchase/Accounts remain ambiguous.

This task is complete only when all profiles are governed.

---

# 12. Tool Catalog / Documentation

Inspect `scripts/generate_tool_catalog.py`.

If the tool catalog is generated from the contract registry, extend the source/generator so documentation exposes useful routing metadata or normalized descriptions without creating another source of truth.

Update documentation to include:

- tool-role taxonomy;
- routing precedence;
- terminal resolver-state behavior;
- prepare/confirm sequencing;
- relationship between server instructions, tool descriptions, standard annotations, and business approval.

Do not manually edit generated catalog sections without updating the generator.

---

# 13. Tests Required

## 13.1 Server instruction test

Verify the actual initialized server publishes the expected cross-tool instruction policy.

Do not only test a string constant that is never wired into the server.

## 13.2 Complete public-tool description coverage

For every public tool returned by each profile:

- description is non-empty;
- description is the governed/current description;
- no tool silently falls back to an unhelpful Python function docstring if governance requires an explicit description.

## 13.3 Family semantics tests

Add representative tests for at least:

- resolve
- select candidate
- get
- search
- query
- aggregate
- prepare
- confirm
- lifecycle
- conversion
- render
- email

Tests should verify key routing language/metadata semantically, not brittle full-paragraph equality unless generated text is deterministic by design.

## 13.4 Resolver terminal-state tests

Representative resolver descriptions/server policy must establish:

- resolved is terminal;
- ambiguity uses returned candidates/selection;
- not-found does not silently trigger query substitution.

Cover at least Customer, Item, and Supplier where those families exist.

## 13.5 Read-vs-discovery-vs-reporting distinction

Verify representative descriptions clearly distinguish:

```text
get
resolve
search
query
aggregate
```

without overlapping language that makes all five look interchangeable.

## 13.6 Prepare/confirm sequencing

Across at least one representative tool from each profile, verify prepare/confirm descriptions clearly encode the existing sequence.

## 13.7 Annotation regression

Task 01 must remain intact.

Re-run annotation tests and verify description/routing work did not remove or mutate:

- readOnlyHint
- destructiveHint
- idempotentHint
- openWorldHint
- custom `meta`

## 13.8 Profile inventory regression

Existing profile tool counts/names must remain unchanged.

## 13.9 Full focused suite

Run at minimum:

- tool annotation tests
- tool contract tests
- tool registration tests
- profile tests
- new routing/description tests
- resolver tests affected by descriptions/registration
- approval tests affected by server initialization

## 13.10 Broader discovery

Run the broader project test discovery if supported.

If the same pre-existing failures reported by Task 01 remain:

- document exact failures;
- confirm whether the failure set is unchanged;
- do not silently alter unrelated business logic to make them disappear.

If new failures appear, they must be resolved before Task 02 is considered complete.

---

# 14. Behavioral Validation Scenarios

In addition to unit tests, add a documented validation matrix using representative user intents.

This is not a requirement to run an external LLM in the automated test suite.

The matrix must show expected first-choice routing.

Examples:

### Transaction with natural-language reference

```text
Create a quotation for client Vertex ...
```

Expected:

```text
resolve_customer
```

not initial `query_customers`.

### Exact known document

```text
Get Sales Order SAL-ORD-2026-00014
```

Expected:

```text
get_sales_order
```

### Browse

```text
Find customers matching Vertex
```

Expected:

```text
search_customers
```

### Structured listing

```text
List customers in territory X sorted by creation
```

Expected:

```text
query_customers
```

### Aggregate

```text
How many sales orders are overdue?
```

Expected:

```text
aggregate_*` where the current tool surface supports that exact aggregate
```

otherwise use the correct structured read path without inventing a nonexistent tool.

### Resolver not found

```text
Create quotation for item "domain"
```

If resolver returns not found:

Expected:

- report not found / ask user;
- optionally offer explicit search for alternatives;
- do not silently select a different Item through `query_items`.

Use actual current tool names/results in the final validation matrix.

---

# 15. Acceptance Criteria

Task 02 is accepted only if all are true:

1. The complete current public tool surface across all profiles is covered.
2. MCP server instructions contain concise global routing policy.
3. Existing useful response-precision guidance is preserved or intentionally superseded.
4. Every public tool has an intentional, non-empty description.
5. Tool descriptions distinguish purpose and nearest alternatives.
6. `resolve`, `get`, `search`, `query`, and `aggregate` have globally consistent semantics.
7. Resolver terminal states are described using actual implementation behavior.
8. Successful resolution is clearly terminal for lookup.
9. Ambiguity routes through candidate selection rather than redundant discovery.
10. Not-found does not authorize silent substitution via query.
11. Prepare/confirm sequencing is clear across Sales, Purchase, and Accounts.
12. Lifecycle, conversion, render, and email tools have clear semantics.
13. No ERPNext business logic changed.
14. No public tool names changed.
15. No profile membership/tool inventory changed.
16. Task-01 MCP annotations remain intact.
17. Existing custom metadata remains intact.
18. Routing governance is centralized enough to prevent obvious future drift.
19. New routing/description tests pass.
20. Relevant existing focused tests pass.
21. Broader test run introduces no new failure beyond any explicitly proven pre-existing baseline.
22. Documentation/catalog generation remains deterministic and passes its check mode where supported.

---

# 16. Expected Result

After Task 02, an MCP-capable model should receive a much clearer tool surface.

Expected conceptual routing:

```text
known exact reference
    -> get

natural-language single-reference workflow
    -> resolve
        -> resolved: reuse result
        -> ambiguous: candidate selection
        -> not_found: ask / explicit alternative search

browse candidates
    -> search

structured list/filter
    -> query

aggregate question
    -> aggregate

consequential mutation
    -> prepare
    -> preview / approval
    -> confirm
```

This should apply consistently across all domains/profiles.

The goal is to reduce unnecessary calls through better server metadata and instructions.

It does **not** create a hard protocol-level prohibition against a client calling another valid tool.

---

# 17. Limitations

MCP server instructions and descriptions guide the model; they do not constitute a deterministic client-side router.

Therefore this task must not claim that the MCP server can absolutely prevent:

```text
resolve -> search -> query
```

if a client independently chooses to call those valid tools.

If, after Task 02 and real-client testing, over-calling remains material, stronger exposure/routing controls can be evaluated separately.

Do not add that future work automatically to this series unless the Task-03 validation proves it necessary.

---

# 18. Implementation Report Required

After implementation create:

`02_MCP_LEVEL_TOOL_ROUTING_DESCRIPTION_SERVER_INSTRUCTIONS_V1_IMPLEMENTATION_REPORT.md`

The report must include:

- summary
- post-Task-01 source inspected
- files changed
- final tool-role taxonomy
- final routing precedence
- final server instructions
- description governance architecture
- resolver state semantics actually found
- all profile/tool coverage counts
- representative before/after descriptions
- validation matrix
- tests added
- exact test commands
- exact results
- broader discovery result
- confirmation that Task-01 annotations remain intact
- confirmation that business logic did not change
- confirmation that public tool names/profile inventories did not change
- limitations/deferred findings

Do not start Task 03 until this report is reviewed and accepted.

---

# 19. Exact Next Task After Acceptance

After Task 02 implementation report is reviewed and accepted:

**03 — MCP Host Approval Policy & End-to-End Validation V1**

That task will:

- use the already-correct standard MCP annotations from Task 01;
- use the already-correct routing/description metadata from Task 02;
- configure and validate host/client approval behavior;
- evaluate `default_tools_approval_mode = "writes"`;
- evaluate narrowly scoped per-tool approval overrides only where justified;
- validate representative Sales, Purchase, and Accounts flows through the actual connected MCP client;
- keep server-side preview/confirm business approval separate from host tool-call approval.

MCP Python SDK v1 -> v2 migration remains postponed and is not part of Task 02 or Task 03 unless a concrete compatibility requirement appears.

# 20. Required Report Output Path

After completing this task, create the implementation report in the same MCP governance task folder:

`docs/tasks/mcp_tool_governance/02_MCP_LEVEL_TOOL_ROUTING_DESCRIPTION_SERVER_INSTRUCTIONS_V1_IMPLEMENTATION_REPORT.md`

Do not create the report under:

- `docs/inspect/`
- repository root
- any temporary/audit folder
- any other documentation folder

The implementation report must be committed alongside the corresponding task file in:

`docs/tasks/mcp_tool_governance/`

Expected pair:

`docs/tasks/mcp_tool_governance/02_MCP_LEVEL_TOOL_ROUTING_DESCRIPTION_SERVER_INSTRUCTIONS_V1_IMPLEMENTATION_TASK.md`

`docs/tasks/mcp_tool_governance/02_MCP_LEVEL_TOOL_ROUTING_DESCRIPTION_SERVER_INSTRUCTIONS_V1_IMPLEMENTATION_REPORT.md`