# Item Creation Conditional Runtime Requirements Implementation Report

Implementation date: 2026-09-10

## Scope and inspected source

This implementation follows the approved `23_ITEM_CREATION_CONDITIONAL_RUNTIME_REQUIREMENTS_IMPLEMENTATION.md` task and the source-confirmed audit in `ITEM_CREATION_EFFECTIVE_VALIDATION_AUDIT.md`.

The inspected implementation and boundary files were:

- `mcp_erpnext/services/masters/item.py`
- `mcp_erpnext/services/common/creation_contract.py`
- `mcp_erpnext/services/common/field_value_resolver.py`
- `mcp_erpnext/config/masters/item.py`
- `mcp_erpnext/tools/masters/item.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/interaction.py`
- `mcp_erpnext/approvals.py`
- `mcp_erpnext/settings.py`
- `mcp_erpnext/profiles/sales.py`
- `mcp_erpnext/profiles/purchase.py`
- `mcp_erpnext/tests/test_item_service.py`
- `mcp_erpnext/tests/test_creation_contract.py`
- installed Frappe, ERPNext, and India Compliance source referenced by the audit

The current source matched the audit: Item creation uses the shared metadata/default contract, only static `reqd` fields were treated as missing, `gst_hsn_code` was not in the controlled Item input fields, and approval was created before native confirmation. No source difference required redesign.

## Implemented architecture

Item preparation still follows:

```text
core metadata/default resolution
    -> core field value resolution
    -> bounded effective-requirements providers
    -> permission-aware duplicate check
    -> approval creation
    -> native Frappe insert after confirmation
```

The new `services/common/effective_requirements.py` module defines typed internal context, requirement, result, provider, and status objects. Its runner merges only provider-declared payload additions and stops on missing, invalid, or unavailable requirements. It is not a generic Frappe expression evaluator or validation framework.

The isolated `services/integrations/india_compliance_item.py` provider does not import India Compliance. It checks, in order:

1. `india_compliance` is installed for the current site;
2. merged Item metadata exposes `gst_hsn_code` as a Link to `GST HSN Code`;
3. effective prepared `is_sales_item` is truthy;
4. `GST Settings.validate_hsn_code` is enabled;
5. `GST Settings.min_hsn_digits` safely produces the source-confirmed accepted lengths among 4, 6, and 8;
6. an exact supplied `gst_hsn_code`, or a safely permission-scoped `Item Group.gst_hsn_code` fetch source, is present and has an accepted length.

The settings are read through the supplied `frappe.get_cached_value` callback. Item Group inheritance uses `frappe.get_list(..., ignore_permissions=False)` and the existing Link resolver is used for the final HSN value. HSN Link existence, final validation, tax propagation, and all other controller/hook behavior remain native Frappe/India Compliance responsibilities.

## Exact input continuation

`item_config.CREATION_FIELDS` was not changed. The legacy Item request is passed to the provider, which recognizes only the exact provider-owned key `gst_hsn_code`, and only after the provider has established that the app, metadata, sales state, and active settings apply. The value is then resolved through the existing metadata-aware Link resolver and added to the payload before `approvals.create`.

Therefore the continuation is:

```text
prepare_item(core input)
    -> needs_input: item.gst_hsn_code, no approval
prepare_item(core input + gst_hsn_code)
    -> resolved HSN value in prepared payload
    -> ready with approval bound to that payload
```

Unknown keys remain excluded. HSN is not injected when the app is absent, validation is disabled, or the Item metadata does not expose a usable field. No `extra_fields` or arbitrary dynamic assignment was introduced.

Missing and invalid HSN cases use the existing frozen legacy `needs_input` shape with safe field metadata and user guidance. Settings or safe Item Group access failures return `ITEM_RUNTIME_REQUIREMENT_UNAVAILABLE` without exposing implementation details.

## Files changed

- `mcp_erpnext/services/common/effective_requirements.py` — added the bounded typed preflight seam.
- `mcp_erpnext/services/integrations/__init__.py` — added the optional integration package marker.
- `mcp_erpnext/services/integrations/india_compliance_item.py` — added the isolated source-confirmed India Compliance HSN provider.
- `mcp_erpnext/services/masters/item.py` — runs preflight after core resolution, maps safe failures, and resolves accepted provider values before approval.
- `mcp_erpnext/tests/test_item_service.py` — added the conditional-runtime requirement matrix and extended test doubles for site settings, metadata, and permission-scoped reads.
- `docs/inspect/ITEM_CREATION_CONDITIONAL_RUNTIME_REQUIREMENTS_IMPLEMENTATION_REPORT.md` — this report.

`creation_contract.py`, `field_value_resolver.py`, `tools/masters/item.py`, `contracts/registry.py`, `contracts/interaction.py`, `approvals.py`, settings, profiles, hooks, fixtures, migrations, and all framework/application source were not changed.

## Approval and confirmation safety

Approval storage and ownership policy were not changed. Incomplete, invalid, or unavailable preflight results return before `approvals.create`. A complete HSN value is included in the approval payload and therefore in the existing payload digest.

`confirm_item` remains unchanged and still calls:

```python
doc.insert(
    ignore_permissions=False,
    ignore_links=False,
    ignore_mandatory=False,
)
```

The final write remains subject to Frappe permissions, link checks, mandatory checks, ERPNext validation, and installed-app hooks.

## Tests and verification

Commands run from `apps/mcp_erpnext`:

```text
../../env/bin/python -m unittest mcp_erpnext.tests.test_item_service mcp_erpnext.tests.test_creation_contract
```

Result: 36 tests passed.

```text
git diff --check
../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
```

Result: `git diff --check` passed for tracked changes and 206 tests passed. The suite includes Item, Customer/shared creation, field resolution, approvals, profiles, tool registration, and HTTP contract regressions.

The added tests cover ERPNext-only behavior, disabled validation, active missing HSN, continuation and approval payload binding, 6/8-digit acceptance, invalid length, Item Group inheritance, uncertain Item Group reads, unavailable settings, non-sales applicability, metadata absence, unknown-field exclusion, and unchanged native confirmation flags.

No live authenticated MCP handshake, database mutation, native Item insert, or end-to-end India Compliance validation was run. The test suite emitted the environment's existing Python prefix and Pydantic `lifespan` warnings, plus the deliberate logged stack trace for the simulated Item Group read failure; all tests still passed. No `ruff` executable was available at `../../env/bin/ruff` or on PATH, so lint was not run.

## Limitations and remaining risks

- This is deliberately not a generic evaluator for `mandatory_depends_on`, `depends_on`, controller validation, or arbitrary installed-app hooks.
- A valid HSN length does not prove that the `GST HSN Code` Link exists; the normal permission-aware Link resolution and final native validation remain authoritative.
- Provider behavior was unit-tested with Frappe-shaped doubles. Live site-specific settings, metadata, permissions, Item Group inheritance, Link records, native insert, and tax propagation remain unverified.
- Approval storage remains process-local as designed by the existing approval architecture.

## Recommended next task

Task 24 — Item Creation Contract Migration Review: review whether the frozen legacy `prepare_item` / `confirm_item` raw-dictionary contracts should migrate to the typed MCP contract standard and shared `InteractionDirective`, without changing the business behavior implemented here.
