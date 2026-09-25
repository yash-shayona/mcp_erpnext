# Terms and Conditions Natural-Language Resolver Implementation Report

## Result

Task 67 is implemented on the current `mcp_erpnext` worktree. The Sales profile now exposes one read-only `resolve_terms_and_conditions` tool that resolves natural-language input to a canonical ERPNext `Terms and Conditions.name`, conservatively returns shared selection semantics for ambiguity, and leaves Task 66's preparation/default behavior unchanged.

The required focused suite passes: **106 tests, 0 failures**. Contract catalog generation/check, compile, and whitespace checks also pass. No business document or Terms record was mutated.

## Baseline and version

- Branch: `master`
- Baseline commit: `f07d40dfe0c6df1e402cf61b6c4f89d2a363d460` (`feat(mcp): enhance sales document authoring and email routing`)
- Pre-Task-67 app version: `0.1.0`
- Post-Task-67 app version: `0.2.0`
- Local framework source revisions: Frappe `v16.34.0`, ERPNext `v16.35.0`
- Python: `3.14.3`
- Pre-existing worktree item preserved unchanged: untracked `docs/tasks/implementation/25-09-2026/67_TASK_TERMS_AND_CONDITIONS_NATURAL_LANGUAGE_RESOLVER.md`

The generic `bench version` command could not complete because the unrelated `apps/india_compliance` checkout is not configured as a Git safe directory. Targeted read-only Git version checks above succeeded.

## Runtime Terms metadata evidence

Read-only runtime metadata was checked on `yob.localhost`:

```text
DocType: Terms and Conditions
name: Terms and Conditions
autoname: field:title
naming_rule: By fieldname

DocField title: Data, required=1, unique=1
DocField disabled: Check, default=0
DocField selling: Check, default=1
DocField buying: Check, default=1
```

Commands used:

```bash
./env/bin/bench --site yob.localhost execute frappe.get_all --args '["DocType"]' --kwargs '{"filters":{"name":"Terms and Conditions"},"fields":["name","autoname","naming_rule"]}'
./env/bin/bench --site yob.localhost execute frappe.get_all --args '["DocField"]' --kwargs '{"filters":{"parent":"Terms and Conditions","fieldname":["in",["title","disabled","selling","buying"]]},"fields":["fieldname","fieldtype","reqd","unique","default"],"order_by":"idx asc"}'
```

The authoritative source metadata was also inspected at `apps/erpnext/erpnext/setup/doctype/terms_and_conditions/terms_and_conditions.json`; it confirms `autoname = field:title`. The controller at `apps/erpnext/erpnext/setup/doctype/terms_and_conditions/terms_and_conditions.py` renders the separate `terms` body only after permission checking. The resolver does not request or expose that body.

## Existing architecture reused

The implementation reuses, without changing thresholds or Customer/Item behavior:

- `services/common/entity_resolution.py::find_candidates()` for permission-aware token/LIKE retrieval;
- `rank_candidates()` for shared normalization and scoring;
- `resolve_ranked_candidates()` for exact, spelling-correction, ambiguity, and not-found decisions;
- shared `MIN_STRONG_MATCH_SCORE = 0.88`, `MIN_MATCH_MARGIN = 0.08`, and public `MAX_CANDIDATES = 10`;
- `revalidate_exact_candidate()` and `services/masters/selection.py::select_resolved_candidate()` for stateless selection revalidation;
- shared `InteractionDirective` `SELECTION` semantics;
- `EntityResolveInput` for the non-empty public `query` contract;
- the governed `ToolContract` registry and generated catalog;
- the same Selling Terms helper already used by Quotation, Sales Order, and Sales Invoice preparation.

No shared scoring threshold or generic Customer/Item candidate-discovery behavior was modified.

## Resolver behavior and safety boundaries

### Eligibility and permissions

Every normal discovery and fallback query applies:

```python
{"selling": 1, "disabled": 0}
```

Every query uses `ignore_permissions=False`. Only `name` and `title` are fetched. The `terms` body, Jinja content, attachments, owner, and unrelated metadata are neither queried nor present in the typed output.

### Normal candidate discovery

`resolve_terms_and_conditions(query)` first calls the shared token/LIKE discovery across `name` and `title`. Returned safe rows are ranked and classified by the unchanged shared resolver.

### All-token typo fallback

When normal discovery returns zero candidates, the Terms service performs one permission-aware scan with:

```text
filters: selling=1, disabled=0
fields: name, title
order: name asc
limit_page_length: 100
ignore_permissions: false
```

`TERMS_TYPO_FALLBACK_SCAN_LIMIT = 100` is explicit in the service. Those safe rows are passed back through the shared rank/classify functions, whose public result is still capped by shared `MAX_CANDIDATES = 10`. The fallback does not lower confidence or margin thresholds. Therefore a single weak candidate remains `ambiguous`, while no eligible row remains `not_found`.

### Public result examples

Resolved:

```json
{
  "status": "resolved",
  "doctype": "Terms and Conditions",
  "reference": {
    "doctype": "Terms and Conditions",
    "name": "Sales Order Terms",
    "title": "Sales Order Terms"
  },
  "match_type": "exact"
}
```

Ambiguous:

```json
{
  "status": "ambiguous",
  "doctype": "Terms and Conditions",
  "query": "sales order",
  "candidates": [
    {
      "reference": {
        "doctype": "Terms and Conditions",
        "name": "Sales Order Terms",
        "title": "Sales Order Terms"
      },
      "label": "Sales Order Terms",
      "score": 0.882
    }
  ],
  "interaction": {
    "required": true,
    "kind": "SELECTION",
    "allowed_actions": ["SELECT", "CANCEL"],
    "reason_code": "AMBIGUOUS_REFERENCE",
    "instructions": "Select exactly one candidate."
  }
}
```

Not found:

```json
{
  "status": "not_found",
  "doctype": "Terms and Conditions",
  "query": "unknown terms",
  "candidates": []
}
```

The exact directive wording is owned by the existing shared interaction helper; the example illustrates the semantic shape.

## Stateless selection revalidation

`ResolvableDoctype` now includes `Terms and Conditions`, and the existing `select_resolved_candidate` service map adds the same Sales filters and display fields. Selection re-fetches the exact name under current permissions with `selling=1`, `disabled=0`, and `ignore_permissions=False`.

It does not trust a previous candidate list or cache. A deleted, disabled, buying-only, or permission-invisible selected Terms template returns `not_found`. No Terms-specific `select_*` tool was added.

## MCP, REST, profile, and instruction changes

- Added Sales-only MCP wrapper `tools/selling/terms.py`.
- Registered exactly one new public tool: `resolve_terms_and_conditions`.
- Added typed `TermsResolutionOutput` contract with `resolved`, `ambiguous`, `not_found`, and shared `error` states.
- Declared `SELECTION` interaction and read-only `RESOLVE` side-effect metadata in `contracts/registry.py`.
- Added the same typed operation to `_SALES_HANDLERS` in `remote_operations.py`; Purchase and Accounts do not expose it.
- Extended the existing selection input/output schema for `Terms and Conditions`.
- Updated Sales instructions to resolve explicitly requested natural-language Terms, use canonical `reference.name` as `tc_name`, revalidate ambiguous selection, never infer Terms from document type, and skip the resolver when the user did not request Terms.
- `mcp_server.py` remains instruction-body free and unchanged.
- Regenerated `docs/TOOLS.md` from actual profile registration/contract metadata.
- No reusable project command changed, so `docs/COMMANDS.md` required no update.

## Task 66 behavior preserved

`apply_selling_terms()` and all Quotation/Sales Order/Sales Invoice prepare flows remain unchanged:

```text
explicit exact tc_name -> validate/use/render it
no explicit tc_name -> Company.default_selling_terms
no explicit tc_name and no Company default -> no Terms
```

The resolver is a separate read convenience. It does not select defaults, alter preparation, create approvals, write transactions, or bypass the existing final exact `tc_name` validation.

## Files changed

Added:

- `mcp_erpnext/contracts/selling/terms.py`
- `mcp_erpnext/tools/selling/terms.py`
- `mcp_erpnext/tests/test_terms_resolution.py`
- `docs/inspect/25-09-2026/TERMS_AND_CONDITIONS_NATURAL_LANGUAGE_RESOLVER_IMPLEMENTATION_REPORT.md`

Modified:

- `mcp_erpnext/__init__.py`
- `mcp_erpnext/contracts/common.py`
- `mcp_erpnext/contracts/masters/resolution.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/instructions/sales.py`
- `mcp_erpnext/remote_operations.py`
- `mcp_erpnext/services/masters/selection.py`
- `mcp_erpnext/services/selling/terms.py`
- `mcp_erpnext/tools/__init__.py`
- `mcp_erpnext/tools/masters/selection.py`
- `mcp_erpnext/tests/test_entity_selection.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_rest_backend.py`
- `mcp_erpnext/tests/test_tool_contracts.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `mcp_erpnext/tests/test_tool_routing.py`
- `docs/TOOLS.md`

## Verification actually run

### Required focused suite

```bash
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python -m unittest   mcp_erpnext.tests.test_terms_resolution   mcp_erpnext.tests.test_entity_selection   mcp_erpnext.tests.test_tool_contracts   mcp_erpnext.tests.test_tool_registration   mcp_erpnext.tests.test_rest_backend   mcp_erpnext.tests.test_profiles   mcp_erpnext.tests.test_tool_routing   mcp_erpnext.tests.test_quotation_service   mcp_erpnext.tests.test_sales_invoice
```

Result: `Ran 106 tests in 9.223s` — `OK`.

Coverage includes exact/normalized/partial matching, typo with normal discovery, all-token typo fallback, weak single ambiguity, close-candidate ambiguity, not-found, disabled/buying-only/permission-invisible exclusion, no Terms-body exposure, Terms selection revalidation and stale eligibility failure, Customer/Item selection regressions, Sales-only exposure, governed contract metadata, REST parity, Sales routing instructions, and Task 66 Terms/default regressions.

### Catalog and static checks

```bash
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python scripts/generate_tool_catalog.py
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python scripts/generate_tool_catalog.py --check
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python -m compileall -q mcp_erpnext
git diff --check
```

Result: all passed. Catalog generation/check and tests emitted the existing `IncompleteFieldDefinitionWarning` for FastMCP's unresolved `lifespan` annotation; it did not fail validation.

### Full-suite boundary

A separate full discovery run executed 450 tests and reported 3 errors outside Task 67:

- `test_customer_service...test_model_confirm_true_cannot_self_grant_approval`
- `test_item_service...test_model_confirm_true_cannot_self_grant_approval`
- `test_purchase_order_service...test_confirm_requires_shared_approval_then_uses_normal_insert`

All three expected `TRUSTED_APPROVAL_UNAVAILABLE` but received a non-error result, producing `KeyError: 'code'`. The same three fail when run alone. Current `ApprovalStore` defaults to `ApprovalMode.AGENT_DELEGATED`, while these fixtures install a fake backend but do not explicitly configure `TRUSTED_HUMAN`. No Task 67 file changes approval logic or these tests. This pre-existing approval-mode test-fixture boundary was not changed as unrelated scope.

## Acceptance evidence

- Exactly one new public Sales tool is registered; profile tests prove it is absent from Purchase and Accounts.
- Public query uses existing `EntityResolveInput` / `NonEmptyString` validation.
- Eligibility, permissions, minimal fields, scan bound, shared top-candidate bound, and no-body contract are directly asserted.
- Exact, normalized, partial, normal typo, fallback typo, weak, ambiguous, and not-found states are covered.
- Stateless exact selection revalidates current permissions and eligibility.
- MCP and REST call the same Terms service.
- Tool contract audit, registration inventory, routing metadata, and generated catalog checks pass.
- Sales instructions encode the explicit-request rule and prohibit document-type guessing.
- Existing Task 66 Quotation and Sales Invoice tests pass.
- No policy/settings DocType, Company field, environment mapping, Purchase resolver, Terms mutation, or document-type default mapping was introduced.
- Version was bumped one MINOR release from `0.1.0` to `0.2.0`.

## Deviations, limitations, and resulting state

- No implementation deviation from the frozen strategy.
- The bounded fallback can rank only the first 100 permission-visible eligible templates ordered by name; this is intentional and reported rather than hidden.
- Conservative shared thresholds can require selection for weak input.
- Buying Terms remain out of scope.
- The resolver returns identity/display metadata, never rendered Terms content.
- Runtime activity was read-only metadata inspection only. No live MCP call and no Terms or transaction mutation was performed.
- No migration, cache clear, service restart, build, commit, tag, push, or deployment was performed.
- The worktree contains the scoped source/tests/catalog/report changes plus the user's pre-existing untracked Task 67 specification.
