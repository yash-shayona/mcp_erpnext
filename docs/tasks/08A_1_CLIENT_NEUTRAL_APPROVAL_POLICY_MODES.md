# Task 08A.1 - Client-Neutral Approval Policy Modes

## Task Type

Focused approval-policy correction.

This task does **not** redesign the existing approval store and does **not** remove Task 07C security hardening.

It introduces a server-level configurable trust policy so the same `mcp_erpnext` server can support:

1. normal chat/agent-driven ERPNext workflows, and
2. stricter deployments that require an independently server-verified human approval signal.

## 1. Context

Current state:

```text
prepare_*
  -> secure pending token
  -> preview
  -> user explicitly approves in chat
  -> Agent/LLM calls confirm_*(confirm=true, approval_token=...)
  -> existing ApprovalStore requires trusted_at
  -> no generic MCP client has a way to set trusted_at
  -> TRUSTED_APPROVAL_UNAVAILABLE
```

This affects LibreChat, VS Code/Codex MCP, and any other generic MCP client.

The failure is not a Quotation bug.

Task 07C intentionally made `confirm=true` insufficient and required `record_trusted_user_approval(...)` before `CONFIRM_WRITE`. That strict model is useful, but requiring it unconditionally makes generic chat clients unable to complete writes unless each client gets a custom trusted adapter.

The project therefore needs two explicit approval policies.

## 2. Architecture Decision

Introduce a validated server setting:

```text
MCP_APPROVAL_MODE
```

Allowed values:

```text
trusted_human
agent_delegated
```

Do not expose this as an MCP tool argument. The model/client must never be able to choose or override the mode.

## 3. Security Default

Default:

```text
trusted_human
```

This preserves current Task 07C fail-closed behavior and avoids silently weakening existing deployments.

For the current local chat-development environment, explicitly configure:

```text
MCP_APPROVAL_MODE=agent_delegated
```

## 4. Policy A - trusted_human

Preserve current behavior.

Flow:

```text
prepare_*
  -> pending operation
  -> trusted external/runtime mechanism independently verifies human approval
  -> record_trusted_user_approval(...)
  -> confirm_*
  -> shared claim_for_confirm_write(...)
  -> ERPNext write
```

Required checks remain:

- approval token exists;
- same site;
- same authenticated Frappe user;
- same action;
- same prepared payload digest;
- within TTL;
- not cancelled/rejected;
- not already consumed;
- trusted human approval recorded;
- Frappe permission rechecked before write.

Without trusted approval, retain:

```text
TRUSTED_APPROVAL_UNAVAILABLE
```

## 5. Policy B - agent_delegated

This is the intended mode for current chat/Agent development.

Trust model:

> The authenticated MCP client/Agent is treated as the user's delegated conversational orchestrator. The Agent is responsible for calling `confirm_*` only after the user explicitly approves the exact prepared preview.

The MCP server must not parse chat language.

In `agent_delegated` mode, the following is sufficient for the shared `CONFIRM_WRITE` boundary:

- `confirm=true`;
- valid pending `approval_token`;
- correct authenticated Frappe user;
- correct site;
- correct action/tool;
- exact prepared payload binding;
- valid TTL;
- token not consumed/cancelled/rejected;
- normal Frappe permission recheck.

`trusted_at` / `record_trusted_user_approval()` is not mandatory in this mode.

Do not remove `record_trusted_user_approval()`; it remains required by `trusted_human`.

## 6. Security Meaning

Document clearly:

- `trusted_human` requires independently verified human-origin approval and is stronger for human provenance.
- `agent_delegated` trusts the authenticated Agent/client to call `confirm_*` only after user approval.

Do not describe both as equally strong.

Even in `agent_delegated`, preserve all token, identity, action, payload, expiry, replay and permission checks.

## 7. Preserve Existing Task 07C Protections

Do not remove or weaken:

- opaque approval token;
- action binding;
- site binding;
- authenticated Frappe user binding;
- prepared payload digest/HMAC binding;
- TTL;
- single-use consumption;
- cross-user replay rejection;
- cross-tool/action replay rejection;
- payload mutation protection;
- cancel/reject handling where present;
- permission recheck immediately before write.

The only policy difference is whether independent `trusted_at` is mandatory.

## 8. Repository Inspection First

Before editing, inspect the actual current equivalents of:

```text
mcp_erpnext/settings.py
mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/contracts/registry.py
confirm tool wrappers
approval tests
docs/architecture/MCP_EXPLICIT_USER_APPROVAL_SAFETY.md
README/config docs
.env.example if present
AGENTS.md
```

Use the real repository structure. Do not create unnecessary files merely to match these examples.

## 9. Settings Contract

Add a validated type/enum for approval mode.

Rules:

```text
setting absent            -> trusted_human
trusted_human             -> accepted
agent_delegated           -> accepted
anything else             -> configuration validation error
```

Do not silently fall back from an invalid value.

Resolve it through the existing settings layer. Do not read the environment variable ad hoc inside each confirm tool.

## 10. Centralize Enforcement

Do not add per-tool branching such as:

```python
if settings.approval_mode == ...
```

inside every `confirm_*`.

Enforce policy centrally in the shared approval claim layer.

Target:

```text
confirm_customer
confirm_item
confirm_quotation
confirm_sales_order
future confirm_*
        |
        v
shared claim_for_confirm_write(...)
        |
        +-- trusted_human
        +-- agent_delegated
```

No Quotation-specific exception.

## 11. Public Tool Contract Must Not Expose Policy

Do not expose any of these to the model:

```text
MCP_APPROVAL_MODE
approval_mode
trusted_at
record_trusted_user_approval
server secrets
Frappe user override
```

Existing confirm tool inputs should remain conceptually:

```text
approval_token
confirm
```

unless current contracts require another already-existing business field.

## 12. Task 08A Interaction Contract Remains Unchanged

Keep:

```text
SELECTION
INPUT
APPROVAL

SELECT
PROVIDE_INPUT
MODIFY
APPROVE
REJECT
CANCEL
```

The Agent interprets free-form text.

Do not add hardcoded `yes`/`haan` parsing.

Do not add an LLM dependency inside `mcp_erpnext`.

## 13. `record_trusted_user_approval()` Behavior

Preserve this internal seam.

### trusted_human

Required before confirm write.

### agent_delegated

Not required before confirm write.

It must remain non-public and must not become an MCP tool.

Do not add model-callable tools such as:

```text
approve_token
mark_approved
trust_me
record_human_approval
```

## 14. Error Semantics

In `trusted_human`, absence of independent trusted approval must still produce the current `TRUSTED_APPROVAL_UNAVAILABLE`.

In `agent_delegated`, do not return `TRUSTED_APPROVAL_UNAVAILABLE` merely because `trusted_at` is absent.

Preserve distinct errors for:

- invalid/unknown token;
- expired token;
- wrong user;
- wrong site;
- wrong action;
- consumed/replayed token;
- cancelled/rejected token;
- tampered/mismatched operation;
- permission denial.

## 15. Process-Local Approval Storage

Do not migrate approval storage to Redis/Frappe DB in this task.

The current process-local limitation remains documented.

It is a future deployment/scaling concern and is not the root cause of the current error.

## 16. Client Neutrality

No LibreChat source changes.

No VS Code/Codex source changes.

No LangGraph implementation.

No WhatsApp adapter.

Any compatible chat MCP client should be able to use:

```text
MCP_APPROVAL_MODE=agent_delegated
```

and complete the normal prepare -> human conversation -> confirm sequence without client-specific source patches.

## 17. Current CONFIRM_WRITE Coverage

Inspect every current `CONFIRM_WRITE`, at minimum expected equivalents of:

```text
confirm_customer
confirm_item
confirm_quotation
confirm_sales_order
```

All must use the same centralized policy.

Future `CONFIRM_WRITE` tools must inherit it automatically through the shared approval guard.

## 18. Configuration Tests

Test:

1. setting absent -> `trusted_human`;
2. explicit `trusted_human` accepted;
3. explicit `agent_delegated` accepted;
4. invalid value such as `unsafe` fails validation clearly.

## 19. trusted_human Regression Tests

For current write-tool families as practical:

```text
prepare pending operation
do not record trusted approval
confirm=true
```

Expected:

```text
TRUSTED_APPROVAL_UNAVAILABLE
no write
```

Then record trusted approval and verify the shared approval claim succeeds in mocked/unit flow.

Existing Task 07C tests must continue to pass under strict mode.

## 20. agent_delegated Tests

With:

```text
MCP_APPROVAL_MODE=agent_delegated
```

prepare a pending operation, do not call `record_trusted_user_approval()`, then confirm with the correct token/user/site/action/payload.

Expected: shared claim succeeds and write path may proceed in mocked/unit flow.

Also verify rejection for:

- wrong user;
- wrong site;
- wrong action/tool;
- tampered payload;
- expired token;
- consumed token replay;
- cancelled/rejected token where supported.

## 21. Public Schema Tests

Verify generated `tools/list` does not expose approval policy/configuration internals.

There should be no model-visible switch that can select `agent_delegated`.

## 22. Interaction Regression Tests

Verify Task 08A remains correct:

- ambiguous Item -> `SELECTION`;
- Quotation ready -> `APPROVAL`;
- Quotation needs input -> `INPUT` where supported.

No language parser.

## 23. Automated Test Safety

Automated tests must not create real ERPNext business documents. Use the current mocked/unit-test style.

## 24. Manual Local E2E Test

After automated tests pass, perform or provide exact steps for one explicit development E2E with:

```text
MCP_APPROVAL_MODE=agent_delegated
```

Flow:

```text
1. Start/restart MCP server with delegated mode.
2. Connect from VS Code/Codex MCP or LibreChat.
3. Ask to create a Draft Quotation.
4. Resolve/select ambiguity.
5. prepare_quotation returns preview + interaction=APPROVAL.
6. User explicitly approves in chat.
7. Agent calls confirm_quotation(confirm=true, token).
8. It must not fail merely with TRUSTED_APPROVAL_UNAVAILABLE.
9. If Frappe permission/business validation allows it, create exactly one Draft Quotation.
10. Verify the Draft in ERPNext.
```

Do not submit the Quotation.

Use test data.

If the live write cannot be safely executed automatically, report `NOT RUN` with exact reason and manual steps. Do not pretend it passed.

## 25. Cross-Client Smoke Test

If practical, repeat the same flow in both:

```text
VS Code/Codex MCP
LibreChat
```

Expected:

- same MCP approval mode;
- no client source patch;
- both can reach confirm with the same server policy.

## 26. Documentation

Update the explicit approval architecture documentation to define both modes, including:

- default mode;
- trust model;
- security difference;
- intended use;
- client-neutral behavior;
- process-local storage limitation;
- why `record_trusted_user_approval()` remains internal;
- why natural-language parsing remains outside MCP.

Update config/setup docs and `.env.example` if present.

Do not commit real secrets or site-specific credentials.

## 27. Tool Catalog / Metadata

If the catalog currently states every `CONFIRM_WRITE` always requires independent trusted-human proof, update it to accurately say:

```text
explicit approval required;
enforcement policy is selected by server configuration.
```

Do not weaken the fact that write tools require explicit conversational approval.

## 28. Project Agent Instructions

Update project agent instructions so future `CONFIRM_WRITE` tools:

1. use the shared approval guard;
2. do not implement their own approval-mode branch;
3. do not expose approval mode publicly;
4. preserve both policies;
5. keep language interpretation outside MCP;
6. include relevant shared-policy tests.

## 29. Allowed Changes

Only focused approval-policy components:

- settings/configuration;
- shared approval guard/store;
- approval tests;
- confirm-write regression tests;
- approval architecture/config docs;
- tool catalog metadata/docs if needed;
- project agent instructions;
- `.env.example` if present.

Small mechanical typing/import changes are allowed where required.

## 30. Do Not Change

Do not redesign:

- Customer business service;
- Item business service;
- Quotation preparation/business rules;
- Sales Order business rules;
- resolver matching;
- Task 08A interaction semantics;
- LibreChat identity mapping;
- HTTP bearer authentication;
- Host protection;
- OAuth/OpenID;
- MCP transports;
- pricing;
- ERPNext permissions;
- approval token payload-binding design.

Do not implement Redis/durable storage.

Do not modify LibreChat or VS Code source.

## 31. Acceptance Criteria

```text
[ ] MCP_APPROVAL_MODE exists
[ ] only trusted_human / agent_delegated are valid
[ ] default is trusted_human
[ ] invalid values fail validation
[ ] mode is server-side only
[ ] mode is not an MCP tool argument
[ ] trusted_human behavior remains unchanged
[ ] agent_delegated does not require trusted_at
[ ] delegated mode preserves token/user/site/action/payload/TTL/single-use checks
[ ] record_trusted_user_approval remains internal
[ ] no hardcoded yes/haan parser
[ ] no LLM dependency added to MCP
[ ] all current CONFIRM_WRITE tools use the common policy
[ ] no Quotation-only exception
[ ] Task 08A interaction contract unchanged
[ ] relevant existing tests pass
[ ] new mode tests pass
[ ] public schemas expose no approval-policy control
[ ] docs clearly explain security difference
[ ] no client source patch is required
```

## 32. Required Completion Report

Return:

1. Exact files changed.
2. Approval-mode enum/type and validation location.
3. Default mode.
4. Exact environment/config syntax.
5. Central shared function/method enforcing policy.
6. `trusted_human` behavior summary.
7. `agent_delegated` behavior summary.
8. Proof token/user/site/action/payload/TTL/single-use checks remain.
9. Current `CONFIRM_WRITE` tools verified.
10. Proof `record_trusted_user_approval()` remains non-public.
11. Generated `tools/list` differences, if any.
12. Tests run and exact pass counts.
13. Strict-mode regression result.
14. Delegated-mode regression result.
15. Wrong-user/site/action/payload/replay test results.
16. Interaction-contract regression result.
17. Documentation/config changes.
18. Local development configuration example.
19. Manual Quotation E2E result or exact `NOT RUN` reason.
20. Cross-client smoke-test result if run.
21. Confirmation no LibreChat/VS Code source was modified.
22. Remaining limitations.

## 33. Local Development Target

After implementation, current local development should explicitly use:

```text
MCP_APPROVAL_MODE=agent_delegated
```

Expected:

```text
User asks to create
-> Agent resolves/prepares
-> MCP returns APPROVAL preview/token
-> Agent asks user
-> User approves in free-form chat
-> Agent calls confirm_*(confirm=true, token)
-> MCP validates delegated policy + secure pending operation + Frappe permission
-> exactly one Draft ERPNext document is created
```

No client-specific trusted approval adapter is required in this mode.

## 34. Exact Next Task

After this task passes and a Draft Quotation is successfully created end-to-end from at least one chat MCP client:

```text
Task 08B - Coordinator Agent Architecture and Tool-Scoping Design
```

Do not begin 08B automatically.

First return the Task 08A.1 completion report and E2E result for review.
