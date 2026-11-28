# test564 — Lambda health assertion repair

Date: 2026-11-28  
Execution type: Hosted Nova plan-only generation; no AWS workload apply  
Customer repository: Synthetic pinned test repository associated with the
source architecture plan; repository contents were not retrieved  
Commit: Deployed backend `104d804fe21bad4187a4dc1fc6332cf0923fb633`
(`terraform-nova2-contract-v25`); repository main at observation
`c79a24b5f11f694a6616d5555dd7391dafaed55f`
AWS account: `654654474502`  
AWS region: `us-east-1`

## Hosted baseline

- Type: real DavDeploy hosted, plan-only Nova generation against a synthetic
  same-account test workspace; no Terraform apply or customer workload.
- Backend runtime: PR #563 merge `104d804fe21bad4187a4dc1fc6332cf0923fb633`,
  prompt `terraform-nova2-contract-v25`.
- AWS account/region: `654654474502` / `us-east-1`.
- Workspace: authenticated administrator. Connection setup state: `VERIFIED`;
  plan-role profile state: `PROFILE_VERIFIED`.
- Source architecture plan:
  `539f558d-16cf-4359-921a-9205a7e81bfe`.
- Revision: `726d9ee0-65d2-4b41-9cf3-ad08e36c8c42`; digest
  `fb7384977baea8ff63b83d19be71ff5e0fcd54d45b19466a4f79a9722779cd4e`;
  state `SUBMITTED`, decision absent, execution `UNEXECUTED_APPROVAL_ONLY`.
- Run: `8316ace6-88cd-4213-ad23-b4a249eebdd2`; terminal state `FAILED`, safe
  error `NOVA_GENERATION_FAILED` / `proposal_invalid`; prompt v25, 2 attempts,
  21,435 input tokens, 7,235 output tokens, 27,373 ms; estimated cost
  unavailable.
- Sanitized validator feedback: one `incompatible_health_target` at
  `health_assertions[*].target_resource_id`; assertion kind
  `container_readiness`; observed resource type `aws_lambda_function`. The
  feedback retains the declared Lambda and requires a compatible declared API
  Gateway HTTP path or SQS-to-Lambda event-processing binding. No raw proposal
  or field values were retrieved.
- Result: failed before CodeBuild; no build, saved plan, artifact, AWS workload,
  approval, apply, or destroy was created.
- Existing Terraform monitor: 75 records, zero active runs. Control-plane
  infrastructure was not changed by the hosted generation request.

## Resources created

- No AWS resources were created. DavDeploy recorded the review-only revision
  and plan-run request above; neither has an approval decision.

## Commands executed

- `davdeploy auth login --username bepoadewale1@gmail.com` — succeeded with a
  user-provided current authenticator code; secrets were not recorded.
- Authenticated `GET /api/v1/me` — workspace role `administrator`.
- Authenticated `GET /api/v1/cloud-connections/3964addb-9f00-4c87-b829-2c3cd3b0b48c`
  — connection/plan-role checks passed for the same-account test.
- Authenticated `POST /api/v1/deployment-plans/539f558d-16cf-4359-921a-9205a7e81bfe/customer-review`,
  `POST /api/v1/customer-plan-revisions/726d9ee0-65d2-4b41-9cf3-ad08e36c8c42/submit`,
  and `POST /api/v1/customer-plan-revisions/726d9ee0-65d2-4b41-9cf3-ad08e36c8c42/generated-plan-runs`
  — created and queued one unapproved plan-only request.
- `GET /api/v1/generated-plan-runs/8316ace6-88cd-4213-ad23-b4a249eebdd2`
  — inspected the safe terminal result and allowlisted validation feedback.

## Observed result

- One bounded repair attempt did not fix the Lambda health assertion mismatch.
  Generation failed before CodeBuild, with no provider plan or saved-plan
  artifact. Prompt v25 needs a positive valid shape/example and fresh hosted
  verification. The PR's local tests, CI, deployment, and v26 run remain
  pending.

## Teardown

- No workload resources were created; no teardown was needed. Keep the
  unapproved review/run records as audit evidence.

## Final boundary

This baseline is one hosted generation failure. It does not prove that the
prompt fix succeeds, that a provider plan is valid, or that any workload was
deployed, operated, recovered, destroyed, or certified. No approval, apply,
destroy, or cleanup of retained audit records was performed.
