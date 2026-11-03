# test285 — Terraform certification input wiring

Date: 2026-11-03

Execution type: Local configuration contract tests; no AWS deployment.

Customer repository: None.

Commit: `1df3f9a` (Terraform workflow input wiring and configuration checks).

AWS account: None.

AWS region: None.

## Resources created

None. No GitHub Environment variables were modified and no infrastructure
changes were applied.

## Commands executed

- `make verify` — passed; 404 tests, Ruff, GitHub Actions variable/secret
  classification, OpenAPI snapshot, and Docker Compose configuration checks.
- `python3 scripts/check_doc_conventions.py` — passed.

## Observed result

The Terraform plan workflow passes an explicit certification boolean defaulting
to `false` and a JSON workspace allowlist defaulting to `[]`. The protected
apply workflow applies the immutable reviewed plan. The configuration checker
classifies both new GitHub variables as non-secret deployment metadata.

## Teardown

No resources were created, so no cleanup was required.

## Final boundary

This PR only wires optional inputs. Certification remains disabled by default;
the workspace allowlist remains empty unless an operator changes the protected
`terraform-plan` environment. General customer execution is unchanged.
