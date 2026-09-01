# Task 08A — MCP Conversational Interaction Contract Foundation

## Task Type

Architecture contract + focused implementation.

This task begins after:

- 07A — MCP Tool Contract Foundation: DONE
- 07B — Generic Ambiguous Entity Selection Enforcement: DONE
- 07C — Generic Explicit Approval Safety Core: DONE
- 07C Precheck — Client-Agnostic Audit: Verdict A

This is not a LibreChat-specific task.

This task freezes the semantic contract between a Chat/Agent/Orchestrator and `mcp_erpnext` for current and future conversational ERPNext workflows.

## 1. Why This Task Exists

The product's primary interaction style is conversational/free-form chat. Different frontends may be used over time: LibreChat, custom web chat, WhatsApp-style chat, VS Code/Codex chat, a LangGraph-based agent, or another future chat client.

Their UI presentation may differ, but the ERPNext MCP server should expose the same semantic interaction requirements.

Example:

- MCP does not care whether the user typed `haan bana do`, `yes create it`, `please proceed`, or clicked an Approve button.
- The AI/Agent interprets the user's language/UI action.
- MCP only exposes that APPROVAL is required.

Similarly, `second wala`, `API Integration wala`, a dropdown click, or a WhatsApp list selection may all become the same semantic action: SELECT.

The server must therefore standardize semantic interaction requirements, not natural-language phrases or frontend components.

## 2. Responsibility Split

### MCP server owns

- ERPNext tool contracts
- business validation
- entity resolution
- candidate validation
- missing-input requirements
- prepare/preview behavior
- permission enforcement
- approval-token integrity
- final write safety
- semantic interaction requirements

### AI / Agent / Orchestrator owns

- natural-language understanding
- `haan bana do` -> APPROVE
- `second wala` -> SELECT
- `qty 5 kar do` -> MODIFY
- conversation history
- workflow/conversation state
- deciding which tool to call next
- asking the user naturally

### Client / UI owns

- display
- chat transport
- buttons/dropdowns if available
- authenticated user session
- sending the actual user message/action

Important: do not move natural-language interpretation into `mcp_erpnext`.

## 3. Important Non-Goal

Do not create a full conversation/workflow engine inside the MCP server in this task.

Do not introduce server-owned:

- LibreChat conversation IDs
- chat transcripts
- assistant message IDs
- LangGraph state
- generic chat memory
- natural-language history
- frontend session state

The future Coordinator Agent will own conversational workflow state.

The MCP server only returns structured semantic guidance about what interaction is required next.

## 4. Core Contract To Freeze

Introduce shared interaction types.

Exact Python naming may vary after repository inspection, but the conceptual contract must be equivalent to:

```python
InteractionKind:
    SELECTION
    INPUT
    APPROVAL

InteractionAction:
    SELECT
    PROVIDE_INPUT
    MODIFY
    APPROVE
    REJECT
    CANCEL
```

Do not add actions merely for theoretical completeness.

Add only actions justified by current/future ERPNext chat workflows.

## 5. Interaction Directive

Create one reusable typed contract similar to:

```python
class InteractionDirective(BaseModel):
    required: bool
    kind: InteractionKind | None
    allowed_actions: list[InteractionAction]
    reason_code: str | None
    instructions: str | None
```

Exact fields may be refined after inspecting current contracts.

Rules:

- `required = false`: no user interaction is required by MCP before normal continuation.
- `required = true`: Agent/client must obtain a user continuation before taking the protected next step.

`instructions` must be semantic/client-neutral.

Good examples:

- `Select exactly one Item candidate.`
- `Provide the missing valid_till field.`
- `Review the prepared Quotation before final creation.`

Bad examples:

- `Click the green LibreChat button.`
- `Type YES.`
- `Reply 'haan bana do'.`
- `Use component id quotation-approve.`

## 6. Do Not Duplicate Business Payloads

The interaction directive should use the existing typed result payload rather than duplicate it.

Example resolver result:

```json
{
  "status": "ambiguous",
  "doctype": "Item",
  "query": "Development item",
  "candidates": [],
  "interaction": {
    "required": true,
    "kind": "SELECTION",
    "allowed_actions": ["SELECT", "CANCEL"],
    "reason_code": "AMBIGUOUS_REFERENCE"
  }
}
```

Candidates stay in the normal result.

Do not duplicate candidate arrays, quotation previews, approval tokens, or missing-field values unless the existing architecture requires it.

## 7. Selection Semantics

For an ambiguous resolver result:

- `interaction.required = true`
- `interaction.kind = SELECTION`
- `allowed_actions` includes SELECT

The server must not prescribe how the client presents candidates.

A client may use free-form text, a numbered list, dropdown, radio button, WhatsApp list, or voice-to-text.

The AI/Agent converts the user's response into the existing structured candidate-selection/revalidation tool contract from Task 07B.

Do not create a second resolver system.

## 8. Missing Input Semantics

When a tool cannot continue because required business input is missing:

- `interaction.required = true`
- `interaction.kind = INPUT`
- `allowed_actions` includes PROVIDE_INPUT

If modification of already provided values is valid, MODIFY may also be allowed.

The output must identify missing/required fields using existing typed business contracts where available.

Do not encode natural-language examples as parser rules.

## 9. Approval Semantics

When `prepare_*` successfully produces a preview that requires explicit approval:

- `interaction.required = true`
- `interaction.kind = APPROVAL`
- allowed actions may include APPROVE, REJECT, MODIFY, CANCEL according to the current workflow

Important: `APPROVE` in the interaction contract is a semantic user intention, not automatic permission to write.

The existing Task 07C trusted-approval safety boundary remains authoritative.

A model-generated APPROVE or `{"confirm": true}` must not by itself bypass the trusted approval guard.

## 10. Reject / Cancel Semantics

### REJECT

Meaning: the user has reviewed a prepared/proposed operation and explicitly declines that operation.

A rejected pending approval must not later create the same operation.

### CANCEL

Meaning: the user abandons the current interactive continuation/workflow step.

This is conversational workflow cancellation, not ERPNext document cancellation unless a specific future tool explicitly performs that business action.

## 11. MODIFY Semantics

MODIFY means the user does not approve the exact current prepared payload and wants business input changed.

Example:

```text
Current preview:
qty = 2

User:
haan but qty 5 kar do

Agent:
MODIFY qty=5
```

Required behavior:

- do not approve the old preview
- invalidate/reject the old pending approval as required by existing approval safety
- re-run the appropriate prepare flow with modified structured input
- produce a new preview
- require approval for the new exact payload

Do not implement natural-language modification parsing in MCP.

The future Agent supplies the structured changed values.

## 12. Client-Neutral Rule

The interaction contract must not include fields such as:

- librechat_user_id
- LibreChat conversation id
- OpenAI tool call id
- Gemini response id
- LangGraph node id
- WhatsApp message id
- UI component id
- button id
- frontend route

If a client needs such fields, its adapter/runtime owns them outside the core MCP contract.

## 13. No Hardcoded Natural-Language Approval Vocabulary

Do not implement:

```python
if text.lower() in [
    "yes",
    "haan",
    "han",
    "confirm",
    "bana do",
]:
    ...
```

Do not use regex phrase lists for semantic user intent.

Do not add multilingual approval/rejection dictionaries.

This prohibition applies to APPROVE, REJECT, SELECT, MODIFY, PROVIDE_INPUT, and CANCEL.

That belongs to the AI/Agent layer.

## 14. No LLM Inside MCP

Do not add an LLM dependency to `mcp_erpnext` for interpreting user chat.

Do not call OpenAI, Gemini, Anthropic, a local model, or a LangGraph LLM node from MCP services for interaction classification.

The MCP server should remain deterministic.

## 15. Backward Compatibility

Do not break existing public tool payloads unnecessarily.

Preferred approach:

```text
existing result
+
additive typed interaction field
```

rather than wrapping every existing result inside a completely new envelope.

Before implementation, inspect all current typed and legacy tool contracts.

If adding `interaction` to a specific legacy output would require a breaking refactor, document it and use the smallest compatible approach.

Do not silently change current tool names.

## 16. Current Mandatory Adoption

Demonstrate the foundation on current real workflows.

At minimum cover:

### Resolver ambiguity

`resolve_customer` and `resolve_item` when status is ambiguous must expose SELECTION.

### Quotation prepare

When ready for user approval, expose APPROVAL.

When missing required business information, expose INPUT if the current service already has such a state.

### Quotation terminal/success/error

Do not claim user interaction is required when none is needed.

### Sales Order

Inspect current prepare/confirm behavior.

Adopt the shared interaction directive where it can be done safely without expanding this into a full Sales Order typed-contract migration.

If legacy schema prevents safe adoption, report the exact legacy blocker and keep it as a documented migration item.

## 17. Future Tool Rule

Update project architecture/agent instructions so every future conversational MCP tool must answer:

```text
Can this result require user interaction?
If yes:
    what InteractionKind?
    what allowed InteractionAction values?
```

Examples:

- Supplier ambiguity -> SELECTION
- missing Warehouse -> INPUT / SELECTION
- Sales Invoice preview -> APPROVAL
- Payment Entry preview -> APPROVAL
- missing payment mode -> INPUT
- modified quantity -> MODIFY then reprepare

Future tools must not invent ad-hoc fields such as:

- needs_user_choice
- ask_again
- approval_needed
- please_confirm
- requires_answer

when the shared interaction contract applies.

## 18. Contract Audit Extension

Extend Task 07A's generic contract audit.

The audit should verify:

- shared interaction models exist
- interaction enums are centralized
- tools/results that use interaction semantics use the shared contract
- APPROVAL directives do not weaken CONFIRM_WRITE safety
- no client-specific fields appear in interaction contracts
- no hardcoded natural-language parsing exists in MCP interaction code

Do not require every read-only tool to emit an interaction object if it provides no value.

## 19. Documentation

Create/update a focused architecture document such as:

```text
docs/architecture/MCP_CONVERSATIONAL_INTERACTION_CONTRACT.md
```

It must define:

- responsibility split
- interaction kinds
- interaction actions
- selection semantics
- input semantics
- approval semantics
- reject/cancel semantics
- modify/reprepare semantics
- client-neutral examples
- security boundary
- future-agent integration

Update:

- MCP_TOOL_CONTRACT_STANDARD.md
- docs/TOOLS.md generation/metadata if appropriate
- AGENTS.md / project agent instruction index
- README only if a small architecture link is useful

Do not turn README into a long chat protocol specification.

## 20. Required Agent-Facing Contract

Document the future Agent behavior in semantic terms.

Example:

```text
MCP result:
interaction.kind = SELECTION

Agent:
ask user naturally using candidate data
interpret user's reply
call structured selection/revalidation tool
```

```text
MCP result:
interaction.kind = INPUT

Agent:
ask for required business information
interpret reply into typed field values
call/re-call appropriate tool
```

```text
MCP result:
interaction.kind = APPROVAL

Agent:
show/restate exact preview
interpret user response as APPROVE / REJECT / MODIFY / CANCEL

BUT:
APPROVE still requires the trusted approval mechanism from Task 07C
before CONFIRM_WRITE can succeed.
```

This document becomes a contract consumed later by the Coordinator Agent task.

## 21. Out of Scope

Do not implement:

- Coordinator Agent
- Quotation Agent
- Customer Agent
- Item Agent
- Accounting Agent
- LangGraph graph
- agent routing
- conversation memory
- LLM prompts
- natural-language classification
- tool subset routing
- multi-agent handoff
- LibreChat middleware
- WhatsApp adapter
- trusted client approval adapter

This task prepares the MCP side for them.

## 22. Files / Components Allowed To Change

After inspecting the actual repository, likely equivalents include:

- `mcp_erpnext/contracts/interaction.py`
- `mcp_erpnext/contracts/common.py`
- Customer/Item resolver result contracts
- Quotation contracts
- minimal Sales Order wrapper/contract metadata if safe
- contract registry/audit
- tests for interaction contracts
- `docs/architecture/**`
- `docs/TOOLS.md` generator/metadata
- `AGENTS.md` or equivalent project agent instructions
- `README.md` only for a concise link if necessary

Use the actual repository structure.

Do not create folders only to match these examples.

## 23. Components Not To Change

Do not redesign:

- Frappe permissions
- LibreChat identity mapping
- HTTP bearer auth
- Host validation
- OpenID/OAuth
- Customer matching algorithm
- Item matching algorithm
- Quotation business logic
- Sales Order business logic
- pricing rules
- approval token security
- approval TTL
- approval user/site/action/payload binding
- process-local approval storage
- CONFIRM_WRITE fail-closed behavior

Do not create real ERPNext business documents in automated tests.

## 24. Implementation Steps

1. Inspect current contract models, resolver outputs, Quotation outputs, Sales Order outputs, approval outputs, contract registry, generated `tools/list` schemas, tests, and docs.
2. Add centralized InteractionKind, InteractionAction, and InteractionDirective.
3. Integrate Customer/Item resolver ambiguity with SELECTION.
4. Integrate Quotation result states with the shared directive.
5. Inspect/adopt Sales Order minimally where safe.
6. Extend contract tests/audit.
7. Update architecture/project docs.
8. Run regressions.
9. Stop and report.

## 25. Tests

### A. Shared schema

Verify generated schema for the interaction directive is explicit and client-neutral.

Expected semantic values:

- SELECTION
- INPUT
- APPROVAL
- SELECT
- PROVIDE_INPUT
- MODIFY
- APPROVE
- REJECT
- CANCEL

Use the enum serialization convention selected by the current codebase.

### B. Ambiguous Item

Input equivalent to `Development item`.

Expected:

```text
status = ambiguous
existing structured candidates present

interaction:
    required = true
    kind = SELECTION
    SELECT allowed
```

No automatic candidate selection.

### C. Exact Item

Exact unique item resolution should not require unnecessary user interaction.

### D. Quotation Ready

Valid prepare:

```text
status = ready
preview present
approval token present
```

Expected:

```text
interaction.required = true
interaction.kind = APPROVAL
APPROVE allowed
REJECT/CANCEL behavior documented/supported
MODIFY allowed if current flow supports reprepare
```

### E. Quotation Needs Input

If the current service produces `needs_input`:

```text
interaction.kind = INPUT
PROVIDE_INPUT allowed
```

Missing fields remain structured.

### F. Direct Confirm Safety Regression

Even after adding semantic APPROVAL information, a direct model-style:

```json
{
  "approval_token": "...",
  "confirm": true
}
```

without trusted user approval must still fail with `TRUSTED_APPROVAL_UNAVAILABLE` or the current equivalent.

No write.

### G. No Language Parser

Source audit verifies the new MCP interaction implementation contains no hardcoded phrase lists for approval/rejection/selection/modification.

Natural-language examples may exist in documentation/tests only as explanatory text, not parsing logic.

### H. No Client Fields

Generated/shared interaction schema must not expose client-specific IDs or transport fields.

### I. Existing Regression

Run relevant current tests for:

- Task 07A contracts
- Task 07B entity selection
- Task 07C approval safety
- HTTP identity/transport
- Customer
- Item
- Quotation
- Sales Order

No real ERPNext documents.

## 26. Expected Results

- shared conversational interaction contract exists
- MCP remains deterministic
- MCP remains client-agnostic
- natural-language meaning remains Agent responsibility
- ambiguous resolver results expose SELECTION semantics
- prepared write results expose APPROVAL semantics
- missing input can expose INPUT semantics
- current trusted approval safety remains unchanged
- future tools have one standard instead of ad-hoc interaction flags
- existing relevant regressions pass

## 27. Acceptance Criteria

- [ ] shared InteractionKind exists
- [ ] shared InteractionAction exists
- [ ] shared InteractionDirective exists
- [ ] no hardcoded natural-language parser was added
- [ ] no LLM dependency was added to MCP
- [ ] no LibreChat-specific field exists in interaction contract
- [ ] Customer/Item ambiguity uses SELECTION contract
- [ ] Quotation ready uses APPROVAL contract
- [ ] missing-input state uses INPUT where currently supported
- [ ] existing candidate/preview payloads are not unnecessarily duplicated
- [ ] direct model confirm remains fail-closed
- [ ] contract audit protects future interaction semantics
- [ ] architecture documentation exists
- [ ] project agent instructions reference it
- [ ] existing tests pass
- [ ] no real ERPNext business document was created

## 28. Known Boundary

This task does not make this flow complete yet:

```text
User:
haan bana do

        ↓
future Agent understands APPROVE

        ↓
future trusted adapter proves
this came from the actual user

        ↓
existing Task 07C approval core

        ↓
confirm_*
```

That missing Agent/Trusted Adapter connection is intentional.

This task defines the stable semantic contract it will consume.

## 29. Required Completion Report

After implementation, report:

1. Exact files changed/created.
2. Existing contracts inspected.
3. Final InteractionKind values.
4. Final InteractionAction values.
5. Final InteractionDirective schema.
6. Customer ambiguous result example.
7. Item ambiguous result example.
8. Quotation ready result example.
9. Missing-input result example if supported.
10. Sales Order adoption status and any legacy blocker.
11. Actual generated MCP schemas affected.
12. Contract audit changes.
13. Documentation/project-agent changes.
14. Tests run and exact results.
15. Proof direct `confirm=true` still fails without trusted approval.
16. Proof no hardcoded natural-language parsing was added.
17. Proof no client-specific field entered the core contract.
18. Confirmation no ERPNext business document was created.
19. Any deferred legacy migration.

Do not begin Agent implementation automatically.

## 30. Exact Next Task

After Task 08A passes:

```text
Task 08B — Coordinator Agent & Shared Workflow State Architecture
```

08B will consume this frozen semantic contract and define:

- Coordinator responsibilities
- specialized-agent boundaries
- shared workflow state
- pending interaction handling
- free-form natural-language interpretation
- tool selection/routing
- APPROVE / REJECT / MODIFY / SELECT interpretation
- trusted user-origin bridge design

without redesigning `mcp_erpnext` interaction semantics.
