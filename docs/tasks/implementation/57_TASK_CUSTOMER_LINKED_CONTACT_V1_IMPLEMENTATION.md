# Task 57 — Customer-Linked Contact V1 Implementation

## Status

**Implementation task**

This task starts only after Task 56 audit has been completed and reviewed.

Source of truth for this task:

- `docs/inspect/CONTACT_MASTER_NATIVE_FLOW_AND_CAPABILITY_AUDIT.md`
- the current checked-out `mcp_erpnext` source at implementation time
- the effective installed Frappe/ERPNext runtime metadata on the selected development/test site

Do **not** replace installed-source/runtime findings with assumptions from generic Frappe knowledge.

---

## 1. Objective

Implement the smallest safe Customer-linked Contact capability in the Sales profile so the MCP server can:

1. search/select Contacts safely;
2. create a new native Frappe `Contact` linked to an existing ERPNext `Customer`;
3. link an explicitly selected existing `Contact` to an existing `Customer`;
4. optionally make a **newly created** Contact primary only under the narrow safety rules defined below;
5. preserve all current Customer creation behavior, approval semantics, permissions, data minimization, REST parity, and native Frappe/ERPNext controller behavior.

The implementation must use Frappe/ERPNext native Contact documents and Dynamic Links.

Do **not** build an MCP-owned Contact store, relationship table, or parallel Contact model.

---

## 2. Business problem being solved

Current Customer creation already supports nested Contact-like input. When the Customer is created with email/mobile/name details, ERPNext can create the initial native primary Contact through `Customer.on_update()` / `create_primary_contact()`.

The missing business flow is:

```text
Customer already exists
        |
        +-- User now wants to add a person
        |
        +-- Person may be:
              A. a new Contact
              B. an existing Contact that should be linked to this Customer
```

Example:

```text
Create Customer "ABC Pvt Ltd"
```

Later:

```text
Add Amit Shah to ABC Pvt Ltd
Email: amit@example.com
Mobile: 999...
```

Or:

```text
Link existing Contact "Amit Shah-ABC" to ABC Pvt Ltd
```

This must not be implemented by pretending Contact email/mobile/name are ordinary Customer scalar fields.

---

## 3. Confirmed Task 56 conclusions that must be preserved

Treat these as frozen implementation constraints unless current installed source proves the audited behavior has changed.

### 3.1 Customer and Contact are separate native records

`customer_primary_contact` is a Link to an existing `Contact`.

Customer fields such as:

- `email_id`
- `mobile_no`
- `first_name`
- `last_name`

are stored/fetched projections from the selected primary Contact and are not a replacement for Contact management.

### 3.2 Contact relationship authority

The native Customer relationship is represented by a `Dynamic Link` row inside the `Contact` document:

```text
Contact.links[]
    link_doctype = "Customer"
    link_name    = <customer name>
```

The MCP public contract must never expose arbitrary `link_doctype`.

For Task 57, the server fixes:

```text
link_doctype = "Customer"
```

### 3.3 Contact email/phone authority

Authoritative values live in Contact child tables:

```text
Contact.email_ids[]  -> Contact Email
Contact.phone_nos[]  -> Contact Phone
```

Parent projections such as:

```text
Contact.email_id
Contact.phone
Contact.mobile_no
```

must be derived by native Contact validation.

Do not treat parent projection fields as independent public write fields.

### 3.4 Native writes

For a new Contact:

```python
frappe.get_doc(contact_payload).insert(ignore_permissions=False)
```

For linking an existing Contact:

```python
contact = frappe.get_doc("Contact", contact_name)

if not contact.has_link("Customer", customer_name):
    contact.append(
        "links",
        {
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
    )
    contact.save(ignore_permissions=False)
```

The exact implementation may reuse equivalent native APIs already present in the project, but the behavior and permission boundary must remain equivalent.

### 3.5 Existing Contact primary promotion is NOT V1

Do not allow an already-existing Contact to be promoted to primary in Task 57.

Reason: `Contact.is_primary_contact` has cross-party semantics when one Contact has multiple links.

Existing-Contact primary promotion remains deferred.

---

## 4. Mandatory pre-implementation inspection

Before editing production code, inspect the current repository and verify the existing project patterns.

At minimum inspect:

- current Customer contracts;
- Customer create service;
- Customer read service;
- shared approval store;
- `claim_for_confirm_write`;
- current interaction directives;
- resolver/reference contract patterns;
- duplicate/ambiguity result patterns;
- current lifecycle stale-state/fingerprint patterns;
- tool registration;
- Sales profile registration;
- contract registry;
- `remote_operations.py`;
- REST typed dispatch tests;
- data-minimization conventions;
- current tool error/result conventions;
- any existing Contact-related helpers already used by email recipient resolution.

Also re-check effective runtime metadata for:

- `Customer`;
- `Contact`;
- `Contact Email`;
- `Contact Phone`;
- `Dynamic Link`.

If the checked-out source/runtime behavior materially differs from Task 56, document the mismatch before changing the design.

Do not silently redesign the capability.

---

## 5. Allowed production changes

Add or modify only what is necessary for this bounded Contact capability.

Expected integration points from Task 56 are:

```text
mcp_erpnext/contracts/masters/contact.py
or an equivalent Customer-scoped Contact contract module

mcp_erpnext/services/masters/customer_contact.py
mcp_erpnext/tools/masters/customer_contact.py

mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py

focused tests
relevant generated/catalog documentation only if required by existing project convention
```

These paths are recommendations, not permission to duplicate existing architecture.

If an equivalent module/pattern already exists, reuse it.

### Allowed supporting changes

Small reusable helpers may be added only when:

1. the same logic is genuinely shared;
2. they do not broaden public mutation scope;
3. they follow current project architecture.

---

## 6. Explicitly forbidden changes

Do not implement any of the following in Task 57:

- arbitrary Contact CRUD;
- arbitrary Dynamic Link mutation;
- public `link_doctype`;
- Supplier Contact support;
- Purchase profile Contact tools;
- Accounts profile Contact tools;
- Contact delete;
- Contact unlink;
- Contact merge;
- Contact bulk operations;
- clear Customer primary Contact;
- existing Contact promotion to primary;
- Contact name/detail update tools;
- email-row replacement/removal;
- phone-row replacement/removal;
- secondary email/phone management;
- portal User creation/link management;
- Google Contact behavior;
- direct SQL writes;
- direct child-table SQL writes;
- `ignore_permissions=True` for the public business mutation;
- raw Frappe Document dumps in tool output;
- caller-controlled approval-policy modes;
- caller-controlled arbitrary custom Contact fields;
- a new MCP DocType or shadow Contact table;
- widening generic Customer lifecycle updates as a substitute for this capability.

Do not fix the generic lifecycle `fieldtype == "Read Only"` boundary issue in this task unless a test proves this new implementation cannot be completed without that change.

That lifecycle hardening is a separate task.

---

# 7. Public tool surface

Task 57 must expose exactly this bounded capability set in the Sales profile.

## 7.1 `search_contacts`

Read-only.

Purpose:

- select an existing Contact;
- identify a Contact already linked to a Customer;
- perform bounded duplicate/reuse discovery.

Do not create a broad Contact listing API.

## 7.2 `prepare_customer_contact`

Mutation preparation only.

One business intent with:

```text
mode = "create" | "link"
```

It must perform:

- reference resolution/validation;
- permission checks;
- duplicate/link checks;
- stale-state capture;
- bounded preview;
- approval-store creation.

It must not write a Contact or Customer business record.

## 7.3 `confirm_customer_contact`

Mutation confirmation only.

It must:

- consume the shared approval token;
- call `claim_for_confirm_write`;
- reload fresh state;
- recheck permission;
- recheck duplicates/link state;
- recheck stale state/fingerprint;
- perform exactly the approved native Contact operation;
- commit only at the existing outer confirmation boundary;
- roll back on failure.

Do not add separate public tools for:

```text
create_contact
link_contact
make_contact_primary
mutate_dynamic_link
```

The mutation surface stays one bounded Customer-linked business capability.

---

# 8. `search_contacts` contract

## 8.1 Input

Use typed public contracts consistent with current project conventions.

Conceptual input:

```text
query: non-empty bounded string
customer: optional exact Customer reference
match: optional enum {
    auto,
    name,
    email,
    phone
}
limit: bounded positive integer
offset: bounded non-negative integer
```

Use the project's normal reference structure if one already exists.

Do not invent an inconsistent reference contract.

## 8.2 Search rules

### With Customer context

After confirming Customer read permission:

- Customer-scoped name/full-name search may be fuzzy/bounded;
- exact email search is allowed;
- exact normalized phone search is allowed;
- exact Contact name is allowed;
- returned Contacts must satisfy normal Contact read permission.

### Without Customer context

To prevent broad personal-data enumeration:

- Contact `name` search must be exact;
- email search must be exact;
- phone search must be exact/normalized;
- unrestricted fuzzy global person-name search is not allowed.

## 8.3 Permission behavior

Use normal Frappe permission-aware reads.

Do not use:

```python
ignore_permissions=True
```

For Customer-scoped search require:

```text
Customer read
AND
Contact read for each returned Contact
```

## 8.4 Search result projection

Return only what is needed for selection:

```text
doctype = "Contact"
name
full_name
company_name? 
email_id?
mobile_no?
phone?
is_primary_contact
linked_to_target_customer
other_party_link_count
```

Pagination metadata may include:

```text
count
limit
offset
```

Do not return:

- all `links`;
- unrelated linked party names;
- addresses;
- comments;
- communications;
- User fields;
- Google fields;
- CRM Deal rows;
- full child-table internals;
- raw Contact JSON;
- framework/system fields.

`other_party_link_count` is allowed.

Unrelated party names are not.

---

# 9. `prepare_customer_contact` contract

## 9.1 Conceptual input

```text
customer: {
    doctype: "Customer",
    name: exact_customer_name
}

mode: "create" | "link"

existing_contact: {
    doctype: "Contact",
    name: exact_contact_name
} | null

new_contact: {
    first_name?,
    middle_name?,
    last_name?,
    company_name?,
    email?,
    mobile?
} | null

make_primary: bool = false
```

Adapt field names to the project's established typed-contract conventions.

## 9.2 Server-fixed doctypes

The public caller must not choose arbitrary doctypes.

The implementation fixes:

```text
customer.doctype = "Customer"
existing_contact.doctype = "Contact"
Dynamic Link.link_doctype = "Customer"
```

Reject or structurally prevent arbitrary values.

---

# 10. Mode rules

## 10.1 `mode=create`

Require:

```text
new_contact != null
existing_contact == null
```

The new Contact must be linked to exactly the target Customer through the public operation.

The public contract must require enough bounded identity to avoid creating a nameless Contact.

Require at least one supported identity shape such as:

```text
first_name
OR
last_name
OR
company_name
```

Use the exact capability rule decided from the current native naming behavior.

Email/mobile alone must not silently become an anonymous public Contact unless the current audited design explicitly supports that and tests prove the intended naming result.

## 10.2 `mode=link`

Require:

```text
existing_contact != null
new_contact == null
make_primary == false
```

The existing Contact must be explicitly selected by exact Contact reference.

Do not auto-link a Contact merely because email/name/mobile looks similar.

---

# 11. New Contact payload construction

For `mode=create`, construct only a bounded native Contact payload.

Conceptual structure:

```text
Contact
  first_name?
  middle_name?
  last_name?
  company_name?

  email_ids:
    - email_id: <email>
      is_primary: 1

  phone_nos:
    - phone: <mobile>
      is_primary_mobile_no: 1
      [is_primary_phone only if intentionally required by audited native semantics]

  links:
    - link_doctype: "Customer"
      link_name: <resolved exact Customer>

  is_primary_contact:
    explicit safe value only
```

Do not accept these public inputs:

```text
email_ids
phone_nos
links
email_id
phone
mobile_no
full_name
user
sync_with_google_contacts
google_contacts
arbitrary custom fields
owner
modified
creation
docstatus
```

The server owns child-row construction.

Native Contact validation must derive projection fields.

---

# 12. `make_primary` V1 rule

Default:

```text
make_primary = false
```

Task 57 may support `make_primary=true` only for:

```text
mode=create
```

and only when the newly created Contact's public operation has exactly one target party link:

```text
Customer -> target Customer
```

It must not be available for:

```text
mode=link
```

It must not promote an already-existing multi-party Contact.

If `make_primary=true` is supported:

1. create the Contact through normal Contact insert;
2. ensure native primary Contact validation runs;
3. update the Customer through a normal Customer document write so:
   - `customer_primary_contact` points to the created Contact;
   - Customer fetch projections are refreshed through the normal native path;
4. keep Contact + Customer changes in the same outer transaction;
5. rollback the entire operation if either document write fails.

Do not use `frappe.db.set_value` as the MCP business mutation shortcut.

If the implementation team finds that safe compound primary behavior cannot be completed without broadening scope, return the primary option as unsupported and implement create/link without primary.

Do not weaken the rest of Task 57 to force this optional path.

---

# 13. Existing Contact linking behavior

For `mode=link`:

1. resolve exact Customer;
2. resolve exact Contact;
3. confirm normal permissions;
4. check:

```python
contact.has_link("Customer", customer.name)
```

### If already linked

Return success:

```text
status = linked
idempotent = true
```

Do not save and do not add a duplicate Dynamic Link.

### If not linked

Append exactly:

```text
{
    "link_doctype": "Customer",
    "link_name": customer.name
}
```

Then save:

```python
contact.save(ignore_permissions=False)
```

Do not mutate Dynamic Link child records directly.

Do not expose arbitrary relationship fields to the caller.

---

# 14. Duplicate/reuse policy

Task 57 must not implement automatic merge or identity guessing.

## 14.1 Exact already-linked match

If the Contact is already linked to the Customer:

- treat link intent as idempotent;
- do not duplicate the link.

## 14.2 New Contact duplicate suspicion

Before preparing a new Contact, perform bounded visible duplicate checks for:

- exact normalized email;
- exact normalized phone;
- exact permitted identity evidence where appropriate.

If an exact visible Contact match exists but is not already linked to the target Customer:

```text
CONTACT_DUPLICATE_SUSPECTED
```

Return a minimal candidate selection result.

Do not:

- automatically reuse;
- automatically link;
- merge;
- copy data;
- expose unrelated party names.

## 14.3 Same human-readable name only

Same `full_name` is not sufficient proof of identity.

Do not silently reuse based only on name.

Contact autoname suffixing is not a duplicate policy.

---

# 15. Permission requirements

Use runtime Frappe permissions.

Do not hard-code site roles.

## Search

Customer-scoped search:

```text
Customer read
Contact read
```

## Create new Contact for Customer

Minimum:

```text
Customer read
Contact create
```

If applying primary state:

```text
Customer write
Contact create/write as required by native path
```

## Link existing Contact

Minimum:

```text
Customer read
Contact read
Contact write
```

Customer write is required only if the approved operation also modifies Customer state.

Task 57 link mode does not modify Customer primary state.

---

# 16. Approval architecture

Reuse the existing shared approval system.

Do not add a Contact-specific approval store.

`prepare_customer_contact` must store an approval-bound payload using the current project pattern.

`confirm_customer_contact` must use:

```text
ApprovalStore.claim_for_confirm_write(...)
```

or the current equivalent canonical method.

Never trust:

```text
confirm=true
```

as standalone authorization.

Never expose a caller-controlled approval mode.

The approval must remain bound to:

- site;
- authenticated/verified user;
- profile;
- action;
- target Customer;
- operation mode;
- exact Contact identity or exact new Contact payload;
- relevant stale-state fingerprint.

---

# 17. Stale-state / fingerprint requirements

## Create mode

Bind enough state to detect meaningful changes between prepare and confirm.

At minimum:

- Customer exact name;
- Customer `modified`;
- Customer permission/existence state;
- intended new Contact data;
- duplicate candidates considered during prepare;
- current relevant Customer primary state if `make_primary=true`.

At confirm:

- reload Customer;
- recheck permissions;
- re-run bounded exact duplicate checks;
- reject if a newly appearing exact duplicate changes the approved decision.

## Link mode

Bind:

- Customer exact name;
- Customer `modified`;
- Contact exact name;
- Contact `modified`;
- current `has_link(Customer, customer)` state;
- relevant permission state.

At confirm:

- reload both documents;
- recheck permissions;
- recheck `has_link`.

If the exact desired link now already exists, return idempotent success when doing so is consistent with the approved operation.

Do not append a duplicate.

---

# 18. Prepare behavior

`prepare_customer_contact` must be non-mutating.

It must not:

- insert Contact;
- save Contact;
- save Customer;
- add Dynamic Link rows to a database document;
- commit;
- use DB writes for preview.

It may build an unsaved Contact document if useful for safe native validation, provided no write occurs.

The preview must be bounded and human-understandable.

Example conceptual create preview:

```text
Customer: ABC Pvt Ltd
Action: Create and link new Contact
Contact: Amit Shah
Email: amit@example.com
Mobile: 999...
Relationship: Contact -> Customer ABC Pvt Ltd
Make primary: No
Duplicate check: No exact visible duplicate found
```

Example link preview:

```text
Customer: ABC Pvt Ltd
Action: Link existing Contact
Contact: Amit Shah-ABC
Already linked: No
Other linked party count: 1
Primary change: None
```

Do not expose raw internal payloads to the LLM/user when a bounded semantic preview is sufficient.

---

# 19. Confirm behavior

Confirm must:

1. validate approval token;
2. claim it exactly once;
3. reload fresh references;
4. recheck normal permissions;
5. recheck stale state;
6. recheck duplicate/link state;
7. perform exactly one approved business intent;
8. allow native hooks/controllers to execute;
9. commit once at the existing outer service boundary;
10. rollback the complete transaction on any failure;
11. return a bounded typed result.

No nested helper in this feature should independently commit.

---

# 20. Result contract

Use existing typed result/interaction conventions.

Successful create result should conceptually contain:

```text
status: "created"
customer:
    doctype
    name

contact:
    doctype
    name
    full_name
    company_name?
    email_id?
    mobile_no?
    phone?
    is_primary_contact
    linked_to_target_customer
    other_party_link_count

idempotent: false

primary:
    requested
    applied
    customer_primary_contact_updated
```

Successful link result:

```text
status: "linked"
customer: bounded reference
contact: bounded Contact projection
idempotent: true | false
primary: null
```

Do not return the full Contact document.

---

# 21. Error/interaction semantics

Reuse current project error and interaction types whenever possible.

Required semantic conditions include:

```text
CUSTOMER_NOT_FOUND
CONTACT_NOT_FOUND
PERMISSION_DENIED
CONTACT_DUPLICATE_SUSPECTED
CONTACT_INVALID_EMAIL
CONTACT_INVALID_PHONE
CONTACT_PRIMARY_UNSUPPORTED
CONTACT_STALE_STATE
CONTACT_LINK_STALE_STATE
CONFIRMATION_REQUIRED
```

If the existing project has equivalent canonical codes, use them instead of duplicating semantically identical ones.

Unexpected native validation/hook failures must use the existing safe `ToolError` mechanism:

- no raw traceback;
- no SQL;
- no unrelated Contact/Customer data;
- include a safe server reference if that is the current project convention.

---

# 22. Profile exposure

Register this capability only in:

```text
sales
```

Expected public tools:

```text
search_contacts
prepare_customer_contact
confirm_customer_contact
```

Do not expose them in:

```text
purchase
accounts
```

Do not create a generic Contact profile.

---

# 23. stdio / HTTP / REST parity

The existing MCP architecture requires one business implementation across transports.

Ensure:

- stdio registration exposes the same typed tools;
- streamable HTTP/MCP registration exposes the same tools;
- REST/remote operation dispatch uses the same service layer;
- no transport contains separate business logic;
- contracts/registry metadata is complete;
- remote operation allowlisting is complete.

Do not create a REST-only or MCP-only Contact behavior.

---

# 24. Data minimization and security

Contact data includes personal/business communication information.

The model/client should receive only the minimum required for:

- resolution;
- duplicate selection;
- preview;
- approved result.

Mandatory constraints:

- normal Frappe permission checks;
- no unrelated party names;
- no full Dynamic Link list;
- no Contact comments/communications;
- no raw CRM Deal data;
- no User linkage details;
- no addresses unless a future capability explicitly requires them;
- no raw child row metadata beyond the bounded values required for this flow;
- no `ignore_permissions=True`;
- no raw database mutation.

If CRM validation hooks update linked CRM Deal snapshots as a native side effect, allow the native hook to run in the same transaction, but do not expose those Deal records in tool results.

---

# 25. Existing Customer creation must remain unchanged

Do not replace or split the current:

```text
prepare_customer
confirm_customer
```

nested initial Contact behavior.

Regression expectations:

- Customer name only still creates no Contact;
- Customer + nested Contact details still follows ERPNext native Customer creation behavior;
- email-only/mobile-only initial Contact behavior remains consistent with installed source;
- current Customer duplicate checks remain unchanged;
- current approval behavior remains unchanged.

Task 57 adds the missing **post-Customer-creation Contact flow**.

It does not replace the established initial Customer creation path.

---

# 26. Email capability interoperability

The existing email service already resolves native linked Contacts.

Task 57 must not rewrite email-recipient logic unless a regression proves an integration defect.

Verify:

- newly linked Contact can become an eligible native linked Contact candidate where current email resolution permits;
- unrelated Contact email is never selected;
- Contact permissions remain respected;
- existing Quotation/Sales Order/Sales Invoice copied recipient snapshots are not rewritten.

If a newly created Contact is made Customer primary, verify Customer-native recipient/default behavior after Customer state is updated consistently.

---

# 27. Sales transaction interoperability

Do not add Contact-specific writes to:

- Quotation;
- Sales Order;
- Sales Invoice.

Existing transactions store copied Contact/email/mobile snapshots.

Task 57 must not rewrite historical transaction fields when Contact is added later.

Only future native defaults may see the newly linked/primary Contact according to ERPNext behavior.

---

# 28. Required tests

Implementation is incomplete until focused tests cover the following.

## 28.1 Existing Customer creation regression

Test:

- Customer + nested Contact still creates/uses the native initial Contact path;
- Customer name only does not create Contact;
- email-only Customer creation remains valid per installed native behavior;
- mobile-only Customer creation remains valid per installed native behavior;
- missing Contact create permission remains bounded;
- failure in native Contact creation rolls back Customer creation.

## 28.2 `search_contacts`

Test:

- Customer-scoped name search;
- Customer-scoped exact email;
- Customer-scoped exact phone;
- exact Contact name;
- global exact email;
- global exact phone;
- global fuzzy-name enumeration rejected/not supported;
- Customer read permission filtering;
- Contact read permission filtering;
- bounded result projection;
- `other_party_link_count` does not reveal party names;
- pagination/hard limit.

## 28.3 Create new Contact

Test:

- valid Contact created;
- exactly one target Customer Dynamic Link;
- native Contact autoname used;
- email child row created correctly;
- mobile child row created correctly;
- parent Contact projections derived natively;
- no public arbitrary Dynamic Link accepted;
- invalid email rejected;
- invalid phone rejected;
- missing identity rejected by capability;
- Customer not found;
- Customer read denied;
- Contact create denied;
- exact duplicate email suspected;
- exact duplicate phone suspected;
- same name alone does not auto-reuse;
- no write happens during prepare.

## 28.4 Link existing Contact

Test:

- valid existing Contact links through normal Contact save;
- exactly one Dynamic Link added;
- already-linked result is idempotent;
- duplicate Dynamic Link is never added;
- Customer not found/read denied;
- Contact not found;
- Contact read/write denied;
- Contact linked to another Customer remains linkable only after explicit selection;
- unrelated party names are not exposed;
- Contact linked to Supplier remains valid;
- existing Contact is not promoted to primary.

## 28.5 Primary behavior, if implemented

Test:

- `make_primary=false` leaves Customer primary unchanged;
- `make_primary=true` accepted only for create mode;
- `make_primary=true` rejected for link mode;
- new Contact primary flag is native-consistent;
- Customer `customer_primary_contact` points to new Contact;
- Customer fetch projections refresh through native Customer save;
- prior Customer primary is handled according to native Contact validation;
- Contact + Customer changes rollback atomically on second-step failure.

If safe primary behavior is not implemented in this task, test that `make_primary=true` returns the documented unsupported state instead of silently changing anything.

## 28.6 Approval

Test:

- prepare creates shared pending approval;
- confirm requires valid shared approval;
- `confirm=true` alone cannot self-authorize;
- wrong user rejected;
- wrong site rejected;
- wrong profile/action rejected;
- expired token rejected;
- replay rejected;
- `confirm=false` performs no write.

## 28.7 Stale/concurrency

Test:

- Customer modified after prepare;
- Contact modified after prepare;
- Contact deleted after prepare;
- Customer deleted after prepare;
- exact duplicate appears after create prepare;
- target link added after link prepare;
- already-added exact link resolves idempotently only under approved rules;
- no duplicate link under repeated/racing final state.

## 28.8 Transport/profile

Test:

- Sales exposes all three intended tools;
- Purchase does not;
- Accounts does not;
- stdio/MCP registration complete;
- REST remote operation registration complete;
- typed contract registry complete;
- same service result across transports.

## 28.9 Data leak regression

Assert tool outputs do not expose:

- unrelated Dynamic Link party names;
- Contact raw JSON;
- Contact User linkage;
- addresses;
- comments;
- communications;
- CRM Deal payloads;
- arbitrary child metadata.

## 28.10 Email/transaction interoperability

Test:

- newly linked valid Contact respects current recipient-resolution rules;
- unrelated Contact cannot be used as Customer recipient;
- existing Quotation/Sales Order/Sales Invoice Contact snapshots remain unchanged.

---

# 29. Testing rules

Use the repository's existing test framework and patterns.

Do not add live production-site mutation tests.

If an isolated test site/database integration boundary already exists, use it according to project convention.

Otherwise:

- unit/service tests;
- mocked/isolated Frappe document behavior where already established;
- focused native integration tests only in the proper test environment.

Run the narrowest relevant test groups first.

Then run the broader affected Sales/profile/REST suites.

Document:

- exact commands;
- pass/fail counts;
- any pre-existing failures;
- any newly introduced failures.

Do not "fix" unrelated pre-existing approval failures inside this task without proving Task 57 caused them.

---

# 30. Acceptance criteria

Task 57 is complete only when all of the following are true.

### Capability

- [ ] `search_contacts` exists and is bounded.
- [ ] Customer-scoped Contact search works.
- [ ] global broad personal-name enumeration is not exposed.
- [ ] `prepare_customer_contact` exists.
- [ ] `confirm_customer_contact` exists.
- [ ] new Contact can be created for an existing Customer.
- [ ] existing Contact can be explicitly linked to a Customer.
- [ ] already-linked Contact is idempotent.
- [ ] arbitrary Dynamic Link mutation is impossible through public contracts.

### Native correctness

- [ ] normal `Contact.insert(ignore_permissions=False)` used for creation.
- [ ] normal `Contact.save(ignore_permissions=False)` used for existing-link mutation.
- [ ] Contact email/phone child rows are authoritative.
- [ ] Contact projections are native-derived.
- [ ] Frappe/CRM Contact validation/hooks are not bypassed.
- [ ] no direct SQL mutation.
- [ ] no MCP shadow Contact model.

### Approval/atomicity

- [ ] prepare is non-mutating.
- [ ] shared approval store reused.
- [ ] `claim_for_confirm_write` or canonical equivalent used.
- [ ] confirm-time stale/permission/duplicate checks exist.
- [ ] exactly one outer commit.
- [ ] complete rollback on failure.
- [ ] approval replay cannot execute another write.

### Scope safety

- [ ] Sales-only registration.
- [ ] no Supplier/Purchase Contact capability.
- [ ] no Contact update/delete/unlink/merge.
- [ ] existing Contact primary promotion unavailable.
- [ ] existing Customer creation flow unchanged.
- [ ] generic lifecycle not broadened to imitate Contact management.

### Security/data minimization

- [ ] normal Frappe permissions everywhere.
- [ ] no `ignore_permissions=True` business mutation.
- [ ] no unrelated linked party names returned.
- [ ] no raw Contact document output.
- [ ] no broad global Contact enumeration.
- [ ] duplicate candidates are minimally projected.

### Verification

- [ ] required focused tests pass.
- [ ] affected existing Customer tests pass.
- [ ] profile tests pass.
- [ ] REST/remote operation tests pass.
- [ ] data-leak assertions pass.
- [ ] any pre-existing failures are separately documented.

---

# 31. Expected end-to-end results

## Scenario A — existing Customer, new person

Input intent:

```text
Add Amit Shah to ABC Pvt Ltd with amit@example.com and 999...
```

Expected flow:

```text
resolve Customer
    ->
bounded duplicate search
    ->
prepare_customer_contact(mode=create)
    ->
preview + shared approval
    ->
confirm_customer_contact
    ->
revalidate
    ->
native Contact.insert()
    ->
Customer Dynamic Link exists
    ->
bounded result
```

Expected result:

- new native Contact exists;
- Contact is linked to ABC Pvt Ltd;
- email/mobile are stored in Contact child rows;
- no duplicate Customer relationship row;
- no unrelated party data exposed.

## Scenario B — existing Customer, existing Contact

Input intent:

```text
Link existing Amit Shah to ABC Pvt Ltd
```

Expected flow:

```text
search/select exact Contact
    ->
prepare_customer_contact(mode=link)
    ->
preview + approval
    ->
confirm
    ->
revalidate
    ->
has_link()
    ->
append Customer Dynamic Link if absent
    ->
Contact.save()
```

Expected result:

- Contact remains the same native record;
- Customer link is added once;
- no primary promotion occurs;
- already-linked retry is idempotent.

## Scenario C — later email change

Input intent:

```text
Change Amit's email to accounts@abc.com
```

Expected Task 57 result:

```text
Not implemented by this task.
```

This belongs to the next dedicated Contact detail/email/phone mutation task.

Do not route this through generic Customer update.

---

# 32. Deliverable report

After implementation, create:

```text
docs/inspect/CUSTOMER_LINKED_CONTACT_V1_IMPLEMENTATION_REPORT.md
```

The report must include:

1. repository branch and HEAD before/after;
2. files changed;
3. final public tools;
4. final contracts;
5. exact permission model;
6. duplicate/reuse behavior;
7. approval/fingerprint behavior;
8. create flow;
9. existing-link flow;
10. primary behavior implemented or explicitly deferred;
11. result/data-minimization fields;
12. transport/profile registration;
13. all tests added/changed;
14. exact test commands and results;
15. pre-existing failures separately identified;
16. deviations from Task 56/Task 57 and why;
17. no-production-data-mutation confirmation.

Do not mark the task complete merely because tools register.

The end-to-end write paths and tests must pass.

---

# 33. Limitations intentionally retained after Task 57

After this task, the following remain intentionally unsupported:

- editing Contact name/designation/details;
- adding/replacing/removing Contact emails;
- adding/replacing/removing Contact phones;
- promoting an existing linked Contact to primary;
- unlinking Contact;
- deleting Contact;
- merging Contacts;
- Supplier-linked Contact capability;
- arbitrary party links;
- portal User management;
- bulk Contact operations;
- generic lifecycle `Read Only` hardening.

These are not Task 57 defects.

They are explicit scope boundaries.

---

# 34. Exact next task

After Task 57 implementation report is reviewed, the next capability task should be:

```text
Task 58 — Customer-Scoped Contact Detail and Email/Phone Update Audit
```

Task 58 should first audit/design the safe mutation contract for:

- Contact name/detail edits;
- primary/secondary email child rows;
- primary phone/mobile child rows;
- add/replace/remove semantics;
- child-row stale fingerprints;
- Customer stored projection refresh behavior;
- CRM Contact validation side effects;
- primary Contact implications.

Do **not** begin Task 58 implementation as part of Task 57.
