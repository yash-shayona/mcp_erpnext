# Generic Document PDF Capability

`render_document_pdf` is one read-only MCP capability shared by the configured
Sales and Purchase profiles. It renders an exact existing transaction through
the authenticated Frappe user.

## Profile boundary

| Profile | Allowed DocTypes |
| --- | --- |
| Sales | `Quotation`, `Sales Order` |
| Purchase | `Purchase Order` |

The service rejects unsupported and cross-profile DocTypes server-side with
`DOCTYPE_NOT_ALLOWED`.

## Input

```json
{
  "doctype": "Sales Order",
  "name": "SAL-ORD-XXXX",
  "print_format": "Optional validated Print Format",
  "letterhead": "Optional Frappe Letter Head name",
  "language": "Optional language code"
}
```

`print_format`, `letterhead`, and `language` are optional. When no format is
provided, Frappe's installed v16 printview resolves the DocType's configured
default and otherwise `Standard`. A stale configured default follows Frappe's
native missing-format fallback to `Standard`. An explicit format must exist,
be enabled, and belong to the requested DocType; invalid or cross-DocType
formats return `INVALID_PRINT_FORMAT`.

Frappe's native Print Settings and Letter Head resolution are retained. The
MCP layer does not accept HTML, CSS, Jinja, or JavaScript and does not duplicate
Letter Head content.

## Permissions and result

The service loads the exact document and requires both its current Frappe
`read` and `print` permissions. It never switches to Administrator, ignores
permissions, or creates a business document.

On success, the structured result identifies the DocType, document, selected
format, filename, `application/pdf` MIME type, ephemeral artifact URI, and byte
length. The PDF bytes are returned as an MCP embedded
`BlobResourceContents` resource. No Frappe `File` is persisted.

```text
status: ok
content[0]: embedded resource, mimeType=application/pdf, base64 blob
structuredContent: document and artifact metadata
```

Missing documents return `not_found`; profile, format, and permission failures
return the normal typed error envelope. PDF rendering has no approval workflow
and this capability does not send email.

## Examples

```text
Sales profile: render_document_pdf(doctype="Sales Order", name="SAL-ORD-XXXX")
Sales profile: render_document_pdf(doctype="Quotation", name="QTN-XXXX")
Purchase profile: render_document_pdf(doctype="Purchase Order", name="PUR-ORD-XXXX")
```
