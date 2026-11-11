# ticket340 — constrain customer Nova planning permissions

PR: [#340](https://github.com/Bepoadewale/davdeploy/pull/340) (merged)
Branch: `feat/nova-readonly-plan-scope-340`

## Problem / goal

Make the customer plan-only role and the Nova worker’s temporary credentials
read-only for the supported first workload slice: API Gateway v2, Lambda and
SQS processing, private S3 bucket metadata, DynamoDB, and the IAM roles/policies
declared in that proposal. Reject unsupported resource types or unscopable
names before assuming the customer role. Bind the exact generated session
policy to the saved plan manifest so the later approval can verify it.

## Current repo state

- Backend `main` includes merge commit
  `8d3b4764bcefae8cb9f93a930b064e10fd893762` for PR #340. Implementation was
  `d46fe7fd60b6ba5bfa31cb319318d6417d2c6b1b`; final evidence commit was
  `35a639143077c75ffbb820aaa4c867eb283e6ce2`.
- The plan-only CloudFormation template previously denied all customer
  service actions. The Nova worker already verifies the connection ExternalId
  and target account before it invokes the fixed Terraform planner.
- State storage is deployed, while the hosted plan runner, state API, role
  verification, and plan review remain disabled. Existing customer roles are
  not updated by this PR.
- Regional pricing remains unavailable. PR #318 remains closed and held for
  account-owner direction. No customer apply is enabled.

## Research / references used

- [AWS IAM policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_policy-eval-denyallow.html): direct grants to a role session can bypass implicit session-policy denies, while explicit denies still apply.
- [AWS `aws:ResourceAccount` guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/resource_examples_iam_policies_resource_account.html): use the resource-owning account to prevent cross-account resource access; missing or unsupported context must fail closed.
- [AWS Lambda service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_lambda.html): resource ARN formats and action resource support for Lambda.
- Pinned HashiCorp AWS provider `5.100.0` read implementations: [S3](https://github.com/hashicorp/terraform-provider-aws/tree/v5.100.0/internal/service/s3), [DynamoDB](https://github.com/hashicorp/terraform-provider-aws/tree/v5.100.0/internal/service/dynamodb), [SQS](https://github.com/hashicorp/terraform-provider-aws/tree/v5.100.0/internal/service/sqs), [Lambda](https://github.com/hashicorp/terraform-provider-aws/tree/v5.100.0/internal/service/lambda), and [API Gateway v2](https://github.com/hashicorp/terraform-provider-aws/tree/v5.100.0/internal/service/apigatewayv2).

## Work planned for the PR

- Added a versioned plan-access builder that allows only the declared supported
  Terraform resource types and rejects unsupported types, invalid regions,
  dynamic/prefix names, bad references, and unsafe IAM paths before STS.
- The fixed worker sends a server-built STS session policy with scoped resource
  ARNs, explicit action denies, explicit resource-scope denies, and an S3
  resource-account deny. IAM resource-policy grants to a session cannot escape
  the declared resource set. S3 bucket ARNs omit the account, so the separate
  `aws:ResourceAccount` deny is required.
- The CloudFormation customer plan role grants only fixed metadata-read action
  patterns, denies actions outside those patterns, and denies cross-account S3
  access. The patterns are bounded by resource ARNs in the worker session.
- Exact provider-read action lists are retained as a regression map for the
  pinned provider. No S3 object-body, DynamoDB item, SQS message, secret value,
  workload invocation, or mutating action is permitted.
- The immutable plan manifest now records the access-policy version and SHA-256;
  the API recomputes it from the trusted staged proposal before it accepts the
  worker result.
- The composed API/storage/database/async profile is checked against the
  2,048-character STS inline session-policy limit.

## Acceptance criteria

- [x] Supported resource families and provider-read actions are versioned and
  bounded; unsupported resource types fail before customer-role assumption.
- [x] No object body, table item, queue message, secret value, invocation, or
  write action is granted by the read profile.
- [x] Session policy uses proposal-derived resource ARNs and explicit denies
  against direct resource-policy grants outside that scope.
- [x] S3 bucket access is denied when `aws:ResourceAccount` differs from the
  trusted customer account.
- [x] The access-policy version and digest are bound into the result manifest
  and recomputed by the API before accepting worker output.
- [x] Hosted execution gates remain disabled; existing customer roles are not
  silently changed; no customer roles or customer workloads are changed by
  this implementation.
- [x] Focused tests, full `make verify` (877 tests), and isolated clean-room
  proof pass at `d46fe7fd60b6ba5bfa31cb319318d6417d2c6b1b`.
- [x] Evidence docs checks and required final-head CI pass (run `42971989437`).
- [x] The production control-plane package was deployed separately; see
  [test341](../test/test341.md). Customer planning and lifecycle gates remain
  disabled.

## Acceptance status

Implementation and local verification are complete; PR #340 merged as
`8d3b4764bcefae8cb9f93a930b064e10fd893762` after all seven required checks
passed for final PR head `35a639143077c75ffbb820aaa4c867eb283e6ce2` in run
`42971989437`. Post-merge CI run `42972528572` also passed. Its protected
production control-plane release is recorded in `docs/test/test341.md`; all
hosted customer planning and lifecycle gates remain disabled.

## Tests / validation performed

See `docs/test/test340.md`; it will be updated with exact final commands,
results, commit, and CI evidence. Production release evidence is in
`docs/test/test341.md`.

## Evidence files produced

- `docs/test/test340.md`

## Boundaries

This PR changes source and the customer setup template only. It does not update
an existing customer role, enable hosted plan execution, verify customer IAM
policy installation, integrate pricing, approve a customer plan, apply or
destroy customer resources, or claim the hosted workflow is ready. API Gateway
reads are limited to the regional `/apis/*` path; Lambda event-source-mapping
reads use that account and region’s mapping ARN pattern because AWS does not
provide a known ID for a newly proposed mapping. These metadata scopes are
broader than a single new resource and remain an explicit limitation.

## Follow-up work

After this boundary is independently reviewed, finish pricing evidence and
customer role setup verification, then prove the disabled hosted plan request
path against a disposable account. Keep runner, state API, and plan-review gates
off until those separate gates pass. PR #318 remains held for owner direction.
