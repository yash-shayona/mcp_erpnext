# Task 59 — Standalone Contact Master Capability Audit

## Status

**Audit / design task only — no production implementation**

This task is inserted after Task 58 because the product scope now explicitly includes a valid Frappe use case that is not Customer-scoped:

```text
Create a standalone Contact now
and optionally link that Contact to a Customer later.
```

The existing Task 57 capability remains valid and unchanged:

```text
search_contacts
prepare_customer_contact
confirm_customer_contact
```

Task 57 solves:

```text
Customer -> create a Contact already linked to that Customer
Customer -> link an existing Contact to that Customer
```

Task 59 audits the separate master-data intent:

```text
create a native Contact without requiring any Customer/Supplier link
```

No production Contact capability is to be implemented in this task.

---

## 1. Objective

Determine the exact safe MCP boundary for **standalone native Frappe Contact creation**.

The audit must decide:

1. whether standalone Contact creation should be publicly exposed;
2. exact allowed input fields;
3. minimum identity requirements;
4. email/phone child-row semantics;
5. duplicate/reuse behavior;
6. permissions;
7. approval/confirmation behavior;
8. profile placement;
9. interaction with existing Task 57 Customer-linked Contact tools;
10. whether existing `search_contacts` is sufficient for finding standalone Contacts;
11. whether standalone Contact creation needs a separate `prepare_contact` / `confirm_contact` pair;
12. what later linking flow should use after standalone creation;
13. exact data minimization and result projection;
14. exact implementation task and tests.

The goal is to support a clean flow such as:

```text
User:
"Create contact Amit Shah with amit@example.com"

        ↓

Standalone native Contact

        ↓ later

"Link Amit Shah to ABC Pvt Ltd"

        ↓

existing Task 57 customer_contact(mode=link)
```

Do not implement the capability during this audit.

---

# 2. Why this task exists

The current MCP architecture must not incorrectly model `Contact` as only a child or property of `Customer`.

Frappe Contact is an independent DocType/master.

A Contact may validly exist as:

```text
Standalone Contact
```

or:

```text
Contact linked to one Customer
```

or:

```text
Contact linked to multiple parties
```

The MCP should preserve that native model.

However, the public MCP surface must still remain bounded and safe.

This task determines how to expose standalone creation without turning Contact into unrestricted CRUD.

---

# 3. Source-of-truth inputs

Inspect all relevant sources before reaching conclusions.

## 3.1 Project sources

At minimum inspect:

```text
Task 56 audit
Task 57 implementation task
Task 57 implementation report
Task 58 audit
current mcp_erpnext source
```

Specifically inspect current:

```text
mcp_erpnext/contracts/masters/contact.py
mcp_erpnext/services/masters/customer_contact.py
mcp_erpnext/tools/masters/customer_contact.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
mcp_erpnext/tests/test_customer_contact.py
docs/TOOLS.md
```

Also inspect:

- shared approval store;
- `claim_for_confirm_write`;
- shared interaction directives;
- reference/result patterns;
- tool registration;
- error envelope;
- stale/fingerprint helpers;
- any generic resolver relevant to Contact.

## 3.2 Installed Frappe/ERPNext/CRM sources

At minimum inspect:

```text
Frappe Contact controller
Contact metadata
Contact Email metadata
Contact Phone metadata
Dynamic Link metadata
Frappe document insert/save permission behavior
ERPNext Customer Contact helpers
ERPNext party/default-contact helpers
CRM Contact override
CRM Contact validate hook
```

Installed checked-out source is authoritative for runtime behavior.

Do not substitute behavior from another upstream branch.

---

# 4. Mandatory runtime verification

Use read-only runtime inspection on the configured development/test site.

Reconfirm effective metadata for:

```text
Contact
Contact Email
Contact Phone
Dynamic Link
```

Reconfirm:

```text
installed apps
Contact override_doctype_class
Contact doc_events
effective Contact permissions
```

Also verify any Property Setters / Custom Fields that materially affect the candidate standalone Contact inputs.

Do not create or modify business records during the audit.

If runtime inspection is unavailable, record:

```text
exact command
exact failure
source-verified conclusions
runtime-unverified conclusions
```

---

# 5. Scope

Task 59 audits standalone Contact creation only.

Example supported business intent to evaluate:

```text
Create contact Amit Shah.
```

```text
Create contact Amit Shah with email amit@example.com.
```

```text
Create contact Amit Shah with mobile +91...
```

```text
Create contact "Accounts Desk" for XYZ with no Customer link yet.
```

The audit must determine which input shapes are valid and useful.

---

# 6. Explicitly out of scope

Do not implement or design unrestricted Contact CRUD.

The following remain outside this audit unless necessary for creation semantics:

- Contact detail update;
- Contact email/phone update after creation;
- Contact delete;
- Contact merge;
- Contact rename;
- Contact unlink;
- arbitrary Dynamic Link editing;
- Customer linking implementation changes;
- Supplier linking implementation;
- Purchase profile Contact management;
- Accounts profile Contact management;
- portal User management;
- Google Contacts behavior;
- broad Contact search;
- bulk Contact creation;
- importing Contact lists;
- existing Contact primary promotion;
- historical Sales transaction mutation.

Task 58 already audits Customer-scoped Contact updating.

Do not merge Task 58 implementation scope into this task.

---

# 7. Confirm native standalone Contact validity

Explicitly prove from installed source/runtime that Contact can be created without:

```text
Customer Dynamic Link
Supplier Dynamic Link
any Dynamic Link
email
phone
```

Document:

- mandatory native fields;
- autoname behavior;
- name generation with no Dynamic Link;
- full-name derivation;
- company-name fallback behavior;
- collision/suffix behavior;
- whether empty/nameless Contact is technically possible;
- whether public MCP rules should be stricter than framework minimums.

The public capability may impose stricter business validation than Frappe.

---

# 8. Standalone Contact identity policy

Determine the minimum public identity requirements.

Compare possible policies.

## Option A

Require:

```text
first_name
```

## Option B

Require one of:

```text
first_name
last_name
company_name
```

## Option C

Require one of:

```text
first_name
last_name
company_name
email
mobile
```

## Option D

Use a different source-verified bounded rule.

Evaluate:

- native naming;
- usability;
- duplicate risk;
- nameless records;
- business Contacts such as "Accounts Desk";
- person vs company-style Contacts;
- later Customer linking;
- searchability.

Recommend one exact rule.

---

# 9. Candidate standalone input fields

Audit whether V1 creation should expose:

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

For each field determine:

```text
native field/child authority
validation
required?
optional?
safe for standalone V1?
reason
```

Do not expose native-derived fields as caller input:

```text
full_name
email_id
mobile_no
phone
```

unless `phone` is intentionally represented through the Contact Phone child table.

Explicitly distinguish:

```text
public semantic input "phone"
```

from:

```text
Contact.phone read-only parent projection
```

---

# 10. Email creation semantics

Audit the safest standalone creation behavior for:

```text
email
```

Confirm:

- server constructs `Contact Email` child row;
- first/only email native primary behavior;
- email validation;
- whitespace behavior;
- duplicate email on same Contact is irrelevant during one-row creation;
- duplicate email across existing Contacts;
- case-insensitive comparison for duplicate suspicion;
- whether email-only Contact creation should be allowed.

Decide whether V1 supports:

```text
one email only
```

or:

```text
multiple email rows at create time
```

Preferred direction should be minimal/bounded unless evidence supports a better design.

Do not expose raw `email_ids` child tables to the caller.

---

# 11. Phone/mobile creation semantics

Audit safe creation behavior for:

```text
mobile
phone
```

Confirm native semantics:

```text
Contact Phone.phone
is_primary_phone
is_primary_mobile_no
```

Determine whether V1 should support:

### Option A

Only one `mobile` input.

### Option B

One `mobile` and one `phone`.

### Option C

Multiple communication rows.

For each supported semantic input, define exactly which child flags the server constructs.

Do not rely on the caller to submit raw Contact Phone rows.

Do not expose an ambiguous `"both"` primary type unless explicitly justified.

---

# 12. No-link creation behavior

For standalone creation, the Contact must be inserted with:

```text
links = []
```

or no `links` field.

Audit which native payload shape is preferred.

Confirm:

- Contact autoname with no links;
- Dynamic Link validation is not required;
- no Customer/Supplier permission is required;
- no Customer projection can be affected;
- no primary-party semantics should be triggered.

Determine whether standalone creation must force:

```text
is_primary_contact = 0
```

or simply omit it and rely on native default.

Public caller must not provide `is_primary_contact`.

---

# 13. Duplicate/reuse strategy

This is critical because standalone creation has no Customer scope.

Task 57 deliberately restricts broad global Contact enumeration.

Audit how standalone creation should avoid duplicates without leaking Contact data.

Evaluate duplicate signals:

```text
exact Contact name
exact primary/child email
normalized phone/mobile
full_name
company_name
```

Determine which signals are safe enough to block or warn.

Recommended categories to evaluate:

## Exact email match

If user has permission to see the Contact:

```text
CONTACT_DUPLICATE_SUSPECTED
```

with minimal candidate output.

If user cannot see the Contact:

- do not leak that hidden Contact exists unless native permissions safely allow a generic duplicate signal;
- determine whether creation should proceed or return a non-enumerating conflict.

## Exact normalized phone match

Same analysis.

## Same full name only

Likely insufficient for automatic reuse.

Confirm exact behavior.

## Exact Contact document name

May be naming collision rather than identity.

Do not automatically interpret it as the same person.

The audit must define:

```text
idempotent
duplicate_suspected
allowed
needs_selection
hard block
```

for each case.

---

# 14. Global search/data enumeration implications

Current Task 57 `search_contacts` intentionally allows:

```text
global exact Contact name
global exact email
global exact phone
```

and does not allow broad fuzzy global personal-name search.

Audit whether standalone Contact creation can reuse that exact search surface unchanged.

Questions:

1. Is exact global search enough to select a suspected duplicate?
2. Does standalone creation require any new search mode?
3. Should global fuzzy Contact search remain prohibited?
4. Can candidate results reuse Task 57 bounded Contact projection?
5. Is `other_party_link_count` meaningful for standalone duplicate selection?
6. Does Task 57's current link-count helper need hardening before reuse?

Preferred outcome is reuse without broadening personal-data enumeration.

---

# 15. Relationship with Task 57 Customer-linked flow

The architecture must keep business intent clear.

Audit and freeze routing semantics.

## Intent A

```text
Create Contact Amit Shah
```

Expected standalone tool.

## Intent B

```text
Create Amit Shah as a Contact for ABC Pvt Ltd
```

Expected existing Task 57:

```text
prepare_customer_contact(mode=create)
```

Do not create standalone then link in two writes when the Customer relationship is already part of the user's original intent.

## Intent C

```text
Link Amit Shah to ABC Pvt Ltd
```

Expected existing Task 57:

```text
prepare_customer_contact(mode=link)
```

after exact Contact selection.

## Intent D

```text
Create Amit Shah now; I'll assign him later
```

Expected standalone Contact creation.

The report must state the exact routing rules so the Agent/client does not create unnecessary duplicate records or multi-step writes.

---

# 16. Proposed public tool surface

Compare these designs.

## Option A — reuse customer-contact tool with nullable Customer

Example:

```text
prepare_customer_contact(customer=null, mode=create)
```

Evaluate why this may blur semantics and contract boundaries.

## Option B — dedicated standalone pair

```text
prepare_contact
confirm_contact
```

while retaining:

```text
prepare_customer_contact
confirm_customer_contact
```

for party-bound intent.

## Option C — generic create master tool

Evaluate whether that is too broad.

## Option D — another architecture

The audit must choose one exact design.

Preferred direction is a dedicated standalone Contact master pair if native/source analysis supports it.

---

# 17. Tool naming

If standalone creation is approved, determine exact public names.

Candidate:

```text
prepare_contact
confirm_contact
```

Existing:

```text
search_contacts
prepare_customer_contact
confirm_customer_contact
```

Avoid redundant names such as:

```text
create_contact
create_standalone_contact
prepare_new_contact_master
```

unless existing project naming conventions require otherwise.

The report must choose names consistent with current MCP vocabulary.

---

# 18. Proposed contract

If standalone creation is approved, define the exact typed public input.

Conceptual candidate:

```text
{
  "contact": {
    "first_name": "...?",
    "middle_name": "...?",
    "last_name": "...?",
    "company_name": "...?",
    "designation": "...?",
    "department": "...?",
    "email": "...?",
    "mobile": "...?",
    "phone": "...?"
  }
}
```

This is illustrative only.

The audit must decide the exact V1 field list.

Public contract must not accept:

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
arbitrary custom fields
Google fields
```

Use `PublicContractModel(extra="forbid")` or the project's equivalent.

---

# 19. Prepare behavior

If approved, `prepare_contact` must be non-mutating.

Audit the exact prepare flow:

```text
validate typed input
    ->
check Contact create permission
    ->
construct unsaved native Contact
    ->
construct bounded email/phone child rows
    ->
native validation preview if safe/non-writing
    ->
duplicate checks
    ->
bounded semantic preview
    ->
shared approval store
```

Prepare must not:

```text
insert Contact
save Contact
commit
create Dynamic Link
write child rows to DB
```

Determine whether running `contact.run_method("validate")` on an unsaved document is safe and useful.

Account for CRM validate hooks:

- would manual validation trigger CRM DB side effects?
- if yes, do not call a hook-bearing validation method during prepare;
- instead validate input through safe metadata/native validators without executing write-capable hooks.

This point must be explicitly investigated.

---

# 20. CRM hook risk during prepare

Task 58 confirms normal Contact save runs an installed CRM validation hook that can update CRM Deal snapshots.

Standalone Contact has no party links initially, but prepare must still remain strictly non-mutating.

Audit whether:

```python
contact.run_method("validate")
```

or equivalent manual validation during prepare could execute:

```text
doc_events["Contact"]["validate"]
```

and therefore perform DB mutation.

If yes:

- prohibit running the full validation event chain during prepare;
- use safe input validation / in-memory controller-specific logic only;
- document exact mechanism for implementation.

This is a mandatory audit item.

---

# 21. Confirm behavior

If standalone creation is approved, confirm should conceptually:

```text
claim shared approval
    ->
re-check Contact create permission
    ->
re-run duplicate checks
    ->
rebuild exact approved Contact payload
    ->
frappe.get_doc(payload)
    ->
Contact.insert(ignore_permissions=False)
    ->
native Contact validation/hooks
    ->
single outer commit
```

Determine exact transaction/commit owner.

Do not copy Task 57 internal commit behavior blindly.

Task 58 identified that Task 57 currently commits inside its create/link service branches.

The standalone implementation should follow the repository's preferred:

```text
one confirmation boundary
one outer commit
rollback on failure
```

Document whether a Task 57 hardening task is prerequisite or merely a separate improvement.

---

# 22. Approval architecture

Standalone creation is a business write and must use prepare/confirm approval.

Reuse:

```text
ApprovalStore
claim_for_confirm_write
InteractionDirective
stable fingerprint
safe ToolError pattern
```

Determine exact approval action.

Candidate:

```text
contact_create
```

or:

```text
standalone_contact
```

Choose based on existing action naming convention.

Approval state should bind at least:

```text
site
user
profile
action
exact typed Contact payload
duplicate candidate fingerprint
expected create permission state
```

No caller-controlled approval policy.

No `confirm=true` self-grant.

---

# 23. Stale-state model

A new Contact has no parent document modified timestamp yet.

Therefore stale state is mostly external duplicate/permission state.

Audit confirm-time checks for:

```text
Contact create permission changed
exact email duplicate appeared
normalized phone duplicate appeared
exact Contact name/collision state changed
same request already created after lost response
profile/site/user mismatch
```

Determine idempotency/recovery behavior for a lost response after successful insert.

The implementation must not create duplicate standalone Contacts on a retry merely because the first response was lost.

Recommend a safe recovery pattern.

---

# 24. Idempotency

Audit these cases:

## Same request prepared twice before any confirm

No write yet.

## Same approval token replayed

Must not create a second Contact.

## Confirm succeeded but client lost response

A new prepare with exact same identity may discover the newly created Contact.

Determine whether to return:

```text
duplicate_suspected
```

or:

```text
already_created / idempotent
```

and what evidence is sufficient.

Do not infer identity from same name alone.

---

# 25. Permission model

Standalone Contact creation should not require Customer permission because no Customer is involved.

Audit expected permission matrix:

| Operation | Candidate permission |
|---|---|
| Exact Contact duplicate lookup | Contact read |
| Standalone Contact prepare | Contact create; possibly Contact read for visible duplicate detection |
| Standalone Contact confirm | Contact create |
| Read result | Contact read or returned freshly created bounded projection under create context |

Determine whether successful creation can safely return the bounded newly created Contact if the role has create but not general read.

Use native Frappe permission semantics as authority.

Do not hard-code roles.

Do not use:

```text
ignore_permissions=True
```

---

# 26. Profile placement

Determine where standalone Contact creation belongs.

Candidates:

## Sales only

Pros:

- current Customer/Contact tooling is Sales profile;
- immediate use case is selling/customer interaction.

## Generic/core profile

Pros/cons:

- Contact is not inherently Sales-only;
- but current project profile inventory and tool exposure may not justify a new generic profile.

## Sales + Purchase

Likely broadens scope prematurely.

The audit must choose based on current architecture, not theoretical future use.

Given current business scope, evaluate whether standalone Contact should remain:

```text
Sales-only for V1
```

with future Supplier/Purchase exposure separately audited.

---

# 27. Data minimization

The result must not return full Contact JSON.

Audit a bounded standalone Contact projection.

Likely fields:

```text
doctype = "Contact"
name
full_name
company_name?
email_id?
mobile_no?
phone?
is_primary_contact
link_count
```

For a new standalone Contact, relationship values should make clear:

```text
linked_to_customer = false
link_count = 0
```

Do not return:

```text
all links
addresses
communications
comments
User data
CRM Deal data
child row names
system metadata
```

unless strictly required.

---

# 28. Interaction/error model

Recommend/reuse semantic states.

At minimum evaluate:

```text
PERMISSION_DENIED
CONTACT_DUPLICATE_SUSPECTED
CONTACT_INVALID_EMAIL
CONTACT_INVALID_PHONE
CONTACT_INVALID_IDENTITY
CONFIRMATION_REQUIRED
CONFIRMATION_UNAVAILABLE
STALE_CONFIRMATION
```

If duplicate candidates are visible:

```text
needs_selection
```

may return minimal candidates.

Do not expose hidden Contacts through error wording.

Use existing project error codes wherever semantically equivalent.

---

# 29. Task 57 findings that may affect standalone creation

Task 58 identified two current Task 57 findings:

1. internal service commits;
2. `other_party_link_count` counts all non-target Dynamic Links rather than clearly party-only links.

Audit whether either issue blocks standalone Contact implementation.

The report must classify each:

```text
blocking prerequisite
non-blocking hardening
not relevant
```

If a prerequisite hardening task is required, name it precisely.

Do not silently modify Task 57 during Task 59 audit.

---

# 30. Search reuse decision

Determine whether existing:

```text
search_contacts
```

can fully support:

```text
find standalone Contact
find duplicate before creation
select Contact for later Customer linking
```

without modification.

Preferred outcome:

```text
reuse unchanged
```

if safe.

If modification is required:

- describe exactly why;
- ensure global fuzzy personal-name enumeration remains prohibited;
- distinguish search enhancement from standalone create.

---

# 31. Future linking flow

The standalone Contact creation capability should not duplicate Task 57 linking logic.

Expected later flow:

```text
prepare_contact
confirm_contact
    ->
standalone Contact exists

later:
search_contacts
    ->
prepare_customer_contact(mode=link)
    ->
confirm_customer_contact
```

Audit and confirm that this reuses native Dynamic Link behavior correctly.

No new standalone-link tool should be introduced unless Task 57 is insufficient.

---

# 32. Existing Customer-linked create behavior must remain

Task 57's:

```text
prepare_customer_contact(mode=create)
```

must remain the preferred path when Customer relationship is already known.

Standalone create must not replace it.

The report must define agent-routing examples:

```text
"Create contact Amit"
    -> standalone

"Add Amit as contact for ABC"
    -> customer-linked create

"Link Amit to ABC"
    -> existing Contact link

"Create Amit now, customer unknown"
    -> standalone
```

---

# 33. Testing design for implementation

The audit must produce an implementation-ready test matrix.

At minimum include:

## Contract

- accepted V1 identity fields;
- missing required identity;
- extra fields forbidden;
- raw `links` rejected;
- raw `email_ids` rejected;
- raw `phone_nos` rejected;
- `is_primary_contact` rejected;
- parent derived fields rejected.

## Prepare

- no business DB write;
- no commit;
- Contact create permission;
- email validation;
- phone validation;
- native naming preview;
- duplicate email;
- duplicate phone;
- same-name-only behavior;
- CRM hooks do not write during prepare.

## Confirm

- valid Contact insert;
- no Dynamic Link rows;
- native Contact autoname;
- email child row;
- phone/mobile child row;
- derived parent projections;
- normal permissions;
- installed hooks execute;
- one outer commit;
- rollback on native failure.

## Approval

- valid token;
- wrong user;
- wrong site;
- wrong action/profile;
- expiry;
- replay;
- `confirm=false`;
- self-approval forbidden.

## Duplicate/race

- duplicate appears after prepare;
- permission changes after prepare;
- lost-response recovery;
- same name does not auto-merge;
- exact visible email/phone candidate handling.

## Profile/transport

- Sales exposes intended pair;
- Purchase does not;
- Accounts does not;
- registry parity;
- REST parity;
- MCP parity;
- generated tool catalog.

## Data minimization

- no raw links;
- no unrelated Contact data;
- no child row names;
- no CRM data;
- no User data.

## Regression

- Task 57 Customer-linked create/link unchanged;
- `search_contacts` unchanged unless audit explicitly approves a minimal extension;
- Task 58 future update scope unaffected.

---

# 34. Required comparison tables

The report must include at least:

## Table A — candidate create fields

```text
Public input
Native target
Validation
Required/optional
V1/defer
Reason
```

## Table B — identity policy options

Compare Options A-D from Section 8.

## Table C — email/phone create semantics

Include:

```text
email only
mobile only
phone only
email + mobile
mobile + phone
multiple emails
multiple phones
```

## Table D — duplicate policy

Include:

```text
same name
exact email
case-varied email
exact phone
formatted phone variant
hidden duplicate
visible duplicate
```

## Table E — public API designs

Compare Section 16 options.

## Table F — profile placement

Compare:

```text
Sales only
generic/core
Sales + Purchase
```

---

# 35. Exact questions the report must answer

1. Should standalone Contact creation be supported?
2. Is a Contact with no party links natively valid?
3. What exact identity input is required?
4. Which parent detail fields belong in standalone V1?
5. Should V1 accept email?
6. Should V1 accept mobile?
7. Should V1 accept phone?
8. Should V1 allow multiple emails at creation?
9. Should V1 allow multiple phones at creation?
10. Should standalone Contact ever be primary?
11. Should public input include Dynamic Links?
12. What exact duplicate policy should apply?
13. How are hidden duplicate Contacts handled without leakage?
14. Can existing `search_contacts` be reused unchanged?
15. What exact public tools should be added?
16. What should the approval action be?
17. What exact prepare fingerprint is required?
18. How does confirm revalidate duplicate state?
19. What is the lost-response/idempotency strategy?
20. What exact permission checks apply?
21. Which profile exposes standalone creation?
22. Does Task 57 require prerequisite hardening?
23. Can CRM hooks mutate anything during prepare?
24. What exact bounded result is returned?
25. What remains deferred?
26. What exact next implementation task should be created?

---

# 36. Deliverable

Create:

```text
docs/inspect/STANDALONE_CONTACT_MASTER_CAPABILITY_AUDIT.md
```

The report must contain:

1. executive summary;
2. repository state/version evidence;
3. Task 57/58 baseline;
4. runtime metadata verification;
5. native standalone Contact validity;
6. Contact naming behavior;
7. identity policy;
8. candidate public create fields;
9. email creation semantics;
10. phone/mobile creation semantics;
11. no-link behavior;
12. duplicate/reuse model;
13. hidden duplicate/data-leak policy;
14. search reuse decision;
15. Customer-linked routing distinction;
16. public API option comparison;
17. exact tool names;
18. exact proposed contracts;
19. prepare validation strategy;
20. CRM hook/prepare side-effect analysis;
21. confirm/native insert flow;
22. approval/fingerprint;
23. stale/idempotency model;
24. permission matrix;
25. profile placement;
26. data-minimization projection;
27. error/interaction states;
28. Task 57 hardening dependency assessment;
29. implementation test matrix;
30. limitations/unverified behavior;
31. exact next implementation task.

Every implementation-relevant claim must cite current project source, installed Frappe/ERPNext/CRM source, or runtime metadata.

---

# 37. Acceptance criteria

Task 59 is complete only when:

- [ ] no production Contact capability is implemented;
- [ ] current Task 57 and Task 58 work is inspected;
- [ ] runtime Contact metadata is rechecked;
- [ ] standalone Contact validity is source/runtime proven;
- [ ] minimum identity policy is decided;
- [ ] exact V1 create fields are decided;
- [ ] email child-row construction is decided;
- [ ] phone/mobile child-row construction is decided;
- [ ] no-link behavior is proven;
- [ ] duplicate policy is implementation-ready;
- [ ] hidden duplicate leakage behavior is decided;
- [ ] existing search reuse is decided;
- [ ] Customer-linked vs standalone routing is frozen;
- [ ] public tool names are frozen;
- [ ] exact contracts are proposed;
- [ ] prepare is proven non-mutating;
- [ ] CRM hook risk during prepare is explicitly analyzed;
- [ ] normal Contact insert confirm flow is frozen;
- [ ] approval/fingerprint model is complete;
- [ ] stale/idempotency model is complete;
- [ ] permission model is complete;
- [ ] profile placement is decided;
- [ ] bounded result projection is defined;
- [ ] error/interaction states are defined;
- [ ] Task 57 hardening dependency is classified;
- [ ] full implementation test matrix is present;
- [ ] exact next task is named.

---

# 38. Expected result

At the end of Task 59, this intent must have one unambiguous MCP flow:

```text
User:
"Create contact Amit Shah with amit@example.com and +91..."

        ↓

prepare_contact
        ↓
validate bounded standalone Contact intent
        ↓
permission check
        ↓
duplicate check
        ↓
non-mutating preview
        ↓
shared approval
        ↓
confirm_contact
        ↓
revalidate permission + duplicates
        ↓
native Contact.insert(ignore_permissions=False)
        ↓
native validation/hooks
        ↓
single transaction commit
        ↓
bounded standalone Contact result
```

And this separate intent must remain routed differently:

```text
"Add Amit as contact for ABC Pvt Ltd"

        ↓

prepare_customer_contact(mode=create)
```

Do not collapse these two business intents.

---

# 39. Limitations

Task 59 does not implement standalone Contact creation.

It does not implement:

- Contact updates;
- Contact delete;
- Contact merge;
- Contact rename;
- Contact unlink;
- arbitrary Dynamic Links;
- Supplier Contact support;
- broad global Contact search;
- existing Contact primary promotion;
- Customer projection update logic;
- Task 58 update implementation.

---

# 40. Exact next task

If this audit approves standalone Contact creation, the next task should be:

```text
Task 60 — Standalone Contact Master Creation Implementation
```

That task should implement only the approved standalone Contact create pair and reuse existing Contact search/approval/registry patterns.

After Task 60 implementation/report review is complete, continue with the already-audited update capability as:

```text
Task 61 — Customer-Scoped Contact Detail and Communication Update Implementation
```

If this audit finds a blocking Task 57 hardening prerequisite, it must name that prerequisite explicitly and explain whether it should become Task 60 instead.

Do not start implementation during Task 59.
