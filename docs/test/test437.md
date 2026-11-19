# test437

Date: 2026-11-19
Execution type: Terraform formatting/schema validation and host-local health fixture; no AWS workload applied.
Customer repository: `Bepoadewale/davdeploy`
Commit: `5a5a464` (`feat: add same-account ECS Express customer pilot`)
AWS account: `654654474502` (identity read only)
AWS region: `us-east-1`

## Resources created

None. Terraform was initialized without a backend and validated; the customer
root was not applied to AWS.

## Commands executed

- `terraform fmt -recursive infrastructure/terraform/customer-workload-ecs-express-pilot`
- `terraform -chdir=infrastructure/terraform/customer-workload-ecs-express-pilot init -backend=false -input=false`
- `terraform -chdir=infrastructure/terraform/customer-workload-ecs-express-pilot validate`
- `terraform fmt -check -recursive infrastructure/terraform`
- `python3 scripts/check_doc_conventions.py`
- `git diff --check`
- Host-local `/healthz` request against `tests/fixtures/customer-ecs-express-health/server.py`.
- Read-only AWS caller identity and default VPC/subnet inventory.

## Observed result

The new root validated without warnings with AWS provider `6.73.0`. The
host-local fixture returned the expected JSON response. AWS documentation says
App Runner closed to new customers and recommends ECS Express Mode. No ECS
service or customer resource has been applied yet.

## Teardown

Not applicable. This validation created no AWS resources.

## Final boundary

This proves source structure, Terraform provider-schema compatibility, and a
host-local handler response only. It does not prove ECS Express deployment,
customer health, Nova apply, or hosted lifecycle. The hosted control plane and
its state, runtime, queues, and API were not touched.
