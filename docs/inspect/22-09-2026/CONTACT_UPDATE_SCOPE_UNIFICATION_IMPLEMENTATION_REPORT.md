# Contact Update Scope Unification — Implementation Report

## Status

Task 65 is implemented on branch `master`. The implementation extends the
existing Contact-specific update pair and does not add `Contact` to generic
document lifecycle updates.

## Implemented behavior

`prepare_contact_update` and `confirm_contact_update` now support two explicit
scopes:

```text
standalone:
  customer omitted
  Contact has no Dynamic Links

customer:
  exact Customer supplied
  Contact has the exact Customer Dynamic Link
```

A linked Contact without an explicit Customer scope returns
`CONTACT_SCOPE_REQUIRED`. This prevents an unscoped update from mutating a
Contact shared with a Customer, Supplier, or another party.

Customer scope retains Task 61's existing shared-contact rejection, Customer
primary projection permission requirement, relationship checks, and Customer
save behavior.

The server does not infer a Customer from an email domain, select the first
matching Customer, create a Customer, or modify Dynamic Links.

## Native and approval behavior

Both scopes use the same bounded operation set and the existing shared approval
action `customer_contact_update`.

Approval state binds the explicit scope, exact Contact state, Customer state
when applicable, operation, relationship state, and affected communication-row
fingerprint. Confirmation revalidates the same scope before the native Contact
save.

Standalone confirmation saves only the Contact with normal permissions and one
outer commit. Customer-primary confirmation preserves the existing Contact
then Customer native-save sequence and projection refresh behavior.

## Files changed

```text
mcp_erpnext/contracts/masters/contact.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/services/masters/contact_update.py
mcp_erpnext/services/masters/customer_contact.py
mcp_erpnext/tools/masters/contact.py
mcp_erpnext/tests/test_contact_update.py
mcp_erpnext/tests/test_customer_contact.py
docs/TOOLS.md
```

The implementation task is:

```text
docs/tasks/implementation/65_TASK_CONTACT_UPDATE_SCOPE_UNIFICATION.md
```

## Tests and verification

Executed:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_contact_update \
  mcp_erpnext.tests.test_customer_contact \
  mcp_erpnext.tests.test_standalone_contact \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_rest_backend
```

Result: `Ran 74 tests ... OK`.

Generated and checked the tool catalog:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
```

`git diff --check` passed.

## Post-implementation permission-context fix

Standalone duplicate detection initially queried `Contact Email` and
`Contact Phone` directly without a parent DocType context. Frappe consequently
checked independent child-table permissions and returned `Insufficient
Permission for Contact Email`, even though the authenticated user had Contact
write permission and the child tables have no independent permission rows.

`customer_contact._child_parent_names()` now passes:

```python
parent_doctype="Contact"
```

so the read-only child query is evaluated through the parent Contact
permission boundary. A focused regression test verifies this query context.

Authorized read-only validation on `yob.localhost` as
`mcp.bhai@example.com` then showed:

```text
Contact write: true
Contact links: 0
Contact email rows: 0
Contact phone rows: 0
Phone prepare validation: passed
Email prepare validation: CONTACT_DUPLICATE_SUSPECTED
```

The requested email is already present on four permission-visible Contacts:
three Customer-linked Contacts and one existing standalone `Yash Solanki`
Contact. The duplicate response is therefore the intended safety policy, not
a remaining permission failure. The requested phone had no visible duplicate.

The test run emitted existing Python environment and Pydantic warnings but no
test failures. No live Contact, Customer, Dynamic Link, or other business
record was created or changed. Public HTTPS, remote deployment, and live
business-record verification remain unperformed.

## Intentionally unchanged

- Generic `prepare_document_update` / `confirm_document_update` do not support
  `Contact`.
- Contact creation and Customer Contact linking remain unchanged.
- Contact primary-party promotion and relationship repair remain outside this
  task.
- Supplier, Purchase, Accounts, unlink, delete, merge, rename, and bulk Contact
  operations remain unsupported.
