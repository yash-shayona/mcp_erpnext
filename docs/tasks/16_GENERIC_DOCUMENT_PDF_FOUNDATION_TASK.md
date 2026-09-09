# TASK — Generic Document PDF Foundation

## Status
NEXT IMPLEMENTATION TASK

## Goal
Add one reusable, permission-safe **generic PDF rendering capability** to the existing `mcp_erpnext` app.

This is **not Sales Order-specific**. The same implementation must be reusable for supported transactional DocTypes such as Quotation, Sales Order, and Purchase Order, while still enforcing the active MCP profile's allowed DocTypes.

Email is **not** part of this task. First make PDF generation correct and verify it independently. Email will reuse this foundation in the next task.

---

# 1. Architecture Decision

Implement one shared public capability:

```text
render_document_pdf
```

Conceptual flow:

```text
Agent
  |
  | doctype + name + optional print_format
  v
render_document_pdf
  |
  +--> active MCP profile DocType allowlist
  +--> current Frappe user read/print permission
  +--> resolve Print Format
  +--> Frappe-native Letter Head / print settings
  +--> Frappe-native PDF generation
  v
PDF artifact/result
```

Do not create one PDF tool per DocType.

---

# 2. Mandatory Source Inspection

Inspect the actual current source first.

At minimum inspect:
- current `mcp_server.py`
- profile/tool registration
- contracts
- services
- runtime/Frappe user context
- permission helpers
- tests
- current tool docs
- sales profile
- purchase profile

Also inspect the installed Frappe v16 implementation for:
- `frappe.get_print`
- `frappe.utils.print_format`
- `frappe.utils.pdf`
- Print Format
- Letter Head
- Print Settings
- Print permission behavior

Prefer Frappe-native PDF generation. Do not build a separate HTML-to-PDF system inside `mcp_erpnext`.

---

# 3. Public Tool Contract

Recommended:

```text
render_document_pdf
```

Conceptual input:

```text
doctype: string
name: string
print_format?: string
letterhead?: string
language?: string
```

Adapt exact field names only to match existing project conventions.

Do not accept arbitrary HTML/CSS/Jinja from the model.

---

# 4. Default Print Format Behavior

Normal requests must NOT require the user to supply HTML/CSS/JS.

When `print_format` is omitted, use Frappe's configured print behavior:

```text
explicit requested Print Format
        ↓ otherwise
DocType/configured default Print Format
        ↓ otherwise
Standard
```

Example:

```text
User:
"SO-14 ka PDF banao."

MCP:
render_document_pdf(
  doctype="Sales Order",
  name="SO-14"
)
```

The user must not be asked for HTML, CSS, logo, page size, or other layout details when ERPNext is already configured.

---

# 5. Explicit Print Format

Allow explicit `print_format` only when:
- it exists,
- it is valid for the requested DocType,
- the active profile permits the DocType,
- current Frappe permissions allow access/printing.

Example:

```text
render_document_pdf(
  doctype="Sales Order",
  name="SO-14",
  print_format="Shayona Sales Order - Without Price"
)
```

Invalid or cross-DocType formats must fail clearly.

---

# 6. Profile-Level DocType Allowlist

Generic must not mean unrestricted.

Conceptually:

```text
sales profile:
  allowed PDF DocTypes:
    - Quotation
    - Sales Order

purchase profile:
  allowed PDF DocTypes:
    - Purchase Order
```

Use actual current supported profile scope as source of truth.

Cross-profile calls must fail server-side, not only by agent instruction.

---

# 7. Frappe Permission Rules

Run under the existing authenticated Frappe user context.

Verify native:
- read permission
- print permission

Never:
- switch to Administrator
- ignore permissions
- use a service-user fallback

---

# 8. Letter Head / Company Standard

Do not duplicate Letter Head HTML inside MCP.

Use Frappe-native resolution for document/default Letter Head wherever possible.

Normal requests should not require the user to specify a Letter Head.

---

# 9. Return Contract

Inspect the current MCP SDK/client behavior and return the PDF in the most idiomatic supported artifact/resource/blob form.

Return enough metadata to identify it, conceptually:

```text
doctype
name
print_format_used
filename
mime_type = application/pdf
artifact/resource/content reference
```

Do not dump raw base64 into conversational text unless the current MCP stack truly requires it.

Prefer ephemeral PDF output for this task.

Do not persist a Frappe `File` unless the source architecture genuinely requires persistence and the completion report explains why.

---

# 10. No Approval Workflow for PDF Rendering

PDF rendering is a read/output operation.

Do not add `prepare_pdf` / `confirm_pdf` unless current source has a concrete reason.

Do not implement email in this task.

Do not create persistent attachments merely to make email easier later.

The later email service should reuse this PDF renderer internally.

---

# 11. Agent Behavior

Expected:

```text
User:
"SO-14 ka PDF do."

Agent:
resolve exact document if needed
-> render_document_pdf
-> present returned artifact
```

If user requests a special format, pass the explicit validated Print Format.

Do not ask for a Print Format when no special format was requested.

---

# 12. Tests

Positive:
1. sales profile -> Sales Order -> default format
2. sales profile -> Quotation -> default format
3. purchase profile -> Purchase Order -> default format
4. explicit valid Print Format
5. Letter Head/default behavior
6. valid `application/pdf` artifact

Use existing test documents only.

Negative:
1. nonexistent document
2. unsupported DocType
3. cross-profile DocType
4. invalid Print Format
5. Print Format for wrong DocType
6. no read permission
7. no print permission

---

# 13. Regression Requirements

Do not change:
- existing sales tools
- existing purchase tools
- Sales Order read/query/analytics tools
- prepare/confirm write behavior
- approval behavior
- `mcp_identity`
- LibreChat transport behavior

Both sales and purchase MCP servers must continue to start independently on their configured profile/port.

---

# 14. Documentation

Update current MCP tool docs with:
- `render_document_pdf`
- supported profiles
- supported DocTypes
- default Print Format behavior
- explicit Print Format behavior
- permission behavior
- artifact return behavior
- examples
- negative cases

---

# 15. Acceptance Criteria

```text
[ ] current mcp_erpnext source inspected
[ ] installed Frappe v16 print/PDF source inspected
[ ] Frappe-native PDF rendering reused
[ ] one generic public PDF capability exists
[ ] no DocType-specific duplicate PDF tools
[ ] profile DocType allowlist enforced server-side
[ ] authenticated Frappe user context preserved
[ ] read/print permission enforced
[ ] default Print Format works without user input
[ ] explicit valid Print Format works
[ ] invalid/cross-DocType Print Format rejected
[ ] Letter Head uses Frappe-native behavior
[ ] valid PDF artifact returned
[ ] no business document created
[ ] no unnecessary Frappe File persisted
[ ] existing sales/purchase/write/approval tests pass
[ ] docs updated
```

---

# 16. Manual End-to-End Prompts

Sales Agent:

```text
Give me the PDF of Sales Order SAL-ORD-XXXX.
Give me the PDF of Quotation QTN-XXXX.
```

Purchase Agent:

```text
Give me the PDF of Purchase Order PUR-ORD-XXXX.
```

Cross-profile negative:

```text
Ask the Sales Agent to render a Purchase Order PDF.
```

Expected: the sales profile must not render the Purchase Order.

---

# 17. Completion Report

Return:
- exact source paths inspected
- exact Frappe-native APIs used
- exact public tool schema
- exact allowed DocTypes per profile
- exact Print Format fallback behavior observed in installed version
- artifact return mechanism
- PASS/FAIL test matrix
- regression confirmation

## Exact Next Task

After this passes:

```text
Generic Document Email Foundation:
prepare_document_email -> trusted approval -> confirm_document_email,
reusing the generic PDF service.
```
