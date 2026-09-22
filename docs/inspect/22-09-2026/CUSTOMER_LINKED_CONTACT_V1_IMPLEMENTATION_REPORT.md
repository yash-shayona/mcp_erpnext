# Customer-Linked Contact V1 Implementation Report

## Context

Task 57 was implemented on branch `master`, at `bf2ccb1ea2e0444ecfaf026957629555abe39d94` before and after the change. The bench root is not a Git repository; the relevant checkout is `apps/mcp_erpnext`.

Task 56's static findings were preserved. Runtime metadata re-check was attempted on `praveg.localhost` with the real Bench command, but the database was unavailable:

```text
MySQLdb.OperationalError: (2004, "Can't create TCP/IP socket (1)")
```

Therefore the write path is source- and unit-test-verified, not live-site verified.

## Public capability

Sales exposes exactly:

- `search_contacts`: bounded Contact search. Global lookup is exact by Contact name, email, or normalized phone; fuzzy name matching is available only with an exact, permission-checked Customer context.
- `prepare_customer_contact`: non-mutating create/link preparation with duplicate checks, native preview validation, stale-state capture, and shared approval storage.
- `confirm_customer_contact`: shared approval claim, fresh permission/stale/duplicate/link checks, and one native Contact operation.

Purchase and Accounts do not expose these tools. No generic Contact profile, Supplier Contact support, unlink, delete, merge, update, or arbitrary Dynamic Link mutation was added.

## Changed files

Production integration:

- `mcp_erpnext/contracts/masters/contact.py`
- `mcp_erpnext/services/masters/customer_contact.py`
- `mcp_erpnext/tools/masters/customer_contact.py`
- `mcp_erpnext/tools/__init__.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/remote_operations.py`

Tests and generated documentation:

- `mcp_erpnext/tests/test_customer_contact.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_rest_backend.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `docs/TOOLS.md`
- this report

The user-provided Task 56 audit and Task 57 specification remained unchanged.

## Contract and data minimization

Public inputs use fixed `Customer` and `Contact` references. New Contact input is limited to first, middle, and last name, company name, email, and mobile. The server constructs `email_ids`, `phone_nos`, and exactly one `Customer` Dynamic Link; callers cannot provide raw child tables, `link_doctype`, projections, system fields, or arbitrary custom fields.

Results expose only Contact name, full name, company, primary email/mobile/phone projections, primary status, target-link status, and an unrelated-party link count. Link rows, party names, addresses, communications, User fields, and CRM data are not returned.

## Permission model

- Search with Customer context requires Customer read and then normal Contact read filtering.
- New Contact creation requires Customer read and Contact create.
- Existing Contact linking requires Customer read, Contact read, and Contact write.
- All document reads use normal Frappe permission-aware APIs and all business writes use `ignore_permissions=False`.

## Native flows

Create confirmation builds a native Contact document with child email/phone rows and one fixed Customer Dynamic Link, then calls:

```python
contact.insert(ignore_permissions=False)
```

Link confirmation reloads the selected Contact, checks `has_link("Customer", customer_name)`, appends one fixed Dynamic Link when absent, and calls:

```python
contact.save(ignore_permissions=False)
```

Frappe Contact validation and installed Contact hooks remain authoritative. The service commits once after the native operation and rolls back on failure. Prepare does not insert, save, mutate child rows, or commit.

## Duplicate, approval, and stale behavior

Exact visible email/phone matches block new Contact preparation with `CONTACT_DUPLICATE_SUSPECTED` and minimal candidate projections. Same-name matches do not auto-reuse. Existing links are idempotent and never duplicated.

The shared `ApprovalStore` action is `customer_contact`; confirmation uses `claim_for_confirm_write`. The approval payload binds site/user/action through the existing store and captures Customer/Contact modified state, operation mode, exact identity payload, duplicate decision, and link state. Confirmation reloads references and rechecks permissions, duplicates, modified state, and `has_link` before writing.

Existing Contact primary promotion and new Contact `make_primary=true` are explicitly deferred. `make_primary=true` returns `CONTACT_PRIMARY_UNSUPPORTED`; no Customer write is performed. This avoids the installed cross-party `is_primary_contact` semantics and keeps Task 57 to one native Contact operation.

## Tests and verification

Passed:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest mcp_erpnext.tests.test_customer_contact
```

Result: 8 tests passed.

The combined focused Customer Contact/profile/REST/registration run passed 40 tests. The generated catalog check passed:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
```

The full app discovery command ran 396 tests. It retained five unrelated failures in existing Customer, Item, Purchase Order, Quotation, and Email approval/profile tests. Those failures concern existing shared approval-policy/profile expectations and do not reference the new Contact implementation. An existing India Compliance Item test also emits its established mocked Item Group HSN read error log. No unrelated failure was changed as part of Task 57.

Additional checks:

- Python AST parsing passed for all new/modified Python production files.
- `git diff --check` passed.
- Ruff was unavailable in the environment.
- No live Contact, Customer, database, queue, HTTP, or production-site mutation was run.

## Deviations and retained limitations

The only intentional deviation from the optional primary behavior is that primary promotion is unsupported in V1. This is explicitly allowed by Task 57 when safe compound Contact+Customer behavior cannot be completed without broadening scope. Existing Customer creation (`prepare_customer` / `confirm_customer`) was not split or rewritten.

The live runtime metadata check remains unverified because the local MariaDB socket could not be created. Static checked-out Frappe/ERPNext/CRM source was used for the native controller and hook boundary.
