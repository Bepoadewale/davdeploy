# ticket422 — verify the Nova plan-role policy profile at use time

PR: https://github.com/Bepoadewale/davdeploy/pull/422
Branch: `feat/nova-plan-role-profile-attestation-422`

## Problem / goal

The current hosted connection check proves that the control-plane broker can
assume the customer plan role and that the role belongs to the expected AWS
account. It does not check whether that role still has the reviewed bounded
Nova plan policy. A changed or over-broad role could therefore pass the
identity check. Add a fail-closed check of the current role trust and policy
profile when verifying a connection and immediately before issuing plan
credentials.

The check must be described as profile verification, not full effective AWS
permission attestation. AWS Organizations service control policies,
resource-based policies, and later changes outside the check remain separate
limits.

## Current repo state

- Backend `main` is `b0b46d6a08e973d7eec38ae9c51c05111b86b8d9` (PR #421,
  documentation reconciliation).
- Draft PR #399 contains default-off exact-plan apply credential/input routes,
  artifact staging, worker, and reconciliation. It remains unmerged and its
  gates remain disabled.
- `StsAwsDiscovery.verify_plan_role` checked only STS assumption and account
  identity. The customer role template already grants IAM metadata reads and
  explicitly denies actions outside its bounded plan profile.
- No customer plan role has been persistently installed or verified; this PR
  uses mocked AWS clients only and performs no AWS mutation.

## Research / references used

- `apps/api/src/davdeploy/integrations.py` — current plan-role identity check.
- `apps/api/src/davdeploy/nova_plan_access.py` — fixed proposal-scoped session
  policy and role read-action profile.
- `infrastructure/cloudformation/customer-discovery-role.yaml` — published
  `NovaPlanOnlyRole` trust and bounded inline policy.
- `docs/customer-aws-connection.md` — customer-facing role setup and status
  explanation.
- `apps/api/src/davdeploy/main.py` — plan credential issuance boundary.
- `docs/test/test392.md` — prior disposable IAM simulation, explicitly not
  hosted customer-role or effective-permission evidence.

## Work planned for the PR

- Define one versioned role-profile verifier that checks exact role identity,
  external-ID trust, required ownership tags, no permissions boundary, no
  attached managed policies, the single expected inline policy, and its exact
  bounded allow/deny shape.
- Assume the role for profile inspection with a separate short-lived session
  policy limited to IAM reads on that exact role and STS identity; never return
  those inspection credentials.
- Run the profile check during connection verification and again before each
  hosted plan credential response so policy drift fails closed.
- Audit only the profile version and SHA-256 digest; never store or log
  credentials, external IDs, or full policy documents.
- Keep apply and plan feature gates unchanged and preserve the distinction
  between profile verification and full effective-permission evidence.

## Acceptance criteria

- [x] Expected template policy and trust shape pass deterministic unit tests.
- [x] Unexpected trust principals, external IDs, role tags, boundaries,
  attached policies, inline policies, or policy statements fail closed.
- [x] Profile inspection uses a role- and action-scoped session policy and
  never returns inspection credentials.
- [x] The hosted plan credential path rechecks the current profile before
  issuing proposal-scoped credentials.
- [x] Audit and customer-facing status describe profile verification without
  claiming full effective permissions or plan-runner readiness.
- [x] Focused tests and required repository checks pass.
- [ ] The full local clean-room cycle is required before this authorization
  change is review-ready.
- [x] No AWS mutation, Terraform operation, feature-gate change, customer
  credential issuance, or customer workload is performed.

## Acceptance status

Implementation and focused/full repository checks are complete. The required
local clean-room cycle has not run, so this PR remains draft. No hosted
customer-role or workload evidence is claimed.

## Tests / validation performed

Commands and results:

- `.venv/bin/python -m pytest -q tests/test_nova_plan_role_profile.py tests/test_customer_cloud_lifecycle.py tests/test_product.py tests/test_connection_experience.py tests/test_nova_plan_credentials.py tests/test_nova_plan_runs.py` — 151 passed.
- `make verify PY=.venv/bin/python` — 1,280 passed; Ruff, Actions configuration, OpenAPI, and Compose configuration checks passed.
- `python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.

The local clean-room cycle remains incomplete. Its final cleanup would remove
generated local files and Docker resources; deletion permission for those
exact targets has not been granted in this conversation. No AWS API mutation,
Terraform operation, control-plane deployment, or customer credential
issuance occurred.

## Evidence files produced

No `docs/test/test422.md` is planned; this PR uses mocked AWS APIs and performs
no customer workload test. This ticket is the source-change record.

## Boundaries

- Do not deploy the control plane or modify feature gates.
- Do not create, update, or delete AWS resources.
- Do not issue customer credentials or run Terraform.
- Preserve the untracked `--only-show-errors` file and `.venv-pr399/`.
- Do not claim complete effective AWS permission attestation.

## Follow-up work

After profile verification merges and is deployed through the protected
control-plane workflow, establish a real customer connection and hosted
plan-only run. Apply-role provisioning and customer workload lifecycle proof
remain separate, explicitly gated acceptance work.
