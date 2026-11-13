# test401 — generated-plan network ACL policy evidence

Date: 2026-11-13
Execution type: isolated local fixture and synthetic Terraform plan policy tests
Customer repository: none; backend source worktree
Commit: `bbcfe72` (implementation and local-proof revision)
AWS account: none; no AWS credentials used
AWS region: none

## Resources created

No AWS resources. The isolated local proof created Docker containers, a
project-specific network and volume, and local proof state; details and
retention status are recorded below.

## Commands executed

- `pytest tests/test_generated_plan_policy.py -q`
- `make verify VENV=.venv-pr401`
- `make local-proof VENV=.venv-pr401` with isolated Compose project
  `davdeploy-pr401-network-final2-20261113` and subnet `10.252.250.0/24`
- `GITHUB_PR_NUMBER=401 .venv-pr401/bin/python scripts/check_doc_conventions.py`
- `git diff --check`
- GitHub Actions CI run `43498568620` passed all seven jobs for implementation
  commit `481c386`.

## Scope and result

This change adds actual-plan checks for ingress rules in `aws_network_acl`,
`aws_default_network_acl`, and `aws_network_acl_rule`. Public administrative
and data ports, and public all-protocol ACL ingress, are denied. Public
web/general ingress requires human review. Malformed and policy-critical
unknown inputs fail closed. Scoped ingress and public egress are not treated as
public inbound exposure. The existing security-group check now recognizes
globally routable CIDRs beyond `/0`.

## Local verification

- `pytest tests/test_generated_plan_policy.py -q`: 159 passed.
- `make verify VENV=.venv-pr401`: passed; 1,102 tests, Ruff, OpenAPI,
  Actions configuration, and Docker Compose configuration checks passed.
- `make local-proof`: passed in the isolated Compose project
  `davdeploy-pr401-network-20261113`. The fixture customer-plan lifecycle,
  smoke services, API contract, demo seed, trace check, full verification,
  OpenAPI, and Compose checks passed.
- Docker services for that isolated project were stopped after the proof.
  Its project volume/network, built images, `.venv-pr401`, and temporary local
  proof inputs were retained. The existing `davdeploy` stack remained running.
- Docs convention and diff checks are recorded after the final PR revision.

The worktree used a Compose override with unused subnet `10.252.250.0/24` and
alternate local ports because Docker's default network address pools were
exhausted and the main local stack already occupied default ports. No existing
network or volume was changed or deleted.

## Cloud boundary

No AWS or Bedrock calls, infrastructure apply/destroy, deployment, or customer
workload operation was performed for this change. This is source and local
fixture evidence only; hosted CI is tracked on PR #401. It does not establish
hosted Nova execution or full network-topology analysis.

## Remaining policy limits

ACL-to-subnet associations, network ACL rule-number precedence, route tables,
NAT, gateways, VPC endpoints, egress policy, and reachability through complete
VPC topology are not evaluated by this check. The finite list of sensitive
ports is not a complete service or threat model.

## Observed result

The focused suite passed with 159 tests. Full verification passed with 1,102
tests and one existing Starlette/httpx deprecation warning. The clean-room
proof passed against the final null-CIDR adjustment, including local fixture
customer-plan lifecycle, API contract, smoke services, demo seed, trace check,
OpenAPI, and Compose checks. The first final-proof attempt could not create its
network because the previously retained test subnet overlapped; it did not
create a network or start containers. The successful retry used the subnet
recorded above.

## Teardown

The isolated project's containers were stopped. The test-created project
volume, network, image(s), virtual environment, override file, and fixture
state were retained; no deletion was performed. The pre-existing local Compose
stack was left running.

## Final boundary

No AWS infrastructure or customer workload was created, applied, operated,
health-checked, or destroyed. This evidence is local only.
