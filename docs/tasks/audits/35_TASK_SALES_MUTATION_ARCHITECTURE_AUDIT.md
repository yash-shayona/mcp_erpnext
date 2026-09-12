# Task 35 — Sales Mutation Architecture Audit

## Status

**Type:** Architecture / inspection task only  
**Implementation changes:** Not allowed in this task  
**Primary profile:** `sales`  
**Purchase profile:** Must remain unchanged  
**Goal:** Inspect the complete current Sales mutation surface before deciding the next implementation task.

---

# 1. Objective

Inspect the current `mcp_erpnext` project end-to-end and determine the correct public MCP architecture for all **Sales-profile mutation capabilities**.

Do **not** begin from a fixed assumption such as:

- only Quotation and Sales Order need changes,
- all generic tools must become explicit,
- all existing allowlisted mutations should remain supported,
- all existing behavior is intentional,
- or all DocTypes should expose the same mutation operations.

The result must come from the **current implementation, shared internals, policies, contracts, runtime metadata usage, tests, docs, and ERPNext/Frappe native behavior**.

The audit must answer:

1. Which Sales DocTypes currently support each mutation operation?
2. Which support is explicit vs generic?
3. Which capabilities are intentional vs accidental/over-broad exposure?
4. Which operations should remain generic?
5. Which operations should become DocType-specific public MCP tools?
6. Which operations should be removed/restricted from public MCP exposure?
7. Which existing shared internal engines should remain generic and reusable?
8. What exact implementation task should be done next?

---

# 2. Scope

Audit the complete **Sales profile** and all shared mutation infrastructure used by it.

At minimum inspect these Sales DocTypes:

- Customer
- Item
- Quotation
- Sales Order
- Sales Invoice

Also inspect any other DocType that is currently exposed by the Sales profile if discovered during inspection.

Audit all mutation categories that exist or are referenced in the current project:

- Create
- Update
- Child-row add / item add
- Submit
- Cancel
- Delete
- Convert / map document
- Any other write/mutation operation discovered in the registry, policies, services, or wrappers

Read capabilities such as `get`, `query`, and `aggregate` are **not the main subject** of this task, except where they help understand target resolution or architecture consistency.

---

# 3. Critical Boundary — Purchase Profile

The Purchase profile is **not being redesigned or refactored in this task**.

Current Purchase behavior must remain unchanged.

You may inspect shared code used by both Sales and Purchase when necessary to understand:

- generic update engines,
- lifecycle engines,
- approval flow,
- registry behavior,
- action policies,
- shared contracts,
- shared target models,
- common tests.

But:

- do not add Purchase tools,
- do not remove Purchase tools,
- do not rename Purchase tools,
- do not change Purchase public schemas,
- do not change Purchase allowlists,
- do not change Purchase business behavior,
- do not migrate Purchase tools to a new architecture.

If a future Sales change would require shared-code changes, the audit must identify the compatibility requirement:

> Purchase observable behavior must remain unchanged.

---

# 4. Inputs / Sources to Inspect

Inspect the **actual current repository**, not only prior task descriptions.

At minimum inspect:

## 4.1 Tool registry and profile registration

Find:

- all registered Sales-profile tools,
- mutation-related public tool names,
- profile-specific registration,
- explicit vs generic tool registration,
- structured output declarations,
- input/output contracts,
- action categories,
- approval requirements.

## 4.2 Action / mutation policies

Inspect all policy/allowlist sources controlling:

- supported DocTypes,
- supported actions,
- allowed update fields,
- allowed child tables,
- child-row selectors,
- submit/cancel/delete permissions,
- delete restrictions,
- create support,
- conversion support.

Do not assume policy intent from names alone.

## 4.3 Public tool wrappers

Inspect every Sales-related mutation wrapper.

Identify:

- typed input models,
- typed output models,
- shared interaction directives,
- `Context` handling,
- target structures,
- dynamic/generic field/value exposure,
- business-specific validation,
- service calls,
- approval preparation/confirmation flow.

## 4.4 Shared mutation services / engines

Inspect the internal engines for:

- update,
- child-row addition,
- lifecycle actions,
- deletion,
- conversion/mapping,
- create flows.

Determine what is already correctly generic internally and should remain reusable.

## 4.5 Sales business services

Inspect the current service implementations for:

- Customer
- Item
- Quotation
- Sales Order
- Sales Invoice

Trace the full call flow:

```text
public MCP tool
→ wrapper/contract
→ resolver/validation
→ policy
→ approval
→ service/shared engine
→ Frappe/ERPNext API
→ result/output contract
```

## 4.6 Runtime DocType metadata usage

Verify where the implementation already uses Frappe runtime metadata.

For every recommendation involving fields or child tables, verify actual fieldnames and DocType structure through the existing metadata-based architecture.

Do not invent field schemas from memory.

## 4.7 Existing tests

Inspect mutation-related tests to determine:

- intended behavior,
- allowed operations,
- denied operations,
- approval guarantees,
- permission guarantees,
- idempotency expectations,
- typed contract expectations,
- profile isolation.

## 4.8 Existing docs / task reports

Inspect relevant architecture docs, generated tool catalog, previous task reports, and task files.

Treat previous decisions as historical context, **not immutable assumptions**.

If current code contradicts an older decision, report the contradiction.

## 4.9 Official Frappe / ERPNext behavior

Where native submit/cancel/delete/update behavior matters, verify against official Frappe/ERPNext documentation or official GitHub source.

Prefer native framework behavior over custom assumptions.

---

# 5. Mandatory Sales Mutation Inventory

Build a complete matrix from the current code.

The report must include a table with at least:

| Operation | Customer | Item | Quotation | Sales Order | Sales Invoice |
|---|---|---|---|---|---|
| Create | | | | | |
| Update | | | | | |
| Child Add | | | | | |
| Submit | | | | | |
| Cancel | | | | | |
| Delete | | | | | |
| Convert | | | | | |

Each cell must state one of:

- `Explicit public tool`
- `Generic public tool`
- `Internal only`
- `Denied by policy`
- `Not applicable`
- `Not implemented`
- `Unknown — requires verification`

For supported cells, also identify the actual public tool name.

---

# 6. Mandatory Public-vs-Internal Architecture Audit

For every mutation operation found, classify two separate questions:

## A. Public MCP API

Should the model/client see:

- a DocType-specific business tool, or
- a generic document tool?

## B. Internal implementation

Should the underlying mechanics remain:

- shared/generic, or
- DocType-specific?

Do not assume public and internal architecture must match.

Example pattern that may be valid:

```text
DocType-specific public wrapper
        ↓
shared generic internal engine
```

The report must explicitly evaluate this for each mutation family.

---

# 7. Update Capability Audit

Inspect the complete current update surface.

For every Sales DocType currently updateable, determine:

1. Is update genuinely intended for MCP use?
2. Which fields are currently updateable?
3. Are field allowlists explicit?
4. Are runtime DocType metadata checks used?
5. Are arbitrary field names accepted?
6. Are arbitrary values accepted?
7. Are child-table changes mixed into the same request?
8. How are rows selected?
9. Can submitted documents be updated?
10. Are native ERPNext validation rules preserved?
11. Does the public schema expose more capability than needed?
12. Would a DocType-specific typed public contract materially improve safety or model accuracy?

Special attention:

- Customer
- Item
- Quotation
- Sales Order
- Sales Invoice

Do not assume Customer/Item update should stay or be removed. Decide from evidence.

---

# 8. Child-Row / Item-Add Audit

Inspect any generic child-add capability.

Determine:

- which Sales DocTypes can use it,
- which child tables are allowed,
- whether it is effectively a business operation,
- whether the same capability should be part of an explicit update contract,
- whether it should be a separate explicit tool,
- or whether the generic public tool is still justified.

For Quotation and Sales Order item rows, specifically inspect:

- item resolution,
- quantity,
- rate,
- UOM-related behavior if relevant,
- row defaults,
- ERPNext calculations,
- row identity,
- approval preview,
- duplicate item behavior,
- server-side validation.

Do not implement a solution in this task.

---

# 9. Lifecycle Audit — Submit / Cancel / Delete

Inspect the current generic lifecycle tools.

For each action determine:

- input shape,
- target model,
- DocType selection,
- profile/DocType/action allowlists,
- permission checks,
- approval flow,
- native Frappe method used,
- submitted/cancelled state checks,
- link/dependency handling,
- replay protection,
- idempotency behavior.

Then answer:

> Does DocType-specific public tooling provide enough additional semantic or safety value to justify duplication?

Do not conclude only from the fact that `doctype` is an input.

Compare payload complexity and business semantics against Update/Child Add.

---

# 10. Create Architecture Consistency Check

Task 34 migrated the remaining Sales create tools to typed contracts.

Inspect the current create architecture only to use it as a consistency reference.

Confirm whether the current public create pattern is:

```text
business-specific public typed contract
→ existing business service
→ approval
→ ERPNext/Frappe
```

Do not modify create behavior in this audit.

If any inconsistency remains, document it instead of fixing it.

---

# 11. Conversion / Mapping Audit

Inspect all current Sales conversion tools, for example any flows such as:

- Quotation → Sales Order
- Sales Order → Sales Invoice

Determine:

- whether they are already business-specific public tools,
- whether ERPNext native mapping is reused,
- whether approval is required,
- whether their architecture supports the broader public-vs-internal principle.

Do not change them unless a critical defect is discovered; report only.

---

# 12. Approval Architecture Check

Inspect how mutation tools use prepare/confirm approval.

Document:

- which operations require prepare/confirm,
- action binding,
- user/site binding,
- token handling,
- trusted-human vs agent-delegated behavior,
- process-local storage limitation,
- whether any proposed future public-wrapper migration would accidentally weaken approval guarantees.

Do **not** redesign process-local approval storage in this task.

That is a separate scalability concern.

---

# 13. Security / Exposure Audit

For each public mutation tool determine whether the LLM can see or control more than necessary.

Check for:

- arbitrary `doctype`,
- arbitrary `field`,
- arbitrary `child_table`,
- arbitrary `value`,
- internal fieldnames unnecessarily exposed,
- internal Context fields,
- ERPNext internals leaking into schemas,
- unrestricted row selectors,
- unsupported DocTypes reachable through a shared tool,
- business data unnecessarily included in previews/results.

Classify each issue as:

- No issue
- Acceptable genericity
- Over-broad public schema
- Policy gap
- Contract gap
- Security concern
- Documentation-only concern

---

# 14. Required Decision Matrix

Produce a final proposed architecture matrix.

Example structure:

| Operation family | Current public API | Recommended public API | Recommended internal architecture | Why |
|---|---|---|---|---|
| Create | ... | ... | ... | ... |
| Update | ... | ... | ... | ... |
| Child Add | ... | ... | ... | ... |
| Submit | ... | ... | ... | ... |
| Cancel | ... | ... | ... | ... |
| Delete | ... | ... | ... | ... |
| Convert | ... | ... | ... | ... |

This decision must come from inspection.

Do not force a predetermined answer.

---

# 15. Required Per-DocType Recommendation

For each Sales DocType provide an explicit recommendation:

## Customer

State:

- mutations currently exposed,
- mutations that should remain,
- mutations that should be removed/restricted,
- public tool architecture recommendation.

## Item

Same.

## Quotation

Same.

## Sales Order

Same.

## Sales Invoice

Same.

If another Sales DocType is found, include it too.

---

# 16. No Code Changes Allowed

This task is inspection and architecture only.

Do **not**:

- add tools,
- remove tools,
- rename tools,
- change contracts,
- change allowlists,
- change services,
- change tests to force a recommendation,
- modify Purchase behavior,
- refactor shared engines,
- change approval storage,
- change ERPNext data,
- create migrations/patches.

Only documentation/report files may be added or updated if needed for the audit output.

---

# 17. Allowed Changes

Prefer creating only the audit report.

Suggested output:

```text
docs/reviews/SALES_MUTATION_ARCHITECTURE_AUDIT_REPORT.md
```

If the repository uses another established architecture-review/report directory, follow the existing project convention after inspection.

Do not create a new folder structure if an appropriate existing location already exists.

---

# 18. Required Report Structure

The final report must contain:

1. Executive summary
2. Repository areas inspected
3. Current Sales-profile public tool inventory
4. Current mutation capability matrix
5. Actual action/DocType allowlists
6. Current call-flow diagrams
7. Update architecture findings
8. Child-add architecture findings
9. Submit/cancel/delete findings
10. Create consistency findings
11. Conversion findings
12. Approval/security findings
13. Generic-vs-explicit analysis
14. Per-DocType recommendation
15. Purchase compatibility boundary
16. Recommended final architecture
17. Risks / migration concerns
18. What should **not** be changed
19. Exact next implementation task
20. Acceptance checklist

Every significant claim should cite the relevant project file/path and symbol/function/class.

Where native ERPNext/Frappe behavior is material, include the official source/doc reference used.

---

# 19. Tests / Verification for This Audit

Because this is not an implementation task, the primary verification is architectural evidence.

Still run safe, non-mutating checks where appropriate:

- existing relevant test suite,
- tool catalog generation,
- contract audit,
- registry/list-tools inspection,
- static searches for mutation tool names,
- static searches for action allowlists,
- static searches for Sales DocType names,
- static searches for update/child-add/lifecycle engines.

Do not perform destructive live ERPNext writes merely for this audit.

If tests already fail before changes, document the baseline.

---

# 20. Acceptance Criteria

Task is complete only when all of the following are true:

- [ ] Full current Sales tool surface was inspected.
- [ ] Customer, Item, Quotation, Sales Order, and Sales Invoice were all evaluated.
- [ ] No recommendation was based only on a previous frozen scope.
- [ ] Existing generic update exposure was traced end-to-end.
- [ ] Existing child-add exposure was traced end-to-end.
- [ ] Submit/cancel/delete were evaluated rather than assumed.
- [ ] Create and conversion architecture were checked for consistency.
- [ ] Approval behavior and security exposure were reviewed.
- [ ] Shared internal engines were distinguished from public MCP contracts.
- [ ] Current action/DocType allowlists were documented.
- [ ] Purchase profile was not redesigned or changed.
- [ ] Any future shared-code change requirement preserves Purchase behavior.
- [ ] A final generic-vs-explicit decision matrix was produced.
- [ ] A per-DocType recommendation was produced.
- [ ] Risks and migration compatibility concerns were documented.
- [ ] The exact next implementation task was defined.
- [ ] No production/business code was changed during the audit.

---

# 21. Expected Result

At the end of this task we should be able to answer, with evidence:

```text
For each Sales mutation:
- what exists now,
- why it exists,
- whether it should stay,
- whether its public API should be generic or explicit,
- what internal engine should be reused,
- what must be restricted,
- and what exact code task should be implemented next.
```

The result must prevent us from making a narrow change based only on one previously discussed DocType or operation.

---

# 22. Known Boundaries / Limitations

This task does not:

- implement the recommended architecture,
- redesign Purchase,
- add Accounts profile functionality,
- add Payment Entry,
- redesign approval persistence,
- add Redis/shared approval storage,
- change ERPNext core behavior,
- centralize unrelated configuration,
- optimize read/query/aggregate capabilities,
- change PDF/email behavior.

If any of these are discovered as relevant future work, list them separately without expanding this task.

---

# 23. Exact Next Task

The audit report must end by defining **one focused implementation task** based on the evidence.

Do not pre-name that implementation as “Quotation + Sales Order update migration” unless the audit proves that is the correct scope.

The next task must include:

- exact DocTypes,
- exact public tools to add/change/retire,
- exact shared internals to reuse,
- exact policies/allowlists affected,
- backward-compatibility approach,
- Purchase compatibility requirements,
- tests required,
- behavior that must remain unchanged.

Only after this audit is reviewed should implementation begin.
