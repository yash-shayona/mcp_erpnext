# MCP Explicit User Approval Safety

## Current deployment decision

The current LibreChat bridge is classified as **Strategy C — no trusted approval
channel is available**. Its `mcpServers.erpnext` configuration forwards an HTTP
bearer credential and LibreChat user identity to this MCP server, but no
server-verifiable per-tool human-approval decision. LibreChat v0.8.8-rc1 does
contain an agent-run Human-in-the-Loop (`endpoints.agents.toolApproval`) feature,
but it is not configured here and its UI decision is not delivered to this MCP
server as an authenticated, payload-bound approval assertion.

Accordingly, every current `CONFIRM_WRITE` tool fails closed with
`TRUSTED_APPROVAL_UNAVAILABLE`. `confirm=true` is only a requested execution
step; it is never evidence of user approval and a model cannot self-grant it.
No LibreChat or identity configuration was changed by this task.

## Shared pending-operation guard

`mcp_erpnext.approvals.ApprovalStore` creates a short-lived pending operation
at prepare time. The opaque handle is bound to the server-side action, Frappe
site, authenticated Frappe user, and HMAC digest of the prepared payload. The
raw prepared document is never accepted from a confirm tool.

`claim_for_confirm_write()` revalidates each binding and atomically consumes a
trusted operation before calling domain persistence. Reuse, cross-user or
cross-tool replay, payload mutation, cancellation, and expiry are rejected.
Frappe create permissions are checked again immediately before every insert.

The internal `record_trusted_user_approval()` seam is deliberately not exposed
as an MCP tool or a public argument. A future transport adapter may call it
only after independently verifying a human-originated decision and binding it
to the same operation. Until such an adapter exists, there is no path to mark a
pending operation trusted in production.

## Required follow-up integration

A separate LibreChat integration task must implement a server-verifiable
approval assertion or an authenticated non-model approval endpoint. It must
bind the actual human decision to the pending operation token, Frappe user,
site, action, and prepared payload before calling the internal approval seam.
It must not trust model text, arbitrary MCP arguments, or an unverified client
header. That task should also define durable shared storage before any
multi-worker deployment is enabled.

## Deployment boundary

The current approval store is process-local and protected with a process-local
lock. It is appropriate only for one local development process; restart loses
pending operations and multiple workers do not share them. This limitation is
safe today because confirms are blocked without the missing trusted adapter.
