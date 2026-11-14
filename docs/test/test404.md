# test404 — EKS managed-node metadata policy

Date: 2026-11-14
Execution type: source-policy tests and isolated local fixture proof
Customer repository: none
Commit: `97a0c7550cb0178caf5eabe6074515c2668566da` (implementation);
`5572fab546e777f4adc38cfad99ede9b0290e89a` (merged main)
AWS account: none
AWS region: none

Status: merged source, locally verified, and all required CI passed. This
change is source policy only; it does not enable or deploy EKS planning or
execution. No AWS resources have been created or changed.

## Scope

The actual-plan policy now requires every planned `aws_eks_node_group` to bind
exactly one `aws_launch_template` present in the same plan. Every reference in
the node group's `launch_template` expression must resolve to that planned
template. The existing EC2 metadata policy then requires `http_tokens =
"required"` for that template. Missing, external, ambiguous, and malformed
bindings fail closed. Configuration lookup includes nested Terraform modules.

The policy does not prove pod-level metadata isolation, Kubernetes RBAC,
cluster endpoint exposure, node IAM least privilege, quotas, or workload
health. The test plan fixtures are synthetic; no customer EKS plan was run.

## Verification

- Focused `tests/test_generated_plan_policy.py`: 182 passed.
- `make verify VENV=.venv-pr399`: 1,127 tests passed; Ruff, Actions
  configuration, OpenAPI, and Compose checks passed. One existing
  Starlette/httpx deprecation warning remains.
- Isolated `make local-proof VENV=.venv-pr399` passed in Compose project
  `davdeploy-pr404-20261114` using API port 18404 and subnet `10.253.12.0/24`.
  Smoke, API/CORS contract, fixture customer-plan lifecycle, demo seed, Tempo
  trace check, and full verification passed. The default Docker address pool
  was exhausted on the first attempt; no existing network was removed, and
  the retry used an unused explicit subnet.
- The PR-specific containers were stopped after proof. The project network,
  PostgreSQL volume, images, `/tmp/davdeploy-pr404-network.yml`, and
  `.venv-pr399` are retained. The pre-existing `davdeploy` stack and all other
  networks/volumes remain untouched.
- Documentation convention and final diff checks pass. All seven required
  final-head GitHub Actions jobs passed for implementation commit `97a0c75` in
  [run `43529880000`](https://github.com/Bepoadewale/davdeploy/actions/runs/43529880000).
- All seven required checks passed for final PR head `199461e` in
  [run `43530471001`](https://github.com/Bepoadewale/davdeploy/actions/runs/43530471001).
- PR #404 merged as `5572fab`; merged-main CI passed all seven jobs in
  [run `43563520542`](https://github.com/Bepoadewale/davdeploy/actions/runs/43563520542).

No AWS/Bedrock calls, deployments, Terraform plans/applies, or workload
mutations occurred.

## Resources created

The isolated Compose proof created the project containers, network, PostgreSQL
volume, and project-specific images for `davdeploy-pr404-20261114`. The
containers were stopped after proof. The project network, volume, images,
`.venv-pr399`, and `/tmp/davdeploy-pr404-network.yml` are retained. The first
attempt built project images but failed before creating the project network,
containers, or volume because Docker's automatic address pool was exhausted;
no existing network or volume was removed.

## Commands executed

- `.venv-pr399/bin/pytest -q tests/test_generated_plan_policy.py`
- `make verify VENV=.venv-pr399`
- Isolated `make local-proof VENV=.venv-pr399` with unique Compose project,
  ports, and subnet `10.253.12.0/24`
- `GITHUB_PR_NUMBER=404 .venv-pr399/bin/python scripts/check_doc_conventions.py`
- `git diff --check`

## Observed result

Focused plan-policy tests passed (182). Full verification passed (1,127 tests),
Ruff, Actions configuration, OpenAPI, and Compose checks passed. The isolated
fixture proof passed smoke, API/CORS contract, customer-plan lifecycle,
seeding, traces, and full verification. Docs convention and diff checks pass.
All seven required final-head GitHub Actions jobs passed for implementation
commit `97a0c75` in run `43529880000`. One existing Starlette/httpx
deprecation warning remains. Final PR-head run `43530471001` and merged-main
run `43563520542` also passed all seven jobs.

## Final boundary

Evidence is source/test only. It does not establish EKS planning or deployment
through DavDeploy, customer workload health, or AWS lifecycle behavior.

## Teardown

Stopped only containers in `davdeploy-pr404-20261114`. Retained its network,
volume, images, override file, and the shared `.venv-pr399`; did not delete any
resources. The pre-existing `davdeploy` stack was untouched.
