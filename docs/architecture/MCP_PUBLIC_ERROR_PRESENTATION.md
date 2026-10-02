# MCP Public Error Presentation

Status: ER-01 complete; ER-02 complete; ER-03 pending; ER-04 pending; ER-05 pending.

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
| `mcp_erpnext/services/selling/`: `sales_order.py`, `sales_order_read.py`, `sales_invoice.py`, `sales_invoice_read.py`, `quotation.py`, `quotation_read.py`, `delivery_note_read.py`, `terms.py`, `payment_terms.py`, `sales_order_to_delivery_note.py`, `sales_order_to_sales_invoice.py`, `sales_invoice_to_delivery_note.py`, `quotation_to_sales_order.py`, `delivery_note_to_sales_invoice.py` | Service-local `_error` helpers, inline business messages, forwarded lifecycle/policy codes, and conversion/read errors. Codes span invalid input, not found, permissions, business-state blocks, stale confirmation, native validation, conversion, and payment/terms failures. | `sales_invoice.py` inspects `str(error)` to classify native validation; it does not directly return that string in the inspected path. Local messages can still expose technical validation details and require review. | `MIGRATE_BUSINESS_DOMAINS` |
| `mcp_erpnext/services/buying/`: `purchase_order.py`, `purchase_order_read.py`, `purchase_order_to_purchase_receipt.py`, `purchase_receipt_read.py`, `commercial_terms.py` | Local error constructors plus `public_error` and policy/lifecycle failure forwarding. Codes cover invalid fields/details, permissions, missing/ineligible source, conversion, stale confirmation, and template/default validation. | Inline messages are mostly business-oriented; configuration/default and capability wording needs normalization. | `MIGRATE_BUSINESS_DOMAINS` |
| `mcp_erpnext/services/accounts/`: `customer_payment_entry.py`, `customer_payment_reconciliation.py`, `multi_invoice_customer_receipt.py`, `payment_entry_read.py`, `sales_invoice_payment.py`, `sales_order_advance_payment.py` | Local `_error` helpers and native/Frappe failure conversion. Codes cover permission, input/allocation validation, not-found/state, approval/stale, reconciliation, payment creation and native validation. | Business semantics are generally retained, but all native validation and operational messages need safe-message review; do not collapse payment-state distinctions. | `MIGRATE_BUSINESS_DOMAINS` |
| `mcp_erpnext/services/masters/`: `contact.py`, `contact_update.py`, `customer.py`, `customer_contact.py`, `customer_primary_contact.py`, `customer_read.py`, `item.py`, `item_read.py`, `supplier_read.py` | Local `_error` helpers, direct error maps, and shared public error helpers. Codes cover permission, invalid input/identity, duplicates/ambiguity, link/scope, primary-contact consistency, not-found, and stale state. | Contact relationship boundaries and native save semantics must be preserved while messages are centralized. | `ER-04 / MIGRATE_REMAINING_DOMAINS` |
| `mcp_erpnext/services/shayona/`: `credential_email.py`, `credentials.py`, `tea_entries.py` | Credential/email and Tea Entry domain errors; typed exceptions are converted to public codes/messages at tool/service boundaries. Codes include capability/schema unavailable, permission, validation, email/configuration, and stale confirmation. | `credential_email.py` uses a service-local message catalog; exception causes are wrapped, while raw cause text is not the intended public response. Verify every catch boundary during migration. | `MIGRATE_REMAINING_DOMAINS` |
| `mcp_erpnext/services/buying/terms.py`, `mcp_erpnext/services/masters/selection.py`, `mcp_erpnext/services/masters/supplier.py`, `mcp_erpnext/services/integrations/india_compliance_customer.py`, `mcp_erpnext/services/integrations/india_compliance_item.py`, `mcp_erpnext/services/sales_order_service.py`, `mcp_erpnext/services/common/aggregate.py`, `mcp_erpnext/services/common/creation_contract.py`, `mcp_erpnext/services/common/entity_resolution.py`, `mcp_erpnext/services/common/effective_requirements.py`, `mcp_erpnext/services/common/field_value_resolver.py`, `mcp_erpnext/services/common/fingerprint.py`, `mcp_erpnext/services/common/terms_resolution.py` | Shared operations/resolvers either raise typed/domain errors or return failures consumed by producer rows above; no independent standard error-envelope builder was found in these files during the producer-pattern scan. | Confirm their callers when each owning domain is migrated; preserve resolver states (`ambiguous`, `not_found`, `error`) and typed distinctions. | `VERIFY_ONLY` |
| `mcp_erpnext/approvals.py`, `mcp_erpnext/services/common/write_policy.py` | Approval storage and write policy raise typed operational errors or return `PolicyFailure(code, message)`; central definitions own the public wording. | Policy and approval semantics remain fail-closed; public messages no longer reveal server-policy/session wording. | `ER-02_COMPLETE` |
| `mcp_erpnext/contracts/accounts/`: `customer_payment_entry.py`, `customer_payment_reconciliation.py`, `multi_invoice_customer_receipt.py`, `payment_entry_read.py`, `sales_invoice_payment.py`, `sales_order_advance_payment.py`; `mcp_erpnext/contracts/buying/`: `purchase_order.py`, `purchase_order_read.py`, `purchase_receipt.py`, `purchase_receipt_read.py`; `mcp_erpnext/contracts/masters/`: `contact.py`, `customer.py`, `customer_read.py`, `item.py`, `item_read.py`, `resolution.py`, `supplier_read.py`; `mcp_erpnext/contracts/selling/`: `delivery_note.py`, `delivery_note_read.py`, `delivery_note_to_sales_invoice.py`, `payment_terms.py`, `quotation.py`, `quotation_read.py`, `quotation_to_sales_order.py`, `sales_invoice.py`, `sales_invoice_read.py`, `sales_invoice_to_delivery_note.py`, `sales_order.py`, `sales_order_read.py`, `sales_order_to_sales_invoice.py`, `terms.py`; `mcp_erpnext/contracts/shayona/`: `credential_email.py`, `credentials.py`, `tea_entries.py`; and `mcp_erpnext/contracts/`: `common.py`, `email.py`, `pdf.py`, `read.py` | These schema consumers use the shared `ToolError` from `contracts/common.py`; there are also tool-specific error state models (for example Sales Order states). No contract field additions are made. | Contract/schema surface is the five-field envelope plus existing typed state unions. Keep client compatibility and review any bespoke error model alongside its tool. | `FOUNDATION_ONLY` |
| `mcp_erpnext/tools/**`, `mcp_erpnext/remote_operations.py`, `mcp_erpnext/runtime.py` | Tool wrappers route service results and exceptions through declared output unions and `execute_tool`; remote operations normalize REST service results. | No separate competing envelope registry found. Verify each wrapper preserves the same shape and code/message semantics for Direct and REST. | `VERIFY_ONLY` |

The service-local code inventory is discoverable at each row's listed source
paths. Common stable code groups include `*_DISABLED`, `APPROVAL_REQUIRED`,
`DIRECT_EXECUTION_REQUIRED`, `PERMISSION_DENIED`/`ERP_PERMISSION_DENIED`,
`*_NOT_FOUND`, `INVALID_*`, `*_UNAVAILABLE`, `*_FAILED`, and
`STALE_CONFIRMATION`; literal codes are intentionally not duplicated into a
second registry until their owning migration registers safe definitions.

### Explicit exposure findings

- **Raw exception text returned publicly: no** in the migrated
  `services/common/lifecycle.py` paths. Native validation and linked-document
  failures now return central messages and log with a correlation reference.
  `services/selling/sales_invoice.py` still reads `str(error)` only to classify
  a native prerequisite failure, then returns a bounded business result.
- **Technical wording returned publicly: no** in migrated lifecycle/write-policy
  paths. **Potentially yes** in local
  service messages that describe native failures, configuration, or backend
  availability; these remain assigned to their listed migration phases and
  are not declared safe merely because they are not raw tracebacks. The
  centralized fallback and registered definitions contain bounded messages.
- **Semantic category coverage:** current local codes are grouped by invalid
  input, permission, not found, ambiguous/duplicate selection, business-state
  block, approval/interaction, stale state, configuration/capability, temporary
  operation, and unexpected failure. The literal code values remain in their
  owning service paths until their migration phase; no cosmetic renaming is
  part of the inventory task.

## Residual risks and migration map

- ER-02 removes the previously confirmed lifecycle exception-text exposure for
  `LIFECYCLE_VALIDATION_FAILED` and `LINKED_DOCUMENT`. Remaining raw-exception
  checks belong to ER-03 through ER-05.
- Service-local `_error` helpers and direct dictionaries remain throughout the
  inventory. The legacy `message=` override also remains for compatibility.
- Write-policy public wording now comes from the catalog while the policy
  module retains write-mode authorization semantics.
- A disabled capability and a permission denial are distinct. Keep their codes,
  categories, and user explanations distinct during later migration.
- Direct and REST must continue to return the same public envelope. No
  backend-specific error semantics or client-detection branches are permitted.
- Native framework messages can contain document, configuration, or internal
  details. Migrations should map known cases to safe messages and log only
  bounded operational context with the existing correlation reference.

| Phase | Ownership |
| --- | --- |
| ER-01 | Foundation, shared instructions, inventory, compatibility tests. |
| ER-02 | Core/security/common and write-policy/lifecycle producers. |
| ER-03 | Sales, Buying, Accounts business-domain producers (pending). |
| ER-04 | Masters, Shayona, integrations, and remaining domain producers (pending). |
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
