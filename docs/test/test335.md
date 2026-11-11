# test335 — November 10 backend release status reconciliation

Date: 2026-11-11
Execution type: Documentation review against merged source, GitHub workflow records, and read-only hosted API/AWS observations
Customer repository: N/A; no customer repository or workload was used
Commit: `f0c6f3af36a0ab14a5dafb9a1684c41140da7eef` (deployed source)
AWS account: `654654474502`
AWS region: `us-east-1`
Terraform plan run: [42902031985](https://github.com/Bepoadewale/davdeploy/actions/runs/42902031985)
Terraform apply run: [42902934302](https://github.com/Bepoadewale/davdeploy/actions/runs/42902934302)

## Resources created

No customer infrastructure was created by this documentation update. The
referenced control-plane changes were deployed in the saved-plan apply listed
above.

## Commands executed

No Terraform or AWS mutation was run for this documentation-only PR. Read-only
AWS CLI checks reconfirmed account `654654474502`, plan/state bucket
versioning, encryption, and public-access blocks. The workflow, Lambda, and
HTTP observations below were collected during the November 10 deployment
verification and rechecked against its recorded evidence.

```text
aws sts get-caller-identity --profile ai-platform-pilot-key --query Account --output text
aws s3api list-buckets --profile ai-platform-pilot-key --query 'Buckets[?contains(Name, `davdeploy`)].Name' --output text
aws s3api get-bucket-versioning --profile ai-platform-pilot-key --bucket davdeploy-tfplans-654654474502
aws s3api get-bucket-encryption --profile ai-platform-pilot-key --bucket davdeploy-tfplans-654654474502
aws s3api get-public-access-block --profile ai-platform-pilot-key --bucket davdeploy-tfplans-654654474502
aws s3api get-bucket-versioning --profile ai-platform-pilot-key --bucket davdeploy-tfstate-654654474502
aws s3api get-bucket-encryption --profile ai-platform-pilot-key --bucket davdeploy-tfstate-654654474502
aws s3api get-public-access-block --profile ai-platform-pilot-key --bucket davdeploy-tfstate-654654474502
```

## Evidence reviewed

- The protected Terraform plan reports 6 additions, 8 in-place changes, and
  0 destroys. The additions provision Terraform state HTTP API routes and
  supporting integration. Plan-history APIs from #333/#334 are present in the
  deployed backend package. The plan keeps Nova plan review, runner
  readiness, and state API switches false.
- The protected apply completed successfully on 2026-11-10 at 21:49:11 UTC;
  the saved-plan apply step and database migration verification passed.
- Read-only Lambda observation: `davdeploy-api` Active,
  `LastModified=2026-11-10T21:48:25Z`,
  `CodeSha256=yu14QmQKQN4NYV2BUHt2/rP/Xf3ZHYQMk9SHcM/Aphw=`.
- `GET https://api.davdeploy.tech/healthz` returned HTTP 200 with
  `{"status":"ok","product":"davdeploy"}`.
- An unauthenticated request to
  `/api/v1/projects/00000000-0000-0000-0000-000000000000/generated-plan-runs?limit=1`
  returned HTTP 401. This confirms the route is protected; it does not verify
  an authenticated customer's access or plan history.
- Nova plan review, runner readiness, role verification, and Terraform state
  API switches remain false; no bucket is configured for Nova tenant state.
- Read-only account inventory found the existing `davdeploy-tfplans-654654474502`
  bucket is versioned, KMS-encrypted with the DavDeploy plans key, and has all
  four public-access blocks enabled. The existing
  `davdeploy-tfstate-654654474502` bucket is versioned and has all four public
  access blocks enabled, but currently uses S3-managed `AES256` encryption.

## Result and limits

The backend plan-history endpoints from PRs #333 and #334 are deployed. The
source/backend release is current at the recorded commit. This is not evidence
of a customer-created Nova plan, an authenticated plan-history journey, priced
approval, Terraform apply of customer resources, workload health, recovery,
teardown, or independent absence verification. No customer infrastructure
was created or changed by the release.

This PR updates documentation only. It makes no AWS calls, changes no runtime
configuration, and does not enable Nova execution.

## Observed result

The backend source through PR #334 is deployed. The basic health endpoint
returned HTTP 200 and the unauthenticated history request returned HTTP 401.
The latter confirms authentication is required; it is not an authenticated
customer access test. Nova execution switches remain disabled.

## Teardown

No resources were created by this documentation change, so no teardown was
required.

## Final boundary

The release is verified for the control-plane deployment and protected route
response only. Costed customer plans, authenticated customer history, customer
apply, application health, recovery, destroy, and absence verification remain
unproven.
