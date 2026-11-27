# test541 — Nova resource ID and health feedback

Date: 2026-11-27
Execution type: Hosted plan-only retry diagnosis and focused local tests
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance input)
Commit: `c714fcb9686653c8e3ee36a334171b9deb4b92f3` (prompt-v5 deployment)
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

No AWS workload resources were created. Nova failed proposal validation before
CodeBuild and produced no plan artifact.

## Commands executed

- Authenticated CLI GET for the existing generated-plan run — read only safe
  diagnostics; raw model output was not accessed.
- Focused tests for generation, run diagnostics, and customer review — 98 passed.
- Ruff, documentation conventions, and `git diff --check` — passed.

## Observed result

The v5 hosted retry returned `NOVA_GENERATION_FAILED` after two attempts and
one repair. Safe diagnostics reported six pattern mismatches on
`resources[*].resource_id` and five on `health_assertions[*]`, with 11,444 input
tokens, 4,236 output tokens, and 15,154 ms latency. Estimated cost was
unavailable. No raw proposal, prompt, plan, or provider response was read.

## Teardown

No workload resources were created; no teardown was required.

## Final boundary

This is failure diagnosis only. Prompt v6 and clearer canonical paths still
need deployed hosted evidence. Do not approve or apply a generated workload.
