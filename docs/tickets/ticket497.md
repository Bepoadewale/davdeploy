# ticket497 — clarify the gated Nova plan-only path

PR: [#497 — docs: correct Nova plan-runner status](https://github.com/Bepoadewale/davdeploy/pull/497)

Branch: `docs/nova-plan-status-496`.

## Problem / goal

The Nova execution handoff says `NovaTerraformGenerator` is not connected to
hosted CodeBuild, while source contains a gated durable worker that generates
a typed proposal, stages its exact request, and starts the fixed plan-only
CodeBuild project. Keep the distinction clear between source integration,
runtime enablement, and verified customer evidence.

## Current repo state

- Backend `main` is `2dec62484f3c7ec52859dab23c0b4b37acf9f45e` (PR #494), a
  documentation reconciliation through code PR #493.
- The last recorded hosted release is PR #420. This documentation update does
  not inspect or change the hosted control plane.
- `ProductService.request_generated_plan_run` validates the submitted
  revision and target, then queues durable work.
- `ProductService._prepare_generated_plan_run` generates the typed proposal,
  stages the exact input, and starts the configured dispatcher.
- `NovaPlanOnlyDispatcher.from_environment` fails closed unless
  `DAVDEPLOY_NOVA_PLAN_RUNNER_READY=true` and its required settings are present.
- Terraform variable `enable_nova_plan_only_runner` defaults to `false`.
- The current handoff has no verified authenticated customer request with a
  recorded hosted plan. No customer workload or deployment is claimed.

## Research / references used

- `apps/api/src/davdeploy/service.py`
- `apps/api/src/davdeploy/nova_plan_dispatch.py`
- `apps/api/src/davdeploy/nova_plan_codebuild.py`
- `infrastructure/terraform/serverless-control-plane/variables.tf`
- `docs/product/NOVA_EXECUTION_ADR.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`

## Work planned for the PR

1. Correct the claim that the typed Nova generator is not connected to
   CodeBuild in source.
2. State that this is a gated plan-only path and that Terraform's runner
   feature variable defaults to false.
3. Keep runtime enablement, authenticated hosted-plan evidence, and full
   composed application lifecycle as separate unproven gates.
4. Make no infrastructure or control-plane changes.

## Acceptance criteria

- [x] The ADR describes the source-level worker-to-CodeBuild plan-only path
  without claiming live enablement or customer use.
- [x] The composed goal no longer says the generator is disconnected from
  CodeBuild; it preserves the missing authenticated-plan and application
  lifecycle evidence.
- [x] No customer plan, apply, health, or certification is claimed.
- [x] No AWS, hosted control-plane, remote-state, lock, or local protected
  resource is changed.
- [x] Documentation conventions and diff checks pass.
- [x] All seven required PR checks passed on source/document commit
  `173de80f8e863a06c1caa44f438a03d97c206757` (run `45538195845`). The
  ticket-only follow-up must still pass final-head CI before merge.

## Acceptance status

The active checklist distinguishes source-level plan-only CodeBuild
integration from live runtime enablement and a verified authenticated
customer plan. Seven required checks passed for the implementation commit. The
final PR head will include this evidence update and must pass CI before merge.

## Tests / validation performed

Documentation-only change; no application tests or cloud operations are
required.

- `GITHUB_PR_NUMBER=497 python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- Required PR CI run `45538195845` on commit
  `173de80f8e863a06c1caa44f438a03d97c206757`: all seven checks passed.

## Evidence files produced

- `docs/product/NOVA_EXECUTION_ADR.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/tickets/ticket497.md`

## Boundaries

- No AWS or hosted control-plane read/write was performed for this change.
- No Terraform operation, apply, or destroy was run.
- Preserve all protected untracked files and existing audit evidence.

## Follow-up work

Record a real authenticated hosted plan request only after the user and
deployment boundaries permit that test. Full hosted plan/apply/lifecycle,
multi-module execution, and scenario certification remain separate gates.
