# test547 — Hosted Nova resource-name validation and v12 follow-up

Date: 2026-11-27
Execution type: Hosted plan-only generation failure before CodeBuild
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance project)
Commit: deployed control-plane `a0b06dc2debde3bc17caeb42699476556e9bb825`
AWS account: `654654474502` (verified control-plane account; no workload apply)
AWS region: `us-east-1`

## Resources created

No Nova customer workload resources were created. The protected control-plane
release updated existing control-plane resources only.

## Commands executed

- Verified protected plan `45973303637` and apply `45974135992` against the
  exact merge commit.
- Retrieved only allowlisted run status and generation diagnostics for
  `7ed97bc9-4460-40bb-9ca7-7bf8a84b38b2`.

## Observed result

The deployed v11 prompt passed the previous credential-value issue. The fresh
hosted run then failed as `proposal_invalid` after 2 attempts and 1 semantic
repair in 15,860 ms, using 12,404 input and 4,057 output tokens; estimated cost
was unavailable. The only safe feedback was
`resources[*].name` / `string_pattern_mismatch`. It failed before CodeBuild; no
saved plan or workload was created. The run has not been explicitly retried
and is eligible for one retry after v12 deployment.

## Source regression verification

The v12 source change states that Terraform `name` uses lowercase letters,
digits, and underscores, while `resource_id` may use hyphens. It gives paired
examples and returns fixed, sanitized guidance for a
`resources[*].name` pattern mismatch. Validation remains strict.

- Focused generation/run/review suites: 106 passed.
- Full `make verify`: 2,030 tests passed; lint, config check, OpenAPI snapshot,
  and Docker Compose validation passed.
- `git diff --check` passed.
- These are local source checks only. PR CI, protected deployment, and the
  single v12 hosted retry have not yet run.

## Teardown

No workload or plan resources were created; no teardown was needed. Run
metadata remains as audit evidence.

## Final boundary

This establishes a bounded hosted generation failure only. It does not
establish a valid plan, approval, apply, application behavior, lifecycle,
recovery, or certification. The synthetic workload remains unapproved and
unapplied.
