# Frappe-Native Shared ApprovalStore Implementation Report

Date: 2026-09-12  
Task: 39 — Implement Frappe-Native Shared ApprovalStore

## Scope completed

`ApprovalStore` no longer keeps production authorization records in a Python
dictionary. Prepared approvals are now shared through the Frappe-managed Redis
cache already initialized for the active site. No public MCP contract, profile,
runtime identity rule, Redis service/configuration, database table, or DocType
was changed.

## Sources inspected

The implementation re-opened `mcp_erpnext/approvals.py`, `runtime.py`,
`settings.py`, `mcp_server.py`, `observability.py`, every approval-backed
service family, the requested approval/service tests, and the Task 38 audit.
The installed runtime authority was `apps/frappe/frappe/__init__.py` and
`apps/frappe/frappe/utils/redis_wrapper.py`. The latter confirms that
`RedisWrapper` provides `make_key()` site/database namespacing and inherits the
raw Redis pipeline operations used here.

## Files changed

- `mcp_erpnext/approvals.py`
- `mcp_erpnext/tests/approval_test_backend.py`
- approval and approval-backed service tests
- current-state approval/deployment documentation listed in Task 39

## Final architecture

Business services retain their existing `create`, `lookup`,
`record_trusted_user_approval`, `claim_for_confirm_write`, `cancel`, and
`prune_expired` calls. `ApprovalStore` delegates raw state operations to the
private `FrappeApprovalBackend`, which uses the active `frappe.cache` instance.
`prune_expired()` remains a compatibility no-op because Redis TTL owns cleanup.

The backend uses `frappe.cache.make_key(..., shared=False)`, raw `get`, `set`,
`pttl`, and a `pipeline()` `WATCH` / `MULTI` / `EXEC` transaction. It does not
call `get_value()` or `set_value()`, so `frappe.local.cache` cannot satisfy an
approval authorization read or mask a failed shared write.

## Authorization and storage details

- The service-supplied active site remains stored and equality-checked; no
  concrete site is present in production code.
- The resolved Frappe user, action, and canonical-payload digest remain exact
  equality/binding checks before a transition.
- Public tokens remain `secrets.token_urlsafe(32)` values. Redis keys use
  `mcp_erpnext:approval:<sha256(token)>` before Frappe adds its site/database
  namespace, so keys do not expose the raw token.
- Records use server-side pickle protocol 5, matching Frappe's trusted cache
  convention and preserving existing payload shapes.
- Timestamps use `time.time()` wall-clock values, which are portable across
  workers. Redis's original 900-second key lifetime is authoritative.
- State rewrites use the raw key's current `PTTL` as `PX`; trust, cancellation,
  and consumption never reset the 900-second lifetime.
- The digest is deterministic canonical-JSON SHA-256. It preserves
  cross-worker payload binding/corruption detection, but is not a keyed MAC
  against an actor able to rewrite both a trusted Redis record and its digest.
  Redis is therefore treated as trusted internal Frappe infrastructure.

## Atomic and failure behavior

Claim, trusted-state, and cancel transitions validate the record first, then
conditionally rewrite it through `WATCH` / `MULTI` / `EXEC`. A conflicting
transaction is reread only to classify a safely observed consumed state; it
never authorizes an ERP write. Backend, serialization, read, write, or
transaction uncertainty fails closed. Create does not return a token unless the
shared write succeeds. A successfully claimed token remains consumed after a
later ERP write failure, preserving the existing one-shot rule.

The test-only `FakeSharedApprovalBackend` models shared raw state, TTL,
compare-and-set conflicts, and backend failures. It is injected explicitly by
tests and is not a production fallback.

## Public contract and runtime boundary

No tool names, schemas, profile inventories, `InteractionDirective`, approval
mode values, HTTP headers, or STDIO/HTTP identity behavior changed. `runtime.py`
continues to initialize the dynamic configured Frappe site and resolved user
before business-service approval calls.

## Verification

The focused approval and approval-backed service suite passed:

```text
../../env/bin/python -m unittest mcp_erpnext.tests.test_approvals \
  mcp_erpnext.tests.test_customer_service mcp_erpnext.tests.test_item_service \
  mcp_erpnext.tests.test_quotation_service \
  mcp_erpnext.tests.test_sales_order_to_sales_invoice \
  mcp_erpnext.tests.test_sales_invoice \
  mcp_erpnext.tests.test_quotation_to_sales_order \
  mcp_erpnext.tests.test_purchase_order_service mcp_erpnext.tests.test_lifecycle \
  mcp_erpnext.tests.test_email
```

Result: `Ran 142 tests ... OK`.

The complete unit suite also passed:

```text
../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
```

Result: `Ran 278 tests ... OK`.

The unit coverage includes cross-instance/restart visibility, stable digest and
timestamps, user/site/action non-consumption, one concurrent winner, conflict
failure, opaque key fingerprinting, trusted/delegated policy, corruption,
expiry, cancellation, and backend failure. No optional live Redis/cache check
was run; all automated coverage uses the isolated fake backend.

`ruff` check/format verification could not run because this environment's
project virtual environment does not have the `ruff` module installed. No
dependency was installed.

## Documentation and limitations

Current documents that claimed process-local approvals now describe the shared
Frappe cache behavior. Historical Task 38 audit material was left unchanged.

Redis is still ephemeral coordination state, not durable approval history. A
lost, evicted, expired, or flushed key fails closed and requires a new prepare.
The Redis claim and the ERP database commit remain separate systems, so this
task does not provide cross-system idempotency or a human-approval UI.

## Next task recommendation

Review this Task 39 implementation and choose the next roadmap task; do not
bundle an unrelated workflow or deployment change into this storage migration.
