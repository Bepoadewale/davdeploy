# ticket559 — expose safe secret-reference repair context

PR: [#559](https://github.com/Bepoadewale/davdeploy/pull/559) (draft)

Branch: `fix/nova-secret-reference-feedback-559`

## Problem / goal

The fresh hosted v20 plan-only run failed during proposal validation with the
safe issue `invalid_secret_reference_location`. The final run record identifies
the fixed rule but not the destination resource type or location category, so
we cannot tell whether Nova put the secret reference on a non-Lambda resource,
in a non-environment field, or under an environment variable with the wrong
name. No Terraform artifact or customer workload was created.

## Current repo state

- Main: `28f229416d7897ec2fe48b3def83ade6b9d4bcaf` (merged PR #558); this
  package is draft PR #559.
- PR #558 is deployed through protected plan `46063294020` and saved-plan
  apply `46064179578`; release and hosted diagnostic evidence is in
  `docs/test/test559.md`.
- The authenticated workspace administrator and verified same-account
  plan-only connection remain available. The fresh revision has no decision.
- No Terraform operation is active. The v20 run failed before an artifact or
  CodeBuild plan step; do not retry it. This package will use one new review
  revision and one new idempotent plan-only run after deployment.

## Research / references used

- `GeneratedDeploymentProposal.validate_graph` validates typed secret-reference
  destinations before Terraform JSON is generated.
- `NovaTerraformGenerator` maps known contract failures to fixed repair
  guidance and stores bounded generation diagnostics.
- Hosted run status and artifact routes expose safe summaries; no raw proposal,
  saved plan, or state was retrieved for this diagnosis.

## Work planned for the PR

1. Carry only the validated AWS resource type and a fixed, allowlisted
   secret-reference location category through contract validation.
2. Preserve those safe fields in bounded repair feedback and final diagnostics;
   keep all resource IDs, argument values, secret data, rationale, and raw
   proposal content out of model context and API evidence.
3. Direct Nova to use an RDS-managed secret ARN output only in a declared
   Lambda environment variable ending `_SECRET_ARN`, and keep the original
   architecture and application requirements fixed.
4. Bump the prompt version and test accepted and rejected locations, redaction,
   and bounded repair.
5. Deploy through the reviewed control-plane saved-plan path, then run one
   fresh review-only hosted plan. No customer approval, apply, or destroy.

## Acceptance criteria

- [x] Valid RDS managed-secret output references in Lambda `_SECRET_ARN`
  environment variables remain accepted; invalid destinations fail closed.
- [x] Repair and persisted diagnostics expose only the validated AWS resource type,
  location category, canonical field, issue, and fixed guidance.
- [x] Resource IDs, argument names/values, secret values, rationale, and raw
  proposal text never enter feedback or API output.
- [x] Bounded repair and negative redaction tests pass; full verification and
  docs checks pass.
- [x] Clean-room proof passes on commit `ce287522`.
- [ ] Review and all required PR CI pass.
- [ ] After protected deployment, a fresh review-only hosted run reaches an
  inspectable saved plan or a precise next blocker. No customer approval/apply.

## Evidence and boundary

The v20 baseline run is documented in `docs/test/test559.md`. No Nova customer
workload has been applied, operated, or certified. Preserve the existing plan
approval, apply, and destroy boundaries, and keep credentials and raw plan or
state material out of logs.

## Acceptance status

Implementation, bounded-repair tests, full local verification, docs checks,
and clean-room proof complete. Review and CI remain pending.

## Tests / validation performed

`make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify` passed with
2,088 tests, Ruff, OpenAPI snapshot, and Compose validation. The focused
secret-reference tests also passed for both rejected locations and the
bounded Lambda environment-name repair. Docs conventions and
`git diff --check` passed. Clean-room `make local-proof` passed on commit
`ce287522`; it ran the API smoke/contract, customer-plan E2E, trace check,
2,088 tests, OpenAPI snapshot, and Compose validation. `make clean-local`
completed and the named containers, network, volumes, external venv, and
`.local` data were absent. Review and final PR CI remain pending.
The hosted v20 baseline is recorded in `docs/test/test559.md`.

## Evidence files produced

- `docs/tickets/ticket559.md`
- `docs/test/test559.md`

## Boundaries

No customer approval, apply, or destroy. Preserve secret redaction and all
existing tenant and AWS execution gates.

## Follow-up work

After protected deployment, submit one fresh review-only revision and queue one
plan-only run. Inspect only bounded diagnostics and value-free artifact evidence.
