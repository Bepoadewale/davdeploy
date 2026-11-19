# test440 — Nova goal handoff refresh

- Date: 2026-11-19
- Execution type: Documentation review plus isolated same-account customer IAM
  role and session-policy validation; no hosted control-plane execution
- Repository: `Bepoadewale/davdeploy`
- Customer repository: N/A; temporary customer-side test resources only
- Commit: `ff6ffae9ab88a37facbc443dfb35efe8c11b598d` (reviewed source base)
- Pull request: [#440](https://github.com/Bepoadewale/davdeploy/pull/440)
- AWS account: `654654474502`
- AWS region: `us-east-1`

## Resources created

Temporary test resources:

- CloudFormation stack `davdeploy-nova-apply-smoke-b9e85dc2`
- Customer role `davdeployNovaApply-smoke-20261119-b9e85dc2`
- Temporary broker role `davdeployNovaBrokerSmoke-b9e85dc2`
- S3 bucket `davdeploy-nova-apply-smoke-654654474502-b9e85dc2`

All were removed; the stack reached `DELETE_COMPLETE`, and independent reads
confirmed both roles and the bucket are absent.

## Commands executed

- `gh pr list --state open --json number,title,isDraft,headRefName`
- `gh pr view 399` and `gh pr checks 399` — merged state and seven passing
  checks in run `44598735006`
- `gh pr view 438` and `gh pr view 439` — merged status and merge commits
- `python3 scripts/terraform_run_monitor.py status` — no active Terraform run
- `aws sts get-caller-identity --profile ai-platform-pilot-key` — confirmed
  account `654654474502` before customer-side mutations
- Created a temporary broker role and deployed
  `infrastructure/cloudformation/customer-nova-apply-role.yaml` with a random
  ExternalId; assumed the broker role and attempted the customer role with
  both correct and incorrect ExternalIds
- Assumed the customer role with an exact S3 session policy, created and
  deleted its fresh bucket, and attempted unrelated EC2 `DescribeInstances`
- `aws cloudtrail lookup-events` confirmed `Client.UnauthorizedOperation` and
  an explicit identity-policy denial for that EC2 action at
  `2026-11-19T19:57:25Z`
- Deleted the stack and broker role; independently checked both roles and
  bucket absent
- `GITHUB_PR_NUMBER=440 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Matrix count validation — 26 architecture entries and 30 Terraform roots.

## Observed result

The handoff and matrix are updated to current main `ff6ffae`, reflect merged
PRs #399 and #438, preserve the accepted isolated ECS customer-side lifecycle
evidence, and keep hosted-control-plane and Nova-specific status distinct. The
matrix retains all 26 architecture entries and 30 Terraform roots. The role
template passed the bounded same-account trust/session-policy checks described
above; it did not use Nova dispatch or modify the hosted control plane.

Two preliminary attempts were also cleaned up: the first harness stopped before
its explicit denial assertion because of shell fail-fast handling; the next
CloudFormation attempt rolled back when IAM had not yet propagated the newly
created broker principal. The final run waited for propagation and passed all
assertions. No temporary role, stack-managed role, or S3 bucket remains.

## Teardown

Deleted the temporary customer role stack and broker role, deleted the test
bucket, waited for stack deletion, and independently confirmed the roles and
bucket were absent.

## Final boundary

The ECS test remains customer-side evidence and is not described as
Nova-generated or Nova-dispatched. The role test used direct STS calls and a
temporary broker, not Nova's credential broker. The apply path remains
source-only, its gates remain disabled, and no customer workload is claimed as
Nova-applied or certified.
