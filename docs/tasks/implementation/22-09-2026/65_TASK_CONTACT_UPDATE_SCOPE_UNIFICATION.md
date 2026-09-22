# Task 65 — Contact Update Scope Unification

## Status

**Implementation task**

This task follows the existing Contact capability baseline:

```text
Task 57: Customer-linked Contact create/link
Task 60: Standalone Contact creation
Task 61: Customer-scoped Contact detail and communication update
Task 63: Customer primary Contact promotion
```

Task 64 remains a separate Contact relationship and primary-state hardening
audit. This task must not overwrite or absorb Task 64.

## 1. Objective

Extend the existing Contact-specific update pair:

```text
prepare_contact_update
confirm_contact_update
```

so the same capability supports both:

```text
standalone Contact updates
Customer-scoped updates for an already-linked Contact
```

The implementation must not add Contact to the generic lifecycle update
allowlist. Generic lifecycle updates remain intended for bounded exact-field
updates on their currently supported doctypes.

## 2. Current problem

`prepare_contact` / `confirm_contact` can create a standalone Contact without
email or phone values. Task 61 can update email, phone, and bounded Contact
details only when an exact Customer is supplied and the Contact already has the
Customer Dynamic Link.

Therefore a standalone Contact cannot be updated through MCP even though the
native Frappe Contact form can edit it. The conversational layer must not infer
a Customer from an email domain, search for a presumed company, or create a
Customer merely to update a standalone Contact.

## 3. Public contract direction

Update the existing Contact update input so `customer` is optional:

```text
contact: exact Contact reference
customer: exact Customer reference or omitted
operation: existing bounded Contact update operation
```

Do not create a second standalone update tool pair unless current registry or
transport constraints prove that one pair cannot represent the two explicit
scopes safely.

The output must disclose the selected scope sufficiently for review, while
continuing to return only bounded Contact/Customer references and projections.

## 4. Scope-specific authorization

### Standalone scope

When `customer` is omitted:

- load the exact Contact with normal read permission;
- require normal Contact write permission before preparation and confirmation;
- do not require or resolve a Customer;
- do not create, remove, or modify Dynamic Links;
- do not refresh Customer projections;
- reject operations whose semantics require a Customer projection.

### Customer scope

When `customer` is supplied, preserve Task 61 behavior:

- load the exact Customer and Contact with normal permissions;
- require the exact Customer Dynamic Link;
- reject Contacts shared with any additional party relationship;
- require Customer write permission when the Contact is that Customer's
  primary Contact and native Customer projection refresh may occur;
- preserve all existing stale-state, duplicate, and relationship checks.

The server must never select the first matching Customer or derive Customer
identity from an email domain.

## 5. Operations

Preserve the existing bounded operation set:

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

Email and phone updates must continue to mutate native child rows through the
loaded Contact document. Parent projections such as `email_id`, `phone`, and
`mobile_no` must remain native-derived fields and must not be directly patched.

Do not add arbitrary Contact field patching, child-table replacement, removal,
unlink, rename, merge, delete, bulk operations, or primary-party promotion to
this task.

## 6. Approval and stale-state requirements

Keep the existing shared approval flow and action unless a source-backed
reason requires a versioned action change. Approval payloads must bind:

- authenticated site and user;
- explicit standalone or Customer scope;
- exact Contact name and modified value;
- Customer name and modified value when Customer scope is used;
- operation values;
- affected child-row names, values, and primary flags;
- relevant relationship state for Customer scope.

Confirmation must re-load and re-check the exact same scope before mutation.
Changing from standalone to Customer scope, or changing Customer identity,
must fail closed and require a fresh preparation.

## 7. Native mutation and transaction boundary

Use normal native saves:

```python
contact.save(ignore_permissions=False)
```

For standalone updates, save only the Contact and commit once.

For Customer-scoped primary Contacts, preserve Task 61's Contact-save followed
by Customer-save sequence in one outer transaction so native Customer projection
refresh remains authoritative.

Preserve native Frappe, ERPNext, and CRM validation/hooks. Do not use direct
SQL, direct child-table SQL, `ignore_permissions=True`, or direct writes to
Customer projection fields.

## 8. Files to inspect and likely change

Inspect the current worktree before editing. Likely files are:

```text
mcp_erpnext/contracts/masters/contact.py
mcp_erpnext/services/masters/contact_update.py
mcp_erpnext/services/masters/customer_contact.py
mcp_erpnext/tools/masters/contact.py
mcp_erpnext/remote_operations.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/tests/test_contact_update.py
mcp_erpnext/tests/test_customer_contact.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
docs/TOOLS.md
```

Do not modify generic lifecycle allowlists or generic lifecycle behavior unless
a separate source-proven requirement is discovered.

## 9. Required tests

Add or update focused tests for:

- standalone email replacement;
- standalone email addition and primary selection;
- standalone phone/mobile update;
- standalone Contact detail update;
- standalone update requiring only Contact write permission;
- rejection of accidental Customer inference or implicit linking;
- Customer-scoped Task 61 behavior remaining unchanged;
- Customer-primary projection permission and save behavior;
- shared-contact rejection in Customer scope;
- stale scope, Contact, Customer, relationship, and child-row state;
- approval binding to the authenticated user and site;
- MCP, REST, and profile registration parity.

Run the focused Contact, profile, registration, contract, and REST suites plus
the generated tool catalog check. Report source/unit, local-live metadata, and
public/deployment evidence separately.

## 10. Non-goals

This task does not:

- add Contact to generic `prepare_document_update`;
- create a Customer for a standalone Contact;
- infer or auto-select a Customer;
- change Contact linking behavior;
- add Contact unlink/delete/merge/rename;
- add Supplier, Purchase, or Accounts Contact capabilities;
- implement primary Contact relationship repair or clear/unset semantics;
- perform a live business-record mutation without explicit authorization.

## 11. Completion criteria

Task 65 is complete only when:

1. one existing Contact update pair supports both explicitly selected scopes;
2. standalone updates work without a Customer lookup or Dynamic Link mutation;
3. Customer-scoped Task 61 behavior remains source- and regression-tested;
4. generic lifecycle Contact behavior remains unchanged;
5. approval, permission, stale-state, transaction, and native-hook boundaries
   are covered by tests;
6. MCP and REST expose the same typed behavior;
7. documentation and generated tool catalog are updated;
8. implementation and runtime evidence are reported separately.
