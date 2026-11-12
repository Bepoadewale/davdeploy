# test382 — record the PR #381 template and control-plane release

- Date: 2026-11-12
- Execution type: Documentation reconciliation using completed AWS deployment
  records and read-only post-deployment checks
- Repository: `Bepoadewale/davdeploy`
- Customer repository: N/A; DavDeploy control-plane deployment
- Commit: PR #381 merge commit `a12205972cc124d08d85845f30c9b574f7cf87fd`
- Pull request: [#382](https://github.com/Bepoadewale/davdeploy/pull/382)
- AWS account: `654654474502`
- AWS region: `us-east-1`

## Template publication

The monitored Terraform apply `pr381-template-host-a122059` targeted
`infrastructure/terraform/connection-template-host`, completed with exit code
0, and reported 1 added, 0 changed, and 0 destroyed. Its monitor recorded
supervisor PID `48889`, Terraform PID `48890`, and log
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/pr381-template-host-a122059.log`.

The published immutable URL is:

`https://davdeploy-customer-templates-654654474502.s3.us-east-1.amazonaws.com/cloudformation/customer-discovery-role-8c5d1c82682b3bb90ff1f45d121b475e7b33b484f556feabafbf387c335aea4e.yaml`

The new object returned HTTP 200, had content type `application/x-yaml`,
server-side AES256 encryption, and matched its content-hash key. CloudFormation
`validate-template` accepted the URL and returned the expected five parameters.
The previous `f3d9…` URL remains available and returned HTTP 200. The hosted
`terraform-plan` environment's `AWS_CONNECTION_TEMPLATE_URL` now points to the
verified new URL.

## Commands executed

- Terraform template-host apply was run through
  `scripts/terraform_run_monitor.py` using the exact reviewed saved plan.
- Protected control-plane plan and exact saved-plan apply ran through GitHub
  Actions after verifying the new template URL.
- Read-only checks queried Lambda status/configuration, API health, template
  HTTP availability, content digest, and CloudFormation template validity.

## Resources created

- One immutable public S3 object for the customer plan-role template.
- No customer-account role, stack, or workload.

The reviewed control-plane release updated six Lambda packages in place; it did
not create or delete workload resources.

## Control-plane release

Protected Terraform plan run `43260003885` targeted exact source
`a12205972cc124d08d85845f30c9b574f7cf87fd`; it completed applyable with 0
additions, 6 in-place Lambda updates, 0 destroys/replacements, and 0 drift.
It used the verified `8c5d…` template URL. The exact saved-plan apply was run
`43261766144`, GitHub deployment `7743511328`; its manifest verification and
database migrations succeeded.

Read-only checks found all six control-plane Lambda functions Active and
Successful with common `CodeSha256=6B3DVTL6dXaQ6K5leePzfmckPO+2/3BTKenPHpBOoqQ=`.
API `/healthz` returned HTTP 200 with `{"status":"ok","product":"davdeploy"}`.
API, worker, and migration functions reference the new immutable template URL.

The Nova plan runner, credential broker, plan reviews, and Terraform state API
remain disabled; plan-role trust/account verification is enabled. No customer
role or stack was installed, and no Nova plan or customer workload was created
or applied. Therefore this release is not evidence of customer planning,
approval, apply, health, recovery, teardown, or composed certification.

## Observed result

Template and control-plane deployments completed; all post-deployment checks
described above passed. Nova execution gates remain disabled.

## Teardown

No teardown was required. The newly published immutable customer template is
intentionally retained for future customer setup links. No customer AWS role,
CloudFormation stack, or workload was created.

## Final boundary

This evidence verifies template publication and a control-plane release only.
It does not prove customer role installation/effective permissions, hosted Nova
planning, exact cost approval, customer apply, health, recovery, teardown, or
composed certification. PR-local documentation validation and CI results are
recorded in `docs/tickets/ticket382.md` and the pull request checks.
