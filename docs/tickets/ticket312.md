# ticket312 Enforce policy on generated Terraform plans

PR: #312
Branch: feat/nova-terraform-plan-policy

## Problem / goal

Terraform schema validation confirms that a configuration is structurally accepted. DavDeploy must also inspect the actual planned resource values and fail closed on unsafe public access, privilege escalation, unencrypted databases, unbounded ingress, account/region mismatch, or unexplained resources before presenting the plan for approval.

## Current repo state

PR #307 provides a typed proposal; #308 generates it with trusted context binding; #309 validates its AWS schema; #310 summarizes Terraform plan effects without values; #311 creates a pinned, account-checked, backend-free saved plan. The policy layer does not yet inspect the actual plan values. The hosted executor remains disabled for this generic path.

## Research / references used

- Terraform plan JSON: https://developer.hashicorp.com/terraform/internals/json-format
- S3 Block Public Access: https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html
- AWS IAM least privilege: https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html
- AWS Trusted Advisor unrestricted security group ports: https://docs.aws.amazon.com/awssupport/latest/user/security-checks.html
- RDS storage encryption: https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/rds.html
- RDS public exposure guidance: https://docs.aws.amazon.com/prescriptive-guidance/latest/security-controls-by-caf-capability/data-controls.html

## Work planned for the PR

Build deterministic plan findings for account/region, proposal-to-plan resource ownership, public S3 access, public ingress, dangerous IAM permissions/trust, RDS exposure/encryption, critical unknowns, destructive changes and sensitive changes. Use typed findings with stable codes and plain-English explanations; never return or log plan values. `REVIEW_REQUIRED` must mean an authenticated human decision is required; no policy outcome in this component authorizes apply. Integrate the policy result into the Nova plan result and test real plan evidence.

## Acceptance criteria

- [x] Plan region and resource inventory are reconciled with trusted proposal context.
- [x] Public S3 access, critical open ports, wildcard IAM administration/pass-role, public/unsecured databases, unbounded ingress, and critical unknown values fail closed.
- [x] Destructive replacements and sensitive changes are surfaced for explicit human review; deletes outside the proposal are denied.
- [x] Findings contain no raw plan values, secrets, or Terraform JSON.
- [x] Policy errors and unsupported structures fail closed with stable plain-English messages.
- [x] A secure composed S3 plan is eligible for human review; an unsafe plan is denied.
- [x] Focused tests, `make verify`, documentation conventions, and clean-room checks pass.
- [ ] Required CI and PR review pass.
- [ ] Review is complete.

## Acceptance status

Implementation and local verification are complete. The generic plan runner
now returns a deterministic policy verdict alongside secret-safe plan summary
and digests. The live AWS check uses plan-only Terraform with no apply or
resource creation. CI and review remain pending.

## Tests / validation performed

Focused policy, plan-inspection, and Terraform-runner tests pass (62 tests).
`make verify` passes: 590 tests, Ruff, Actions configuration, OpenAPI snapshot,
and Compose configuration. Documentation conventions and `git diff --check`
pass. The isolated clean-room cycle also passes; hosted CI and PR review remain
pending.

A real authenticated read-only plan in account `654654474502`, region
`us-east-1`, Terraform `1.14.7`, and AWS provider `5.100.0` proposed three
creates (synthetic S3 bucket, four-setting S3 public access block, and trusted
account guard), with no updates/deletes/replacements. Policy result:
`ELIGIBLE_FOR_HUMAN_REVIEW`, version
`nova-generated-plan-2026-11-04.2`, no findings. A preceding run surfaced
`s3_public_access_block_missing` because Terraform's computed bucket ID is
unknown during planning; the evaluator was corrected to follow Terraform's
configuration reference metadata and then the same safe proposal passed.
Independent review also led to policy checks for the exact trusted account
guard, nested module resources, malformed IAM policy structure, and invalid
CIDR values. Direct public S3 bucket policies are denied. Neither plan applied
changes or created AWS resources.

## Evidence files produced

`docs/test/test312.md` records redacted evidence. Saved plans are retained in
private local workspaces for reproducibility; no raw JSON plan is checked in.

## Boundaries

These rules cover a versioned initial security baseline, not every AWS security control or every service-specific requirement. A policy pass is only eligibility for human review; it is not approval, cost validation, deploy authorization, or proof of application behavior. Plan application remains separate and disabled.

## Follow-up work

Extend policy coverage across the full finite capability matrix, add time-stamped cost/quota/permission checks, bind findings and policy version into an immutable saved-plan approval, encrypt and durably store plan artifacts, and connect the policy-gated path to the hosted worker.
