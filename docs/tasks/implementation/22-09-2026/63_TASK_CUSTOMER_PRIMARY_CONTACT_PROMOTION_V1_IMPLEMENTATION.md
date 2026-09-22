# Task 63 — Customer Primary Contact Promotion V1 Implementation

## Status

**Implementation task**

Task 62 audit is complete and is the source-of-truth design for this task:

```text
docs/inspect/CUSTOMER_CONTACT_PRIMARY_PROMOTION_RELATIONSHIP_HARDENING_AUDIT.md
```

Current Contact capability baseline:

```text
search_contacts

prepare_contact
confirm_contact

prepare_customer_contact
confirm_customer_contact

prepare_contact_update
confirm_contact_update
```

Task 63 adds one new Customer relationship/default capability:

```text
prepare_customer_primary_contact
confirm_customer_primary_contact
```

This task must not broaden Contact CRUD, relationship mutation, communication updates, or Supplier/Purchase scope.

---

# 1. Objective

Implement safe promotion of an **existing Contact already linked to exactly one target Customer** as that Customer's primary Contact.

Example:

```text
Customer: ABC Pvt Ltd
Linked Contacts:
  Ravi
  Amit

Current primary:
  Ravi

User:
"Make Amit the primary Contact for ABC Pvt Ltd"
```

Expected final native state:

```text
Amit.is_primary_contact = 1
Ravi.is_primary_contact = 0   # native Contact demotion path
ABC.customer_primary_contact = Amit
ABC.email_id / mobile_no / first_name / last_name
    refreshed through normal Customer save
```

All changes must occur in one logical transaction.

---

# 2. Important Task 62 interpretation rule

Task 62 contains one wording inconsistency that must not be copied literally into code.

The report clearly defines these as valid promotion cases:

```text
Customer has no current primary -> promote selected linked Contact
Customer has current primary Ravi -> promote selected linked Contact Amit
```

Therefore:

```text
selected Contact is non-primary
AND
Customer currently points to a DIFFERENT VALID linked old primary Contact
```

is a **normal replacement case**, not an inconsistency.

Treat state as inconsistent only when the existing pointer/flags/links cannot represent a coherent native Customer-primary state.

Examples of genuine inconsistency include:

```text
Customer.customer_primary_contact points to a Contact not linked to Customer

Customer.customer_primary_contact = Amit
but another linked Contact is also primary

Customer.customer_primary_contact = Ravi
but Ravi is not linked to Customer

selected Contact is already primary while Customer points to a different linked Contact

multiple Customer-linked Contacts are already marked primary

pointer/relationship/primary state changes after prepare
```

Before production edits, trace current source and current test fixtures and encode the exact coherent-state validator explicitly.

Do not reject a legitimate "replace current primary" request merely because the selected Contact differs from the current primary.

---

# 3. Business boundary

Task 63 supports only:

```text
existing Customer
+
existing Contact
+
Contact already has exact Customer Dynamic Link
+
Contact has no additional Dynamic Link
+
promote that Contact to Customer primary
```

Task 63 does not:

- create Contact;
- link Contact;
- update email/phone/details;
- remove Customer link;
- clear primary Contact;
- repair arbitrary corrupt relationship state;
- promote a shared Contact;
- merge Contacts;
- delete Contacts.

---

# 4. Public tools

Add exactly:

```text
prepare_customer_primary_contact
confirm_customer_primary_contact
```

Do not add:

```text
make_primary_contact
set_primary_contact
promote_contact
```

as separate public operations.

Do not add:

```text
mode="make_primary"
```

to `prepare_customer_contact`.

Do not add primary relationship behavior to:

```text
prepare_contact_update
```

Primary Customer relationship semantics must remain clearly separate from:

```text
primary email
primary phone
primary mobile
```

---

# 5. Approval action

Use a distinct shared approval action:

```text
customer_primary_contact
```

Do not reuse:

```text
customer_contact
customer_contact_update
contact_create
```

Use existing:

```text
ApprovalStore
claim_for_confirm_write()
InteractionDirective
ToolError
stable_fingerprint
```

No new approval store.

No public approval-mode argument.

`confirm=true` alone must not self-authorize.

---

# 6. Mandatory pre-implementation inspection

Before editing production code, inspect current implementation after Tasks 57, 60, and 61.

At minimum inspect:

```text
mcp_erpnext/contracts/masters/contact.py

mcp_erpnext/services/masters/customer_contact.py
mcp_erpnext/services/masters/contact.py
mcp_erpnext/services/masters/contact_update.py

mcp_erpnext/tools/masters/contact.py
mcp_erpnext/tools/masters/customer_contact.py

mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py

mcp_erpnext/tests/test_customer_contact.py
mcp_erpnext/tests/test_standalone_contact.py
mcp_erpnext/tests/test_contact_update.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_rest_backend.py
docs/TOOLS.md
```

Inspect current framework/app source:

```text
frappe.contacts.doctype.contact.contact.Contact
Contact.validate_primary_contact
Contact.has_link
Dynamic Link
Document.save

ERPNext Customer
Customer.create_primary_contact
customer_primary_contact metadata
Customer fetch fields
party default Contact logic

CRM Contact override
CRM Contact validate hook
ERPNext Contact doc_events
```

Do not rely on stale line offsets from Task 62 if source changed.

---

# 7. Mandatory runtime metadata re-check

Before final implementation verification, use read-only runtime inspection on the configured development/test site.

Verify effective fields:

```text
Contact.is_primary_contact
Contact.links
Customer.customer_primary_contact
Customer.email_id
Customer.mobile_no
Customer.first_name
Customer.last_name
```

Verify:

```text
installed Contact override
Contact doc_events
Customer doc_events
effective Customer permissions
effective Contact permissions
```

Do not hard-code role names.

Do not mutate live business records merely to inspect metadata.

If runtime access is unavailable, document the limitation separately.

---

# 8. Public prepare contract

Conceptual input:

```text
PrepareCustomerPrimaryContactInput {
    customer: CustomerReference
    contact: ContactReference
}
```

Use existing exact reference models.

Do not accept:

```text
is_primary_contact
customer_primary_contact
links
link_doctype
link_name
old_primary
approval mode
field maps
raw Contact payload
raw Customer payload
```

The server resolves all current state.

Public models must follow existing `PublicContractModel` strict extra-field rejection.

---

# 9. Public confirm contract

Conceptual input:

```text
ConfirmCustomerPrimaryContactInput {
    approval_token: string
    confirm: bool
}
```

Do not re-submit Customer/Contact on confirm.

Confirm operates only on approval-bound state.

---

# 10. Customer resolution

Prepare must resolve exact Customer and require:

```text
Customer read
Customer write
```

Why write is required at prepare:

```text
promotion necessarily changes customer_primary_contact
and refreshes Customer stored projections
```

If Customer write is unavailable:

```text
PERMISSION_DENIED
```

or current canonical bounded permission result.

Do not generate an approval token for a promotion the user cannot complete.

---

# 11. Selected Contact resolution

Prepare must resolve exact Contact and require:

```text
Contact read
Contact write
```

Do not use:

```text
ignore_permissions=True
ignore_user_permissions=True
```

for the public operation.

---

# 12. Exact membership enforcement

At prepare and confirm require:

```python
contact.has_link("Customer", customer.name)
```

If false:

```text
CONTACT_NOT_LINKED_TO_CUSTOMER
```

Do not auto-link.

Linking remains Task 57:

```text
prepare_customer_contact(mode=link)
confirm_customer_contact
```

---

# 13. Selected Contact relationship-sharing rule

Selected Contact must have exactly one Dynamic Link:

```text
("Customer", target_customer_name)
```

Any additional Dynamic Link means the selected Contact is shared.

Examples:

```text
another Customer
Supplier
Lead
Prospect
CRM Deal
any other link_doctype
```

Return:

```text
CONTACT_SHARED_WITH_OTHER_PARTIES
```

No mutation.

Do not expose unrelated link names or doctypes in public result.

---

# 14. "Any additional Dynamic Link" is the V1 sharing rule

Do not attempt to classify only certain doctypes as "party".

Task 62 found native Contact primary behavior operates over all Dynamic Links.

Therefore authorization/safety rule is:

```text
sorted links == [("Customer", target_customer)]
```

for the selected Contact.

No incomplete hard-coded party-doctype allowlist.

---

# 15. Internal relationship fingerprint

Create/reuse an internal helper that produces a stable sorted relationship fingerprint.

Conceptually:

```text
[
  (link_doctype, link_name),
  ...
]
```

Requirements:

- deterministic sort;
- exact target Customer membership visible internally;
- additional links detectable;
- no unrelated link identities exposed publicly;
- suitable for approval fingerprint/stale comparison.

Do not use public `other_party_link_count` as the security decision.

---

# 16. Current `other_party_link_count` limitation

Current Task 57 projection semantics may count all non-target Dynamic Links while naming the field `other_party_link_count`.

Task 63 must **not** silently change that existing public field's meaning.

For promotion authorization:

```text
use internal exact sorted Dynamic Link fingerprint
```

not the public count.

If Task 63 preview includes a count, use only an accurately named bounded field if current contract can add it safely, for example:

```text
additional_link_count
```

Otherwise omit the count.

Do not expose unrelated relationship identities.

---

# 17. Current Customer primary resolution

Prepare must inspect:

```text
customer.customer_primary_contact
```

Cases:

```text
A. empty
B. already selected Contact
C. different existing Contact
```

Each case has different state validation.

---

# 18. Case A — no current Customer primary

If:

```text
customer.customer_primary_contact is empty
```

validate all Customer-linked Contact primary flags.

Expected coherent state for promotion:

```text
selected may be non-primary
no conflicting Customer-linked primary Contact exists
```

If another linked Contact is already `is_primary_contact=1` while Customer pointer is empty, classify as inconsistent rather than silently repairing.

Return:

```text
CONTACT_PRIMARY_STATE_INCONSISTENT
```

unless current source/test evidence justifies a narrower canonical normalization path.

---

# 19. Case B — selected Contact already Customer primary

If:

```text
customer.customer_primary_contact == selected_contact.name
```

then inspect:

```text
selected_contact.is_primary_contact
other Customer-linked primary flags
membership state
```

If coherent:

```text
selected.is_primary_contact = 1
no conflicting linked primary Contact
```

return safe idempotent success:

```text
already primary
idempotent=true
```

No unnecessary business save.

If pointer says selected but flag is false or conflicting primaries exist:

```text
CONTACT_PRIMARY_STATE_INCONSISTENT
```

Do not silently repair under V1.

---

# 20. Case C — different valid current primary

This is the normal replacement case.

Example:

```text
Customer.customer_primary_contact = Ravi
selected Contact = Amit
```

Require current old primary Contact:

- exists;
- is readable enough through the chosen safe internal path;
- has exact target Customer link;
- represents a coherent current primary state;
- is not an unrelated/unlinked pointer.

Selected Contact must be linked to target Customer and have no additional link.

Then prepare promotion:

```text
Ravi -> old primary
Amit -> selected new primary
```

Do not reject merely because current pointer is different from selected Contact.

---

# 21. Old primary Contact state

Load current old primary Contact when Customer pointer is non-empty and different from selected.

Bind:

```text
old primary name
old primary modified
old primary is_primary_contact
old primary relationship fingerprint
```

The report found old primary demotion is performed by selected Contact native validation using direct `db.set_value`.

Task 63 must inspect old primary sharing before promotion because demotion can affect its global Contact-primary semantics.

---

# 22. Old primary shared-state safety

This is a mandatory implementation boundary.

If old primary Contact has any Dynamic Link other than the exact target Customer link, promotion may demote a Contact that is also primary for another linked party.

V1 must conservatively reject this case unless current source proves demotion cannot affect other relationships.

Recommended result:

```text
PRIMARY_CONTACT_PROMOTION_UNSAFE
```

or:

```text
CONTACT_SHARED_WITH_OTHER_PARTIES
```

depending on current canonical error taxonomy.

Do not expose old primary's unrelated party names.

This rule applies even if the **selected** Contact itself is single-Customer.

---

# 23. Coherent old primary state

For normal replacement, require:

```text
old_primary.has_link("Customer", customer.name)
old_primary.is_primary_contact == true
```

and no additional Dynamic Links under the V1 safety rule.

If Customer pointer references a Contact that is:

```text
missing
unlinked
non-primary
shared in a way that makes demotion unsafe
```

return bounded inconsistency/unsafe result.

Do not silently normalize arbitrary existing data.

---

# 24. Multiple primary Contact detection

Before approval, inspect Customer-linked Contacts sufficiently to detect:

```text
more than one Contact with is_primary_contact=1
```

If multiple linked primaries already exist:

```text
CONTACT_PRIMARY_STATE_INCONSISTENT
```

Do not promote another Contact.

Do not silently choose which existing Contact should remain.

Keep output bounded; do not enumerate unrelated Contact details unless user selection/repair workflow later requires it.

---

# 25. Native promotion sequence

Use the Task 62-selected sequence.

Inside one outer transaction:

```text
1. selected_contact.is_primary_contact = 1
2. selected_contact.save(ignore_permissions=False)

3. customer.customer_primary_contact = selected_contact.name
4. customer.save(ignore_permissions=False)

5. commit once
```

No intermediate commit.

On any exception:

```text
rollback
```

---

# 26. Why Contact save comes first

Selected Contact normal save is required to preserve:

```text
Contact.validate_primary_contact()
native Customer-row locking
native demotion of other primary Contacts sharing target Customer link
Frappe Contact validation
CRM Contact validate hook
ERPNext Contact hooks
```

Do not replace selected Contact save with direct:

```text
frappe.db.set_value("Contact", ...)
```

as the MCP mutation seam.

---

# 27. Why Customer save comes second

Customer normal save is required to:

```text
store customer_primary_contact
refresh fetch_from projections:
  email_id
  mobile_no
  first_name
  last_name
run Customer native lifecycle
```

Do not directly assign read-only projection fields.

Do not use direct `db_set`/`frappe.db.set_value` for Customer projections.

---

# 28. Customer internal Contact set_value behavior

ERPNext Customer `create_primary_contact()` may internally ensure:

```text
Contact.is_primary_contact = 1
```

using `frappe.set_value`.

Task 63 must not rely on that as the sole public promotion mutation.

The selected Contact must already have gone through normal:

```text
Contact.save(ignore_permissions=False)
```

before Customer save.

If Customer's internal ensure operation writes the same `1` again, treat it as native internal behavior.

Do not bypass Customer lifecycle to avoid it.

---

# 29. Native demotion behavior

When selected Contact is saved as primary, native Contact validation may demote old Customer-linked primary Contact through internal:

```text
frappe.db.set_value
```

Do not manually demote old primary first unless current source/testing proves native behavior requires it.

Do not duplicate demotion logic in MCP.

After selected Contact save, verify expected old-primary state before Customer save if doing so is safe and necessary for invariant checking.

At minimum final postcondition verification must ensure:

```text
selected is primary
old primary is no longer primary
```

for replacement case.

---

# 30. CRM hooks

Selected Contact normal save must run installed CRM/Frappe/ERPNext hooks.

Do not bypass them.

Old primary's native direct demotion may not run normal Contact hooks.

Do not manually invoke old-primary hooks.

Document this native behavior in implementation report.

Promotion itself should not alter email/mobile, so CRM snapshot changes may be no-op, but native selected Contact hook path must remain intact.

---

# 31. Customer projection refresh

After:

```text
customer.customer_primary_contact = selected.name
customer.save(ignore_permissions=False)
```

return bounded refreshed Customer projections if current public result needs them:

```text
email_id
mobile_no
first_name
last_name
```

These values must be read after normal Customer save.

Do not pre-compute them as authoritative result.

---

# 32. Historical transaction behavior

Task 63 must not modify existing:

```text
Quotation
Sales Order
Sales Invoice
```

fields:

```text
contact_person
contact_display
contact_email
contact_mobile
```

Promotion affects future native default/contact resolution, not historical snapshots.

No transaction document save belongs in this task.

---

# 33. Email service behavior

Do not rewrite email recipient logic.

Promotion may affect future Customer-primary fallback through native Customer state.

Existing transaction-specific recipient snapshots remain unchanged.

Regression tests should verify no unrelated recipient behavior is broadened.

---

# 34. Prepare must be non-mutating

`prepare_customer_primary_contact` may:

```text
load Customer
load selected Contact
load old primary Contact if needed
inspect exact Dynamic Links
inspect Customer-linked primary flags
check permissions
derive coherent/inconsistent state
compute internal fingerprints
build bounded preview
create approval record
```

Prepare must not:

```text
save Contact
save Customer
demote Contact
commit
run write-capable save hooks
modify Dynamic Links
```

---

# 35. Prepare permissions

Require before ready approval:

```text
Customer read
Customer write
selected Contact read
selected Contact write
```

For old primary Contact:

audit/current implementation should use normal safe loading/inspection.

Do not require caller to possess write on old primary merely because native selected Contact validation internally demotes it unless current framework permission model/source explicitly requires that for public safety.

However, if old primary is shared or otherwise unsafe:

```text
reject before write
```

Do not hard-code roles.

---

# 36. Old primary visibility/data minimization

The operation may need internal old-primary state even if public preview only returns its bounded reference.

Do not expose:

```text
old primary's other Dynamic Links
unrelated party names
raw Contact JSON
```

If the authenticated user cannot safely inspect enough old-primary state to prove promotion safety, fail closed rather than bypass permissions.

Define a bounded permission result.

---

# 37. Approval fingerprint

Bind at least:

```text
site
authenticated user
profile = sales
action = customer_primary_contact

Customer:
  name
  modified
  customer_primary_contact

selected Contact:
  name
  modified
  is_primary_contact
  exact sorted Dynamic Link fingerprint

old primary Contact if present:
  name
  modified
  is_primary_contact
  exact sorted Dynamic Link fingerprint

Customer-linked primary-state fingerprint
expected post-state
```

Unrelated link identities remain internal.

---

# 38. Customer-linked primary-state fingerprint

Create a deterministic internal fingerprint sufficient to detect:

```text
new linked primary Contact appeared
old primary flag changed
selected primary flag changed
Customer pointer changed
selected/old relationship changed
```

Do not expose the full fingerprint publicly.

Do not rely only on:

```text
Customer.modified
Contact.modified
```

because native direct demotion can change Contact fields without necessarily representing all relationship state in the desired way.

---

# 39. Confirm flow

Conceptual confirm:

```text
claim_for_confirm_write(action="customer_primary_contact")
    ->
reload Customer
    ->
reload selected Contact
    ->
reload old primary if current pointer requires it
    ->
recheck Customer read/write
    ->
recheck selected Contact read/write
    ->
recheck selected exact Customer membership
    ->
recheck selected single-link rule
    ->
recheck old-primary safety
    ->
recheck coherent primary state
    ->
compare all fingerprints
    ->
if already coherent selected primary:
        idempotent success
    else:
        selected.is_primary_contact = 1
        selected.save(ignore_permissions=False)

        verify selected/old native primary outcome

        customer.customer_primary_contact = selected.name
        customer.save(ignore_permissions=False)

        verify final Customer pointer/projections
        commit once
```

On any failure:

```text
rollback
```

---

# 40. Concurrent promotion behavior

Consider two approvals:

```text
A -> promote Amit
B -> promote Ravi
```

prepared against the same current state.

Native selected Contact save locks target Customer row through Contact primary validation.

MCP also binds:

```text
Customer.modified
Customer current primary pointer
selected/old Contact modified
primary flags
relationship fingerprints
```

Only one should complete from the same starting state.

The other must return stale/reprepare after fresh state observation.

Do not retry automatically by changing the user's selected Contact.

---

# 41. Stale-state conditions

Return stale/reprepare when any approval-bound state changes:

```text
Customer modified
Customer current primary pointer
selected Contact modified
selected Contact primary flag
selected Contact link fingerprint
old primary modified
old primary primary flag
old primary link fingerprint
Customer-linked primary-state fingerprint
```

Also stale if:

```text
selected Contact becomes shared
old primary becomes shared
selected Contact loses Customer link
old primary loses Customer link
new conflicting primary appears
```

---

# 42. Idempotent state

Return idempotent success without unnecessary save when all are already coherent:

```text
customer.customer_primary_contact == selected.name
selected.is_primary_contact == 1
selected has exactly target Customer link
no conflicting Customer-linked primary Contact
selected not shared
```

Do not run promotion again merely to produce the same result.

---

# 43. Inconsistent states

Return:

```text
CONTACT_PRIMARY_STATE_INCONSISTENT
```

or canonical equivalent when data cannot be safely interpreted as:

```text
no-primary coherent state
valid current-primary coherent state
already-selected coherent state
```

Examples:

```text
Customer pointer -> unlinked Contact
Customer pointer -> missing Contact
Customer pointer -> Contact with primary flag false
selected Contact primary true while Customer points elsewhere
multiple Customer-linked primary Contacts
pointer/flag relationship changed unexpectedly
```

Do not silently repair these in V1.

---

# 44. Relationship-unsafe states

Use a bounded unsafe/shared result when:

```text
selected Contact has additional Dynamic Link
old primary Contact has additional Dynamic Link and native demotion would affect broader scope
```

Do not expose unrelated relationships.

Recommended codes:

```text
CONTACT_SHARED_WITH_OTHER_PARTIES
PRIMARY_CONTACT_PROMOTION_UNSAFE
```

Reuse canonical existing error if one semantic code already covers both safely.

---

# 45. Result projection

Successful result should be bounded.

Conceptually:

```text
status = promoted | already_primary | error

customer:
  doctype
  name
  customer_primary_contact
  email_id?
  mobile_no?
  first_name?
  last_name?

previous_primary_contact:
  bounded ContactReference | null

primary_contact:
  bounded ContactProjection

idempotent: bool
```

Do not expose:

```text
all links
all Customer Contacts
old primary unrelated relationships
raw Contact JSON
CRM records
communications/comments
```

---

# 46. Prepare preview

Bounded preview should include:

```text
Customer reference
selected Contact reference
current primary Contact reference or null
action = promote Customer primary Contact
selected already primary? bool
Customer pointer currently selected? bool
Customer projections will refresh = true
selected additional-link count = 0
old primary relationship safe = true
native side-effect note
```

Do not dump Dynamic Link rows.

---

# 47. Error/interaction semantics

Reuse project conventions.

Required semantic states:

```text
CUSTOMER_NOT_FOUND
CONTACT_NOT_FOUND
CONTACT_NOT_LINKED_TO_CUSTOMER
CONTACT_SHARED_WITH_OTHER_PARTIES
CONTACT_PRIMARY_STATE_INCONSISTENT
PRIMARY_CONTACT_PROMOTION_UNSAFE
CUSTOMER_PRIMARY_CONTACT_STALE
CONTACT_STALE_STATE
PERMISSION_DENIED
CONFIRMATION_REQUIRED
CONFIRMATION_UNAVAILABLE
STALE_CONFIRMATION
```

Do not create duplicate codes if equivalent canonical ones already exist.

---

# 48. Sales-only exposure

Register pair only in:

```text
sales
```

Do not expose in:

```text
purchase
accounts
```

Do not create a generic Contact relationship profile.

---

# 49. Transport parity

Update current integration points:

```text
contracts
service
tools
tools/__init__.py
Sales profile
contract registry
remote operations
REST typed dispatch
docs/TOOLS.md
tests
```

All transports must call the same service implementation.

No REST-specific primary logic.

No MCP-specific primary logic.

---

# 50. Suggested code placement

Prefer:

```text
mcp_erpnext/contracts/masters/contact.py

mcp_erpnext/services/masters/customer_primary_contact.py

mcp_erpnext/tools/masters/customer_contact.py
or a narrowly named contact relationship tool module

mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
```

Reuse relationship/fingerprint helpers only when semantics are exact.

Do not create circular imports.

---

# 51. Task 57 transaction hardening boundary

Task 62 classified Task 57 internal commits as separate non-blocking hardening.

Task 63 must not silently refactor Task 57 create/link commits unless current implementation makes primary promotion call those committing helpers.

Primary promotion must not call a Task 57 helper that commits internally.

If shared lower-level helpers are needed:

```text
extract pure/non-committing helper
```

without changing Task 57 behavior unless explicitly necessary and fully regression-tested.

Any Task 57 transaction ownership change must be documented as a deliberate deviation and justified.

Preferred Task 63 scope:

```text
leave Task 57 behavior unchanged
implement promotion with independent one-outer-transaction service
```

---

# 52. No clear-primary support

Do not implement:

```text
clear customer_primary_contact
unset primary Contact
demote without replacement
```

This is a different destructive/default-state intent.

Task 63 only promotes a selected existing linked Contact.

---

# 53. No automatic relationship repair

Do not:

```text
add missing Customer link
remove extra link
fix Customer pointer
fix multiple primary flags
normalize corrupt data
```

before promotion.

Return bounded error and require a future repair/hardening capability.

---

# 54. Required tests — contract

Test strict public models:

```text
valid CustomerReference
valid ContactReference
unknown fields rejected
no primary flags accepted
no raw links accepted
no old_primary caller input
confirm only approval_token + confirm
```

---

# 55. Required tests — membership

Test:

```text
selected Contact linked exactly to target Customer -> eligible
selected Contact not linked -> CONTACT_NOT_LINKED_TO_CUSTOMER
selected Contact link removed after prepare -> stale
selected Contact additional link -> shared/unsafe
additional link appears after prepare -> stale/unsafe
```

No unrelated link identity exposed.

---

# 56. Required tests — no current primary

Test coherent:

```text
Customer pointer empty
no linked Contact primary
selected linked Contact non-primary
```

Promotion result:

```text
selected primary true
Customer pointer selected
Customer projections refreshed
```

Test incoherent:

```text
Customer pointer empty
another Customer-linked Contact already primary
```

Expected:

```text
CONTACT_PRIMARY_STATE_INCONSISTENT
```

---

# 57. Required tests — replace current primary

Test:

```text
Customer pointer = Ravi
Ravi linked, primary=true, relationship-safe
Amit linked, primary=false, relationship-safe
```

Promote Amit.

Verify:

```text
Amit primary=true
Ravi primary=false
Customer pointer=Amit
Customer projections from Amit
one final commit
```

This is a normal supported V1 case.

Do not classify it as inconsistent.

---

# 58. Required tests — already primary

Coherent:

```text
Customer pointer = Amit
Amit primary=true
no conflicting primaries
single target Customer link
```

Expected:

```text
idempotent=true
no unnecessary Contact save
no unnecessary Customer save
```

---

# 59. Required tests — inconsistent states

Test:

```text
Customer pointer -> unlinked Contact
Customer pointer -> missing Contact
Customer pointer -> Contact primary=false
selected primary=true while Customer points to different Contact
multiple linked Contacts primary=true
```

Expected bounded inconsistency.

No mutation.

---

# 60. Required tests — selected shared Contact

Selected Contact links:

```text
Customer ABC
Customer XYZ
```

or:

```text
Customer ABC
Supplier DEF
```

Expected:

```text
CONTACT_SHARED_WITH_OTHER_PARTIES
```

No mutation.

No unrelated names disclosed.

---

# 61. Required tests — old primary shared Contact

Current old primary:

```text
Ravi links:
  Customer ABC
  Supplier DEF
```

Selected Amit is otherwise safe.

Promotion must be rejected under V1 because native demotion of Ravi's global primary flag may affect DEF semantics.

Expected:

```text
PRIMARY_CONTACT_PROMOTION_UNSAFE
```

or canonical equivalent.

No mutation.

---

# 62. Required tests — permissions

Test:

```text
Customer read denied
Customer write denied
selected Contact read denied
selected Contact write denied
old primary inspection unavailable
```

Fail before mutation.

Do not hard-code role names.

No `ignore_permissions=True`.

---

# 63. Required tests — native Contact save

Verify promotion uses:

```text
selected_contact.save(ignore_permissions=False)
```

and does not direct-write selected `is_primary_contact`.

Verify native validation/demotion path is allowed to run.

Verify selected Contact CRM/Frappe/ERPNext hooks are not bypassed.

---

# 64. Required tests — native demotion

Mock/integration boundary should prove:

```text
selected Contact save results in old primary demotion
```

Do not manually pre-demote old primary in the service.

Verify final:

```text
old primary is_primary_contact = false
```

before/after Customer save according to test framework capabilities.

---

# 65. Required tests — Customer save

Verify:

```text
customer.customer_primary_contact = selected.name
customer.save(ignore_permissions=False)
```

Customer projection fields refresh through native link-fetch behavior.

No direct projection assignment.

No `frappe.db.set_value` from MCP service.

---

# 66. Required tests — atomicity

Verify exact call order:

```text
selected Contact save
Customer save
single commit
```

No commit between saves.

Rollback on:

```text
selected Contact save failure
CRM/Contact hook failure
Customer save failure
postcondition failure
```

No partial promotion.

---

# 67. Required tests — concurrency/stale

Test:

```text
Customer modified after prepare
selected Contact modified
old primary modified
Customer pointer changed
selected primary flag changed
old primary flag changed
relationship fingerprint changed
new conflicting primary appears
```

Each unsafe change requires re-prepare.

Simulate concurrent promotions where possible.

Second approval from stale starting state must not overwrite first promotion silently.

---

# 68. Required tests — approval

Test:

```text
prepare non-mutating
valid approval
wrong user
wrong site
wrong profile/action
expired token
replay
confirm=false
approval backend unavailable
payload cannot be replaced after prepare
```

Action:

```text
customer_primary_contact
```

---

# 69. Required tests — data minimization

Ensure public output excludes:

```text
raw Dynamic Links
unrelated party names
old primary unrelated links
raw Contact JSON
CRM Deal data
comments
communications
User data
system metadata
```

---

# 70. Required tests — Customer projections

After promotion verify bounded Customer:

```text
email_id
mobile_no
first_name
last_name
```

match native selected Contact projections after normal Customer save.

Do not assert direct assignment implementation.

---

# 71. Required tests — email/Sales history regression

Verify existing:

```text
Quotation
Sales Order
Sales Invoice
```

contact snapshots remain unchanged.

Verify future native party resolution may choose promoted Contact.

Do not update historical business documents.

---

# 72. Required tests — existing Contact capability regression

Run focused suites for:

```text
Task 57 Customer Contact create/link
Task 60 standalone Contact create
Task 61 Customer-scoped Contact updates
search_contacts
```

Promotion must not regress them.

---

# 73. Required tests — profile/transport

Verify:

```text
Sales:
  prepare_customer_primary_contact
  confirm_customer_primary_contact

Purchase:
  absent

Accounts:
  absent
```

Verify:

```text
tool registration
contract registry
remote operation registry
REST typed dispatch
MCP/stdio exposure
generated tool catalog
```

---

# 74. Test execution strategy

Run:

1. new focused primary-promotion tests;
2. Contact capability regression suites;
3. profile/registration/REST suites;
4. broader app tests where normal.

Document:

```text
commands
pass/fail counts
pre-existing failures
new failures
environment failures
```

Do not fix unrelated failures.

---

# 75. Optional authorized integration verification

Task 62 recommended authorized local-live read/write verification.

Only perform a write verification if the repository already has an isolated test site/database and project conventions explicitly allow it.

Do not mutate production/business records.

If no safe isolated test boundary exists:

```text
unit/source verified
runtime metadata verified
live mutation not performed
```

is acceptable, but must be stated in report.

---

# 76. Code-quality checks

Run available project checks:

```text
Python compile/AST
git diff --check
tool catalog --check
focused tests
broader affected tests
```

Run Ruff only if installed/configured.

Do not install tooling as part of this task.

---

# 77. Acceptance criteria — public capability

- [ ] dedicated `prepare_customer_primary_contact` exists.
- [ ] dedicated `confirm_customer_primary_contact` exists.
- [ ] Sales-only.
- [ ] exact linked Customer membership required.
- [ ] selected Contact additional links rejected.
- [ ] old-primary unsafe sharing rejected.
- [ ] valid current-primary replacement supported.
- [ ] coherent already-primary state idempotent.
- [ ] no clear-primary support.

---

# 78. Acceptance criteria — primary-state correctness

- [ ] `Contact.is_primary_contact` treated as global Contact flag.
- [ ] `Customer.customer_primary_contact` treated as Customer-scoped pointer.
- [ ] native Contact save happens before Customer save.
- [ ] native old-primary demotion preserved.
- [ ] Customer pointer updated through normal save.
- [ ] Customer projections refreshed through native lifecycle.
- [ ] inconsistent existing state is not silently repaired.

---

# 79. Acceptance criteria — relationship safety

- [ ] exact sorted Dynamic Link fingerprint used internally.
- [ ] public `other_party_link_count` not used as authorization.
- [ ] any selected additional link blocks V1.
- [ ] old primary relationship safety checked.
- [ ] unrelated link identities never public.
- [ ] membership/sharing rechecked at confirm.

---

# 80. Acceptance criteria — permission/approval

- [ ] Customer read/write required.
- [ ] selected Contact read/write required.
- [ ] no role names hard-coded.
- [ ] no permission bypass.
- [ ] shared ApprovalStore reused.
- [ ] action `customer_primary_contact`.
- [ ] one-shot claim used.
- [ ] token replay cannot write again.
- [ ] confirm payload immutable from caller.

---

# 81. Acceptance criteria — transaction

- [ ] no intermediate commit.
- [ ] selected Contact save first.
- [ ] Customer save second.
- [ ] one final commit.
- [ ] rollback on any failure.
- [ ] Task 57 committing helpers not called.
- [ ] Task 57 transaction behavior not silently changed.

---

# 82. Acceptance criteria — data minimization/regression

- [ ] no unrelated party names.
- [ ] no raw links.
- [ ] no raw Contact JSON.
- [ ] no historical transaction mutation.
- [ ] existing Task 57/60/61 tests pass.
- [ ] Purchase/Accounts unchanged.
- [ ] same business service across transports.

---

# 83. Expected flow — no current primary

```text
User:
"Make Amit primary Contact for ABC"
```

Current:

```text
ABC.customer_primary_contact = null
Amit linked only to ABC
Amit.is_primary_contact = 0
no conflicting linked Contact primary
```

Flow:

```text
prepare
  -> permission + relationship checks
  -> coherent-state check
  -> preview
  -> approval

confirm
  -> recheck/fingerprint
  -> Amit.is_primary_contact = 1
  -> Amit.save()
  -> ABC.customer_primary_contact = Amit
  -> ABC.save()
  -> commit
```

---

# 84. Expected flow — replace Ravi with Amit

Current:

```text
ABC.customer_primary_contact = Ravi
Ravi linked only to ABC
Ravi.is_primary_contact = 1

Amit linked only to ABC
Amit.is_primary_contact = 0
```

Expected:

```text
valid promotion
```

Not:

```text
CONTACT_PRIMARY_STATE_INCONSISTENT
```

Confirm:

```text
Amit.save(primary=true)
  -> native demotes Ravi

ABC.save(primary_contact=Amit)
  -> projections refresh

commit
```

---

# 85. Expected flow — selected shared Contact

```text
Amit links:
  Customer ABC
  Customer XYZ
```

Expected:

```text
CONTACT_SHARED_WITH_OTHER_PARTIES
```

No write.

---

# 86. Expected flow — old primary shared

```text
Ravi is current ABC primary
Ravi links:
  Customer ABC
  Supplier DEF

Amit links:
  Customer ABC
```

Expected:

```text
PRIMARY_CONTACT_PROMOTION_UNSAFE
```

No write.

Reason:

```text
native demotion changes Ravi's global Contact primary flag
```

---

# 87. Expected flow — already primary

Current:

```text
ABC.customer_primary_contact = Amit
Amit.is_primary_contact = 1
Amit linked only to ABC
no conflicting linked primaries
```

Expected:

```text
idempotent success
no writes
```

---

# 88. Expected flow — corrupt pointer

Current:

```text
ABC.customer_primary_contact = Ravi
Ravi not linked to ABC
```

Expected:

```text
CONTACT_PRIMARY_STATE_INCONSISTENT
```

Do not auto-link Ravi.

Do not promote Amit while hiding corrupt current state.

---

# 89. Implementation report

After implementation create:

```text
docs/inspect/CUSTOMER_PRIMARY_CONTACT_PROMOTION_V1_IMPLEMENTATION_REPORT.md
```

The report must include:

1. repository branch/HEAD before and after;
2. files changed;
3. final public tools;
4. exact contracts;
5. exact approval action;
6. coherent-state rules;
7. interpretation of valid existing-old-primary replacement;
8. selected Contact relationship safety;
9. old primary relationship safety;
10. exact relationship fingerprint;
11. exact primary-state fingerprint;
12. membership enforcement;
13. selected Contact save flow;
14. native old-primary demotion behavior;
15. Customer save/projection refresh;
16. CRM/native hook behavior;
17. permission matrix;
18. transaction ownership;
19. idempotency/stale behavior;
20. data-minimization output;
21. profile/transport registration;
22. tests added/changed;
23. exact test commands/results;
24. pre-existing failures separately identified;
25. deviations from Task 62 and why;
26. confirmation Task 57/60/61 behavior remains unchanged;
27. confirmation Task 57 internal commit hardening was not silently folded in;
28. runtime metadata/live-write verification status.

---

# 90. Limitations intentionally retained

After Task 63 these remain unsupported:

- clear/unset Customer primary Contact;
- arbitrary primary-state repair;
- shared Contact promotion;
- shared old-primary demotion;
- arbitrary Dynamic Link mutation;
- Contact unlink/delete/merge;
- Supplier Contact promotion;
- Purchase/Accounts Contact primary tools;
- bulk operations;
- Task 57 transaction-boundary hardening;
- silent repair of inconsistent primary state.

These are explicit scope boundaries.

---

# 91. Exact next task

After Task 63 implementation report is reviewed and accepted:

1. provide the Git commit message for Task 63;
2. create:

```text
Task 64 — Contact Relationship Transaction and Primary-State Repair Hardening Audit
```

Task 64 should audit separately:

```text
Task 57 internal commit normalization
safe repair of inconsistent Customer/Contact primary state
clear/unset primary Contact semantics
public relationship-count naming/versioning
shared Contact relationship hardening
whether destructive unlink/delete flows can be safely added later
```

Do not start Task 64 during Task 63.
