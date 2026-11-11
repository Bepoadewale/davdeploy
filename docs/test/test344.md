# test344 — customer template retention address migration

Date: 2026-11-11

Execution type: Terraform configuration validation and read-only hosted plan.
The initial hosted plan failed before any mutation; the corrected plan
succeeded with one template-object creation and zero changes or destroys.

Repository: `Bepoadewale/davdeploy`

Customer repository: Not applicable; no customer repository or workload was
used.

Commit: `dda5068c5c0d2d961efdb6e84fb52b760aa7333e` (evidence update pending).

AWS account: `654654474502` for the read-only initial plan.

AWS region: `us-east-1`.

## Resources created

None. The checks were read-only; no AWS resource was created or changed.

## Commands executed

Initial hosted plan:

```text
EXPECTED_AWS_ACCOUNT_ID=654654474502 TF_STATE_BUCKET=davdeploy-tfstate-654654474502 TF_LOCK_TABLE=davdeploy-terraform-locks AWS_REGION=us-east-1 DAVDEPLOY_TEMPLATE_BUCKET=davdeploy-customer-templates-654654474502 AWS_PROFILE=ai-platform-pilot-key ./scripts/customer-aws-template-host.sh plan
```

The command failed with Terraform `Moved object still exists`: the declared
`current_customer_discovery_role` object occupied the source of the new move.
No plan was produced and no AWS writes occurred.

`.venv/bin/python -m pytest -q tests/test_customer_aws_connection_contract.py`
passed (9 tests). `terraform -chdir=infrastructure/terraform/connection-template-host
fmt -check -diff` passed. `make terraform-validate` passed for all roots.
`GITHUB_PR_NUMBER=344 .venv/bin/python scripts/check_doc_conventions.py` and
`git diff --check` passed. Required PR CI run `42982526696` passed all seven
checks: cloud contracts, documentation conventions, local integration,
policy, Python, secrets, and supply chain.

Read-only state inspection used
`AWS_PROFILE=ai-platform-pilot-key terraform -chdir=infrastructure/terraform/connection-template-host state list`.
`HeadObject` metadata probes confirmed the existing 600 (4,950 bytes) and 7e
(5,401 bytes) objects and returned 404 for the configured 0e key. After moving
the actual `active_customer_discovery_role` address to the retained 7e key and
removing the absent 0e entry, the corrected read-only plan proposed exactly
one create for the new f3d9e1 template, zero changes, and zero destroys. The
existing 7e object is represented as a state move, not an upload. No apply was
run.

## Teardown

None. No cloud or local disposable resources were created by these checks.

## Observed result

The initial plan refreshed the existing bucket and objects, then stopped at
Terraform's configuration validation before proposing actions. A second plan
proposed two creates because state showed the live 7e object under the `active`
address and the configured 0e key had no S3 object. The corrected plan moves
the active state to retained[7e], creates the new f3d9e1 object, and proposes
zero destroy or in-place changes. No plan was applied; no object upload,
deletion, customer role change, or control-plane deployment occurred.

## Resources created / teardown

None. No teardown was needed.

## Final boundary

The Terraform failure is evidence that PR #343 alone cannot publish the new
object. The corrected plan is read-only and preserves the old URL. Any apply
must use a freshly saved and reviewed plan after this PR merges.
