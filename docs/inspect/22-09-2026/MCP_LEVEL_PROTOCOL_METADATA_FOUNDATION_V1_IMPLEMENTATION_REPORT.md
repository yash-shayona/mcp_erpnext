# MCP-Level Protocol Metadata Foundation V1 — Implementation Report

Date: 2026-09-22

## Summary

Implemented standard MCP `ToolAnnotations` for the complete public
`mcp_erpnext` tool surface. The existing `ToolContract` registry remains the
single source of truth for both the project-specific `mcp_erpnext` metadata
and the standards-compatible MCP annotations. No ERPNext business service,
approval-token flow, profile membership, public name, or typed request/response
contract was changed.

## Files changed

- `mcp_erpnext/contracts/registry.py` — adds contract-derived annotation
  defaults and explicit semantic overrides.
- `mcp_erpnext/contracts/__init__.py` — exports the annotation registry API.
- `mcp_erpnext/contracts/audit.py` — rejects missing or contract-divergent
  annotations from the registered public surface.
- `mcp_erpnext/tools/registration.py` — adds the central governed registrar.
- `mcp_erpnext/tools/__init__.py` — routes normal profile registration through
  the governed registrar.
- `mcp_erpnext/tests/test_tool_annotations.py` — complete profile/contract
  coverage and annotation policy tests.
- `mcp_erpnext/tests/test_tool_registration.py` — verifies governed registration
  and failure for an uncontracted public tool.
- `scripts/generate_tool_catalog.py` and generated `docs/TOOLS.md` — publishes
  the annotation layer in the catalog.
- `docs/architecture/MCP_TOOL_CONTRACT_STANDARD.md` — documents ownership,
  defaults, exceptions, and the host/server approval separation.

## Compatibility findings

The active Bench interpreter has MCP Python SDK `1.29.0`, which is within the
existing `mcp>=1.0,<2.0` dependency range. Its verified API is:

```python
from mcp.types import ToolAnnotations

FastMCP.tool(..., annotations: ToolAnnotations | None = None, ...)
ToolAnnotations(
    readOnlyHint=...,
    destructiveHint=...,
    idempotentHint=...,
    openWorldHint=...,
)
```

`list_tools()` returns the annotation model, and its wire representation uses
the expected camel-case fields. No dependency constraint was changed.

## Annotation policy

| Side-effect class | readOnlyHint | destructiveHint | idempotentHint | openWorldHint |
| --- | --- | --- | --- | --- |
| `READ` | true | false | true | false |
| `RESOLVE` | true | false | true | false |
| `PREPARE` | false | false | false | false |
| `CONFIRM_WRITE` | false | false | false | false |

`PREPARE` is intentionally non-read-only because it creates or maintains
server-side reviewed-operation/approval state, even when the final ERPNext
business document is not yet written.

## Explicit exceptions

- Destructive: `confirm_customer_primary_contact`, `confirm_contact_update`,
  `confirm_document_update`, `confirm_document_submit`,
  `confirm_document_cancel`, `confirm_document_delete`, and
  `confirm_customer_payment_reconciliation`. These overwrite existing state,
  make a Draft immutable, invalidate/remove a document, or alter an existing
  payment allocation.
- `confirm_document_email` is `openWorldHint=true`: it queues delivery to an
  external recipient. `prepare_document_email` remains closed-world because it
  only prepares internal state and a server-rendered attachment.
- Ordinary document/payment creation and conversions retain the non-destructive
  `CONFIRM_WRITE` default. They are consequential writes but do not delete or
  overwrite an existing business record.

## Coverage and registration architecture

Actual `list_tools()` results after the change:

| Profile | Tools | All annotated |
| --- | ---: | --- |
| Sales | 66 | yes |
| Purchase | 21 | yes |
| Accounts | 19 | yes |
| Unique public tools / `TOOL_CONTRACTS` | 85 / 85 | exact set equality |

Before this change, registration modules called `FastMCP.tool` with only
custom `meta=tool_meta(...)`. Now `register_tools()` passes the selected profile
through `GovernedMCP`; the wrapper resolves the explicit/decorator-derived name,
requires a declared `ToolContract`, preserves existing custom metadata, and
injects contract-derived `annotations`. The contract audit independently checks
the actual registered values, preventing registration drift.

## Verification

Passed:

```text
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python -m unittest \
  mcp_erpnext.tests.test_tool_annotations \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_approvals
# Ran 49 tests — OK

PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python \
  scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python \
  scripts/generate_tool_catalog.py --check
# both completed successfully

git diff --check
# passed
```

The full discovery run was also attempted:

```text
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
# Ran 419 tests — FAILED (4 errors, 1 failure)
```

The failures are reproducible when run directly and are outside files touched
by this task: four service tests receive a result without the expected
`TRUSTED_APPROVAL_UNAVAILABLE` code, and the email service test receives
`PROFILE_MISMATCH` instead. No approval/business-flow change was made to mask
those failures. The focused approval and metadata suites above pass.

## Limitations and deferred work

- Verification covers static registration and local FastMCP `list_tools()`;
  it does not constitute a live ERPNext write or external email-delivery test.
- The SDK emits an existing `IncompleteFieldDefinitionWarning` from
  `pydantic_settings` during test startup; it did not fail the focused suite.
- The next MCP-wide routing/description/instruction governance task was not
  started, as required by the implementation task.
