# Task 66 implementation report

## Source baseline inspected

- App repository: `apps/mcp_erpnext`, branch `master`, baseline commit `01f4480`.
- `mcp_erpnext` was `0.0.1`; it is now `0.1.0`. `pyproject.toml` uses the existing dynamic version mechanism.
- Installed source inspected: Frappe `16.34.0`; ERPNext `16.35.0`.
- ERPNext `SellingController.onload` uses `Company.default_selling_terms` when Terms are empty, then calls `set_missing_terms()`. `AccountsController.set_missing_terms()` owns native template rendering.

## Runtime metadata evidence

Read-only `yob.localhost` metadata check found:

| Field | Runtime fieldtype |
| --- | --- |
| `Item.description` | `Text Editor` |
| `Quotation Item.description` | `Text Editor` |
| `Sales Order Item.description` | `Text Editor` |
| `Sales Invoice Item.description` | `Text Editor` |
| `Quotation.tc_name` / `terms` | `Link` / `Text Editor` |
| `Sales Order.tc_name` / `terms` | `Link` / `Text Editor` |
| `Sales Invoice.tc_name` / `terms` | `Link` / `Text Editor` |
| `Company.default_selling_terms` | `Link` |
| `Sales Order.custom_remarks` | absent |
| `Sales Invoice.custom_remarks` | absent |

The absence of `custom_remarks` on this site is handled as the required safe prepare error. No Custom Field, fixture, patch, or migration was created.

## Files changed and added

- `mcp_erpnext/instructions/{__init__,base,sales}.py`: source-controlled common/Sales instruction composition.
- `mcp_erpnext/mcp_server.py`: consumes the instruction composer; owns no instruction body.
- `mcp_erpnext/services/selling/terms.py`: shared native Terms adapter.
- `mcp_erpnext/contracts/{email,masters/item,selling/quotation,selling/sales_order,selling/sales_invoice}.py`: typed public input and preview fields.
- `mcp_erpnext/services/{common/email,masters/item,selling/quotation,selling/sales_order,selling/sales_invoice}.py`: safe resolution, native defaulting, preview, and approved-payload implementation.
- `mcp_erpnext/tools/{email,selling/sales_order,selling/sales_invoice}.py` and `mcp_erpnext/remote_operations.py`: MCP/REST argument parity.
- `mcp_erpnext/config/masters/item.py`: permits controlled Item description.
- `mcp_erpnext/contracts/registry.py`: governed email routing description.
- `mcp_erpnext/__init__.py`: SemVer minor update.
- `mcp_erpnext/tests/test_{tool_routing,email,item_service,quotation_service,sales_invoice,create_contracts}.py`: focused coverage and metadata fixtures.
- `docs/architecture/MCP_DOCUMENT_EMAIL.md`: recipient-scope and approval-revalidation documentation.
- `docs/TOOLS.md`: regenerated from the contract catalog.

The task specification under `docs/tasks/.../66_...md` was already untracked before implementation and was preserved.

## Instruction architecture result

`get_mcp_instructions(profile)` composes `BASE_INSTRUCTIONS` with `SALES_INSTRUCTIONS` only for the Sales profile. Purchase and Accounts receive common routing, response, and `party`/`self` document-email guidance without Quotation or Terms guidance. `mcp_server.py` is now only a consumer.

## Email result

`DocumentEmailPrepareInput.recipient_scope` is typed as `party | self`, defaults to `party`, and is bound into the approval payload and preview.

- `party` continues to resolve only document-linked party/Contact addresses and rejects unrelated input.
- `self` rejects `recipient_email`, reads only `frappe.db.get_value("User", authenticated_user, "email")`, validates it through the existing email boundary, and never enumerates Users.
- Confirm reloads the approved scope: party recipient association is rechecked; self re-resolves the authenticated User email and fails with `PREPARED_STATE_CHANGED` if it differs or is invalid.
- Natural-language mapping remains instructions-only; the service accepts typed scope only.

## Description result

Item Master `description` is an optional controlled creation field and appears in its preview when supplied. Quotation, Sales Order, and Sales Invoice row inputs now accept optional `description`.

Rows initially enter native ERPNext defaulting without a blank override. After `set_missing_values()`, only explicitly supplied descriptions are reapplied, because native item detail population may overwrite them. The reviewed preview and stored approved payload therefore preserve authored document-specific text, while omitted descriptions remain ERPNext-owned. No transaction path modifies Item Master.

## Terms result

`apply_selling_terms()` implements the frozen priority:

1. exact, permission-visible explicit `tc_name`;
2. `Company.default_selling_terms` when omitted;
3. no Terms when neither exists.

The helper never searches or guesses template names. It uses native `doc.set_missing_terms()` for rendered content. Quotation, Sales Order, and standalone Sales Invoice previews expose effective `tc_name` and `terms`; their existing approved payload/rebuild mechanisms persist the same reviewed values. No Terms policy, settings, resolver, custom Company field, or environment mapping was added.

## Custom remarks result

Sales Order and Sales Invoice accept optional `custom_remarks`. When supplied, each prepare service checks the exact runtime DocField with `frappe.get_meta(...).has_field()`. Missing metadata returns `CUSTOM_REMARKS_UNAVAILABLE`; present metadata is set before the preview/fingerprint/approval payload and shown in preview. No field creation was performed. The current `yob.localhost` metadata lacks both fields, so only the safe-unavailable branch was live-verified.

## Transport parity

Direct MCP wrappers construct the updated typed contracts and pass every new value once. `remote_operations.py` dispatches the same typed values to the same services. `docs/TOOLS.md` was generated after contract changes.

## Tests actually run

Passed:

```text
cd /home/frappe/frappe-bench/apps/mcp_erpnext
MCP_APPROVAL_MODE=trusted_human PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest mcp_erpnext.tests.test_tool_routing mcp_erpnext.tests.test_email mcp_erpnext.tests.test_quotation_service mcp_erpnext.tests.test_sales_invoice mcp_erpnext.tests.test_create_contracts mcp_erpnext.tests.test_item_service mcp_erpnext.tests.test_tool_contracts mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_rest_backend mcp_erpnext.tests.test_profiles
```

Result: `Ran 145 tests ... OK`.

Also passed:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
```

The test interpreter emitted pre-existing environment warnings about relative `sys.prefix` and Pydantic incomplete settings forward references. One Item requirement test deliberately logs a simulated Item Group read failure; the suite still passed. Static AST parsing of 13 changed Task-66 modules and `git diff --check` passed.

## Live/runtime checks actually run

- Performed read-only runtime metadata queries on `yob.localhost`.
- Inspected installed ERPNext controller source.
- Did not prepare or confirm business documents, create Drafts, queue email, restart services, or alter records. Those actions were not authorized as part of this implementation handoff.

## Generated docs check

The catalog generator completed and its `--check` mode found `docs/TOOLS.md` current. `MCP_DOCUMENT_EMAIL.md` now documents `party` versus authenticated-User `self` resolution.

## Versioning

The backward-compatible public capabilities warrant a MINOR release: `0.0.1 -> 0.1.0`. No Git tag was created or pushed. Intended later tag: `v0.1.0`.

## Acceptance criteria matrix

| Criteria | Evidence |
| --- | --- |
| 1-6 | Email typed scope, approval payload/revalidation implementation; `test_email`, `test_tool_routing`. |
| 7-14 | Item/row contracts and services; `test_item_service`, `test_quotation_service`, `test_sales_invoice`, `test_create_contracts`. |
| 15-23 | Shared native Terms helper and previews; `test_quotation_service`, `test_sales_invoice`. |
| 24-27 | Runtime `has_field` safe branch and Invoice fixture coverage; no schema artifacts; metadata query. |
| 28-32 | New instruction package and `test_tool_routing`; catalog/profile tests. |
| 33-35 | Wrapper/remote parity code; `test_rest_backend`, `test_tool_contracts`, `test_tool_registration`, catalog check. |
| 36 | `mcp_erpnext/__init__.py` reports `0.1.0`. |

## Deviations and unresolved items

- No authorized live prepare-preview/Draft/email-queue test was performed.
- `custom_remarks` is absent on `yob.localhost`, so its present-field path is covered by a focused fake-runtime test rather than this site.
- `bench version` could not complete because unrelated `apps/india_compliance` has a Git dubious-ownership condition; Frappe/ERPNext versions above were read directly from their installed source.

## Resulting project state

Task 66 is implemented as a focused source change. The worktree remains intentionally uncommitted for review; no unrelated tracked files were modified. The untracked task document remains alongside the newly added instruction package and Terms helper.
