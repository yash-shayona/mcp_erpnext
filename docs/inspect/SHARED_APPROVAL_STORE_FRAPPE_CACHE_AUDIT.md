# Shared Approval Store / Frappe Cache Architecture Audit

Date: 2026-09-12  
Task source: `docs/tasks/audits/38_TASK_SHARED_APPROVAL_STORE_FRAPPE_CACHE_AUDIT.md`  
Project: `mcp_erpnext`  
Runtime: Frappe `16.33.1`, ERPNext `16.34.2`, Python `3.14.3`  
Frappe checkout: `apps/frappe`, branch `version-16`, commit
`988e54f3c4c291e2077a83809663f123731abe76`

The task filename is numbered 38, while its heading and required next task
identify the audit as Task 37 and the implementation as Task 38. This report
follows the required output and does not change production behavior.

## 1. Executive summary

The current approval store is process-local. `approvals = ApprovalStore()` is a
module-global singleton, but its records live in `self._approvals`, an ordinary
Python dictionary protected by one process-local `RLock`. A prepare in one MCP
process is therefore invisible to another process and is lost on process exit.

The installed Frappe foundation is suitable for shared ephemeral approval
state. `frappe.init()` creates one `RedisWrapper` connection from the resolved
`redis_cache` configuration, and Frappe documents that workers use
`frappe.cache` against the bench Redis service. The normal high-level cache
helpers are not sufficient as the approval authorization boundary because they
populate/read `frappe.local.cache` and suppress Redis connection errors.

The recommended outcome is Outcome B:

- use the existing Frappe-configured `frappe.cache` / `RedisWrapper` connection;
- do not add a Redis service, Redis URL, credentials, package, or approval
  DocType;
- keep Redis details inside `ApprovalStore` or a private storage adapter;
- use a small internal adapter around the inherited Redis connection for
  fail-closed raw reads/writes and `WATCH` / `MULTI` / `EXEC` compare-and-set;
- do not use `frappe.cache.get_value()` for claim authorization unless the
  local-cache path is explicitly bypassed and backend failures are separately
  detected;
- preserve the 900-second lifetime, bindings, trusted-human policy, safe public
  errors, stale document checks, and normal Frappe writes;
- make the payload digest process-stable. The current random per-process HMAC
  key cannot be retained unchanged in a shared store.

No live Redis/cache mutation, ERP record mutation, migration, service restart,
or production-code edit was performed for this audit.

## 2. Current ApprovalStore architecture

### Sources inspected

The current equivalents requested by the task are present at:

- `mcp_erpnext/approvals.py`
- `mcp_erpnext/settings.py`
- `mcp_erpnext/runtime.py`
- `mcp_erpnext/observability.py`
- `mcp_erpnext/contracts/interaction.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/profiles/sales.py`
- `mcp_erpnext/profiles/purchase.py`
- `mcp_erpnext/services/**`
- `mcp_erpnext/tools/**`
- `mcp_erpnext/tests/**`
- `docs/TOOLS.md`
- `docs/architecture/**`
- `docs/inspect/**`

The installed framework sources are under `apps/frappe/frappe/`; there is no
`apps/frappe/frappe/local.py`. Local state is provided by
`frappe.utils.local.Local` and initialized in `frappe/__init__.py`.

### Creation

`ApprovalStore` is defined in `mcp_erpnext/approvals.py:23-183`.

- `create()` uses `secrets.token_urlsafe(32)` (`approvals.py:71-85`). This is an
  opaque token with 32 random bytes before URL-safe encoding.
- The record is a `PendingApproval` dataclass containing `action`, `site`,
  `user`, `created_at`, the full prepared `payload`, `payload_digest`, and
  mutable `trusted_at`, `consumed_at`, and `cancelled_at` timestamps.
- `created_at` uses `time.monotonic()` (`approvals.py:81`). It is valid for
  comparisons inside one process but is not a portable timestamp between
  processes or restarts.
- The digest is an HMAC-SHA256 over canonical JSON (`sort_keys=True`, compact
  separators, `default=str`) using `_signing_key`, which is a random 32-byte
  key generated separately by every `ApprovalStore` instance
  (`approvals.py:55-69`).
- The full payload, rather than only the digest, is needed by confirmation
  services and is currently retained in process memory.
- There is no profile field in the dataclass. Lifecycle and email payloads can
  contain a profile, and lifecycle action names are prefixed with
  `lifecycle_`; the generic create actions are distinct. Profile is not a
  direct store binding.
- There is no client, session, conversation, thread, run, or process ID in the
  approval record.
- `approvals` at `approvals.py:183` is a module-level singleton. It is global
  only within one Python process; it is not shared memory.

### TTL and cleanup

`APPROVAL_TTL_SECONDS = 15 * 60` at `approvals.py:16`, exactly 900 seconds.
Expiry is calculated as `time.monotonic() - created_at > 900`
(`approvals.py:37-40`). The current store has no Redis TTL, database TTL, or
background cleanup.

Cleanup is lazy:

- `create()` calls `_prune_expired_locked()` before adding a new record;
- `lookup()`, trusted-approval recording, and claim remove the individual
  record when their lookup sees expiry;
- `prune_expired()` is called by several prepare services;
- unused records can remain until a later prepare or lookup in that same
  process;
- process exit drops all records and the per-process signing key.

### Process-local limitation

`self._approvals` and `self._lock` are created in `ApprovalStore.__init__`
(`approvals.py:52-58`). The lock makes the validation-and-consume sequence
atomic only for callers sharing that object. Two independent MCP processes
have two dictionaries and two locks, so Process B cannot find a token created
by Process A. A client reconnect or worker replacement has the same effect as
expiry from the caller's perspective.

The current source therefore proves the known failure mode rather than merely
suggesting it.

## 3. Current approval lifecycle

### Prepare to trust

Prepare services call `approvals.create(...)` only after their input,
permission, native-default, and preview checks. The resulting token and
`expires_in_seconds: APPROVAL_TTL_SECONDS` are returned in the prepare result.

The policy is defined by `ApprovalMode` in `mcp_erpnext/settings.py:15-20`:

- `trusted_human` is the default;
- `agent_delegated` is the alternate server configuration.

`MCPSettings.from_environment()` reads `MCP_APPROVAL_MODE` at
`settings.py:71-83`; invalid values fail. `mcp_server.create_mcp()` validates
the setting and configures the shared singleton at `mcp_server.py:28-35`.
Tools do not receive the mode, `trusted_at`, or a trusted-approval method as
public input.

`record_trusted_user_approval()` at `approvals.py:101-119` is an internal seam.
It revalidates the token/action/site/user and payload digest, refuses expired,
consumed, or cancelled records, then sets `trusted_at`. There are no
production call sites in `mcp_erpnext`; current uses are in approval tests.
The documented design expects a transport/client adapter to call this only
after independently verifying a human-originated decision.

In `trusted_human` mode, `claim_for_confirm_write()` requires `trusted_at`.
In `agent_delegated` mode, that one check is skipped. The mode remains
server-selected and does not weaken the action, site, user, payload, expiry,
single-use, or final ERP permission checks.

### Lookup and claim order

`_lookup_locked()` at `approvals.py:155-171` performs this order:

1. dictionary lookup;
2. absent record -> `expired`;
3. monotonic TTL check; expired records are removed -> `expired`;
4. exact action, site, and user equality -> `unavailable`;
5. recompute the payload HMAC and constant-time compare it with the stored
   digest; mismatch removes the record -> `unavailable`;
6. return the pending record as `available`.

`claim_for_confirm_write()` then checks cancellation/consumption, checks
`trusted_at` when required, and sets `consumed_at` before returning the record
(`approvals.py:121-140`). This is atomic under the one process-local `RLock`.
The record remains present as consumed until it expires, so replay returns
`consumed` rather than looking like a missing token.

The claim happens before persistence. If native permission, validation, insert,
send, or document mutation fails, services roll back their ERP transaction but
there is no approval rollback. The token remains consumed and the operation
must be prepared again. This is deliberate one-shot behavior and must be
preserved by Task 38.

### Reject / cancel

For confirm tools that accept `confirm: bool`, `confirm=False` calls
`approvals.cancel(...)` and returns `CONFIRMATION_REQUIRED`; a matching pending
record receives `cancelled_at` and cannot later be trusted or claimed. Wrong
action/site/user or an absent token is not cancelled.

The generic document email confirm takes the token and profile and claims
directly; it has no boolean reject parameter (`services/common/email.py:421-427`).
Conversational reject/cancel is therefore represented by the calling workflow
where available, not by an ERP document cancellation. None of these approval
operations cancels an ERP document.

### Public error mapping

`confirmation_failure()` at `approvals.py:186-210` maps internal claim states:

| Internal state | Public code | Retry guidance |
| --- | --- | --- |
| `expired` | `CONFIRMATION_EXPIRED` | Prepare again |
| `consumed` | `CONFIRMATION_CONSUMED` | Prepare again |
| `not_trusted` | `TRUSTED_APPROVAL_UNAVAILABLE` | No retry until trusted approval exists |
| `unavailable` and other fallback states | `CONFIRMATION_UNAVAILABLE` | No retry; prepare again as appropriate |

The current public contract intentionally does not distinguish missing token,
wrong action, wrong site, wrong user, or digest failure. A future shared
adapter should keep this fail-closed public behavior and add only safe internal
reason codes for operations.

## 4. Approval call-site inventory

All current production call sites use the imported shared `approvals` object and
the same `create` / `cancel` / `claim_for_confirm_write` abstraction. No service
creates a second approval store.

| Capability | Prepare function | Confirm function | Approval action | Shared store? | Special stale revalidation? |
| --- | --- | --- | --- | --- | --- |
| Customer | `services/masters/customer.py:400` `prepare_customer` | `:435` `confirm_customer` | `create_customer` | Yes | No source document; native create checks are repeated |
| Item | `services/masters/item.py:346` `prepare_item` | `:373` `confirm_item` | `create_item` | Yes | No source document; effective requirements are checked again |
| Quotation | `services/selling/quotation.py:252` `prepare_quotation` | `:381` `confirm_quotation` | `create_quotation` | Yes | Reuses prepared payload and repeats permission/native checks |
| Sales Order | `services/selling/sales_order.py:170` `prepare_sales_order` | `:279` `confirm_sales_order` | `create_sales_order` | Yes | Reuses prepared payload and repeats create permission |
| Quotation -> Sales Order | `services/selling/quotation_to_sales_order.py:246` | `:284` | `convert_quotation_to_sales_order` | Yes | Source modified/fingerprint/native mapping rechecked |
| Sales Order -> Sales Invoice | `services/selling/sales_order_to_sales_invoice.py:254` | `:294` | `convert_sales_order_to_sales_invoice` | Yes | Source modified/fingerprint/native mapping rechecked |
| Sales Invoice | `services/selling/sales_invoice.py:428` | `:487` | `create_sales_invoice` | Yes | Effective invoice rebuilt and fingerprint/stale state rechecked |
| Lifecycle update | `services/common/lifecycle.py:285` | `:580` | `lifecycle_update` | Yes | Target modified/docstatus and child old values rechecked |
| Lifecycle child/item add | `services/common/lifecycle.py:384` | `:580` | `lifecycle_child_add` | Yes | Target modified/docstatus, target configuration, duplicates, and row types rechecked |
| Lifecycle submit | `services/common/lifecycle.py:696` via `_prepare_action` | `:580` | `lifecycle_submit` | Yes | Target modified/docstatus and permission rechecked |
| Lifecycle cancel | `services/common/lifecycle.py:700` via `_prepare_action` | `:580` | `lifecycle_cancel` | Yes | Target modified/docstatus and permission rechecked |
| Lifecycle delete | `services/common/lifecycle.py:704` via `_prepare_action` | `:580` | `lifecycle_delete` | Yes | Target modified/docstatus, links/blockers, cancel-delete plan, and permission rechecked |
| Purchase Order | `services/buying/purchase_order.py:172` | `:262` | `create_purchase_order` | Yes | Unsaved native defaults/validation repeated before insert |
| Document email | `services/common/email.py:338` | `:421` | `document_email` | Yes | Document modified/docstatus, recipient association, and PDF digest rechecked |
| Document PDF | `services/common/pdf.py` through `tools/pdf.py` | None | None | No | Permission-checked read/render only; not approval-gated |

The service actions and all current approval references were inventoried with
`rg` across `mcp_erpnext/services`. The profile registration boundary is
unchanged: Sales is registered by `profiles/sales.py`, Purchase by
`profiles/purchase.py`, and the shared lifecycle/PDF/email tools are registered
for each allowed profile.

## 5. Installed Frappe cache / Redis architecture

### Runtime and connection setup

The installed Frappe source is the runtime authority. At
`apps/frappe/frappe/__init__.py:342-354`, `setup_redis_cache_connection()` sets
the module-level `frappe.cache` to `setup_cache()` and creates a separate
`ClientCache`.

`apps/frappe/frappe/utils/redis_wrapper.py:38` defines `RedisWrapper` as a
subclass of `redis.Redis`. `setup_cache()` at `:369-384` resolves either the
configured Redis Sentinel connection or `RedisWrapper.from_url(frappe.conf.get("redis_cache"))`.
The bench currently has the non-secret common setting
`sites/common_site_config.json:12`:

```text
redis_cache = redis://127.0.0.1:13000
```

The effective source also permits the official `FRAPPE_REDIS_CACHE`
environment override at `apps/frappe/frappe/config.py:123-129`. Thus workers
share cache only when they resolve the same bench/site configuration; a
different override or separate Redis deployment is an operational split, not a
Frappe guarantee.

`frappe.init()` at `apps/frappe/frappe/__init__.py:144-227` loads site
configuration, sets `local.site`, `local.site_name`, `local.conf`, and creates
`local.cache` before ensuring the Redis connection. The approval adapter must
run after site initialization so `frappe.local.conf` and its database/site
namespace are available.

### Namespacing

`RedisWrapper.make_key()` at `apps/frappe/frappe/utils/redis_wrapper.py:52-62`
uses:

```text
<frappe.local.conf.db_name>|<key>
```

unless `shared=True`, in which case it returns the key unchanged. A user-scoped
key adds `user:<user>:` before the site/database prefix. The installed source
does not use the literal site name in the prefix; the effective per-site
database name is the namespace. The approval record must still retain and
validate the explicit `site` field, and the adapter must not use
`shared=True`.

The official Frappe caching guide describes this as site-context key
prefixing and states that each Frappe worker connects to the bench Redis
service. It also documents `frappe.cache` values, TTLs, pickle serialization,
and client-side caching:

- [Frappe caching guide](https://docs.frappe.io/framework/user/en/guides/caching)
- [Frappe utility API](https://docs.frappe.io/framework/user/en/api/utils)
- [Frappe site configuration](https://docs.frappe.io/framework/user/en/basics/site_config)
- [Installed-version `redis_wrapper.py` source](https://github.com/frappe/frappe/blob/988e54f3c4c291e2077a83809663f123731abe76/frappe/utils/redis_wrapper.py)
- [Installed-version `caching.py` source](https://github.com/frappe/frappe/blob/988e54f3c4c291e2077a83809663f123731abe76/frappe/utils/caching.py)
- [Installed-version `__init__.py` source](https://github.com/frappe/frappe/blob/988e54f3c4c291e2077a83809663f123731abe76/frappe/__init__.py)

The live installed source takes precedence if future official documentation
differs.

### Serialization and payload size

`RedisWrapper.set_value()` pickles values using protocol 5 and sends them to
Redis with `ex=expires_in_sec` (`redis_wrapper.py:64-77`). `get_value()`
unpickles non-`None` values (`:79-112`). This is compatible with a
`PendingApproval` serialization strategy but means the cache is a trusted
Python-value boundary, as with other Frappe cached objects.

The Frappe `ClientCache` documentation in the installed source recommends
small, infrequently changing values, roughly 4 KB on average, and a ten-minute
local TTL (`redis_wrapper.py:448-476`). Approval state must not use
`frappe.client_cache`: it is a long-lived optimization cache, not a one-shot
authorization store. The approval adapter should also bound or minimize
prepared payload size in Task 38 and should not put raw business payloads in
logs.

## 6. Frappe local-cache behavior

There are three relevant cache layers:

1. `frappe.local.cache` is initialized as `{}` by `frappe.init()`
   (`__init__.py:212-216`).
2. `RedisWrapper.set_value()` writes the value into `frappe.local.cache` before
   attempting Redis (`redis_wrapper.py:72-77`).
3. `RedisWrapper.get_value()` returns `frappe.local.cache[key]` first when
   `use_local_cache=True` (`redis_wrapper.py:79-112`).

The high-level helper catches `redis.exceptions.ConnectionError` on read and
then returns `None`; it does not raise the backend failure. `set_value()` and
`delete_value()` similarly suppress connection errors. `exists()` returns
`False` on connection failure, and `get_keys()` can fall back to matching
`frappe.local.cache` keys (`redis_wrapper.py:128-163` and `:221-227`).

Frappe also has request-local caching in `frappe.local.request_cache`, created
at `__init__.py:212`, and a separate parent-process `site_cache` documented as
not shared among workers (`utils/caching.py:78-90`). The approval store does
not currently use either decorator, but a future implementation must not use
them for authorization state.

### Answer to the stale-local-cache question

Yes. An approval lookup can be incorrectly satisfied by stale
`frappe.local.cache` if it uses `frappe.cache.get_value()` with its default
`use_local_cache=True`. A persistent STDIO MCP process can retain Frappe local
state across tool calls when the site remains initialized. A direct
`set_value()` also populates that local cache even if Redis is unavailable,
which is unsafe if the caller returns a token without proving the shared write.

Task 38 must bypass local cache for every security-sensitive approval read and
claim. The safest audited boundary is to use the already-configured
`frappe.cache` connection and call its raw inherited Redis operations after
applying `frappe.cache.make_key(..., shared=False)` explicitly. If a high-level
read is retained for convenience, it must pass `use_local_cache=False` and
must have an independent backend-health/error path; it must not turn `None`
into an authorization success or silently fall back to process memory.

The Frappe client-side cache is also unsuitable. It retains values across
requests, has a local ten-minute TTL, and its own documentation says not to
use it where sub-second invalidation is required. A one-shot approval claim
requires stronger semantics.

## 7. TTL behavior

Frappe's string cache writes support `expires_in_sec`, which is passed to Redis
as the Redis `EX` option (`redis_wrapper.py:64-77`). Expiration is therefore
server-side and shared, subject to Redis availability and configuration.

Task 38 should set the approval key's Redis TTL to exactly
`APPROVAL_TTL_SECONDS` (900) at creation. It should also retain a process-stable
creation timestamp for diagnostics and any state reserialization. It must not
use the current `time.monotonic()` value as a cross-process timestamp.

When a claim rewrites an available record as consumed, it must preserve the
remaining TTL rather than resetting the full 900 seconds. An approval that
expires between validation and claim must not be claimed. A missing Redis key
is safely treated as expired/unavailable according to the existing public
mapping; no write may proceed.

There is no need for active cleanup: Redis expires the key. A consumed or
cancelled marker may remain until the original TTL so the existing
`CONFIRMATION_CONSUMED` semantics can be preserved. If the implementation
deletes consumed keys instead, consumed and expired states collapse and the
current public/test contract changes; that is not recommended.

## 8. Atomic primitive findings

### What Frappe exposes

The installed `RedisWrapper` explicitly implements convenience methods for
key/value and hashes, but no Frappe-level atomic get-and-delete,
compare-and-delete, or approval claim helper was found. It inherits
`redis.Redis` from redis-py 7.1.1, so the connection exposes `getdel`, `setnx`,
`pipeline`, `lock`, and `eval`. Those are lower-level inherited Redis APIs, not
Frappe approval primitives.

Frappe uses `frappe.cache.pipeline()` in its own two-factor code
(`apps/frappe/frappe/twofactor.py:94-109`), proving that the configured
connection can create and execute a pipeline. Frappe source search found no
existing compare-and-delete or one-shot cache helper suitable for this
authorization boundary.

### Options

| Option | Native boundary | Atomicity and race behavior | Failure behavior / complexity | Decision |
| --- | --- | --- | --- | --- |
| High-level `get_value()` then `delete_value()` | Frappe cache helpers | Non-atomic; two workers can validate the same value and both delete/continue; local cache may be stale | Suppresses connection errors; low code but unsafe | Reject |
| `GETDEL` | Inherited redis-py method on `frappe.cache` | Atomic retrieval/deletion, but validation occurs after deletion; wrong user/action/not-trusted requests consume the record and cannot preserve current states | Does not provide conditional claim; unsafe contract change | Reject |
| `SETNX` lock or marker | Inherited Redis command | Atomic marker creation but does not validate and consume one specific approved record | Requires lock lifecycle, expiry, and recovery; extra state | Not sufficient |
| Distributed `lock()` | Inherited redis-py method on configured connection | Can serialize a critical section if every operation uses the same lock key and lease | Adds lock timeout/ownership failure modes and does not remove the need for raw reads/writes | Fallback only |
| `WATCH` + `MULTI` + `EXEC` | `frappe.cache.pipeline()` plus explicit Frappe key namespace | Conditional serialized update; one concurrent `EXEC` succeeds, other watcher receives `WatchError` and fails closed/re-reads consumed state | Small private adapter; retry only boundedly and never on uncertain write outcome | Recommend |
| Lua `EVAL` compare-and-set | Inherited redis-py method on configured connection | Atomic server-side script | Custom script, serialization/key handling, deployment/debugging complexity; no Frappe helper | Not necessary |

### Recommended atomic operation

Use the existing `frappe.cache` `RedisWrapper` connection as follows, entirely
inside a private approval storage adapter:

1. derive a namespaced approval key with `make_key(..., shared=False)` after
   Frappe site initialization;
2. read the raw Redis bytes, not `get_value()` local-cache data;
3. deserialize and validate the record's action, explicit site, authenticated
   user, process-stable payload digest, TTL, cancellation, consumption, and
   trusted-human state;
4. start a Redis pipeline and `WATCH` the namespaced key;
5. read the key again through the watched connection and repeat the validation;
6. `MULTI`, write the same record with `consumed_at` set and the remaining
   original TTL, then `EXEC`;
7. on `WatchError`, do not continue to a business write. Return the safe
   consumed/unavailable result after a fresh raw read if that read is reliable;
8. on any Redis connection, serialization, or transaction uncertainty, fail
   closed. Do not claim success and do not execute the business write.

This is a minimal adapter around Frappe's configured connection, not a parallel
Redis architecture. It uses Frappe's configured host, authentication,
Sentinel support, key namespace, connection pooling, and lifecycle. It adds no
new Redis service or configuration.

`GETDEL` is not recommended even though redis-py 7.1.1 exposes it: a valid
claim is conditional on several fields and on trusted approval. A blind atomic
delete cannot validate those fields before consuming the operation. The
conditional state transition is the required atomic operation.

## 9. Concurrency analysis and required scenarios

The current implementation passes Scenario A only when both calls share the
same `ApprovalStore` object. It fails Scenario B and J by design. The target
adapter should produce these results:

| Scenario | Target result | Required reason |
| --- | --- | --- |
| A. Same-process prepare/confirm | Works | Redis-backed record is visible to the same process |
| B. Different-process prepare/confirm | Works | Both processes resolve the same Frappe cache Redis and site namespace |
| C. Simultaneous confirm | Exactly one succeeds | `WATCH`/`EXEC` allows one conditional consumed-state transition |
| D. Expired approval | No write; prepare again | Redis TTL and explicit remaining-TTL validation |
| E. Consumed token | No replay; prepare again | Consumed marker remains until original expiry |
| F. Wrong user | Fail closed | User binding is checked before the claim; no business write |
| G. Wrong site | Fail closed | Explicit site binding and Frappe namespace both apply |
| H. Wrong action | Fail closed | Exact action binding is checked |
| I. Missing trusted approval | Fail closed in `trusted_human` | `trusted_at` remains required at the shared policy boundary |
| J. Process restart | Works while key is valid | State is in shared Redis, not process memory or process signer |
| K. Redis unavailable | Fail closed; no write | Raw backend errors are not converted into missing/local approval success |

The business write must remain after the successful claim. The claim does not
make ERP persistence atomic with Redis; it intentionally prevents duplicate
writes before persistence. A post-claim ERP failure still consumes the token,
the existing database transaction may roll back, and the caller must prepare
again. This is safer than restoring a token after uncertain persistence because
restoration can enable duplicate or ambiguous writes.

## 10. Security analysis

The following current properties are preserved by the recommended design:

- opaque `secrets.token_urlsafe(32)` token;
- exact action binding;
- explicit site binding;
- authenticated Frappe-user binding;
- payload binding and digest verification;
- 900-second expiry;
- server-selected trusted-human/delegated policy;
- internal-only trusted approval recording;
- cancellation and one-shot consumption;
- stale source/document revalidation in services;
- normal Frappe/ERPNext permissions and native validation;
- safe public confirmation errors;
- no raw prepared payload accepted from confirm tools.

### Process-stable digest requirement

The current `_signing_key` is generated at `ApprovalStore.__init__`, so it is
different in every process. Persisting the current HMAC digest in Redis would
make a valid record created in Process A fail digest verification in Process B.
Task 38 must not copy this random-key behavior into shared storage.

The minimal recommended approach is a deterministic SHA-256 digest of the same
canonical JSON representation, compared with `compare_digest`. The Redis/cache
backend is already the trusted server-side state boundary; the digest detects
record/payload tampering or corruption and remains stable across workers. If a
keyed integrity guarantee against cache operators is required, Task 38 must
introduce an explicitly shared server secret through an approved existing
secret-configuration mechanism. It must not silently reuse
`MCP_HTTP_SHARED_SECRET`, `MCP_FRAPPE_USER`, a client value, or a process-random
key.

### Cache key

The public token need not change. A private key such as an approval namespace
plus a one-way SHA-256 token fingerprint is preferable to placing the raw
bearer token in a Redis key, because Redis key inspection and operational
diagnostics would not expose the bearer value. This is a concrete operational
benefit and does not replace token validation: the raw token must still be
required as the public lookup input. Frappe's site namespace and the explicit
stored site binding remain mandatory.

The key transformation is private and must be applied consistently by create,
lookup, trusted approval, claim, and cancel. It must not be presented as a new
public token format.

## 11. Failure and Redis-unavailable behavior

The installed high-level Frappe cache methods are optimized for ordinary cache
misses, not authorization:

- `get_value()` catches `ConnectionError` and can return `None`;
- `set_value()` writes local state and suppresses `ConnectionError`;
- `delete_value()` removes local state and suppresses `ConnectionError`;
- `exists()` converts connection failure to `False`;
- `get_keys()` can fall back to local keys.

Therefore:

- `create()` must not return a token unless the shared Redis write completed
  successfully. If creation is uncertain, return an internal failure that the
  existing observability boundary maps to a safe retryable error.
- `lookup()`, trusted approval recording, claim, and cancel must fail closed on
  backend errors. They must not use a stale `frappe.local.cache` record.
- A backend error must not be mapped internally to a successful `available`
  state. Public mapping may remain deliberately generic.
- A claim transaction whose result is unknown must be treated as not safely
  claimable. The service must not continue to a write.
- No automatic in-memory fallback is permitted for approval authorization.

## 12. Public error semantics audit

The current public confirmation envelope is service-specific but uses stable
codes and a new error reference. `confirmation_failure()` intentionally folds
several security-sensitive distinctions into `CONFIRMATION_UNAVAILABLE`.
Missing, wrong action, wrong site, wrong user, and payload mismatch are not
revealed separately. Expired and consumed are distinguished because the current
store retains consumed state until TTL; trusted approval has its own safe code.

The recommended public contract is unchanged. Internal operation results may
use reason codes such as:

```text
missing_or_expired
expired
consumed
cancelled
wrong_action
wrong_site
wrong_user
payload_digest_mismatch
not_trusted
backend_unavailable
watch_conflict
serialization_failure
```

Those reason codes must remain server logs/metrics only. Raw approval tokens,
full payloads, credentials, authorization headers, and shared secrets must not
be logged. A short token fingerprint is optional and should be used only if
the logging policy accepts its operational value.

## 13. Observability audit

`observability.execute_tool()` currently logs a safe error reference, code,
tool, site, and a short user fingerprint while excluding natural-language
inputs and approval tokens (`mcp_erpnext/observability.py:116-187`). Normal
service confirmation failures return their own safe error envelopes and are
not necessarily logged by `execute_tool()`.

For Task 38, add internal approval events through the existing observability
boundary or a private logger, without changing public schemas. Useful fields
are:

- process PID;
- stable server-instance ID generated at process startup, not a client ID;
- approval action;
- site;
- short authenticated-user fingerprint;
- optional short token fingerprint;
- create/claim timestamps and remaining TTL;
- result (`created`, `trusted`, `claimed`, `cancelled`, `rejected`);
- internal reason code;
- watch conflict/backend failure classification.

PID and instance ID are particularly useful for diagnosing STDIO/Codex worker
replacement and confirming that a cross-process claim was attempted. They do
not belong in the approval record or public MCP contract. Raw tokens and
payloads remain excluded.

The existing missing-log gap for returned normal confirmation errors should be
closed only if it can be done without exposing data or changing the public
envelope. This audit does not modify `observability.py`.

## 14. Redis / Frappe infrastructure boundary

Use:

- `frappe.cache` after `frappe.init(site)`;
- `RedisWrapper.make_key()` with `shared=False`;
- the configured `redis_cache` / Sentinel connection;
- raw inherited Redis operations only inside a private approval adapter where
  high-level helpers cannot meet fail-closed or atomic requirements;
- Redis server TTL and conditional state transitions.

Do not add:

- another Redis service or container;
- a new `redis://` environment variable;
- a direct `redis.Redis(...)` connection;
- new Redis credentials or packages;
- a parallel cache framework;
- a new approval database table or DocType;
- client-specific approval state.

Calling inherited methods on the already-created `RedisWrapper` is not a
parallel Redis architecture. It reuses Frappe's connection and configuration;
the adapter exists only because the installed Frappe convenience API does not
expose the conditional one-shot state transition or fail-closed error signal.

## 15. Redis cache versus Frappe DocType

| Criterion | Frappe cache / Redis | DocType / MariaDB |
| --- | --- | --- |
| Multi-process sharing | Native when workers use the same configured cache | Native through database |
| TTL | Native key expiry | Requires scheduled/lazy cleanup fields and queries |
| Atomic claim | Redis `WATCH`/`EXEC` adapter on configured connection | Transaction/row-lock design, more database-specific |
| Temporary state fit | Good; ephemeral cache data | Poorer; creates ERP database churn |
| Restart behavior | Survives MCP restart while Redis key remains | Survives restart, but is durable business-adjacent data |
| Audit history | Not intended as long-term history | Better if approval history is a business/audit requirement |
| Cleanup | Automatic TTL | Explicit cleanup/indexing required |
| Security | Trusted cache boundary; avoid logs and unsafe fallback | Normal database permissions, but larger exposure and lifecycle |
| Complexity | Small adapter plus isolated tests | New DocType/schema, permissions, migrations, cleanup, locks |

Approval records contain transient prepared operations and one-shot coordination
state, not long-term ERP business facts. Redis is the better operational fit.
A separate audit/history requirement would be a different feature and should
not be smuggled into this migration.

## 16. STDIO / HTTP / multi-worker compatibility

The target is transport-neutral because approval state remains behind the
service-level `ApprovalStore` abstraction.

- STDIO single process: works through the shared cache after site context is
  initialized.
- Multiple STDIO clients/processes: prepare and confirm can be handled by
  different processes when they resolve the same Frappe cache.
- Codex-launched child processes: process replacement no longer removes a
  valid approval, subject to shared Redis availability and the 900-second TTL.
- HTTP one or many workers: all workers use the same configured cache and the
  authenticated Frappe user remains part of the approval binding.
- Multiple MCP containers: works only when containers are configured for the
  same intended Frappe site and cache service; separate cache endpoints are
  correctly isolated.
- Sales and Purchase: shared storage works for both profiles. Action names,
  payloads, profile allowlists, and explicit profile checks prevent accidental
  cross-profile use. No profile field is required in the core record unless a
  later source audit finds an action collision.

No Codex, LibreChat, conversation, thread, run, process, or UI identifier is
needed in the core approval contract.

## 17. Profile boundary

The current profile is not a direct `ApprovalStore` field. The action constants
are already distinct for all current creation/conversion operations, and
lifecycle claims use `lifecycle_<action>`. Lifecycle and email additionally
validate the profile stored in the payload before native work. This means the
existing action/site/user/payload binding is sufficient for the current
inventory.

Task 38 should not add a profile field or public profile binding without a
demonstrated collision. It should preserve the existing payload profile checks
and action namespace. The explicit site field remains required even though
Frappe's cache key is also namespaced.

## 18. Public MCP contract boundary

The migration can preserve the current public boundary:

- no tool rename;
- no prepare input schema change;
- no confirm input schema change;
- no public approval-token format change;
- no business-service Redis dependency;
- no profile inventory change;
- no change to `InteractionDirective` or approval actions;
- no public `approval_mode`, `trusted_at`, or trusted-approval method.

Only private storage details change: key derivation, serialization/timestamps,
backend access, stable digest handling, and atomic claim state. `docs/TOOLS.md`
and MCP `tools/list` should remain unchanged unless implementation changes
require a documentation regeneration check.

## 19. Exact files expected to change in Task 38

Required implementation/test scope:

- `mcp_erpnext/approvals.py` — shared storage adapter, stable serialization/
  digest, Redis TTL, raw fail-closed operations, and atomic claim.
- `mcp_erpnext/tests/test_approvals.py` — backend-mocked unit tests, two-store
  visibility, state transitions, failure handling, and concurrency/transaction
  behavior.
- Existing service tests that access `_approvals` internals must be adapted to
  a private test backend seam rather than relying on a process dictionary:
  `tests/test_customer_service.py`, `test_item_service.py`,
  `test_quotation_service.py`, `test_sales_invoice.py`,
  `test_sales_order_to_sales_invoice.py`,
  `test_quotation_to_sales_order.py`, `test_purchase_order_service.py`,
  `test_lifecycle.py`, and `test_email.py`.

Likely active documentation updates, if the project keeps these deployment
statements current:

- `docs/architecture/MCP_EXPLICIT_USER_APPROVAL_SAFETY.md`;
- `docs/architecture/MCP_TOOL_CONTRACT_ARCHITECTURE.md`;
- `docs/architecture/MCP_DOCUMENT_EMAIL.md`;
- `docs/MCP_PROFILES.md`;
- `docs/testing/POSTMAN_MCP_HTTP_TESTING.md`;
- `docs/ERPNext_MCP_ARCHITECTURE.md`;
- `docs/guides/MCP_SYSTEM_HUMAN_GUIDE_HINGLISH.md`.

Historical implementation/audit reports should not be rewritten merely to
remove historical facts. If the project requires a current-status annotation,
add it deliberately and separately.

`runtime.py`, `settings.py`, `profiles/**`, `contracts/**`, `tools/**`, and
`docs/TOOLS.md` do not need behavior or schema changes for the recommended
storage migration. A runtime readiness check may be considered only if tests
show that Frappe site initialization is not guaranteed before an approval
operation.

## 20. Exact files that must remain untouched by Task 38

Unless a separate approved requirement is added, Task 38 must not change:

- ERPNext business services or their native validation/mapping rules;
- `mcp_erpnext/contracts/**`, public tool schemas, or profile registries;
- `mcp_erpnext/tools/**` and MCP transport identity code;
- `mcp_erpnext/settings.py` approval modes or TTL policy;
- Frappe or ERPNext source under `apps/frappe` and `apps/erpnext`;
- India Compliance, `mcp_identity`, LibreChat, LangGraph, or Codex code;
- `sites/site_config.json`, `sites/common_site_config.json`, hooks, or Redis
  configuration;
- database schema, DocTypes, migrations, or ERP records;
- external service definitions, Docker files, dependencies, or credentials;
- Git history, commits, deployment, process restarts, or cache flushes.

The report itself is the only file created by this audit.

## 21. Required Task 38 tests

### Unit and backend-seam tests

Use a fake shared backend or mocked `RedisWrapper`; do not require a live Redis
server for the default unit suite. Cover:

- create stores the record through the shared backend;
- no token is returned after a backend write failure;
- exact 900-second TTL is set;
- creation timestamp is process-stable and not monotonic-process-local;
- action/site/user/payload binding remains enforced;
- digest verification is stable across independent `ApprovalStore` instances;
- trusted-human state is required and delegated mode changes only that policy;
- trusted approval remains action/site/user/payload-bound;
- cancel preserves consumed/cancelled semantics;
- wrong action/user/site fails without consuming a valid record;
- expired, consumed, malformed, and digest-invalid records fail safely;
- cache backend read/write/serialization/transaction failures fail closed;
- no lookup path consults stale `frappe.local.cache`.

### Cross-instance and concurrency tests

Create independent store instances representing separate processes:

```text
store A create
store B claim
```

The claim must succeed under the same site/user/action and policy.

Then verify:

```text
store A create
store A claim
store B claim
```

The first claim succeeds and the second returns consumed/unavailable without a
second write path. Use two concurrent clients against the fake transactional
backend and assert exactly one successful `EXEC`/claim. Include a forced
`WatchError` and an uncertain backend result; neither may continue to a
business write.

### Regression and contract tests

Run the existing approval-backed service coverage for Customer, Item,
Quotation, Sales Order, Sales Invoice, both native conversions, lifecycle
update/child-add/submit/cancel/delete, Purchase Order, and document email.
PDF remains read/render-only and should not acquire an approval requirement.

Verify registered names and public schemas remain unchanged through the existing
profile, tool-registration, contract-audit, and generated-catalog checks.

## 22. Risks and limitations

- Frappe cache is shared only when all workers resolve the same cache endpoint
  and intended site namespace. Configuration drift correctly creates isolation.
- Redis is ephemeral and subject to eviction or restart. A missing key must
  require a fresh prepare; approval state is not durable audit history.
- Redis/cache claim and ERP database commit are separate systems. Consuming
  before the write prevents duplicate confirms but means a post-claim business
  failure requires re-prepare.
- Frappe's high-level helpers are deliberately forgiving about cache outages;
  the approval adapter must not inherit that fail-open ambiguity.
- Pickle is the installed Frappe cache serialization convention. The cache
  backend must be treated as trusted, and payloads must be bounded and kept out
  of logs.
- A deterministic digest preserves cross-worker binding but is not a secret
  MAC against an attacker who can both alter the cache payload and digest. A
  stronger threat model requires an explicitly shared server secret and a
  separate configuration decision.
- The current tests inspect `_approvals` directly and will need a private test
  backend seam; this is test maintenance, not a public contract change.
- No live Redis transaction or multi-worker MCP run was performed. The atomic
  recommendation is source-backed and must receive the isolated fake-backend
  and, where available, dedicated temporary-key runtime coverage in Task 38.

## 23. Final decision

```text
DECISION:
Use the existing Frappe cache/Redis infrastructure.

No new Redis service.
No custom Redis connection.
No new approval DocType.

Frappe's high-level cache helpers are sufficient for ordinary storage and TTL
but do not expose the conditional one-shot primitive or fail-closed backend
error behavior required by ApprovalStore.

Use the smallest possible internal adapter around the existing Frappe
RedisWrapper connection for:
  - explicitly namespaced raw reads/writes;
  - exact 900-second Redis TTL;
  - process-stable payload digest validation;
  - WATCH/MULTI/EXEC compare-and-set from available to consumed;
  - trusted/cancelled state transitions with the original remaining TTL.

Local request/cache handling:
  bypass frappe.local.cache and frappe.client_cache for all approval
  authorization reads and claims; never fall back to process memory.

TTL:
  preserve APPROVAL_TTL_SECONDS = 900 seconds, with Redis expiry authoritative
  and remaining TTL preserved when rewriting consumed/cancelled state.

Failure behavior:
  fail closed; backend errors, serialization failures, watch conflicts with
  uncertain state, and missing/expired/mismatched records must never authorize
  a business write.

Public MCP contracts:
  unchanged.
```

## Exact next task

`Task 38 — Implement Frappe-Native Shared ApprovalStore`

Task 38 must implement the adapter and tests described above, preserve the
existing service interface and 900-second policy, handle the process-stable
digest issue explicitly, and produce an implementation report. It must not
change business tools, public schemas, profiles, Redis infrastructure, or
database records.
