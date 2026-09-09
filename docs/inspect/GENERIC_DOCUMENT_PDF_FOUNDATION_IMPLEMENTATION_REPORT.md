# Generic Document PDF Foundation — Implementation Report

## 1. Final Status

PARTIAL

The generic capability, profile registration, typed contract, permission
guards, native Frappe print path, embedded MCP blob result, documentation, and
static regression suite are implemented and passing. A live ERPNext site render
and LibreChat artifact presentation were not run in this task, so an end-to-end
PASS is not claimed.

## 2. Source Inspected

### `mcp_erpnext`

- `mcp_erpnext/mcp_server.py`
- `mcp_erpnext/runtime.py`
- `mcp_erpnext/settings.py`
- `mcp_erpnext/observability.py`
- `mcp_erpnext/tools/__init__.py`
- `mcp_erpnext/tools/pdf.py`
- `mcp_erpnext/tools/read.py`
- `mcp_erpnext/profiles/sales.py`
- `mcp_erpnext/profiles/purchase.py`
- `mcp_erpnext/services/common/pdf.py`
- `mcp_erpnext/services/common/read.py`
- `mcp_erpnext/contracts/common.py`
- `mcp_erpnext/contracts/pdf.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/audit.py`
- `mcp_erpnext/tests/test_pdf.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `mcp_erpnext/tests/test_tool_contracts.py`
- `scripts/generate_tool_catalog.py`
- `docs/TOOLS.md`
- `docs/COMMANDS.md`
- `docs/architecture/MCP_DOCUMENT_PDF.md`

The app worktree contained pre-existing uncommitted PDF-related changes. They
were preserved and audited in place.

### Frappe v16

The local Frappe checkout is branch `version-16`, version `16.33.1`.

- `apps/frappe/frappe/utils/print_utils.py`
- `apps/frappe/frappe/www/printview.py`
- `apps/frappe/frappe/utils/pdf.py`
- `apps/frappe/frappe/utils/pdf_generator/browser.py`
- `apps/frappe/frappe/translate.py`
- `apps/frappe/frappe/model/document.py`
- `apps/frappe/frappe/permissions.py`
- `apps/frappe/frappe/website/serve.py`
- `apps/frappe/frappe/printing/doctype/print_format/print_format.py`
- `apps/frappe/frappe/printing/doctype/print_format/print_format.json`
- `apps/frappe/frappe/printing/doctype/letter_head/letter_head.py`
- `apps/frappe/frappe/printing/doctype/letter_head/letter_head.json`
- `apps/frappe/frappe/printing/doctype/print_settings/print_settings.py`
- `apps/frappe/frappe/printing/doctype/print_settings/print_settings.json`

## 3. Files Changed

Implementation-related files changed in the app worktree are:

- `docs/TOOLS.md`
- `docs/architecture/MCP_DOCUMENT_PDF.md`
- `docs/inspect/GENERIC_DOCUMENT_PDF_FOUNDATION_IMPLEMENTATION_REPORT.md`
- `mcp_erpnext/contracts/pdf.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/purchase.py`
- `mcp_erpnext/profiles/sales.py`
- `mcp_erpnext/services/common/pdf.py`
- `mcp_erpnext/tests/test_pdf.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `mcp_erpnext/tools/pdf.py`
- `scripts/generate_tool_catalog.py`

The task files `docs/tasks/16_GENERIC_DOCUMENT_PDF_FOUNDATION_TASK.md` and
`docs/tasks/17_TASK_GENERIC_DOCUMENT_PDF_FOUNDATION.md` were already present as
uncommitted work and were not edited.

## 4. Final MCP Tool Contract

The single public tool is registered as `render_document_pdf` in both profiles.
There are no DocType-specific PDF tools.

Public input schema:

```json
{
  "doctype": "Quotation | Sales Order | Purchase Order",
  "name": "non-empty string",
  "print_format": "optional non-empty string or null",
  "letterhead": "optional non-empty string or null",
  "language": "optional non-empty string or null"
}
```

`ctx` is an injected MCP context parameter and is not public input. The
structured output is `RenderDocumentPdfOutput` with these terminal states:

- `ok`: `doctype`, `name`, `print_format_used`, `filename`,
  `mime_type="application/pdf"`, `artifact_uri`, and `size_bytes`.
- `not_found`: the requested exact document was not found.
- `error`: the existing typed error envelope with `code`, `message`,
  `reference`, and `retryable`.

The installed MCP SDK exposes the output schema through `tools/list`; the
observed schema is an object with a discriminator on `status`.

## 5. Frappe-Native APIs Used

- `frappe.get_doc(doctype, name)` loads the exact existing transaction.
- `frappe.get_meta(doctype).default_print_format` reads the configured
  DocType default.
- `frappe.get_print(..., as_pdf=True, doc=doc, letterhead=letterhead)` is the
  PDF entry point used by the service.
- `frappe.translate.print_language(language)` scopes an optional language
  override.
- `frappe.www.printview.get_print_format_doc()` resolves a selected/default
  Print Format and performs Frappe's native Standard/missing-format fallback.
- `frappe.www.printview.get_rendered_template()` applies Print Settings and
  calls `get_letter_head()`.
- `frappe.www.printview.get_letter_head()` resolves the document Letter Head
  or the default Letter Head.
- `frappe.utils.pdf.get_pdf()` converts the native print HTML to in-memory PDF
  bytes and reads the native Print Settings page size.
- `Document.has_permission()` delegates to Frappe's normal permission system.

These APIs preserve installed ERPNext/Frappe print formats, Jinja templates,
Print Settings, Letter Heads, PDF generator hooks, and print lifecycle behavior
without accepting model-supplied HTML, CSS, Jinja, or JavaScript.

## 6. Print Format Resolution

Observed in the installed Frappe v16 source:

1. An explicit non-empty `print_format` is validated by the MCP service for
   existence, `print_format_for == "DocType"`, matching `doc_type`, and
   `disabled == false`; it is then passed to `frappe.get_print`.
2. With no explicit format, the MCP service reports
   `frappe.get_meta(doctype).default_print_format` when it exists.
3. Frappe `printview.get_print_format_doc()` independently resolves
   `frappe.form_dict.format or meta.default_print_format or "Standard"`.
4. `Standard` uses Frappe's standard print template.
5. If a configured non-Standard format no longer exists, Frappe catches
   `DoesNotExistError` and uses the Standard template; the MCP service reports
   `Standard` to match that observed native behavior.

The MCP service does not replace native template rendering or Print Settings.

## 7. Profile Policy

The server-side policy reuses the existing supported-document allowlist in
`mcp_erpnext/services/common/read.py`:

```text
sales:
- Quotation
- Sales Order

purchase:
- Purchase Order
```

The service rejects unsupported and cross-profile requests with
`DOCTYPE_NOT_ALLOWED` before loading the document.

## 8. Permission Behavior

`execute_tool_with_context()` preserves the existing authenticated Frappe
runtime. HTTP requests resolve the user from the authenticated MCP identity;
stdio uses its configured service user under the existing runtime rules.

After loading the exact document, the service requires both:

- `doc.has_permission("read")`
- `doc.has_permission("print")`

The native `printview` path performs its own print validation and can also
reject draft/cancelled documents according to native Print Settings. The MCP
service does not switch to Administrator, use a service-user fallback for HTTP,
set `ignore_permissions`, or set Frappe's `ignore_print_permissions` flag.

## 9. PDF Artifact Behavior

On success, the service returns PDF bytes in a private `_pdf` field to its MCP
wrapper. The wrapper removes that private field from structured metadata and
returns the bytes as an embedded MCP `BlobResourceContents` resource:

- URI: `artifact://mcp-erpnext/document-pdf/<quoted-doctype>/<quoted-name>`
- MIME type: `application/pdf`
- Blob encoding: base64, as required by the installed MCP type
- Filename metadata: `<document-name-with-spaces-and-slashes-scrubbed>.pdf`
- Structured metadata: includes `artifact_uri`, `filename`, and `size_bytes`

The PDF is ephemeral and held in the MCP response. No temporary PDF file and
no Frappe `File` document is created by this capability.

## 10. Runtime Test Matrix

The following are the actual observed static results. No live site render was
run, so rows requiring a real database, native PDF binary, or permissions are
explicitly not marked as runtime passes.

| Test | Expected | Observed | Result |
| --- | --- | --- | --- |
| Sales Order default PDF | valid PDF | FakeFrappe service test passed; configured default reported and native call requested | STATIC PASS; RUNTIME NOT RUN |
| Quotation default PDF | valid PDF | Sales-profile allowlist and service path test passed | STATIC PASS; RUNTIME NOT RUN |
| Purchase Order default PDF | valid PDF | Purchase-profile allowlist and service path test passed | STATIC PASS; RUNTIME NOT RUN |
| Explicit valid Print Format | works | Matching enabled DocType format was accepted and passed to `frappe.get_print` | STATIC PASS; RUNTIME NOT RUN |
| Invalid Print Format | rejected | Missing, disabled, report, and wrong-DocType formats are rejected by service tests | STATIC PASS; RUNTIME NOT RUN |
| Cross-profile DocType | rejected | Sales-to-Purchase and unsupported DocTypes return `DOCTYPE_NOT_ALLOWED` before lookup | STATIC PASS; RUNTIME NOT RUN |
| Missing document | not found | Fake missing document returns `status=not_found` | STATIC PASS; RUNTIME NOT RUN |
| No read permission | denied | Service test returns `PERMISSION_DENIED` | STATIC PASS; RUNTIME NOT RUN |
| No print permission | denied | Service test returns `PERMISSION_DENIED` | STATIC PASS; RUNTIME NOT RUN |
| Letter Head/default behavior | Frappe-native | Optional Letter Head is forwarded unchanged; native printview source was inspected for document/default resolution | STATIC PASS; RUNTIME NOT RUN |
| `application/pdf` artifact | valid MCP artifact | Installed MCP schema inspected; fake PDF bytes were base64-decoded from embedded `BlobResourceContents` | STATIC PASS; REAL PDF NOT RUN |

## 11. End-to-End MCP / LibreChat Verification

The following prompts were not executed against a live MCP server:

- `Give me the PDF of Sales Order SAL-ORD-XXXX.` — NOT VERIFIED; no sales
  profile server request was run.
- `Give me the PDF of Quotation QTN-XXXX.` — NOT VERIFIED; no sales profile
  server request was run.
- `Give me the PDF of Purchase Order PUR-ORD-XXXX.` — NOT VERIFIED; no
  purchase profile server request was run.

The profile registrations were verified statically and through `create_mcp()`
`tools/list` for both Sales and Purchase. Independent process startup was not
run.

NOT VERIFIED IN LIBRECHAT

## 12. Regression Results

Command executed:

```bash
../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
```

Observed result: `Ran 152 tests ... OK`.

The passing suite includes tests for sales tools, purchase tools, Sales Order
read/query/analytics, prepare/confirm workflows, approval behavior,
`mcp_identity`/HTTP identity, runtime handling, profile registration, and
contract audits. `scripts/generate_tool_catalog.py --check` also passed, and
the live in-process `tools/list` inspection showed the expected typed PDF input
and output schema for the registered capability.

Independent long-running Sales and Purchase server startup was not run.

## 13. Important Findings

- Frappe v16 `printview.validate_print_permission()` allows either document
  read or print permission by itself. The MCP service intentionally requires
  both, matching this task's stronger requirement.
- Frappe's native `get_print_format_doc()` falls back to Standard when a
  configured format is missing. The MCP metadata follows that behavior.
- The installed MCP SDK supports embedded binary resources through
  `BlobResourceContents`; its blob field is base64 text and its URI accepts the
  `artifact://` URI used here.
- LibreChat artifact presentation was not available for verification in this
  task.
- A live native print call was not run because it requires a real site/document
  and Frappe's printview also records a native print access log.

## 14. Remaining Limitations

- A live ERPNext render using existing Sales Order, Quotation, and Purchase
  Order records remains unverified.
- Actual installed-site Print Format, Letter Head, Print Settings, and PDF
  generator output remain unverified at runtime.
- LibreChat display/download behavior for the embedded PDF remains unverified.
- Independent process startup for both configured profiles remains unverified
  in this task.

## 15. Safety Confirmation

- No real secrets were added.
- No business documents were created for PDF testing.
- No permission bypass was introduced.
- No existing approval behavior was changed.
- No Frappe `File` document was persisted by the PDF capability.

## 16. Exact Next Task

After live PDF and client verification, the exact next task is:

```text
Generic Document Email Foundation

prepare_document_email
-> preview
-> trusted approval
-> confirm_document_email
```

That implementation must reuse `mcp_erpnext/services/common/pdf.py` rather than
creating a second PDF rendering path.
