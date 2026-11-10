# ticket332 — bind the Nova plan worker to isolated remote Terraform state

PR: [#332](https://github.com/Bepoadewale/davdeploy/pull/332), draft stacked on [#331](https://github.com/Bepoadewale/davdeploy/pull/331)
Branch: `feat/nova-remote-state-runner-332`
Base: `feat/tenant-isolated-terraform-state-331`

## Problem / goal

Teach the fixed Nova plan-only CodeBuild worker to obtain a short-lived
credential for its exact durable request and attempt, initialize Terraform's
HTTP backend from the trusted response, and preserve the existing saved-plan,
policy, and artifact path. The customer plan-only role remains the only role
used by Terraform for AWS provider reads. CodeBuild's service role signs only
the state-credential bootstrap request.

## Current repo state

- PR #331 implements the state service and optional storage, but the runner
  still runs `terraform init -backend=false` and `terraform plan -lock=false`.
- The API bootstrap route is disabled by default and checks both the durable
  row ID and active attempt/build binding.
- Pricing is unavailable. Plans must remain unapprovable, and there is no
  apply or destroy path in this change.

## Research / references used

- [Terraform HTTP backend](https://developer.hashicorp.com/terraform/language/backend/http)
- [Terraform state locking](https://developer.hashicorp.com/terraform/language/state/locking)
- [API Gateway HTTP API IAM authorization](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html)
- [Botocore SigV4 signing](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/auth.html)

## Work planned for the PR

- Carry the validated durable control-plane request ID through the immutable
  staged input; do not confuse it with the per-attempt CodeBuild run ID.
- Add bounded SigV4 bootstrap using CodeBuild service-role credentials and
  validate the response contract, HTTPS endpoints, and credential lifetime.
- Inject only trusted HTTP-backend addresses and lock methods into generated
  Terraform configuration. Pass short-lived Basic credentials through the
  Terraform process environment, never configuration, logs, or artifacts.
- Retain backend-free behavior only for explicitly disabled test/local use;
  if hosted state is enabled but bootstrap/configuration fails, fail closed.
- Test signing, durable/attempt identity binding, malformed and mismatched
  bootstrap responses, Terraform backend configuration, secret redaction, and
  preservation of policy/saved-plan result binding.
- Keep Terraform state, plan runner, and apply gates disabled by default.

## Acceptance status

The client, runner wiring, result contract, manifest binding, and feature-flag
plumbing are implemented in this draft. Full local verification and Terraform
validation pass. The worker rejects a bootstrap response whose scope digest
does not match the trusted immutable request, and SigV4 uses the control-plane
API Gateway region rather than the customer's deployment region. All seven
GitHub CI checks passed for `0e0f24e` in run `42856971505` and the tenant-scope
guard `bbf7e42` in run `42859321640`, and for the API-region signing change
`6746541` in run `42860462692`. The state feature remains disabled, and no AWS
deployment or hosted state request occurred. Hosted state behavior remains
unverified. The final run included the full fresh-runner local-e2e/clean-room
sequence. Independent static security review found no blocking findings. The
default-off and no-deployment boundary is met.

## Tests / validation performed

- Focused suites: 27 state-client and state-worker tests passed; 19 worker
  tests include tenant-scope mismatch coverage.
- `make verify`: 849 passed; Ruff, OpenAPI, Actions configuration, and Compose
  configuration passed.
- `make terraform-validate`: all configured roots passed.
- Documentation convention and diff checks passed.
- GitHub Actions run `42859321640`: all seven required checks passed for the
  tenant-scope guard `bbf7e42`.
- GitHub Actions run `42860462692`: all seven required checks passed for
  implementation commit `6746541`; its fresh-runner `local-e2e` job ran the
  clean-room lifecycle sequence. See `docs/test/test332.md`.
- Runtime and Terraform evidence: `docs/test/test332.md`.

## Evidence files produced

- `docs/test/test332.md` records local validation and the unverified hosted
  boundary.

## Acceptance criteria

- [ ] Bootstrap uses the CodeBuild service-role identity and the exact active
      durable request, project, attempt, and build ARN.
- [ ] Terraform receives server-issued HTTP backend addresses and short-lived
      credentials only through process environment; backend configuration has
      no caller-selected URL or credentials.
- [ ] Hosted enabled-state planning uses remote state locking; disabled mode
      cannot silently masquerade as a hosted stateful plan.
- [ ] Secrets and state values do not enter logs, result envelopes, or saved
      plan manifests.
- [x] Negative tests cover identity mismatch, invalid response, expired
      credentials, tenant scope mismatch, and signing/transport failure.
- [x] `make verify`, Terraform validation, docs checks, required CI, independent
      static review, and the fresh-runner clean-room lifecycle gate pass.
- [x] No feature flag is enabled, no AWS infrastructure is deployed, and no
      apply/destroy or customer workload is executed.

## Boundaries

This PR cannot make a plan approvable. It does not add pricing, approval,
apply, health, recovery, or teardown. The state feature remains disabled until
the service, runner, pricing, exact-plan approval, and hosted security gates
are reviewed and verified together.

## Follow-up work

After the state service and runner pass review, integrate complete regional
pricing and exact costed-plan approval before considering apply or lifecycle
operations. The current remote-state boundary deliberately remains
unapprovable.
