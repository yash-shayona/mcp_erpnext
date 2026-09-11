# Customer GST / India Compliance Native Flow Audit

## 1. Executive Summary

This is a source and read-only runtime inspection of the Customer GST flow in
the installed bench. No Customer, Address, or other business record was
created, and no GST/GSP external lookup was made.

The inspected site is `yob.localhost`. It has Frappe, ERPNext, India
Compliance, and `mcp_erpnext` installed. The effective Customer and Address
metadata contains India Compliance GST custom fields. The current
`prepare_customer` is already partially GST-aware because it accepts `gstin`,
checks the effective Customer metadata, validates an unsaved Address, and runs
unsaved Customer validation. It is not a complete native bridge: it ignores a
supplied `gst_category`, does not copy validation mutations into the approval
payload or preview, and detects `_address_line1` through `Customer` metadata
even though the installed native implementation uses that name as a transient
Quick Entry attribute rather than a DocField.

The native Quick Entry flow is client-triggered. Its reusable server capability
is `india_compliance.gst_india.utils.gstin_info.get_gstin_info`, which checks
Desk access, validates the GSTIN, reads recent archived results, and otherwise
calls the India Compliance Public API. The returned party name, GST category,
and permanent address are mapped into unsaved Quick Entry state. The native
method is directly callable inside the Frappe process; loopback HTTP and copied
GST/API logic are unnecessary.

However, the installed method is not a pure read operation. A successful API
request enqueues GSTIN-status work and an Integration Request persistence job;
the API call can also consume credits. Therefore the current method cannot be
called unconditionally from the existing no-business-write `prepare_customer`
boundary. The next implementation should add a lazy, optional India
Compliance adapter with a prepare-safe path. It may reuse native archived data
and native validation, but must not perform an external lookup or enqueue
auxiliary persistence during prepare unless a separately proven native
prepare-safe seam is introduced. Confirmation should use the approval-bound
effective payload and continue through normal `Customer.insert()`; native
Customer/Address validation and hooks remain authoritative.

## 2. Scope and Non-Changes

Inspected:

- Current `mcp_erpnext` Customer creation, public registration, approvals,
  runtime identity, tests, and tool catalog.
- Installed Frappe, ERPNext, and India Compliance Customer/Address source.
- India Compliance custom-field definitions, hooks, Quick Entry JavaScript,
  GSTIN utility, Public API client, settings, and tests/mocks.
- Read-only merged metadata, installed-app state, non-secret GST Settings
  flags, and version values on `yob.localhost`.

Only this report is changed:

`apps/mcp_erpnext/docs/inspect/CUSTOMER_GST_INDIA_COMPLIANCE_NATIVE_FLOW_AUDIT.md`

Not changed:

- `mcp_erpnext` runtime, contracts, schemas, tests, hooks, profiles, or
  settings.
- Frappe, ERPNext, or India Compliance source.
- Database records, Custom Fields, Property Setters, GST Settings, India
  Compliance credentials, Customer, Address, Contact, fixtures, or patches.

The real external API was not called. Secret values were not read or printed.

## 3. Current Installed Versions Observed

The versions were read from the installed Python application modules on the
active site, not assumed for architecture design:

| Application | Observed version | Evidence |
|---|---:|---|
| Frappe | `16.33.1` | `apps/frappe/frappe/__init__.py:58` and site expression inspection |
| ERPNext | `16.34.2` | `apps/erpnext/erpnext/__init__.py:9` and site expression inspection |
| India Compliance | `16.9.0` | `apps/india_compliance/india_compliance/__init__.py:5` and site expression inspection |
| mcp_erpnext | `0.0.1` | `apps/mcp_erpnext/mcp_erpnext/__init__.py:1` and site expression inspection |

These values are traceability evidence only. No architecture condition below
requires a fixed version string.

`bench version` was also attempted, but the command could not complete because
GitPython encountered dubious ownership in the installed India Compliance Git
checkout. The module-version and site inspections completed successfully.

## 4. Sites / Installed-App State Inspected

The active development site inspected was `yob.localhost`. The read-only
installed-app result was:

```text
frappe, yob_core, yob_auth, erpnext, payments, india_compliance,
yob_storefront, mcp_erpnext, mcp_identity
```

This came from the site database through:

```text
./env/bin/bench --site yob.localhost execute <read-only expression>
```

The presence of `india_compliance` in the bench directory or `apps.txt` was
not treated as site proof; the site database result above is the authority for
this report. Other site directories were listed but not used as runtime
evidence for this audit.

## 5. Current mcp_erpnext Customer Creation Call Flow

### `prepare_customer`

The current call flow is:

```text
MCP prepare_customer wrapper
  -> execute_tool_with_context
  -> _prepare_customer
  -> _current_user
  -> _customer_data
       -> narrow CREATION_FIELDS extraction
       -> resolve_creation_contract(Customer, frappe.get_meta, frappe.new_doc)
       -> resolve_contract_values for Customer Group / Territory links
       -> optional Contact flattening
       -> optional GSTIN metadata check and upper-casing
       -> optional unsaved Address validation
       -> flatten Address into Customer payload
  -> Customer permission check
  -> exact duplicate checks with permission-scoped get_list
  -> frappe.get_doc(data).run_method("validate")
  -> process-local approvals.create(payload=data)
  -> legacy preview
```

Evidence:

- The public wrapper is `mcp_erpnext/tools/masters/customer.py:60-63`.
- Authenticated user resolution is `mcp_erpnext/services/masters/customer.py:52-62`.
- Narrow input extraction and runtime-default resolution are at
  `mcp_erpnext/services/masters/customer.py:193-230`.
- Contact flattening and GSTIN handling are at
  `mcp_erpnext/services/masters/customer.py:232-253`.
- Address validation and flattening are at
  `mcp_erpnext/services/masters/customer.py:255-290`.
- Customer/Contact/Address permission checks are at
  `mcp_erpnext/services/masters/customer.py:293-305`.
- Duplicate reads use `ignore_permissions=False` at
  `mcp_erpnext/services/masters/customer.py:151-190`.
- Customer validation happens at
  `mcp_erpnext/services/masters/customer.py:341-355`.
- The approval payload is the pre-validation `data` dictionary passed at
  `mcp_erpnext/services/masters/customer.py:356-358`.
- The preview is reconstructed from that same pre-validation dictionary at
  `mcp_erpnext/services/masters/customer.py:316-338`.

`prepare_customer` does not insert Customer, Address, or Contact. It does run
validation, and installed hooks invoked by that validation may perform work
outside the intended pure-preview boundary; this is discussed in Section 17.

### `confirm_customer`

The current confirmation flow is:

```text
MCP confirm_customer wrapper
  -> execute_tool_with_context
  -> _current_user
  -> approvals.claim_for_confirm_write
  -> Customer/Contact/Address permission recheck
  -> duplicate recheck
  -> frappe.get_doc(approval.payload)
  -> doc.insert(ignore_permissions=False, ignore_links=False,
               ignore_mandatory=False)
  -> commit
```

Evidence:

- Public wrapper: `mcp_erpnext/tools/masters/customer.py:65-70`.
- Approval claim and context binding:
  `mcp_erpnext/services/masters/customer.py:367-384`.
- Permission and duplicate rechecks:
  `mcp_erpnext/services/masters/customer.py:385-388`.
- Normal insert and commit:
  `mcp_erpnext/services/masters/customer.py:390-399`.
- The approval store binds payload, site, and user and uses a process-local
  digest at `mcp_erpnext/approvals.py:23-85`.

Frappe `Document.insert()` itself checks create permission, links, before-insert
hooks, validation, `on_update`, and `after_insert`:
`apps/frappe/frappe/model/document.py:438-505`. Confirmation therefore
retains normal lifecycle behavior and does not use an Administrator fallback or
`ignore_permissions=True`.

## 6. Current Public Customer Creation Contract

`prepare_customer` and `confirm_customer` remain intentionally frozen legacy
contracts. They are registered as legacy entries in
`mcp_erpnext/contracts/registry.py:164-240` and documented as legacy public
schemas in `docs/TOOLS.md:73-89`.

The accepted Customer fields currently listed in
`mcp_erpnext/config/masters/customer.py:9-18` are:

```text
customer_name, customer_type, customer_group, territory, tax_id, gstin
```

The nested Contact mapping is explicitly limited to
`first_name`, `last_name`, `email`, and `mobile`, mapped to the Customer
fields at `customer.py:20-25`. The nested Address mapping is limited to
`address_line1`, `address_line2`, `city`, `state`, `pincode`, and `country` at
`customer.py:27-34`.

Findings:

1. `gstin` is already accepted publicly through the legacy object contract and
   `CREATION_FIELDS`; it is normalized to uppercase.
2. `gst_category` is not accepted by the creation field list and is silently
   excluded from the prepared Customer payload. It is not a supported generic
   field and there is no `extra_fields` dictionary.
3. Customer defaults are obtained from `frappe.new_doc("Customer")` by
   `resolve_creation_contract`; runtime metadata decides mandatory fields and
   defaults. Evidence: `creation_contract.py:53-115`.
4. Customer Group and Territory values are resolved against permitted link
   candidates through `resolve_contract_values`; evidence:
   `customer.py:221-230` and `config/masters/customer.py:40-45`.
5. Contact values are flattened into the Customer payload. Normal Customer
   lifecycle behavior later creates a Contact when those fields are present.
6. An Address is validated unsaved during prepare, but the current service does
   not insert it separately. It flattens address values into the Customer
   payload for Customer lifecycle helpers.
7. Validation mutations are not copied back. `run_method("validate")` is
   called on a document made from `data`, but the resulting document is
   discarded; the approval payload and preview still use the original
   dictionary. This is confirmed by `customer.py:354-363`.

## 7. Effective Customer and Address GST Metadata

### Source definition

India Compliance defines `party_fields` for both Customer and Supplier in
`apps/india_compliance/india_compliance/gst_india/constants/custom_fields.py:19-48`:

- `gstin`: Custom Field, `Autocomplete`, label `GSTIN / UIN`, optional.
- `gst_category`: Custom Field, `Select`, default `Unregistered`, required,
  with options supplied by `GST_CATEGORIES`.

The same `party_fields` object is assigned to both Customer and Supplier in
`custom_fields.py:547-548`, and custom fields are created through
`setup/__init__.py:46-50`.

Address GST fields are defined in
`custom_fields.py:1212-1257`:

- `gstin`: Custom Field, `Data`, optional.
- `gst_state`: Custom Field, `Select`, read-only.
- `gst_category`: Custom Field, `Select`, default `Unregistered`, required.
- `gst_state_number`: Custom Field, `Data`, read-only.

### Runtime result on `yob.localhost`

The merged metadata and `Custom Field` records agree:

| DocType | Field | Type | Required/default | Other effective properties |
|---|---|---|---|---|
| Customer | `gstin` | Autocomplete | optional | editable; no dependency/fetch |
| Customer | `gst_category` | Select | required; `Unregistered` | editable; ten native options |
| Address | `gstin` | Data | optional | editable; no dependency/fetch |
| Address | `gst_category` | Select | required; `Unregistered` | editable; ten native options |
| Address | `gst_state` | Select | optional | read-only |
| Address | `gst_state_number` | Data | optional | read-only |

The runtime query found no Customer `_address_line1`, `_pincode`, or equivalent
underscore-prefixed DocField. It found no Address `_address_line1` either.

The Customer core JSON defines `customer_name` and `customer_type` as required,
with `customer_type` default `Company`, at
`apps/erpnext/erpnext/selling/doctype/customer/customer.json:116-152`.
Address core JSON defines `address_line1`, `city`, and `country` as required
core fields at `apps/frappe/frappe/contacts/doctype/address/address.json:53-92`.
India Compliance adds conditional server-side Address rules for Indian state
and pincode through `setup/property_setters.py:13-31`.

## 8. India Compliance Hooks Relevant to Customer/Address

The installed hooks register:

```text
Customer.validate    -> india_compliance.gst_india.overrides.party.validate_party
Customer.after_insert -> india_compliance.gst_india.overrides.party.create_primary_address

Address.validate     -> india_compliance.gst_india.overrides.address.validate
Address.validate     -> india_compliance.gst_india.overrides.party.set_docs_with_previous_gstin
Address.on_update     -> india_compliance.gst_india.overrides.address.update_party_gstin_and_gst_category
```

Evidence: `apps/india_compliance/india_compliance/hooks.py:123-149`.

Customer validation is implemented by `validate_party` at
`gst_india/overrides/party.py:17-22`:

1. Native `validate_gstin` normalizes and checks length/check digit.
2. `set_gst_category` fetches or derives the category.
3. `validate_gst_category` checks category/GSTIN compatibility.
4. PAN is derived or validated.
5. Previous-GSTIN response bookkeeping is prepared when relevant.

Address validation is implemented by `gst_india/overrides/address.py:51-103`:
it applies native GSTIN/category validation, overseas-category validation,
Indian state/GSTIN consistency, and pincode validation.

The Customer after-insert hook is not a duplicate of the ERPNext core helper.
It is a modified helper specifically for `_address_line1`, at
`gst_india/overrides/party.py:129-163`. It inserts an Address with Customer
GSTIN/category, links it to the new Customer, and sets the primary-address
fields through `db_set`.

## 9. Quick Entry GSTIN Autofill Client Trigger

India Compliance is included globally through
`hooks.py:41` (`app_include_js = "india_compliance.bundle.js"`), and the bundle
imports `quick_entry` at `public/js/india_compliance.bundle.js:1-3`.

The native trigger is:

```text
GSTQuickEntryForm constructor
  -> api_enabled = india_compliance.is_api_enabled()
                    && gst_settings.autofill_party_info
  -> transient `_gstin` field onchange
  -> duplicate GSTIN check and Customer type inference
  -> if api_enabled && !sandbox_mode: autofill_fields(dialog)
  -> otherwise state-from-GSTIN and native client category guess
```

Evidence: `apps/india_compliance/india_compliance/public/js/quick_entry.js:1-10`
and `quick_entry.js:88-121`.

The Quick Entry class creates transient fields, not DocFields:

- `_gstin` is created from the real GSTIN metadata field at
  `quick_entry.js:88-96`.
- `_pincode` is an Autocomplete helper at `quick_entry.js:39-49`.
- Customer/Supplier `update_doc()` moves the address line to
  `_address_line1` and maps contact helpers at `quick_entry.js:213-226`.
- The base `update_doc()` moves `_gstin` to `gstin` at
  `quick_entry.js:124-129`.

Thus browser Quick Entry uses underscore-prefixed temporary object properties
to avoid form-layout/read-only collisions. They are not evidence of effective
Customer metadata fields.

## 10. Native GSTIN Autofill Server Call Chain

The actual installed chain is:

```text
Quick Entry `_gstin` onchange
  -> autofill_fields(dialog)
  -> get_gstin_info(gstin, doctype)
  -> frappe.call(
       "india_compliance.gst_india.utils.gstin_info.get_gstin_info",
       {gstin, throw_error: true, doc: {doctype}}
     )
  -> whitelisted get_gstin_info(gstin, doc, throw_error)
  -> Desk-access check for frappe.session.user
  -> _get_gstin_info
       -> native validate_gstin
       -> recent Integration Request archive lookup
       -> PublicAPI(doc).get_gstin_info(gstin) when no archive result
       -> enqueue GSTIN status update
       -> normalize business name/category/status/address
  -> map_gstin_info(dialog.doc, result)
       -> gstin and gst_category
       -> Customer/Supplier name
       -> permanent address fields
       -> all-address pincode choices
  -> Quick Entry update_doc
  -> normal Frappe Customer insert
```

Evidence:

- Client call: `public/js/quick_entry.js:402-477`.
- Client mapping: `public/js/quick_entry.js:479-510`.
- Server wrapper and permission check:
  `gst_india/utils/gstin_info.py:49-58`.
- Native lookup, archive path, API call, status enqueue, and normalized result:
  `gst_india/utils/gstin_info.py:61-108`.
- Returned address normalization:
  `gst_india/utils/gstin_info.py:144-192`.
- Public API endpoint selection:
  `gst_india/api_classes/public.py:9-40`.

The underlying Python capability is directly callable in-process. The
whitelisted decorator does not require a loopback HTTP request. The public
wrapper is the safer bridge candidate than the private `_get_gstin_info`
function because it preserves the native Desk-access check. Directly calling
the private helper would bypass that wrapper check.

The capability is not read-only in the strict MCP prepare sense. On an API
request, `BaseAPI._make_request` always enqueues an Integration Request in its
`finally` block (`api_classes/base.py:162-215`); the worker creates and inserts
an `Integration Request` with `ignore_permissions=True` at
`utils/api.py:4-37`. `_get_gstin_info` also enqueues GSTIN status work at
`gstin_info.py:73-78`. The API request itself is external I/O.

## 11. India Compliance API / Account / Settings Gates

The source gate chain is:

```text
is_api_enabled(settings)
  = settings.enable_api
    && (settings.api_secret || frappe.conf.ic_api_secret)

is_production_api_enabled(settings)
  = is_api_enabled(settings) && !settings.sandbox_mode

is_autofill_party_info_enabled()
  = is_production_api_enabled(GST Settings)
    && settings.autofill_party_info
```

Evidence: `gst_india/utils/__init__.py:850-875`.

`BaseAPI.__init__` repeats the API gate and raises if disabled at
`api_classes/base.py:50-67`. Its request header uses the native GST Settings
API secret or `frappe.conf.ic_api_secret`; no mcp_erpnext credential is
required or appropriate (`base.py:58-63`). The Public API does not fetch a
GST Credential row. GST Credential rows are used by other authenticated NIC
services through `BaseAPI.fetch_credentials` at `base.py:73-96`.

Relevant GST Settings fields are defined at
`gst_india/doctype/gst_settings/gst_settings.json:273-313` and
`gst_settings.json:344-353`:

- `enable_api` controls the API master gate.
- `autofill_party_info` enables Quick Entry party enrichment.
- `sandbox_mode` prevents production party autofill.
- `archive_party_info_days` controls recent archived-result reuse.
- `api_secret` is a native Password field and was not read as a value.

The installed Public API has no separate “India Compliance Account” gate for
the party lookup. Its usable credential is the native API secret/configuration
gate. Authenticated NIC services may additionally require GST Settings
credential rows; that is not the path used by Quick Entry party lookup.

## 12. Local Development and Developer Mode Findings

The read-only runtime result for `yob.localhost` was:

| Boolean/setting | Observed value |
|---|---:|
| `GST Settings.enable_api` | `true` |
| `GST Settings.autofill_party_info` | `true` |
| `GST Settings.sandbox_mode` | `true` |
| API secret present in GST Settings | `false` |
| API secret present in site config | `false` |
| native `is_api_enabled()` | `false` |
| native `is_production_api_enabled()` | `false` |
| native `is_autofill_party_info_enabled()` | `false` |
| `frappe.conf.developer_mode` | `true` |

The values were obtained without printing either secret. The source default
setup sets `sandbox_mode` when `frappe.conf.developer_mode` is true at
`gst_india/setup/__init__.py:210-250`, but developer mode does not supply an API
secret and does not make `is_api_enabled()` true. This directly disproves the
assumption that developer mode enables India Compliance API access.

On this local site, Quick Entry therefore does not call `autofill_fields`:
`quick_entry.js:5` requires the API gate and autofill setting, while
`quick_entry.js:108-118` falls back to state extraction and
`guess_gst_category`. Customer/Address server validation also does not enter
the external `_get_gstin_info` branch because
`is_autofill_party_info_enabled()` is false; it still performs native local
GSTIN/category validation.

## 13. Sandbox Findings, If Applicable

Sandbox behavior is explicitly present in the installed source:

- The Public API client raises “Autofill Party Information based on GSTIN is
  not supported in sandbox mode” during setup at
  `gst_india/api_classes/public.py:17-20`.
- Quick Entry avoids calling the server lookup in sandbox mode and only derives
  state/category locally at `public/js/quick_entry.js:108-118`.
- The API base class can construct test URLs and shows a sandbox message for
  API requests at `api_classes/base.py:98-110` and `base.py:216-220`, but the
  Public API party-autofill setup rejects sandbox first.

The current site is in sandbox mode and has no usable API secret, so no claim
is made that a sandbox external lookup is available. No sandbox API call was
made.

## 14. GST Category Native Behavior

The Customer and Address `gst_category` fields are required Custom Fields with
default `Unregistered` and the same ten effective options:

```text
Registered Regular
Registered Composition
Unregistered
SEZ
Overseas
Deemed Export
UIN Holders
Tax Deductor
Tax Collector
Input Service Distributor
```

Source: `gst_india/constants/custom_fields.py:39-46` and
`custom_fields.py:1241-1249`; runtime metadata returned the same values.

Customer native category precedence is in
`gst_india/overrides/party.py:25-58`:

1. Existing `Overseas` is preserved.
2. Existing `Deemed Export` is preserved when a GSTIN exists.
3. If a GSTIN exists, production autofill is enabled, and the request is not
   an import, native GSTIN information can supply the category.
4. Otherwise `guess_gst_category` derives the category from GSTIN, country, and
   the existing category.

`validate_gst_category` requires `Unregistered` or `Overseas` without a GSTIN,
rejects `Unregistered` with a GSTIN, and validates the GSTIN against the native
category format when present (`gst_india/utils/__init__.py:286-320`).

The GSTIN service maps returned API business types to category values through
`GST_CATEGORIES` at `gstin_info.py:27-38` and result construction at
`gstin_info.py:95-100`.

Address uses the same category setter and validation. An Address may legally
have a different category from its Customer because an Address carries its own
GSTIN/category, but India Compliance's native Customer primary-address helper
copies the Customer values into the newly created primary Address at
`overrides/party.py:146-162`.

MCP must accept and preview native effective category values in the next
implementation, but must not duplicate these derivation, format, state, or
category rules.

## 15. Customer Address Native Behavior

### ERPNext-only site

ERPNext Customer `on_update` invokes `create_primary_contact()` and
`create_primary_address()` at
`apps/erpnext/erpnext/selling/doctype/customer/customer.py:275-285`.
The core address helper runs when a new Customer has `address_line1` and calls
ERPNext `make_address`, which inserts an Address containing core address fields
and links it to the Customer (`customer.py:312-323` and
`customer.py:966-1002`). It does not copy India Compliance GST fields because
those fields are not part of the ERPNext-only helper dictionary.

### India Compliance site

India Compliance registers Customer `after_insert` to
`create_primary_address` (`hooks.py:146-149`). Its helper only runs when the
new Customer has transient `_address_line1`, then calls its own `make_address`
with `gstin` and `gst_category` and inserts the linked Address
(`overrides/party.py:129-163`). It sets the Customer primary-address fields
after the Address insert.

This creates an important current MCP mismatch: on the inspected site,
`frappe.get_meta("Customer").has_field("_address_line1")` is false, so current
MCP stores the input address as `address_line1` at
`mcp_erpnext/services/masters/customer.py:277-285`. On confirmation, ERPNext
core can therefore create the Address through its `address_line1` path, while
the India Compliance after-insert helper sees no `_address_line1`. The current
MCP path is consequently not equivalent to native India Compliance Quick Entry
for GST-bearing primary addresses.

The safe next implementation must deliberately select the native transient
payload convention only when the installed app's native Customer hook is
present, and must ensure the actual Address data is approval-bound. It must not
cause both ERPNext and India Compliance address helpers to create duplicate
addresses.

## 16. `_address_line1` / Transient Helper Finding

`_address_line1` is a transient Quick Entry helper, not a Customer DocField:

- Quick Entry creates it by renaming the address-line value in
  `public/js/quick_entry.js:213-219`.
- India Compliance's Customer after-insert hook reads it at
  `overrides/party.py:134-151`.
- The runtime `frappe.get_meta("Customer")` inspection returned
  `has_field("_address_line1") == False`.
- The runtime `Custom Field` query returned no such field.

The current detection is therefore incorrect:

```python
"_address_line1" if _customer_has_field("_address_line1") else "address_line1"
```

Evidence: `mcp_erpnext/services/masters/customer.py:277-285`; the test double
also incorrectly injects `_address_line1` into fake Customer metadata at
`mcp_erpnext/tests/test_customer_service.py:59-76`. This is a confirmed source
and test-model defect, not an assumption. It was not fixed because this task
allows only the inspection report to change.

## 17. Prepare-Time Side Effects and Safety

The current prepare boundary does not insert an ERPNext Customer, Address, or
Contact. That is confirmed by the absence of insert/commit in the prepare path
and by the approval creation call at `customer.py:341-364`.

It is not fully side-effect-free on an India Compliance site:

1. Unsaved Address validation at `customer.py:276` invokes India Compliance
   Address validation. In a production-autofill configuration, the shared
   category setter can call `_get_gstin_info`.
2. Unsaved Customer validation at `customer.py:355` invokes
   `validate_party`. With a GSTIN and production autofill enabled,
   `party.py:52-58` calls `_get_gstin_info`.
3. `_get_gstin_info` may perform external Public API I/O and enqueue GSTIN
   status work (`gstin_info.py:61-78`).
4. `BaseAPI._make_request` enqueues Integration Request persistence in its
   `finally` block (`api_classes/base.py:162-215`), with the worker inserting
   that record at `utils/api.py:11-37`.

Accordingly:

- Native lookup is not a pure read/fetch service in this installed source.
- Calling it from prepare can consume API credits and create auxiliary
  Integration Request/GSTIN status effects.
- Calling the current public wrapper directly is technically possible and
  preserves the native Desk-access check, but is not safe as an unconditional
  implementation of the existing `PREPARE` side-effect contract.
- Calling the private helper would avoid only the wrapper permission check, not
  the external and queued effects, and is therefore not recommended.

The current local site does not enter the production autofill branch because
all native API/autofill predicates are false. That local result does not prove
that a production-configured site would be side-effect-free.

## 18. Permission and Identity Behavior

### MCP identity and Customer lifecycle

The MCP runtime initializes the configured site, resolves HTTP identity through
the authenticated request, and sets the resolved Frappe user at
`mcp_erpnext/runtime.py:86-141`. It never uses client-supplied Frappe user
identity as a fallback for HTTP. `_current_user` rejects Guest at
`mcp_erpnext/services/masters/customer.py:52-62`.

`prepare_customer` checks Customer create permission, and conditionally Contact
and Address create permission at `customer.py:293-305`. Duplicate reads use
permission-aware `frappe.get_list(..., ignore_permissions=False)`.
Confirmation repeats these checks and inserts with all three normal safety
flags false at `customer.py:385-399`.

### Native lookup

The whitelisted native `get_gstin_info` explicitly checks that the current
Frappe user has Desk access at `gstin_info.py:49-58`. Calling this public Python
function directly under the existing Frappe request/user context preserves
that check. A loopback HTTP call would add transport/auth complexity without
adding a native permission boundary.

The native lookup does not check Customer create permission because it is a
fetch/autofill capability. Customer and Address creation permissions remain
the responsibility of the normal document lifecycle. Native Address creation
uses ordinary `insert()` in `overrides/party.py:146-163`; MCP must not change
that to an ignored-permission insert.

No Administrator fallback, service-user bypass, hardcoded role, or
`ignore_permissions=True` bridge is permitted by this evidence.

## 19. Error / Failure Behavior

### Existing MCP behavior

Current Customer preparation returns or raises the following established
outcomes:

- Invalid object shape: `INVALID_CUSTOMER_DETAILS`,
  `customer.py:197-202`.
- Missing runtime-required input: shared `needs_input` result,
  `customer.py:209-219` and `creation_contract.py:119-125`.
- Invalid/ambiguous/not-found link values: shared resolver outcomes,
  `customer.py:221-229`.
- GSTIN absent from effective metadata: `GSTIN_UNSUPPORTED`,
  `customer.py:245-253`.
- Permission denial: `permission_denied`, `customer.py:308-313`.
- Duplicate: `duplicate_suspected`, `customer.py:349-352`.
- Native validation exceptions: no local conversion in `prepare_customer`, so
  they flow through the existing tool observability/error path.
- Confirm errors: shared approval failure conversion at
  `customer.py:379-384`, with rollback for permission/general exceptions at
  `customer.py:390-399`.

### Native outcomes and recommended mapping

| Native condition | Observed native behavior | Next-task mapping |
|---|---|---|
| India Compliance absent | ERPNext Customer lifecycle has no IC hooks/fields | Keep current flow unchanged; no integration import at module load |
| GSTIN omitted | Category is native default/guess path; no lookup | Keep manual Customer/Address behavior |
| API/autofill disabled | Quick Entry does local state/category fallback; server validation skips remote fetch | Do not call an external API; continue native local validation |
| API/account unavailable | Base API raises a native configuration/API error; `throw_error=False` path logs and returns empty result | Return a safe actionable availability result or continue native fallback, without secrets; do not approve incomplete enrichment as if fetched |
| Native lookup succeeds | Returns normalized business name, category, status, permanent/all addresses | Use only a prepare-safe native result; bind effective values into approval payload and preview |
| Native GSTIN invalid/not found | Format/check-digit validation raises; `FO8000` is normalized to status `Invalid` by Public API | Return a safe actionable validation/not-found result; no approval/write |
| Conflicting user values | Quick Entry mapping overwrites mapped name/category/address fields; source has no MCP conflict policy | Next task must define explicit precedence based on native mapping, surface the effective preview, and avoid silently inventing another rule |
| Category missing | Native defaults/derives category where possible; `validate_gst_category` remains authoritative | Do not duplicate category derivation; include effective category in preview |

The next implementation should use the existing shared interaction contract for
continuation/approval results, not ad-hoc `approval_needed` or client-specific
fields. The shared semantic directive schema is in
`mcp_erpnext/contracts/interaction.py:13-85`; current legacy Customer tools do
not yet declare typed interaction metadata.

### Required behavior matrix

| Scenario | Native app state | Expected MCP bridge behavior | Source evidence | Live verified? |
|---|---|---|---|---|
| ERPNext-only site | India Compliance absent | Existing Customer flow unchanged; no optional import failure | `mcp_erpnext/services/masters/customer.py:245-253`; ERPNext Customer helper `customer.py:312-323` | No; no second site runtime tested |
| India Compliance installed, no GSTIN | GST extension present; no GSTIN input | Native normal Customer/category/address behavior; no remote lookup | `overrides/party.py:43-58`; `overrides/address.py:51-58` | No; no Customer write |
| GSTIN supplied, autofill disabled | `is_autofill_party_info_enabled()` false | Follow native non-autofill fallback and local validation; do not call external API | `utils/__init__.py:850-875`; `quick_entry.js:108-118` | Partially; gate runtime-read on `yob.localhost`, no tool/UI run |
| GSTIN supplied, autofill enabled but API unavailable | Autofill preference true but API gate/account/config unavailable | Follow native safe error/fallback; never bypass native gate or call a custom API | `utils/__init__.py:857-875`; `base.py:50-63`; `party.py:52-58` | No; no unavailable production call |
| GSTIN supplied, autofill available | API enabled, production mode, autofill preference true | Reuse only a prepare-safe native result in the approval preview; otherwise report unavailable enrichment | `quick_entry.js:402-477`; `gstin_info.py:61-108`; side-effect evidence in `api.py:4-37` | No; no external lookup |
| Native GSTIN invalid/not found | Native format/check-digit failure or Public API `FO8000` | Return safe actionable validation/not-found outcome; no approval/write | `utils/__init__.py:248-283`; `public.py:45-58`; `test_gstin_info.py:203-225` | No; source/test mocks only |
| User supplies address without GSTIN lookup | Manual address path | Preserve native Customer/Address validation and normal ERPNext/IC lifecycle | `mcp_erpnext/services/masters/customer.py:255-290`; `overrides/address.py:51-103` | No; no write |
| India Compliance creates primary Address after Customer insert | Customer `after_insert` hook registered | Pass the native transient address convention when applicable; do not create a second Address | `hooks.py:146-149`; `overrides/party.py:129-163` | No; no write |
| ERPNext-only manual address creation | No India Compliance hook | Preserve core `address_line1` helper behavior | `erpnext/selling/doctype/customer/customer.py:312-323`; `customer.py:966-1002` | No; no second site runtime tested |

## 20. ERPNext-Only Compatibility

ERPNext-only behavior can remain unchanged if India Compliance integration is
lazy and absent-capability handling returns to the current code path. The
existing Customer service already detects the `gstin` metadata field before
accepting GSTIN, and core Customer creation uses `address_line1` through the
ERPNext helper (`customer.py:312-323` and `customer.py:966-1002`).

The adapter must therefore:

- not import India Compliance unconditionally at `mcp_erpnext` module import
  time;
- detect the installed site capability at runtime;
- not make missing India Compliance an error for ordinary Customer creation;
- not change ERPNext-only Customer/Address field mapping;
- preserve normal Frappe permissions, links, validation, and hooks.

## 21. Architecture Options Comparison

| Option | Installed-source result | Decision |
|---|---|---|
| A. Rely only on `Customer.insert()` hooks | Insert runs native Customer validation and conditional after-insert behavior, but does not reproduce Quick Entry's returned name/address mapping. It only uses `_address_line1` for IC primary-address creation. | Insufficient alone |
| B. Copy Quick Entry/client logic | Quick Entry is UI state management: transient fields, onchange, dialog refresh, pincode selector, and mapping. Copying it would duplicate browser UX and GST rules. | Reject |
| C. Call native whitelisted method through HTTP | The method is already in the same Frappe process and has a directly callable Python wrapper. Loopback HTTP adds auth/transport failure and identity complexity. | Reject |
| D. Directly call native Python capability | `get_gstin_info` is directly callable and preserves Desk access; the private helper does not. But current implementation performs external I/O and enqueues persistence. | Use only behind a prepare-safe policy/seam |
| E. Reimplement GST/GSP API in MCP | Native `PublicAPI`, settings gate, error mapping, masking, logging, archive, and status behavior already own this logic. | Reject |
| F. Lazy optional integration adapter | Keeps ERPNext-only startup independent and centralizes capability detection. Can reuse native metadata/validation and an archived/read-only path without duplicating GST logic. | Recommended boundary |

No new `create_gst_customer` tool is justified by the installed source.

## 22. Recommended Bridge Architecture

The frozen boundary for the next implementation should be:

```text
prepare_customer
  -> current authenticated context and generic Customer defaults/resolution
  -> detect native Customer GST capability lazily for the current site
  -> if India Compliance is absent:
       retain current ERPNext-only path
  -> if GSTIN is omitted:
       retain native manual category/address path
  -> if GSTIN is supplied and a prepare-safe native result is available:
       reuse the installed native GSTIN result/normalization
       under the current Frappe user context
       bind effective Customer name/category/GSTIN/address values
       run native unsaved validation without persisting auxiliary records
  -> if the only available native path would call the external API or enqueue
     Integration Request/status work:
       do not call it during prepare under the current PREPARE contract;
       return the established safe availability/input result or continue the
       documented native non-autofill path
  -> build preview from the post-native effective document values
  -> approval binds the complete effective Customer/Contact/Address/GST state

confirm_customer
  -> existing process-local approval claim and site/user binding
  -> existing Customer/Contact/Address permission and duplicate rechecks
  -> normal Customer insert with ignore_permissions=False,
     ignore_links=False, ignore_mandatory=False
  -> native Customer validation/hooks remain authoritative
  -> use approval-bound effective values; do not MCP-refetch GSTIN
  -> do not duplicate India Compliance primary Address creation
  -> commit only after normal insert succeeds
```

The optional adapter/provider belongs under an integration-specific service
module next to existing integrations, for example:

```text
mcp_erpnext/services/integrations/india_compliance_customer.py
```

That path is a recommendation for Task 25, not a file created by this audit.
It should be lazily imported from the Customer service only after a runtime
capability check. It should call the public native Python wrapper when a
prepare-safe result is proven, not the browser code and not a copied API
client. It should not become a general plugin framework.

The source evidence means the default implementation must not simply call
`get_gstin_info` during every prepare: the installed method's queued
Integration Request/GSTIN-status behavior violates the current strict prepare
boundary. The adapter should initially support the native archived-result path
or another explicitly non-persisting native seam, and report unavailable
remote enrichment safely when no such result exists.

Confirmation should not perform a second MCP-level lookup. It should use the
approval-bound preview. Normal `Customer.insert()` necessarily reruns native
validation as part of Frappe insert (`document.py:474-487`), and a
production-configured India Compliance Customer validation can itself invoke
the installed native lookup. The next task must document that native lifecycle
behavior rather than bypassing it or adding a duplicated refetch.

## 23. Required MCP Contract Change, If Any

The current public contract already exposes `gstin`, so no new GSTIN field is
required.

The smallest explicit extension for the next implementation is a typed/top-
level `gst_category` Customer field, with values resolved and validated by
native runtime metadata. It should be added to the Customer creation contract
only as an explicit field; do not add `extra_fields: dict`.

The prepared output/preview must also expose the effective native
`gst_category` and any native-enriched Customer name/address values that are
actually approval-bound. This is necessary because current validation mutation
is discarded and the legacy preview currently includes only `gstin`, not
`gst_category` (`customer.py:316-338`).

The contract remains the existing `prepare_customer -> confirm_customer` pair.
No new public tool is required. Because both tools are frozen legacy entries,
the next implementation must either perform the smallest deliberate legacy
contract migration or document why the explicit field can be added without
breaking existing callers; it must not silently widen the object with
arbitrary fields.

## 24. Test Plan for Next Implementation Task

The following tests are required in the separately authorized implementation
task. They were not added here.

1. ERPNext-only capability absent: lazy import/capability check does not load
   India Compliance and the current Customer prepare/confirm behavior remains
   unchanged.
2. India Compliance present with GSTIN omitted: no remote lookup, native
   manual category/default behavior, and normal Address validation.
3. API disabled or no usable native API configuration: no external HTTP call,
   no MCP-created Integration Request, safe actionable availability/fallback
   result, and normal native validation.
4. Sandbox mode: no party-autofill HTTP call; native local fallback behavior is
   preserved.
5. Archived native GSTIN result: adapter consumes the native normalized result
   without an external call or queued persistence, and the effective category,
   name, address, and GSTIN appear in both approval payload and preview.
6. Native invalid/check-digit/not-found result: no approval token and no
   Customer/Address write.
7. User category/name/address precedence: explicit, source-backed precedence
   is reflected in the effective preview; no hidden duplicate business rule is
   introduced.
8. Customer validation mutation: a fake/native validation result that changes
   category or normalized values is copied into the approval-bound payload and
   preview.
9. India Compliance primary Address path: confirm with the native transient
   address convention creates exactly the native primary Address once and
   preserves GSTIN/category; the MCP service does not insert a second Address.
10. ERPNext-only primary Address path: `address_line1` continues to use the
    core ERPNext helper.
11. Permission and identity: native lookup runs as the authenticated user;
    Guest, missing Desk access, Customer create denial, and Address create
    denial do not use bypasses.
12. Approval safety: confirm uses approval-bound values, does not refetch in
    MCP, rechecks duplicates, and retains the existing trusted approval guard.
13. Public contract: explicit `gst_category` is accepted/rejected according to
    the migrated schema; arbitrary `extra_fields` remains unavailable.

Static/unit tests must be distinguished from live external API, database,
native hook, queue, and browser verification.

## 25. Known Limitations / Not Live Verified

- No real GST/GSP/India Compliance external lookup was made.
- No API credit, sandbox endpoint, or account subscription was tested.
- No Customer, Address, Contact, Integration Request, GSTIN status, or Error
  Log record was created by this audit.
- No actual MCP `prepare_customer` request was run on the live site.
- No live Customer insert or after-insert hook execution was performed.
- No browser Quick Entry interaction was executed.
- The runtime metadata/settings query was read-only and did not inspect secret
  values.
- `bench version` did not complete because of the installed India Compliance
  Git ownership warning; module values and site module imports were observed.
- Existing India Compliance tests use mocks/fixtures; they establish source
  expectations, not current external service availability. The relevant mock
  result shape is in `gst_india/utils/test_gstin_info.py:11-124`, and the
  invalid `FO8000` behavior is covered at `test_gstin_info.py:203-225`.
- The current `mcp_erpnext` Customer tests use a fake metadata field for
  `_address_line1` (`tests/test_customer_service.py:59-76`), so those tests do
  not prove the installed merged metadata or native after-insert path.

## 26. Final Frozen Decision Proposal

1. `prepare_customer` is partially GST-aware but currently not native-flow
   equivalent.
2. `gstin` is already publicly accepted; `gst_category` is currently missing.
3. Quick Entry autofill is client-triggered and calls a server-side native
   India Compliance function.
4. The correct in-process bridge target is the public Python function
   `get_gstin_info`, not browser code, loopback HTTP, or a copied API client.
5. `Customer.insert()` alone conditionally invokes native external lookup during
   Customer validation when production autofill is enabled, but it does not
   reproduce Quick Entry's party/address mapping. It does still invoke native
   validation and after-insert behavior.
6. India Compliance creates/copies GST data into a primary Address only when
   its `_address_line1` transient convention is supplied to its after-insert
   helper.
7. `_address_line1` is not a real Customer DocField, and current MCP metadata
   detection is incorrect.
8. Developer mode does not enable API access; the current site has developer
   mode and sandbox enabled but native API/autofill predicates false.
9. The current native lookup is not prepare-safe as-is because it performs
   external I/O and queues auxiliary persistence. A Task 25 adapter must
   enforce a prepare-safe native/read-only boundary.
10. Confirmation must not perform a separate MCP refetch. It must use the
    approval-bound effective payload and let normal Frappe/ERPNext/India
    Compliance validation run.
11. ERPNext-only sites can remain unchanged through lazy optional integration.
12. No new public GST Customer tool is required.

### Explicit frozen findings

1. **YES** — Current `prepare_customer` is already partially GST-aware: it
   accepts/normalizes GSTIN, checks metadata, validates an unsaved Address, and
   runs unsaved Customer validation (`mcp_erpnext/services/masters/customer.py:245-285`,
   `customer.py:341-355`).
2. **YES** — `gstin` is already accepted publicly through
   `config/masters/customer.py:9-18` and `customer.py:245-253`.
3. **YES** — `gst_category` is missing from the MCP creation contract; it is
   absent from `CREATION_FIELDS` and is not copied from the input dictionary
   (`config/masters/customer.py:9-18`, `customer.py:204-230`).
4. **YES** — Quick Entry autofill is triggered client-side by the transient
   `_gstin` onchange (`public/js/quick_entry.js:88-121`).
5. **YES** — The actual GST lookup is server-side in India Compliance through
   the whitelisted `get_gstin_info` and `_get_gstin_info`
   (`gstin_info.py:49-108`).
6. **CONDITIONAL** — The native public Python function can be called directly
   in-process under the current user, but the installed implementation is not
   prepare-safe as-is because it performs external I/O and queues persistence
   (`gstin_info.py:49-78`, `api_classes/base.py:162-215`, `utils/api.py:11-37`).
7. **CONDITIONAL YES** — `Customer.insert()` conditionally triggers external
   GSTIN lookup through Customer validation when production autofill is enabled;
   it does not reproduce Quick Entry's full mapping (`document.py:438-505`,
   `overrides/party.py:17-58`).
8. **YES** — Normal insert hooks still perform India Compliance Customer
   validation and registered after-insert behavior (`hooks.py:146-149`).
9. **YES** — India Compliance's primary-address hook copies Customer GSTIN and
   category into its inserted primary Address when `_address_line1` is present
   (`overrides/party.py:129-163`).
10. **NO** — `_address_line1` is not a real Customer DocField; it is a transient
    Quick Entry helper (`public/js/quick_entry.js:213-219`, runtime metadata).
11. **NO** — Current MCP detection of that helper through
    `frappe.get_meta("Customer").has_field()` is not correct; runtime returned
    false and the source creates the property only in JavaScript
    (`mcp_erpnext/services/masters/customer.py:277-285`).
12. **NO** — `developer_mode` does not enable API access. It can default
    sandbox mode during setup, but `is_api_enabled()` still requires the native
    API secret/configuration (`setup/__init__.py:210-250`, `utils/__init__.py:857-875`).
13. **CONDITIONAL** — Autofill requires `enable_api`, a native GST Settings or
    site-config API secret, production mode (`sandbox_mode` false), and
    `autofill_party_info`; the Public API uses the native API key rather than a
    separate GST Credential account (`base.py:50-67`, `utils/__init__.py:857-875`).
14. **CONFIRMED LOCAL** — On `yob.localhost`, the site has API/autofill
    preference flags true but no API secret/config value, sandbox true, and all
    native API/autofill predicates false. Normal Quick Entry therefore uses
    local state/category fallback; no live Customer operation was run.
15. **NO, as-is** — The current native lookup cannot safely be used in
    prepare without persistent/queued side effects; an archived/read-only or
    separately proven prepare-safe seam is required (`utils/api.py:4-37`).
16. **CONDITIONAL** — MCP should not refetch at confirm. It should use
    approval-bound effective values and allow normal `Customer.insert()` to
    rerun native lifecycle validation; the installed Customer validation may
    itself perform the native lookup in production mode (`document.py:474-487`,
    `party.py:52-58`).
17. **YES** — ERPNext-only sites can remain unchanged with a lazy optional
    adapter and the existing core `address_line1` path (`customer.py:312-323`).
18. **NO** — A new public MCP tool is not required; the existing
    `prepare_customer -> confirm_customer` boundary is sufficient, with the
    smallest explicit contract extension being `gst_category`.

## 27. Exact Next Task

### Task 25 - Customer GST / India Compliance Native Bridge Implementation

After review of this report, implement only the proven bridge boundary:

- Add a lazy optional India Compliance Customer adapter under
  `mcp_erpnext/services/integrations/`.
- Preserve ERPNext-only startup and behavior when India Compliance is absent.
- Add only the explicit `gst_category` contract extension required for the
  effective preview; retain existing `gstin` and reject arbitrary extra fields.
- Reuse native `get_gstin_info` only where a prepare-safe result path is
  available. Do not call the current external/queued implementation during
  prepare merely to imitate Quick Entry.
- Reuse native metadata, normalization, validation, settings gates, and
  current-user permission behavior; do not duplicate GST/GSP/API rules.
- Correctly approval-bind effective Customer and Address values, including the
  installed India Compliance transient address convention when applicable.
- Keep `prepare_customer -> confirm_customer`, process-local approval binding,
  normal permissions, duplicate rechecks, and normal `Customer.insert()`.
- Do not duplicate India Compliance primary Address creation.
- Do not refetch from MCP during confirmation.
- Add regression coverage for India Compliance present/absent, disabled,
  sandbox, archived/native result, invalid/unavailable, permissions, and
  primary Address behavior.
- Run only explicitly authorized tests and report live external/database/
  browser boundaries separately.

No implementation code, contract, test, schema, hook, setting, or database
change was made in this Task 24 inspection.
