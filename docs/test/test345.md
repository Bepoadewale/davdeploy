# test345 — Nova customer template and control-plane rollout

Date: 2026-11-11

Execution type: Real AWS template-host and control-plane deployment; no
customer workload was deployed.

Repository: `Bepoadewale/davdeploy`

Customer repository: Not applicable; no customer repository or workload was
used.

Commit: `10103149d444805877b464ae4e9afe056f8af3f8` (control-plane source).

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

- One public, immutable, versioned S3 CloudFormation template object:
  `cloudformation/customer-discovery-role-f3d9e1e5776fe147bbbc10107e41d221497f9b98c6b641eb8ac08467fd54aedb.yaml`.
- The existing 7e object was retained through a Terraform state move; it was
  not re-uploaded or deleted.
- No customer CloudFormation stack, IAM role, or workload resource was created
  or changed.

Existing public setup URL:
`https://davdeploy-customer-templates-654654474502.s3.us-east-1.amazonaws.com/cloudformation/customer-discovery-role-7e03683a397f0d4e2a5f68b9559d2790ff127e5513540457b47e9c4779b2b793.yaml`.
New public setup URL:
`https://davdeploy-customer-templates-654654474502.s3.us-east-1.amazonaws.com/cloudformation/customer-discovery-role-f3d9e1e5776fe147bbbc10107e41d221497f9b98c6b641eb8ac08467fd54aedb.yaml`.

## Commands executed

Template-host saved plan and account guard:

```text
EXPECTED_AWS_ACCOUNT_ID=654654474502 TF_STATE_BUCKET=davdeploy-tfstate-654654474502 TF_LOCK_TABLE=davdeploy-terraform-locks AWS_REGION=us-east-1 DAVDEPLOY_TEMPLATE_BUCKET=davdeploy-customer-templates-654654474502 AWS_PROFILE=ai-platform-pilot-key ./scripts/customer-aws-template-host.sh plan
```

The saved template-host plan was produced from merged main commit
`10103149d444805877b464ae4e9afe056f8af3f8`. Terraform 1.14.0 plan digest:
`1ff1e6dda6e928af15d2106dae7ae6802c9bb5dba7796292f50c3ccb218afd86`.
Reviewed actions: one S3 object create for the f3d9e1 template, zero updates,
zero destroys; the previous active object state moved to retained key 7e.
Bucket policy, encryption, versioning, ownership controls, and public-access
configuration were no-ops.

The exact saved plan was applied by repository monitor run
`davdeploy-template-host-344-apply-20261111` against
`infrastructure/terraform/connection-template-host`. Supervisor PID `37420`,
Terraform PID `37421`, exit code `0`; the log recorded one object added, zero
changed, zero destroyed. Log:
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/davdeploy-template-host-344-apply-20261111.log`.

Read-only S3 `HeadObject` checks confirmed the old 7e object is 5,401 bytes,
version `n2TcoAoYYbzagk4VM5E8ermoFgV5kZsw`, AES256; the new f3d9e1 object is
8,813 bytes, version `X7zBQKpVUOz05MhKqyoW3tvzgPJK6YJL`, AES256. Public GETs
for both old and new URLs returned HTTP 200 with `application/x-yaml`.

The protected GitHub environment variable `AWS_CONNECTION_TEMPLATE_URL` was
updated to the f3d9e1 URL. Terraform plan workflow run `42985045247` succeeded
for commit `10103149d444805877b464ae4e9afe056f8af3f8`. Its encrypted saved-plan
manifest SHA-256 is
`c6a7f6577ee92645dd8f570e5736f2fee64fdea00819385048b5ed041cd78733`. The
reviewed control-plane plan had zero additions, six in-place Lambda updates,
and zero destroys; `DAVDEPLOY_AWS_CONNECTION_TEMPLATE_URL` changed to the new
URL in the API, worker, and migration runtime configuration.

Protected apply workflow run `42985628568` succeeded for the exact plan.
Saved-plan verification and database migration checks passed. Read-only
postchecks in account `654654474502` found all six Lambda functions Active,
`LastUpdateStatus=Successful`, and the same deployed package SHA-256
`vzY68YDPtiVlLgUODzoAJLfUfr9GbWtqGc+vYdWl1XE=`. The API, worker, and migration
functions use the new template URL. `GET https://api.davdeploy.tech/healthz`
returned HTTP 200 and `{"status":"ok","product":"davdeploy"}`.

The Nova plan-review, plan-only runner, plan-role verification, and Terraform
state API flags were `false`. The existing `ALLOW_CLOUD_APPLY=true` legacy
setting was unchanged and does not enable the Nova saved-plan path.

Documentation checks run for this evidence PR:
`GITHUB_PR_NUMBER=345 .venv/bin/python scripts/check_doc_conventions.py` and
`git diff --check` both passed locally. All seven required final-head CI checks
passed in run `42987624957` (cloud contracts, docs conventions, local
integration, policy, Python, secrets, and supply chain).

## Observed result

The new template is public and versioned, the previous customer setup URL
continues to work, and the hosted control plane now emits the new URL. No Nova
customer plan, customer role, or customer workload was created, applied,
operated, or certified. Regional pricing remains unavailable, so exact costed
Nova plan approval remains blocked.

## Teardown

None. The template is a published product artifact intended to remain
available; both old and new immutable URLs are retained.

## Final boundary

This is control-plane/template-host deployment evidence only. It does not
prove Nova-generated customer planning or execution, customer application
health, recovery, teardown, or certification.
