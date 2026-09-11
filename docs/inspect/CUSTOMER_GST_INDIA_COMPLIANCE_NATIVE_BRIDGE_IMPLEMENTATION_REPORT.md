# Customer GST / India Compliance Native Bridge — Implementation Report

## 1. Scope and result

Task 25 was implemented for the existing `prepare_customer` / `confirm_customer`
pair. No new public GST tool, GST/GSP client, Quick Entry implementation, app
source change, schema change, setting mutation, credential change, or approval
semantic change was added.

The bridge now delegates prepare-safe GSTIN/category behavior to installed
India Compliance helpers, carries the effective values into the preview and
approval payload, and selects India Compliance's transient primary-address
carrier from optional capability detection rather than Customer metadata.

Remote GSTIN enrichment remains unavailable during prepare because the native
lookup path is side-effecting. No MCP archive reader or copied API behavior was
added.

## 2. Runtime evidence observed

Target site: `yob.localhost`

The read-only runtime installed-app query returned:

```text
frappe, yob_core, yob_auth, erpnext, payments, india_compliance,
yob_storefront, mcp_erpnext, mcp_identity
```

Observed package versions at implementation time:

| App | Version |
|---|---|
| Frappe | 16.33.1 |
| ERPNext | 16.34.2 |
| India Compliance | 16.9.0 |
| mcp_erpnext | 0.0.1 |

These versions are recorded for traceability only. The implementation does not
branch on a version string.

Effective runtime metadata included:

- Customer `gstin`: `Autocomplete`, optional, editable.
- Customer `gst_category`: `Select`, required, default `Unregistered`, with
  the installed native category options.
- Address `gstin`: `Data`, optional, editable.
- Address `gst_category`: `Select`, required, default `Unregistered`.
- Address `gst_state` and `gst_state_number`: read-only.
- No `_address_line1` DocField exists on Customer or Address.

The live adapter capability query returned:

```json
{"installed": true, "native_gst_prepare": true,
 "transient_primary_address": true, "prepare_safe_enrichment": false}
```

## 3. Files inspected before change

- `mcp_erpnext/config/masters/customer.py`
- `mcp_erpnext/services/masters/customer.py`
- `mcp_erpnext/tools/masters/customer.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/services/common/creation_contract.py`
- `mcp_erpnext/services/common/field_value_resolver.py`
- `mcp_erpnext/services/integrations/india_compliance_item.py`
- `mcp_erpnext/approvals.py`
- `mcp_erpnext/contracts/interaction.py`
- `mcp_erpnext/tests/test_customer_service.py`
- `apps/erpnext/erpnext/selling/doctype/customer/customer.py`
- `apps/india_compliance/india_compliance/hooks.py`
- `apps/india_compliance/india_compliance/gst_india/overrides/party.py`
- `apps/india_compliance/india_compliance/gst_india/overrides/address.py`
- `apps/india_compliance/india_compliance/gst_india/utils/__init__.py`
- `apps/india_compliance/india_compliance/gst_india/utils/gstin_info.py`
- `apps/india_compliance/india_compliance/public/js/quick_entry.js`
- `apps/india_compliance/india_compliance/gst_india/api_classes/public.py`
- `apps/india_compliance/india_compliance/gst_india/doctype/gst_settings/gst_settings.json`

The existing Item integration was used as the structural pattern for an
optional, narrowly scoped integration module. No generic provider framework was
introduced.

## 4. Native functions reused and safety boundary

The adapter lazily imports these installed functions from
`india_compliance.gst_india.utils`:

- `validate_gstin`: prepare-safe native normalization and format/check-digit
  validation.
- `guess_gst_category`: prepare-safe native category derivation without the
  side-effecting party setter.
- `validate_gst_category`: prepare-safe native category/GSTIN compatibility
  validation.

The final confirmation still relies on the normal native Customer lifecycle,
including `india_compliance.gst_india.overrides.party.validate_party` and
`create_primary_address`, through normal `Customer.insert()`.

The adapter deliberately does not call:

- `india_compliance.gst_india.utils.gstin_info.get_gstin_info`;
- its internal `_get_gstin_info` path;
- `PublicAPI.get_gstin_info`;
- copied archive/API/response mapping logic.

The inspected lookup first checks archived `Integration Request` data, but can
fall through to the Public API and enqueue GSTIN status / Integration Request
persistence. It is therefore not a prepare-safe enrichment seam. The report and
code explicitly leave this enrichment unavailable during prepare.

## 5. Before and after flow

### Customer prepare

Before:

1. Resolve the narrow Customer contract and link fields.
2. Validate an unsaved Address.
3. Select `_address_line1` by testing Customer metadata, even though it is a
   transient native property rather than a DocField.
4. Run Customer validation and discard the mutated document.
5. Approve the original pre-validation dictionary and build the preview from it.

After:

1. Resolve the existing narrow contract plus explicit `gst_category` when
   effective Customer metadata exposes it.
2. Discover installed optional capabilities through runtime installed-app state
   and lazy source-compatible imports.
3. On India Compliance sites, use only native pure GST helpers during prepare;
   full Customer/Address hooks remain confirmation-time behavior.
4. On ERPNext-only sites, retain the existing unsaved Address/Customer
   validation path and project supported effective values back into the payload.
5. Select `_address_line1` only when the installed native after-insert helper
   confirms that transient convention; otherwise use the ERPNext core carrier.
6. Build the preview and approval token from the same effective payload.

### Primary Address

Before, the transient carrier was inferred from `Customer` metadata. After the
change, India Compliance capability/source knowledge selects `_address_line1`.
The payload does not also contain `address_line1` in that path, so the native
India Compliance after-insert hook owns creation of exactly one primary Address.
ERPNext-only preparation continues to carry `address_line1` and uses the core
lifecycle path.

## 6. Public contract delta

The existing Customer creation pair and frozen legacy registry entries remain.
`gst_category` was added as the only deliberate Customer GST contract field.
It is resolved through runtime metadata and the existing field-value resolver;
unknown fields and `extra_fields` remain unsupported. Existing callers that omit
`gst_category` continue to use native defaults.

The preview now includes effective `gst_category` alongside `gstin`.

## 7. Exact files changed

- `mcp_erpnext/config/masters/customer.py`
- `mcp_erpnext/services/masters/customer.py`
- `mcp_erpnext/services/integrations/india_compliance_customer.py`
- `mcp_erpnext/tests/test_customer_service.py`
- `docs/TOOLS.md`
- This implementation report.

No Frappe, ERPNext, India Compliance, database, settings, schema, credentials,
transport, identity, approval, or unrelated capability files were changed.

## 8. Tests and verification

Passed:

```text
../../env/bin/python -m unittest mcp_erpnext.tests.test_customer_service
Ran 20 tests ... OK

../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
Ran 209 tests ... OK

../../env/bin/python -m compileall -q \
  mcp_erpnext/services/masters/customer.py \
  mcp_erpnext/services/integrations/india_compliance_customer.py \
  mcp_erpnext/tests/test_customer_service.py
```

The focused tests cover ERPNext-only address-carrier regression, explicit GST
category/effective preview and approval projection, transient-address behavior,
and the fact that India Compliance prepare does not invoke Customer validation.
The broader suite covers the existing approval, permission, contract, and
integration regressions.

Static lint could not be run because `ruff` is not installed in the bench
environment (`../../env/bin/ruff: No such file or directory`).

## 9. Mocked versus live-verified boundaries

Unit tests mock Frappe documents, metadata, runtime capabilities, and native
helper callables. They prove delegation and payload selection, not live native
database behavior.

Live read-only verification covered installed apps, package versions, effective
Customer/Address metadata, and adapter capability discovery on `yob.localhost`.
No live `prepare_customer` or `confirm_customer` business record was run for
this implementation verification. Browser Quick Entry behavior was source
inspected only. No external GST/GSP request, API credit consumption, queue
operation, Integration Request insert, Customer insert, Address insert, or
setting mutation was performed.

## 10. Remaining limitations and next task

The MCP prepare path does not reproduce Quick Entry's remote GSTIN party-name
or address autofill. This is intentional because the only installed lookup path
observed is not safe inside the prepare/approval boundary. Native confirmation
validation and after-insert behavior remain authoritative.

The next task should be a focused runtime verification of Customer creation on
the India Compliance site with current local/sandbox settings and, if safely
available, an ERPNext-only site. A separate remote-enrichment task should be
created only if a genuine native prepare-safe seam is later identified without
duplicating India Compliance internals or violating prepare safety.
