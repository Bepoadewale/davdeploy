# ticket365 — reject literal credentials in Nova proposal arguments

PR: [#365](https://github.com/Bepoadewale/davdeploy/pull/365) (draft)
Branch: `security/nova-secret-reference-contract`

## Problem / goal

Nova-generated Terraform arguments must not carry literal credentials or secret values. Safe secret integration must use typed, controlled references; the customer plan runner must never receive a model-authored secret value.

## Current repo state

The generated deployment contract rejects a short list of exact argument keys and Terraform expressions. Provider-schema validation rejects literals for provider attributes marked sensitive and validates output sensitivity, but the generic proposal contract does not consistently reject common credential-field variants or enforce typed references for secret-named fields. The customer Nova execution path remains gated.

## Research / references used

- Goal handoff: secret material must be resolved through controlled references and never model text.
- Existing module-port contracts accept secret-reference values and never read secret contents.
- `generated_provider_validation.py` checks provider-declared sensitive arguments and generated output metadata against the pinned provider schema.

## Work planned for the PR

- Harden the proposal contract against common credential and secret literal field names, including nested and case/separator variants.
- Permit secret-valued arguments only when they contain a typed `resource_reference` declared as `secret_reference`, while preserving boolean configuration controls.
- Add regression tests for denied literals, accepted typed references, and ordinary values.
- Preserve existing plan-only and feature-gate boundaries; this PR does not enable a customer secret lookup or Nova apply path.

## Acceptance criteria

- Obvious credential or secret literals fail at contract validation before Terraform configuration is generated; boolean controls such as secret-management toggles remain representable.
- Typed references declared as `secret_reference` remain representable without embedding secret material.
- Existing provider-schema sensitivity checks remain authoritative for other sensitive fields.
- No secret value is added to logs, model feedback, plans shown to customers, or evidence.

## Acceptance status

- Implemented and locally verified, including the full clean-room cycle required for Terraform validation changes. Awaiting final CI and review. Hosted Nova execution remains gated; end-to-end secret lookup is follow-up work.

## Tests / validation performed

- `uv run pytest tests/test_generated_deployment_contract.py -q`: 18 passed.
- `make verify`: 1,004 tests passed; lint, OpenAPI snapshot and Docker Compose configuration checks passed.
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365 make local-proof`: passed, including API contract, customer-plan E2E, traces and the full verification suite.
- `git diff --check` and `python3 scripts/check_doc_conventions.py`: passed.
- Initial hosted CI run `43127441913` passed all seven required jobs on implementation commit `7002969588443df4baa38c637db8544cf643c76a`.
- Codex review identified boolean secret-management controls as a false positive; the validator now permits boolean controls and adds explicit regressions for `manage_master_user_password`, `generate_secret`, and `enable_token_revocation`.
- After that correction, focused contract tests passed (21), `make verify` passed (1,007 tests), and `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365b make local-proof` passed. Both local Compose projects' containers are stopped; their project networks and Postgres volumes remain.
- Follow-up review identified valid policy/configuration objects and token lifetime settings in the existing Cognito Terraform root. Detection now exempts the typed policy/configuration blocks and numeric token validity fields while continuing to check secret-valued nested members; dedicated regressions cover those patterns.
- After the policy/lifetime correction, `make verify` passed (1,011 tests) and `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365c make local-proof` passed. Its containers were stopped; the network and PostgreSQL volume remain.
- Full clean-room cycle passed from detached worktree `/private/tmp/davdeploy-pr365-cleanroom-20261112` at code commit `a3a5d6d0e70e0dcaaf4c6fa85e3296a7d116cf0b`, using Compose project `davdeploy-pr365-cleanroom`, temporary tmpfs Postgres override, and external venv `/private/tmp/davdeploy-pr365-venv`. Required demos, trace check, and `verify` passed; final clean and absence checks removed only this PR's containers/network, `.local`, and external venv. No named volume was created. The worktree and override are retained.

## Evidence files produced

- [`docs/test/test365.md`](../test/test365.md)

## Boundaries

- No credentials are fetched or printed.
- No customer AWS plan/apply or feature-gate change is included.
- This change does not claim end-to-end customer secret provisioning is complete.

## Follow-up work

- Integrate trusted, tenant-scoped secret references and safe runtime resolution in the hosted plan/apply lifecycle. Ensure provider data access never exposes secret values to Nova and approval binds the exact reference and saved plan.
