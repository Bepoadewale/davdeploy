# Agent Guide

## Mission

Build and maintain **davdeploy**, the private commercial product. Use plain English first. Explain technical terms when they matter to a customer, operator or reviewer.

## Product rules

- AI proposes; typed validation, policy and approved deterministic systems authorize and execute.
- Start every recommendation with the cheapest, simplest option that meets hard requirements. EKS, GPUs, containers and multi-cloud are never defaults.
- Mark fixture inventory and fixture pricing as simulated. Never call an estimate an AWS bill.
- Never give an LLM, customer browser, developer, or agent unrestricted shell, Terraform, Kubernetes, cloud-admin or secret access.
- Keep customer workloads, cloud accounts and data in the customer cloud where possible.
- Preserve public repositories as technical evidence; do not copy private strategy, pricing, buyer research or proprietary ranking logic into them.
- Never commit secrets, private keys, customer data or long-lived cloud credentials.
- Every privileged change needs an attributable actor, immutable plan hash, policy result and audit event.
- Claims must say whether they are executed locally, simulated, planned or roadmap-only.

## Development rules

- Prefer a modular monolith until a real execution need justifies more services.
- Use deterministic fixtures when credentials are unavailable. Label them clearly.
- Keep interfaces provider-neutral, but implement AWS first.
- Use bounded readiness checks, useful failures and project-scoped cleanup.
- Do not push directly to `main`; use a focused branch and reviewable PR.
- **PR-only workflow:** every repository change, including documentation, configuration, tests, and cleanup, must be made on a focused branch and merged through a GitHub pull request. `main` is updated only by merging a reviewed PR after its required checks pass.
- Open a draft PR before substantive implementation whenever GitHub permits it. If GitHub requires an initial commit before it can create the PR, make that smallest possible bootstrap commit, open the draft PR immediately, then add the required PR-numbered ticket before further substantive work.
- Treat a direct commit or push to `main` as a process incident: stop, disclose it in the PR/ticket or appropriate audit record, and do not repeat it. Do not rewrite shared history unless the repository owner explicitly directs it.
- Before merging, confirm the PR has a focused scope, current ticket and evidence, required validation, no unresolved review feedback, and a clean merge state. After merge, delete the branch unless there is a documented operational reason to retain it.

## Customer workload evidence

- Every PR that performs a customer workload test run must have a PR-numbered evidence file under `docs/test/`.
- Use the GitHub PR number as the filename: PR #42 uses `test42.md`, PR #43 uses `test43.md`, and so on.
- If one PR performs multiple customer workload cycles, record all cycles in that one PR-numbered file.
- Do not overwrite, rename, or renumber older test evidence.
- Each file must state whether the run was local, simulated, statically validated, or real AWS execution.
- For real AWS workload runs, record the exact repository, commit, account, region, commands, resources created, observed readiness result, teardown command, absence check, retained resources, and limitations.
- `docs/VALIDATION.md` may summarize multiple runs, but `docs/test/test<PR_NUMBER>.md` is the per-PR customer workload evidence source of truth.

## PR tickets

- Every PR must have a PR-numbered ticket file under `docs/tickets/`.
- Use the GitHub PR number as the filename: PR #42 uses `ticket42.md`, PR #43 uses `ticket43.md`, and so on.
- Create the ticket file before implementation work starts whenever the PR number is already known. If the PR does not exist yet, create the branch, open a draft PR early to get the number, then add the matching ticket before substantive implementation.
- Do not overwrite, rename, or renumber older tickets.
- Each ticket must include the PR goal, current repo state relevant to the PR, research/references, work to be done, acceptance criteria, whether each criterion was met, validation performed, evidence files, boundaries, and follow-up work.
- Keep the ticket updated as implementation changes. Before marking the PR review-ready, update the acceptance status truthfully.

## Validation gate

- Run focused local tests for every runnable change and record the exact commands and results.
- Required GitHub CI is the merge gate for every PR and performs the clean integration proof on a
  fresh GitHub-hosted runner. The `local-e2e` job owns its Compose stack and cleanup.
- Do not start a separate local Compose stack or run `make local-proof` to satisfy a PR integration
  gate. Those targets remain optional developer tools for local troubleshooting.
- If a change needs integration coverage beyond the existing `local-e2e` job, add or extend a
  GitHub Actions job on a fresh runner and make its result part of the PR checks. Satisfy reviewer
  requests for additional integration evidence through GitHub Actions or the relevant hosted
  environment, not by starting a clean-room stack on the developer's machine.
