# MCP Public Error Presentation

Status: ER-01 complete; ER-02 complete; ER-03 complete; ER-04 complete; ER-05 pending.

## Frozen public contract

The public `ToolError` remains the five-field object defined in
`mcp_erpnext/contracts/common.py`:

| Field | Owner and meaning |
| --- | --- |
| `status` | Discriminator; remains `error`. |
| `code` | Stable machine/agent semantic signal. Preserve existing codes. |
| `message` | Safe, concise explanation for the user. It is not a diagnostic channel. |
| `reference` | Correlation identifier for support and server logs. |
| `retryable` | Machine retry guidance. Do not infer a retry from wording. |

The server contract is the same for direct MCP clients, coordinators, Direct
backend, and REST backend. The client normally explains the failure in business
language and does not repeat codes or references. If a user asks for technical
troubleshooting, a code/reference may be shared when useful and safe. Technical
details remain in server logs. The base instructions are guidance, not a security
boundary; every public message must be safe on its own.

`public_errors.py` owns `ErrorCategory`, `PublicErrorDefinition`, and the
registered safe defaults. `defined_error()` is the preferred API for new
centralized callers: it accepts a code and optional reference/retry override,
but no message or exception text. An unknown code keeps its machine value and
uses the bounded `ERP_REQUEST_FAILED` presentation definition. The existing
`observability.public_error(..., message=...)` and
`logged_public_error(..., message=...)` remain compatible during migration;
their message override is a legacy path and must not be used by new centralized
callers. Logging and reference generation remain in `observability.py`.

## Semantic taxonomy

| Category | Meaning |
| --- | --- |
| `capability_unavailable` | The action is disabled or unavailable in this setup. |
| `permission_denied` | The authenticated user cannot access or perform the action. |
| `approval_required` | Review/approval is required before continuing. |
| `interaction_required` | A different supported interaction/execution path is required. |
| `invalid_request` | Input or request shape is invalid. |
| `not_found` | The requested entity or resource does not exist or is unavailable. |
| `ambiguous_selection` | More than one candidate requires user selection. |
| `business_rule_blocked` | The request conflicts with a business rule or document state. |
| `stale_state` | Prepared state changed; prepare/review again. |
| `configuration_unavailable` | Required site or integration configuration is unavailable/invalid. |
| `temporary_failure` | A transient operational failure may be retried. |
| `unexpected_failure` | Unclassified internal failure; expose no internal diagnostic. |

Capability restrictions must not be described as user permission failures.
Approval-required and stale-state errors must retain their distinct next steps.
Codes are compatibility anchors and are not renamed as part of categorization.

## Source inventory

Inventory was built by searching runtime Python for `_error`, direct error
dictionaries, `public_error`, `logged_public_error`, `new_error_reference`,
`frappe.throw`, exception conversion, `str(error)`/`str(exc)`, and `ToolError`
schema use. Source paths below are the complete current runtime producer set
found by that search. Repeated paths are grouped by responsibility; all files
in each row share the message and migration notes shown.

| Source paths | Current construction and code/message source | Exposure and semantic coverage | Migration |
| --- | --- | --- | --- |
| `mcp_erpnext/observability.py`, `mcp_erpnext/remote_api.py` | Central public/logged helpers; exception-to-code mapping; REST request/response validation. Codes include `ERP_PERMISSION_DENIED`, `ERP_REQUEST_FAILED`, `ORDER_CREATE_UNAVAILABLE`, `ORDER_PREVIEW_UNAVAILABLE`, MCP auth/identity codes and remote request/response invalid. Safe catalog messages, with internal failures logged and references correlated. | Generic fallback is bounded. Shared definitions now own REST wording and the same public code has the same presentation across backends. | `ER-02_COMPLETE` |
| `mcp_erpnext/services/common/`: `email.py`, `lifecycle.py`, `pdf.py`, `read.py` | Shared `defined_error()` construction for common errors; lifecycle logs correlated validation/link failures. Stable codes include write-policy, permission, stale, invalid/not-found, email/PDF, and lifecycle validation/link cases. | Public messages come from registered definitions; native exception text is retained only in server logs. | `ER-02_COMPLETE` |
| `mcp_erpnext/services/selling/`: `sales_order.py`, `sales_order_read.py`, `sales_invoice.py`, `sales_invoice_read.py`, `quotation.py`, `quotation_read.py`, `delivery_note_read.py`, `terms.py`, `payment_terms.py`, `sales_order_to_delivery_note.py`, `sales_order_to_sales_invoice.py`, `sales_invoice_to_delivery_note.py`, `quotation_to_sales_order.py`, `delivery_note_to_sales_invoice.py` | Domain error envelopes use catalog-owned `PublicErrorDefinition` messages through `defined_error(...)`; confirmation failures retain shared ApprovalStore codes and retryability. | `sales_invoice.py` still inspects `str(error)` only to classify the existing native prerequisite outcome; no native text is returned. This classification-only check remains for ER-05 review. | `ER-03_COMPLETE` |
| `mcp_erpnext/services/buying/`: `purchase_order.py`, `purchase_order_read.py`, `purchase_order_to_purchase_receipt.py`, `purchase_receipt_read.py`, `commercial_terms.py` | Domain error envelopes use catalog-owned messages; Purchase Receipt source, row, quantity, and warehouse distinctions remain separate. | Shared `needs_input` and other non-error response messages remain workflow guidance, not `ToolError` overrides. | `ER-03_COMPLETE` |
| `mcp_erpnext/services/accounts/`: `customer_payment_entry.py`, `customer_payment_reconciliation.py`, `multi_invoice_customer_receipt.py`, `payment_entry_read.py`, `sales_invoice_payment.py`, `sales_order_advance_payment.py` | Domain error envelopes use catalog-owned messages for payment creation, allocation, account/party/company compatibility, outstanding state, and reconciliation failures. | Accounting calculations, native validation, permissions, and transaction boundaries remain authoritative and unchanged. | `ER-03_COMPLETE` |
| `mcp_erpnext/services/masters/`: `contact.py`, `contact_update.py`, `customer.py`, `customer_contact.py`, `customer_primary_contact.py`, `customer_read.py`, `item.py`, `item_read.py`, `supplier_read.py` | Standard Master errors use `defined_error()` and central catalog messages. Stable codes cover permission, invalid input/identity, duplicates/ambiguity, link/scope, primary-contact consistency, not-found, and stale state. | Contact relationship boundaries, native save semantics, and permission checks remain owned by Frappe/ERPNext. | `ER-04_COMPLETE` |
| `mcp_erpnext/services/shayona/`: `credential_email.py`, `credentials.py`, `tea_entries.py` | Credential/email and Tea Entry errors use central `defined_error()` / `logged_defined_error()` definitions. | Credential secrets, recipient/template/email security, approval binding, Tea Entry rollback, and structured not-found/preview/ready states remain unchanged. Typed exceptions carry stable codes only. | `ER-04_COMPLETE` |
| `mcp_erpnext/services/buying/terms.py`, `mcp_erpnext/services/masters/selection.py`, `mcp_erpnext/services/masters/supplier.py`, `mcp_erpnext/services/integrations/india_compliance_customer.py`, `mcp_erpnext/services/integrations/india_compliance_item.py`, `mcp_erpnext/services/sales_order_service.py`, `mcp_erpnext/services/common/aggregate.py`, `mcp_erpnext/services/common/creation_contract.py`, `mcp_erpnext/services/common/entity_resolution.py`, `mcp_erpnext/services/common/effective_requirements.py`, `mcp_erpnext/services/common/field_value_resolver.py`, `mcp_erpnext/services/common/fingerprint.py`, `mcp_erpnext/services/common/terms_resolution.py` | Shared operations/resolvers either raise typed/domain errors or return failures consumed by producer rows above; Master-owned India Compliance codes are defined centrally. No independent standard error-envelope builder or raw public error forwarding was found in the inspected helper/integration paths. | Preserve resolver states (`ambiguous`, `not_found`, `error`) and typed distinctions; public presentation remains at the owning Master boundary. | `VERIFY_ONLY_COMPLETE` |
| `mcp_erpnext/approvals.py`, `mcp_erpnext/services/common/write_policy.py` | Approval storage and write policy raise typed operational errors or return `PolicyFailure(code, message)`; central definitions own the public wording. | Policy and approval semantics remain fail-closed; public messages no longer reveal server-policy/session wording. | `ER-02_COMPLETE` |
| `mcp_erpnext/contracts/accounts/`: `customer_payment_entry.py`, `customer_payment_reconciliation.py`, `multi_invoice_customer_receipt.py`, `payment_entry_read.py`, `sales_invoice_payment.py`, `sales_order_advance_payment.py`; `mcp_erpnext/contracts/buying/`: `purchase_order.py`, `purchase_order_read.py`, `purchase_receipt.py`, `purchase_receipt_read.py`; `mcp_erpnext/contracts/masters/`: `contact.py`, `customer.py`, `customer_read.py`, `item.py`, `item_read.py`, `resolution.py`, `supplier_read.py`; `mcp_erpnext/contracts/selling/`: `delivery_note.py`, `delivery_note_read.py`, `delivery_note_to_sales_invoice.py`, `payment_terms.py`, `quotation.py`, `quotation_read.py`, `quotation_to_sales_order.py`, `sales_invoice.py`, `sales_invoice_read.py`, `sales_invoice_to_delivery_note.py`, `sales_order.py`, `sales_order_read.py`, `sales_order_to_sales_invoice.py`, `terms.py`; `mcp_erpnext/contracts/shayona/`: `credential_email.py`, `credentials.py`, `tea_entries.py`; and `mcp_erpnext/contracts/`: `common.py`, `email.py`, `pdf.py`, `read.py` | These schema consumers use the shared `ToolError` from `contracts/common.py`; there are also tool-specific error state models (for example Sales Order states). No contract field additions are made. | Contract/schema surface is the five-field envelope plus existing typed state unions. Keep client compatibility and review any bespoke error model alongside its tool. | `FOUNDATION_ONLY` |
| `mcp_erpnext/tools/**`, `mcp_erpnext/remote_operations.py`, `mcp_erpnext/runtime.py` | Tool wrappers route service results and exceptions through declared output unions and `execute_tool`; remote operations normalize REST service results. | No separate competing envelope registry found. Verify each wrapper preserves the same shape and code/message semantics for Direct and REST. | `VERIFY_ONLY` |

The service-local code inventory is discoverable at each row's listed source
paths. All standard Master and Shayona error codes found in ER-04 resolve to an
explicit definition in `mcp_erpnext/public_errors.py`; no second registry owns
their public wording. The code families remain distinct for permission, invalid
input, not found, ambiguous selection, business-state blocks, approvals,
staleness, capability/configuration, and temporary failures.

### Explicit exposure findings

- **Raw exception text returned publicly: no** in the migrated
  `services/common/lifecycle.py` paths. Native validation and linked-document
  failures now return central messages and log with a correlation reference.
  `services/selling/sales_invoice.py` still reads `str(error)` only to classify
  a native prerequisite failure, then returns a bounded business result.
- **Technical wording returned publicly:** the ER-04 Master and Shayona standard
  error paths use central messages; their former inline wording and Credential
  Email message map are removed. ER-05 must independently scan the entire
  repository and compare Direct/REST behavior before overall closure.
- **Semantic category coverage:** stable codes remain grouped by invalid input,
  permission, not found, ambiguous/duplicate selection, business-state block,
  approval/interaction, stale state, configuration/capability, temporary
  operation, and unexpected failure. Codes were preserved during ER-04.

## Residual risks and migration map

- ER-02 removes the previously confirmed lifecycle exception-text exposure for
  `LIFECYCLE_VALIDATION_FAILED` and `LINKED_DOCUMENT`. Remaining raw-exception
  checks belong to ER-03 through ER-05.
- Thin service-local adapters may remain where they delegate to the catalog;
  they do not accept or own public message text. The legacy observability
  `message=` parameter remains only for compatibility outside migrated callers.
- Write-policy public wording comes from the catalog while the policy module
  retains write-mode authorization semantics. Capability restrictions and
  permission denials remain distinct.
- ER-05 must verify Direct/REST presentation parity and scan for remaining
  legacy message overrides and raw exception paths across the repository.

| Phase | Ownership |
| --- | --- |
| ER-01 | Foundation, shared instructions, inventory, compatibility tests. |
| ER-02 | Core/security/common and write-policy/lifecycle producers. |
| ER-03 | Sales, Buying, Accounts business-domain producers (complete). |
| ER-04 | Masters, Shayona, integrations, and remaining domain producers (complete). |
| ER-05 | Full-surface parity, raw-exception, and contract verification (pending). |

## ER-01 scope and version

ER-01 adds a typed catalog and preferred safe constructor, delegates the
existing observability fallback to that catalog, adds cross-profile presentation
guidance, and bumps the PATCH version from `3.2.0` to `3.2.1`. It does not
migrate service-local helpers, change write/approval/permission semantics, add
public fields, or implement the separate Email Approval / Email Action Security
workstream.

## ER-02 scope and version

ER-02 routes core/common errors through the central definitions, removes lifecycle
exception text from public responses, centralizes shared approval and write-policy
wording, and aligns REST errors with Direct execution. It preserves the five-field
ToolError envelope and existing authorization, approval, persistence, read, print,
and email behavior. The PATCH version is `4.0.1`. ER-03 covers Sales, Buying,
and Accounts; ER-04 covers Masters, Shayona, integrations, and remaining domains;
ER-05 verifies full-surface parity and residual raw-exception paths.

## ER-03 scope and version

ER-03 migrates Sales, Buying, and Accounts error envelopes to catalog-owned
messages while preserving the five-field `ToolError`, stable codes, approval
semantics, permission behavior, accounting/conversion rules, and structured
non-error states. The PATCH version is `4.0.2`.

## ER-04 scope and version

ER-04 migrates Master and Shayona standard error envelopes to catalog-owned
messages and verifies that India Compliance/helper paths do not independently
present standard errors. It preserves the five-field `ToolError`, stable codes,
permission and approval semantics, Contact relationship rules, credential
secrecy/email safeguards, Tea Entry transaction behavior, and structured
non-error states. The PATCH version is `4.0.5` after the `PROFILE_MISMATCH`
business-wording correction. ER-05 remains repository-wide
residual scanning, Direct/REST parity, and live Direct-MCP validation.
