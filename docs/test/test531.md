# test531 — Authenticated hosted Nova plan attempt

Date: 2026-11-27
Execution type: Hosted API planning with isolated same-account AWS role setup
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance input only)
Commit: `b520906aa59073967fa0e5f81f559be957b255cd` (source main at role/plan test time; package mapping not re-established)
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

Test ID: `nova-hosted-acceptance-3964addb`

- Connection: `3964addb-9f00-4c87-b829-2c3cd3b0b48c`.
- Discovery stack `davdeploy-Discovery-3964addb`: `CREATE_COMPLETE`; its only
  resource is the exact read-only discovery role. The trust policy uses the
  connection-scoped external ID. No secret value is recorded here.
- Plan stack `davdeploy-Plan-3964addb-9f00-4c87-b829-2c3cd3b0b48c`:
  `CREATE_COMPLETE`; its only resource is the exact plan-only role. The final
  role has exactly the `ManagedBy`, `ConnectionId`, and `Access` tags required
  by its verifier. Both roles use the versioned template whose SHA-256 is
  `8c5d1c82682b3bb90ff1f45d121b475e7b33b484f556feabafbf387c335aea4e`.
- A temporary stack-level `TestId` tag propagated to the plan role and caused
  the first profile verification to fail. The stack tag set was updated without
  replacing its template or parameters; subsequent authenticated verification
  succeeded with connection state `VERIFIED` and plan-role state
  `PROFILE_VERIFIED`.
- No Nova customer workload resource was created.

## Commands executed

- CLI password-plus-TOTP sign-in through `davdeploy auth login`; `/api/v1/me`
  verified the workspace before the CLI session was stored in macOS Keychain.
- Read-only AWS caller, CloudFormation, IAM, Lambda readiness-flag, and
  Terraform-monitor checks. The Terraform monitor had 75 historical records
  and zero active operations.
- Authenticated hosted connection verification, intent/architecture planning,
  customer-review submission, and review-only generated-plan request.
- API `/healthz` returned HTTP 200.

## Observed result

- The plan-only role verification succeeded after its stack tags matched the
  strict profile.
- Architecture plan `4adb10ea-ee9e-43eb-8ee1-dfb860a63f13` returned `PLANNED`
  and policy `ALLOW`, but selected only Lambda/API and omitted private storage,
  database, and queue-backed processing requested by the test intent.
- The reported `$50–$170` monthly range used fixture catalogue
  `aws-v1-fixture-2026-10` and `us-east-1-like` pricing assumptions. It is not
  current regional pricing evidence.
- Generated-plan run `754421c8-1f04-4b81-8f95-78d92e0ee243` failed with
  `NOVA_GENERATION_FAILED` before a Terraform artifact existed. No human
  approval or apply was attempted. Exact-plan apply readiness and project
  configuration were false.
- A later Keychain lookup timed out; a subsequent CLI login attempt was
  rejected by Cognito MFA and did not create a new session. Do not reuse the
  expired code.

## Teardown

No teardown was run. The two exact role stacks are retained to support the
verified test connection and the next plan-only attempt. No workload resources
exist from this test. Cleanup remains a later explicit evidence step.

## Final boundary

This proves a CLI-authenticated workspace identity, a verified same-account
discovery/plan-only connection, and one hosted architecture-plan attempt. It
does not prove a valid generic saved plan, approval, apply, application health,
update, recovery, destroy, or independent workload absence. No Nova customer
workload has been applied, operated, or certified.
