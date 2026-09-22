# Task 61 — Customer-Scoped Contact Detail and Communication Update Implementation

## Status

**Implementation task**

The design for this task was completed in Task 58:

```text
docs/inspect/CUSTOMER_SCOPED_CONTACT_DETAIL_EMAIL_PHONE_UPDATE_AUDIT.md
```

Task 57 and Task 60 are now the existing Contact capability baseline:

```text
Task 57:
search_contacts
prepare_customer_contact
confirm_customer_contact

Task 60:
prepare_contact
confirm_contact
```

Task 61 adds Customer-scoped update capability for an **existing Contact already linked to the selected Customer**.

This task must not redesign standalone Contact creation or Customer Contact linking.

---

# 1. Objective

Implement:

```text
prepare_contact_update
confirm_contact_update
```

in the Sales profile.

The capability must support one bounded Contact mutation per prepare/confirm cycle.

Approved V1 operation set:

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

The implementation must:

- use native Frappe Contact documents;
- verify the Contact belongs to the selected Customer;
- reject shared/multi-party Contacts in V1;
- mutate Contact Email / Contact Phone child rows rather than parent projections;
- refresh stored Customer Contact projections when the edited Contact is the Customer's primary Contact;
- use normal permissions;
- use the existing shared approval store;
- bind exact child-row state for stale detection;
- execute one approved operation atomically;
- preserve installed Frappe/ERPNext/CRM validation and hooks.

---

# 2. Business problem

Current capabilities support:

```text
create standalone Contact
create Contact already linked to Customer
link existing Contact to Customer
search Contacts
```

They do not support:

```text
Change Amit's email for ABC Pvt Ltd
Change Amit's mobile
Add a secondary email
Make another existing email primary
Correct Amit's last name
Update designation/department
```

Task 61 fills that bounded update gap.

---

# 3. Customer-scoped boundary

Every Task 61 update requires:

```text
exact Customer reference
+
exact Contact reference
+
Customer read permission
+
Contact read permission
+
Contact write permission
+
Contact.has_link("Customer", customer.name)
```

The Contact must already be linked to that Customer.

If not:

```text
CONTACT_NOT_LINKED_TO_CUSTOMER
```

Do not auto-link as part of update.

Linking remains Task 57.

---

# 4. Shared Contact V1 safety rule

If the target Contact has **any additional party relationship** beyond the target Customer, reject the update in V1.

Examples:

```text
Customer ABC + Customer XYZ
Customer ABC + Supplier DEF
Customer ABC + another business party
```

Return:

```text
CONTACT_SHARED_WITH_OTHER_PARTIES
```

Do not expose unrelated party names.

A bounded count may be returned only if it is permission-safe.

Task 61 must not update a shared Contact.

---

# 5. Existing Contact tools to reuse

Reuse existing:

```text
search_contacts
ContactReference
CustomerReference
ContactProjection
PublicContractModel
InteractionDirective
ToolError
ApprovalStore
claim_for_confirm_write
stable_fingerprint
```

Reuse current Task 57/60 permission, projection, duplicate, registry, and transport patterns when correct.

Do not create duplicate parallel abstractions.

---

# 6. Mandatory pre-implementation inspection

Before editing production code, inspect current implementations of:

```text
mcp_erpnext/contracts/masters/contact.py
mcp_erpnext/services/masters/customer_contact.py
mcp_erpnext/services/masters/contact.py
mcp_erpnext/tools/masters/customer_contact.py
mcp_erpnext/tools/masters/contact.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
docs/TOOLS.md
```

Inspect tests from Task 57 and Task 60.

Also re-check installed source for:

```text
Contact.validate
Contact.set_primary_email
Contact.set_primary
Contact Email
Contact Phone
Customer.customer_primary_contact
Customer fetch projections
Document.save
child-table synchronization
CRM Contact validate hook
ERPNext party/contact defaults
```

If current source materially differs from Task 58 audit, document the mismatch before implementation.

---

# 7. Explicitly out of scope

Do not implement:

- Contact delete;
- Contact merge;
- Contact rename;
- Contact unlink;
- Contact link creation;
- arbitrary Dynamic Link mutation;
- Contact primary-party promotion;
- clearing Customer primary Contact;
- email removal;
- phone/mobile removal;
- clearing primary email;
- clearing primary phone/mobile;
- multiple operations in one prepare;
- arbitrary field patching;
- raw child-table patching;
- shared Contact editing;
- Supplier Contact updates;
- Purchase Contact updates;
- Accounts Contact updates;
- broad global Contact update/search;
- historical transaction rewrites;
- generic Contact CRUD;
- generic lifecycle child-table mutation.

---

# 8. Public tools

Add exactly:

```text
prepare_contact_update
confirm_contact_update
```

Do not add one tool per operation.

Do not add:

```text
update_contact_email
update_contact_phone
update_contact_details
```

as separate public tools.

The mutation is a typed discriminated union inside one prepare contract.

---

# 9. Public prepare contract

Conceptually:

```text
PrepareContactUpdateInput {
  customer: CustomerReference
  contact: ContactReference
  operation: ContactUpdateOperation
}
```

The exact models must follow current Pydantic/PublicContractModel patterns.

Use:

```text
extra="forbid"
```

or the current equivalent strict contract behavior.

---

# 10. Contact update operation union

Implement one typed operation per prepare request.

Approved operations:

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

Do not allow arrays/lists of operations.

---

# 11. `set_details`

Allowed fields:

```text
first_name
middle_name
last_name
company_name
designation
department
```

At least one actual field change must be supplied unless the operation is recognized as idempotent.

Reject:

```text
full_name
email_id
mobile_no
phone
links
is_primary_contact
user
name
owner
modified
arbitrary custom fields
```

Normal Contact validation derives:

```text
full_name
```

The persisted Contact document `name` must remain unchanged.

Do not rename the Contact document.

---

# 12. Detail update preview

Preview should show:

```text
Contact reference
Customer reference
full_name_before
full_name_after
changed fields
unchanged Contact.name
Customer projection refresh required? true|false
CRM snapshot refresh may occur? true|false
other_party_link_count = 0
```

Do not expose raw Contact JSON.

---

# 13. `add_email`

Input concept:

```text
action = add_email
email
make_primary = false
```

Rules:

- validate one email;
- reject multi-address values;
- append exactly one Contact Email row;
- no raw child row input;
- if Contact currently has zero email rows, native semantics make the sole row primary;
- if existing primary exists and `make_primary=false`, new row is secondary;
- if `make_primary=true`, clear `is_primary` on existing rows and mark the new row primary.

If requested state is already exactly present:

```text
idempotent=true
```

Do not append a duplicate row.

---

# 14. `replace_primary_email`

Input concept:

```text
current_email
email
```

The public caller does not supply child row name.

Server must resolve the exact current primary Contact Email row.

If multiple rows match the public selector:

```text
needs_selection / CONTACT_EMAIL_AMBIGUOUS
```

If the current primary row does not exist:

```text
CONTACT_EMAIL_NOT_FOUND
```

Mutate the existing selected child row value in place.

Preserve child row identity.

Do not remove/recreate the row.

---

# 15. `set_primary_email`

Input concept:

```text
email
```

The value must resolve to exactly one existing Contact Email row.

Set that row:

```text
is_primary=1
```

and clear the flag on all other email rows.

Do not delete any email row.

If already primary:

```text
idempotent=true
```

---

# 16. Email duplicate policy

Do not invent global uniqueness.

For same Contact:

- exact already-present requested state may be idempotent;
- duplicate row creation is not allowed;
- ambiguous duplicates require selection/input.

For other Contacts visible within permitted target Customer scope:

```text
CONTACT_DUPLICATE_SUSPECTED
```

Do not merge.

Do not reveal inaccessible Contacts.

Use case-insensitive email comparison for duplicate suspicion, consistent with existing project email comparison.

Do not rewrite stored casing solely for comparison.

---

# 17. `add_phone`

Input concept:

```text
phone
kind = "phone" | "mobile"
make_primary = false
```

No `both` kind.

For:

```text
kind="phone"
```

append one Contact Phone row.

If `make_primary=true`:

```text
is_primary_phone=1
```

and clear that flag on other rows.

For:

```text
kind="mobile"
```

use:

```text
is_primary_mobile_no=1
```

and clear that flag on other rows if `make_primary=true`.

Do not alter the other independent flag family unless required by exact native preservation of the selected row.

---

# 18. First phone/mobile semantics

Unlike email, Frappe does not automatically make the first phone row primary.

Therefore the public semantic must remain explicit.

If no primary mobile exists and user calls:

```text
add_phone(kind="mobile", make_primary=false)
```

the row may remain secondary and parent `mobile_no` may remain empty.

The preview must make that consequence clear.

Do not silently make it primary.

---

# 19. `replace_primary_phone`

Input:

```text
current_phone
phone
```

Resolve exactly one row carrying:

```text
is_primary_phone=1
```

Mutate that row's `phone` value in place.

Preserve:

```text
child row name
is_primary_phone
existing is_primary_mobile_no flag
```

unless the approved operation explicitly changes the mobile-primary semantics, which this action does not.

---

# 20. `replace_primary_mobile`

Input:

```text
current_mobile
phone
```

Resolve exactly one row carrying:

```text
is_primary_mobile_no=1
```

Mutate that row's `phone` value in place.

Preserve the independent phone-primary flag.

---

# 21. `set_primary_phone`

Input:

```text
phone
```

Resolve exactly one existing Contact Phone row.

Set:

```text
is_primary_phone=1
```

on selected row and clear that flag from all other rows.

Do not alter:

```text
is_primary_mobile_no
```

flags.

If already primary:

```text
idempotent=true
```

---

# 22. `set_primary_mobile`

Input:

```text
phone
```

Resolve exactly one existing Contact Phone row.

Set:

```text
is_primary_mobile_no=1
```

on selected row and clear that flag from all other rows.

Do not alter:

```text
is_primary_phone
```

flags.

If already primary:

```text
idempotent=true
```

---

# 23. Same row carrying both native flags

Native Frappe permits one Contact Phone row to carry both:

```text
is_primary_phone=1
is_primary_mobile_no=1
```

Task 61 must preserve such existing state when an operation does not target both semantics.

Do not expose a public:

```text
kind="both"
```

operation.

Do not silently split the row.

Do not silently clear the unrelated primary flag.

---

# 24. Phone duplicate policy

Use bounded normalized comparison only for duplicate suspicion.

Do not rewrite stored formatting.

Do not claim Frappe global phone uniqueness.

Same-Contact exact requested state:

```text
idempotent
```

Duplicate row creation:

```text
reject / duplicate suspected
```

Visible same normalized number on another relevant Contact:

```text
CONTACT_DUPLICATE_SUSPECTED
```

Hidden Contact:

```text
do not disclose
```

---

# 25. Child row identity

Public caller must not supply child row names.

During prepare, server resolves selected child row(s).

Approval payload must internally bind for each affected row:

```text
parent Contact name
child doctype
parentfield
child row name
current value
current primary flags
```

Also bind:

```text
Contact.modified
complete affected child-row fingerprint
target value
requested primary change
```

At confirm, reload and verify both:

```text
row name
current row state
```

Do not rely only on mutable value matching.

---

# 26. Ambiguous child row selection

If an exact public value identifies multiple rows:

```text
needs_selection
```

or:

```text
CONTACT_EMAIL_AMBIGUOUS
CONTACT_PHONE_AMBIGUOUS
```

using current interaction conventions.

Return only the minimum candidate information required to choose.

Do not expose unnecessary child metadata.

Do not guess destructive/primary intent.

---

# 27. Shared Contact detection

At prepare:

1. verify target Customer link exists;
2. inspect Contact relationships;
3. determine whether Contact has any additional party link.

At confirm:

repeat the check.

If it becomes shared after prepare:

```text
CONTACT_STALE_STATE
```

or the exact current stale/shared code chosen by the implementation.

Do not continue the mutation.

---

# 28. Party-link counting

Task 58/59 identified that Task 57's current `other_party_link_count` naming may count all non-target Dynamic Links rather than only business party links.

For Task 61's **security decision**, do not rely on a misleading display helper.

Implement or reuse a clearly defined relationship fingerprint/count that conservatively detects any additional relationship that should block V1 update.

Requirements:

- no unrelated linked entity names in public result;
- no false claim that count represents only Customers if it includes more types;
- use a separate internal relationship fingerprint if needed.

Do not silently change Task 57's public search projection semantics unless required.

---

# 29. Customer-primary detection

Determine whether:

```text
customer.customer_primary_contact == contact.name
```

at prepare and confirm.

Bind this state into approval.

If false:

```text
Contact-only update
```

If true:

```text
Contact update + Customer projection refresh
```

If this status changes after prepare:

```text
CONTACT_STALE_STATE
```

Do not guess.

---

# 30. Customer projection fields

When the edited Contact is the Customer's primary Contact, Customer stores fetch projections:

```text
email_id
mobile_no
first_name
last_name
```

Task 61 must not directly assign these fields.

Do not use:

```text
frappe.db.set_value
```

for them.

After Contact save, perform a normal Customer document save so native Link fetch behavior refreshes projections.

---

# 31. Customer write permission

If the target Contact is the Customer primary Contact, prepare must require:

```text
Customer write
```

in addition to Contact write.

If Customer write is missing:

```text
CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED
```

Do not allow Contact mutation that would knowingly leave Customer stored projections stale.

Fail before write.

---

# 32. Non-primary Contact update

If the Contact is linked to the Customer but is not:

```text
customer_primary_contact
```

then:

```text
do not save Customer
```

Only save Contact.

Customer read permission is still required because Customer context is the authorization boundary.

---

# 33. Customer projection refresh transaction

For Customer-primary Contact:

```text
Contact.save(ignore_permissions=False)
Customer.save(ignore_permissions=False)
```

must happen in one logical confirmation transaction.

No commit between the two.

If Customer save fails:

```text
rollback Contact update
```

If Contact/CRM hook fails:

```text
Customer must not commit
```

One final commit only after both succeed.

---

# 34. Contact-only transaction

For non-primary Contact:

```text
Contact.save(ignore_permissions=False)
```

then one outer commit.

On failure:

```text
rollback
```

---

# 35. No direct projection mutation

Never directly write:

```text
Contact.email_id
Contact.phone
Contact.mobile_no
Contact.full_name

Customer.email_id
Customer.mobile_no
Customer.first_name
Customer.last_name
```

These are native-derived/fetch projection values.

Mutate source fields/child rows and let normal validation derive projections.

---

# 36. CRM Contact hook

Normal Contact save must run installed:

```text
CRM Contact validate hook
```

Task 58 found it may refresh linked CRM Deal email/mobile snapshots.

Preserve this native behavior.

Preview may disclose only:

```text
native CRM contact snapshots may refresh
```

Do not expose:

```text
Deal names
Deal values
CRM data
```

Do not bypass hooks.

---

# 37. Prepare must remain non-mutating

Do not call a full hook-bearing Contact save/validation path during prepare if it can write.

Prepare may:

- load Customer;
- load Contact;
- inspect child rows;
- inspect relationships;
- validate typed semantic inputs;
- validate email/phone values safely;
- build an in-memory proposed state;
- derive deterministic preview;
- calculate fingerprints;
- query permission-visible duplicate candidates;
- create approval record.

Prepare must not:

- save Contact;
- save Customer;
- mutate business DB state;
- commit;
- run write-capable Contact hooks.

---

# 38. Native validation on confirm

Confirm must use:

```python
contact.save(ignore_permissions=False)
```

after mutating the loaded document in memory.

Do not bypass:

- write permission;
- modified timestamp checks;
- child-table synchronization;
- email/phone validation;
- Contact.validate;
- CRM hooks;
- ERPNext hooks.

---

# 39. Approval action

Use a new action:

```text
customer_contact_update
```

unless current canonical naming requires the exact equivalent.

Do not reuse:

```text
customer_contact
contact_create
```

The action must remain semantically distinct.

---

# 40. Approval payload

Bind at least:

```text
site
authenticated user
profile = sales
action = customer_contact_update

Customer name
Customer modified

Contact name
Contact modified

Customer-Contact relationship fingerprint
other relationship/shared state

whether Contact is Customer primary

operation type
operation target values

selected child row names
selected child row values
selected child primary flags
all affected child-row state needed for primary uniqueness

duplicate candidate fingerprint

predicted resulting primary email
predicted resulting primary phone
predicted resulting primary mobile

Customer projection refresh required
```

Use stable fingerprint/current project conventions.

---

# 41. Confirm input

Confirm input remains:

```text
approval_token
confirm
```

Do not allow re-submission of:

- Customer;
- Contact;
- operation;
- child rows;
- target values;
- approval policy.

Confirm operates only on approved stored state.

---

# 42. Confirm flow

Conceptual flow:

```text
claim_for_confirm_write
    ->
reload Customer
    ->
reload Contact
    ->
recheck Customer read
    ->
recheck Contact read/write
    ->
recheck Customer write if primary Contact
    ->
recheck Customer-Contact membership
    ->
recheck shared Contact rule
    ->
recheck Customer primary state
    ->
compare modified/fingerprints
    ->
recheck selected child rows
    ->
recheck duplicate target state
    ->
apply exactly one approved in-memory mutation
    ->
Contact.save(ignore_permissions=False)
    ->
if primary: Customer.save(ignore_permissions=False)
    ->
one commit
    ->
bounded result
```

On any failure:

```text
rollback
```

---

# 43. Stale-state conditions

Treat as stale / re-prepare required:

- Customer modified;
- Contact modified;
- Customer link removed;
- Contact becomes shared;
- Contact becomes/unbecomes Customer primary;
- selected child row removed;
- selected child row name changes unexpectedly;
- selected child value changes;
- selected child primary flags change;
- affected row set changes so primary uniqueness differs;
- new scoped duplicate candidate appears;
- permission state changes materially.

Do not guess through these changes.

---

# 44. Error semantics

Reuse canonical project codes when available.

Required semantic conditions include:

```text
CUSTOMER_NOT_FOUND
CONTACT_NOT_FOUND
CONTACT_NOT_LINKED_TO_CUSTOMER
CONTACT_SHARED_WITH_OTHER_PARTIES

CONTACT_EMAIL_NOT_FOUND
CONTACT_PHONE_NOT_FOUND
CONTACT_EMAIL_AMBIGUOUS
CONTACT_PHONE_AMBIGUOUS

CONTACT_INVALID_EMAIL
CONTACT_INVALID_PHONE
CONTACT_DUPLICATE_SUSPECTED

CONTACT_STALE_STATE
CONTACT_CHILD_STALE_STATE

CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED
PERMISSION_DENIED

CONFIRMATION_REQUIRED
CONFIRMATION_UNAVAILABLE
STALE_CONFIRMATION
```

Do not add duplicates of existing equivalent codes.

---

# 45. `needs_input` / `needs_selection`

Examples:

```text
"Change Amit's phone"
```

when Contact has both primary phone and primary mobile:

```text
needs_input
```

Ask semantic clarification:

```text
phone or mobile?
```

If public selector matches multiple child rows:

```text
needs_selection
```

Do not infer.

---

# 46. Idempotency

Safe idempotent cases:

- detail field already has requested value;
- requested email already exists with requested primary state;
- selected email already primary;
- selected phone already requested primary-phone state;
- selected phone already requested primary-mobile state;
- replace action target equals exact current selected value and state.

Return:

```text
updated / idempotent=true
```

without unnecessary business save where possible.

---

# 47. Non-idempotent ambiguity

Do not call these idempotent:

- selected row disappeared;
- selected row value changed;
- new duplicate row makes selector ambiguous;
- Customer link changed;
- Contact sharing changed;
- Customer-primary state changed.

These require re-prepare.

---

# 48. Duplicate lookup scope

Task 61 update is Customer-scoped.

Duplicate checks must be permission-aware and bounded.

Do not perform unrestricted global person-data enumeration.

For target email/phone values, use exact/scoped visible duplicate detection sufficient to warn about likely duplicate communication identities.

Do not disclose inaccessible Contacts.

Do not merge Contacts.

---

# 49. Data minimization

Prepare/result may include only what user needs to review:

```text
Customer reference
Contact reference
full_name_before
full_name_after
operation summary
selected_current_value
proposed_value
selected_row_is_primary
resulting_primary_email
resulting_primary_phone
resulting_primary_mobile
Customer projection refresh true|false
CRM snapshot refresh may occur true|false
other_party_link_count = 0
```

Do not expose:

- full Contact JSON;
- all links;
- unrelated party names;
- all child row names;
- addresses;
- comments;
- communications;
- CRM Deal records;
- User details;
- system fields;
- arbitrary custom fields.

---

# 50. Result contract

Successful confirm should return a bounded:

```text
status = updated
idempotent = true|false
Customer reference
Contact projection
operation summary
resulting primary communication values
Customer projection refresh result when applicable
```

Do not return raw child-table dumps.

If Customer projection was refreshed, return only bounded refreshed fields required to demonstrate consistency.

---

# 51. Existing transaction snapshots

Task 61 must not update historical:

```text
Quotation
Sales Order
Sales Invoice
```

fields such as:

```text
contact_person
contact_display
contact_email
contact_mobile
```

Existing copied transaction values remain historical snapshots.

Future documents may derive updated native Contact values.

---

# 52. Email service regression

Do not rewrite existing email recipient logic unless a failing integration test proves Task 61 caused an issue.

Verify:

- primary Customer stored email refreshes when primary Contact email changes;
- linked non-primary Contact updates do not rewrite Customer projection;
- existing transaction `contact_email` stays unchanged;
- inaccessible/unrelated Contact is not selected as recipient.

---

# 53. Contact document name

`set_details` may change:

```text
first_name
middle_name
last_name
company_name
```

and therefore:

```text
full_name
```

but must not rename:

```text
Contact.name
```

Return stable Contact reference.

Rename remains out of scope.

---

# 54. Parent detail field validation

Use normal native Contact validation where applicable.

Trim public strings according to current project conventions.

Do not invent destructive coercion.

If an unchanged `set_details` request produces no effective changes:

```text
idempotent=true
```

---

# 55. Email child-table synchronization

When manipulating email rows:

- operate on loaded Contact child rows;
- preserve child row names;
- do not replace the entire table blindly;
- allow `Contact.save()` to synchronize children;
- ensure exactly one primary email where approved/native rules require one;
- never introduce multiple primary rows.

Do not use direct child SQL.

---

# 56. Phone child-table synchronization

When manipulating phone rows:

- preserve child names;
- modify only intended values/flag family;
- maintain independent phone/mobile primary semantics;
- do not replace table blindly;
- allow native save/child sync;
- do not introduce unintended flag changes.

Do not use direct child SQL.

---

# 57. No removal operations

Reject unsupported attempts to:

```text
remove_email
remove_phone
clear_primary_email
clear_primary_phone
clear_primary_mobile
```

with a bounded unsupported/input error.

Do not interpret replacement as deletion.

Removal requires a later dedicated destructive contract.

---

# 58. No Contact primary-party promotion

Do not expose:

```text
make_primary_contact
set_contact_primary_for_customer
```

Task 61 primary communication rows are unrelated to:

```text
Contact.is_primary_contact
```

Do not confuse:

```text
primary email/mobile/phone
```

with:

```text
primary Contact for Customer
```

Existing Contact primary-party promotion remains separate future work.

---

# 59. Sales-only registration

After Task 61, Sales Contact surface includes:

```text
search_contacts
prepare_contact
confirm_contact
prepare_customer_contact
confirm_customer_contact
prepare_contact_update
confirm_contact_update
```

Purchase and Accounts must not expose the update pair.

---

# 60. Transport parity

Update:

```text
contracts
tool registration
Sales profile
contract registry
remote operations
REST typed dispatch
generated tool catalog/docs
```

All transports must invoke the same business service.

No REST-specific mutation logic.

No MCP-specific mutation logic.

---

# 61. Expected code placement

Prefer extending the existing Contact modules cleanly.

Likely:

```text
mcp_erpnext/contracts/masters/contact.py
mcp_erpnext/services/masters/contact_update.py
mcp_erpnext/tools/masters/contact.py
or a narrowly named update tool module

mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
```

Reuse helpers from:

```text
customer_contact.py
contact.py
```

only when semantics match.

Do not create circular dependencies or duplicate large helpers.

---

# 62. Required tests — contract

Test every operation model.

Reject:

- unknown action;
- multiple operations;
- raw field patch dict;
- raw email child rows;
- raw phone child rows;
- raw links;
- `is_primary_contact`;
- system fields;
- arbitrary custom fields.

Ensure all public models forbid extras.

---

# 63. Required tests — Customer/Contact boundary

Test:

- valid exact Customer + Contact link;
- Customer not found;
- Contact not found;
- Customer read denied;
- Contact read denied;
- Contact write denied;
- Contact not linked to Customer;
- link removed after prepare;
- link changed after prepare;
- global fuzzy Contact update resolution unavailable.

---

# 64. Required tests — shared Contacts

Test:

- only target Customer link -> update permitted;
- multiple Customer links -> blocked;
- Customer + Supplier -> blocked;
- another relevant party -> blocked;
- no unrelated party names returned;
- Contact becomes shared after prepare -> stale/reject.

---

# 65. Required tests — `set_details`

Test each field:

```text
first_name
middle_name
last_name
company_name
designation
department
```

Test:

- valid update;
- multiple allowed detail fields in one `set_details` operation;
- full_name recomputed;
- Contact.name unchanged;
- unchanged input idempotent;
- Contact stale;
- Customer-primary detail update refreshes Customer first/last projections;
- non-primary detail update does not save Customer.

---

# 66. Required tests — add email

Test:

- first email becomes native primary;
- add secondary preserves current primary;
- `make_primary=true` moves primary flag;
- exact same requested row/state idempotent;
- duplicate same Contact does not create another row;
- invalid email;
- scoped visible duplicate;
- hidden duplicate not leaked;
- stale row set.

---

# 67. Required tests — replace primary email

Test:

- exact current primary selected;
- child row value changed in place;
- row name preserved;
- parent `Contact.email_id` derived;
- Customer primary projection refreshed when applicable;
- wrong current email -> not found;
- ambiguous selector -> needs selection;
- row changed after prepare -> child stale;
- replacement equal current -> idempotent.

---

# 68. Required tests — set primary email

Test:

- select secondary email;
- selected row becomes primary;
- previous primary cleared;
- rows preserved;
- Contact.email_id derived;
- already-primary idempotent;
- ambiguous selector;
- stale flags.

---

# 69. Required tests — add phone/mobile

Test:

- phone secondary;
- phone primary;
- mobile secondary;
- mobile primary;
- first row does not become primary unless requested;
- same row duplicate state idempotent;
- invalid phone;
- normalized duplicate;
- unrelated primary flag family preserved.

---

# 70. Required tests — replace primary phone

Test:

- correct primary-phone row selected;
- row value changed in place;
- child name preserved;
- `is_primary_phone` retained;
- `is_primary_mobile_no` retained if present;
- Contact.phone derived;
- stale/ambiguous/not-found behavior.

---

# 71. Required tests — replace primary mobile

Equivalent tests for:

```text
is_primary_mobile_no
Contact.mobile_no
```

Preserve independent phone-primary state.

---

# 72. Required tests — set primary phone/mobile

Test each independently:

```text
set_primary_phone
set_primary_mobile
```

Verify:

- selected flag set;
- only same flag family cleared on other rows;
- other flag family unchanged;
- same row carrying both flags remains valid when appropriate;
- already requested primary state idempotent.

---

# 73. Required tests — Customer projection refresh

Test:

- Contact is Customer primary;
- Customer write permitted;
- Contact save then Customer save;
- Customer email/mobile/name projections refreshed;
- no direct projection assignment;
- missing Customer write permission blocks before Contact mutation;
- Customer save failure rolls back Contact update;
- Contact hook failure prevents Customer commit;
- primary state changes after prepare -> stale.

---

# 74. Required tests — non-primary Customer Contact

Test:

- Contact update succeeds;
- Customer not saved;
- no Customer write permission required;
- Customer projections unchanged;
- bounded result says projection refresh false.

---

# 75. Required tests — CRM hooks

Test/mocking boundary should prove:

- Contact save invokes native hook path;
- Task 61 does not bypass CRM validate;
- hook failure rolls back;
- public result does not expose Deal data;
- preview only contains bounded side-effect warning.

Do not require real CRM Deal mutation on a business site.

---

# 76. Required tests — approval

Test:

- prepare non-mutating;
- approval token generated;
- `customer_contact_update` action bound;
- valid confirm;
- wrong user;
- wrong site;
- wrong profile/action;
- expiry;
- replay;
- `confirm=false`;
- self-approval unavailable;
- operation payload cannot be altered after prepare.

---

# 77. Required tests — stale state

Test:

- Customer modified;
- Contact modified;
- Contact link removed;
- Contact becomes shared;
- Customer primary changes;
- selected email row changed;
- selected phone row changed;
- row removed;
- primary flags changed;
- new scoped duplicate appears.

Each must prevent unsafe write.

---

# 78. Required tests — atomicity

For non-primary:

```text
one Contact save
one final commit
```

For Customer-primary:

```text
Contact save
Customer save
one final commit
```

Test no commit occurs between Contact and Customer save.

Test rollback on:

```text
Contact save failure
CRM hook failure
Customer save failure
```

---

# 79. Required tests — data minimization

Assert no output contains:

- unrelated Dynamic Link names;
- all links;
- child row names except internal approval state;
- raw Contact JSON;
- comments;
- communications;
- addresses;
- User info;
- CRM Deal records;
- system metadata.

---

# 80. Required tests — transaction/history regression

Verify existing:

```text
Quotation
Sales Order
Sales Invoice
```

copied Contact/email/mobile fields are not rewritten.

Future native resolution may see updated values.

---

# 81. Required tests — profile and transport

Verify:

```text
Sales:
  update pair present

Purchase:
  absent

Accounts:
  absent
```

Verify:

- contracts registry;
- remote operation registry;
- REST typed handler;
- tool registration;
- catalog generation;
- MCP/stdio parity;
- same service implementation.

---

# 82. Existing Contact capability regression

Task 61 must not regress:

```text
search_contacts
prepare_contact
confirm_contact
prepare_customer_contact
confirm_customer_contact
```

Run Task 57 and Task 60 focused tests.

Do not alter standalone Contact creation semantics.

Do not alter Customer Contact create/link semantics.

---

# 83. Test execution strategy

Run narrow Task 61 tests first.

Then affected Contact suites.

Then profile/REST/registration suites.

Then broader app discovery if normal for the project.

Document:

```text
exact commands
pass counts
new failures
pre-existing failures
environment failures
```

Do not fix unrelated failures inside Task 61.

---

# 84. Code-quality checks

Run available repository checks:

```text
Python compile/AST
git diff --check
tool catalog --check
focused tests
broader affected tests
```

Run Ruff only if installed/configured.

Do not install tooling as part of Task 61.

---

# 85. Acceptance criteria — tools

- [ ] `prepare_contact_update` exists.
- [ ] `confirm_contact_update` exists.
- [ ] Sales-only exposure.
- [ ] existing `search_contacts` reused.
- [ ] no operation-specific public tool explosion.
- [ ] one typed operation per prepare.

---

# 86. Acceptance criteria — relationship safety

- [ ] exact Customer required.
- [ ] exact Contact required.
- [ ] Contact must link to Customer.
- [ ] shared Contact blocked.
- [ ] unrelated party names never exposed.
- [ ] shared/link state rebound at confirm.

---

# 87. Acceptance criteria — communication correctness

- [ ] email child rows authoritative.
- [ ] phone child rows authoritative.
- [ ] parent projections never directly written.
- [ ] child row identity preserved for replacement.
- [ ] email primary flags native-consistent.
- [ ] phone/mobile primary flags independent.
- [ ] no remove/clear operations.
- [ ] no raw child patch API.

---

# 88. Acceptance criteria — Customer projections

- [ ] Customer-primary Contact detected.
- [ ] Customer write permission required when refresh needed.
- [ ] missing Customer write blocks before Contact mutation.
- [ ] normal Customer save used for refresh.
- [ ] Customer projection fields not directly assigned.
- [ ] non-primary Contact does not trigger Customer save.
- [ ] Contact + Customer changes atomic.

---

# 89. Acceptance criteria — approval/stale

- [ ] shared ApprovalStore reused.
- [ ] `customer_contact_update` action or canonical equivalent.
- [ ] `claim_for_confirm_write` used.
- [ ] child row names/flags internally fingerprinted.
- [ ] Customer/Contact modified state bound.
- [ ] relationship/shared state bound.
- [ ] duplicate state rebound.
- [ ] replay impossible.
- [ ] stale child rows never guessed through.

---

# 90. Acceptance criteria — native Frappe behavior

- [ ] `Contact.save(ignore_permissions=False)` used.
- [ ] `Customer.save(ignore_permissions=False)` used only when required.
- [ ] no `ignore_permissions=True`.
- [ ] no raw SQL business mutation.
- [ ] no direct child SQL.
- [ ] CRM/Frappe/ERPNext hooks preserved.
- [ ] one final commit per approved operation.
- [ ] rollback on failure.

---

# 91. Acceptance criteria — regression/data safety

- [ ] Task 57 still passes.
- [ ] Task 60 still passes.
- [ ] historical transaction snapshots unchanged.
- [ ] email recipient logic not broadened.
- [ ] no hidden Contact data exposed.
- [ ] no Supplier/Purchase scope added.
- [ ] no generic Contact CRUD added.

---

# 92. Expected flow — detail correction

User:

```text
Correct Amit Shah's last name to Mehta for ABC Pvt Ltd
```

Flow:

```text
resolve exact Customer
resolve exact linked Contact
check single-party rule
prepare_contact_update(set_details)
preview full_name before/after
approval
confirm
recheck state
Contact.save
if Customer primary: Customer.save
commit
```

Contact document name remains stable.

---

# 93. Expected flow — replace primary email

User:

```text
Change Amit's primary email from old@abc.com to accounts@abc.com
```

Flow:

```text
resolve Customer + Contact
find exact primary Contact Email child row
check duplicate target
fingerprint child row
preview replacement
approval
confirm
recheck row name/value/flags
mutate row in place
Contact.save
if Customer primary: Customer.save
commit
```

No delete/recreate.

---

# 94. Expected flow — promote secondary email

User:

```text
Make billing@abc.com Amit's primary email
```

Flow:

```text
resolve exact existing email row
preview old/new primary state
approval
confirm
set selected primary
clear previous primary flag
Contact.save
refresh Customer if required
commit
```

Rows remain.

---

# 95. Expected flow — ambiguous phone

User:

```text
Change Amit's phone
```

Contact has:

```text
primary phone
primary mobile
```

Expected:

```text
needs_input
```

Ask:

```text
phone or mobile?
```

Do not guess.

---

# 96. Expected flow — shared Contact

Contact is linked to:

```text
ABC Pvt Ltd
XYZ Pvt Ltd
```

User asks:

```text
Change Amit's email for ABC Pvt Ltd
```

Expected:

```text
CONTACT_SHARED_WITH_OTHER_PARTIES
```

No mutation.

Do not expose `XYZ Pvt Ltd`.

---

# 97. Expected flow — Customer primary without Customer write

Contact is:

```text
ABC.customer_primary_contact
```

User has:

```text
Contact write
Customer read
no Customer write
```

Expected prepare result:

```text
CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED
```

No approval token for an unsafe mutation.

No Contact write.

---

# 98. Implementation report

After implementation create:

```text
docs/inspect/CUSTOMER_SCOPED_CONTACT_DETAIL_COMMUNICATION_UPDATE_IMPLEMENTATION_REPORT.md
```

Report must include:

1. branch and HEAD before/after;
2. files changed;
3. final tools;
4. exact final operation union;
5. exact contracts;
6. Customer/Contact membership enforcement;
7. shared Contact detection;
8. detail update behavior;
9. email operations;
10. phone/mobile operations;
11. child row identity/fingerprinting;
12. duplicate policy;
13. Customer-primary detection;
14. Customer projection refresh;
15. permission matrix;
16. CRM/native hook preservation;
17. approval action/fingerprint;
18. transaction ownership;
19. idempotency/stale semantics;
20. data-minimization result fields;
21. profile/transport registration;
22. tests added/changed;
23. exact test commands/results;
24. pre-existing failures separately identified;
25. deviations from Task 58 and why;
26. confirmation Task 57/60 behavior remains unchanged;
27. confirmation no manual business/site data mutation was used for verification.

---

# 99. Limitations intentionally retained

After Task 61 these remain unsupported:

- shared Contact editing;
- email removal;
- phone/mobile removal;
- clearing primary communication value;
- Contact delete;
- Contact unlink;
- Contact merge;
- Contact rename;
- arbitrary Dynamic Link mutation;
- existing Contact primary-party promotion;
- Supplier Contact management;
- Purchase/Accounts Contact management;
- bulk Contact operations;
- arbitrary Contact patching;
- generic lifecycle child-table mutation.

These are scope boundaries, not defects.

---

# 100. Exact next task

After Task 61 implementation report is reviewed and accepted:

1. provide the Git commit message for Task 61;
2. create the next audit task:

```text
Task 62 — Customer Contact Primary Promotion and Relationship Hardening Audit
```

Task 62 should audit:

- promoting an existing linked Contact to Customer primary;
- `Contact.is_primary_contact` cross-party semantics;
- `Customer.customer_primary_contact`;
- native locking/demotion behavior;
- Customer projection refresh;
- shared Contact restrictions;
- Task 57 transaction-boundary hardening;
- exact party-link count semantics;
- whether Task 57 create/link commit ownership should be normalized before primary promotion.

Do not begin Task 62 during Task 61.
