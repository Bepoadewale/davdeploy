# test285 — Terraform certification input wiring

Date: 2026-11-03

Execution type: Local configuration contract tests and protected production control-plane deployment.

Customer repository: None.

Commit: `2e39e4a45fee9bd69b5827a48431c052e5f772e2` (Terraform workflow input wiring and configuration checks).

AWS account: `654654474502` (control-plane release only; no customer workload).

AWS region: `us-east-1`.

## Resources created

The protected apply changed six existing control-plane Lambda package versions
in place and created or destroyed no infrastructure. No customer workload was
deployed. The certification flag remained `false`, and its workspace list
remained empty.

## Commands executed

- `make verify` — passed; 404 tests, Ruff, GitHub Actions variable/secret
  classification, OpenAPI snapshot, and Docker Compose configuration checks.
- `python3 scripts/check_doc_conventions.py` — passed.
- Protected plan run [41729846651](https://github.com/Bepoadewale/davdeploy/actions/runs/41729846651)
  passed for the merged main commit. It planned 0 additions, 6 in-place Lambda
  package updates, and 0 destructions.
- Protected apply run [41730396958](https://github.com/Bepoadewale/davdeploy/actions/runs/41730396958)
  passed after the authorized `terraform-apply` environment review. Migration
  verification succeeded.
- Read-only Lambda configuration check confirmed
  `DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION=false` and an empty
  `DAVDEPLOY_SERVERLESS_CERTIFICATION_WORKSPACE_IDS` value.
- `curl -fsS https://api.davdeploy.tech/healthz` — returned
  `{"status":"ok","product":"davdeploy"}`.

## Observed result

The Terraform plan workflow passes an explicit certification boolean defaulting
to `false` and a JSON workspace allowlist defaulting to `[]`. The protected
apply workflow applies the immutable reviewed plan. The configuration checker
classifies both new GitHub variables as non-secret deployment metadata. The
merged code is now deployed with those safe values.

## Teardown

No resources were created, so no cleanup was required.

## Final boundary

This PR wires optional inputs and is deployed. Certification remains disabled;
the workspace allowlist is empty. General customer execution is unchanged.
