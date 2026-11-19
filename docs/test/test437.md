# test437 — same-account ECS Express customer pilot

Date: 2026-11-19
Execution type: Direct Terraform customer-side AWS create, health check, and destroy; the hosted control plane was not used.
Customer repository: `Bepoadewale/davdeploy`
Commit: `33c8e0803b6f334112665c6f6685e00ca3f0caa7` (tested source)
AWS account: `654654474502` (verified as `adewale-terminal`)
AWS region: `us-east-1`
Test connection: `ecs-customer-20261119-a1`

## Resources created

The monitored foundation apply `nova-customer-ecs-foundation-20261119-a2`
created 14 resources: a dedicated VPC, two public subnets, internet gateway,
route table and associations, ECR repository, two IAM roles and policy
attachments, a three-day CloudWatch log group, and an account guard. The saved
foundation plan contained 14 creates and no changes or deletes.

The service apply `nova-customer-ecs-service-20261119-a1` created one ECS
Express Mode service from the immutable image digest
`sha256:542b1b91cf26e144bde0d325ad7a6e0850e17b8b63d1b47e184d41f101616dbd`.
The service had a one-task ceiling, used the dedicated customer VPC, and did
not use the hosted control plane or platform state. Terraform waited 5m37s for
steady state.

## Commands executed

- `terraform fmt -recursive infrastructure/terraform/customer-workload-ecs-express-pilot`
  and `terraform -chdir=infrastructure/terraform/customer-workload-ecs-express-pilot init -backend=false -input=false`
  followed by `terraform validate`; validation passed with AWS provider `6.73.0`.
- `terraform fmt -check -recursive infrastructure/terraform`,
  `python3 scripts/check_doc_conventions.py`, and `git diff --check`; the PR
  CI run `44495466452` passed all seven checks at commit `33c8e08`.
- The `linux/amd64` health image was pushed to ECR with immutable tag
  `20261119-a1`; AWS reported digest
  `sha256:542b1b91cf26e144bde0d325ad7a6e0850e17b8b63d1b47e184d41f101616dbd`.
- The foundation plan contained 14 creates and was applied by monitored run
  `nova-customer-ecs-foundation-20261119-a2`. The service plan contained one
  create and was applied by monitored run
  `nova-customer-ecs-service-20261119-a1`.
- `curl --fail --show-error --silent --max-time 20 https://da-493a59786fdf471d88214bf9707533e0.ecs.us-east-1.on.aws/healthz`
  returned `{"status": "ok", "scope": "same-account-customer-sandbox"}`.
- The saved destroy plan contained 15 deletes and no creates or updates.

## Observed result

ECS Express reached steady state in 5m37s and the live `/healthz` endpoint
returned the expected JSON. The platform account was used only as a customer
sandbox, with local Terraform state and a dedicated VPC. The hosted control
plane was not used.

## Teardown

The first monitor invocation used Terraform's `destroy` command with a saved
destroy plan; Terraform rejected that command form before making changes. The
same reviewed plan was correctly applied through the monitor as
`nova-customer-ecs-destroyplan-apply-20261119-a1`; it completed with 15
destroyed, zero added, and zero changed.

The VPC, ECR repository, both IAM roles, log group, load balancer, target group,
network interfaces, and all Terraform-managed resources are absent. Local
Terraform state is empty. ECS reports the test service as `INACTIVE` with
zero desired, running, or pending tasks; the default cluster is empty. AWS
retains stopped-task/service history and an empty default cluster record. These
records have no running workload; the tag index may continue to show historical
ECS records after deletion.

## Final boundary

This is direct same-account customer-side infrastructure evidence and may serve
as the isolated customer deployment test while the hosted control plane remains
untouched. It is not evidence that Nova initiated an apply, and it does not
prove cross-account isolation. No update/recovery test was run. The PR remains
draft pending that lifecycle gate and the broader Nova acceptance decision.
