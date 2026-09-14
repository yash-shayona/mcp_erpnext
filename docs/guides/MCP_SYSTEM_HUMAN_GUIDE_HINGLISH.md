# MCP ERPNext system guide — Hinglish

Yeh guide un developers aur admins ke liye hai jinhone system build nahi kiya
hai. Isko zero se padho: pehle basic terms, phir dono apps, phir ek request ka
complete journey.

## Sabse pehle: system kya karta hai?

ERPNext business application hai. Ismein Customer, Supplier, Item, Quotation,
Sales Order aur Purchase Order jaise business documents hote hain. Frappe woh
framework hai jo ERPNext ko chalata hai: site/database connection, DocTypes,
document lifecycle, users, Roles, User Permissions, validation aur permission
checks Frappe/ERPNext control karte hain.

MCP, ya Model Context Protocol, ek standard interface hai jiske through koi
client server ke tools discover aur call kar sakta hai. MCP server ek process
hai jo protocol messages receive karke controlled tools expose karta hai. MCP
client woh program hai jo server se connect hota hai.

AI/LLM client-side intelligence ho sakti hai, lekin MCP server khud LLM nahi
hai. Server natural language samajhne ke bajay typed arguments validate karta
hai, ERPNext rules/permissions apply karta hai aur structured result deta hai.
Agent ya client user ki baat ko tool call mein badalta hai.

## Hamare do apps

### mcp_identity

mcp_identity ko security gate samjho. HTTP request mein do important cheezein
aati hain:

~~~http
Authorization: Bearer <server-configured-secret>
X-MCP-User-Email: person@example.com
~~~

Pehle shared Bearer secret verify hota hai. Uske baad email se existing aur
enabled Frappe User resolve hota hai. Missing, malformed, unknown, disabled, ya
unauthenticated identity fail closed hoti hai.

Is app ka kaam user ko identify karna hai. Yeh ERPNext business logic,
DocTypes, roles, MCP tool permissions, LibreChat mapping, ya approval UI own
nahi karta. Actual Frappe permission check consumer app, yahan mcp_erpnext,
normal Frappe APIs ke through karta hai.

### mcp_erpnext

mcp_erpnext controlled ERPNext capabilities ko MCP tools ke roop mein expose
karta hai. Ismein profile selection, MCP wrappers, contracts, resolvers,
workflow services, approval guard, runtime bootstrap aur observability hain.

Yeh generic ERPNext CRUD, arbitrary SQL, arbitrary DocType access, ya
Administrator bypass nahi hai. Tool list fixed profile se aati hai aur har tool
ka input/output contract defined hai.

## Puri request journey

~~~text
Client / Agent / Postman
        |
        | HTTP Streamable HTTP ya stdio
        v
MCP transport + JSON-RPC
        |
        v
Bearer check (HTTP)
        |
        v
MCP tool registry
        |
        v
Request se X-MCP-User-Email copy
        |
        v
mcp_identity -> enabled Frappe User
        |
        v
Frappe site init/connect + set_user
        |
        v
Typed MCP wrapper
        |
        v
Domain service / resolver
        |
        v
Normal Frappe permissions + ERPNext validation
        |
        v
Structured MCP result
        |
        v
HTTP response; HTTP tool scope ke baad Frappe state clear
~~~

HTTP mein Bearer middleware endpoint tak aane wali request ko pehle check karta
hai. Protocol handshake (initialize, tools/list) mein current code Frappe user
lookup nahi karta. Jab actual tool execute hota hai, runtime.py request headers
se identity copy karta hai; mcp_identity user resolve karta hai; Frappe site
connect hoti hai aur resolved user set hota hai.

Uske baad wrapper typed input ko service payload mein convert karta hai. Service
business validation aur permitted-record lookup karta hai. Frappe roles aur
record permissions final authority hain. Result client ko wapas jaata hai.
HTTP tool call ke around Frappe local state clear hoti hai, taaki agla request
pichhle user ya site context ko accidentally reuse na kare.

## Transport ka matlab

### Streamable HTTP

HTTP mode mein MCP server ek independent process hai. Client connect karne se
pehle server listening hona chahiye. Current default endpoint
http://127.0.0.1:8765/mcp hai, lekin host, port aur path environment se change ho
sakte hain.

Current SDK stateful session use karta hai. Client initialize se protocol
version aur capabilities negotiate karta hai, response ka server-generated
mcp-session-id save karta hai, phir notifications/initialized, tools/list, aur
tool calls mein wahi session ID bhejta hai. Current app SSE response mode use
karti hai, isliye raw HTTP response mein event: message aur data: {...} dikh
sakta hai.

### stdio

stdio mode mein compatible MCP client process ko launch karke stdin/stdout par
baat kar sakta hai. Current local development flow mein MCP_FRAPPE_USER
configured service user ke roop mein use ho sakta hai. Postman stdio ko directly
test nahi karta.

HTTP aur stdio ko mix mat samjho: HTTP caller identity request header se aati
hai; HTTP kabhi MCP_FRAPPE_USER ko fallback ke roop mein use nahi karta.

## Server kaise start hota hai

Safe local Streamable HTTP example:

~~~bash
export MCP_BACKEND=direct
export MCP_FRAPPE_SITE=your-site.localhost
export MCP_TRANSPORT=streamable-http
export MCP_PROFILE=sales
export MCP_HTTP_HOST=127.0.0.1
export MCP_HTTP_PORT=8765
export MCP_HTTP_PATH=/mcp
export MCP_HTTP_SHARED_SECRET='<minimum-32-character-development-secret>'
export MCP_HTTP_ALLOWED_HOSTS='127.0.0.1:8765,localhost:8765'

cd /home/frappe/frappe-bench/sites
../env/bin/python -m mcp_erpnext.mcp_server
~~~

MCP_FRAPPE_SITE selected Frappe site hai. MCP_BACKEND=direct current
implemented backend hai. REST settings source mein future boundary ke liye
hain; current server unko use nahi karta.

HTTP endpoint ko public internet par expose mat karo. Plain HTTP local bridge
development ke liye hai; production deployment ko TLS, firewall, secret
management, process model aur shared approval storage separately design karna
chahiye.

## Profiles: Sales aur Purchase

Ek hi app MCP_PROFILE ke through ek process ka public inventory select karti hai:

| Profile | Capabilities |
| --- | --- |
| sales (default) | Customer, sales-enabled Item, Quotation, Sales Order, lifecycle aur existing Sales Order/Quotation reads |
| purchase | Supplier, purchase-enabled Item, Purchase Order, lifecycle aur existing Purchase Order reads |

Profile tool argument nahi hai. Yeh process startup configuration hai. Dono
profiles ek saath chahiye to separate processes aur ports use karo. Profile
boundary ke bahar ka tool server expose nahi karta.

## MCP protocol mein tools kaise milte hain

Client pehle initialize se protocol version aur server capabilities negotiate
karta hai. Phir notifications/initialized bhejta hai. tools/list response se
actual tool names, description, inputSchema, aur current typed tools ke liye
outputSchema milte hain.

Uske baad tools/call mein exact name aur arguments bheje jaate hain:

~~~json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "search_customers",
    "arguments": {"query": "Acme"}
  }
}
~~~

Postman mein yeh sab manually karna padta hai. Inspector protocol samajhkar
sequence automate karta hai. LibreChat/VS Code jaise clients language aur
workflow orchestration bhi de sakte hain, lekin business safety server ki
responsibility rehti hai.

## Tools ko chaar categories mein samjho

mcp_erpnext contract metadata har tool ka side-effect class batata hai:

| Category | Meaning |
| --- | --- |
| READ | Permitted records search/read; data create ya change nahi hota. |
| RESOLVE | Exact ya candidate reference resolve/revalidate; ambiguous result ko guess nahi karta. |
| PREPARE | Validation aur preview; final persistent write nahi. |
| CONFIRM_WRITE | Final write/action boundary; shared approval guard aur Frappe permission re-check ke baad hi action. |

### Search aur resolve

search_customers, resolve_customer, search_items, resolve_item, aur Purchase
profile ke Supplier equivalents permitted records par kaam karte hain. Resolver
ke terminal states resolved, ambiguous, not_found, aur safe error hain.

ambiguous ka matlab hai system ko multiple possible records mile. Ranking sirf
presentation help hai; first ya highest-score candidate automatically select
nahi hota. Client ko user se choice leni hoti hai. Phir
select_resolved_candidate exact Customer/Item reference ko current permissions
ke saath dobara check karta hai.

### Prepare

Quotation/Purchase Order prepare mein resolved party aur Item references,
quantity, dates aur optional commercial fields typed form mein jaate hain.
Service ERPNext defaults/calculations apply karke unsaved preview banata hai.
Result needs_input, permission_denied, error, ya ready ho sakta hai.

ready preview ko human ko dikhana chahiye. Ismein approval token aur expiry mil
sakti hai, lekin token khud approval nahi hai. Prepare se Draft document save
nahi hota.

Existing-document lifecycle tools exact document ke update, child item add,
submit, cancel, aur delete actions ko bhi prepare/confirm flow mein rakhte hain.
Yeh arbitrary filters se parent documents mutate nahi karte; target aur profile
allowlist validate hoti hai.

## Conversation aur interaction ka boundary

Server deterministic hai. Conversation history, natural-language parsing, user
ke haan/no, UI button, chat ID, ya LLM state server store nahi karta. Shared
InteractionDirective sirf semantic guidance deta hai:

~~~json
{
  "required": true,
  "kind": "SELECTION",
  "allowed_actions": ["SELECT", "CANCEL"],
  "reason_code": "AMBIGUOUS_REFERENCE",
  "instructions": "Select exactly one candidate."
}
~~~

Kinds SELECTION, INPUT, APPROVAL hain. Actions SELECT, PROVIDE_INPUT, MODIFY,
APPROVE, REJECT, CANCEL hain. Yeh values UI controls ya fixed phrases nahi hain.

Agent/client natural language ko semantic action aur typed tool input mein
convert karta hai. Agar preview modify karna ho, purana preview approve nahi
karna: pending action reject/cancel karke changed input se fresh prepare karna
hai.

## Approval aur write safety

Creation/action ka intended flow:

~~~text
resolve -> validate -> prepare -> preview -> explicit approval -> confirm -> ERPNext action
~~~

confirm: true sirf confirm step ki request hai. Isko human approval mat samjho.

Default MCP_APPROVAL_MODE=agent_delegated hai: trusted Agent/client explicit
user approval ke baad hi confirm call kar sakta hai. Is mode mein bhi token,
action, site, authenticated user, payload digest, 15-minute expiry, cancellation,
single-use atomic claim, aur final Frappe permission check enforce hote hain.

Sirf explicitly MCP_APPROVAL_MODE=trusted_human set karne par server ko
independently authenticated human approval record chahiye jo exact token,
action, site, user, payload digest aur pending operation se bound ho. Current
internal record_trusted_user_approval() MCP tool ya public argument nahi hai.
Isliye raw Postman/Gemini/model-generated confirmation trusted_human mode mein
fail closed hoti hai, aam taur par TRUSTED_APPROVAL_UNAVAILABLE ke saath.

Approval store Frappe ke configured shared Redis cache mein hai. Same site/cache
use karne wale alag worker ya restarted process pending token ko use kar sakte
hain; Redis expiry ya loss par fresh prepare chahiye.
Final writes ko sirf authorized development/test site par manually verify karo.

## Permissions kaise kaam karti hain

Bearer secret valid hone ka matlab sirf itna hai ki configured MCP client ko HTTP
endpoint tak aane diya gaya. X-MCP-User-Email se enabled Frappe User resolve
hota hai. Us user ke Roles, User Permissions, DocType permissions aur record
permissions hi decide karte hain ki search/read/prepare/confirm allowed hai ya
nahi.

Caller tool arguments mein frappe_user, run_as, role, Administrator ya secret
dekar identity change nahi kar sakta. HTTP MCP_FRAPPE_USER fallback nahi hai.
Permission failure ko bypass karne ke liye direct SQL ya ignore_permissions=True
use nahi kiya jaata.

## Errors ko layer ke hisaab se padho

| Layer | Typical signal | Simple meaning |
| --- | --- | --- |
| Network | Connection refused | Server running nahi hai ya host/port unreachable hai. |
| HTTP auth | 401 | Bearer secret/header problem. |
| Host security | 421 | Host allowlist mein nahi hai. |
| Origin security | 403 | Supplied Origin allowlist mein nahi hai; Postman mein Origin omit karo. |
| Identity | MCP_USER_IDENTITY_MISSING, MCP_USER_NOT_FOUND, MCP_USER_DISABLED | Caller valid Frappe user nahi ban saka. |
| MCP protocol | 400/404 | JSON-RPC, version, ya session mismatch. |
| Tool contract | Schema/invalid params error | Tool name ya arguments tools/list schema se match nahi karte. |
| Frappe permission | ERP_PERMISSION_DENIED / PERMISSION_DENIED | Resolved user ko requested access nahi hai. |
| Domain | INVALID_CUSTOMER, INVALID_ITEM, INVALID_QUOTATION_DETAILS, business validation code | ERPNext/MCP rules ne data reject kiya. |
| Approval | TRUSTED_APPROVAL_UNAVAILABLE, CONFIRMATION_EXPIRED, CONFIRMATION_UNAVAILABLE | Final protected action guard ne request roki. |

Safe error response mein stable code, safe message, retryable, aur MCP-ERR-...
reference milta hai. Reference se server log correlate karo. Public response
mein stack trace, secret, Authorization header, SQL ya private database detail
nahi aani chahiye.

## Clients ka role

~~~text
Postman       = manual HTTP/MCP protocol operator
MCP Inspector = MCP-aware discovery/debug client
VS Code       = coding-agent workflow ka MCP client
LibreChat     = chat/Agent client jo MCP tools use karta hai
~~~

Sab clients same mcp_erpnext server/profile se tools consume kar sakte hain,
lekin startup aur identity wiring alag ho sakti hai. HTTP clients ke liye
server pehle se running hona chahiye. Compatible MCP client stdio process khud
launch kar sakta hai. Postman MCP orchestrator nahi hai.

## Current source map

Yeh explanation in actual implementation areas par based hai:

- mcp_identity/identity.py — Bearer validation, generic email header aur enabled Frappe User lookup.
- mcp_identity/README.md — identity app responsibility boundary.
- mcp_erpnext/mcp_server.py — FastMCP construction, profile registration, stdio/HTTP startup.
- mcp_erpnext/settings.py — environment defaults and validation.
- mcp_erpnext/http_transport.py — HTTP shared-secret middleware.
- mcp_erpnext/runtime.py — Frappe context and per-request identity.
- mcp_erpnext/tools/ and mcp_erpnext/contracts/ — public wrappers and typed contracts.
- mcp_erpnext/services/ — business validation, resolution and persistence.
- mcp_erpnext/approvals.py — shared Frappe-cache pending-operation guard.
- [TOOLS.md](../TOOLS.md) — generated profile inventory.
- [MCP_CONVERSATIONAL_INTERACTION_CONTRACT.md](../architecture/MCP_CONVERSATIONAL_INTERACTION_CONTRACT.md) — interaction responsibility split.
- [MCP_EXPLICIT_USER_APPROVAL_SAFETY.md](../architecture/MCP_EXPLICIT_USER_APPROVAL_SAFETY.md) — approval safety boundary.

## Important operational note

Installed runtime facts currently are Python 3.14.3, Frappe 16.25.0, ERPNext
16.15.0, MCP SDK 1.29.0, Pydantic 2.12.5, mcp_identity 0.0.1 and
mcp_erpnext 0.0.1. These are environment facts, not permanent protocol
guarantees.

During this documentation pass, a no-write in-process HTTP probe emitted the
installed SDK warning IncompleteFieldDefinitionWarning: Field 'lifespan' has an
incomplete definition and did not finish initialize within 30 seconds.
Therefore live HTTP/ERPNext behavior should be rechecked in the target bench;
this guide does not claim that a database write or live Postman workflow was
verified.
