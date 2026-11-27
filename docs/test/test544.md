# test544 — Specific Nova resource validation feedback

Date: 2026-11-27
Execution type: Hosted plan-only generation failure before CodeBuild

## Baseline evidence

Control-plane commit `f508951645327e0d2b77d0904d17d44a783e1e57` is deployed by
protected plan `45954762410` and exact saved-plan apply `45955715362`. The
control-plane migration passed, all six Lambdas match the versioned release
package, and `/healthz` returned HTTP 200.

One authorized retry of fresh hosted plan-only run
`137ab46f-f5ee-4fa8-80cf-363ffc5f2736` under prompt v8 failed as
`NOVA_GENERATION_FAILED` / `proposal_invalid` after two attempts and one repair.
The bounded diagnostics reported one `value_error` at `resources[*]`; they did
not expose raw validator text or proposal contents. No CodeBuild build, saved
plan, or AWS workload was created. Do not retry this run again.

## PR #544 result

Pending implementation and hosted v9 evidence. No customer workload has been
approved or applied.
