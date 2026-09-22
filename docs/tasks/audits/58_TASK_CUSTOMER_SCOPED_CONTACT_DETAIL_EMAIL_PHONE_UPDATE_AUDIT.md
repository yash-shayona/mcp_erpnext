# Task 58 — Customer-Scoped Contact Detail and Email/Phone Update Audit

## Status

**Audit / design task only — no production implementation**

Task 57 has implemented the first Customer-linked Contact vertical slice:

- bounded `search_contacts`;
- `prepare_customer_contact`;
- `confirm_customer_contact`;
- create new native Contact for an existing Customer;
- link an explicitly selected existing Contact to a Customer.

Task 57 intentionally did **not** implement Contact detail changes, email/phone child-row edits, existing-Contact primary promotion, unlink, delete, or merge.

This task audits the exact native and MCP boundaries required for the next Contact-update implementation.

---

## 1. Objective

Determine the safest, smallest, Frappe-native public capability for updating an **existing Contact in an explicit Customer context**, including:

1. supported Contact identity/detail fields;
2. primary and secondary email behavior;
3. primary phone/mobile behavior;
4. add/change/remove semantics for `Contact Email` and `Contact Phone` rows;
5. duplicate and normalization behavior;
6. permission requirements;
7. approval and stale-state requirements;
8. Customer stored projection refresh behavior;
9. CRM Contact-hook side effects;
10. impact on current email-recipient and Sales transaction behavior;
11. exact public tool/contract surface for the next implementation task.

The result must be an implementation-ready audit report.

Do **not** implement Contact update tools in Task 58.

---

## 2. Source-of-truth inputs

Inspect all of the following before reaching conclusions.

### Project sources

- current checked-out `mcp_erpnext` source;
- Task 56 audit:
  - `docs/inspect/CONTACT_MASTER_NATIVE_FLOW_AND_CAPABILITY_AUDIT.md`;
- Task 57 specification;
- Task 57 implementation report:
  - `docs/inspect/CUSTOMER_LINKED_CONTACT_V1_IMPLEMENTATION_REPORT.md`;
- actual Task 57 production code and tests;
- current shared approval, interaction, error, registry, profile, and REST patterns.

### Installed Frappe/ERPNext sources

Use the checked-out installed source as authority for runtime behavior.

At minimum inspect:

- Frappe `Contact` controller;
- Contact JSON metadata;
- `Contact Email`;
- `Contact Phone`;
- `Dynamic Link`;
- document save/validation/permission behavior;
- ERPNext `Customer` controller;
- Customer metadata;
- Customer primary-contact behavior;
- ERPNext party/default-contact logic;
- Sales transaction contact validation/defaulting;
- installed CRM Contact override/hooks;
- any installed app hook that affects Contact or Customer writes.

Do not replace checked-out behavior with assumptions from a different upstream branch.

---

## 3. Mandatory runtime re-check

Task 57 could not complete live runtime metadata verification because the development database was unavailable.

Task 58 must attempt the runtime check again on the configured development/test site.

Verify effective runtime metadata for:

- `Contact`;
- `Contact Email`;
- `Contact Phone`;
- `Dynamic Link`;
- `Customer`.

Also verify:

- installed apps;
- `override_doctype_class` affecting Contact;
- `doc_events` affecting Contact;
- relevant Customer hooks;
- effective permissions relevant to Contact/Customer.

### If the database is still unavailable

Do not mutate infrastructure or production data to force the check.

Record:

- exact command;
- exact failure;
- what could not be runtime-verified;
- which conclusions remain source-only.

The audit may continue using checked-out source, but the report must clearly distinguish:

```text
runtime verified
source verified
inferred / still unverified
```

---

## 4. Scope

Task 58 is strictly about **editing an already-existing Contact that is explicitly associated with a Customer context**.

Examples to analyze:

```text
Change Amit Shah's email for ABC Pvt Ltd to accounts@abc.com
```

```text
Add another email to Amit Shah for ABC Pvt Ltd
```

```text
Change Amit's mobile number
```

```text
Add office phone +91...
```

```text
Correct Amit's last name
```

The audit must determine which of these belong in the next V1 update capability and which should remain deferred.

---

## 5. Out of scope for Task 58 implementation

Do not implement or design a generic all-purpose Contact CRUD surface.

Unless the audit proves that one of these is inseparable from safe detail updating, keep these outside the next implementation:

- Contact delete;
- Contact unlink from Customer;
- Contact merge;
- arbitrary Dynamic Link mutation;
- Supplier Contact capability;
- Purchase profile support;
- Accounts profile Contact support;
- arbitrary custom fields;
- portal User creation/linking;
- Google Contacts synchronization;
- bulk Contact updates;
- broad global Contact enumeration;
- Customer delete behavior;
- historical Sales transaction rewrites.

Existing-Contact promotion to Customer primary must be analyzed, but do not assume it belongs in the same implementation task.

---

## 6. First inspect the actual Task 57 implementation

Before designing any update contract, inspect exactly what Task 57 implemented.

Document:

- public contracts;
- service functions;
- result models;
- current Contact projection;
- search behavior;
- Customer scoping behavior;
- duplicate helpers;
- permission helpers;
- approval action;
- stale-state/fingerprint representation;
- Contact reference representation;
- REST registration;
- Sales profile registration;
- tests.

Determine what can be safely reused instead of creating parallel Contact helpers.

Pay special attention to:

```text
search_contacts
prepare_customer_contact
confirm_customer_contact
```

Do not redesign these tools unless a concrete defect is discovered.

If a Task 57 defect is found, classify it separately as:

```text
Task 57 defect
```

Do not silently fold unrelated fixes into the future Contact-update implementation.

---

## 7. Confirm the authoritative Contact data model

Produce a concise authority map.

At minimum determine:

```text
Contact.first_name
Contact.middle_name
Contact.last_name
Contact.company_name
Contact.designation
Contact.department
Contact.email_ids[]
Contact.phone_nos[]
Contact.email_id
Contact.phone
Contact.mobile_no
Contact.links[]
Contact.is_primary_contact
```

For every relevant field, classify it as:

```text
caller-editable parent field
native-derived parent projection
child-table authority
relationship authority
system/native-only
unsafe / deferred
```

Do not infer writability from UI appearance alone.

Use effective metadata plus controller behavior.

---

## 8. Contact name/detail update audit

Determine whether the next public capability should support changes to:

- `first_name`;
- `middle_name`;
- `last_name`;
- `company_name`;
- `designation`;
- `department`.

For each field answer:

1. Is it natively writable?
2. Does changing it alter Contact `name`?
3. Does Contact autoname run again on save, or only insert?
4. Can changing these fields produce a misleading `name`/`full_name` divergence?
5. Does Frappe rename the document automatically?
6. If document rename is separate, should the MCP expose it?
7. Does changing person/company identity impact duplicate detection?
8. Does the field affect CRM, email, Sales defaults, or User linkage?
9. Should it be in V1 or deferred?

The report must explicitly distinguish:

```text
Contact document name
full_name projection/display
editable identity/detail fields
rename operation
```

Do not assume changing first/last name safely renames the Contact document.

---

## 9. Contact Email child-table audit

Trace the exact installed implementation of:

```text
Contact.email_ids
Contact Email.email_id
Contact Email.is_primary
Contact.email_id
```

Determine native behavior for each operation below.

### 9.1 Add first email

Example:

```text
Contact currently has no email
Add amit@example.com
```

Determine whether the first row automatically becomes primary.

### 9.2 Add secondary email

Example:

```text
Primary: amit@example.com
Add: billing@example.com
```

Determine native flags and parent projection behavior.

### 9.3 Change current primary email

Analyze alternatives:

**Replace row value**

```text
existing primary child row:
amit@example.com

becomes:
accounts@example.com
```

**Add new row + change primary flag**

```text
old row retained
new row becomes primary
```

Determine which semantic is safest and most natural for the MCP contract.

Do not assume “change email” means delete and recreate.

### 9.4 Set an existing secondary email as primary

Determine native flag-clearing/validation behavior.

### 9.5 Remove secondary email

Determine safe child-row identification and deletion behavior.

### 9.6 Remove primary email

Determine:

- whether another email automatically becomes primary;
- whether parent `Contact.email_id` becomes empty;
- whether the operation should require an explicit replacement/fallback;
- impact on Customer recipient/default behavior.

### 9.7 Duplicate email behavior

Determine:

- exact duplicate within the same Contact;
- case normalization;
- whitespace trimming;
- exact email present on another Contact;
- whether Frappe enforces global uniqueness;
- whether MCP should block, warn, or permit cross-Contact duplicates.

Do not invent a uniqueness rule that native Frappe does not have.

---

## 10. Contact Phone child-table audit

Trace:

```text
Contact.phone_nos
Contact Phone.phone
is_primary_phone
is_primary_mobile_no
Contact.phone
Contact.mobile_no
```

Audit each operation.

### 10.1 Add first mobile

Determine required primary flags and derived projection.

### 10.2 Add secondary mobile/phone

Determine whether phone type is inferred from flags or from separate semantics.

### 10.3 Change primary mobile

Compare:

```text
replace existing child row value
```

versus:

```text
add new row + move primary_mobile flag
```

### 10.4 Change primary phone

Audit separately from mobile.

### 10.5 Same row as primary phone + primary mobile

Task 56 found native validation treats the flags independently.

Reconfirm this against current installed source/runtime.

Decide whether the public API should allow this explicitly or hide it.

### 10.6 Remove phone/mobile

Determine:

- parent projection after removal;
- required fallback;
- safe child-row identity;
- stale-state implications.

### 10.7 Phone normalization and duplicates

Determine:

- native phone validation;
- normalization performed by Frappe;
- exact duplicate behavior;
- same number in formatting variants;
- duplicate on another Contact;
- whether existing Task 57 phone normalization helper can be reused.

---

## 11. Child-row identity strategy

This is a critical audit item.

The next implementation must be able to update/delete a precise child row without relying only on mutable values.

Determine whether public mutation preparation should internally bind:

```text
child row name
parent Contact name
current value
primary flags
parent modified
```

Decide whether child row `name` should:

- be exposed publicly;
- remain opaque/internal inside approval state;
- be represented by a stable semantic selector.

Preferred direction is to avoid exposing unnecessary internal child IDs to the LLM if the server can resolve them safely.

Audit the tradeoff and make an exact recommendation.

---

## 12. Customer-scoped authorization boundary

The update capability must not become a generic personal-data editing endpoint.

Determine the safest rule for identifying the Contact.

Candidate boundary:

```text
Customer reference
+
exact Contact reference
+
server verifies Contact.has_link("Customer", customer)
```

Audit whether this should be mandatory for every Contact update operation.

Questions to answer:

1. Must Contact be linked to the target Customer?
2. What if Contact was linked after prepare?
3. What if it becomes unlinked after prepare?
4. What if Contact has links to multiple Customers/Suppliers?
5. Does updating a shared Contact affect all linked parties?
6. What warning/result should be returned for a shared Contact?
7. Should update be permitted at all when `other_party_link_count > 0`?
8. If permitted, what must preview disclose without leaking party identities?

Do not expose unrelated party names.

---

## 13. Shared Contact side-effect analysis

A single Contact may be linked to multiple parties.

Editing:

```text
email
mobile
name
designation
```

changes the shared Contact for **all** linked parties.

This is materially different from simply linking it to one Customer.

The audit must recommend one of these policies:

### Option A — permit shared Contact update

Require explicit preview such as:

```text
This Contact is linked to the target Customer and 2 other parties.
The Contact record itself will be changed for all usages.
```

No party names exposed.

### Option B — reject shared Contact update in V1

Require a single-target Contact for update.

### Option C — permit only selected field classes

For example:

- non-identity detail maybe allowed;
- email/mobile maybe blocked;
- or vice versa.

Choose based on native semantics, user intent, data minimization, and risk.

Do not make the decision based merely on implementation convenience.

---

## 14. Customer projection refresh audit

This is mandatory.

Task 56 established that Customer fields such as:

```text
email_id
mobile_no
first_name
last_name
```

are stored fetch projections from `customer_primary_contact`.

A Contact-only save may leave Customer's stored projections stale.

Trace the exact installed behavior for:

```text
Customer.customer_primary_contact
Customer.email_id
Customer.mobile_no
Customer.first_name
Customer.last_name
```

After updating the Contact, determine:

1. Does Frappe automatically update linked Customer projections?
2. If not, when are they refreshed?
3. Is re-saving Customer enough?
4. Is assigning the same `customer_primary_contact` again required?
5. Does normal Customer validation fetch the linked values?
6. What permission is required?
7. If the updated Contact is **not** Customer primary, should Customer be touched at all?
8. If the updated Contact **is** Customer primary, should MCP refresh Customer in the same transaction?
9. What if Customer write permission is missing but Contact write is allowed?
10. Should Contact update succeed while reporting Customer projection not refreshed, or should the operation fail atomically?

Compare possible policies and recommend the safest consistent contract.

Do not use direct `frappe.db.set_value` as a shortcut unless installed native code proves it is the intended external seam.

---

## 15. Existing Contact primary promotion

Task 57 intentionally deferred:

```text
existing Contact -> make primary for Customer
```

Re-audit the installed behavior because this capability may interact with Contact update UX.

Determine:

- cross-party effect of `Contact.is_primary_contact`;
- relationship between that flag and `Customer.customer_primary_contact`;
- whether native Customer save validates Contact membership;
- how other primaries are demoted;
- locking/concurrency behavior;
- Customer projection refresh;
- required Contact + Customer permissions;
- whether promotion can safely be implemented as a separate future capability.

Do **not** assume it belongs in the Contact detail-update implementation.

Give a clear recommendation:

```text
include in next implementation
```

or

```text
keep as a separate later task
```

with reasons.

---

## 16. CRM and installed-hook side effects

Task 57 identified an installed CRM Contact validation hook.

Reconfirm the current source.

For each Contact update category, determine whether normal Contact save can update:

- CRM Deal email snapshot;
- CRM Deal mobile snapshot;
- other CRM fields;
- any installed app side effect.

Classify each side effect as:

```text
expected native side effect
unexpected risk
requires preview disclosure
requires additional permission
```

Do not bypass hooks to avoid side effects.

The MCP must preserve native behavior.

---

## 17. Email-recipient interoperability

Inspect the existing MCP email service and ERPNext recipient/default resolution.

Determine how Contact update affects:

- Customer native primary email;
- linked Contact fallback;
- transaction-specific copied contact/email;
- email sending for existing Quotation;
- existing Sales Order;
- existing Sales Invoice;
- future Sales documents.

Explicitly confirm whether changing Contact email should alter historical/copied transaction recipient fields.

Expected direction:

```text
historical transaction snapshots should not be rewritten
```

But verify against current code.

---

## 18. Sales transaction behavior

Trace native fields such as:

```text
contact_person
contact_display
contact_email
contact_mobile
```

for relevant Sales documents.

Determine:

- what is copied;
- what is live-linked;
- what future documents derive from Contact;
- what old documents retain.

The future Contact update service must not silently update historical business transactions unless native ERPNext explicitly does so.

---

## 19. Permission model audit

Build an exact permission matrix for the possible future operations.

At minimum evaluate:

| Operation | Candidate permission requirements |
|---|---|
| Read/select Contact in Customer context | Customer read + Contact read |
| Update Contact parent detail | Customer read + Contact write |
| Add/change email | Customer read + Contact write |
| Add/change phone | Customer read + Contact write |
| Remove email/phone | Customer read + Contact write |
| Refresh Customer projection if Contact is primary | Customer write + Contact write |
| Promote existing Contact to primary | Customer write + Contact write |

Verify against native document APIs.

Do not hard-code role names.

Do not use `ignore_permissions=True`.

---

## 20. Native API/helper comparison

Inspect all relevant native helpers and compare them against direct normal document mutation.

Examples may include:

- `Contact.add_email`;
- `Contact.add_phone`;
- primary setters;
- Frappe contact API methods;
- ERPNext party/contact helpers;
- Customer methods.

For every helper, record:

```text
what it does
permission behavior
autosave behavior
whether it uses ignore_permissions
whether it is safe as a public MCP seam
```

Task 56 found some Contact helper autosave paths may use `ignore_permissions=True`.

Reconfirm before recommending reuse.

Prefer normal:

```python
contact.save(ignore_permissions=False)
```

when it preserves native validation and public permission boundaries.

---

## 21. Proposed public operation model

Compare at least these designs.

### Option A — generic patch style

```text
prepare_contact_update(
    customer,
    contact,
    changes={...}
)
```

Advantages/disadvantages:

- flexible;
- but may expose arbitrary field/child mutation.

### Option B — typed operation list

Conceptually:

```text
operations = [
    set_detail(...),
    add_email(...),
    set_primary_email(...),
    remove_email(...),
    add_phone(...),
    ...
]
```

Audit complexity, ordering, stale state, and atomicity.

### Option C — one bounded intent per prepare

Conceptually:

```text
prepare_contact_update(
    customer,
    contact,
    action="replace_primary_email",
    ...
)
```

Audit tool-call explosion versus safety.

### Option D — separate detail and communication update capability

Example:

```text
prepare_contact_details_update
prepare_contact_communication_update
```

Compare LLM usability, contract clarity, and server safety.

The audit must select an exact model for the next implementation.

Do not simply choose the model with the fewest lines of code.

---

## 22. Tool-count optimization

The project should not create one MCP tool for every tiny Contact action unless necessary.

Determine whether the safest design can remain:

```text
search_contacts
prepare_contact_update
confirm_contact_update
```

with a typed bounded action inside the prepare contract.

Or whether separate mutation pairs are justified.

The report must give the final exact public tool names.

---

## 23. Natural-language ambiguity cases

Audit how the future capability should handle user requests such as:

```text
Change Amit's email to x@example.com
```

when:

- multiple Amit Contacts are linked to the Customer;
- the exact email already exists on another Contact;
- Amit has two email rows;
- Amit is shared across multiple parties;
- no Customer is specified;
- Contact is not linked to Customer;
- target current email is not specified;
- user says "replace email" but there are multiple emails;
- user says "change phone" but Contact has both phone and mobile.

Recommend when the tool should return:

```text
needs_selection
needs_input
duplicate_suspected
unsupported
ready
```

Do not let the service guess destructive row intent.

---

## 24. Duplicate policy for updates

New Contact creation and existing Contact updates have different duplicate concerns.

Audit:

### Email

- exact same email already on same Contact;
- target email on another Contact;
- case differences;
- whitespace;
- primary versus secondary duplicate.

### Phone

- same normalized number already on same Contact;
- formatting variants;
- target number on another Contact.

For each case decide:

```text
idempotent success
validation error
duplicate warning requiring continuation
hard block
allowed
```

Do not silently merge Contacts.

---

## 25. Destructive operation semantics

Removing a child email/phone is destructive.

Audit whether the next implementation should include removal at all.

If yes, define requirements such as:

- explicit action;
- exact child-row/current-value match;
- preview of whether row is primary;
- preview of resulting primary projection;
- stale child-row fingerprint;
- confirmation;
- no implicit fallback guessing.

If the audit determines deletion creates too much ambiguity for the next vertical slice, recommend:

```text
add/replace only in first implementation
remove in later task
```

Make this an explicit design decision.

---

## 26. Approval and stale-state model

Every Contact mutation must remain prepare/confirm gated.

Audit the minimum approval fingerprint.

Likely state to consider:

```text
site
user
profile
action
Customer name
Customer modified
Contact name
Contact modified
Customer-Contact link existence
other party link count
current primary Contact relationship
relevant child row names
current child row values
current primary flags
target values
duplicate candidates
```

Determine exactly which values must be bound for each operation category.

Confirm behavior if:

- Contact modified after prepare;
- Customer modified after prepare;
- target child row removed;
- target child row changed;
- primary flag changed;
- new duplicate appears;
- Customer link removed;
- Contact becomes shared after prepare.

Recommend exact stale-state codes or reuse existing project codes where appropriate.

---

## 27. Atomicity

Determine transaction boundaries for:

### Contact-only change

```text
Contact.save()
```

### Contact + Customer projection refresh

```text
Contact.save()
Customer.save()
```

### Future primary promotion

Potential multi-document flow.

The report must identify:

- outer commit owner;
- rollback expectations;
- installed hook side effects;
- whether any helper commits internally.

The future MCP service must preserve one logical approval -> one atomic business transaction wherever the operation promises combined state.

---

## 28. Idempotency

Define idempotent behavior for common update intents.

Examples:

```text
set primary email to value that is already primary
add email that already exists on same Contact
set mobile to current primary mobile
set last_name to current value
remove row that disappeared after prepare
```

Distinguish:

```text
safe idempotent success
stale state requiring re-prepare
ambiguous/destructive conflict
```

---

## 29. Data minimization

The future update capability must not expose full Contact records.

Determine minimal preview/result fields for each operation.

Possible bounded fields:

```text
Contact reference
full_name
target Customer reference
other_party_link_count
current selected email/phone value
proposed value
whether selected row is primary
resulting primary email/mobile/phone
Customer projection refresh effect
```

Do not return:

- unrelated party names;
- full Dynamic Links;
- all child rows unless the user must choose among them;
- communications;
- comments;
- addresses;
- User details;
- CRM Deal data;
- raw Document JSON.

If multiple child rows require selection, return only the minimum candidate rows needed for selection.

---

## 30. Error / interaction model

Recommend semantic states for the next implementation.

Evaluate/reuse existing codes for:

```text
CUSTOMER_NOT_FOUND
CONTACT_NOT_FOUND
CONTACT_NOT_LINKED_TO_CUSTOMER
CONTACT_SHARED_WITH_OTHER_PARTIES
CONTACT_DUPLICATE_SUSPECTED
CONTACT_EMAIL_NOT_FOUND
CONTACT_PHONE_NOT_FOUND
CONTACT_EMAIL_AMBIGUOUS
CONTACT_PHONE_AMBIGUOUS
CONTACT_INVALID_EMAIL
CONTACT_INVALID_PHONE
CONTACT_STALE_STATE
CONTACT_CHILD_STALE_STATE
CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED
PERMISSION_DENIED
CONFIRMATION_REQUIRED
```

Do not add a new code if an existing project code already represents the same semantic state.

---

## 31. Generic lifecycle interaction

Task 56 documented a generic lifecycle boundary issue involving `fieldtype == "Read Only"`.

Audit whether the future Contact-update capability needs any lifecycle change.

Preferred boundary:

```text
dedicated Customer-scoped Contact update service
```

not:

```text
enable arbitrary Contact child-table edits in generic lifecycle
```

If lifecycle hardening should happen separately, state:

- exact defect;
- whether it is security/correctness relevant;
- suggested separate task number/title;
- whether it blocks Contact update implementation.

Do not implement lifecycle hardening in Task 58.

---

## 32. Profile placement

Audit should assume the current business scope remains:

```text
Sales profile -> Customer Contact
```

Verify whether the next update tools should remain Sales-only.

Do not expose Supplier/Purchase Contact management merely because native Contact supports Supplier links.

---

## 33. REST / MCP parity requirements

Inspect Task 57 registration and recommend exact integration points for the future update implementation.

The report must identify:

- contracts module;
- service module;
- tool module;
- Sales profile registration;
- tool registry;
- contract registry;
- remote operation registration;
- REST typed handler;
- test files;
- generated catalog/doc updates.

No transport-specific business logic.

---

## 34. Required source/runtime experiments

Task 58 is an audit, but safe **read-only** runtime inspection is allowed.

Do not mutate business data on the development site.

If native behavior cannot be proven from source alone and a write would be required, either:

1. use an existing isolated test site/database if explicitly available; or
2. create an automated test fixture only if the repository's normal test framework already supports it without touching business data; or
3. mark the behavior as source-proven / unverified at runtime.

Do not create ad-hoc production records merely to answer the audit.

---

## 35. Required audit comparison tables

The final report must include at least these tables.

### Table A — field authority

Columns:

```text
Field
DocType
Native authority
Writable?
Derived?
V1 candidate?
Reason
```

### Table B — email operation matrix

Rows:

```text
add first
add secondary
replace primary value
promote secondary
remove secondary
remove primary
duplicate same Contact
duplicate another Contact
```

Columns:

```text
Native behavior
Permission
Stale state needed
Recommended public semantic
V1/defer
```

### Table C — phone operation matrix

Include:

```text
primary phone
primary mobile
secondary
same row both flags
replace
remove
duplicates
normalization
```

### Table D — shared Contact risk matrix

Compare:

```text
single-Customer Contact
multi-Customer Contact
Customer + Supplier Contact
```

for:

```text
name update
email update
mobile update
primary promotion
```

### Table E — Customer projection refresh

Compare:

```text
updated Contact is Customer primary
updated Contact is linked but not primary
Customer write permission present
Customer write permission absent
```

and exact recommended outcome.

### Table F — public API design options

Compare Options A-D from Section 21 and select one.

---

## 36. Required test design for the next implementation

Task 58 must produce an implementation-ready test matrix.

At minimum include tests for:

### Resolution/security

- exact Customer + Contact link verification;
- Contact not linked to Customer;
- Customer read denied;
- Contact read denied;
- Contact write denied;
- shared Contact;
- no unrelated party names leaked.

### Parent details

For every V1 candidate parent field:

- valid change;
- unchanged value;
- invalid value if applicable;
- stale Contact;
- native derived-field behavior.

### Email

- add first;
- add secondary;
- make secondary primary;
- change primary;
- remove secondary if V1;
- remove primary if V1;
- same value idempotency;
- duplicate same Contact;
- duplicate other Contact;
- invalid email;
- stale child row.

### Phone/mobile

Equivalent tests for phone/mobile primary flags and duplicate/normalization behavior.

### Customer projections

- updated primary Contact;
- updated non-primary Contact;
- Customer write available;
- Customer write unavailable;
- rollback if Contact succeeds but Customer refresh fails.

### Approval

- prepare non-mutating;
- valid confirm;
- wrong user;
- wrong site;
- wrong profile/action;
- replay;
- expiry;
- `confirm=false`;
- stale Contact;
- stale Customer;
- stale child row.

### Hooks/interoperability

- CRM Contact hook preserved;
- email-recipient logic unchanged except native Contact values;
- historical transaction snapshots unchanged;
- profile/REST/tool registry coverage.

---

## 37. Audit questions that must receive explicit answers

The final report must answer all of these directly.

1. What exact Contact fields should V1 allow updating?
2. Should V1 support detail/name updates?
3. Should V1 support add email?
4. Should V1 support replacing current primary email?
5. Should V1 support secondary email?
6. Should V1 support removing email?
7. Should V1 support add mobile?
8. Should V1 support replacing primary mobile?
9. Should V1 distinguish phone vs mobile?
10. Should V1 support removing phone/mobile?
11. How should child rows be identified safely?
12. Should child row names be public or approval-internal?
13. Can a Contact shared by multiple parties be edited?
14. What warning/state is required for shared Contacts?
15. What exact duplicate policy applies during update?
16. What happens to Customer projections after primary Contact email/mobile/name changes?
17. Must Customer be re-saved?
18. What if Customer write permission is missing?
19. Must Contact + Customer refresh be atomic?
20. Should existing-Contact primary promotion remain separate?
21. What exact tools should the next task implement?
22. What exact inputs/outputs should they use?
23. What exact permissions apply?
24. What exact stale fingerprints are required?
25. What remains deferred after that implementation?

---

## 38. Deliverable

Create:

```text
docs/inspect/CUSTOMER_SCOPED_CONTACT_DETAIL_EMAIL_PHONE_UPDATE_AUDIT.md
```

The report must contain:

1. executive summary;
2. repository state and versions;
3. Task 57 implementation baseline;
4. runtime metadata result;
5. installed Contact/Customer hooks/overrides;
6. field-authority map;
7. name/detail update analysis;
8. email child-table analysis;
9. phone child-table analysis;
10. child-row identity strategy;
11. Customer-scoped authorization rule;
12. shared Contact side-effect policy;
13. Customer projection refresh behavior;
14. existing Contact primary promotion decision;
15. CRM/native hook effects;
16. email-recipient interoperability;
17. Sales transaction interoperability;
18. permission matrix;
19. native helper/API comparison;
20. duplicate/update policy;
21. destructive-operation policy;
22. approval/fingerprint design;
23. atomicity/idempotency;
24. data-minimization model;
25. recommended public API;
26. exact contracts/inputs/outputs;
27. exact error/interaction states;
28. profile/REST integration points;
29. implementation test matrix;
30. limitations/unverified behavior;
31. exact next implementation task recommendation.

Every implementation-relevant conclusion must cite:

- current project file/function;
- installed Frappe/ERPNext/CRM source;
- runtime metadata where available.

---

## 39. Acceptance criteria

Task 58 is complete only when:

- [ ] no production Contact/Customer capability is implemented;
- [ ] current Task 57 code is inspected, not assumed;
- [ ] runtime metadata re-check is attempted;
- [ ] runtime/source/unverified evidence is clearly separated;
- [ ] Contact field authority is mapped;
- [ ] Contact name/detail behavior is proven;
- [ ] Contact Email semantics are proven;
- [ ] Contact Phone semantics are proven;
- [ ] child-row identity strategy is decided;
- [ ] Customer-context membership rule is decided;
- [ ] shared Contact update policy is decided;
- [ ] Customer projection refresh behavior is proven/recommended;
- [ ] missing Customer write permission behavior is decided;
- [ ] existing Contact primary promotion is either included or explicitly separated;
- [ ] CRM hook effects are documented;
- [ ] email and Sales transaction interoperability is documented;
- [ ] permission matrix is complete;
- [ ] duplicate rules are complete;
- [ ] destructive-operation scope is decided;
- [ ] approval/stale fingerprints are implementation-ready;
- [ ] exact future tool names are chosen;
- [ ] exact input/output contracts are proposed;
- [ ] exact error/interaction states are proposed;
- [ ] full implementation test matrix is provided;
- [ ] no unrelated lifecycle/product code is modified.

---

## 40. Expected result

At the end of Task 58, there should be no ambiguity about how a future request such as:

```text
Change Amit's email for ABC Pvt Ltd to accounts@abc.com
```

will execute.

The audit should reduce that request to an explicit flow similar to:

```text
resolve Customer
    ->
resolve exact Contact in Customer context
    ->
verify Customer-Contact relationship
    ->
inspect exact Contact email child rows
    ->
resolve intended row/action
    ->
check shared-Contact implications
    ->
check duplicate target value
    ->
prepare bounded semantic preview
    ->
bind Contact + child-row + Customer state
    ->
user approval
    ->
confirm revalidation
    ->
normal Contact.save(ignore_permissions=False)
    ->
native validation/hooks
    ->
optional native Customer projection refresh if required
    ->
single outer transaction commit
    ->
bounded result
```

But the final exact flow must come from the audit evidence, not from this illustrative sequence.

---

## 41. Limitations

Task 58 intentionally does not implement the update capability.

It also does not authorize:

- generic Contact CRUD;
- arbitrary Dynamic Link changes;
- Contact delete/unlink/merge;
- Supplier Contact management;
- broad Contact search;
- historical transaction rewrites;
- lifecycle hardening unless separately tasked.

The development database may still be unavailable. If so, the audit must retain that limitation rather than claiming runtime verification.

---

## 42. Exact next task

If Task 58 concludes the capability is safe and sufficiently specified, the next task should be:

```text
Task 59 — Customer-Scoped Contact Detail and Communication Update Implementation
```

Task 59 must implement only the V1 operation set explicitly approved by the Task 58 audit.

If Task 58 instead concludes that Customer projection refresh, shared-Contact behavior, or primary semantics require a prerequisite hardening task, the report must name that prerequisite precisely and explain why it blocks Task 59.

Do not start Task 59 implementation during Task 58.
