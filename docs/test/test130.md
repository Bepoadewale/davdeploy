# test130 — Live customer cloud pilot

Date: 2026-10-24
Execution type: Real AWS customer-style execution, partially complete
Customer repository: Pending live private-GitHub onboarding
Commit: Pending repository selection
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

- Customer-sandbox VPC, two private subnets, security group, App Runner VPC connector, CloudWatch
  log group and ECR repository, created by the successful foundation apply recorded below.
- No App Runner service has been created.

## Commands executed

- AWS read-only identity, resource-tag, ECR, App Runner, CodeBuild, Lambda, API Gateway, Aurora
  and S3-artifact inspection using the existing scoped operator profile.
- Cognito `USER_AUTH` for the founder account and authenticated `GET /api/v1/me`.
- Authenticated `GET /api/v1/github/connection`,
  `GET /api/v1/admin/customer-plan-revisions`, and `GET /api/v1/cloud-connections`.
- HTTPS checks for the API health endpoint, `davdeploy.tech`, and
  `davdeploy-frontend.pages.dev`.

## Observed result

- AWS account `654654474502`, region `us-east-1`; the API health endpoint returned `200`.
- Cognito founder authentication and `/api/v1/me` returned an administrator identity.
- The founder workspace currently has no customer-plan revisions or cloud connections.
- Its GitHub endpoint reports `execution=SIMULATED`; no GitHub App credentials are configured in
  the production API, so private-repository onboarding is not yet live. The existing App
  installation `167128937` for `Bepoadewale` was subsequently verified with the local App key.
- The existing customer connection ID `0dc9b546-6ec6-4d46-a498-b078d1fc273c` has a successful
  foundation apply run `9187d820-c769-40dd-93ff-01b90f804fd9` and successful image build run
  `70935f5c-1f71-43fc-9d1e-561c2b47f43d`.
- Retained workload resources are the scoped VPC, two private subnets, security group, App Runner
  VPC connector, CloudWatch log group, and ECR repository. No App Runner service exists.
- Cloudflare Pages production deployment is healthy for both `davdeploy.tech` and
  `davdeploy-frontend.pages.dev`.

## Teardown

No teardown command ran. The retained customer-sandbox workload resources require a separately
reviewed saved destroy plan and explicit owner approval after service smoke testing.

## Final boundary

The run uses the customer's scoped connection roles, a reviewed immutable plan digest, an approved
revision, a checksum-bound saved Terraform plan, and the bounded CodeBuild runner. No credentials
or external IDs are included in this record. Private GitHub onboarding, App Runner service apply,
and governed destroy are not claimed as complete.

## Evidence to record before completion

- Customer repository and pinned commit.
- Account and region.
- Plan-only review result and artifact location class.
- Apply result, actual resources, outputs, and observations.
- Separately reviewed destroy-plan result.
- Destroy result and direct absence checks.
- Retained control-plane and customer-connection resources.
- Known limitations, including any fixture-only evidence.

## Current blocker

The existing customer workspace is accessible through its refreshed short-lived Cognito session.
Private GitHub onboarding remains blocked on deployment of the existing installed GitHub App's
dedicated Secrets Manager configuration. The current approved revision uses fixture pricing, so a
fresh plan with current pricing provenance is required before service apply. No claim of private
repository discovery, service apply, or destroy is made until those controls are live and
validated.

## Final lifecycle evidence — 2026-10-25

This section supersedes the historical progress notes above.

- Approved revision: `91ee8d55-834f-47fb-a090-bb17a42daf9d`; immutable digest:
  `1f99bb927ac151d9e018fd613470c71535dc95357745c1cac6ac15962b837fcd`.
- Authenticated saved apply-plan review: `584f8393-7988-4a29-a394-f733e26423e7`; runner
  `9d9420b2-bbdf-4bdf-bd34-29fabe09d53d` succeeded.
- Authenticated apply: `2431209c-4912-4ea0-85a0-cf750d49148a`; CodeBuild succeeded and ingested
  real service, ECR, VPC, subnet, connector, and runtime-role outputs.
- The corrected private egress design added a NAT subnet/gateway, internet gateway, routes, and
  HTTPS-only outbound security-group rule. The App Runner workload remained in private subnets.
- App Runner reached `RUNNING`; direct HTTPS `GET /healthz` returned `{"status":"ok"}`.
- Separate saved destroy-plan review: `66dcb7b7-02de-4aad-bf62-4acd2334e0f9`; runner
  `ede81547-afc3-44b0-95c6-4e63189a4ef3` succeeded.
- Governed destroy: `74dbf1c3-7377-475b-9e1d-69bbd15efd29`; CodeBuild succeeded and recorded
  `DESTROYED_VERIFIED` / `confirmed_absent`.
- Independent AWS reads found the VPC and ECR repository absent and App Runner/NAT in terminal
  `DELETED` / `deleted` states. Customer connection roles were retained intentionally.

Private GitHub onboarding is the only remaining external dependency: App `5159790`, installation
`167128937` exists, but the private pilot repository has not been owner-authorized into that
installation. Pricing/inventory provenance was refreshed, while the displayed estimate remains a
documented fixture range rather than a live commercial quote.

