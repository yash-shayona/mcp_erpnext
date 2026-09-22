# Customer-Scoped Contact Detail and Communication Update — Implementation Report

## 1. Repository state

- Repository: `apps/mcp_erpnext`
- Branch before/after: `master`
- HEAD before/after: `e119e18419ad9a10ad01a274b8aa1317cb2d9bf2`
- No commit, migration, site-data mutation, or deployment was performed.
- The pre-existing Task 61 implementation task file remains untracked and was
  not modified.

## 2. Changed files

- `mcp_erpnext/contracts/masters/contact.py`
- `mcp_erpnext/services/masters/contact_update.py`
- `mcp_erpnext/tools/masters/contact.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/remote_operations.py`
- `mcp_erpnext/tests/test_contact_update.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `docs/TOOLS.md` (regenerated)
- This report.

## 3. Public capability

Sales now exposes exactly:

```text
prepare_contact_update
confirm_contact_update
```

The exact discriminated operation union is:

```text
set_details
add_email
replace_primary_email
set_primary_email
add_phone
replace_primary_phone
replace_primary_mobile
set_primary_phone
set_primary_mobile
```

The public contracts are `ContactUpdatePrepareInput`,
`ContactUpdateConfirmInput`, `PrepareContactUpdateOutput`, and
`ConfirmContactUpdateOutput`. Every public model inherits the existing
`PublicContractModel` extra-field rejection behavior. Confirm accepts only the
existing `approval_token` and `confirm` fields.

## 4. Boundary and relationship safety

Prepare and confirm load the exact Customer and Contact through the existing
permission-aware loaders. The Contact must have the exact Customer Dynamic
Link; update never creates a link. Contact read/write permission is checked,
and a Customer-primary Contact additionally requires Customer write
permission before any mutation.

Any additional Contact relationship is treated conservatively as shared and
returns `CONTACT_SHARED_WITH_OTHER_PARTIES`. Related party names are never
returned. The same relationship state, Customer membership, and primary state
are rebound and checked at confirm.

## 5. Mutation behavior

`set_details` accepts only `first_name`, `middle_name`, `last_name`,
`company_name`, `designation`, and `department`. Contact document names and
native-derived projections are not assigned directly.

Email operations validate one address, preserve child row identity, reject
ambiguous selectors, and manage only the email primary flag family. Phone and
mobile operations validate one number, preserve child row identity, and manage
the independent `is_primary_phone` and `is_primary_mobile_no` flag families.
Existing rows are mutated in place; new rows are appended through the loaded
Contact document. No removal, clearing, raw child-row patch, or `both` phone
kind is exposed.

Duplicate checks are permission-aware and Customer-scoped. Same-Contact exact
states can be idempotent; likely visible duplicates return
`CONTACT_DUPLICATE_SUSPECTED`; inaccessible Contacts are not disclosed.

## 6. Stale state, approval, and transactions

Prepare binds the authenticated user/site, Sales profile, Customer and Contact
modified values, relationship state, Customer-primary state, operation values,
affected child-row names/values/flags, child fingerprint, and duplicate target
fingerprint. Confirm uses the shared `ApprovalStore.claim_for_confirm_write()`
with the distinct action `customer_contact_update`.

Confirm reloads both documents, repeats permission and relationship checks,
compares modified values and fingerprints, then applies one approved in-memory
operation. Changed or missing rows, changed primary flags, changed links,
sharing, duplicate applicability, or Customer-primary state require a fresh
prepare.

For a non-primary Contact, confirm saves only Contact and performs one outer
commit. For a Customer-primary Contact, it saves Contact followed by Customer
with no intermediate commit, then performs one outer commit. Any failure rolls
back. Customer projection fields are refreshed by native Customer save; no
direct projection assignment or `frappe.db.set_value` is used.

Normal `Contact.save(ignore_permissions=False)` is retained, so installed
Frappe, ERPNext, and CRM validation/hooks remain authoritative. The preview
only states that native CRM snapshots may refresh and does not expose CRM
records.

## 7. Bounded results

Prepare and confirm expose Customer/Contact references, before/after full name,
changed fields, selected/proposed communication values, selected primary state,
resulting primary email/phone/mobile values, Customer projection-refresh
status, CRM snapshot warning, idempotency, and zero additional-party count.
They do not expose raw Contact JSON, unrelated links, child-table dumps,
addresses, comments, communications, User data, or CRM Deal data.

## 8. Registration and transport parity

The update pair is registered by the existing Sales Contact tool registration,
declared in the contract registry, dispatched by the fixed typed REST registry,
and included in generated `docs/TOOLS.md`. Purchase and Accounts profiles do
not expose the pair. MCP and REST call the same service implementation.

## 9. Tests and verification

Added `mcp_erpnext/tests/test_contact_update.py` covering non-mutating prepare,
child-row replacement, Customer-primary refresh, primary email switching,
shared-contact rejection, stale link detection, and Customer write preflight.
Updated tool-registration expectations for the two Sales tools.

Executed successfully:

```text
../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_contact_update \
  mcp_erpnext.tests.test_customer_contact \
  mcp_erpnext.tests.test_standalone_contact \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_rest_backend
```

Result: `Ran 71 tests ... OK`.

The generated catalog commands also completed successfully:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
```

The commands emitted existing Python/Frappe and Pydantic warnings but no
failure. No pre-existing test failures were observed in the executed suites.

No live business record or site data was created, updated, deleted, migrated,
or used as a mutation fixture. Task 57 and Task 60 production behavior was not
altered; their focused regression tests passed.

## 10. Deviations and retained limitations

The implementation follows Task 58's native Contact/Customer boundary. The
public search projection and existing create/link flows were left unchanged.
The implementation conservatively treats every additional Contact
relationship as shared, matching the Task 61 security requirement without
changing Task 57's broader public count semantics.

Shared Contacts, communication removal/clearing, Contact delete/unlink/merge/
rename, arbitrary Dynamic Link mutation, Contact primary-party promotion,
Supplier/Purchase/Accounts Contact management, bulk operations, and arbitrary
Contact patching remain intentionally unsupported.
