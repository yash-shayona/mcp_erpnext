# Generic Document Email Foundation — Implementation Report

## 1. Final Status

PARTIAL — the generic implementation, typed contracts, approval binding,
native queue integration, static/unit coverage, and catalog generation are
complete. Live ERPNext email queue delivery, live PDF rendering, and LibreChat
compound-prompt presentation were not run. No real customer or supplier email
was sent.

## 2. Source Inspected

### `mcp_erpnext`

- `mcp_erpnext/mcp_server.py`
- `mcp_erpnext/runtime.py`
- `mcp_erpnext/settings.py`
- `mcp_erpnext/profiles/sales.py`
- `mcp_erpnext/profiles/purchase.py`
- `mcp_erpnext/tools/pdf.py`
- `mcp_erpnext/services/common/pdf.py`
- `mcp_erpnext/contracts/pdf.py`
- `mcp_erpnext/approvals.py`
- `mcp_erpnext/services/common/lifecycle.py`
- `mcp_erpnext/services/common/read.py`
- `mcp_erpnext/contracts/interaction.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/audit.py`
- `mcp_erpnext/tools/lifecycle.py`
- `mcp_erpnext/contracts/lifecycle.py`
- `mcp_erpnext/tests/test_approvals.py`
- `mcp_erpnext/tests/test_pdf.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_tool_contracts.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `scripts/generate_tool_catalog.py`

### Installed Frappe/ERPNext source

- `apps/frappe/frappe/email/__init__.py`
- `apps/frappe/frappe/email/doctype/email_queue/email_queue.py`
- `apps/frappe/frappe/email/email_body.py`
- `apps/frappe/frappe/email/doctype/email_account/email_account.py`
- `apps/frappe/frappe/contacts/doctype/contact/contact.py`
- `apps/frappe/frappe/utils/__init__.py`
- `apps/erpnext/erpnext/selling/doctype/sales_order/sales_order.json`
- `apps/erpnext/erpnext/selling/doctype/sales_order/sales_order.py`
- `apps/erpnext/erpnext/selling/doctype/quotation/quotation.json`
- `apps/erpnext/erpnext/selling/doctype/quotation/quotation.py`
- `apps/erpnext/erpnext/buying/doctype/purchase_order/purchase_order.json`
- `apps/erpnext/erpnext/buying/doctype/purchase_order/purchase_order.py`
- `apps/erpnext/erpnext/selling/doctype/customer/customer.json`
- `apps/erpnext/erpnext/buying/doctype/supplier/supplier.json`

## 3. Files Changed

- `docs/TOOLS.md` — regenerated catalog.
- `docs/architecture/MCP_DOCUMENT_EMAIL.md` — email architecture and safety behavior.
- `docs/inspect/GENERIC_DOCUMENT_EMAIL_FOUNDATION_IMPLEMENTATION_REPORT.md` — this report.
- `scripts/generate_tool_catalog.py` — catalog link for the email architecture.
- `mcp_erpnext/contracts/email.py` — typed prepare/confirm contracts.
- `mcp_erpnext/contracts/registry.py` — public metadata for the two tools.
- `mcp_erpnext/profiles/sales.py` — Sales registration.
- `mcp_erpnext/profiles/purchase.py` — Purchase registration.
- `mcp_erpnext/services/common/email.py` — shared email service.
- `mcp_erpnext/tools/email.py` — public wrappers.
- `mcp_erpnext/tests/test_email.py` — service/approval/send safety tests.
- `mcp_erpnext/tests/test_profiles.py` — profile inventory regression expectations.
- `mcp_erpnext/tests/test_tool_registration.py` — registration regression expectation.

The checkout also contains pre-existing uncommitted PDF-foundation files; those
were preserved and reused rather than rewritten.

## 4. Final MCP Tool Contracts

`prepare_document_email` input is the typed `DocumentEmailPrepareInput` model:

```text
doctype: "Quotation" | "Sales Order" | "Purchase Order"
name: non-empty string
recipient_email?: non-empty string
subject?: string, 1..255 characters
message?: string, 1..10000 characters
print_format?: non-empty string
letterhead?: non-empty string
language?: non-empty string
```

It returns `DocumentEmailPrepareOutput` with terminal statuses:

```text
ready_for_approval: preview, approval_token, expires_in_seconds, interaction
needs_input: doctype, name, candidates[email,label], message, interaction
not_found: doctype, name
error: shared ToolError
```

`confirm_document_email` input is only `approval_token` and returns
`DocumentEmailConfirmOutput`:

```text
queued: doctype, name, recipient, queue_reference?, message
error: shared ToolError
```

There is no public `send_document_email` tool.

## 5. Profile Policy

The service reuses the existing profile policy from
`services/common/read.py`:

| Profile | Allowed email DocTypes |
|---|---|
| Sales | `Quotation`, `Sales Order` |
| Purchase | `Purchase Order` |

The public enum intentionally lists all three current transaction types in
both profile schemas because the current registry uses one shared typed model.
The server-side service allowlist is authoritative and rejects cross-profile
requests before document lookup.

## 6. Recipient Resolution

- Sales Order uses `Customer` / `customer`.
- Purchase Order uses `Supplier` / `supplier`.
- Quotation uses its actual dynamic `quotation_to` / `party_name` fields.
- A populated transaction `contact_email` is preferred.
- Otherwise a permission-checked native party `email_id` is authoritative.
- Otherwise linked Contacts are read through Frappe's native
  `get_contacts_linking_to` helper; only email and display-label data are
  returned.
- One unique address is selected. Multiple addresses produce typed
  `needs_input` with `INPUT`, `PROVIDE_INPUT`, and `CANCEL` semantics.
- An explicit recipient must pass Frappe email validation and match an
  associated candidate, otherwise `INVALID_EMAIL` or `INVALID_RECIPIENT` is
  returned.
- Missing party/email data returns `RECIPIENT_NOT_FOUND`.

## 7. Permission Behavior

Both prepare and confirm load the exact document and require native
`doc.has_permission("read")`, `doc.has_permission("email")`, and
`doc.has_permission("print")`. The runtime's authenticated Frappe session user
remains authoritative. There is no Administrator fallback,
`ignore_permissions`, or service-user fallback.

## 8. PDF Reuse

`services/common/email.py` imports the existing `services/common/pdf.py` as
`pdf_service` and calls `render_document_pdf` in both prepare and confirm. No
second `frappe.get_print` path was added, and no Frappe `File` is persisted.

## 9. Approval Binding

The existing `ApprovalStore` binds the action (`document_email`), Frappe site,
authenticated user, TTL, trust policy, and single-use state. The payload also
binds:

```text
profile
doctype, name
modified, docstatus
recipient_email
subject, message
print_format, print_format_used, letterhead, language
attachment_filename, attachment_mime_type, attachment_sha256
```

The selected strategy is hash/revalidation. Exact PDF bytes are rendered for
prepare and hashed; confirm reloads/revalidates the document and permissions,
revalidates the recipient association, rerenders with the approved inputs, and
compares the hash plus attachment metadata. A changed document, recipient
association, or artifact is rejected as
`PREPARED_STATE_CHANGED`. Confirmation takes no mutable action fields.

## 10. Frappe-Native Email APIs

The service uses `frappe.sendmail` with the v16 in-memory attachment keys
`fname`, `fcontent`, and `content_type`, plus the document reference
`doctype`/`name`. Frappe's `QueueBuilder.process(send_now=False)` creates the
`Email Queue` row. It does not implicitly commit the row in the inspected v16
source. The service calls `frappe.db.commit()` only after successful queue
creation, following existing high-level MCP confirm-write services, and calls
rollback on queue failure. The returned status is `queued`; it is not SMTP
delivery confirmation. No custom SMTP implementation or File document was
added.

## 11. Runtime Test Matrix

| Test | Expected | Observed | Result |
|---|---|---|---|
| Sales Order prepare | ready preview | Mocked native contact/PDF produced ready preview | PASS |
| Quotation prepare | ready preview | Not run in live site; shared service path covered statically | NOT VERIFIED |
| Purchase Order prepare | ready preview | Not run in live site; profile/service policy covered statically | NOT VERIFIED |
| Recipient missing | safe failure | `RECIPIENT_NOT_FOUND` path implemented; no live site data | STATIC |
| Recipient ambiguity | needs input | Typed `needs_input` with candidate emails/labels | PASS |
| Email permission denied | denied | `PERMISSION_DENIED` | PASS |
| Print permission denied | denied | `PERMISSION_DENIED` | PASS |
| Cross-profile DocType | denied | `DOCTYPE_NOT_ALLOWED` before lookup | PASS |
| Prepare sends nothing | no email | mocked sendmail not called | PASS |
| Confirm without approval | denied | shared confirmation failure | PASS |
| Replay approval | no duplicate | second confirm `CONFIRMATION_CONSUMED`; one send call | PASS |
| Native queue/send | exact result | mocked `frappe.sendmail`, commit, queue reference | PASS |
| PDF attachment | exact approved artifact | digest and bytes compared in test | PASS |

## 12. End-to-End LibreChat Verification

NOT VERIFIED IN LIBRECHAT. No live compound prompt or real queue/delivery test
was run.

## 13. Regression Results

Command:

```text
../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
```

Observed: `Ran 163 tests ... OK`.

The focused command also passed:

```text
../../env/bin/python -m unittest mcp_erpnext.tests.test_email mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_profiles mcp_erpnext.tests.test_tool_contracts
```

Observed: `Ran 24 tests ... OK`.

Catalog validation command:

```text
../../env/bin/python scripts/generate_tool_catalog.py --check
```

Observed: passed with no stale-catalog error. `git diff --check` also passed.

## 14. Important Findings

- ERPNext v16 transaction fields are `Sales Order.customer`,
  `Quotation.quotation_to` + `party_name`, and `Purchase Order.supplier`.
- All three supported transactions expose native `contact_person` and
  `contact_email` fields; Customer and Supplier expose a read-only native
  `email_id` from their primary contact.
- Frappe's Contact helper returns linked contacts; the service additionally
  reads only their email fields and labels under normal permissions.
- Frappe v16's `sendmail` queue path accepts in-memory `fcontent` and creates
  an Email Queue row without an implicit commit.
- The current shared contract model cannot narrow the public doctype enum per
  process profile without introducing separate model variants, so the service
  allowlist remains the authoritative cross-profile boundary.

## 15. Remaining Limitations

- Live prepare against existing Sales Order, Quotation, and Purchase Order
  records was not run.
- Live outgoing Email Account/Email Queue creation and worker processing were
  not run.
- Live PDF rendering and final email delivery were not run.
- LibreChat artifact/preview/approval presentation was not run.
- Trusted-human approval still requires an independently verified transport
  adapter in `trusted_human` mode; unit tests use `agent_delegated` for the
  deterministic confirm path.

## 16. Safety Confirmation

- No real secrets were added.
- No arbitrary permission bypass was introduced.
- No custom SMTP path was created.
- No customer/supplier email was sent during testing.
- No duplicate PDF implementation was created.
- Existing approval semantics were reused and not weakened.
- No Frappe `File` was created by the email implementation.

## 17. Exact Next Task

Live PDF + Email Verification, followed by either Generic Document WhatsApp
Foundation or Compound Document Communication Workflows according to project
priority.
