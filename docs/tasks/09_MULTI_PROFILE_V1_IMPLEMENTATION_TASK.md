# MCP ERPNext Multi-Profile V1 Implementation Task

## Status
Architecture frozen for V1.

## Objective
Refactor the existing `mcp_erpnext` Frappe app so the same codebase can expose multiple domain-specific MCP server profiles without creating separate Frappe apps or duplicating shared logic.

V1 must prove that LibreChat can connect to two distinct ERPNext MCP profiles from the same `mcp_erpnext` app:

- `sales`
- `purchase`

`accounts` is explicitly deferred to a later phase.

---

## Frozen Architecture

```text
mcp_erpnext  (one Frappe app)
│
├── shared MCP/Frappe infrastructure
│   ├── request/Frappe context
│   ├── mcp_identity integration
│   ├── common resolvers
│   ├── validation
│   ├── approval / confirmation infrastructure
│   └── common error handling
│
├── sales domain
│   └── existing Sales MCP profile
│
└── purchase domain
    └── new Purchase MCP profile
```

Expose the profiles as separate MCP server instances/endpoints/configurations while keeping the implementation in one Frappe app.

Do **not** create:

- `mcp_erpnext_sales` app
- `mcp_erpnext_purchase` app
- nested MCP servers inside another MCP server
- duplicate copies of shared resolver/context/approval logic

---

## V1 Scope

### Sales MCP profile
Reuse the existing sales functionality already implemented in `mcp_erpnext`.

The Sales profile should expose only the currently supported sales-related tools, such as the existing tools for:

- Customer resolution/search
- Item resolution/search
- Quotation flow
- Sales Order flow
- Existing generic/shared resolver or approval tools that are genuinely required for those flows

Do not redesign the existing Sales business flow unless required to support profile-based registration.

### Purchase MCP profile
Add the smallest useful Purchase flow necessary to prove multi-profile MCP architecture.

V1 Purchase functionality should cover:

- Supplier search/resolution
- Item search/resolution by reusing existing shared item logic where appropriate
- Prepare Purchase Order
- Confirm/Create Purchase Order using the same approval/confirmation principles already used by existing write flows

Do not implement Accounts, Purchase Invoice, Payment Entry, Material Request, RFQ, Supplier Quotation, receipt flows, or complex buying workflows in this task unless they are strictly required by ERPNext metadata for a valid Purchase Order.

---

## Important First Step — Inspect Before Modifying

Before changing code, inspect the actual current local `mcp_erpnext` implementation.

At minimum inspect:

- current package/folder structure
- current MCP server entrypoint(s)
- current transport handling (`stdio`, `streamable-http`, if both exist)
- current tool registration approach
- current Sales tools and their module locations
- current generic resolver infrastructure
- current approval/confirmation state implementation
- current `mcp_identity` integration
- current settings/environment variables
- current tests
- current `hooks.py`
- current dependency declarations
- current README/AGENTS/task documentation
- current git status

Do not assume filenames or functions from older tasks if the local working tree differs.

Before modifying, report briefly:

```text
Current MCP entrypoint
Current tool registry structure
Current Sales tool list
Shared components that can be reused by Purchase
Files proposed for modification
Files proposed for creation
Compatibility risks
```

Then proceed unless a serious destructive ambiguity is found.

---

## Profile Selection Design

Implement a clean profile-selection mechanism.

The design must allow the same codebase to start as either:

```text
sales
purchase
```

The exact mechanism may use an environment/config setting, CLI/startup parameter, or another small explicit runtime selector, but it must be simple and deterministic.

Preferred conceptual contract:

```text
MCP_PROFILE=sales
```

or:

```text
MCP_PROFILE=purchase
```

Do not hardcode LibreChat-specific profile selection.

### Requirements

- Unknown profile must fail clearly at startup.
- Missing profile may preserve the current existing behavior only if doing so is backward-compatible and unambiguous.
- If the current server already has a default mode, preserve it unless there is a strong reason not to.
- Each running MCP instance must register only the tools belonging to its selected profile plus genuinely shared tools required by that profile.
- Sales instance must not expose Purchase Order tools.
- Purchase instance must not expose Quotation/Sales Order tools.

---

## Tool Registration Architecture

Refactor toward explicit domain registries rather than one giant unconditional tool registry.

Conceptually:

```text
profile = sales
→ register shared-required tools
→ register sales tools only

profile = purchase
→ register shared-required tools
→ register purchase tools only
```

Keep tool implementations domain-owned, but shared technical helpers must stay shared.

Do not duplicate existing Item resolution code merely to create a Purchase profile. Reuse shared/native logic where it already fits.

Prefer small registries/modules over large `if/elif` blocks spread throughout the server.

---

## Purchase Order Flow

Implement the minimum robust Purchase Order flow.

Expected conversational behavior:

```text
User asks to create PO
        ↓
resolve supplier
        ↓
resolve item(s)
        ↓
collect/validate minimum required fields
        ↓
prepare Purchase Order preview
        ↓
request/receive confirmation
        ↓
create draft Purchase Order
```

### ERPNext metadata

Do not guess required Purchase Order fields from memory.

Inspect ERPNext/Frappe DocType metadata and reuse the existing metadata/config/resolver infrastructure already created in `mcp_erpnext` where available.

Use ERPNext/Frappe defaults where appropriate instead of asking the user for values ERPNext can safely derive.

Do not bypass Frappe/ERPNext permissions.

### Supplier resolution

Add a supplier search/resolution flow consistent with the existing Customer/Item resolver behavior:

- exact match when possible
- fuzzy/partial candidate discovery if the existing resolver framework supports it
- ambiguity must not silently choose an unsafe candidate
- no supplier creation in this V1 unless explicitly already supported by a generic master-creation framework and required by the task

### Item resolution

Reuse existing Item resolver/search/select behavior wherever possible.

### Confirmation

Purchase Order writes must follow the same confirmation/approval safety contract already used by existing Sales write flows.

Do not invent a second confirmation framework.

If the current confirmation mechanism has known limitations, preserve the existing architectural contract and document any blocker rather than implementing a competing subsystem inside Purchase.

---

## Identity and Permission Rules

Use the already frozen `mcp_identity` boundary.

Do not add:

- Purchase-specific identity mapping
- Sales-specific identity mapping
- LibreChat-specific mapping
- additional ERPNext permission tables
- MCP tool permission tables

Once the Frappe user is resolved, ERPNext/Frappe native permission checks remain authoritative.

Fail closed if identity is missing or invalid according to the existing `mcp_identity` contract.

---

## Transport Requirements

Preserve current supported transports.

If both exist today:

- `stdio`
- `streamable-http`

then both must continue to work unless a current documented limitation prevents it.

Profile selection must work consistently for each supported transport.

Do not create separate copies of transport code for Sales and Purchase.

---

## LibreChat Target Configuration

After implementation it must be possible to register two MCP servers in LibreChat that point to the same `mcp_erpnext` codebase but run with different profiles.

Conceptually:

```text
ERPNext Sales MCP
→ mcp_erpnext with profile=sales

ERPNext Purchase MCP
→ mcp_erpnext with profile=purchase
```

The exact URLs/ports/process definitions depend on the current deployment model and must be documented after inspecting the existing HTTP server startup.

Do not make LibreChat itself responsible for filtering a giant shared tool list if profile-level filtering can be done server-side.

---

## Backward Compatibility

Existing Sales behavior is important.

Preserve:

- existing tool names unless a change is strictly necessary
- existing tool input/output contracts
- existing confirmation behavior
- existing identity behavior
- existing transport behavior
- existing Frappe/ERPNext permissions
- existing error semantics

Do not turn this task into a Sales refactor beyond what is required for domain profile registration.

---

## Suggested Logical Structure

Use the actual repository structure after inspection, but target a clean separation approximately like:

```text
mcp_erpnext/
├── mcp_server.py / server entrypoint
├── profiles/
│   ├── sales.py
│   └── purchase.py
├── tools/
│   ├── shared/
│   ├── sales/
│   └── purchase/
└── ... existing shared infrastructure
```

This is guidance, not a requirement to rename working files unnecessarily.

Do not create empty folders for future Accounts work.

---

## Testing

### 1. Profile startup tests

Verify:

```text
sales profile starts
purchase profile starts
invalid profile fails clearly
```

### 2. Tool exposure tests

Sales profile:

```text
Customer tools present
Item tools required by Sales present
Quotation tools present
Sales Order tools present
Purchase Order tools absent
```

Purchase profile:

```text
Supplier tools present
Item tools required by Purchase present
Purchase Order tools present
Quotation tools absent
Sales Order tools absent
```

### 3. Existing Sales regression

Run the existing Sales tests and verify that current Customer/Item/Quotation/Sales Order flows still pass.

### 4. Purchase read test

Example:

```text
Search suppliers matching <known supplier>
```

Expected:

- appropriate matches returned
- no write occurs

### 5. Purchase prepare test

Example:

```text
Prepare a purchase order for <known supplier> with <known item>, quantity 2.
```

Expected:

- supplier/item resolved
- valid preview returned
- no Purchase Order created before confirmation

### 6. Purchase confirm test

After explicit confirmation:

- Draft Purchase Order is created
- correct Frappe user context is used
- ERPNext permissions apply
- no Sales document is created

### 7. Permission denial

Use a Frappe user without Purchase Order create permission.

Expected:

- Purchase profile can resolve identity
- ERPNext/Frappe rejects unauthorized create
- no permission bypass

### 8. Multi-MCP LibreChat test

Connect both profiles simultaneously.

Run two separate prompts:

```text
Create/prepare a Sales Order for <existing customer> ...
```

Expected route:

```text
Sales Agent / Sales MCP
```

Then:

```text
Prepare a Purchase Order for <existing supplier> ...
```

Expected route:

```text
Purchase Agent / Purchase MCP
```

Verify the model is not presented with irrelevant domain tools from the other profile.

---

## Acceptance Criteria

Task is complete only when all are true:

- one Frappe app `mcp_erpnext` remains the ERPNext MCP codebase
- Sales and Purchase profiles can run independently
- Sales profile exposes only Sales-relevant tools plus required shared tools
- Purchase profile exposes only Purchase-relevant tools plus required shared tools
- current Sales flows remain working
- Supplier resolution works
- Purchase Order prepare/confirmation/create flow works
- no duplicate resolver/context/confirmation subsystem is introduced
- no new ERPNext permission system is introduced
- `mcp_identity` remains the identity boundary
- LibreChat can connect both profiles simultaneously
- exact startup/config instructions are documented
- tests pass

---

## Explicitly Out of Scope

Do not implement in this task:

- Accounts MCP profile
- Sales Invoice
- Purchase Invoice
- Payment Entry
- accounting reports
- Material Request unless ERPNext PO creation absolutely requires it (normally it should not)
- RFQ / Supplier Quotation workflow
- Purchase Receipt
- supplier creation flow
- separate Frappe apps per ERPNext domain
- Google/Gmail MCP
- generic coordinator-agent redesign
- new authentication system
- new authorization policy layer

---

## Final Report Required

After implementation provide a concise report with:

### Architecture

```text
mcp_erpnext
├── sales profile
└── purchase profile
```

and shared components reused by both.

### Files changed
List created/modified files and why.

### Profile startup
Show exact commands/env/config needed to start:

```text
Sales MCP
Purchase MCP
```

for the current environment.

### Tool exposure
Show final tool list for each profile.

### Tests
Show commands executed and exact pass/fail results.

### LibreChat setup
Show the two MCP server configurations needed to connect Sales and Purchase simultaneously.

### Known limitations
Only real current limitations; do not add hypothetical future work.

---

## Exact Next Task After This

After Sales + Purchase multi-profile routing is proven in LibreChat, review whether an `accounts` profile is justified.

Do not implement Accounts in this task.
