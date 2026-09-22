# Task 62 — Customer Contact Primary Promotion and Relationship Hardening Audit

## Status

**Audit / design task only — no production implementation**

Task 61 has completed the Customer-scoped Contact detail and communication update capability.

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

This task audits the remaining relationship/primary-state boundary before any implementation that can promote an existing linked Contact to Customer primary.

It also audits two known hardening items from Tasks 57–61:

1. Task 57 create/link transaction commit ownership;
2. exact semantics of "other party" relationship counting/fingerprinting.

Do not implement primary promotion or relationship hardening in this audit.

---

# 1. Objective

Determine the exact Frappe/ERPNext-native design for safely supporting:

```text
"Make Amit the primary Contact for ABC Pvt Ltd"
```

when Amit is already linked to ABC Pvt Ltd.

The audit must answer:

1. what authoritative fields participate in "primary Contact";
2. how `Contact.is_primary_contact` behaves across all Dynamic Links;
3. how `Customer.customer_primary_contact` behaves;
4. whether Customer and Contact primary states can diverge;
5. native lock/demotion/concurrency behavior;
6. exact permission requirements;
7. shared Contact safety rules;
8. Customer stored projection refresh;
9. stale-state and approval fingerprint requirements;
10. transaction ownership;
11. whether Task 57 internal commits must be hardened first;
12. exact "party link" semantics for shared-state detection;
13. whether current public link-count naming is accurate/safe;
14. exact public tool surface for primary promotion;
15. exact next implementation task.

---

# 2. Source-of-truth inputs

Inspect all current project and installed framework sources.

## Project sources

At minimum inspect:

```text
Task 56 Contact audit
Task 57 Customer-linked Contact implementation/report
Task 58 Contact update audit
Task 59 standalone Contact audit
Task 60 standalone Contact implementation/report
Task 61 Contact update implementation/report
```

Inspect current production code:

```text
mcp_erpnext/contracts/masters/contact.py
mcp_erpnext/services/masters/customer_contact.py
mcp_erpnext/services/masters/contact.py
mcp_erpnext/services/masters/contact_update.py
mcp_erpnext/tools/masters/contact.py
mcp_erpnext/tools/masters/customer_contact.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
```

Inspect approval/transaction infrastructure:

```text
ApprovalStore
claim_for_confirm_write
stable_fingerprint
InteractionDirective
ToolError
service commit/rollback conventions
```

## Installed Frappe/ERPNext/CRM sources

At minimum inspect:

```text
Frappe Contact controller
Contact.validate_primary_contact
Contact.has_link
get_contacts_linking_to
Dynamic Link
Document.save / insert transaction behavior

ERPNext Customer controller
Customer.create_primary_contact
customer_primary_contact field metadata
get_customer_primary
party.py default-contact logic

CRM Contact override/hooks
any installed Contact/Customer hooks
```

Installed checked-out source and effective runtime metadata are authoritative.

---

# 3. Mandatory runtime verification

Use read-only runtime inspection on the configured development/test site.

Verify effective runtime metadata for:

```text
Contact.is_primary_contact
Contact.links
Customer.customer_primary_contact
Customer.email_id
Customer.mobile_no
Customer.first_name
Customer.last_name
Dynamic Link
```

Verify:

```text
installed apps
Contact override_doctype_class
Contact doc_events
Customer doc_events
effective Contact permissions
effective Customer permissions
```

Do not mutate business records.

If runtime inspection cannot complete, distinguish:

```text
runtime verified
source verified
inferred/unverified
```

with exact failed commands.

---

# 4. Core business intent

Primary promotion means:

```text
Existing Customer: ABC Pvt Ltd
Existing Contact: Amit Shah
Contact already linked to ABC Pvt Ltd

User:
"Make Amit the primary Contact for ABC Pvt Ltd"
```

This is not:

```text
create Contact
link Contact
change primary email
change primary mobile
```

It is a relationship/default-state change.

Do not merge it into Task 61 communication update operations.

---

# 5. Authoritative primary-state model

Audit the relationship between:

```text
Contact.is_primary_contact
Customer.customer_primary_contact
```

For each field determine:

```text
storage owner
scope
native writer
native reader
validation behavior
side effects
whether it is per-Customer or global
```

The report must explicitly answer whether:

```text
Contact.is_primary_contact
```

is:

```text
per Contact
per Customer
per Dynamic Link
global across Contact links
```

and how that affects multi-party Contacts.

---

# 6. Native promotion call chains

Trace all relevant native paths.

At minimum analyze:

## Path A — saving Contact with `is_primary_contact=1`

Trace:

```text
Contact.save()
Contact.validate()
Contact.validate_primary_contact()
locks
other Contact demotion
Dynamic Link scope
```

## Path B — saving Customer with `customer_primary_contact=<contact>`

Trace:

```text
Customer.save()
Customer.on_update()
create_primary_contact()
Contact primary-state mutation
Customer fetch projection refresh
```

Determine which path, or combination, is correct for a public MCP promotion operation.

Do not assume the UI behavior is sufficient evidence.

---

# 7. Membership enforcement

Task 56 identified a potential mismatch:

```text
Customer.customer_primary_contact
```

may be set to an existing Contact without native Customer controller first verifying the Contact has a matching Customer Dynamic Link.

Reconfirm current source/runtime.

The MCP operation must never promote:

```text
Contact X
```

for:

```text
Customer ABC
```

unless:

```text
Contact.has_link("Customer", "ABC") == true
```

at prepare and confirm.

Determine exact error:

```text
CONTACT_NOT_LINKED_TO_CUSTOMER
```

or canonical equivalent.

---

# 8. Shared Contact problem

A Contact may link to:

```text
Customer ABC
Customer XYZ
Supplier DEF
other parties
```

Audit exact native side effects of setting:

```text
Contact.is_primary_contact = 1
```

for a shared Contact.

Questions:

1. Which parties are locked?
2. Which other Contacts are demoted?
3. Does promotion for ABC also affect XYZ/Supplier default-primary state?
4. Does Customer.customer_primary_contact for other Customers change automatically?
5. Can Contact flag state become inconsistent with Customer link fields?
6. Is a shared Contact safe to promote at all in V1?

The report must choose a policy:

```text
reject shared Contact promotion
```

or

```text
permit under bounded explicit rules
```

with source evidence.

Preferred safety direction should be evaluated, not assumed.

---

# 9. Single-Customer Contact promotion

Analyze the simplest safe case:

```text
Contact links = exactly one Customer
Contact.is_primary_contact = 0
Customer.customer_primary_contact = another linked Contact or empty
```

Determine the exact required native mutation sequence.

Possible designs:

## Option A

```text
set Customer.customer_primary_contact
Customer.save()
```

and rely on Customer controller to update Contact primary state.

## Option B

```text
set Contact.is_primary_contact
Contact.save()
then set Customer.customer_primary_contact
Customer.save()
```

## Option C

```text
Customer save only + explicit post-validation
```

## Option D

another source-proven sequence.

Compare atomicity, validation, demotion, fetch projection refresh, concurrency, and failure behavior.

---

# 10. Existing old primary Contact

If ABC currently has:

```text
Primary Contact = Ravi
```

and user promotes:

```text
Amit
```

audit exact native final state:

```text
Amit.is_primary_contact
Ravi.is_primary_contact
Customer.customer_primary_contact
Customer.email_id
Customer.mobile_no
Customer.first_name
Customer.last_name
```

Determine whether native Contact validation demotes Ravi.

Determine whether Customer save alone ensures that demotion.

Determine whether old Customer references/projections update correctly.

---

# 11. No existing Customer primary

If:

```text
Customer.customer_primary_contact = empty
```

but multiple linked Contacts exist, analyze promotion of one selected Contact.

Confirm:

- exact membership;
- Contact primary flag;
- Customer Link field;
- Customer fetch projections;
- other Contact primary flags.

---

# 12. Inconsistent pre-existing states

Audit how the future public operation should behave if existing data is inconsistent.

Examples:

```text
Customer.customer_primary_contact = Amit
but Amit.is_primary_contact = 0
```

```text
Amit.is_primary_contact = 1
but Customer.customer_primary_contact = Ravi
```

```text
two Contacts linked to same Customer both have is_primary_contact = 1
```

```text
Customer.customer_primary_contact points to unlinked Contact
```

For each decide:

```text
auto-heal during prepare/confirm
block and require repair
promote selected Contact and normalize native state
separate hardening task
```

Do not silently hide corruption.

---

# 13. Native locking/concurrency

Trace `Contact.validate_primary_contact()` locking behavior in exact installed source.

Document:

```text
which linked documents are locked
lock ordering
when query for existing primary Contacts happens
how demotion writes occur
what races are prevented
what races remain
```

Audit concurrent cases:

```text
User A promotes Amit
User B promotes Ravi
same Customer
```

and:

```text
same Contact shared across multiple parties
```

Determine what MCP stale fingerprint must supplement native locks.

---

# 14. Permission matrix

Build exact native permission requirements.

At minimum evaluate:

| Operation | Candidate permissions |
|---|---|
| Prepare promotion | Customer read + Contact read |
| Promote selected Contact | Customer write + Contact write |
| Demote old primary Contact | Does native path require explicit write permission on old Contact? |
| Refresh Customer projections | Customer write |
| Shared Contact inspection | Contact read + bounded relationship inspection |

Determine whether Contact controller internal demotion uses:

```text
frappe.db.set_value
```

and whether that bypasses normal Contact permission for demoted Contacts.

Explain what public MCP preflight should require despite native internals.

Do not hard-code roles.

---

# 15. Customer projection refresh

Promotion changes:

```text
Customer.customer_primary_contact
```

and should refresh stored projections:

```text
email_id
mobile_no
first_name
last_name
```

Audit exact source/runtime behavior.

Determine whether normal:

```text
Customer.save(ignore_permissions=False)
```

is sufficient.

Do not directly assign read-only projection fields.

---

# 16. Email recipient interoperability

Inspect current email resolution.

Determine how primary Contact promotion changes future fallback:

```text
Customer.email_id
linked Contact preference
transaction fallback
```

Verify:

- historical transaction `contact_email` snapshots remain unchanged;
- future Customer-based fallback may use promoted Contact;
- no unrelated Contact becomes recipient.

No email business logic should be reimplemented in promotion service.

---

# 17. Sales transaction defaults

Trace future document creation behavior for:

```text
Quotation
Sales Order
Sales Invoice
```

after promotion.

Determine which default Contact is selected through native party logic.

Verify existing documents are not rewritten.

---

# 18. CRM side effects

Determine whether promotion save paths trigger:

```text
CRM Contact validate hook
CRM Deal snapshots
other installed hooks
```

If normal Contact save is part of promotion, preserve hooks.

If Customer-only save internally changes Contact via `frappe.set_value`, determine whether Contact hooks run or are bypassed.

This may materially affect the choice of mutation sequence.

The report must explicitly compare hook behavior between candidate promotion sequences.

---

# 19. Task 57 transaction boundary audit

Current Task 57 report/source identified branch-local commits in:

```text
confirm_customer_contact()
```

for create/link operations.

Task 62 must inspect current code after Tasks 60/61 and answer:

1. Are those commits still present?
2. Do they violate current transaction design conventions?
3. Are they safe because Task 57 operations are single-document writes?
4. Will primary promotion need a multi-document transaction?
5. Should Task 57 transaction ownership be hardened before implementing promotion?
6. Can hardening be included in the primary-promotion implementation without unrelated risk?
7. Should it be a separate prerequisite task?

Classify:

```text
blocking prerequisite
recommended non-blocking hardening
unrelated
```

with exact evidence.

---

# 20. Relationship count semantics

Current Contact projection exposes:

```text
other_party_link_count
```

Task 58/59 noted existing helper may count every non-target Dynamic Link rather than only "party" links.

Audit exact current implementation.

Determine:

```text
what is counted
what is excluded
whether the name is accurate
whether it is security-sensitive
whether it can drive shared-Contact blocking
```

Do not use an inaccurately named public count for authorization decisions.

---

# 21. Define "party relationship"

The report must define exactly which Dynamic Link doctypes should count as relationship-sharing for Contact primary/update safety.

Possible approaches:

## Option A

Any additional Dynamic Link row.

Conservative.

## Option B

Only party-like doctypes:

```text
Customer
Supplier
Lead
Prospect
...
```

## Option C

Use ERPNext/Frappe party-type helper/metadata if available.

## Option D

Different source-proven rule.

Compare maintainability and future generic use.

Do not hard-code an incomplete arbitrary list if framework-native semantics exist.

---

# 22. Relationship fingerprint

For primary promotion approval, determine exact internal relationship fingerprint.

Candidate state:

```text
sorted (link_doctype, link_name) pairs
target Customer membership
count
Contact.modified
Customer.modified
current customer_primary_contact
current Contact.is_primary_contact
old primary Contact reference/state
```

Decide what must be bound to prevent a relationship race.

Public output must not disclose unrelated relationship identities.

---

# 23. Primary-state fingerprint

Bind enough state to detect:

```text
selected Contact primary flag changed
Customer current primary changed
old primary Contact changed/deleted
relationship membership changed
new linked party added
old linked party removed
```

Determine exact stale codes.

---

# 24. Approval model

Promotion must be prepare/confirm gated.

Possible public tools:

```text
prepare_customer_contact_primary
confirm_customer_contact_primary
```

or:

```text
prepare_customer_primary_contact
confirm_customer_primary_contact
```

or another naming consistent with current vocabulary.

Audit naming to avoid confusion with:

```text
primary email
primary phone
primary mobile
```

The tool name must clearly represent:

```text
Customer's primary Contact relationship
```

not communication-primary flags.

---

# 25. Tool surface options

Compare:

## Option A — extend `prepare_customer_contact`

Add:

```text
mode="make_primary"
```

Pros/cons:

- reuse existing pair;
- but create/link/promotion have different permission and transaction semantics.

## Option B — dedicated primary pair

Example:

```text
prepare_customer_primary_contact
confirm_customer_primary_contact
```

Pros/cons:

- explicit semantics;
- separate approval action;
- clearer multi-document transaction.

## Option C — add primary action to Task 61 update tool

Likely conflates relationship-primary with communication-primary.

Evaluate and likely reject if unsafe.

## Option D — another design

Select one exact design.

---

# 26. Approval action

Recommend exact shared ApprovalStore action.

Candidate:

```text
customer_primary_contact
```

or:

```text
customer_contact_primary
```

It must be distinct from:

```text
customer_contact
customer_contact_update
contact_create
```

---

# 27. Prepare behavior

Prepare must be non-mutating.

Conceptual:

```text
load Customer
load selected Contact
verify permissions
verify exact Customer link
inspect relationship-sharing state
inspect current Customer primary
inspect selected Contact primary flag
inspect old primary Contact state
derive expected post-state
build bounded preview
store approval fingerprint
```

Do not save Contact/Customer.

Do not run write-capable hooks.

---

# 28. Promotion preview

Preview should include only:

```text
Customer reference
selected Contact reference
current primary Contact reference or null
selected Contact already primary? bool
selected Contact currently Customer primary? bool
relationship-safe/shared? bounded bool/count
Customer projections that will switch semantically
native side-effect warning
```

Do not expose unrelated party names.

Do not dump Contact links.

---

# 29. Confirm behavior

Conceptual confirm:

```text
claim approval
reload Customer
reload selected Contact
reload old primary if needed
recheck permissions
recheck membership
recheck relationship sharing
recheck modified/fingerprint
apply exact native promotion sequence
refresh Customer projections
one final commit
rollback on any failure
```

The exact mutation sequence must come from audit conclusions.

---

# 30. Atomicity

Primary promotion is likely multi-document.

The report must define whether the transaction includes:

```text
selected Contact
old primary Contact
Customer
CRM hook side effects
```

and how native demotion writes fit into the same DB transaction.

No intermediate commit.

---

# 31. Idempotency

Define behavior for:

```text
selected Contact is already Customer.customer_primary_contact
selected Contact.is_primary_contact already true
both already true
Customer field already selected but Contact flag inconsistent
```

Distinguish:

```text
safe idempotent success
repairable inconsistent state
stale/corrupt state
```

Do not guess through unlinked/inconsistent relationships.

---

# 32. Unpromotion / clear-primary

Audit whether the same future capability should support:

```text
clear Customer primary Contact
```

Likely separate/destructive semantic.

Decide:

```text
include
defer
```

Do not assume symmetry with promotion.

---

# 33. Multi-party Contact promotion

If audit concludes shared Contact promotion is unsafe in V1, freeze:

```text
CONTACT_SHARED_WITH_OTHER_PARTIES
```

If it can be safe under a narrower model, specify exact requirements.

Do not expose other party names.

---

# 34. Old primary Contact shared state

Even if selected Contact is single-Customer, the current old primary Contact may be shared.

Analyze whether native demotion of old primary has cross-party side effects.

This is critical.

Example:

```text
Ravi is primary for ABC
Ravi also linked to Supplier DEF
User promotes Amit for ABC
```

What does native demotion do to Ravi's Supplier relationship?

The report must prove this from source.

This may affect whether promotion is safe even when the selected Contact itself is single-party.

---

# 35. Data-minimization model

Recommend bounded result fields.

Possible:

```text
Customer reference
previous primary Contact reference
new primary Contact reference
Customer projections refreshed
selected Contact primary flag
idempotent
```

Do not return:

```text
all Contacts
all links
unrelated party names
raw Contact JSON
CRM Deal data
child rows
```

---

# 36. Error/interaction states

Audit/reuse semantic states:

```text
CUSTOMER_NOT_FOUND
CONTACT_NOT_FOUND
CONTACT_NOT_LINKED_TO_CUSTOMER
CONTACT_SHARED_WITH_OTHER_PARTIES
PRIMARY_CONTACT_STATE_INCONSISTENT
PRIMARY_CONTACT_PROMOTION_UNSAFE
CUSTOMER_PRIMARY_CONTACT_STALE
CONTACT_STALE_STATE
PERMISSION_DENIED
CONFIRMATION_REQUIRED
CONFIRMATION_UNAVAILABLE
STALE_CONFIRMATION
```

Do not add new codes where existing canonical equivalents exist.

---

# 37. Native state-repair question

Determine whether public promotion operation should repair native inconsistencies incidentally.

Example:

```text
Customer already points to Amit
Amit.is_primary_contact = 0
```

Could promotion confirm normalize this?

Or should a separate repair/hardening operation handle it?

Choose explicitly.

---

# 38. Relationship hardening scope

Task 62 must make a concrete recommendation for current Task 57/61 relationship helper semantics.

Potential hardening:

```text
rename other_party_link_count
introduce internal relationship_count
introduce internal party_relationship_count
introduce sorted link fingerprint helper
```

Determine which changes are required before primary implementation.

Do not implement them in audit.

---

# 39. Genericity / future Supplier support

The MCP project should remain extensible.

Audit whether internal relationship helper design should be generic enough for future:

```text
Supplier Contact
Purchase profile
```

without exposing those capabilities now.

Do not implement Supplier support.

Avoid hard-coding logic that prevents future extension unless native framework requires it.

---

# 40. Profile placement

Primary promotion remains:

```text
Sales profile
Customer scope
```

Audit should confirm no Accounts/Purchase exposure.

---

# 41. REST/MCP parity

Recommend integration points for future implementation:

```text
contracts/masters/contact.py
service module
tool module
Sales profile
tool registry
contract registry
remote operations
REST typed dispatch
docs/TOOLS.md
focused tests
```

No transport-specific business logic.

---

# 42. Required comparison tables

Final report must include:

## Table A — primary field authority

```text
Field
DocType
Scope
Native writer
Native side effects
Public role
```

## Table B — promotion sequence options

Compare Options A-D from Section 9.

## Table C — shared Contact matrix

Rows:

```text
selected Contact single-party
selected Contact multi-Customer
selected Contact Customer+Supplier
old primary single-party
old primary multi-party
```

Columns:

```text
native effect
risk
V1 decision
```

## Table D — permission matrix

Include selected Contact, old primary, Customer.

## Table E — inconsistent state matrix

Include all states from Section 12.

## Table F — relationship-count semantics

Compare current helper and recommended helper.

## Table G — public API options

Compare Section 25.

## Table H — transaction hardening dependency

Classify Task 57 commit ownership.

---

# 43. Required test design for next implementation

The audit must produce an implementation-ready test matrix.

At minimum:

## Membership/security

- Contact linked to Customer;
- Contact not linked;
- selected Contact shared;
- old primary shared;
- unrelated link added after prepare;
- no unrelated names leaked.

## Permissions

- Customer read/write;
- selected Contact read/write;
- old primary permission considerations;
- missing permission blocks before mutation.

## Primary state

- no current primary;
- promote selected;
- replace old primary;
- selected already primary;
- selected already Customer field;
- inconsistent states.

## Customer projections

- email/mobile/name refresh;
- no direct projection writes;
- rollback on Customer failure.

## Concurrency/stale

- Customer modified;
- selected Contact modified;
- old primary modified;
- relationship changes;
- concurrent promotion;
- token replay.

## Hooks

- selected Contact hooks;
- old primary demotion hook behavior if applicable;
- CRM behavior;
- no raw data leaks.

## Transactions

- no intermediate commit;
- selected + old primary + Customer atomic rollback;
- Task 57 hardening regression if included later.

## Transport/profile

- Sales only;
- registry parity;
- REST/MCP parity.

---

# 44. Exact audit questions

Final report must explicitly answer:

1. Is `Contact.is_primary_contact` per Customer or global across links?
2. What does Customer save do when `customer_primary_contact` changes?
3. Does Customer save validate Contact membership?
4. What exact sequence should MCP use for promotion?
5. Is selected shared Contact promotion safe?
6. Is old-primary shared Contact demotion safe?
7. What happens to other linked parties during demotion?
8. What permissions are required on selected Contact?
9. What permissions are required on old primary Contact?
10. What permissions are required on Customer?
11. Which native locks are acquired?
12. Is concurrent promotion serialized?
13. Which stale fingerprints are required?
14. How are Customer projections refreshed?
15. What CRM/hook side effects occur?
16. Are historical transaction snapshots unchanged?
17. Must Task 57 commits be hardened first?
18. What exactly should `other_party_link_count` mean?
19. What exact internal relationship fingerprint is required?
20. Should shared Contact promotion be rejected in V1?
21. Should clear-primary be included?
22. Should inconsistent state auto-repair be included?
23. What exact public tools should implement promotion?
24. What exact approval action should be used?
25. What exact next implementation task should be created?

---

# 45. Deliverable

Create:

```text
docs/inspect/CUSTOMER_CONTACT_PRIMARY_PROMOTION_RELATIONSHIP_HARDENING_AUDIT.md
```

Report sections:

1. executive summary;
2. repository/runtime state;
3. current Contact capability baseline;
4. runtime metadata;
5. primary-state authority map;
6. Contact primary controller behavior;
7. Customer primary controller behavior;
8. membership validation;
9. selected Contact shared-state analysis;
10. old primary shared-state analysis;
11. native locks/concurrency;
12. promotion sequence comparison;
13. inconsistent-state matrix;
14. Customer projection refresh;
15. permissions;
16. CRM/native hooks;
17. email/Sales interoperability;
18. Task 57 commit ownership audit;
19. current link-count semantics;
20. recommended relationship helper/fingerprint;
21. approval/stale design;
22. atomicity/idempotency;
23. public API option comparison;
24. exact proposed contracts;
25. error/interaction states;
26. data-minimization result;
27. profile/transport integration;
28. implementation test matrix;
29. prerequisites/hardening tasks;
30. limitations;
31. exact next implementation task.

Every implementation-relevant conclusion must cite current project source, installed framework/app source, or runtime metadata.

---

# 46. Acceptance criteria

Task 62 is complete only when:

- [ ] no production behavior is changed;
- [ ] current Task 57/60/61 code is inspected;
- [ ] runtime metadata is rechecked;
- [ ] `Contact.is_primary_contact` scope is proven;
- [ ] Customer primary field behavior is proven;
- [ ] membership validation gap is proven/resolved in design;
- [ ] selected Contact shared-state policy is frozen;
- [ ] old-primary shared-state risk is frozen;
- [ ] native demotion behavior is proven;
- [ ] native lock/concurrency behavior is documented;
- [ ] exact promotion sequence is selected;
- [ ] exact permissions are selected;
- [ ] Customer projection refresh is proven;
- [ ] CRM/hook side effects are documented;
- [ ] Task 57 commit ownership is classified;
- [ ] relationship-count semantics are corrected in design;
- [ ] internal relationship fingerprint is specified;
- [ ] approval/stale state is implementation-ready;
- [ ] atomicity/idempotency is specified;
- [ ] exact public tools are chosen;
- [ ] exact contracts are proposed;
- [ ] full test matrix is present;
- [ ] exact next implementation task is named.

---

# 47. Expected result

At the end of Task 62, this request must have one source-proven flow:

```text
"Make Amit the primary Contact for ABC Pvt Ltd"
```

The audit should determine an exact sequence similar to:

```text
resolve Customer
resolve exact linked Contact
verify membership
verify relationship-sharing safety
inspect current primary Contact
inspect selected/old primary native state
permission checks
prepare preview
approval
confirm
recheck all relationship/primary fingerprints
execute chosen native promotion sequence
refresh Customer projections
one transaction commit
bounded result
```

The exact mutation sequence must come from the audit, not this illustration.

---

# 48. Limitations

Task 62 does not implement:

- primary promotion;
- clear-primary;
- Contact create/link/update changes;
- Supplier Contact management;
- Purchase profile Contact tools;
- destructive Contact operations;
- generic Contact CRUD.

---

# 49. Exact next task

If audit concludes primary promotion is safe after bounded hardening, create:

```text
Task 63 — Customer Primary Contact Promotion and Relationship Hardening Implementation
```

Task 63 should implement only:

- required relationship helper/fingerprint hardening;
- any required Task 57 transaction-boundary prerequisite approved by Task 62;
- Customer primary Contact promotion;
- exact bounded approval/permission/stale model;
- Sales-only registration.

If Task 62 finds transaction hardening must be a separate prerequisite, it must instead recommend:

```text
Task 63 — Contact Relationship Transaction and Link-State Hardening
```

followed by promotion implementation as Task 64.

Do not start implementation during Task 62.
