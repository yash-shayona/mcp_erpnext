# Task: Add Project-Specific Command Registry

## Objective

Add a small command registry to the current `mcp_erpnext` repository so developers do not need to remember or rediscover the commands required to start the MCP server.

This is **not** intended to become a generic Frappe/Linux/Docker command reference.

## Scope

Modify only:

* `docs/COMMANDS.md` — create if it does not exist.
* `AGENTS.md` — add a small standing rule for maintaining the command registry.

Do not modify MCP runtime behavior, server code, configuration, profiles, authentication, or transport implementation.

## Step 1 — Inspect Current MCP Startup

Inspect the current repository and determine the **actual currently supported command(s)** used to start `mcp_erpnext`.

Especially account for the current multi-profile/multi-process MCP setup.

Do not invent or assume commands.

Use the commands already supported by the current implementation/configuration.

## Step 2 — Create `docs/COMMANDS.md`

Keep the file intentionally small.

For now, document only the reusable command(s) directly required to start the `mcp_erpnext` MCP server/profile processes.

Example structure:

````md
# MCP ERPNext Commands

## Start MCP Server

### Sales Profile

Run from:
`<working-directory>`

```bash
<actual-current-command>
````

### Purchase Profile

Run from:
`<working-directory>`

```bash
<actual-current-command>
```

```

Only include separate Sales/Purchase entries if the current implementation actually requires separate commands/processes.

If there is one command that starts the complete required MCP setup, document only that command.

### Do NOT add

Do not add generic commands such as:

- `bench start`
- `bench migrate`
- `bench clear-cache`
- generic Frappe commands
- LibreChat commands
- generic Docker commands
- generic Linux commands
- temporary debugging commands
- one-off investigation commands

## Step 3 — Update `AGENTS.md`

Add a concise standing rule similar to:

> ### Project Command Registry
>
> `docs/COMMANDS.md` contains reusable project-specific operational commands.
>
> When a task introduces, changes, or removes a reusable command required to run, start, test, inspect, or operate this project, update `docs/COMMANDS.md`.
>
> Only document commands that are directly specific to this project and reasonably expected to be reused.
>
> Do not add generic framework, Bench, Docker, operating-system, unrelated application, or temporary debugging commands merely because they were used while completing a task.
>
> Before documenting a command, verify it against the project's actual implementation/configuration rather than guessing.
>
> Never place passwords, tokens, shared secrets, or other secret values in `docs/COMMANDS.md`. Reference environment-variable names/placeholders instead.

Keep this rule concise; do not duplicate large sections elsewhere in `AGENTS.md`.

## Acceptance Criteria

- `docs/COMMANDS.md` exists.
- It contains the actual current MCP startup command(s).
- Commands match the current multi-profile/process implementation.
- No unrelated generic commands are added.
- No secrets are written into the file.
- `AGENTS.md` contains the standing maintenance rule.
- Existing MCP functionality is unchanged.

## Verification

Verify each documented command against the current repository implementation/configuration.

If practical, execute or otherwise validate the command syntax without making unrelated application changes.

## Expected Result

A developer should be able to open:

`docs/COMMANDS.md`

and immediately find the command needed to start the current `mcp_erpnext` MCP server setup.

Future agents should automatically keep this file updated when project-specific reusable commands change.

## Limitations

Do not expand this task into general project documentation or a CLI redesign.

## Next Task

None.

Complete only this documentation/agent-rule task and report:

1. files created/modified,
2. exact commands documented,
3. how those commands were verified.
```
