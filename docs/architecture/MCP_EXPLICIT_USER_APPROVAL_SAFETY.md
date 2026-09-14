# MCP Explicit User Approval Safety

## Server-selected approval policy

`MCP_APPROVAL_MODE` is a validated server setting and is never exposed as an
MCP tool argument. It has two modes:

- `agent_delegated` is the default. It trusts the authenticated MCP
  Agent/client as the user's delegated conversational orchestrator. The
  Agent/client must call
  `confirm_*` only after the user explicitly approves the exact prepared
  preview. The MCP server does not parse natural-language approval.
- `trusted_human` is the stronger provenance policy and applies only when
  `MCP_APPROVAL_MODE=trusted_human` is configured explicitly. An independently
  verified human decision must be recorded through the internal approval seam
  before `confirm_*`; otherwise the server returns
  `TRUSTED_APPROVAL_UNAVAILABLE`.

The modes are not equally strong: `trusted_human` independently verifies human
origin, while `agent_delegated` relies on the authenticated Agent/client to
enforce that conversational step. No LibreChat, Codex, or other client-specific
source change is required for a compatible client to use delegated mode.

## Shared pending-operation guard

`mcp_erpnext.approvals.ApprovalStore` creates a short-lived pending operation
at prepare time. The opaque handle is bound to the server-side action, Frappe
site, authenticated Frappe user, and SHA-256 digest of the prepared payload. The
raw prepared document is never accepted from a confirm tool.

`claim_for_confirm_write()` centrally revalidates each binding and atomically
consumes a policy-compliant operation before calling domain persistence. In
`trusted_human` mode it additionally requires the trusted approval record; in
`agent_delegated` mode that is the only policy difference. Reuse, cross-user or
cross-tool replay, payload mutation, cancellation, and expiry are rejected in
both modes. Frappe create permissions are checked again immediately before every
insert.

The internal `record_trusted_user_approval()` seam is deliberately not exposed
as an MCP tool or a public argument. A transport adapter may call it only after
independently verifying a human-originated decision and binding it to the same
operation. It remains mandatory in `trusted_human` mode and is optional in
`agent_delegated` mode.

## Deployment boundary

The approval store uses Frappe's configured Redis cache and its site/database
namespace. Restarted or separate MCP workers can use the same still-valid
approval, while the explicit stored site, user, action, payload, trust, and
single-use checks remain the authorization boundary. Redis is ephemeral:
expiry, eviction, flush, or Redis restart requires a fresh prepare.

For a stricter deployment, set `MCP_APPROVAL_MODE=trusted_human` explicitly and
provide a transport adapter that independently verifies a payload-bound human
decision. The default `agent_delegated` mode keeps explicit approval
interpretation in the Agent/client, outside MCP.
