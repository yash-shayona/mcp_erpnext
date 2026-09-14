# Generic Document Email

`prepare_document_email` and `confirm_document_email` provide one generic,
profile-scoped workflow for emailing an existing transactional document with
its company-standard PDF:

```text
prepare -> exact preview -> trusted approval -> confirm -> Frappe Email Queue
```

The capability supports `Quotation` and `Sales Order` in the Sales profile and
`Purchase Order` in the Purchase profile. The service is shared; there are no
DocType-specific email tools or direct-send bypasses.

## Prepare

`prepare_document_email` accepts an exact `doctype` and `name`, with optional
`recipient_email`, `subject`, `message`, `print_format`, `letterhead`, and
`language`. It performs no send.

The active profile allowlist is enforced in the service before document
lookup. The authenticated Frappe user must have `read`, `email`, and `print`
permission on the document. The PDF is rendered by
`mcp_erpnext/services/common/pdf.py`, so Frappe Print Format, Letter Head,
language, and native PDF behavior remain centralized.

## Recipient resolution

Recipient addresses are restricted to the document's business party:

- Sales Order: `Customer` from `customer`.
- Purchase Order: `Supplier` from `supplier`.
- Quotation: the dynamic party in `quotation_to` and `party_name`.

ERPNext's native transaction `contact_email` is preferred when present. If it
is absent, the party's permission-checked native `email_id` is used as the
authoritative primary-contact address. If no party email exists, permission-
checked Contacts linked through Dynamic Link are enumerated. A single address
is selected automatically; multiple addresses return `needs_input` with only
email and display-label candidates. An explicitly supplied address must be a
valid email and match one of those associated addresses.

No arbitrary external recipient, SMTP credential, Contact metadata, phone
number, or address is accepted or returned.

## Approval binding

The prepare operation stores a shared Frappe-cache approval through the existing
`ApprovalStore`. Its payload binds the profile, exact document, document
`modified` and `docstatus` markers, recipient, subject, message, PDF render
inputs and resolved format, attachment filename/MIME type, and SHA-256 digest.
The store separately binds the authenticated site/user, applies its configured
TTL/trust policy, and consumes approvals atomically.

The implementation uses hash/revalidation rather than storing PDF bytes in the
approval store. Confirm reloads the document with all three permissions,
checks the document state marker, revalidates the recipient association,
rerenders through the shared PDF service, and compares the format, filename,
MIME type, and digest. A mismatch returns
`PREPARED_STATE_CHANGED` and sends nothing.

`confirm_document_email` accepts only the approval token. It cannot change the
recipient, content, document, render inputs, or attachment. In the default
`trusted_human` mode, a server-verified trusted approval is required; a model
argument such as `confirm=true` is not used.

## Frappe queue and attachment

Confirm calls native `frappe.sendmail` with its default delayed queue behavior,
the exact recipient/subject/message, and an in-memory attachment:

```python
{"fname": "SO-001.pdf", "fcontent": pdf_bytes, "content_type": "application/pdf"}
```

Frappe v16 creates the `Email Queue` row during `sendmail`; it does not commit
that transaction. The high-level confirm service commits after successful
queue creation, matching existing MCP confirm-write services, and rolls back
on failure. The result says `queued`, not delivered, and returns the native
queue name when available. No custom SMTP connection or Frappe `File` is
created by this capability.

## Result and error states

Prepare returns typed `ready_for_approval`, `needs_input`, `not_found`, or
`error` results. Confirm returns typed `queued` or `error` results. Relevant
errors include `DOCTYPE_NOT_ALLOWED`, `DOCUMENT_NOT_FOUND`,
`PERMISSION_DENIED`, `RECIPIENT_NOT_FOUND`, `RECIPIENT_AMBIGUOUS` through the
`needs_input` state, `INVALID_RECIPIENT`, `INVALID_EMAIL`, PDF errors,
`EMAIL_ACCOUNT_NOT_CONFIGURED`, `PREPARED_STATE_CHANGED`, approval errors, and
`EMAIL_QUEUE_FAILED`.

## Agent behavior

For “Email this Sales Order to the customer,” the agent calls prepare, shows
the exact preview, waits for trusted user approval, and only then calls
confirm. The original request to email is not itself approval. A compound
request composes existing resolution/read/PDF tools with this same prepare /
approval / confirm workflow.

Live customer/supplier delivery and LibreChat presentation remain manual
verification activities; unit tests use mocked native email calls.
