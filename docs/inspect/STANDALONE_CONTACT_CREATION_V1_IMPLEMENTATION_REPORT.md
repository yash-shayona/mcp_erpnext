# Standalone Contact Creation V1 Implementation Report

## Scope and checkout

Task 60 is implemented on branch `master`. The checked-out HEAD before and
after the implementation is `6b88b01`; changes remain uncommitted. The
pre-existing untracked Task 59 and Task 58 audit/specification files were not
modified.

Files changed for Task 60:

- `mcp_erpnext/contracts/masters/contact.py`
- `mcp_erpnext/services/masters/contact.py`
- `mcp_erpnext/tools/masters/contact.py`
- `mcp_erpnext/tools/__init__.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/remote_operations.py`
- `mcp_erpnext/tests/test_standalone_contact.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `docs/TOOLS.md`
- this report

## Public capability

Sales exposes the dedicated pair:

- `prepare_contact`
- `confirm_contact`

The public input is `ContactPrepareInput { contact: ContactCreateInput }`.
`ContactCreateInput` accepts only `first_name`, `middle_name`, `last_name`,
`company_name`, `designation`, `department`, `email`, `mobile`, and `phone`.
Unknown fields are rejected by `PublicContractModel`. Confirm accepts only
`approval_token` and `confirm`.

At least one of `first_name`, `last_name`, or `company_name` is required after
trimming. Email, mobile, and phone are optional and each has one bounded V1
semantic value.

## Native payload and safety boundaries

The service constructs a native `Contact` payload. Email becomes one primary
`Contact Email` child row. Mobile and phone become separate `Contact Phone`
rows, each with only its corresponding primary flag. The caller cannot submit
raw child rows, relationship rows, primary-contact state, system fields, or
custom fields.

Standalone creation omits `links`; it does not require or check Customer
permissions and never fabricates a Customer, Supplier, or other relationship.
The bounded result reuses `ContactProjection` and returns the actual inserted
Contact name, native projections, and zero relationship count.

Prepare performs typed/trimmed input validation, email/phone validation,
permission preflight, visible exact email/normalized-phone duplicate checks,
and deterministic full-name preview derivation. It does not construct a
Frappe Contact document, call Contact validation, insert child rows, commit,
or invoke CRM hooks. Same-name-only collisions are allowed; exact visible
email/phone matches return `CONTACT_DUPLICATE_SUSPECTED`. Permission filtering
means hidden Contacts are neither enumerated nor disclosed.

## Approval and confirmation

The standalone action is `contact_create`, distinct from Task 57’s
`customer_contact`. The shared `ApprovalStore` binds site, authenticated user,
action, profile (`sales`), normalized input, and the deterministic operation
fingerprint. Confirm uses `claim_for_confirm_write()` and cannot be
self-authorized by `confirm=true`; replay is consumed and cannot write twice.

Confirm rechecks create permission and visible duplicate state, rebuilds the
approved native payload, and calls:

```python
contact = frappe.get_doc(payload)
contact.insert(ignore_permissions=False)
frappe.db.commit()
```

The service owns one outer commit after successful native insert/hooks and
rolls back on permission or native failure. Native Contact validation,
autoname, child validation, ERPNext hooks, and CRM hooks therefore remain
authoritative during confirmation. Task 57 was not changed or transaction-
hardened as part of this task.

## Exposure and transport parity

The pair is registered through the existing Sales registration path only.
Purchase and Accounts do not register it. The typed contract registry,
FastMCP wrappers, fixed REST remote-operation registry, and generated
`docs/TOOLS.md` catalog all point to the same standalone service; no
transport-specific Contact business logic was added.

## Verification

Executed from the Bench root:

```text
./env/bin/python -m unittest \
  apps.mcp_erpnext.mcp_erpnext.tests.test_standalone_contact \
  apps.mcp_erpnext.mcp_erpnext.tests.test_customer_contact \
  apps.mcp_erpnext.mcp_erpnext.tests.test_tool_registration \
  apps.mcp_erpnext.mcp_erpnext.tests.test_profiles \
  apps.mcp_erpnext.mcp_erpnext.tests.test_rest_backend
```

Result: 44 tests passed, 0 failed.

```text
./env/bin/python apps/mcp_erpnext/scripts/generate_tool_catalog.py --check
git -C apps/mcp_erpnext diff --check
```

Both checks passed. Python compile checks passed for all changed Python
modules. Ruff was not run because it is not installed in the Bench
environment. The test process emitted an existing Pydantic
`IncompleteFieldDefinitionWarning` for `lifespan`; it did not fail the tests.

No live business/site records were created or modified during implementation
verification. Confirmation tests use mocked Frappe documents and the shared
approval test backend.

## Intentional limitations

Task 60 does not implement Contact update/delete/merge/rename/unlink, multiple
communication values, arbitrary Dynamic Links, Supplier/Purchase/Accounts
Contact tools, primary promotion, bulk import, generic CRUD, or stronger
lost-response idempotency. Customer-known creation and existing Contact
linking continue to use Task 57’s `prepare_customer_contact` and
`confirm_customer_contact` flows.
