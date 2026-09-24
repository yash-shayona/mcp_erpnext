# MCP Conversational Interaction Contract

`mcp_erpnext` is deterministic and client-neutral. This document freezes the
semantic contract between an Agent/orchestrator and the MCP server; it is not a
chat protocol or a conversation-state design.

## Responsibility split

The MCP server owns ERPNext validation, permissions, entity resolution,
candidate revalidation, missing-input requirements, previews, approval-token
integrity, and final write safety. The Agent owns natural-language
interpretation, conversation state, and choosing the next structured tool call.
The client owns display, transport, UI controls, and its authenticated session.

MCP does not store conversation IDs, transcripts, assistant messages, UI
component IDs, LangGraph state, or natural-language history. It does not parse
phrases or call an LLM to classify the user's intent.

## Shared directive

Typed public results that need a continuation add this additive object:

```json
{
  "interaction": {
    "required": true,
    "kind": "SELECTION",
    "allowed_actions": ["SELECT", "CANCEL"],
    "reason_code": "AMBIGUOUS_REFERENCE",
    "instructions": "Select exactly one candidate."
  }
}
```

`required: false` means normal MCP continuation needs no user input; it has no
kind or actions. Read-only and terminal results do not need to emit an empty
directive. The directive never duplicates the result's candidates, missing
fields, preview, or approval token.

The centralized `InteractionKind` values are:

- `SELECTION`
- `INPUT`
- `APPROVAL`

The centralized `InteractionAction` values are:

- `SELECT`
- `PROVIDE_INPUT`
- `MODIFY`
- `APPROVE`
- `REJECT`
- `CANCEL`

These are semantic intentions, not required user phrases or UI controls.

## Selection and input

An ambiguous resolver returns `SELECTION` with `SELECT` and the existing
typed candidates. The Agent asks naturally, interprets a response or UI
selection, then calls `select_resolved_candidate` with the selected typed
reference. MCP revalidates it with normal permissions.

When a prepare workflow returns structured `missing` fields, it returns `INPUT`
with `PROVIDE_INPUT`. The Agent asks for the business value, turns the response
into typed input, and calls the appropriate prepare tool again. MCP does not
parse the reply.

## Approval, reject, cancel, and modify

A prepared preview returns `APPROVAL`. The Agent must show or restate the exact
preview and interpret the user response as one of the allowed semantic actions.
`APPROVE` is not authorization to write: the matching confirm tool remains
fail-closed until the existing trusted, server-recorded approval guard accepts
the original site, user, action, payload digest, and token.

`REJECT` declines the prepared operation. `CANCEL` abandons the current
conversational continuation; neither is an ERPNext document cancellation.
For `MODIFY`, the Agent must not approve the old preview: it cancels/rejects
that pending operation through the existing flow, sends the changed structured
input to prepare again, and obtains a new preview and approval requirement.

## Current adoption and future-agent rule

Contracts that can require interaction declare their allowed semantic kinds in
`contracts/registry.py`; the generated [tool catalog](../TOOLS.md) publishes
that metadata for every selected profile. Current resolvers use `SELECTION`
when their result is ambiguous. Current prepare tools use `INPUT`, `SELECTION`,
or `APPROVAL` only for result states their typed contract declares; terminal
permission and error states do not request interaction. For example,
`prepare_sales_order` and `prepare_quotation` declare `INPUT` and `APPROVAL`,
while source-document conversion and payment preparation flows declare their
applicable `APPROVAL` continuation. Do not infer interaction requirements from
the tool name; inspect the contract or live `tools/list` output.

Every future conversational MCP tool must decide whether a result requires
interaction and, if so, declare the shared kind and allowed actions in the
contract registry. It must not invent fields such as `needs_user_choice`,
`ask_again`, `approval_needed`, `please_confirm`, or `requires_answer`.

The future Coordinator Agent consumes this contract: it asks users naturally,
interprets replies into semantic actions and typed values, and invokes the
existing MCP tools. It must preserve the trusted approval boundary rather than
treating an LLM or UI decision as permission to write.
