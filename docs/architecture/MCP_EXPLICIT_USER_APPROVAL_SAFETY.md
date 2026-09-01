# MCP Explicit User Approval Safety

## Server-selected approval policy

`MCP_APPROVAL_MODE` is a validated server setting and is never exposed as an
MCP tool argument. It has two modes:

- `trusted_human` is the default and the stronger provenance policy. An
  independently verified human decision must be recorded through the internal
  approval seam before `confirm_*`; otherwise the server returns
  `TRUSTED_APPROVAL_UNAVAILABLE`.
- `agent_delegated` trusts the authenticated MCP Agent/client as the user's
  delegated conversational orchestrator. The Agent/client must call
  `confirm_*` only after the user explicitly approves the exact prepared
  preview. The MCP server does not parse natural-language approval.

The modes are not equally strong: `trusted_human` independently verifies human
origin, while `agent_delegated` relies on the authenticated Agent/client to
enforce that conversational step. No LibreChat, Codex, or other client-specific
source change is required for a compatible client to use delegated mode.

## Shared pending-operation guard

`mcp_erpnext.approvals.ApprovalStore` creates a short-lived pending operation
at prepare time. The opaque handle is bound to the server-side action, Frappe
site, authenticated Frappe user, and HMAC digest of the prepared payload. The
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

The approval store is process-local and protected with a process-local lock.
Restart loses pending operations and multiple workers do not share them. This
task intentionally does not migrate it to Redis or Frappe DB; durable shared
storage remains a future deployment/scaling concern.

For a stricter deployment, retain `trusted_human` and provide a transport
adapter that independently verifies a payload-bound human decision. For the
current local chat-development flow, set `MCP_APPROVAL_MODE=agent_delegated` and
keep explicit approval interpretation in the Agent/client, outside MCP.
