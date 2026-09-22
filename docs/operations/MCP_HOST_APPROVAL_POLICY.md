# MCP Host Approval Policy

This guide configures the Codex/ChatGPT Desktop host layer only. It does not
change `mcp_erpnext` business approval: a consequential ERPNext operation still
uses `prepare -> preview/prepared operation -> confirm`, with the existing
approval-token, payload, site, user, TTL, replay, and permission checks.

## Verified Codex configuration semantics

Verified against the official OpenAI documentation on 2026-09-22:

- Codex stores user configuration in `~/.codex/config.toml`; a trusted project
  can have `.codex/config.toml` overrides.
- ChatGPT Desktop, Codex CLI, and the IDE extension share that configuration.
- `mcp_servers.<id>.default_tools_approval_mode` and
  `mcp_servers.<id>.tools.<tool>.approval_mode` accept `auto`, `prompt`,
  `writes`, and `approve`.
- `writes` prompts for a tool that is not marked read-only. Per-tool approval
  modes override the server default.

See the official [MCP configuration guide](https://learn.chatgpt.com/docs/extend/mcp?translationFallback=fr-FR)
and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference?translationFallback=fr-FR).

## Before editing

1. Locate the existing `[mcp_servers.<server-id>]` table for the deployed
   `mcp_erpnext` endpoint in the effective Codex configuration.
2. Record its server ID and any overlapping local/test ERPNext MCP server IDs.
3. Preserve its `url`, OAuth/bearer/header configuration, enabled-tool settings,
   and all secret references. Never copy real tokens, shared secrets, identity
   headers, or passwords into this repository.
4. Do not create a second `[mcp_servers.<server-id>]` table. Add the baseline
   setting to the existing table and append only distinct child tables.

If overlapping test servers make selection ambiguous, temporarily set their
existing `enabled = false` values for the validation session and restore them
afterward. Do not delete their server tables.

## Policy A: conservative `writes` baseline

Add this one line to the existing target-server table:

```toml
[mcp_servers.<actual-server-id>]
# Keep the existing URL/auth/header values in this same table.
default_tools_approval_mode = "writes"
```

With the current contract annotations, `READ` and `RESOLVE` tools are read-only
and should run without a host prompt. `PREPARE` and `CONFIRM_WRITE` are
intentionally non-read-only, so both may prompt. This is the safe fallback
policy when Policy B has not been host-validated.

## Policy B: generated PREPARE auto-approval candidate

Policy B keeps Policy A's `writes` default, but adds `approval_mode = "approve"`
only to `ToolContract.side_effect == PREPARE`. It is not a blanket trust policy:
all `CONFIRM_WRITE` tools continue to prompt in the host, including delete,
cancel, submit/update/reconciliation, and external email confirmation.

Generate the exact current override tables instead of maintaining a hand-written
list:

```bash
cd /path/to/your/frappe-bench/apps/mcp_erpnext
PYTHONDONTWRITEBYTECODE=1 /path/to/your/frappe-bench/env/bin/python \
  scripts/generate_tool_catalog.py --prepare-approval-overrides \
  --server-id '<actual-server-id>'
```

The command prints only child tables such as:

```toml
[mcp_servers."<actual-server-id>".tools."prepare_quotation"]
approval_mode = "approve"
```

Append its complete output after the existing server table. The generator fails
if an override target is not a `PREPARE`, advertises destructive/open-world
semantics, or lacks a guarded `CONFIRM_WRITE` counterpart. It is derived from
the same registry as `docs/TOOLS.md`; rerun it whenever tool contracts change.

Do not select Policy B for a deployment until its host validation matrix below
has observed the expected behavior. Do not set
`default_tools_approval_mode = "approve"` as a production default.

## Reload, connection, and rollback

Restart/reload the relevant Codex/ChatGPT Desktop client after every config
change, then confirm that the intended server connects to its configured `/mcp`
endpoint and exposes the expected profile-specific tools. An initialized
connection alone is insufficient: inspect the available tool list and run the
matrix below.

Rollback is local and reversible:

1. Remove the generated `tools.<prepare-tool>` child override tables.
2. Retain or restore `default_tools_approval_mode = "writes"` in the one
   existing server table.
3. Reload the host and repeat a read and a confirm-boundary check in a fresh
   thread.

Do not alter the ERPNext endpoint, authorization values, or server-side
`MCP_APPROVAL_MODE` as part of a host-policy rollback.

## Operator validation matrix

Use a safe/test business context. Record actual host prompts and tool traces,
not expected results. Never delete a valued record, send external email, or
create/reconcile a financial transaction merely to prove a popup.

| Layer / representative action | Policy A expected | Policy B expected | Record |
| --- | --- | --- | --- |
| Sales resolve Customer/Item | no host prompt | no host prompt | tool, thread, prompt result |
| Exact known Sales document `get_*` | no host prompt | no host prompt | tool trace |
| Candidate `search_*` / filtered `query_*` | no host prompt | no host prompt | tool trace |
| Supported `aggregate_*` metric | no host prompt | no host prompt | tool trace |
| Sales `prepare_quotation` preview | host prompt | no host prompt | preview, no write |
| Purchase `prepare_purchase_order` preview | host prompt | no host prompt | preview, no write |
| Accounts `prepare_*payment*` preview | host prompt | no host prompt | preview, no write |
| Any safe confirm boundary | host prompt | host prompt | do not approve unless authorized |
| `confirm_document_delete` boundary | host prompt | host prompt | do not execute destructive write |
| `confirm_document_email` boundary | host prompt | host prompt | do not send email |

For each profile, verify `tools/list` before selecting an action. Keep the
server-side prepared-operation token private. A host approval permits the tool
call only; it does not replace the server's business confirmation checks.

## Routing and fresh-thread checks

In two fresh conversations after reload, record the host's actual first tools:

- Natural-language quotation intent: `resolve_customer` and `resolve_item`,
  then reuse a `resolved` reference rather than a verification search/query.
- Exact known Sales Order: `get_sales_order`, not discovery first.
- Explicit browse: `search_*`; structured filters: `query_*`; server metric:
  matching `aggregate_*`.
- Resolver `not_found`: ask for clarification or search only after an explicit
  request for alternatives; never silently substitute a query result.

These server instructions and descriptions guide the host/client; they do not
make an independently acting client incapable of extra valid tool calls.
