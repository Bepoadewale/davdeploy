# test340 — customer Nova plan-role permission profile

Date: 2026-11-11
Execution type: Local code and policy validation only. No customer AWS API calls, AWS resource changes, or Nova model calls.
Customer repository: Not applicable; this PR changes the DavDeploy backend and customer-role setup template.
PR implementation head: Pending final commit.
Commit: Pending final implementation commit.
AWS account: None used for this test.
AWS region: None used for this test.

## Resources created

None. No customer role was assumed and no AWS resources were created or changed.

## Commands executed

- Focused Nova plan-access, CodeBuild contract, customer connection template,
  generated-plan manifest, and related service tests — 34 passed before the
  final composed-profile regression was added. The full final command/result
  will be recorded after rerun.
- Ruff check on changed Python files — passed before the final regression was
  added. Final lint and formatting results are pending.
- `make verify` — pending.
- Isolated `make local-proof` — pending.
- `python3.12 scripts/check_doc_conventions.py` — pending.
- `git diff --check` — pending.

## Observed result

The worker constructs a versioned, deterministic STS session policy before
assuming the customer plan role. Unsupported resource types and unsafe resource
identifiers fail before the role assumption. Policy resource scopes are derived
from the trusted account, region, and proposal; S3 also has an explicit
resource-account deny. The access-policy version and digest are included in
the saved-plan manifest and independently recomputed before the API accepts
the result.

The first composed profile contains API Gateway v2, Lambda/SQS async work,
private S3, DynamoDB, and scoped IAM role policy resources. It must remain under
the 2,048-character AWS STS inline policy limit. Exact length and final test
results will be recorded after final verification.

## Teardown

No AWS resources were created. The isolated clean-room cycle’s exact project
containers and generated artifacts will be recorded after it runs; no existing
customer or shared production resources may be removed.

## Final boundary

Passing local policy tests do not attest an installed customer role policy,
AWS organization policies, customer account permissions, hosted worker
behavior, regional pricing, approval, apply, health, recovery, or teardown.
Hosted feature gates remain disabled. The existing customer setup role is not
changed by this PR until the customer installs the updated template.
