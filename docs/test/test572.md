# test572 — GitHub Actions integration proof policy

Date: 2026-11-28

Execution type: Documentation and workflow-instruction review; no application
or cloud execution was performed.

Repository: `Bepoadewale/davdeploy`

Customer repository: Not applicable; this is a documentation-only change.

Commit: Documentation PR #572; no merge/deployment yet.

AWS account: Not applicable; no AWS calls were made.

AWS region: Not applicable.

## Audit results

- The required `local-e2e` job is defined in `.github/workflows/ci.yml`, runs
  on `ubuntu-latest`, bootstraps the Compose test stack, executes readiness,
  API contract, demo, customer-plan E2E, persistence, trace and full verification
  steps, and invokes `make clean-local` in an always-run cleanup step.
- Manual local-cycle wording was found in the contributor/agent gate, PR
  template, definition of done, daily Codex task, flagship evolution strategy,
  README, and demo guide.
- Those active instructions now require GitHub Actions proof or describe local
  stack commands as optional developer troubleshooting tools.
- Historical evidence in `docs/test/` and historical PR tickets is not an
  active instruction and remains unchanged.
- The workflow file and its cleanup step are unchanged.

## Resources created

None. No Docker containers, networks, volumes, AWS resources, GitHub
deployments, or Terraform operations were created.

## Commands executed

- Read-only repository searches for clean-room and `local-proof` instructions.
- Read the `local-e2e` job, contributor guide, pull request template, README,
  and related development guidance.
- `GITHUB_PR_NUMBER=572 python3 scripts/check_doc_conventions.py` and
  `git diff --check`: passed.
- GitHub Actions PR CI: pending.

## Observed result

The repository already has a blocking fresh-runner GitHub Actions integration
job. This PR makes that job the required proof and clearly labels local Compose
commands as optional developer tooling.

## Teardown

No resources were created; no teardown was needed.

## Final boundary

This change affects contributor validation instructions only. It does not
change the `local-e2e` job, hosted control plane, Terraform, customer resources,
or Nova acceptance status.
