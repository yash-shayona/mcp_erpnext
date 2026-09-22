# 03 — MCP Host Approval Policy & End-to-End Validation V1 — Implementation Task

## Series

`mcp_tool_governance`

This is Task **03**, the final mandatory task in the current MCP Tool Governance series.

Prerequisites completed and accepted:

- `01_MCP_LEVEL_PROTOCOL_METADATA_FOUNDATION_V1_IMPLEMENTATION_TASK.md`
- `01_MCP_LEVEL_PROTOCOL_METADATA_FOUNDATION_V1_IMPLEMENTATION_REPORT.md`
- `02_MCP_LEVEL_TOOL_ROUTING_DESCRIPTION_SERVER_INSTRUCTIONS_V1_IMPLEMENTATION_TASK.md`
- `02_MCP_LEVEL_TOOL_ROUTING_DESCRIPTION_SERVER_INSTRUCTIONS_V1_IMPLEMENTATION_REPORT.md`

Task 01 established governed standard MCP annotations across the complete public tool surface.

Task 02 established governed routing roles, descriptions, and server instructions across the complete public tool surface.

Task 03 must validate that those server-side foundations produce the intended approval and routing behavior in the actual MCP host/client without weakening the existing ERPNext business-approval boundary.

MCP Python SDK v1 -> v2 migration remains postponed and is not part of this task unless a concrete compatibility blocker is proven.

---

# 1. Scope

This is a **whole-MCP / all-profile / host-policy / end-to-end validation** task.

It covers:

- Sales profile
- Purchase profile
- Accounts profile
- complete current public MCP surface
- Task-01 standard MCP annotations
- Task-02 routing metadata and server instructions
- ChatGPT Desktop / Codex-host MCP configuration
- representative real connected MCP flows
- host tool-call approval behavior
- separation between host approval and the server's own prepare/confirm business workflow

This task is not a Quotation-only test and is not limited to the one prompt that originally exposed the issue.

---

# 2. Objective

Establish and validate a production-appropriate host approval policy that:

1. automatically allows genuinely read-only/read-like MCP operations where supported by the host;
2. does not repeatedly interrupt the user for normal reads, searches, resolution, queries, or aggregates;
3. preserves human control over consequential ERPNext writes;
4. keeps server-side `prepare -> preview/approval -> confirm` workflow semantics intact;
5. avoids blanket trust settings unless explicitly justified;
6. verifies the actual ChatGPT Desktop/Codex host behavior rather than assuming configuration behavior from documentation alone;
7. validates representative Sales, Purchase, and Accounts workflows after Tasks 01 and 02;
8. records a reproducible client configuration and validation procedure for future deployments.

The desired outcome is a practical internal-business MCP experience with fewer unnecessary host prompts and no reduction in write safety.

---

# 3. Current Verified Baseline

From the accepted Task-02 report, the current source baseline is:

- Sales: 66 public tools
- Purchase: 21 public tools
- Accounts: 19 public tools
- Unique public tools / `TOOL_CONTRACTS`: 85 / 85
- all public tools governed by Task-01 standard annotations
- all public tools governed by Task-02 descriptions/routing roles
- common server instructions published through the initialized MCP server

Task 02 also confirmed the routing model:

```text
exact known reference                    -> get_*
natural-language workflow reference      -> resolve_*
  resolved                               -> reuse returned reference
  ambiguous                              -> returned candidates / selection flow
  not_found                              -> ask; search only for requested alternatives
explicit browse/candidate discovery      -> search_*
structured filtering/listing             -> query_*
supported server-side metric             -> aggregate_*
consequential operation                  -> prepare -> preview/approval -> confirm
```

Before making any Task-03 change, inspect the actual post-Task-02 source and generated tool catalog to confirm the baseline remains current.

---

# 4. Official Host Configuration Baseline

At implementation time, verify the current official OpenAI MCP/Codex documentation again before editing client configuration.

The currently verified host capabilities as of this task definition are:

```text
mcp_servers.<id>.default_tools_approval_mode
    = auto | prompt | writes | approve

mcp_servers.<id>.tools.<tool>.approval_mode
    = auto | prompt | writes | approve
```

The current documented meaning of:

```toml
default_tools_approval_mode = "writes"
```

is:

> prompt for tools that are not marked read-only.

The host also currently supports:

```text
enabled_tools
disabled_tools
```

and ChatGPT Desktop, Codex CLI, and the IDE extension share MCP configuration for the same Codex host through `config.toml`.

Fine-grained MCP configuration is currently documented through:

```text
~/.codex/config.toml
```

or project-scoped:

```text
.codex/config.toml
```

for trusted projects.

Do not assume these options remain unchanged if current official documentation differs at implementation time. Record the documentation date and any discrepancy in the implementation report.

---

# 5. Source / Inputs to Inspect

Inspect at minimum:

## Repository

- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/audit.py`
- `mcp_erpnext/tools/registration.py`
- `mcp_erpnext/mcp_server.py`
- profile modules
- generated `docs/TOOLS.md`
- `scripts/generate_tool_catalog.py`
- Task-01 annotation tests
- Task-02 routing tests
- approval-store / prepare / confirm implementation
- current approval mode configuration such as `MCP_APPROVAL_MODE`
- deployment/run documentation
- Docker/reverse-proxy configuration relevant to the live MCP endpoint

## Existing task artifacts

- Task 01 implementation task/report
- Task 02 implementation task/report

## Host

Where available:

- actual ChatGPT Desktop/Codex MCP server block for the deployed `mcp_erpnext` server
- effective `config.toml`
- exact configured server ID(s)
- actual connected profile endpoint(s)
- host/client version
- `/mcp` connection status
- authentication/header setup, with secrets redacted in documentation

Do not copy bearer tokens, shared secrets, user identity headers, passwords, or other secrets into repository documentation or the implementation report.

---

# 6. Important Safety Boundary

There are two separate approval layers.

## 6.1 Host tool-call approval

Controlled by ChatGPT Desktop / Codex MCP host configuration.

Examples:

```text
auto
prompt
writes
approve
```

This determines whether the host asks before invoking an MCP tool.

## 6.2 Server business approval

Controlled by the existing `mcp_erpnext` architecture.

Examples:

```text
prepare
-> preview/prepared state
-> confirm
```

with prepared-operation tokens, payload binding, user/site/action binding, TTL/replay protections, and current approval mode behavior.

Task 03 must never treat these two layers as interchangeable.

Changing host approval behavior must not remove, weaken, or bypass the server's existing business workflow.

---

# 7. Approval Policy Candidates to Validate

Do not jump directly to blanket `approve`.

Validate the policies in stages.

---

## 7.1 Policy A — Baseline `writes`

Configure the target MCP server with:

```toml
[mcp_servers.<actual-server-id>]
# existing URL/auth/header settings remain unchanged
default_tools_approval_mode = "writes"
```

Do not create a duplicate server table.

Expected behavior based on Task-01 annotations:

### Expected automatic/no-host-prompt

Tools governed as read-only, including representative:

```text
READ
RESOLVE
```

such as:

- `get_*`
- `search_*`
- `query_*`
- `aggregate_*`
- `resolve_*`
- eligible candidate-selection/read behavior according to actual annotations

### Expected host prompt

Tools not marked read-only, including:

```text
PREPARE
CONFIRM_WRITE
```

This means Policy A may still prompt twice in a mutation workflow:

```text
prepare -> host prompt
confirm -> host prompt
```

Record actual behavior rather than assuming it.

---

## 7.2 Policy B — Optimized prepare-auto / confirm-prompt

If Policy A behaves correctly, evaluate whether the internal-business UX should auto-approve only the server's **PREPARE** tools while retaining host prompts for actual `CONFIRM_WRITE` tools.

Conceptually:

```toml
[mcp_servers.<actual-server-id>]
default_tools_approval_mode = "writes"

[mcp_servers.<actual-server-id>.tools.<prepare-tool>]
approval_mode = "approve"
```

for the exact current set of tools whose authoritative `ToolContract.side_effect` is `PREPARE`.

Do not manually guess this list.

Derive the exact prepare-tool set from the current contract registry/generated catalog.

Expected optimized mutation UX:

```text
resolve/get/search/query/etc. -> no host prompt
prepare                       -> no host prompt
preview shown to user
user approves business action
confirm                       -> host prompt
```

This policy may be selected as the recommended internal-host policy only if validation proves:

1. every auto-approved tool is actually `PREPARE`;
2. no auto-approved PREPARE tool performs the final ERPNext business write;
3. no PREPARE tool sends external communication;
4. confirm/write tools remain prompted;
5. Task-01 annotations remain truthful;
6. server prepare/confirm security remains unchanged.

If any PREPARE tool has semantics that do not fit this policy, use an explicit exception rather than weakening the whole classification.

---

## 7.3 Policy C — Blanket `approve`

Do **not** adopt:

```toml
default_tools_approval_mode = "approve"
```

as the production recommendation in this task unless a separate explicit safety decision is made.

The current server uses its own prepare/confirm architecture, but the existing approval mode and host integration must not be assumed to provide an independently verified human event for every confirm path.

Task 03 should document blanket `approve` as an available host capability, not silently make it the default production policy.

---

# 8. Client Configuration Deliverable

Create a sanitized, reproducible host configuration guide in the repository.

Preferred path:

```text
docs/operations/MCP_HOST_APPROVAL_POLICY.md
```

If an established operations/client-configuration documentation folder already exists, reuse that established location instead and document the reason.

The guide must include:

1. where ChatGPT Desktop/Codex reads the MCP config;
2. how to find the existing server block;
3. rule against duplicating `[mcp_servers.<id>]`;
4. Policy A example;
5. Policy B example using the actual prepare tool list or a deterministic generated list;
6. confirmation that auth/header values must be preserved and secrets must not be committed;
7. restart/reload requirement;
8. `/mcp` connection verification;
9. rollback instructions;
10. validation matrix;
11. distinction between host approval and server business approval.

Do not include real secrets.

---

# 9. Maintainability of PREPARE Overrides

If Policy B is selected, prevent the prepare override list from becoming an unmaintained hand-written list.

Inspect the existing contract/catalog generator first.

Choose the smallest maintainable approach.

Acceptable options include:

- generate a sanitized TOML policy snippet from `ToolContract.side_effect == PREPARE`;
- extend the existing tool-catalog generator with an approval-policy output mode;
- add an audit/test that verifies the documented PREPARE override set equals the contract-derived PREPARE set.

Do not introduce a large new configuration framework if a small generator/check is sufficient.

The source of truth must remain the existing `ToolContract` registry.

---

# 10. Server-Side Regression Verification

Before live client testing, verify Task-01 and Task-02 foundations still hold.

At minimum:

- all public tools have expected standard annotations;
- all public tools have governed descriptions;
- routing-role metadata is present;
- server instructions are published;
- profile tool inventories are unchanged;
- custom project metadata remains present;
- current `MCP_APPROVAL_MODE` and approval-store behavior are unchanged unless explicitly required by this task.

Do not modify ERPNext business logic just to make host approval UX easier.

---

# 11. End-to-End Validation — General Rules

The validation must test the **actual connected Streamable HTTP MCP** where operator access is available.

Expected path:

```text
ChatGPT Desktop / Codex host
        ->
configured MCP server
        ->
reverse proxy / deployed endpoint
        ->
Docker MCP service
        ->
mcp_erpnext
        ->
ERPNext
```

Use a test/safe business context where possible.

Do not create destructive production records merely to prove a popup behavior if the same behavior can be safely validated against draft/test data.

For delete/cancel/email/payment actions, use controlled test records and do not proceed with destructive/external effects unless explicitly authorized.

---

# 12. Required Host Approval Validation Matrix

Record **observed**, not assumed, behavior.

At minimum validate:

| Tool family | Representative action | Expected with Policy A |
| --- | --- | --- |
| resolve | resolve Customer/Item/Supplier | no host prompt |
| get | get exact document/master | no host prompt |
| search | browse candidates | no host prompt |
| query | structured listing | no host prompt |
| aggregate | supported metric | no host prompt |
| prepare | representative mutation prepare | host prompt |
| confirm | representative final write | host prompt |

If testing Policy B:

| Tool family | Expected with Policy B |
| --- | --- |
| READ / RESOLVE | no host prompt |
| PREPARE | no host prompt |
| CONFIRM_WRITE | host prompt |

Test multiple fresh conversations/threads to verify the policy is configuration-driven rather than a one-thread temporary "Always allow" state.

---

# 13. Required Routing Validation After Task 02

Task 03 must also verify that Task-02 routing guidance works in the real client.

At minimum use representative scenarios.

## 13.1 Natural-language transaction

Example intent:

```text
Create a quotation for client Vertex for item ...
```

Expected:

```text
resolve_customer
resolve_item
...
```

A successful resolver result should not be followed merely for verification by:

```text
search_*
query_*
```

Record actual tool trace.

## 13.2 Exact known document

Example:

```text
Get Sales Order SAL-ORD-...
```

Expected:

```text
get_sales_order
```

not search/query discovery first.

## 13.3 Browse

Expected first choice:

```text
search_*
```

## 13.4 Structured listing/filter

Expected first choice:

```text
query_*
```

## 13.5 Aggregate

Expected:

```text
aggregate_*
```

where a matching server-side aggregate capability exists.

## 13.6 Resolver not-found

A resolver `not_found` must not lead to silent substitute selection through `query_*`.

Expected:

- clarification; or
- explicit alternative search only when requested.

The MCP server cannot deterministically prevent all client over-calling, so record observed compliance rather than claiming a hard guarantee.

---

# 14. Representative Cross-Profile E2E Flows

Validate at least one representative workflow per profile.

Use actual tools currently present in the profile.

## Sales

Prefer a safe draft workflow such as:

```text
resolve/read prerequisites
-> prepare Quotation or Sales Order
-> inspect preview
-> optional confirm only with explicit test authorization
```

Validate:

- routing
- read prompt behavior
- prepare prompt behavior
- confirm prompt behavior

## Purchase

Use a representative Supplier/Item/Purchase Order read/prepare path.

Validate the same boundaries.

## Accounts

Use safe Payment Entry/accounting read/prepare behavior.

Do not create or reconcile live financial transactions solely for testing unless explicit authorization and suitable test data exist.

If final confirm cannot safely be executed, validate the host prompt reaching the confirm boundary without approving execution and record that limitation.

---

# 15. Destructive and Open-World Validation

Task 01 deliberately marked exceptional semantics.

At minimum inspect/validate host recognition for representative:

- destructive lifecycle tool such as `confirm_document_delete`;
- open-world communication tool such as `confirm_document_email`.

Do not actually delete a valuable record or send an external email just to validate the host.

It is sufficient to reach the approval boundary with safe/test inputs where supported.

Confirm that Policy B does not auto-approve these `CONFIRM_WRITE` tools.

---

# 16. Fresh-Thread Persistence Validation

One original UX problem was repeated "Always allow" behavior across threads.

After applying the chosen `config.toml` policy:

1. restart/reload the relevant host;
2. open a fresh chat/thread;
3. call representative read tools;
4. confirm they do not require repeated manual allow decisions;
5. open another fresh chat/thread;
6. repeat;
7. record whether behavior remains policy-driven.

Do not confuse a temporary per-thread approval cache with persisted configuration.

---

# 17. Multiple MCP Server Ambiguity

The user may have local/testing MCP servers connected alongside the deployed live server.

During Task-03 validation:

- identify all active overlapping ERPNext/Sales MCP servers;
- record their server IDs;
- do not permanently delete them merely for testing;
- when necessary, temporarily disable overlapping test servers using the supported server `enabled` setting or equivalent current host mechanism;
- validate whether Task-02 server name/instructions/tool descriptions are sufficient for the model to choose the intended live server.

Do not turn this task into a public plugin/marketplace integration.

Raw internal MCP remains the intended architecture.

---

# 18. Allowed Changes

Allowed:

- sanitized operations/client configuration documentation
- deterministic helper/generator/check for host approval snippets if justified
- tests/audits supporting approval-policy generation
- narrowly scoped Task-01/Task-02 metadata corrections discovered during validation
- non-secret example `config.toml` snippets
- task implementation report

Not allowed without separate approval:

- MCP Python SDK v1 -> v2 migration
- removing server-side prepare/confirm controls
- changing ERPNext business validation
- changing permissions
- changing public tool schemas
- changing profile membership
- changing tool names
- introducing marketplace/plugin publication
- blanket auto-approval of final writes
- committing real credentials/secrets
- modifying live financial/business records unnecessarily

---

# 19. Automated Tests / Checks

Run the existing focused governance suites at minimum:

```text
test_tool_routing
test_tool_annotations
test_tool_contracts
test_tool_registration
test_profiles
test_approvals
```

Run any new tests for:

- approval policy snippet generation/checking;
- PREPARE override set equality with contract registry;
- no CONFIRM_WRITE tool accidentally included in auto-approved PREPARE overrides;
- generated docs/config check mode, if implemented.

Run the broader test discovery.

Task 02 baseline was:

```text
426 tests
4 errors
1 failure
```

with the same pre-existing approval-related failure category carried from Task 01.

Do not claim broad-suite success if those failures remain.

Acceptance requires:

- no new failure category caused by Task 03;
- any existing baseline failures clearly compared against Task 02.

---

# 20. Manual / Operator-Assisted Validation Rule

The coding environment may not have access to the user's local ChatGPT Desktop UI or local `~/.codex/config.toml`.

If that access is unavailable:

- do not fabricate E2E results;
- complete repository-side preparation/checks;
- produce the exact sanitized configuration block and test steps;
- mark Desktop validation as **operator-assisted pending**;
- wait for the operator/user to provide observed results before claiming Task 03 fully complete.

The final implementation report must distinguish:

```text
automated/repository verified
server/deployment verified
ChatGPT Desktop/Codex host verified
operator-assisted pending
```

Task 03 is not fully accepted until the intended host behavior has actual evidence.

---

# 21. Acceptance Criteria

Task 03 is accepted only when all applicable criteria are met:

1. Task-01 annotations remain intact across all public tools.
2. Task-02 descriptions, routing roles, and server instructions remain intact.
3. Profile inventories remain unchanged.
4. Current official host approval configuration semantics were re-verified.
5. The chosen server block uses a supported `default_tools_approval_mode`.
6. `writes` behavior is tested against actual Task-01 annotations.
7. Read/resolve tools do not repeatedly prompt in the validated host.
8. Final consequential write tools remain host-controlled.
9. Server prepare/confirm business workflow remains unchanged.
10. If Policy B is adopted, every auto-approved override is contract-derived `PREPARE`.
11. No `CONFIRM_WRITE` tool is accidentally included in the prepare-auto set.
12. Destructive confirm tools remain protected.
13. Open-world email confirm remains protected.
14. Representative Sales behavior is validated.
15. Representative Purchase behavior is validated.
16. Representative Accounts behavior is validated.
17. At least two fresh-thread checks prove read-tool behavior is not a one-thread temporary allowance.
18. Task-02 routing is evaluated in the actual client with representative traces.
19. No silent resolver-not-found substitution is accepted as desired behavior.
20. Secrets are absent from committed docs/report.
21. Focused automated governance tests pass.
22. Broader test discovery introduces no new Task-03 failure category.
23. Rollback instructions are documented.
24. The final chosen policy and rationale are documented.
25. If host UI access is unavailable, the report clearly remains pending rather than claiming completion.

---

# 22. Expected Result

Preferred production outcome, if validation supports it:

```text
READ / RESOLVE
    -> automatic host execution

PREPARE
    -> automatic host execution
       only through explicit contract-derived per-tool overrides

preview/business approval
    -> user sees intended operation

CONFIRM_WRITE
    -> host approval remains required

server business confirmation
    -> existing mcp_erpnext prepared-operation protections remain active
```

If Policy B cannot be validated safely, fall back to the more conservative:

```text
default_tools_approval_mode = "writes"
```

where PREPARE and CONFIRM_WRITE both prompt.

Correctness and safety take priority over minimizing one extra prompt.

---

# 23. Limitations

This task validates the current internal MCP deployment/host combination.

It does not guarantee identical approval UX across every third-party MCP client.

Other MCP hosts may:

- ignore annotations;
- implement different approval rules;
- not support `default_tools_approval_mode`;
- use different configuration files;
- interpret server instructions differently.

The MCP server remains standards-oriented, while client-specific approval policy is documented separately.

MCP SDK v2 migration remains postponed.

---

# 24. Required Implementation Report

Create the report with the exact filename:

```text
03_MCP_HOST_APPROVAL_POLICY_END_TO_END_VALIDATION_V1_IMPLEMENTATION_REPORT.md
```

The report must include:

- summary
- source/deployment/host inspected
- official host docs/config semantics verified and date
- effective server ID(s)
- secrets-redaction confirmation
- Policy A configuration tested
- Policy A observed results
- Policy B configuration tested, if applicable
- exact contract-derived PREPARE override set, if applicable
- final chosen policy
- rationale
- rollback configuration
- fresh-thread persistence results
- Sales validation
- Purchase validation
- Accounts validation
- destructive/open-world boundary validation
- Task-02 routing trace examples
- resolver-not-found behavior
- automated test commands/results
- broader discovery comparison against Task-02 baseline
- any operator-assisted steps and evidence
- limitations
- confirmation that SDK v2 migration was not performed
- confirmation that no ERPNext business logic/profile/tool schema was changed

---

# 25. Required Report Output Path

The implementation report must be created in the **same MCP governance task folder**:

```text
docs/tasks/mcp_tool_governance/03_MCP_HOST_APPROVAL_POLICY_END_TO_END_VALIDATION_V1_IMPLEMENTATION_REPORT.md
```

Do not create the report under:

- `docs/inspect/`
- repository root
- a temporary/audit folder
- another documentation folder

Expected task/report pair:

```text
docs/tasks/mcp_tool_governance/03_MCP_HOST_APPROVAL_POLICY_END_TO_END_VALIDATION_V1_IMPLEMENTATION_TASK.md

docs/tasks/mcp_tool_governance/03_MCP_HOST_APPROVAL_POLICY_END_TO_END_VALIDATION_V1_IMPLEMENTATION_REPORT.md
```

---

# 26. Exact Next Step After Task 03

Task 03 is the **final mandatory task in the current `mcp_tool_governance` series**.

After the implementation report and operator-assisted host evidence are reviewed and accepted:

```text
01 Protocol Metadata Foundation
        -> complete

02 Routing / Description / Server Instructions
        -> complete

03 Host Approval Policy / E2E Validation
        -> complete

MCP Tool Governance series
        -> CLOSED
```

Do not automatically create Task 04.

If Task-03 evidence reveals a genuinely separate issue such as:

- server-side dynamic tool exposure;
- client-specific incompatibility;
- MCP SDK v2 requirement;
- approval-model redesign;
- unresolved tool-selection over-calling;

document it as a separate finding and decide explicitly whether it deserves a new feature/optimization series.
