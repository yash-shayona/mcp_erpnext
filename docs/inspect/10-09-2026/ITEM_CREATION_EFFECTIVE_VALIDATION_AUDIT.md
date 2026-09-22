# Item Creation Effective Validation Audit

Audit date: 2026-09-10

Scope: source inspection and read-only runtime inspection only. No production
code, public contract, schema, configuration, hook, test, migration, fixture,
or database record was changed for this audit.

## 1. Executive Summary

The current Item creation flow is a generic, permission-aware, two-phase flow,
but its preflight is narrower than the effective Item validation performed at
write time.

The immediate HSN/SAC failure is proven. India Compliance adds
Item.gst_hsn_code as a runtime Custom Field with mandatory_depends_on, and
registers india_compliance.gst_india.overrides.item.validate on Item validate.
The current MCP Item capability does not accept or carry gst_hsn_code, and the
shared creation helper only checks static reqd; it records mandatory_depends_on
fields as informational conditional_fields without evaluating them. Because MCP
policy makes the prepared Item a sales Item, the India Compliance validator sees
is_sales_item as true during confirmation and raises frappe.MandatoryError when
HSN/SAC is blank.

The recommended boundary is a small generic effective-requirements/preflight
layer plus isolated optional-app providers. Core metadata/default resolution
should remain generic. India Compliance knowledge should be isolated behind a
provider that is loaded only when the app is installed and evaluates the
provider's own authoritative settings and applicable Item state. The provider
may collect a known missing input before approval, but confirmation must still
use the normal frappe.get_doc(...).insert(ignore_permissions=False,
ignore_mandatory=False) path so Frappe and installed-app validators remain the
final authority.

No public extra_fields dictionary or globally mandatory HSN field is
recommended. The existing legacy prepare_item contract may remain unchanged
for the next focused implementation; its structured needs_input result can be
extended only through the already-established interaction-contract migration
decision.

## 2. Current Item Creation Flow

### Source and runtime context

The inspected source versions are Frappe 16.33.1, ERPNext 16.34.2, and India
Compliance 16.8.4 from:

~~~text
apps/frappe/frappe/__init__.py:58
apps/erpnext/erpnext/__init__.py:9
apps/india_compliance/india_compliance/__init__.py:4
~~~

The bench sites/apps.txt includes India Compliance. Read-only active-site checks
showed:

| Site | Installed applications relevant to this audit | Effective Item metadata |
| --- | --- | --- |
| yob.localhost | Includes erpnext, india_compliance, mcp_erpnext, and mcp_identity | Contains gst_hsn_code with the conditional rule |
| praveg.localhost | Includes frappe, erpnext, hrms, crm, praveg, insights | No India Compliance HSN field in the inspected Item metadata |

The active yob.localhost GST Settings read returned [1, "6"], meaning
validate_hsn_code is enabled and min_hsn_digits is 6. This is runtime evidence
for that site only, not a default to impose on other sites.

### Call flow

~~~text
MCP tools/masters/item.py
  search_items(query, ctx)
    -> execute_tool_with_context(ctx, "search_items", ...)
    -> runtime.py::_run_stdio_tool or _run_http_tool
    -> ensure_context(...): authenticate, initialize Frappe, set user
    -> services/masters/item.py::search_items
    -> _search_items(query, item_config.SEARCH_FILTERS)
    -> entity_resolution.find_candidates("Item", ...)
       with normal permission-aware Frappe list lookup
    -> _classify_item_candidates
    -> typed resolver wrapper adds selection InteractionDirective when ambiguous

  resolve_item(query, ctx)
    -> same runtime/context path
    -> services/masters/item.py::resolve_item_for_workflow
    -> resolve_sales_item
    -> find_candidates + _classify_item_candidates
    -> resolved / ambiguous / not_found public state

  prepare_item(item, ctx)
    -> execute_tool_with_context(ctx, "prepare_item", ...)
    -> services/masters/item.py::prepare_item
    -> _current_user
    -> _item_data
       -> narrow item_config.CREATION_FIELDS input projection
       -> common.creation_contract.resolve_creation_contract
          -> frappe.get_meta("Item")
          -> frappe.new_doc("Item") for runtime defaults
          -> user input > MCP policy > new-document defaults
          -> static reqd missing-field detection
       -> common.field_value_resolver.resolve_contract_values
          -> metadata-driven scalar/link/select/boolean resolution
    -> Item create permission check
    -> permission-aware duplicate Item-code lookup
    -> approvals.create(action="create_item", site, user, payload)
    -> ready preview plus private approval token

  confirm_item(approval_token, confirm, ctx)
    -> execute_tool_with_context(ctx, "confirm_item", ...)
    -> services/masters/item.py::confirm_item
    -> _current_user
    -> approvals.claim_for_confirm_write(...)
       -> validates action/site/user/payload digest/TTL/policy
       -> consumes the approval before persistence
    -> Item create permission recheck
    -> permission-aware duplicate Item-code lookup
    -> frappe.get_doc(approval.payload)
    -> Document.insert(ignore_permissions=False,
                       ignore_links=False,
                       ignore_mandatory=False)
       -> Frappe defaults, permission and link checks
       -> before_insert
       -> run_before_save_methods -> validate hooks/controller
       -> Frappe document validation
       -> database insert and after_insert
    -> frappe.db.commit()
    -> created Item reference
~~~

The public functions are registered in mcp_erpnext/tools/masters/item.py:39-66.
search_items and resolve_item use typed resolver output models;
prepare_item and confirm_item remain in the frozen legacy inventory in
mcp_erpnext/contracts/registry.py:164-175 and :289-305, so their wrapper
arguments/results are still raw dictionaries.

resolve_item does not create a record. An unresolved Item can continue into the
controlled creation path only after the caller has decided to create it:

~~~text
not_found -> prepare_item -> needs_input or ready
          -> trusted explicit approval -> confirm_item -> Item insert
~~~

### Search and resolution details

The sales resolver uses item_config.SEARCH_FILTERS:
disabled != 1 and is_sales_item = 1. It ranks permission-scoped candidates
through services/common/entity_resolution.py:140-170 and applies the Item-only
weak-candidate policy in services/masters/item.py:100-120. The purchase wrappers
reuse the service with is_purchase_item = 1 filters and do not create Items.

## 3. Current Metadata-Driven Requirement Logic

The current implementation is in mcp_erpnext/services/common/creation_contract.py
and is called for Item by mcp_erpnext/services/masters/item.py:_item_data.

### What it does

1. Calls frappe.get_meta(doctype) directly through the injected get_meta callable
   at creation_contract.py:69. Frappe Meta processing merges Custom Fields and
   applies Property Setters at frappe/model/meta.py:175-177.
2. Creates an unsaved frappe.new_doc(doctype) and reads values from it at
   creation_contract.py:71-84.
3. Applies precedence: user input, explicit MCP policy, then runtime default.
4. Iterates only the configured creation_fields tuple. Item's tuple is
   item_code, item_name, item_group, stock_uom, is_stock_item, and is_sales_item
   at config/masters/item.py:18-27.
5. Treats a field as missing only when metadata has truthy reqd and no resolved
   value at creation_contract.py:100-107.
6. Records truthy mandatory_depends_on as descriptive conditional_fields but
   does not evaluate the expression or add it to missing at :86-99.
7. Resolves populated values using runtime field metadata and normal
   permission-aware link lookup through field_value_resolver.py:496-524.

### What it does not do

- It does not inspect Custom Field or Property Setter rows directly; it relies on
  merged frappe.get_meta output.
- It does not evaluate mandatory_depends_on or depends_on.
- It does not inspect hidden, read_only, or visibility conditions to infer a
  creation requirement.
- It does not run the Item controller validate method or document-event hooks
  during preparation.
- It does not distinguish a controller-enforced requirement from static metadata.
- It does not apply fetch_from values during preparation. Frappe's normal link
  validation can fetch values during confirmation, but prepare_item does not
  call that lifecycle.
- It does not support fields outside the narrow configured creation allowlist.
  The Item service filters input to CREATION_FIELDS at item.py:190-196.

The Item capability supplies is_sales_item=1 as MCP policy in
config/masters/item.py:35-37; the input cannot override it through the current
service. The preview repeats that effective state at
services/masters/item.py:260-269.

The server-side Frappe mandatory checker is also static in the inspected version:
frappe/model/base_document.py:939-983 iterates meta fields with reqd, while
Document._validate at frappe/model/document.py:827-839 invokes that checker.
The presence of mandatory_depends_on in merged metadata therefore does not by
itself make the server checker report this field.

## 4. Exact HSN/SAC Failure Path

The failure is confirmed in the existing logs/mcp_erpnext.log and is consistent
with the installed source:

~~~text
confirm_item
  -> mcp_erpnext/services/masters/item.py:323
       frappe.get_doc(approval.payload)
  -> :324
       doc.insert(ignore_permissions=False,
                  ignore_links=False,
                  ignore_mandatory=False)
  -> frappe/model/document.py:479
       _validate_links()
  -> frappe/model/document.py:486-487
       run_before_save_methods(); _validate()
  -> frappe/model/document.py:1411
       self.run_method("validate")
  -> India Compliance doc event from hooks.py:160
       india_compliance.gst_india.overrides.item.validate
  -> india_compliance/gst_india/overrides/item.py:9-11
       update_hsn_code(doc)
       validate_hsn_code(doc)
       set_taxes_from_hsn_code(doc)
  -> :25-30
       if doc.is_sales_item: _validate_hsn_code(doc.gst_hsn_code)
  -> india_compliance/gst_india/doctype/gst_hsn_code/gst_hsn_code.py:115-125
       get_hsn_settings(); blank code -> frappe.throw(..., frappe.MandatoryError)
~~~

The logged exception is:

~~~text
frappe.exceptions.MandatoryError:
HSN/SAC Code is required. Please enter a valid HSN/SAC code.
~~~

The logged MCP references include MCP-ERR-20C7F444, MCP-ERR-F6D99279, and later
references for the same failure family. The observability layer maps an
unexpected exception from confirm_item to the safe public ERP_REQUEST_FAILED
envelope and logs only operational metadata
(mcp_erpnext/observability.py:151-188). The ordinary client therefore does not
receive the internal validator name or stack trace.

The immediate failing function is India Compliance's
gst_hsn_code.validate_hsn_code, not the approval guard and not the core static
mandatory checker. The architectural cause is earlier: prepare_item does not
carry gst_hsn_code in its accepted field set and does not evaluate the
conditional requirement before issuing approval.

The approval token is claimed/consumed before the insert at approvals.py:121-140.
A failed validation rolls back the database in confirm_item, but the consumed
approval is not reusable; the caller must prepare again after supplying missing
data.

## 5. India Compliance Source Findings

### Hook and Item integration

The installed India Compliance app registers the Item client script and server
event:

- india_compliance/hooks.py:61-62 registers gst_india/client_scripts/item.js.
- india_compliance/hooks.py:160-161 registers
  india_compliance.gst_india.overrides.item.validate for Item validate.

The server validator at gst_india/overrides/item.py:8-11 performs three actions:
it may copy a cross-app HSN value from frappe.flags, validates HSN/SAC, and if a
nonblank code is present and the Item has no taxes, loads GST HSN Code and copies
its taxes to the Item.

The Item-specific gate is explicit at overrides/item.py:25-30: HSN validation
is skipped when doc.is_sales_item is false. The validator does not require HSN
merely because the app is installed.

### Runtime Custom Field

India Compliance defines the Item field in
gst_india/constants/custom_fields.py:1285-1297:

~~~text
fieldname: gst_hsn_code
fieldtype: Link
options: GST HSN Code
fetch_from: item_group.gst_hsn_code
fetch_if_empty: 1
mandatory_depends_on: eval:gst_settings.validate_hsn_code && doc.is_sales_item
reqd: not set (therefore false in merged metadata)
~~~

The app creates these fields during post-install setup through
gst_india/setup/__init__.py:33-50, which gathers the installed Custom Field
definitions at :331-347. The current yob.localhost merged metadata confirms the
same field and condition, with reqd=0, fetch_from=item_group.gst_hsn_code, and
fetch_if_empty=1.

### Client-side behavior

gst_india/client_scripts/item.js:1-16 configures the HSN link query and, when a
code is entered, reads the GST HSN Code document to populate Item taxes. The
client script is not the authoritative server requirement and is not run by the
MCP process.

## 6. GST Settings Findings

The relevant fields are declared in
india_compliance/gst_india/doctype/gst_settings/gst_settings.json:125-138:

- validate_hsn_code: Check, default 1, described as validation for sales Items and
  transactions.
- min_hsn_digits: Select, default 6, options 4, 6, 8, and
  mandatory_depends_on eval: doc.validate_hsn_code.

The server setting reader is india_compliance/gst_india/utils/__init__.py:489-500:

~~~text
frappe.get_cached_value(
    "GST Settings", "GST Settings",
    ("validate_hsn_code", "min_hsn_digits")
)
~~~

It converts the minimum to an integer and keeps lengths from
VALID_HSN_LENGTHS=(4, 6, 8) that are at least that minimum. Thus:

| validate_hsn_code | min_hsn_digits | Accepted lengths by this helper |
| --- | --- | --- |
| false | any | no HSN/SAC check by this validator |
| true | 4 | 4, 6, 8 |
| true | 6 | 6, 8 |
| true | 8 | 8 |

The active yob.localhost values are 1 and 6, so the effective lengths for that
site are 6 and 8.

The code uses Frappe's cached single-value lookup; it does not maintain a
separate MCP cache. A settings update therefore follows Frappe's normal cache
invalidation behavior. The source has no explicit MCP fallback for a missing
GST Settings document. A null validation flag skips this rule; a null minimum
is converted by cint to zero and leaves the standard lengths. A missing settings
document or database/configuration failure should be treated as an
environment/configuration error, not silently interpreted as permission to
bypass an active app validator.

The lookup is against the single global GST Settings document and accepts no
company argument. The inspected Item requirement is therefore global for the
site, while the sales-item gate is evaluated from each effective Item state.

gst_hsn_code.validate_hsn_code at :115-133 does the final field checks:

- validation disabled: return without requiring or length-checking the code;
- blank code with validation enabled: raise frappe.MandatoryError;
- nonblank code of an unaccepted length: raise a validation exception;
- accepted length: continue.

This function does not itself prove that the code exists as a GST HSN Code
record. The field is a Link to that DocType, and normal Frappe link validation
at frappe/model/base_document.py:1000-1047 remains responsible for link
validity. The Item hook subsequently loads the HSN document for tax propagation
at overrides/item.py:33-48.

The authoritative checks that should remain in India Compliance/Frappe are the
active setting, accepted lengths, code existence/link validity, and all
controller/hook side effects. MCP may use a provider to identify missing input
and, if the same settings are safely readable, give actionable length guidance;
it must not replace these checks.

## 7. Sales vs Purchase Item Behavior

Core ERPNext Item metadata declares:

- is_purchase_item default 1 at erpnext/stock/doctype/item/item.json:574-580;
- is_sales_item default 1 at :700-706;
- is_stock_item default 1 at :237-247.

The MCP sales Item capability does not rely on the core default for sales
eligibility: config/masters/item.py:35-37 sets explicit policy is_sales_item=1.
It excludes is_sales_item from direct user input at services/masters/item.py:190-196,
so current prepare_item always prepares a sales Item. The preview explicitly
reports is_sales_item: True.

The purchase profile registers only purchase Item search/resolution wrappers
(profiles/purchase.py:8-16, tools/masters/purchase_item.py:36-50); it does not
register Item creation. The shared resolver uses separate filters:

~~~text
sales:    disabled != 1 and is_sales_item = 1
purchase: disabled != 1 and is_purchase_item = 1
~~~

The India Compliance Item validator gates only on is_sales_item; it does not use
is_purchase_item. Therefore an Item with is_sales_item=0 does not receive this
specific HSN requirement, even if it is purchase-enabled. That conclusion is
source-confirmed, but a purchase-only creation capability would need its own
explicit contract and review because current MCP has no purchase Item creation.

The effective state is knowable at current sales prepare_item time because MCP
policy fixes is_sales_item=1. It is not currently used to evaluate conditional
metadata or the India Compliance validator.

## 8. Existing Project Capability / Integration Patterns

The repository search found these reusable patterns:

- MCPSettings and profile registration separate process/runtime configuration
  from domain services (settings.py, profiles/sales.py, profiles/purchase.py).
- services/common/creation_contract.py is a shared metadata/default resolution
  primitive for Customer and Item.
- services/common/field_value_resolver.py is a generic strategy layer for
  configured runtime fields, but not a document-validation engine.
- contracts/registry.py provides shared tool metadata and a frozen legacy inventory.
- approvals.py provides one shared approval store and guarded confirm path; it has
  no app-specific approval branches.
- Frappe provides installed-app discovery through frappe.get_installed_apps()
  (frappe/__init__.py:924) and hook discovery through frappe.get_hooks()
  (:992). India Compliance itself uses get_installed_apps for optional
  HRMS/Education/Healthcare setup (gst_india/setup/__init__.py:51-60).

No existing mcp_erpnext capability provider, effective-requirements registry,
optional validation adapter, or app-specific preflight abstraction was found.
The existing app/profile registration patterns are useful boundaries, but they
do not solve this audit's requirement. The next implementation should avoid
inventing a universal interpreter for arbitrary Python hooks.

## 9. Public MCP Contract Constraints

The governing standard is
docs/architecture/MCP_TOOL_CONTRACT_STANDARD.md:1-26,66-98,115-132. It requires
explicit typed fields/models, forbids arbitrary dictionaries at the public
boundary, keeps runtime identity server-controlled, and distinguishes
preparation from guarded confirmation. Current Item create tools are explicitly
listed as frozen legacy exceptions in contracts/registry.py:164-175.

| Design | Assessment |
| --- | --- |
| A. Optional gst_hsn_code field | Not the general solution. It would be a public India-specific field and still would not express when it is conditionally required. Consider only later as a deliberate typed sales capability field. |
| B. extra_fields: dict | Reject. Violates the explicit-schema standard, weakens discoverability/validation, and creates a mass-assignment surface. |
| C. Generic dynamic key/value fields | Reject. Same schema/security problems and cannot safely represent arbitrary controller behavior. |
| D. Typed integration-specific optional structures | Possible but too broad now. Couples public schema to optional apps and creates schema churn. |
| E. Unchanged public input plus structured needs_input | Preferred immediate UX boundary. Surface a known missing requirement without globally making the field mandatory. |
| F. Generic internal effective-requirements layer | Preferred implementation boundary. Lets core metadata/defaults and isolated providers contribute known requirements while preserving explicit public contracts and Frappe. |

The shared InteractionDirective in contracts/interaction.py:21-64 is the correct
client-neutral continuation signal for a typed needs_input result. It should be
used when Item creation is migrated, rather than adding approval_needed or
UI-specific identifiers. This audit does not migrate the frozen legacy contract.

## 10. Architecture Options Comparison

| Option | Source fit | Portability | Safety/authority | Complexity | Decision |
| --- | --- | --- | --- | --- | --- |
| A. Metadata-only | Cannot evaluate the controller-only rule; conditional metadata is only recorded, not executed | Excellent | Safe but incomplete; late write failures remain | Lowest | Insufficient |
| B. Hardcoded India Compliance branch in Item service | Reproduces the known condition but duplicates optional-app knowledge in a generic service | Poorer; must avoid import when absent | Risks drift from app settings/version and grows app-specific branches | Low initially | Reject |
| C. Generic effective-requirements service | Correctly extends the existing creation helper with effective values and providers | Good | Safe if advisory and confirm remains native | Moderate | Necessary core |
| D. Generic preflight plus isolated integration provider | Best match for optional installed apps: generic core plus India-specific source knowledge | Excellent | Provider can fail closed for uncertainty and never bypass native validation | Moderate | Recommended |
| E. Run doc.validate or insert during prepare | Could discover more rules but violates side-effect-free preparation and may trigger mutations/messages/lookups | Site-dependent | Unsafe as general preflight and cannot provide a write-free approval preview | High risk | Reject |

Option D is not a plugin registry for arbitrary apps, not an interpreter of Python
validation code, and not a replacement for Frappe's lifecycle. It is a small
internal provider interface for requirements knowable before write and worth
collecting conversationally.

## 11. Recommended Architecture

Adopt Option D: generic effective-requirements preflight plus isolated, optional
integration providers.

The conceptual flow is:

~~~text
prepare_item
  -> resolve configured core input fields from merged runtime metadata/defaults
  -> build effective unsaved Item state, including MCP policy values
  -> collect known requirements from core metadata and applicable providers
  -> if a known requirement is missing, return needs_input before approval
  -> resolve safe link values and build preview
  -> issue approval bound to complete prepared payload

confirm_item
  -> claim existing shared approval
  -> recheck permission and duplicate state
  -> frappe.get_doc(approved payload)
  -> normal permission-enforced Frappe insert
  -> ERPNext and installed-app validation remain final authority
~~~

The core provider should understand only bounded generic concepts: merged
DocField metadata, effective values/defaults, and requirements explicitly
declared by a provider. It should not execute arbitrary mandatory_depends_on or
depends_on expressions, because that would be unsafe and incomplete.

The India Compliance provider should be isolated and lazy/optional. It should:

1. determine whether india_compliance is installed for the current site;
2. verify that effective Item metadata exposes gst_hsn_code as a usable field;
3. read the same non-secret GST Settings values used by the app;
4. evaluate effective is_sales_item;
5. recognize an HSN inherited from item_group.gst_hsn_code only if it can
   resolve that fetch safely without mutating the document;
6. return a structured requirement for missing HSN/SAC, plus safe length
   guidance when the configured rule is known;
7. leave HSN link existence, final normalization, tax propagation, and other
   validation to Frappe/India Compliance during confirmation.

The provider must not import India Compliance at module import time on an
ERPNext-only site. It must not add HSN to every Item, force a purchase-only
Item to satisfy a sales-only rule, or accept an approval or validation bypass.

## 12. Verified Behavior Matrix

The matrix separates source-confirmed behavior from recommended future preflight
behavior. “Normal validation” means the current native Frappe/ERPNext lifecycle
continues to run.

| Environment / state | Expected prepare_item behavior | Expected confirm_item behavior |
| --- | --- | --- |
| ERPNext only; no India Compliance | Current metadata/default flow; no HSN requirement from this app | Current normal Frappe Item insert |
| India Compliance absent and HSN field absent | No India Compliance import or requirement; current behavior | Normal Frappe validation |
| India Compliance installed; validate_hsn_code=0 | Do not ask for HSN because of this rule | India Compliance returns without this HSN check; other validation remains |
| Installed; validation enabled; sales Item; inherited or supplied HSN present | Continue after safely known checks | Native Frappe/India Compliance validation remains final |
| Installed; validation enabled; sales Item; HSN missing | Return needs_input before approval with HSN/SAC requirement | Must not be reached from that prepared flow until input is supplied |
| Installed; validation enabled; sales Item; invalid length | Surface actionable invalid-length input if the same setting is readable | Native India Compliance length validation remains final |
| Installed; validation enabled; non-sales Item | Do not require HSN for this specific rule | Normal validation; Item gate returns early |
| Settings document/values unavailable | Do not silently assert HSN is optional; safe configuration/unavailable result | Native validation remains final; configuration errors are not suppressed |
| Purchase-only capability later with is_sales_item=0 | Do not apply this sales-only rule | Normal native validation |
| Optional app absent | No runtime import/dependency on India Compliance | Existing Item creation remains functional |

The source-confirmed HSN condition is:

~~~text
India Compliance Item validate hook runs
AND effective Item.is_sales_item is truthy
AND GST Settings.validate_hsn_code is truthy
AND gst_hsn_code is blank
=> MandatoryError
~~~

Installation alone is not sufficient. min_hsn_digits affects accepted length, not
whether blank code is required once validation is enabled.

## 13. Error and User-Experience Recommendation

For a known missing conditional requirement, prepare_item should return its
existing status: needs_input shape with a structured missing-field entry. The
entry should describe:

~~~text
field: HSN/SAC Code
path: contract-compatible Item field path
reason: required by active GST/India Compliance validation for this sales Item
constraints: accepted lengths, only when read safely from active settings
~~~

The exact public field names should be frozen during later legacy-contract
migration. The implementation must not introduce a parallel ad-hoc field such as
approval_needed; when typed, it should use InteractionDirective with INPUT and
PROVIDE_INPUT/CANCEL.

A normal user should see: “Provide the HSN/SAC code for this sales Item.” If the
setting or capability cannot be read safely, direct the user to an authorized
administrator/support person without exposing stack traces, imports, database
details, or internal paths.

Invalid length should be actionable only when the provider successfully reads the
same active setting. Otherwise the native validator should explain the failure
through a safe mapped error path.

## 14. Security and Validation Boundaries

MCP preflight may inspect merged metadata and safe non-secret settings, apply the
approved Item policy, resolve permitted Item Group/UOM links, identify a known
missing field, validate safely derivable format constraints, and bind the
complete payload to the existing approval digest.

MCP must not use ignore_validate, ignore_mandatory, or any bypass flag; execute
arbitrary installed-app validation as a generic interpreter; trust client-provided
app names, settings, approval modes, or runtime identity; expose arbitrary
fields through mass assignment; assume preflight guarantees write success; or
suppress/rewrite the authoritative India Compliance exception.

~~~text
MCP preflight = proactive conversational guidance
Frappe / ERPNext / installed-app validation = final write authority
~~~

The current confirmation path already satisfies the native boundary: it
rechecks permission, claims the shared approval, calls frappe.get_doc, and
invokes insert with permissions, links, and mandatory validation enabled
(services/masters/item.py:311-325).

## 15. Backward Compatibility

ERPNext-only sites must continue using the current metadata/default Item flow.
The absence of India Compliance means no provider and no HSN requirement from
this app.

When India Compliance is installed but HSN validation is disabled, the provider
must not ask for HSN because of this rule. Core mandatory fields, link
resolution, duplicate checks, approval policy, and native validation remain.

When installed and active, only the point at which a known missing HSN is
requested changes: from post-approval confirm failure to pre-approval
needs_input. Item eligibility, profile registration, approval policy, and final
persisted data must not otherwise change.

The current prepare_item and confirm_item contracts are frozen legacy contracts.
Avoid unrelated contract migration; any InteractionDirective/output-schema
migration is a separate task.

## 16. Exact Files for Next Task

### Allowed implementation scope

The next task should be limited to the smallest files needed for generic preflight
and the isolated provider, likely:

~~~text
mcp_erpnext/services/common/creation_contract.py
  Extend or compose the existing creation-resolution result with bounded,
  provider-supplied effective requirements.

mcp_erpnext/services/masters/item.py
  Invoke preflight after effective Item values are known and before approval;
  preserve the existing confirm insert path.

mcp_erpnext/services/common/<small effective-requirements module>.py
  Add only if a provider interface cannot remain a small creation-helper extension.

mcp_erpnext/services/integrations/<isolated India Compliance provider>.py
  Add only if the repository convention confirms a dedicated integrations module;
  keep import optional and lazy.

mcp_erpnext/tests/test_item_service.py
mcp_erpnext/tests/test_creation_contract.py
  Add provider applicability, missing input, settings-off, non-sales, and
  normal-insert regression coverage.
~~~

The exact module path should be finalized by the implementation task after one
more convention check. No new app registry or universal validation interpreter
is justified.

### Must remain untouched

~~~text
mcp_erpnext/approvals.py
mcp_erpnext/tools/masters/item.py        (unless separate typed-contract task)
mcp_erpnext/contracts/registry.py        (no new legacy exception or approval mode)
mcp_erpnext/contracts/interaction.py     (reuse; no ad-hoc kinds/actions)
apps/erpnext/**
apps/india_compliance/**
database records and GST Settings
migrations, fixtures, hooks, and profile allowlists
~~~

The next task must not add gst_hsn_code to a global Item field tuple unless the
public capability is deliberately expanded and separately approved. It must not
make HSN mandatory for all Items.

## 17. Test Plan for Next Task

Required unit/static scenarios:

1. Existing ERPNext-only metadata path: no provider and no HSN requirement.
2. India Compliance absent: no import failure and current preparation remains.
3. HSN validation disabled: no needs_input for HSN.
4. Enabled validation, effective is_sales_item=1, blank HSN: structured
   needs_input before approvals.create.
5. Enabled validation, sales Item, accepted HSN length: existing ready/approval.
6. Enabled validation, sales Item, invalid length: actionable preflight when
   settings are readable, without replacing native validation.
7. Non-sales effective Item: no provider HSN requirement.
8. Item Group fetch candidate: safely inherited HSN satisfies preflight; an
   inaccessible/unresolvable value does not bypass final link validation.
9. Missing/invalid GST settings: safe configuration handling, no silent
   disablement or stack-trace exposure.
10. Existing static metadata-required fields retain their current needs_input.
11. Duplicate and permission checks retain normal permission behavior.
12. Confirmation still calls insert with ignore_permissions=False,
    ignore_links=False, and ignore_mandatory=False.
13. Provider input is included in the prepared payload digest.
14. Direct confirm=true still cannot self-authorize.
15. If typed output is migrated, validate shared InteractionDirective and
    outputSchema without changing approval enforcement.

Live verification, if separately authorized, should use one ERPNext-only site and
one India Compliance site, read settings first, and use isolated development
data for prepare/approve/confirm. Unit success alone is not live MCP/database
confirmation.

## 18. Known Limitations / Open Questions

- No live Item write was performed for this audit. Failure evidence is from the
  existing MCP log plus source trace.
- The logger recorded site=unknown and user_fp=missing for observed failures, so
  the log proves the tool/error path but not the historical actor.
- The source has no explicit safe behavior for a missing GST Settings singleton.
  The implementation must choose and test fail-closed configuration handling.
- mandatory_depends_on is represented in metadata and meaningful to forms, but
  the inspected server mandatory checker is static. This audit does not
  recommend evaluating arbitrary dependency expressions generically.
- A non-sales Item bypasses this specific HSN gate, but other controller or
  installed-app validations may still apply.
- gst_hsn_code can be fetched from item_group.gst_hsn_code during normal Frappe
  link validation at frappe/model/base_document.py:1024-1064. Preparation does
  not perform that lifecycle, so inherited-value behavior needs focused design.
- Future India Compliance releases may change implementation details and need
  compatibility/regression policy.
- The frozen legacy Item contract lacks typed output and a public interaction
  directive. That is separate from this audit.
- apps.txt is bench inventory, not site installation state; the report
  distinguishes it from frappe.get_installed_apps site checks.

## 19. Final Decision Proposal

Freeze this architecture decision:

> mcp_erpnext Item preparation remains generic and metadata/default aware, but
> gains a bounded internal effective-requirements preflight seam. Optional app
> rules are isolated in lazy providers. The first provider models only the
> source-confirmed India Compliance Item HSN rule: installed app, active GST HSN
> validation, and effective is_sales_item. It returns structured missing input
> before approval when HSN is absent, while normal Frappe/ERPNext/India
> Compliance validation remains authoritative during confirmation. No global HSN
> requirement, arbitrary extra-field dictionary, app import dependency on
> ERPNext-only sites, approval change, or validation bypass is allowed.

This addresses the root cause without turning the generic Item service into an
India-Compliance-only implementation or an interpreter for arbitrary controller
code.

## 20. Exact Next Task

### Task 23 — Item Creation Conditional Runtime Requirements Implementation

Implement the approved generic effective-requirements preflight seam and the
isolated optional India Compliance HSN provider so applicable missing HSN/SAC
input is returned before Item approval, while preserving ERPNext-only behavior,
the current public contract boundary, shared approval guard, and normal native
Frappe validation on confirmation.
