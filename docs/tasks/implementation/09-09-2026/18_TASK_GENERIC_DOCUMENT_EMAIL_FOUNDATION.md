# TASK — Generic Document Email Foundation

## Status

NEXT IMPLEMENTATION TASK

## Context / Source of Truth

This task follows the implemented **Generic Document PDF Foundation**.

The implementation report confirms that:

- the shared public PDF tool is `render_document_pdf`;
- the reusable PDF service is `mcp_erpnext/services/common/pdf.py`;
- Sales profile currently allows `Quotation` and `Sales Order`;
- Purchase profile currently allows `Purchase Order`;
- PDF rendering is ephemeral and does not create a Frappe `File`;
- PDF rendering uses the authenticated Frappe user and requires read + print permission;
- the PDF implementation has static/regression coverage, but live ERPNext PDF rendering and LibreChat artifact presentation are still intentionally deferred for later manual verification.

Do **not** block this email implementation task only because live PDF/LibreChat verification is still pending.

However, do not claim a live end-to-end email/PDF PASS unless it is actually tested.

---

# 1. Objective

Add one reusable, permission-safe **generic document email capability** to the existing `mcp_erpnext` app.

This must NOT be Sales Order-specific.

The same shared implementation must support the currently allowed transactional documents:

```text
sales profile:
- Quotation
- Sales Order

purchase profile:
- Purchase Order
```

The architecture must be:

```text
prepare_document_email
        ↓
exact preview
        ↓
trusted approval
        ↓
confirm_document_email
        ↓
Frappe Email Queue / native email path
```

The email implementation MUST reuse the existing generic PDF service:

```text
mcp_erpnext/services/common/pdf.py
```

Do not create a second PDF renderer.

---

# 2. Core Architecture Decision

Use:

```text
BUSINESS / READ TOOLS
        +
GENERIC PDF SERVICE
        +
GENERIC DOCUMENT EMAIL SERVICE
```

Do not create:

```text
email_sales_order
email_quotation
email_purchase_order
send_sales_order_pdf
send_purchase_order_pdf
```

Do not create giant compound tools such as:

```text
find_latest_sales_order_generate_pdf_and_email
```

The agent/orchestrator should compose independent capabilities.

Example:

```text
User:
"Find Patel Trading's latest sales order,
tell me the price they paid for Item ABC,
generate its PDF and email it to them."

Agent:
resolve/search/read tools
        ↓
answer requested item price
        ↓
render_document_pdf        # because the user explicitly asked to generate/view it
        ↓
prepare_document_email     # email service internally reuses same PDF service
        ↓
approval
        ↓
confirm_document_email
```

---

# 3. Mandatory Source Inspection Before Coding

Inspect the current source. Do not implement from assumptions.

## `mcp_erpnext`

At minimum inspect the actual equivalents of:

```text
mcp_erpnext/mcp_server.py
mcp_erpnext/runtime.py
mcp_erpnext/settings.py

mcp_erpnext/profiles/sales.py
mcp_erpnext/profiles/purchase.py

mcp_erpnext/tools/pdf.py
mcp_erpnext/services/common/pdf.py
mcp_erpnext/contracts/pdf.py

existing prepare/confirm tools
existing approval service/state
approval contracts
approval errors
approval expiry/replay behavior

mcp_erpnext/services/common/read.py
profile DocType allowlist

contracts/
tools/
services/
tests/
docs/TOOLS.md
scripts/generate_tool_catalog.py
```

The exact current approval implementation is especially important.

Reuse the existing trusted approval architecture rather than inventing a new confirmation mechanism.

## Installed Frappe v16 / ERPNext v16

Inspect the installed source for:

```text
frappe.sendmail
Frappe Email Queue
Communication
Email Account selection
document Email permission
attachments accepted by frappe.sendmail
transaction / commit behavior in v16
Contact / Dynamic Link helpers
party/contact email resolution
Sales Order contact fields
Quotation contact/party fields
Purchase Order contact fields
Customer/Supplier/Lead contact behavior
```

Prefer native Frappe/ERPNext helpers.

Do not write custom SMTP code.

---

# 4. Public MCP Tools

Implement exactly one generic prepare/confirm family:

```text
prepare_document_email
confirm_document_email
```

No public direct-send tool.

Do NOT expose:

```text
send_document_email
```

that can bypass preparation/approval.

---

# 5. `prepare_document_email`

## Purpose

Resolve and validate the exact email action, generate/validate the attachment, and return a human-readable preview.

It MUST NOT send the email.

Conceptual public input:

```text
doctype: string
name: string

recipient_email?: string

subject?: string
message?: string

print_format?: string
letterhead?: string
language?: string
```

Adapt exact names to current project conventions.

### Do not expose

Do not expose:

```text
approval=true
confirm=true
run_as
user
sender_password
SMTP credentials
raw HTML/Jinja/CSS for PDF
arbitrary attachment file paths
```

---

# 6. Profile-Level DocType Policy

Email capability is generic, but the active MCP profile must enforce its own supported documents server-side.

Current policy from the implemented PDF foundation:

```text
sales:
- Quotation
- Sales Order

purchase:
- Purchase Order
```

Use the actual shared profile/read allowlist if possible.

Example:

```text
active profile = sales

prepare_document_email(
    doctype="Purchase Order",
    ...
)
```

must fail before document/email resolution.

Do not depend on agent instructions for this boundary.

If the current tool-contract architecture can expose profile-specific `doctype` enums in `tools/list`, prefer that.

If the current contract architecture cannot narrow the public schema without destabilizing existing contracts, keep the server-side allowlist authoritative and document the schema limitation in the implementation report.

Do not make unrelated PDF contract changes in this task unless necessary and regression-safe.

---

# 7. Recipient Resolution — Critical Safety Rule

The main v1 workflow is:

```text
"email it to them"
```

where "them" means the party/contact already associated with the ERPNext document.

Do not let the model silently choose an unrelated external recipient.

## Default behavior

When `recipient_email` is omitted:

1. Inspect the document's native contact/party fields.
2. Prefer the document's explicitly selected/contact email when ERPNext provides one.
3. Otherwise use Frappe/ERPNext native Contact / Dynamic Link / party helpers where appropriate.
4. Resolve only recipients genuinely associated with the document's business party.
5. Never pick a random email from multiple candidates.

## Supported party semantics

Inspect actual ERPNext v16 fields before coding.

Expected concepts may include:

```text
Sales Order -> Customer / linked Contact
Quotation -> inspect actual quotation_to / party/contact semantics
Purchase Order -> Supplier / linked Contact
```

Do not hard-code field names from this task if the installed source differs.

## Ambiguity

If there are multiple valid party/contact emails and no authoritative default:

```text
prepare_document_email
    -> needs_input / ambiguous
    -> return allowed candidate emails + enough non-sensitive labels
```

The agent asks the user to choose.

Then the selected `recipient_email` may be supplied on the next prepare call.

## Explicit `recipient_email`

For this v1 foundation, an explicitly provided `recipient_email` must normally match a validated recipient associated with the document/party.

Do not enable arbitrary third-party exfiltration by default.

If the current project already has an explicit policy allowing arbitrary recipients, do not silently reuse it; document and test it first.

A future task may add a separate, policy-controlled "custom external recipient" capability.

---

# 8. Recipient Privacy / Output

Return only the email information needed for selection/approval.

Do not dump full Contact records.

Example ambiguity result:

```text
status: needs_input

candidates:
- accounts@customer.example — Primary Contact
- purchase@customer.example — Purchase Contact
```

Do not expose unrelated phone numbers, addresses, notes, or Contact metadata.

---

# 9. Subject and Message

The email action must bind the exact subject and body before approval.

## If the agent supplies them

Validate length and basic shape, then include exact text in the prepare preview.

## If omitted

Use deterministic, minimal defaults.

Conceptually:

```text
Subject:
Sales Order SAL-ORD-2026-00014

Message:
Please find attached Sales Order SAL-ORD-2026-00014.
```

Use translated/document labels where appropriate if the current project has a native convention.

Do not generate hidden AI-written email content inside the MCP service.

The MCP server should not invent promotional, legal, payment, or commercial language.

## Email Template

Do not add a complicated new Email Template policy unless the existing project already has one.

If current Frappe-native Email Template reuse is simple and clearly useful, it may be supported as an OPTIONAL explicitly selected field, but it must be:

```text
validated
rendered before approval
included in the exact approval-bound content
```

Do not let this expand the task unnecessarily.

---

# 10. PDF Attachment — Must Reuse Existing Service

The document email must attach the same company-standard Frappe PDF behavior already implemented.

Reuse:

```text
mcp_erpnext/services/common/pdf.py
```

Do not:

```text
call a second copy of frappe.get_print logic
create a separate email PDF renderer
persist a Frappe File just for email
write a temporary PDF unless technically unavoidable
```

The existing PDF service already handles:

```text
Print Format
Letter Head
language
profile policy
read permission
print permission
Frappe-native PDF rendering
```

The email service should call the shared service layer directly rather than round-tripping through the public MCP tool.

---

# 11. Permissions

The existing authenticated Frappe user context remains authoritative.

At PREPARE time require:

```text
document read permission
document email permission
document print permission      # because a PDF is being attached
```

At CONFIRM time revalidate the required permissions.

Do not:

```text
switch to Administrator
use a service-user fallback for HTTP
set ignore_permissions
bypass Email permission
bypass Print permission
```

Frappe exposes separate `Email` and `Print` document permissions. Use native permission semantics.

---

# 12. Prepare Result / Human Preview

When ready, the prepare tool should return an exact preview similar to:

```text
Email ready for approval

Document: Sales Order SAL-ORD-2026-00014
To: accounts@pateltrading.example
Subject: Sales Order SAL-ORD-2026-00014

Message:
Please find attached Sales Order SAL-ORD-2026-00014.

Attachment:
SAL-ORD-2026-00014.pdf

Print Format:
Shayona Standard Sales Order

MIME:
application/pdf
```

Also return the current approval metadata required by the existing MCP approval system.

Do not send during prepare.

---

# 13. Trusted Approval — Reuse Existing System

This is a real external side effect.

Do not treat any of these as sufficient approval:

```text
confirm=true
approved=true
"yes" inside model-generated tool arguments
the model saying "user approved"
```

Reuse the existing trusted approval mechanism already used by `mcp_erpnext`.

The prepare/confirm email flow must inherit the same:

```text
user binding
profile binding
expiry
single-use behavior
trusted channel requirement
replay protection
fail-closed behavior
```

where those semantics already exist.

Do not create a second independent approval framework.

---

# 14. Exact Prepared-State Binding

Approval must bind the exact action that will be sent.

At minimum bind:

```text
authenticated user
active MCP profile
doctype
document name

recipient email(s)

subject
message

print format
letterhead
language

attachment filename
attachment MIME type

document state/version marker
```

Also bind the attachment content safely.

## Preferred approach

Inspect the existing approval state implementation.

If it safely supports private binary prepared state:

```text
prepare:
render PDF once
store exact prepared PDF bytes privately
store hash/metadata
return preview only

confirm:
send the exact already-approved bytes
```

This gives the strongest guarantee that the approved attachment is exactly the attachment sent.

## Alternative

If binary state is not appropriate:

```text
prepare:
render PDF
store SHA-256
store document modified/version marker
store render inputs

confirm:
revalidate document + permissions
rerender PDF
compare SHA-256
```

If the resulting artifact differs:

```text
PREPARED_STATE_CHANGED
```

or equivalent, and require a fresh prepare/approval cycle.

Do not silently email a changed document after the user approved an earlier preview.

The implementation report must state which strategy was used and why.

---

# 15. Confirm Contract

`confirm_document_email` should take only the existing trusted approval reference/token/input required by the project.

It must NOT allow the model to change:

```text
recipient
subject
message
doctype
name
print_format
letterhead
language
attachment
```

during confirmation.

Any requested change requires:

```text
prepare again
-> new preview
-> new approval
-> confirm
```

---

# 16. Duplicate Send / Replay Safety

An approved email action must be single-use.

If `confirm_document_email` is replayed:

```text
do not send a second email
```

Use the existing approval-consumption semantics.

Tests must verify that the native email send function is called at most once per approved action.

---

# 17. Native Frappe Email Sending

Use Frappe's native email API / queue.

Preferred direction:

```text
frappe.sendmail(...)
```

with the installed v16-native attachment structure and Email Queue behavior.

Do not implement custom SMTP.

Do not directly connect to Gmail/Outlook/SMTP servers from `mcp_erpnext`.

Inspect the installed v16 source to determine the correct in-memory attachment shape.

The PDF foundation currently produces ephemeral bytes and no `File` document, so prefer a native in-memory attachment form when Frappe supports it.

Do not persist a `File` only because documentation examples commonly use `file_url`.

---

# 18. Queue vs Immediate SMTP

Prefer Frappe's normal queued email behavior.

A successful confirm should normally mean:

```text
accepted/queued by Frappe
```

not necessarily:

```text
recipient SMTP server has already delivered it
```

Return the most useful native Email Queue / Communication reference if available.

Do not wait for final SMTP delivery unless the existing project explicitly does so.

---

# 19. Frappe v16 Transaction Rule — Mandatory Inspection

The installed project is on Frappe v16.

Frappe v16 changed `frappe.sendmail` transaction behavior; do not assume it implicitly commits.

Inspect:

```text
existing mcp_erpnext runtime transaction lifecycle
current confirm-write commit behavior
frappe.sendmail implementation
Email Queue creation
worker scheduling / queue behavior
```

Use the existing project's transaction boundary.

Do not add arbitrary `frappe.db.commit()` inside a low-level email service unless the current runtime architecture explicitly requires and justifies it.

Ensure the Email Queue/Communication records are durable before asynchronous processing can depend on them.

Add tests for the chosen transaction behavior where possible.

---

# 20. Failure Handling

Return typed structured errors consistent with the current project.

Cover at least:

```text
DOCTYPE_NOT_ALLOWED
DOCUMENT_NOT_FOUND
PERMISSION_DENIED
RECIPIENT_NOT_FOUND
RECIPIENT_AMBIGUOUS / needs_input
INVALID_RECIPIENT
INVALID_EMAIL
PDF_RENDER_FAILED
PRINT_FORMAT_INVALID
EMAIL_ACCOUNT_NOT_CONFIGURED
EMAIL_PREPARE_FAILED
TRUSTED_APPROVAL_UNAVAILABLE
APPROVAL_EXPIRED
APPROVAL_ALREADY_USED
APPROVAL_MISMATCH
PREPARED_STATE_CHANGED
EMAIL_QUEUE_FAILED
```

Use existing project error codes where equivalent codes already exist.

Do not invent duplicate code names if the current error taxonomy already covers them.

Do not expose SMTP credentials, server secrets, stack traces, or internal contact data to the model.

---

# 21. Output Contracts

Use typed contracts.

Conceptual `prepare_document_email` terminal states:

```text
ready_for_approval
needs_input
not_found
error
```

A ready result should include:

```text
doctype
name
recipient
subject
message preview
attachment filename
print_format_used
mime_type
approval metadata/reference
```

Conceptual `confirm_document_email` states:

```text
queued / sent
error
```

Prefer wording such as `queued` if the native action only queues delivery.

Do not claim final external delivery unless Frappe actually confirms delivery.

---

# 22. Agent / LibreChat Instructions

Update relevant agent instructions/configuration only where this project stores those instructions in source/docs.

At minimum account for:

```text
ERPNext Coordinator
ERPNext Quotation Agent
ERPNext Sales Order Agent
ERPNext Purchase Agent
```

Behavior:

```text
User:
"Email SO-14 to the customer."

Agent:
1. call prepare_document_email
2. show exact preview
3. wait for trusted user approval
4. only then call confirm_document_email
```

Do not auto-confirm just because the original user sentence used the verb "email".

If the client-side agent configuration is not stored in this repository, document the exact instruction block that must be added manually rather than modifying unrelated LibreChat source.

---

# 23. Compound Prompt Acceptance Flow

Primary acceptance prompt:

```text
Find Patel Trading's latest sales order,
tell me the price they paid for Item ABC,
generate its PDF and email it to them.
```

Expected orchestration:

```text
resolve Patel Trading
        ↓
find latest Sales Order
        ↓
query Item ABC price
        ↓
answer price
        ↓
render_document_pdf
        ↓
prepare_document_email
        ↓
show exact email preview
        ↓
WAIT FOR TRUSTED APPROVAL
        ↓
confirm_document_email
        ↓
Frappe queue
```

No giant compound MCP tool should be created.

---

# 24. Cross-Profile Safety

Tests must prove:

```text
Sales MCP:
Quotation email          -> allowed
Sales Order email        -> allowed
Purchase Order email     -> denied

Purchase MCP:
Purchase Order email     -> allowed
Sales Order email        -> denied
Quotation email          -> denied
```

Enforce this in the service layer.

---

# 25. Tests — PREPARE

Add static/unit/service tests for:

```text
Sales Order auto recipient resolution
Quotation recipient resolution
Purchase Order recipient resolution

unique recipient
no recipient
multiple recipients
selected valid candidate
selected invalid/unrelated candidate

default subject
custom subject
default message
custom message

default Print Format
explicit Print Format
PDF service reuse

read permission denied
email permission denied
print permission denied

cross-profile DocType
missing document
invalid email
```

Mock native Frappe APIs appropriately.

Do not send real external email from the unit suite.

---

# 26. Tests — APPROVAL / CONFIRM

Verify:

```text
prepare does not send
confirm without trusted approval fails
expired approval fails
replayed approval does not resend
approval belongs to correct user
approval belongs to correct profile
recipient cannot change after approval
subject cannot change after approval
message cannot change after approval
document cannot change after approval
PDF/attachment cannot change after approval
successful confirm calls native send exactly once
```

---

# 27. Tests — Native Send / Queue

Verify with mocks or a designated test environment:

```text
frappe.sendmail/native API used
custom SMTP not used
correct recipient
correct subject
correct message
correct PDF filename
correct PDF bytes
correct MIME behavior
no Frappe File created
queue/communication reference captured if available
transaction lifecycle correct
```

---

# 28. Live Email Safety

Do NOT send a real customer/supplier email just to test this task.

A real confirm/send test is allowed only if there is an explicitly designated test mailbox/recipient and the user separately authorizes the test.

Otherwise:

```text
PREPARE runtime may be verified safely.
CONFIRM live send = NOT VERIFIED.
```

This is acceptable for the implementation report.

Do not fake a PASS.

---

# 29. Regression Requirements

Do not change behavior of:

```text
mcp_identity
sales/purchase profile startup
existing search/read tools
Sales Order analytics
prepare/confirm document writes
existing approval framework
render_document_pdf public behavior
existing PDF service semantics
```

Run the full existing test suite.

Also run:

```text
scripts/generate_tool_catalog.py --check
```

or the current equivalent.

---

# 30. Documentation

Update the current tool documentation.

Add an architecture document if consistent with the repository:

```text
docs/architecture/MCP_DOCUMENT_EMAIL.md
```

Document:

```text
prepare_document_email
confirm_document_email
recipient resolution
profile allowlist
permissions
PDF reuse
approval binding
Frappe Email Queue
transaction behavior
side-effect safety
error states
examples
limitations
```

Do not duplicate full Frappe email documentation.

---

# 31. Mandatory Implementation / Inspection Report

After implementation, inspect the final source and create:

```text
mcp_erpnext/docs/inspect/GENERIC_DOCUMENT_EMAIL_FOUNDATION_IMPLEMENTATION_REPORT.md
```

Create this report even if some runtime tests are blocked or fail.

The report must contain:

## 1. Final Status

```text
PASS / PARTIAL / FAIL
```

## 2. Source Inspected

Exact `mcp_erpnext`, Frappe, and ERPNext paths inspected.

## 3. Files Changed

Every file created or modified.

## 4. Final MCP Tool Contracts

Actual schemas for:

```text
prepare_document_email
confirm_document_email
```

Do not repeat planned schemas if implementation differs.

## 5. Profile Policy

Actual allowed DocTypes in Sales/Purchase profiles.

## 6. Recipient Resolution

Explain exact runtime rules for:

```text
Sales Order
Quotation
Purchase Order
```

including ambiguity and explicit selection.

## 7. Permission Behavior

Explain exact:

```text
read
email
print
```

checks and authenticated-user behavior.

## 8. PDF Reuse

Prove that:

```text
mcp_erpnext/services/common/pdf.py
```

is reused and no second PDF path was created.

## 9. Approval Binding

List every field bound to approval and explain replay/expiry/user/profile binding.

Explain whether exact PDF bytes or hash/revalidation is used.

## 10. Frappe-Native Email APIs

Exact functions/modules used.

Explain:

```text
Email Queue behavior
Communication behavior
attachment representation
transaction/commit behavior
```

## 11. Runtime Test Matrix

Include:

| Test | Expected | Observed | Result |
|---|---|---|---|
| Sales Order prepare | ready preview | ... | ... |
| Quotation prepare | ready preview | ... | ... |
| Purchase Order prepare | ready preview | ... | ... |
| Recipient missing | safe failure | ... | ... |
| Recipient ambiguity | needs input | ... | ... |
| Email permission denied | denied | ... | ... |
| Print permission denied | denied | ... | ... |
| Cross-profile DocType | denied | ... | ... |
| Prepare sends nothing | no email | ... | ... |
| Confirm without approval | denied | ... | ... |
| Replay approval | no duplicate | ... | ... |
| Native queue/send | exact result | ... | ... |
| PDF attachment | exact approved artifact | ... | ... |

Never fabricate observed values.

## 12. End-to-End LibreChat Verification

Document whether the compound prompt was actually tested.

If not:

```text
NOT VERIFIED IN LIBRECHAT
```

## 13. Regression Results

Exact command + test count/result.

## 14. Important Findings

Especially:

```text
recipient-field surprises
Frappe contact helper behavior
Email Account requirements
transaction behavior
queue behavior
approval limitations
MCP/LibreChat limitations
```

## 15. Remaining Limitations

Only actual limitations.

## 16. Safety Confirmation

Explicitly confirm:

```text
No real secrets were added.
No arbitrary permission bypass was introduced.
No custom SMTP path was created.
No customer/supplier email was sent during testing unless explicitly authorized.
No PDF duplicate implementation was created.
No existing approval semantics were weakened.
```

## 17. Exact Next Task

If email foundation is implemented successfully:

```text
Live PDF + Email Verification

Then:
Generic Document WhatsApp Foundation
or
Compound Document Communication Workflows,
depending on project priority.
```

---

# 32. Acceptance Criteria

Task is complete when:

```text
[ ] actual current source inspected first
[ ] installed Frappe/ERPNext email/contact behavior inspected
[ ] prepare_document_email implemented
[ ] confirm_document_email implemented
[ ] no public direct-send bypass tool
[ ] same implementation supports Sales and Purchase profiles
[ ] profile DocType allowlist enforced server-side
[ ] recipient automatically resolves from the document party when unique
[ ] recipient ambiguity returns structured needs_input
[ ] unrelated arbitrary recipient is not silently accepted
[ ] authenticated Frappe user preserved
[ ] read permission enforced
[ ] email permission enforced
[ ] print permission enforced for PDF attachment
[ ] existing common PDF service reused
[ ] no duplicate PDF renderer
[ ] no Frappe File persisted merely for attachment
[ ] prepare does not send
[ ] trusted approval is mandatory
[ ] confirm cannot mutate prepared action
[ ] approval is single-use / replay safe
[ ] approved document/recipient/content/attachment are bound
[ ] Frappe-native email API/queue used
[ ] no custom SMTP
[ ] Frappe v16 transaction behavior explicitly handled
[ ] typed output/error contracts added
[ ] tool catalog/docs updated
[ ] full existing regression suite passes
[ ] implementation report created in docs/inspect/
```

---

# 33. Expected End State

The system should support:

```text
"Email this Sales Order to the customer."
"Email this Quotation to the customer."
"Email this Purchase Order to the supplier."
```

through the same generic foundation.

And a compound request such as:

```text
"Find Patel Trading's latest sales order,
tell me the price they paid for Item ABC,
generate its PDF and email it to them."
```

should be composed from reusable tools, with the email side effect always going through:

```text
prepare
-> exact preview
-> trusted approval
-> confirm
-> Frappe Email Queue
```

No DocType-specific email duplication.
No arbitrary identity/permission bypass.
No arbitrary recipient exfiltration.
No second PDF implementation.
