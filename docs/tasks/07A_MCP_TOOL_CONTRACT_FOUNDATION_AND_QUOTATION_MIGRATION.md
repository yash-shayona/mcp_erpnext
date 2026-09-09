# Task 07A — MCP Tool Contract Foundation + Quotation First Migration

## Task Type

Architecture foundation + one focused production migration.

This task **supersedes the older Quotation-only Task 07A**.

Do not implement the older Task 07A separately after this one.

---

## 1. Scope

Establish a reusable project-level contract architecture for all current and future MCP tools in `mcp_erpnext`, then migrate `prepare_quotation` as the first concrete adopter.

This task exists because the LibreChat Quotation failure exposed a project-wide weakness: a public MCP tool can currently advertise a structure that is too generic for the model/client to call reliably.

The solution must not be a one-off Quotation patch.

The foundation must be reusable by future tools such as:

```text
Customer
Item
Quotation
Sales Order
Sales Invoice
Payment Entry
Warehouse
Stock
Accounting
and future ERPNext domains
```

---

## 2. Objective

After this task:

1. The project has a documented MCP public contract standard.
2. Every future tool has a defined path for explicit input and output contracts.
3. Public tool schemas are treated as API contracts.
4. Quotation no longer exposes generic item dictionaries.
5. Quotation has an explicit output contract as well as an input contract.
6. A contract audit/guard exists so new tools cannot casually introduce untyped public payloads.
7. Tool documentation can scale to 100+ tools without manually dumping every full schema into README.
8. Existing services, Frappe permissions, HTTP identity, and approval semantics remain unchanged.

---

## 3. Mandatory First Step — Inspect Current Repository

Before editing, inspect the actual current source.

At minimum identify:

```text
MCP server/tool registration entrypoint
current registered tool names
current wrapper signatures
current service modules
Quotation prepare/confirm implementation
Customer/Item resolvers
approval implementation
tests
README/docs structure
AGENTS.md or equivalent agent instructions if present
installed MCP SDK version
installed Pydantic version
```

Do not assume paths from this task if the repository differs.

Report the discovered structure before choosing final file locations.

---

## 4. Architecture Standard to Add

Create a concise project document at an appropriate path such as:

```text
docs/architecture/MCP_TOOL_CONTRACT_STANDARD.md
```

Use the supplied `MCP_TOOL_CONTRACT_ARCHITECTURE.md` as the architectural intent.

The repository version must describe:

```text
public input contract rules
public output contract rules
resolved-reference rules
error contract
operation families
side-effect classification
thin wrapper/service boundary
runtime Context exclusion
contract testing
tool documentation generation
future-tool definition of done
legacy migration policy
```

Keep it architecture-focused, not an implementation diary.

---

## 5. Required Contract Model Organization

Introduce a small reusable contract/schema layer.

Choose exact names after inspecting the current project.

A reasonable target shape is:

```text
mcp_erpnext/
    contracts/
        __init__.py
        common.py
        errors.py
        selling/
            __init__.py
            quotation.py
```

Do not create unnecessary folders merely to match this example.

### Common contract concepts

Create reusable typed concepts only where they are genuinely shared.

Examples:

```text
safe error response/envelope
resolved Customer reference
resolved Item reference
possibly shared status/type helpers
```

Do not create one unrestricted `ResolvedReference(doctype: str, name: str)` if doing so weakens the generated schema.

The public schema for a Customer reference must still clearly constrain Customer.

The public schema for an Item reference must still clearly constrain Item.

---

## 6. Public Input Contract Policy

A public MCP tool parameter must not use an unrestricted type merely for implementation convenience.

Avoid at public boundaries unless genuinely required and documented:

```python
Any
dict[str, Any]
list[dict[str, Any]]
untyped object
untyped **kwargs
```

Use explicit nested models/types for known structures.

Example conceptual Quotation models:

```python
class CustomerReference(...):
    doctype: Literal["Customer"]
    name: str

class ItemReference(...):
    doctype: Literal["Item"]
    name: str

class QuotationItemInput(...):
    item: ItemReference
    qty: PositiveNumber
```

Inspect the current MCP SDK/Pydantic versions and choose the implementation that produces the clearest actual MCP schema.

Do not upgrade dependencies unless required and explicitly justified.

---

## 7. Public Output Contract Policy

Do not stop at input typing.

Every future public tool must have an explicit output contract/model in code.

For this task, fully type the `prepare_quotation` result states that already exist.

Inspect actual service behavior first.

Preserve existing payload semantics.

Possible concepts may include:

```text
ready
validation/error
preview
approval token/handle
```

Do not invent response states that the current service does not use.

### SDK output-schema handling

Determine whether the installed MCP SDK can expose a structured `outputSchema` from typed return models/annotations.

If yes:

```text
use the supported mechanism
verify through tools/list / Inspector
```

If no:

```text
keep explicit typed return models in code
serialize to the existing JSON-compatible response
document the SDK limitation
test the exact returned structure
do not add a fake/non-standard protocol extension
```

---

## 8. Thin Wrapper Rule

Preserve this boundary:

```text
MCP typed public contract
        ↓
thin wrapper conversion
        ↓
existing domain service
        ↓
ERPNext/Frappe
```

The wrapper may:

```text
receive typed public arguments
receive SDK Context privately
convert typed models to existing service payloads
convert service results to typed public results
```

The wrapper must not duplicate major ERPNext business logic.

---

## 9. Runtime Identity Must Stay Private

Do not expose any request/runtime identity field in public MCP schemas.

Examples that must remain model-invisible:

```text
frappe_user
frappe_session
librechat_user_id
authorization header
shared bearer token
role
run_as
site credentials
request Context
```

Preserve the existing Task 05/Task 06 identity and HTTP transport design.

---

## 10. Side-Effect Classification

Create a lightweight, maintainable way to classify public tools as:

```text
READ
RESOLVE
PREPARE
CONFIRM_WRITE
```

This may be contract metadata, documentation metadata, or another minimal mechanism appropriate to the current codebase.

Do not redesign permissions around this metadata.

It exists so humans, docs, tests, and future orchestration can understand the tool boundary.

Typical mapping:

```text
search_*   -> READ
resolve_*  -> RESOLVE
prepare_*  -> PREPARE
confirm_*  -> CONFIRM_WRITE
```

The dedicated approval-safety task will enforce explicit user approval later.

---

## 11. Quotation First Migration

Fully migrate `prepare_quotation` to the new standard.

Required public input meaning:

```json
{
  "customer": {
    "doctype": "Customer",
    "name": "GreenLeaf Foods Pvt Ltd"
  },
  "items": [
    {
      "item": {
        "doctype": "Item",
        "name": "SV-FRAPPE-DEVELOPMENT"
      },
      "qty": 2
    }
  ]
}
```

Rules:

```text
customer.doctype = exactly Customer
customer.name = required non-empty resolved document name
items = typed array
items[].item.doctype = exactly Item
items[].item.name = required non-empty resolved document name
items[].qty = existing positive-quantity rule
```

`valid_till` must be derived from the current service contract after inspection.

Do not invent a new date/default policy.

### Existing wrong shapes

These must no longer be advertised as valid public input:

```json
{
  "item_code": "...",
  "quantity": 2
}
```

and:

```json
{
  "customer": {
    "name": "..."
  }
}
```

---

## 12. Quotation Output Migration

Model the actual current `prepare_quotation` output states.

Do not change:

```text
preview meaning
approval token generation
approval TTL
approval user binding
persistence behavior
error codes
business validation
```

The new output model is a contract representation of existing behavior, not a behavior redesign.

---

## 13. Automated Contract Audit / Guard

Add a generic automated check for public tool contracts.

The implementation must adapt to what the installed MCP SDK exposes.

The audit should verify as much as technically possible:

```text
tool has a non-empty public description
tool has explicit input schema
known nested inputs are not advertised as arbitrary untyped objects
required fields are visible
Literal/enum constraints are visible where applicable
runtime Context/identity fields are not model-visible
tool has an explicit output contract in code
outputSchema is visible when SDK supports it
side-effect classification exists
```

### Legacy policy

Do not rewrite every current tool in this task solely to satisfy the new standard.

Instead:

1. Audit all existing registered tools.
2. Mark which already comply.
3. If a temporary legacy exception mechanism is necessary, freeze it to existing tool names discovered at task start.
4. New tools must not be permitted to create new legacy exceptions as normal development.
5. Quotation must not remain a legacy exception.
6. Future focused tasks can migrate existing legacy tools domain by domain.

Do not use the legacy mechanism as a shortcut.

---

## 14. Scalable Tool Documentation

Do not manually place full schemas for every tool into README.

Target documentation responsibilities:

```text
README.md
    overview
    architecture summary
    capability groups
    quick setup
    security notes
    link to complete tool catalog

docs/TOOLS.md
    complete tool catalog
    tool name
    domain
    operation family
    side-effect class
    purpose
    input/output contract summary
    approval requirement

MCP tools/list
    authoritative machine-readable schema
```

### Generation/check

Prefer generating or checking `docs/TOOLS.md` from the real registered tool contracts/tool metadata rather than duplicating schemas manually.

A reasonable mechanism may be:

```text
scripts/generate_tool_catalog.py
```

or an equivalent project-native implementation.

Required modes:

```text
generate/update
check/no-diff for tests/CI
```

Do not force this exact filename if the repository has a better existing tooling location.

The docs generator/check must not require real ERPNext writes.

---

## 15. Agent / Project Instruction Update

If the repository contains:

```text
AGENTS.md
docs/ai/*
CONTRIBUTING.md
or another agent-development instruction file
```

add a short mandatory rule pointing to the contract standard.

Future agent rule:

```text
No new or changed public MCP tool is complete until:
- input contract is explicit
- output contract is explicit
- contract tests pass
- side-effect classification exists
- tool catalog is updated/checked
- relevant domain docs are updated
```

Do not duplicate the full architecture standard into AGENTS.md.

Link/reference the standard instead.

---

## 16. Files Allowed to Change

After source inspection, changes may include the equivalents of:

```text
mcp_erpnext/mcp_server.py
mcp_erpnext/contracts/**
mcp_erpnext/services/selling/quotation.py
    only for minimal compatibility at the boundary if needed

tests related to public contracts/quotation
docs/architecture/MCP_TOOL_CONTRACT_STANDARD.md
docs/TOOLS.md
tool-doc generation/check helper
AGENTS.md or existing agent instruction index
README.md
    only a concise link/capability documentation adjustment if necessary
```

Do not make unrelated cleanup changes.

---

## 17. Do Not Change

```text
LibreChat source/config
OpenID/OAuth implementation
Streamable HTTP auth
Host protection
shared bearer-secret policy
Task 05 LibreChat -> Frappe user mapping
Frappe permission behavior
service-user fallback policy
Frappe User Permissions
approval state storage design
approval TTL
approval user binding
Customer business behavior
Item business behavior
Quotation business rules
Sales Order business rules
tool names
coordinator/sub-agent architecture
```

Do not add or create real business documents during automated tests.

---

## 18. Explicitly Out of Scope

Do not mix these into Task 07A:

```text
ambiguous Customer/Item selection enforcement
explicit user approval / confirm-tool safety
multi-worker approval storage redesign
coordinator agent
specialized sub-agents
dynamic tool exposure by agent
Sales Invoice implementation
Payment Entry implementation
```

The foundation should support them, but not implement them.

---

## 19. Tests

### A. Repository/SDK inspection evidence

Report:

```text
installed MCP SDK version
installed Pydantic version
how tool input schema is generated
whether outputSchema/structured output is supported
```

### B. Quotation public input schema

Verify actual public schema shows:

```text
customer object
customer.doctype constrained to Customer
customer.name required
items typed array
items[].item object
items[].item.doctype constrained to Item
items[].item.name required
items[].qty with existing numeric constraint
valid_till according to existing contract
```

Verify it no longer advertises generic arbitrary quotation item dictionaries.

### C. Quotation output contract

Verify each actual current prepare result state is represented by a typed result model.

If SDK exposes output schema, verify it through the actual public tool listing.

If it does not, verify typed serialization and document the limitation.

### D. Validation

Test:

```text
correct nested Customer/Item references accepted at wrapper boundary
legacy item_code/quantity shape rejected
missing customer.doctype rejected
wrong Customer doctype rejected
missing item reference rejected
wrong Item doctype rejected
missing qty rejected
qty <= 0 follows existing rule
```

### E. Runtime identity regression

Verify model-visible schema does not include:

```text
Frappe user
LibreChat user
authorization
role
run_as
request Context
```

Run existing Task 05/06 regression tests relevant to identity/HTTP.

### F. Contract audit

Verify:

```text
current tool catalog is audited
Quotation complies
new contract guard works
legacy exceptions, if any, are explicit and frozen
a deliberately untyped temporary test tool fails the contract policy
```

The temporary test tool must not remain registered in production code.

### G. Tool documentation

Verify:

```text
docs/TOOLS.md generation/check succeeds
catalog matches actual registered tools
README does not require a full manual schema dump
generated docs contain no secrets/runtime identity data
```

### H. Existing regressions

Run safe tests for:

```text
Customer
Item
Quotation
Sales Order
approval binding
HTTP transport
request-scoped identity
```

No real ERPNext business document should be created.

---

## 20. Expected Test Results

Expected:

```text
all focused contract tests pass
all existing relevant regression tests pass
prepare_quotation actual MCP input schema is explicit
Quotation output model is explicit
runtime identity remains hidden
tool catalog check reports clean/no diff
no approval behavior changes
no HTTP/LibreChat changes
no real ERPNext Quotation created by automated tests
```

---

## 21. Acceptance Criteria

```text
[ ] project-level MCP Tool Contract Standard exists
[ ] standard is not Quotation-specific
[ ] future input contract rule is documented
[ ] future output contract rule is documented
[ ] operation families are documented
[ ] side-effect classification exists
[ ] thin wrapper/service boundary is preserved
[ ] request identity remains private
[ ] prepare_quotation is migrated to explicit typed input
[ ] prepare_quotation has explicit typed output
[ ] actual public input schema is verified
[ ] outputSchema is verified if supported by installed SDK
[ ] generic contract audit exists
[ ] new untyped tools are prevented by policy/tests
[ ] legacy exceptions cannot casually grow
[ ] scalable docs/TOOLS.md mechanism exists
[ ] README remains concise
[ ] agent/project instructions reference the contract standard
[ ] existing business behavior is unchanged
[ ] relevant regressions pass
```

---

## 22. Known Limitations / Boundaries

This task does not guarantee that an LLM will never make a bad semantic choice.

Typed contracts solve structural ambiguity.

Separate tasks are still required for:

```text
ambiguous candidate selection
explicit approval enforcement
orchestration/tool routing
distributed approval state
```

If the installed MCP SDK cannot publish output schema, report that exact limitation instead of hiding it or upgrading dependencies without approval.

---

## 23. Required Completion Report

After implementation, stop and report:

1. Repository structure discovered.
2. Exact files changed/created.
3. Installed MCP SDK and Pydantic versions.
4. Shared contract architecture introduced.
5. Exact `prepare_quotation` input models.
6. Exact `prepare_quotation` output models.
7. Exact actual public `prepare_quotation` schema from tools/list/Inspector.
8. Exact output schema if supported.
9. Existing tools that already comply.
10. Any temporary legacy contract exceptions.
11. How the generic contract audit works.
12. How `docs/TOOLS.md` is generated/checked.
13. Agent/project doc updates.
14. Tests run and results.
15. Confirmation that no real ERPNext document was created by automated tests.
16. Confirmation that ambiguity handling and confirm safety were not changed.

Do not continue into the next task automatically.

---

## 24. Exact Next Task

After this foundation passes:

```text
Task 07B — Ambiguous Entity Selection Enforcement
```

That task should apply the same principle generically to Customer, Item, Warehouse, and future resolvers instead of being Quotation-only.

After that:

```text
Task 07C — Explicit User Approval / Confirm Tool Safety
```

That task should apply generically to all current/future confirm/write tools.
