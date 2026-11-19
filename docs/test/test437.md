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

## Additional update, recovery, and teardown run

The second run used fresh local state in
`/private/tmp/davdeploy-ecs-lifecycle-20261119-b1/root`, connection
`ecs-lifecycle-20261119-b1`, and source commit
`bc59160bbce3143ecf5e54938531f0637b60cb8f`. The AWS account was verified as
`654654474502` (`adewale-terminal`) in `us-east-1`. It did not call or modify
the hosted control plane, its state, locks, runtime, queues, or API.

The foundation saved plan contained 14 creates, zero changes, and zero deletes.
The service v1 plan contained one create; the v2 and failed-health plans each
contained one in-place update and no replacement or unrelated resource action.
Images were built for `linux/amd64` and deployed by digest:

| Revision | Immutable image digest | Observed result |
| --- | --- | --- |
| v1 | `sha256:f9daaacbcbd6260cf6c72a1b145508a3b3b7cc61842931952d56629981f05274` | `/version` and `/healthz` returned healthy v1; initial service reached steady state in 5m03s |
| v2 | `sha256:7375991c183327719e31599d827279eaf83f1425dc49fce5ee7b324a1abbed52` | In-place update completed in 8m36s; `/version` and `/healthz` returned healthy v2 |
| failed | `sha256:4fe5398fda4d4f6fa0c5b7a8c9398d1721b54355130455a367cf2b10245486bc` | ECS deployment circuit breaker rolled back the revision; monitored Terraform apply returned the expected error after 14m11s; `/healthz` returned HTTP 200 and healthy v2 |

A fresh plan against the restored v2 configuration showed no changes. The
reviewed saved destroy plan contained exactly 15 deletes and no additions or
updates. Its monitored apply completed with zero added, zero changed, and 15
destroyed. Independent AWS reads confirmed that the ECR repository, customer
VPC, both IAM roles, and CloudWatch log group were absent; local Terraform state
was empty. ECS retains the service record as `INACTIVE` with zero desired,
running, and pending tasks. AWS historical service records remain; there is no
running workload or Terraform-managed test infrastructure.

### Monitored runs

All runs used the existing `scripts/terraform_run_monitor.py` and the same
isolated local-state root. Supervisor PID / Terraform PID and log path:

| Run ID | Result | Supervisor / Terraform PID | Log |
| --- | --- | --- | --- |
| `nova-customer-ecs-foundation-20261119-b1` | Succeeded: 14 created | `35797 / 35798` | `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-customer-ecs-foundation-20261119-b1.log` |
| `nova-customer-ecs-service-v1-20261119-b1` | Succeeded: 1 created | `38134 / 38135` | `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-customer-ecs-service-v1-20261119-b1.log` |
| `nova-customer-ecs-service-v2-20261119-b1` | Succeeded: 1 in-place update | `39852 / 39853` | `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-customer-ecs-service-v2-20261119-b1.log` |
| `nova-customer-ecs-service-failed-20261119-b1` | Expected circuit-breaker rollback; apply returned exit 1 | `43746 / 43747` | `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-customer-ecs-service-failed-20261119-b1.log` |
| `nova-customer-ecs-lifecycle-destroy-20261119-b1` | Succeeded: 15 destroyed | `55536 / 55537` | `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-customer-ecs-lifecycle-destroy-20261119-b1.log` |

## Final boundary

This is direct same-account customer-side infrastructure evidence and may serve
as the isolated customer deployment test while the hosted control plane remains
untouched. The first run proved create, health, and cleanup. A second isolated
run additionally proved healthy v1-to-v2 update, circuit-breaker rollback of a
deliberately unhealthy revision, recovery on v2, and teardown. Both runs used
direct Terraform and local state; neither proves Nova initiated an apply or
cross-account isolation. On 2026-11-19, the goal owner accepted this isolated
customer-side evidence for the general Nova infrastructure goal in place of a
hosted customer apply under the required control-plane isolation. It does not
establish Nova generation, authorization, dispatch, cross-account isolation, or
Nova-specific lifecycle behavior. No Nova customer workload is claimed as
applied or certified.
