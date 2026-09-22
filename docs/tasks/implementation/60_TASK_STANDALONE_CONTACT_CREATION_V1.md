# Task 60 — Standalone Contact Creation V1

## Status

**Implementation task**

Task 59 audit is complete and is the source-of-truth design for this implementation.

Required source documents:

```text
docs/inspect/STANDALONE_CONTACT_MASTER_CAPABILITY_AUDIT.md
docs/inspect/CONTACT_MASTER_NATIVE_FLOW_AND_CAPABILITY_AUDIT.md
docs/inspect/CUSTOMER_LINKED_CONTACT_V1_IMPLEMENTATION_REPORT.md
docs/inspect/CUSTOMER_SCOPED_CONTACT_DETAIL_EMAIL_PHONE_UPDATE_AUDIT.md
```

This task implements only the standalone Contact creation capability approved by Task 59.

Do not broaden the scope.

---

# 1. Objective

Implement a bounded, Sales-profile, native Frappe Contact creation capability for genuinely standalone Contact intent.

The new public tools are:

```text
prepare_contact
confirm_contact
```

The capability must allow a user to create a native Contact without requiring:

```text
Customer
Supplier
Dynamic Link
party-primary state
```

Example:

```text
User:
"Create contact Amit Shah with amit@example.com and +91..."
```

Expected flow:

```text
prepare_contact
    ->
validate bounded standalone Contact input
    ->
permission-aware visible duplicate checks
    ->
non-mutating preview
    ->
shared approval
    ->
confirm_contact
    ->
claim approval
    ->
revalidate permission + duplicates
    ->
Contact.insert(ignore_permissions=False)
    ->
native validation/hooks
    ->
one outer commit
    ->
bounded Contact result
```

This capability must remain distinct from Task 57 Customer-linked Contact creation.

---

# 2. Business routing boundary

The Agent/client must route these intents differently.

## Standalone Contact intent

```text
"Create contact Amit Shah"
"Create Amit Shah, customer not known yet"
"Create Amit now; I'll assign him later"
```

Use:

```text
prepare_contact
confirm_contact
```

## Customer-known Contact intent

```text
"Create Amit Shah as a contact for ABC Pvt Ltd"
"Add Amit to ABC Pvt Ltd"
```

Use existing Task 57:

```text
prepare_customer_contact(mode=create)
confirm_customer_contact
```

Do not create a standalone Contact first and then perform a second link write when the Customer relationship is already part of the original user intent.

## Existing Contact linking intent

```text
"Link Amit Shah to ABC Pvt Ltd"
```

Use:

```text
search_contacts
prepare_customer_contact(mode=link)
confirm_customer_contact
```

Task 60 must not duplicate Customer-linking logic.

---

# 3. Frozen Task 59 decisions

Treat the following as implementation constraints unless current checked-out source proves a material incompatibility.

## 3.1 Standalone Contact creation is valid

A native Frappe Contact may exist with:

```text
no Dynamic Links
no Customer
no Supplier
no email
no phone
```

The public MCP contract is intentionally stricter than framework minimums to prevent nameless/unsearchable Contact records.

## 3.2 Minimum identity rule

At least one of the following must be non-empty after trimming:

```text
first_name
last_name
company_name
```

Email/mobile/phone alone are not sufficient identity.

## 3.3 V1 public fields

V1 may accept only:

```text
first_name
middle_name
last_name
company_name
designation
department
email
mobile
phone
```

## 3.4 Communication limits

V1 supports at most:

```text
one email
one mobile
one phone
```

No multi-email or multi-phone creation input.

## 3.5 No relationship input

Public caller must not provide:

```text
links
link_doctype
link_name
is_primary_contact
```

Standalone Contact must have no party Dynamic Link.

## 3.6 Dedicated public pair

Use:

```text
prepare_contact
confirm_contact
```

Do not make `customer` nullable in `prepare_customer_contact`.

## 3.7 Sales-only

Expose standalone Contact creation only in:

```text
sales
```

Do not register in:

```text
purchase
accounts
generic/core
```

## 3.8 Existing search reuse

Reuse existing:

```text
search_contacts
```

Do not add a second Contact search tool.

Do not broaden global fuzzy person-name search.

---

# 4. Mandatory pre-implementation inspection

Before changing production code, inspect the current checkout.

At minimum inspect:

```text
mcp_erpnext/contracts/masters/contact.py
mcp_erpnext/services/masters/customer_contact.py
mcp_erpnext/tools/masters/customer_contact.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
mcp_erpnext/tests/test_customer_contact.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_rest_backend.py
mcp_erpnext/tests/test_tool_registration.py
docs/TOOLS.md
```

Also inspect the current implementations of:

```text
ApprovalStore
claim_for_confirm_write
InteractionDirective
PublicContractModel
ToolError
stable_fingerprint
safe error mapping
profile registration
REST fixed typed dispatch
```

Inspect the installed Contact source and effective metadata before implementation:

```text
Contact
Contact Email
Contact Phone
CRM Contact override/hooks
ERPNext Contact hooks
```

Do not assume Task 59's source offsets still match if the checkout changed.

If current source materially differs, document the mismatch before altering the design.

---

# 5. Allowed production changes

Expected integration points:

```text
mcp_erpnext/contracts/masters/contact.py
mcp_erpnext/services/masters/contact.py
or a clearly named equivalent standalone Contact service

mcp_erpnext/tools/masters/contact.py
or the existing Contact tool module if that is cleaner and non-duplicative

mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
docs/TOOLS.md
focused tests
```

Reuse existing Contact reference/projection/result models where appropriate.

Do not duplicate a model/helper solely because the new operation is standalone.

---

# 6. Explicitly forbidden changes

Do not implement:

- Contact update;
- Contact delete;
- Contact merge;
- Contact rename;
- Contact unlink;
- arbitrary Dynamic Link creation;
- Customer linking changes;
- Supplier linking;
- Purchase Contact tools;
- Accounts Contact tools;
- generic Contact CRUD;
- generic create-master tooling;
- bulk Contact creation;
- import functionality;
- raw child-table input;
- existing Contact primary promotion;
- Customer primary changes;
- Customer projection refresh;
- historical transaction updates;
- portal User management;
- Google Contacts features;
- arbitrary custom fields;
- broad global fuzzy Contact search;
- hidden Contact enumeration;
- direct SQL Contact creation;
- direct child-table SQL mutation;
- `ignore_permissions=True` business writes.

Do not modify Task 57 production behavior unless a blocker is proven.

Task 57 transaction hardening is separate.

---

# 7. Public contract

Add typed models consistent with existing `PublicContractModel`.

Conceptual contract:

```text
ContactCreateInput {
  first_name?: string
  middle_name?: string
  last_name?: string
  company_name?: string
  designation?: string
  department?: string
  email?: string
  mobile?: string
  phone?: string
}
```

Prepare input:

```text
PrepareContactInput {
  contact: ContactCreateInput
}
```

Confirm input:

```text
ConfirmContactInput {
  approval_token: string
  confirm: bool
}
```

Use exact project naming/style conventions.

All public models must reject unknown fields.

---

# 8. Public fields that must be rejected

Caller must not be able to supply:

```text
name
full_name
email_id
mobile_no
links
link_doctype
link_name
email_ids
phone_nos
is_primary_contact
user
owner
creation
modified
docstatus
idx
image
status
sync_with_google_contacts
google_contacts
arbitrary custom fields
```

If `phone` is accepted publicly, it is a semantic input that becomes a Contact Phone child row.

It must not be interpreted as direct assignment to the read-only parent `Contact.phone`.

---

# 9. Identity validation

Normalize accepted string fields by the project's current safe trimming convention.

At least one must be non-empty:

```text
first_name
last_name
company_name
```

If all three are empty:

```text
CONTACT_INVALID_IDENTITY
```

with the project's normal input/interaction directive.

Do not permit:

```text
email only
mobile only
phone only
```

to create a Contact.

`middle_name`, `designation`, and `department` do not satisfy the identity rule.

---

# 10. Email validation and construction

V1 accepts at most one semantic:

```text
email
```

Trim whitespace.

Use the existing project/Frappe email validation boundary already used by Customer-linked Contact creation where safe.

Reject:

- invalid email;
- comma-separated/multiple email values;
- empty normalized supplied value if the contract treats it as present.

Recommended semantic error:

```text
CONTACT_INVALID_EMAIL
```

Construct exactly one child row when email is present:

```text
email_ids = [
    {
        "email_id": <email>,
        "is_primary": 1,
    }
]
```

Do not publicly expose or accept `email_ids`.

Let native Contact validation derive:

```text
Contact.email_id
```

during confirm.

---

# 11. Mobile and phone construction

V1 accepts:

```text
mobile?
phone?
```

Use existing Frappe/project phone validation.

When `mobile` exists, construct one Contact Phone child row:

```text
{
    "phone": <mobile>,
    "is_primary_mobile_no": 1,
    "is_primary_phone": 0
}
```

When `phone` exists, construct one separate Contact Phone child row:

```text
{
    "phone": <phone>,
    "is_primary_phone": 1,
    "is_primary_mobile_no": 0
}
```

If both are supplied:

```text
two separate child rows
```

Do not construct one row with both flags.

Do not let caller provide flags.

Do not let caller provide raw `phone_nos`.

Let native Contact validation derive:

```text
Contact.phone
Contact.mobile_no
```

during confirm.

Use semantic error:

```text
CONTACT_INVALID_PHONE
```

or the current equivalent project code.

---

# 12. Contact relationship state

Standalone creation must not fabricate any Dynamic Link.

Preferred payload:

```text
omit "links"
```

Do not create:

```text
links=[]
```

unless current Frappe/document construction requires it for a concrete reason.

Never add:

```text
Customer
Supplier
Lead
Prospect
CRM Deal
or any other link
```

as part of standalone creation.

Do not set:

```text
is_primary_contact
```

Public caller cannot provide it.

Native/default false state remains authoritative.

---

# 13. Prepare must be strictly non-mutating

`prepare_contact` must not:

- insert Contact;
- save Contact;
- write child rows;
- commit;
- write Dynamic Link;
- update CRM data;
- create User;
- execute any business DB mutation.

Most importantly:

**Do not call the full hook-bearing Contact validation chain during prepare.**

Do not call:

```python
contact.run_method("validate")
```

or any equivalent path that dispatches Contact validate `doc_events`.

Task 59 confirmed installed CRM:

```text
Contact.validate -> crm.api.contact.validate
```

can write CRM Deal snapshot fields.

That behavior is valid on real Contact save/insert but prohibited during prepare.

---

# 14. Safe prepare-time validation

Prepare should use only non-writing validation/derivation.

At minimum:

```text
typed contract validation
identity rule
trim/normalize public inputs
email validation
phone validation
deterministic full-name preview derivation
deterministic child-row construction
create-permission preflight
permission-visible duplicate lookup
```

If a native helper is used during prepare, first prove that it:

```text
does not call save
does not insert
does not commit
does not run doc_events
does not use ignore_permissions
does not write DB state
```

Otherwise do not use it in prepare.

---

# 15. Full-name preview

The preview should follow the installed Contact naming/full-name semantics.

Conceptually:

```text
first_name + middle_name + last_name
```

with native-style spacing/trimming.

If no person-name component exists:

```text
company_name
```

The preview may return:

```text
full_name
```

but this is a derived preview.

Do not promise the final document `name` as an exact value if collision suffixing may occur at insert time.

Preview should distinguish:

```text
expected_full_name
```

from:

```text
created Contact.name
```

if current contracts benefit from that distinction.

---

# 16. Duplicate lookup

Standalone creation must perform bounded, permission-aware duplicate checks.

Do not implement global fuzzy person search.

Only use normal Contact read permission.

Candidate duplicate signals:

```text
exact/case-insensitive email
normalized phone/mobile
```

Same full name alone is not a duplicate blocker.

Exact document naming collision alone is not a duplicate decision.

Native Contact autoname may suffix collisions.

---

# 17. Email duplicate policy

For a supplied email:

- compare visible permitted Contact email values;
- use case-insensitive comparison for duplicate suspicion;
- do not claim native/global uniqueness;
- do not merge;
- do not silently reuse.

If exact visible duplicate exists:

```text
CONTACT_DUPLICATE_SUSPECTED
```

Return minimal permitted candidates using the existing bounded Contact projection.

Do not expose unrelated linked party names.

Do not disclose hidden Contact existence.

---

# 18. Phone/mobile duplicate policy

For supplied `mobile` or `phone`:

- use Task 57's existing bounded normalization/comparison helper if appropriate;
- treat normalization as comparison only;
- do not rewrite stored formatting;
- do not claim Frappe globally normalizes phone data.

If a visible exact-normalized match exists:

```text
CONTACT_DUPLICATE_SUSPECTED
```

Do not merge or auto-reuse.

---

# 19. Same-name behavior

A same `full_name` or generated naming collision is not enough to establish identity.

Therefore:

```text
Amit Shah
Amit Shah
```

may legitimately become separate Contacts if no stronger duplicate signal exists.

Do not block creation solely on same human-readable name.

Let native Contact naming append a suffix when required.

---

# 20. Hidden duplicate behavior

Permission filtering is mandatory.

If an existing Contact is not visible to the authenticated Frappe user:

- do not return its identity;
- do not return its email;
- do not return its phone;
- do not state that "a hidden Contact already exists";
- do not query around permissions.

If permission-aware duplicate search cannot see it, standalone creation may proceed according to normal Frappe rules.

Do not invent global uniqueness.

---

# 21. Existing search tool

Reuse:

```text
search_contacts
```

unchanged.

Do not add:

```text
search_standalone_contacts
find_contacts
list_contacts
```

Task 60 should not broaden global fuzzy search.

The existing exact global:

```text
name
email
phone
```

search remains the correct selection/reuse surface.

---

# 22. Prepare permission

Prepare must check:

```text
Contact create
```

through native/current project permission APIs.

Visible duplicate lookup additionally depends on:

```text
Contact read
```

Do not hard-code role names.

Do not require:

```text
Customer read
Customer write
Supplier permission
```

for standalone creation.

---

# 23. Prepare output

Use current result/interaction patterns.

A successful prepare should be a bounded `ready` result.

Conceptual preview:

```text
status: ready
approval_token: opaque
expires_in_seconds: ...

preview:
    full_name: Amit Shah
    company_name: ...
    designation: ...
    department: ...
    email: ...
    mobile: ...
    phone: ...
    linked_to_customer: false
    link_count: 0
    action: create standalone Contact

interaction:
    approval
```

Do not include:

- raw payload dict;
- raw child rows;
- child row names;
- raw `links`;
- owner/system fields;
- CRM details;
- User details.

---

# 24. Approval action

Use:

```text
contact_create
```

unless the current canonical action registry requires an equivalent established naming pattern.

Do not reuse:

```text
customer_contact
```

for standalone creation.

The approval state must remain semantically distinct from Task 57.

---

# 25. Approval state/fingerprint

Bind at minimum:

```text
site
authenticated user
profile
action = contact_create
normalized typed input
deterministic child-row intent
duplicate candidate fingerprint
```

The shared ApprovalStore already handles site/user/action binding if that is current implementation behavior.

Do not create a separate Contact approval store.

Use:

```text
ApprovalStore.claim_for_confirm_write()
```

or current canonical equivalent.

No caller-controlled approval mode.

No self-grant through `confirm=true`.

---

# 26. Confirm input

Public confirm input remains bounded:

```text
approval_token
confirm
```

Do not accept Contact payload again during confirm.

Do not accept:

```text
name
links
child rows
approval mode
site override
user override
```

from caller.

---

# 27. Confirm flow

Confirm must:

1. validate/claim shared approval;
2. re-check Contact create permission;
3. rebuild the exact approved Contact payload;
4. re-run permission-visible exact duplicate checks;
5. stop if a new visible duplicate now changes the approved decision;
6. call normal Frappe Contact insert;
7. allow native Contact validation and all installed hooks;
8. commit once at the outer confirmation boundary;
9. rollback on failure;
10. return bounded created Contact projection.

Native insert:

```python
contact = frappe.get_doc(payload)
contact.insert(ignore_permissions=False)
```

Do not use:

```text
ignore_permissions=True
frappe.db.insert
direct SQL
direct child-table SQL
```

---

# 28. Confirm-time native hooks

Unlike prepare, confirm must allow normal installed native behavior.

This includes:

```text
Contact controller validation
ERPNext Contact hooks
CRM Contact validate hook
child table validation
email/phone validation
autoname
duplicate Dynamic Link cleanup if relevant
```

Standalone Contact has no Dynamic Link by design.

Do not bypass CRM/Frappe hooks merely to simplify the operation.

If a native hook fails:

```text
rollback
safe bounded error
```

No raw traceback to public tool output.

---

# 29. Transaction boundary

Task 60 must implement:

```text
one approved Contact creation
one outer commit
```

Do not copy Task 57's current branch-local commit pattern blindly.

The standalone Contact service should:

```text
insert Contact
run native hooks
then outer confirm commits once
```

On failure:

```text
rollback
```

No helper should independently commit.

If the repository's current service architecture requires the service itself to own the confirmation commit, it must still be exactly one commit after the complete native insert/hook chain, with rollback in the same confirm boundary.

Document the final boundary in the implementation report.

---

# 30. Task 57 transaction finding

Task 59 identified current Task 57 internal create/link commits.

Task 60 must not silently change them.

Classification:

```text
non-blocking separate hardening
```

Do not modify Task 57 only to make Task 60 stylistically identical.

A future dedicated hardening task may fix Task 57 transaction ownership after tests are reviewed.

Task 60 itself must use the safer single confirmation transaction pattern.

---

# 31. Result projection

Reuse the existing bounded `ContactProjection` where possible.

Standalone created result should expose only:

```text
doctype
name
full_name
company_name?
email_id?
mobile_no?
phone?
is_primary_contact
linked_to_customer = false
other_party_link_count = 0
```

If the existing projection requires Customer context, adjust/reuse it cleanly rather than creating a raw document result.

Do not return:

```text
links
email_ids
phone_nos
addresses
communications
comments
CRM Deals
User
Google fields
system metadata
custom fields
```

---

# 32. Created Contact `name`

Return the actual inserted:

```text
Contact.name
```

after native autoname runs.

Do not generate or reserve the document name during prepare.

This is important because native naming may append numeric suffixes.

Example:

```text
preview full_name: Amit Shah
created Contact.name: Amit Shah-2
```

is valid if collision rules produce it.

---

# 33. Stale state

Standalone create has no existing Contact `modified` fingerprint.

Confirm-time stale/revalidation concerns are:

```text
create permission changed
new visible email duplicate appeared
new visible normalized-phone duplicate appeared
approval expired/replayed
wrong site/user/action/profile
```

A change in name-collision suffix state is not by itself a failure unless the approved contract incorrectly promised a fixed document name.

Do not bind exact future Contact `name`.

---

# 34. Lost-response behavior

If Contact creation succeeds but client does not receive the response, a new prepare may discover the created Contact through:

```text
exact email
normalized phone
```

In V1:

```text
return duplicate_suspected
```

rather than automatically claim:

```text
already_created
```

unless there is a stronger server-side idempotency identity.

Do not use same name alone as lost-response recovery evidence.

Do not create caller-controlled idempotency using Contact name.

---

# 35. Idempotency

Approval token replay must never create a second Contact.

Same approval token:

```text
one write maximum
```

Separate repeated new prepares:

```text
duplicate checks re-run
```

If no strong duplicate signal exists, same-name Contacts may still be separately created because that is native-valid behavior.

Do not silently merge.

---

# 36. Error and interaction semantics

Reuse existing error/result conventions.

Required semantic conditions include:

```text
CONTACT_INVALID_IDENTITY
CONTACT_INVALID_EMAIL
CONTACT_INVALID_PHONE
CONTACT_DUPLICATE_SUSPECTED
PERMISSION_DENIED
CONFIRMATION_REQUIRED
CONFIRMATION_UNAVAILABLE
STALE_CONFIRMATION
```

If current project has canonical equivalents, reuse them.

For visible duplicate candidates:

```text
needs_selection
```

or the current selection interaction may be used.

Do not expose hidden candidate data.

Unexpected native errors must use the safe `ToolError` path.

No stack trace, SQL, or internal personal data in public result.

---

# 37. Sales profile exposure

After implementation, Sales should expose:

```text
search_contacts
prepare_contact
confirm_contact
prepare_customer_contact
confirm_customer_contact
```

plus all existing unrelated Sales tools.

Purchase and Accounts must not expose:

```text
prepare_contact
confirm_contact
```

Do not create a new profile.

---

# 38. Registry and transport parity

Update all current integration points required by the project.

At minimum verify:

```text
tool registry
Sales profile registry
contract registry
remote operations registry
REST typed dispatch
MCP/stdio tool exposure
streamable HTTP exposure through the same server registration
generated docs/tool catalog
```

No REST-only business logic.

No MCP-only business logic.

All transports call the same standalone Contact service.

---

# 39. No duplicate business implementation

Business rules must live in one service layer.

Contracts:

```text
schema only
```

Tools:

```text
thin adapter
```

Remote operations:

```text
typed dispatcher/adapter
```

Service:

```text
permissions
validation
duplicates
approval state
native insert
transaction
result projection
```

Do not duplicate Contact creation rules across transports.

---

# 40. Required tests — contracts

Test all accepted V1 fields:

```text
first_name
middle_name
last_name
company_name
designation
department
email
mobile
phone
```

Test identity alternatives:

```text
first_name only
last_name only
company_name only
first + last
company + contact details
```

Reject no identity.

Reject unknown/raw fields:

```text
name
full_name
email_id
mobile_no
links
email_ids
phone_nos
is_primary_contact
user
owner
modified
docstatus
arbitrary custom field
```

---

# 41. Required tests — prepare non-mutation

Prove `prepare_contact`:

- does not insert Contact;
- does not save Contact;
- does not insert Contact Email;
- does not insert Contact Phone;
- does not create Dynamic Link;
- does not commit;
- does not run CRM write-capable Contact validation hooks;
- does not create User;
- does not mutate CRM Deal;
- stores only approval/interaction state through the approved shared infrastructure.

---

# 42. Required tests — identity/name preview

Test:

- first name only;
- last name only;
- company name only;
- person full name;
- middle name;
- trimmed input;
- deterministic full-name preview;
- preview does not promise exact persisted `Contact.name`;
- same display name does not block creation.

---

# 43. Required tests — email

Test:

- valid email;
- whitespace trim;
- invalid email;
- multiple/comma-separated email rejection;
- one child row construction;
- child row primary flag;
- native created `email_id` projection;
- visible exact duplicate;
- case-varied visible duplicate;
- hidden/unreadable candidate not leaked;
- duplicate appears after prepare.

---

# 44. Required tests — mobile/phone

Test:

- mobile only;
- phone only;
- mobile + phone;
- valid values;
- invalid values;
- separate child rows when both supplied;
- mobile row only has mobile-primary flag;
- phone row only has phone-primary flag;
- created parent `mobile_no`;
- created parent `phone`;
- normalized visible duplicate;
- formatting-variant duplicate;
- no storage reformatting solely because comparison is normalized.

---

# 45. Required tests — no-link state

Test created Contact has:

```text
no Customer Dynamic Link
no Supplier Dynamic Link
no arbitrary Dynamic Link
is_primary_contact false/default
```

Test public contract cannot inject links.

Test no Customer permission check occurs.

---

# 46. Required tests — duplicate policy

Test:

- same full name only -> allowed;
- same company name only -> allowed unless stronger duplicate signal;
- exact visible email -> duplicate suspected;
- case-varied visible email -> duplicate suspected;
- normalized visible mobile -> duplicate suspected;
- normalized visible phone -> duplicate suspected;
- hidden candidate -> not exposed;
- no auto-merge;
- no auto-reuse.

---

# 47. Required tests — confirm

Test:

- valid approval creates Contact;
- native insert uses `ignore_permissions=False`;
- native autoname used;
- actual inserted name returned;
- child email inserted;
- child phone/mobile inserted;
- parent projections derived;
- native hooks execute;
- exactly one commit at confirmation boundary;
- rollback on native insert failure;
- rollback on hook failure;
- safe bounded error.

---

# 48. Required tests — approval

Test:

- valid approval;
- wrong user;
- wrong site;
- wrong profile/action;
- expired token;
- replay;
- `confirm=false`;
- caller cannot self-grant approval;
- approval backend unavailable;
- payload cannot be changed after prepare.

---

# 49. Required tests — permission

Test:

- Contact create denied;
- Contact create permitted;
- Contact read unavailable during duplicate lookup;
- duplicate lookup does not leak unreadable Contact;
- Customer permission irrelevant;
- no `ignore_permissions=True`.

---

# 50. Required tests — lost response / repeat

Test or simulate:

- confirm success followed by new identical email prepare;
- newly created Contact appears as visible duplicate;
- new prepare does not blindly create another Contact;
- same-name-only repeat is not treated as exact identity;
- approval replay cannot create twice.

---

# 51. Required tests — profile exposure

Test:

```text
sales:
    prepare_contact present
    confirm_contact present

purchase:
    absent

accounts:
    absent
```

Ensure existing Task 57 tools remain present and unchanged.

---

# 52. Required tests — transport parity

Test:

- tool registration;
- contract registry;
- remote operation registry;
- REST typed dispatch;
- MCP/stdio path;
- generated schema/catalog checks;
- same result semantics across transports.

Do not create transport-specific Contact rules.

---

# 53. Required tests — regression

Run affected existing suites.

At minimum cover:

```text
customer contact tests
Contact tool registration
Sales profile tests
REST backend tests
contract registry tests
approval tests relevant to this action
email tests if Contact projection helper is shared
```

Ensure Task 57:

```text
search_contacts
prepare_customer_contact
confirm_customer_contact
```

continues to work unchanged.

Task 58 update design remains future scope.

---

# 54. Full test strategy

Run narrow tests first.

Then broader affected suites.

Then full app discovery if the repository convention supports it.

Document:

```text
exact commands
tests run
pass count
fail count
pre-existing failures
new failures
```

Do not fix unrelated pre-existing failures unless Task 60 caused them.

Clearly separate:

```text
Task 60 failures
pre-existing failures
environment failures
```

---

# 55. Code quality verification

At minimum run the repository's available equivalents of:

```text
Python syntax/AST check
git diff --check
tool catalog --check
focused unit tests
broader affected tests
```

Use Ruff only if currently available/configured.

Do not add or modify tooling merely to satisfy this task.

---

# 56. Acceptance criteria — capability

Task 60 is complete only when:

- [ ] `prepare_contact` exists.
- [ ] `confirm_contact` exists.
- [ ] both are Sales-only.
- [ ] Contact can be created with no party relationship.
- [ ] at least one of first_name/last_name/company_name is required.
- [ ] email is optional.
- [ ] mobile is optional.
- [ ] phone is optional.
- [ ] at most one of each semantic communication field is public.
- [ ] Contact is inserted natively.
- [ ] no Dynamic Link is created.
- [ ] `is_primary_contact` is not public input.
- [ ] Customer permissions are not required.

---

# 57. Acceptance criteria — safety

- [ ] public raw child tables are impossible.
- [ ] arbitrary fields are rejected.
- [ ] prepare is non-mutating.
- [ ] full hook-bearing Contact validate chain is not run during prepare.
- [ ] visible duplicate checks are permission-aware.
- [ ] hidden Contacts are not disclosed.
- [ ] same name does not auto-merge.
- [ ] exact visible email/phone duplicate does not silently create.
- [ ] no broad global fuzzy personal search is added.
- [ ] no `ignore_permissions=True` business write.
- [ ] no direct SQL mutation.

---

# 58. Acceptance criteria — approval/transaction

- [ ] shared ApprovalStore is reused.
- [ ] action is standalone-specific (`contact_create` or canonical equivalent).
- [ ] `claim_for_confirm_write` is used.
- [ ] confirm rechecks create permission.
- [ ] confirm rechecks duplicate state.
- [ ] approval replay cannot write again.
- [ ] one outer commit occurs only after successful native insert/hooks.
- [ ] failure rolls back.
- [ ] Task 57 internal commit behavior is not copied.
- [ ] Task 57 itself is not silently modified.

---

# 59. Acceptance criteria — native correctness

- [ ] email stored as Contact Email child row.
- [ ] mobile stored as Contact Phone child row with mobile-primary flag.
- [ ] phone stored as separate Contact Phone child row with phone-primary flag.
- [ ] parent email/phone/mobile projections are native-derived.
- [ ] actual Contact autoname is native.
- [ ] native collision suffix is preserved.
- [ ] installed Frappe/ERPNext/CRM hooks are not bypassed.
- [ ] no MCP-owned Contact master/shadow table exists.

---

# 60. Acceptance criteria — data minimization

Public result does not expose:

- [ ] raw `links`;
- [ ] raw `email_ids`;
- [ ] raw `phone_nos`;
- [ ] child row names;
- [ ] addresses;
- [ ] comments;
- [ ] communications;
- [ ] CRM Deal data;
- [ ] User fields;
- [ ] Google fields;
- [ ] system metadata;
- [ ] arbitrary custom fields.

Created result includes only the bounded Contact projection required for future selection/linking.

---

# 61. Acceptance criteria — routing/regression

- [ ] standalone intent uses standalone pair.
- [ ] Customer-known create continues to use Task 57.
- [ ] existing Contact linking continues to use Task 57.
- [ ] `search_contacts` is reused unchanged.
- [ ] Customer-linked creation does not become a two-write standalone+link flow.
- [ ] Purchase/Accounts exposure remains unchanged.
- [ ] Task 57 tests continue to pass.

---

# 62. Expected end-to-end scenario A

Input:

```text
Create contact Amit Shah with amit@example.com
```

Expected:

```text
prepare_contact
    ->
identity valid
    ->
Contact create permission valid
    ->
email valid
    ->
no visible exact duplicate
    ->
ready preview
    ->
approval
    ->
confirm_contact
    ->
approval claimed
    ->
permission + duplicate recheck
    ->
native Contact insert
    ->
native hooks
    ->
commit
```

Created Contact:

```text
Contact.name = native generated value
full_name = Amit Shah
email_id = amit@example.com
links = none
is_primary_contact = false/default
```

---

# 63. Expected end-to-end scenario B

Input:

```text
Create contact Accounts Desk for XYZ
```

Assuming:

```text
company_name = "Accounts Desk for XYZ"
```

or another contract-valid identity mapping chosen by the Agent.

Expected:

```text
standalone Contact
no Customer link
no Supplier link
```

Do not fabricate a Customer merely from the words "for XYZ" unless the user explicitly intends a Customer relationship and a Customer resolves.

Agent interpretation remains outside the MCP service.

---

# 64. Expected end-to-end scenario C

Input:

```text
Create Amit Shah as a contact for ABC Pvt Ltd
```

Expected:

```text
DO NOT use prepare_contact
```

Use existing:

```text
prepare_customer_contact(mode=create)
```

because the relationship is already known.

---

# 65. Expected end-to-end scenario D

First:

```text
Create contact Amit Shah
```

Task 60:

```text
prepare_contact -> confirm_contact
```

Later:

```text
Link Amit Shah to ABC Pvt Ltd
```

Existing Task 57:

```text
search_contacts
prepare_customer_contact(mode=link)
confirm_customer_contact
```

No duplicate Contact should be created.

---

# 66. Expected duplicate scenario

Input:

```text
Create contact Amit Shah with amit@example.com
```

Visible existing Contact already has:

```text
amit@example.com
```

Expected:

```text
CONTACT_DUPLICATE_SUSPECTED
```

with minimal visible candidate projection.

Do not:

```text
auto-create
auto-link
auto-merge
```

---

# 67. Implementation report

After implementation, create:

```text
docs/inspect/STANDALONE_CONTACT_CREATION_V1_IMPLEMENTATION_REPORT.md
```

The report must contain:

1. branch and HEAD before/after;
2. files changed;
3. final public tools;
4. exact final contracts;
5. identity rule;
6. email construction;
7. mobile/phone construction;
8. no-link behavior;
9. permission checks;
10. duplicate policy;
11. hidden duplicate behavior;
12. prepare non-mutation evidence;
13. CRM-hook prepare safety;
14. confirm native insert flow;
15. approval action/fingerprint;
16. transaction/commit/rollback ownership;
17. final bounded result;
18. profile exposure;
19. REST/MCP parity;
20. tests added/changed;
21. exact test commands/results;
22. full-suite/pre-existing failures;
23. deviations from Task 59 and why;
24. confirmation that Task 57 behavior was not silently changed;
25. confirmation that no business/site data was manually mutated during implementation verification.

---

# 68. Limitations intentionally retained

After Task 60 the following remain intentionally unsupported:

- Contact detail update;
- email update;
- phone/mobile update;
- multiple emails at create;
- multiple phones at create;
- Contact delete;
- Contact merge;
- Contact rename;
- Contact unlink;
- arbitrary Dynamic Links;
- Supplier Contact creation/linking;
- Purchase Contact tools;
- Accounts Contact tools;
- existing Contact primary promotion;
- standalone Contact bulk import;
- generic Contact CRUD;
- hidden Contact enumeration;
- automatic lost-response identity recovery without stronger idempotency design.

These are scope boundaries, not Task 60 defects.

---

# 69. Exact next task

After Task 60 implementation report is reviewed and accepted, provide the Git commit message for Task 60 according to the project workflow.

Then continue with the already completed Task 58 design as:

```text
Task 61 — Customer-Scoped Contact Detail and Communication Update Implementation
```

Task 61 must implement only the operation set already approved by Task 58:

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

with:

```text
shared Contact rejection
Customer-primary projection refresh
child-row stale fingerprints
one bounded operation per prepare
normal Contact.save(ignore_permissions=False)
```

Do not re-audit the Task 58 scope unless Task 60 implementation reveals a material conflict.
