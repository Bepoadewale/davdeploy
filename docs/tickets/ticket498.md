# ticket498 — bound generated AWS Batch plans

PR: [#498 — feat: bound generated AWS Batch plans](https://github.com/Bepoadewale/davdeploy/pull/498)
Branch: `feat/aws-batch-plan-policy-498`

## Problem / goal

Generated-plan policy has no AWS Batch-specific bounds even though the
repository has direct Batch retry and recovery evidence. Add a source-only
policy for a small, explicit Fargate container-job shape, with capacity,
retry, timeout, image, privilege, and queue-binding checks. Unsupported Batch
shapes must fail closed or require explicit review rather than being treated as
certified.

## Current repo state

- `main` is `b57c1c4811f6a581892a17548fa4728c8ea4a9cc` (PR #497).
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` records direct Batch retry
  and recovery evidence in PR #458, but calls out missing generated-plan
  checks for job roles, retries, capacity, and cost.
- `generated_plan_policy.py` currently applies generic IAM and ownership
  checks but has no Batch resource-family checker.
- PR #486 and draft PR #495 remain open. The Terraform monitor has 66
  records and no active operations. AWS account `654654474502` was verified;
  the unrelated AppConfig test application from PR #495 remains present while
  teardown approval is pending.

## Research / references used

- Repository source: `apps/api/src/davdeploy/generated_plan_policy.py`,
  `tests/test_generated_plan_policy.py`, and
  `infrastructure/terraform/modules/batch-compute/main.tf`.
- Direct Batch lifecycle evidence: `docs/tickets/ticket458.md` and
  `docs/test/test458.md`.
- AWS [Fargate job definitions](https://docs.aws.amazon.com/batch/latest/userguide/fargate-job-definitions.html)
  documents supported Fargate settings and CPU/memory requirements.
- AWS [job definition parameters](https://docs.aws.amazon.com/batch/latest/userguide/job_definition_parameters.html)
  documents retries, resource requirements, and container settings.
- AWS [automated job retries](https://docs.aws.amazon.com/batch/latest/userguide/job_retries.html)
  documents the 1–10 AWS attempt range.
- HashiCorp AWS provider [`aws_batch_job_definition`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/batch_job_definition)
  documents Terraform's plan fields.

## Work planned for the PR

1. Add a policy checker for managed AWS Batch compute environments, queues,
   and job definitions, limited to one same-plan Fargate environment/queue/job
   binding.
2. Bound aggregate compute capacity to six vCPUs, per-job Fargate CPU to at
   most two vCPUs with a valid AWS CPU/memory pair, retries to 1–3 attempts,
   and per-attempt runtime to 60–3,600 seconds.
3. Require a SHA-256 image digest, reject privileged containers and reserved
   or secret-like plaintext environment variables, and require literal
   same-account Batch service, execution, and optional job role ARNs.
4. Keep public-IP assignment visible as a review finding without claiming
   complete network or permission analysis.
5. Add focused regression tests for accepted and rejected plan shapes and
   update the Nova capability evidence matrix.
6. Make no AWS workload, hosted control-plane, or Terraform-state change.

## Acceptance criteria

- [x] A checked plan binds one Batch queue to exactly one planned managed
  Fargate compute environment.
- [x] Compute capacity is at most six vCPUs; one job uses a supported Fargate
  CPU/memory pair with at most two vCPUs, 1–3 attempts, and a 60–3,600 second
  timeout.
- [x] Unsafe, unknown, unpinned, privileged, cross-account or wildcard-role,
  reserved-environment, or unsupported shapes fail closed.
- [x] Public-IP use is surfaced for review rather than hidden.
- [x] Roles outside the plan produce a human-review finding for effective
  trust and permission verification.
- [x] Findings contain no raw customer values or secrets.
- [x] Focused regression tests, documentation conventions, and diff checks
  pass; required final-head CI is tracked separately below.
- [x] The capability matrix distinguishes source policy from direct AWS test
  evidence and does not claim Nova dispatch or customer certification.
- [x] No AWS resources, hosted control-plane state, Terraform state/locks, or
  protected untracked local files are modified.
- [ ] All required final-head GitHub checks pass.

## Acceptance status

Partially met. The source policy and focused regression coverage are in place.
Documentation and local validation pass; final-head GitHub CI remains pending.

## Tests / validation performed

- `PYTHONDONTWRITEBYTECODE=1 /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -p no:cacheprovider tests/test_generated_plan_policy.py -q`: 523 passed.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py`: passed.
- `git diff --check`: passed.
- `GITHUB_PR_NUMBER=498 python3 scripts/check_doc_conventions.py`: passed.
- Required PR CI: pending.

## Evidence files produced

- `docs/tickets/ticket498.md`
- Planned: `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

Source and documentation only. Do not create or delete AWS resources, run a
Terraform plan/apply/destroy, alter the hosted control plane, change remote
state/locks, or modify protected local files in this PR.

## Follow-up work

Complete effective Batch role-policy analysis, full per-plan cost estimates,
non-Fargate Batch shapes, and Nova-dispatched application lifecycle evidence
remain separate work.
