# ticket443 — fit mixed Nova apply scopes within the STS policy limit

PR: https://github.com/Bepoadewale/davdeploy/pull/443
Branch: `fix/nova-apply-session-policy-size`

## Problem / goal

`build_nova_apply_access_policy` emits one exact-resource allow for each changed
resource, then repeats the complete action and resource lists in explicit deny
statements. A representative plan with one S3 bucket, one SQS queue, and one
DynamoDB table produces a 2,313-byte policy, exceeding AWS STS's 2,048-byte
inline session-policy limit. The plan therefore cannot reach credential
issuance even though every resource type is supported.

## Current repo state

- Backend `main` at the implementation base is `b60ca15` (PR #442).
- PR #399 is merged; the customer apply worker and credential path remain
  disabled and have not been exercised by Nova.
- The apply-role template's maximum policy explicitly denies actions outside
  its fixed S3, SQS, DynamoDB, IAM-inspection, and STS identity ceiling.
- Implementation commit `af147685998efbc423785a35e4bef0a3084a4fbf` is on
  `fix/nova-apply-session-policy-size`. PR #443's initial implementation and
  evidence head `83b292afc3ed5b4ee819e103f4155f66710600e2` passed all seven
  checks in run `45064740248`; this ticket update receives its own CI run.

## Research / references used

- `apps/api/src/davdeploy/nova_apply_access.py` — exact-plan permission mapping.
- `infrastructure/cloudformation/customer-nova-apply-role.yaml` — fixed
  customer role action ceiling.
- `tests/test_nova_apply_access.py` — scope, replacement, and size regressions.
- `tests/test_nova_apply_contract.py` and
  `tests/test_nova_apply_role_profile.py` — apply artifact and role contracts.

## Work planned for the PR

1. Keep exact-resource session grants and the S3 cross-account denial; retain
   the explicit session `Deny/NotResource` boundary.
2. Add a mixed S3/SQS/DynamoDB policy-size regression while keeping the
   fail-closed STS size limit.
3. Record local and isolated AWS validation; leave no persistent AWS resource
   or hosted control-plane change.

## Proposed change

- Keep service permissions in exact-resource `Allow` statements and retain the
  cross-account S3 denial.
- Remove the redundant session-policy maximum-action `Deny/NotAction` list.
  Keep the exact-resource `Deny/NotResource` boundary to constrain access even
  if a resource policy grants directly to the assumed role session. The
  customer role's fixed policy also keeps its explicit maximum-action deny.
- Keep the STS byte limit check so oversized plans still fail closed.
- Add a three-service regression asserting exact resource ARNs and a serialized
  policy size within the STS limit.

## Acceptance criteria

- [x] A representative S3 + SQS + DynamoDB plan builds within 2,048 bytes.
- [x] Service grants remain scoped to the exact planned resource ARNs.
- [x] The session policy contains no broad service-resource `Allow`; S3 retains
  its cross-account resource denial.
- [x] Existing unsupported-resource, replacement, S3 configuration, and
  oversized-policy checks remain in force.
- [x] Focused apply-policy, role-profile, and apply-contract regressions pass.
- [x] A temporary same-account role accepted exact-plan S3, SQS, and DynamoDB
  create/read grants, an SQS update grant, and a separate destroy grant; out-of-
  scope S3/SQS/DynamoDB creates and unrelated EC2 access were denied.
- [x] Independent post-cleanup reads confirmed the temporary stack, roles,
  bucket, queue, and table were absent.
- [x] The implementation/evidence head passed all seven required PR checks;
  the ticket follow-up is checked by PR CI before merge.
- [x] The hosted runtime, control-plane state, Terraform state, and execution
  gates were not changed.

## Acceptance status

Implementation and the isolated same-account action matrix are complete.
Documentation conventions, final PR CI, and independent review remain before
merge.

## Tests / validation performed

The focused suite passes 41 tests:

```text
PYTHONPATH=apps/api/src .venv-pr399/bin/python -m pytest \
  tests/test_nova_apply_access.py tests/test_nova_apply_contract.py \
  tests/test_nova_apply_role_profile.py -q
```

The regression's prior implementation measured 2,313 bytes for the mixed
three-service plan. The post-change policy sizes and live role checks are
recorded in [`test443.md`](../test/test443.md). The AWS calls used a temporary
same-account broker and the checked-in customer role template; Nova itself did
not issue the credentials or dispatch the work. All test resources were
removed and independently checked absent.

## Evidence files produced

- `apps/api/src/davdeploy/nova_apply_access.py`
- `tests/test_nova_apply_access.py`
- `docs/tickets/ticket443.md`
- `docs/test/test443.md`

## Boundaries

This fixes policy serialization for the tested resource mix; it does not prove
the complete effective AWS permission set, cross-account trust, Nova credential
issuance, or a hosted customer apply. Continue with the dedicated role and
authorization/dispatch acceptance work while preserving the general-goal ECS
customer-side lifecycle evidence already accepted by the owner.

## Follow-up work

Continue with the dedicated role and authorization/dispatch acceptance work,
then gather per-entry lifecycle evidence without changing the hosted control
plane or enabling execution gates.
