# Task 36 — Frappe / ERPNext Authority Duplication Audit Report

**Audit date:** 2026-09-12  
**Project:** `apps/mcp_erpnext`  
**Checkout:** `master`  
**Status:** Complete; inspection/report only  
**Implementation result:** No production code, configuration, registration, permission, lifecycle, database, Purchase behavior, or runtime state was changed by this audit.

## 1. Executive summary

The current MCP is predominantly a thin, permission-aware bridge. Its final document writes use Frappe Document APIs with native permission and validation enforcement, its conversion paths use ERPNext's installed mappers, and its read/PDF/email paths use permission-filtered Frappe APIs. MCP-specific behavior is concentrated in profile exposure, identity hand-off, entity resolution, missing-input handling, preview/approval, bounded contracts, response shaping, and observability.

Two confirmed duplications should be removed or simplified in a follow-up implementation:

1. `mcp_erpnext/services/selling/sales_invoice.py:_direct_invoice_policy()` copies the `SalesInvoice.so_dn_required()` configuration and Customer-exception decision already executed by native Sales Invoice validation.
2. `mcp_erpnext/services/selling/quotation.py:prepare_quotation()` independently rejects `valid_till < transaction_date`, exactly duplicating ERPNext Quotation `validate_valid_till()`.

Several items are possible duplication, but should not be removed automatically because they also provide a safe MCP preparation boundary: the Item India Compliance HSN preflight, commercial-default presence lists, the field-type strategy catalog, and the standalone Sales Order delivery-date default. These require a focused compatibility decision rather than a broad cleanup.

No custom role matrix, ownership rule, direct SQL write, `ignore_permissions=True` business write, custom tax/amount formula, or replacement for ERPNext's conversion mapper was found in the inspected project.

## 2. Architecture principle evaluated

The evaluated ownership boundary is:

```text
LLM / MCP client
        |
        v
MCP profile and typed tool surface
        |
        v
identity -> entity resolution -> missing input -> preview -> approval
        |
        v
Frappe / ERPNext runtime authority
metadata -> permissions -> document state -> validation -> hooks
links -> calculations/defaults -> transactions -> persistence
        |
        v
MCP bounded, client-neutral result and error response
```

The question applied to each rule was: **does Frappe/ERPNext already decide this correctly at runtime?** If yes, MCP should call or preserve that authority and avoid maintaining an independent copy. If the rule concerns which tools are exposed, how ambiguous entities are resolved, how approval is obtained, or how data is shaped for a client, it is an MCP responsibility and is not duplication merely because it is custom.

## 3. Repository areas inspected

| Area | Inspected paths and symbols | Result |
|---|---|---|
| Server/profile boundary | `mcp_erpnext/mcp_server.py`, `profiles/sales.py`, `profiles/purchase.py`, `tools/__init__.py` | Profile selection is MCP exposure policy. |
| Runtime identity | `mcp_erpnext/runtime.py`, `settings.py`, `http_transport.py` | Frappe user context is established before business calls; HTTP identity does not fall back to the process user. |
| Approval/interaction | `approvals.py`, `contracts/interaction.py`, lifecycle and create services | Approval is server-controlled and write confirmation is bound to action, site, user, and payload. |
| Contracts/registry | `contracts/registry.py`, `contracts/lifecycle.py`, create/read/conversion contracts | Typed model-facing envelopes and tool governance are MCP concerns. |
| Shared metadata/entity/read services | `services/common/creation_contract.py`, `effective_requirements.py`, `field_value_resolver.py`, `entity_resolution.py`, `read.py`, `aggregate.py` | Runtime metadata and permission-filtered reads are used; narrow projections remain deliberate contract policy. |
| Lifecycle mutation | `services/common/lifecycle.py`, `tools/lifecycle.py` | Static maps limit public addressability; native document methods remain final authority. |
| Sales and Purchase creation | `services/masters/customer.py`, `masters/item.py`, `selling/quotation.py`, `selling/sales_order.py`, `selling/sales_invoice.py`, `buying/purchase_order.py` | Native defaults, calculations, validation, and insert are used; two business-rule mirrors were found. |
| Conversions | `services/selling/quotation_to_sales_order.py`, `sales_order_to_sales_invoice.py` | ERPNext public mappers are used. |
| PDF/email | `services/common/pdf.py`, `services/common/email.py` | Native print/PDF/email queue behavior is retained behind MCP safety and data boundaries. |
| Optional official app | `services/integrations/india_compliance_customer.py`, `india_compliance_item.py`; installed `india_compliance` source | Customer bridge is thin; Item HSN preflight overlaps official validation and needs compatibility review. |
| Framework/ERP authority | Frappe `Document`, `delete_doc`, `Meta`; ERPNext Quotation, Sales Order, Sales Invoice, Purchase Order controllers | Runtime metadata, permissions, hooks, links, lifecycle, and business validation are native authority. |

The local `yob.localhost` runtime was queried read-only for installed apps and metadata. It reported Frappe, ERPNext, `india_compliance`, and `mcp_erpnext` installed. Runtime metadata also showed site-specific/custom fields, including Customer `gst_category` and Item `custom_slug`; this confirms that source DocType JSON alone cannot be treated as the complete installed schema.

The framework version command was not used as evidence because the local India Compliance checkout triggered Git dubious-ownership handling. Exact version claims are therefore intentionally omitted. Source inspection used the installed local checkouts.

## 4. Complete MCP-specific responsibility inventory

The following responsibilities are valid MCP/product or interaction concerns:

| Responsibility | Current implementation | Classification |
|---|---|---|
| Profile exposure | Sales and Purchase registration in `profiles/*.py`; profile-specific public DocType/action maps | **A/B — valid MCP boundary** |
| Identity hand-off | `runtime.py` initializes Frappe and sets the resolved Frappe user; HTTP headers are resolved separately from stdio configuration | **B — valid identity bridge** |
| Entity resolution | `entity_resolution.py` ranks permission-visible candidates and reports resolved, ambiguous, or not-found outcomes | **B/C — valid interaction logic** |
| Missing input | Creation contracts combine explicit fields, MCP policy values, runtime defaults, and metadata-required fields | **B/D — valid preparation contract** |
| Narrow input contracts | Creation field tuples and typed Pydantic contracts expose only supported model-facing fields | **D — valid data minimization** |
| Preview | Services serialize bounded document projections and selected child/totals fields | **C/D — valid review boundary** |
| Approval | `ApprovalStore` creates opaque process-local pending operations and claims them atomically before writes | **C — valid safety logic** |
| Stale confirmation | Payload fingerprints and modified/docstatus checks require re-preparation after relevant changes | **C — valid safety logic** |
| Interaction directive | Shared `InteractionDirective` communicates continuation/approval semantics without client-specific fields | **C/D — valid conversational contract** |
| Tool naming and registry | `contracts/registry.py` records typed operations, side-effect classes, and approval guards | **D — valid MCP governance** |
| Data minimization | Read projections, aggregate operation allowlists, PDF artifact bounds, and email payload limits | **D — valid contract policy** |
| Error normalization | `public_error()` and `observability.execute_tool()` produce bounded public errors and operational references | **D — valid response/observability policy** |
| Profile-specific business capability | Sales creation/conversion surface and Purchase creation surface are intentionally different | **G — intentional product restriction** |

These responsibilities should remain custom even when they call Frappe APIs internally.

## 5. Complete Frappe/ERPNext authority inventory

| Authority | Evidence inspected | Required MCP behavior |
|---|---|---|
| Installed metadata | `frappe.get_meta()` / `Meta`; `creation_contract.py` uses runtime metadata | Use runtime fields, `reqd`, `mandatory_depends_on`, field types, options, and table definitions where capability behavior depends on installed schema. |
| Permission checks | `doc.has_permission()`, `doc.check_permission()`, `frappe.has_permission()`, `frappe.get_list(ignore_permissions=False)` | Early checks may improve UX, but final native checks must remain enabled. |
| Document insertion | Frappe `Document.insert()` | Preserve hooks, mandatory validation, links, and permission checks. |
| Document save/update | Frappe `Document.save()` and `db_update()` through the Document lifecycle | Do not replace with direct field updates for business mutations. |
| Submit/cancel | Frappe `Document.submit()` / `cancel()` and controller hooks | Use native methods; metadata and docstatus are runtime truth. |
| Delete and links | Frappe `delete_doc()`, `get_linked_docs()`, dynamic links, child deletion and hooks | Use native deletion/link behavior; MCP preflight may explain blockers. |
| Controller validation | ERPNext controllers for Customer, Item, Quotation, Sales Order, Sales Invoice, Purchase Order | Avoid copies of controller rules; final native validation is authoritative. |
| Defaults/calculations | `set_missing_values()`, `calculate_taxes_and_totals()`, controller methods | Call native methods; do not calculate tax, amounts, currency, or commercial defaults independently. |
| Mapping/conversion | ERPNext `make_sales_order()` and `make_sales_invoice()` | Use installed mapper and preserve source lineage. |
| India Compliance | Official GST/customer/item/transaction hooks and utilities | Use a thin optional bridge; final official-app hooks must run on native persistence. |
| Transaction boundary | Native Document persistence plus explicit MCP commit/rollback around final writes | Keep persistence in Frappe Document APIs and rollback on failed final writes. |

The official [Frappe Document API](https://docs.frappe.io/framework/user/en/api/document) and [DocType controller lifecycle](https://docs.frappe.io/framework/user/en/basics/doctypes/controllers) describe the native methods and controller hooks that must remain authoritative.

## 6. Duplication search methodology

The audit used source and runtime tracing rather than naming assumptions:

1. Enumerated profile registration, public tools, contracts, services, integrations, and shared helpers.
2. Searched for lifecycle, metadata, permission, persistence, SQL, error, role, and static-map patterns, including `is_submittable`, `docstatus`, `allow_on_submit`, `mandatory`, `reqd`, `read_only`, `fieldtype`, `has_permission`, `check_permission`, `frappe.session.user`, `ignore_permissions`, `db_update`, `set_value`, `delete_doc`, `insert`, `save`, `submit`, `cancel`, `get_meta`, and exception handling.
3. Traced each create, update, child-add, submit, cancel, delete, conversion, PDF, email, read, aggregate, and resolve path to its final Frappe/ERPNext call.
4. Compared custom preflight rules with installed controller methods and official India Compliance utilities.
5. Queried the live local site read-only for installed apps and runtime metadata, without creating or changing business records.
6. Classified findings using the task's A–G categories, distinguishing product scope and safety logic from copied ERP authority.

## 7. Duplication inventory table

| Custom location | Reproduced knowledge | Native authority | Classification | Finding/action |
|---|---|---|---|---|
| `services/selling/sales_invoice.py:230-247` `_direct_invoice_policy` | Selling Settings `so_required`/`dn_required`, Customer exceptions, and prerequisite decision | ERPNext `SalesInvoice.validate()` calls `so_dn_required()` at `../erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py:305-314`; rule body is at `:1167-1185` | **F — confirmed duplication** | Remove/simplify in a focused follow-up; preserve a bounded blocked response only if it is derived from native validation safely. |
| `services/selling/quotation.py:284-293` | `valid_till` must not precede transaction date | ERPNext Quotation `validate()` calls `validate_valid_till()` and applies the identical comparison at `../erpnext/erpnext/selling/doctype/quotation/quotation.py:141-163` | **F — confirmed duplication** | Let native validation decide; adapt its failure to the MCP response. |
| `services/selling/sales_order.py:48-57` | Delivery date default and date ordering | ERPNext Sales Order `validate_delivery_date()` at `../erpnext/erpnext/selling/doctype/sales_order/sales_order.py:425-447` | **E/G — possible duplication plus valid standalone default** | Keep defaulting only if required by the MCP create capability; remove any duplicate rejection once native validation-backed preflight is available. |
| `services/selling/*` `_COMMERCIAL_DEFAULTS`; Sales Invoice `_REQUIRED_DEFAULTS` | Required/default presence for price list, currency, conversion rates, company, posting date, and debit account | Runtime metadata plus native `set_missing_values()` and controller validation | **E — review needed** | These are useful “do not ask for approval yet” checks but can drift; derive from runtime metadata/native default state where possible. |
| `services/integrations/india_compliance_item.py:18-23,71-217` | GST Settings, minimum HSN digits, accepted lengths, Item Group fetch, and conditional sales Item requirement | Official `india_compliance` `get_hsn_settings()` and transaction `_validate_hsn_codes()` | **E — review needed** | Keep final official validation authoritative; consider consuming an official side-effect-free helper or version-gating the prepare-only fallback. |
| `services/common/field_value_resolver.py:19-63` | Framework field-type categories and handling strategies | Frappe DocField `fieldtype` metadata | **E/D — bounded strategy catalog** | Retain only the strategies needed by exposed contracts; add compatibility coverage when framework field types change. |
| `services/common/lifecycle.py:49-62` `_SYSTEM_FIELDS` | Internal/system fields are not directly writable | Frappe Document metadata and persistence behavior | **B/D — valid MCP safety rule** | Retain as a narrow user-safety boundary; native save remains final authority. |
| `services/common/lifecycle.py:17-47` profile/action/child maps | Which DocTypes and child tables this endpoint exposes | No Frappe authority decides the endpoint's public product scope | **A/B/G — valid MCP boundary** | Retain; do not mistake exposure maps for capability truth. |
| `services/common/read.py` and read services static projections | Fields and aggregates exposed to the model/client | Frappe has broader metadata/data access, but not this contract policy | **B/D — valid data minimization** | Retain; runtime existence checks and tests should protect against installed-schema drift. |
| `services/masters/customer.py` duplicate suspicion query | Exact visible Customer matches by selected identifying fields | No equivalent native Customer uniqueness rule was found in the inspected controller | **C/G — intentional UX/business restriction** | Do not label as confirmed duplication; retain only as an explicit “possible duplicate” safety signal. |

## 8. Profile-boundary analysis

`profiles/sales.py` registers Customer, Item, Sales Order, Quotation, Sales Invoice, selection, conversion, lifecycle, PDF, email, and Sales reads. `profiles/purchase.py` registers Supplier, Item, Purchase Order, Purchase reads, lifecycle, PDF, and email. `mcp_server.py` selects one profile and registers that surface.

`services/common/lifecycle.py` uses `PROFILE_DOCTYPES`, `LIFECYCLE_ACTION_DOCTYPES`, and `CHILD_ADD_TARGETS` to constrain the endpoint's public addressability. These maps do not claim that every listed DocType supports every action: `_prepare_action()` checks runtime `doc.meta.is_submittable`, current `docstatus`, native permissions, and linked-document blockers before approval; confirmation calls native methods.

This is a valid MCP scope rule. Frappe cannot decide which capabilities a particular LLM-facing endpoint should expose. The map should not be expanded into a static copy of Frappe capability truth, and no such full capability copy was found.

Purchase was inspected for shared patterns only. No Purchase redesign or behavioral recommendation is authorized by this audit.

## 9. Metadata duplication findings

The strongest metadata pattern is positive: `resolve_creation_contract()` calls runtime `get_meta()` and an unsaved `frappe.new_doc()`, then combines user input, MCP policy values, and installed ERPNext defaults before reporting missing fields. `lifecycle._validate_change()` checks the loaded document's metadata and the child row's runtime metadata for field existence, read-only state, field type, Select options, and permitted Link values.

Narrow static lists remain in the project for intentional contract purposes:

- Customer, Item, Supplier, Quotation, Sales Order, and Sales Invoice read projections.
- Creation field allowlists and MCP policy values.
- Field-type handling strategies needed for generic typed resolution.
- Lifecycle system-field protection and supported child-table targets.

The runtime metadata query on `yob.localhost` showed custom/site fields not inferable from base source definitions, including Customer `gst_category` and Item `custom_slug`. Therefore static lists must remain capability projections, not assertions about the complete DocType schema. The audit found no static `SUBMITTABLE_DOCTYPES`-style capability truth used as the final authority.

## 10. Permission duplication findings

Permission handling is correctly layered:

- Runtime establishes the Frappe user before tool execution (`runtime.py:86-141`).
- Reads use `doc.has_permission("read")` or permission-filtered `frappe.get_list(..., ignore_permissions=False)`.
- Creates check `frappe.has_permission(..., "create")` early and use native `insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)` on confirmation.
- Lifecycle confirmation calls `doc.check_permission("write"/"submit"/"cancel"/"delete")` immediately before native mutation.
- PDF/email paths check read/print/email permissions and use native print/email APIs.

No custom role-name matrix, ownership rule, or independent write/submit/cancel/delete authorization rule was found. Early checks are UX and race-window reduction; they do not replace the final Frappe checks.

## 11. Lifecycle duplication findings

The lifecycle service has an MCP action allowlist and performs safe preflight for state, submittability, permission, and linked-document blockers. These are valid preview/safety concerns when they do not become the final authority.

At confirmation:

- update uses `doc.save(ignore_permissions=False)`;
- child add appends to the loaded document, applies native defaults/calculation/validation, then saves with permissions enabled;
- submit uses `doc.submit()`;
- cancel uses `doc.cancel()`;
- delete uses `doc.delete(ignore_permissions=False)` and handles the native cancel-then-delete plan where appropriate.

Frappe `Document.submit()`, `cancel()`, `save()`, and `delete_doc()` retain hooks, state checks, link checks, and persistence behavior. The MCP action map is therefore **A/B**, not a duplicate of those capabilities. A minor review item is that the public action map can address a non-submittable DocType before runtime rejects it; that is exposure-policy ergonomics, not a reason to copy or remove native metadata checks.

## 12. Validation duplication findings

Valid MCP validation includes input shape, numeric finiteness/ranges, exact entity resolution, permitted Link selection, Select options, child-row identity, duplicate child item detection, and safe missing-input reporting. These prevent ambiguous or unsafe model-facing requests and do not replace native validation.

Creation services call native `set_missing_values()`, `calculate_taxes_and_totals()`, and in Quotation/Sales Order preparation `run_method("validate")`; final confirmation still inserts through Frappe. No independent tax or amount validation was found.

The two confirmed validation mirrors are:

- Sales Invoice direct prerequisite policy, which is explicitly documented as a mirror in its docstring and duplicates `so_dn_required()`.
- Quotation valid-till ordering, whose comparison and user-facing failure duplicate `validate_valid_till()`.

The Sales Order delivery-date function is not classified as confirmed duplication because it also supplies the standalone create capability's default. The rejection portion should be reconsidered together with native validation-backed preparation.

## 13. Calculation/default duplication findings

The inspected services delegate commercial calculations to native methods. Quotation, Sales Order, and Purchase Order call `set_missing_values()` and `calculate_taxes_and_totals()`; Sales Invoice does the same. Conversion services call ERPNext mappers and validate mapped documents.

The `_COMMERCIAL_DEFAULTS` and Sales Invoice `_REQUIRED_DEFAULTS` lists are not amount or tax formula copies. They are MCP readiness gates that prevent creating an approval token when a usable document cannot be previewed. However, some values are runtime defaults or native-derived values, so these lists can drift from installed ERPNext behavior. They are **E**, not **F**, until each field's requiredness and default lifecycle is tested against runtime metadata and native validation.

Preview normalization, such as exposing a missing discount as numeric zero, is contract shaping (**D**) and must not be interpreted as changing the stored document value.

## 14. Link/dependency duplication findings

MCP resolves Link inputs against permission-visible records and uses bounded filters for active Items, Customer/Supplier, Company, Price List, addresses, and related records. This is entity-resolution and least-data-access behavior.

Lifecycle cancellation/deletion preflight uses Frappe/ERPNext link discovery (`get_linked_docs()` and dynamic links). Final `save()`, `insert()`, `submit()`, `cancel()`, and delete operations continue to execute native link checks and hooks.

Conversions preserve native source lineage by calling ERPNext `make_sales_order()` and `make_sales_invoice()` rather than reconstructing mapping rules. This is correctly classified **A**.

No custom dependency graph, direct link deletion, or replacement for Frappe's link validation was found.

## 15. Persistence/API bypass findings

The inspected business mutation paths do not use direct SQL, `frappe.db.set_value`, `db_update`, or an `ignore_permissions=True` final write. Final writes intentionally pass:

```text
insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
save(ignore_permissions=False)
delete(ignore_permissions=False)
submit()
cancel()
```

The services explicitly commit successful final writes and roll back handled failures. Preparation creates unsaved documents and process-local pending approvals; it does not persist a draft. PDF generation uses native `frappe.get_print(..., as_pdf=True)`, and email uses Frappe's email queue after MCP permission/approval checks.

This is the desired bridge behavior. No persistence bypass duplication was confirmed.

## 16. India Compliance / official-app findings

The local runtime reports `india_compliance` installed.

Customer handling is a thin optional bridge. `india_compliance_customer.py` detects installation, dynamically imports official helpers, calls official pure GST helpers such as `validate_gstin`, `guess_gst_category`, and `validate_gst_category`, and deliberately avoids the full hook when it may trigger GST autofill or queued persistence during prepare. Final Customer insertion remains native so installed hooks execute. This is **A/C/G** and should remain.

Item handling is more coupled. `india_compliance_item.py` reads installed metadata, GST Settings, Item Group fetch behavior, sales-item state, and accepted HSN lengths. The official app independently provides `get_hsn_settings()` and transaction `_validate_hsn_codes()`, including the same `(4, 6, 8)` length source and HSN normalization/validation. The MCP path is a prepare-only conditional requirement and final native/official validation remains authoritative, but it still duplicates official knowledge. This is **E**, not yet **F**, because a side-effect-free official helper may not be available as a stable public API and preparation must avoid unsafe hooks.

The next implementation should decide whether to consume a stable official helper, add a narrow compatibility adapter, or keep a clearly documented prepare-only fallback with version-aware tests. It must not make India Compliance a hard dependency or copy its full business rules.

## 17. Error-handling findings

The normal pattern is appropriate: services return bounded error dictionaries through `public_error()`, while `observability.execute_tool()` logs an opaque reference, stable code, tool name, site, and a user fingerprint without logging natural-language inputs or approval tokens. Logging failure does not replace the original safe MCP error envelope.

Native PermissionError, link errors, and validation failures are handled at service boundaries or by the shared runtime wrapper. Approval failures use centralized codes and retryability.

One non-duplication review item remains: generic lifecycle handlers at `services/common/lifecycle.py:441` and `:678` pass `str(error)` into an MCP error in some paths. The shared outer observability wrapper sanitizes uncaught exceptions, but a native exception converted into a returned service result may still carry more detail than the client contract requires. This is an error-contract hardening review, not evidence that MCP has duplicated ERP authority.

## 18. Per-operation authority matrix

| Operation family | MCP owns | Frappe owns | ERPNext / official app owns |
|---|---|---|---|
| Profile/tool exposure | Which Sales/Purchase capabilities are public | N/A | N/A |
| Identity/runtime | Resolve transport identity and establish context | User/session/permission evaluation after hand-off | App-specific permission effects |
| Create | Input contract, entity resolution, missing input, preview, approval | Metadata, permissions, insert lifecycle, mandatory fields, hooks, persistence | Controller validation, defaults, calculations, GST/other official hooks |
| Read/get | Allowlist, projection, bounded response | Query permission, record access | DocType/controller data semantics |
| Query/aggregate | Supported filters, sort/group/aggregate vocabulary, pagination/limits | Permission-filtered query execution | Report/business field meanings |
| Update | Addressable fields, child-row selector, preview, approval, stale check | Save permission, read-only/allow-on-submit rules, hooks, link validation, persistence | Controller validation and workflow/business rules |
| Child-row add | Supported child tables, exact target, input safety, preview, approval | Save/insert/link/mandatory enforcement | Child-row validation, calculations, controller rules |
| Submit | Public action scope, preview, approval, stale check | `is_submittable`, submit permission, docstatus, hooks, persistence | `before_submit`/`on_submit` and business validation |
| Cancel | Public action scope, link-blocker explanation, approval | Cancel permission, submitted state, links, hooks, persistence | Controller cancel rules and linked-document semantics |
| Delete | Public action scope, blocker preview, approval | Delete permission, submitted-state rule, link checks, hooks, child/attachment cleanup | Controller/app-specific linked business constraints |
| Quotation -> Sales Order | Source resolution, scope, preview, approval, stale fingerprint | Target permission and native persistence | ERPNext `make_sales_order()` mapper and Sales Order validation |
| Sales Order -> Sales Invoice | Source resolution, scope, preview, approval, stale fingerprint | Target permission and native persistence | ERPNext `make_sales_invoice()` mapper and Sales Invoice validation |
| PDF | Format/input bounds and response artifact limits | Read/print permission and print rendering | Installed print format/template behavior |
| Email | Recipient/input bounds, approval, response shaping | Read/email/print permissions and Email Queue | Native PDF generation and party/contact business data |
| Metadata requirements | Exposed-field contract and missing-input presentation | Runtime DocField metadata | Controller/official-app conditional validation |
| India Compliance | Optional detection and prepare-safe bridge boundary | Final native document lifecycle | Official GST validation, defaults, hooks, and persistence effects |
| Errors | Stable public code/message/retryability/reference envelope | Native exception and transaction behavior | Controller/official-app exception semantics |

## 19. Valid custom MCP logic that should remain

The following should remain unless a separate product requirement changes:

- Sales/Purchase profile selection and tool exposure.
- HTTP/stdio identity resolution and fail-closed authenticated Frappe context.
- Permission-visible entity resolution and ambiguity handling.
- Runtime metadata-backed creation contracts with narrow field allowlists.
- Missing-input, preview, approval, stale-confirmation, and single-use confirmation behavior.
- Shared `InteractionDirective` and client-neutral result contracts.
- Read projections, bounded aggregates, PDF limits, email safety checks, and data minimization.
- Exact child-row targeting and protection of system/read-only/layout fields.
- Early permission checks when paired with native final checks.
- Native conversion mapper adapters and bounded conversion previews.
- Optional India Compliance bridges that avoid side effects during prepare and leave final authority to the official app.
- Error references and operational logging that exclude business inputs, secrets, and approval tokens.

## 20. Confirmed duplication that should be removed/simplified

### 20.1 Sales Invoice direct prerequisite mirror

`_direct_invoice_policy()` reads the same Selling Settings and Customer exception values as ERPNext `SalesInvoice.so_dn_required()`, then reconstructs the prerequisite decision before the native document is inserted. The source docstring itself says it is a mirror. This creates a second rule that can drift if ERPNext changes item-level checks, return/POS conditions, or prerequisite semantics.

The follow-up should preserve the MCP's useful blocked/needs-input experience only by obtaining the result from a safe native validation-backed path or by translating a native validation result. It must not simply move the same copied conditions into another helper.

### 20.2 Quotation valid-till mirror

The prepare path compares `valid_till` with `transaction_date` and returns `INVALID_QUOTATION_DETAILS`. ERPNext Quotation validation performs the same comparison. The native controller must own the comparison; MCP may map the native failure into its bounded contract.

## 21. Possible duplication needing business decision

| Finding | Why it may be valid | Decision needed |
|---|---|---|
| Item HSN preflight | Avoids running potentially side-effecting official hooks during prepare and gives a field-specific missing-input result | Identify a stable pure official helper or retain a tested compatibility adapter; never make MCP the final GST authority. |
| Commercial-default lists | Prevents approval for a preview missing essential commercial values | Decide whether each check is contract readiness or copied ERP requiredness; prefer runtime metadata/native default state. |
| Sales Order delivery date | Standalone MCP create needs a default even when the user omits the date | Keep defaulting if required; remove duplicate business rejection once native validation handles it. |
| Field-type catalog | Limits generic model-facing value strategies and rejects unknown future types safely | Keep as a bounded capability catalog, not a complete framework schema; add upgrade tests. |
| Static read/creation projections | Protects data minimization and stable public contracts | Keep, with runtime field existence checks and explicit handling of installed custom fields. |
| Customer duplicate suspicion | Provides a safer UX signal than blindly creating a likely duplicate | Keep only as a “possible duplicate” signal; do not present it as Frappe uniqueness authority. |

## 22. Thin bridge target architecture

```text
MCP boundary
  profile scope
  typed contract
  identity hand-off
  entity resolution
  missing-input / preview / approval
  bounded response and error envelope
        |
        v
Native runtime adapter
  frappe.get_meta / get_doc / get_list
  doc.has_permission / frappe.has_permission
  new_doc / set_missing_values
  native validation and controller methods
  insert / save / submit / cancel / delete
  ERPNext public conversion mappers
  official India Compliance helpers/hooks
        |
        v
Frappe / ERPNext / official app authority
  installed metadata and property setters
  permissions and document state
  validation, defaults, calculations, links, hooks
  transactions and persistence
```

The target does not mean “remove every preflight.” It means every preflight must have a documented MCP purpose and must not be an independent final copy of native business truth.

## 23. Migration risks

- Native validation messages and exception classes can change between ERPNext versions; tests must assert stable MCP codes/semantics, not fragile full text.
- Calling more native validation during preparation may expose side effects from hooks or official apps; the next task must verify prepare-time safety before changing behavior.
- Runtime property setters and custom fields differ by site; tests must use installed metadata rather than only base DocType JSON.
- Selling Settings and Customer exception combinations require coverage for both Sales Order and Delivery Note prerequisites, item-level links, return/POS exclusions, and Customer exceptions.
- Approval payload fingerprints must remain stable across prepare/confirm while the document is rebuilt from the approved request.
- Removing a preflight can change whether the user receives `blocked` versus a native validation-derived error; preserve bounded response semantics.
- Shared helpers are used by Purchase flows. Sales-only cleanup must not change Purchase behavior.
- India Compliance is optional; code must work with the app absent and must not import it unconditionally.
- Conversion behavior depends on the installed ERPNext mapper and must continue preserving source links and native calculations.

## 24. What should NOT change

- Do not remove or merge Sales/Purchase MCP profiles.
- Do not replace Frappe permission checks with MCP role or ownership logic.
- Do not use `ignore_permissions=True`, direct SQL, `db_update`, or direct database field writes for business mutations.
- Do not replace native `insert`, `save`, `submit`, `cancel`, `delete`, controller validation, calculations, hooks, or link checks.
- Do not duplicate ERPNext conversion mappings in MCP.
- Do not make India Compliance a hard dependency or copy its full GST rules.
- Do not expose approval tokens to LLM-authored approval semantics beyond the existing server-controlled contract.
- Do not redesign Purchase behavior as part of the Sales authority cleanup.
- Do not broaden read projections or email/PDF payloads merely to avoid metadata work.

## 25. Exact next implementation/refactor task

### Task: Replace confirmed Sales business-rule mirrors with native-validation-backed prepare behavior

**Scope:**

- `mcp_erpnext/services/selling/sales_invoice.py`
- `mcp_erpnext/services/selling/quotation.py`
- Their existing focused tests, currently including `mcp_erpnext/tests/test_sales_invoice.py` and `mcp_erpnext/tests/test_quotation_service.py`

**Required change:**

1. Remove or simplify `_direct_invoice_policy()` so MCP no longer independently evaluates `Selling Settings.so_required`, `dn_required`, or Customer exceptions as ERPNext business truth.
2. Remove the independent Quotation `valid_till` ordering decision from the prepare service.
3. Before implementation, verify that the chosen native validation-backed preparation path is non-persisting and safe with the installed official apps. If full native validation is not safe during prepare, identify a stable side-effect-free native seam or keep only a narrowly documented MCP readiness check pending an explicit business decision; do not recreate the controller rule under a new name.
4. Preserve MCP responsibilities: entity resolution, runtime defaults, data minimization, preview, approval, stale confirmation, native final insert, and bounded error/interaction responses.
5. Add regression coverage for valid and invalid quotation dates; Sales Invoice prerequisite settings, Customer exceptions, item-level prerequisites, and POS/return exclusions; permission failure; re-prepare after failure; and final native persistence. Verify Purchase tests and behavior remain unchanged.

**Out of scope:** profile changes, registry changes, lifecycle policy redesign, approval-policy changes, identity changes, India Compliance redesign, database migration, and Purchase behavior changes.

## 26. Acceptance checklist

- [x] Sales and Purchase profiles inspected.
- [x] Customer, Item, Quotation, Sales Order, Sales Invoice, Supplier, and Purchase Order inspected.
- [x] Additional public/shared surfaces inspected: lifecycle, conversions, PDF, email, read, aggregate, selection, metadata contracts, identity, approval, and India Compliance bridges.
- [x] Create, read, query, aggregate, update, child-row, submit, cancel, delete, convert, PDF, email, resolve, metadata, permission, approval, identity, and error paths traced.
- [x] Static lifecycle, field, permission, persistence, and exception patterns searched.
- [x] Runtime metadata and installed-app evidence collected read-only from `yob.localhost`.
- [x] Native Frappe/ERPNext/official-app authority locations identified.
- [x] Every meaningful finding classified as A, B, C, D, E, F, or G.
- [x] An authority matrix with MCP/Frappe/ERPNext ownership is included.
- [x] Confirmed duplication is separated from valid MCP logic and possible duplication.
- [x] A thin-bridge target architecture is included.
- [x] Migration risks and non-goals are documented.
- [x] The exact next implementation/refactor task is derived from this audit.
- [x] No production code, policy, contract, permission, lifecycle, data, or Purchase behavior was changed.

### Actions not performed

No implementation patch, formatter, build, migration, cache clear, service restart, MCP write call, database mutation, approval claim, commit, or branch/Git history change was performed. The only intended artifact from this task is this audit report.

