# test395

Test evidence for PR #395.

Date: 2026-11-13
Execution type: Local unit tests and static validation only; no cloud or customer workload
Customer repository: None; this validates Nova proposal contracts.
Commit: Recorded in the PR history.
AWS account: None; no AWS calls were made.
AWS region: None; no AWS calls were made.

## Scope

The health assertion contract now has explicit kinds and bounded fields for
HTTP, TLS, storage, database, queue/event processing, container readiness,
retrieval, inference, network connectivity, and DNS. Each kind is restricted to
compatible declared resource types; event checks bind a declared SQS source to
a Lambda target. It rejects unknown kinds, unsafe HTTP paths, arbitrary
headers, unbounded limits, cleanup opt-outs, and unregistered model fixture
identifiers. Saved-plan manifest versions were incremented because the
canonical proposal serialization changed. The shared proposal contract is now
version 1.1 and the Nova generation prompt version is v4; stale proposal
contract version 1.0 is rejected.

Kubernetes workload readiness is deliberately not accepted yet: the generic
proposal graph currently validates AWS-provider resources only, so it cannot
name and bind a Kubernetes workload for a pod-readiness check. That requirement
remains open until typed Kubernetes resources are part of the shared graph.

All assertions remain proposal-only and are labeled unvalidated/unexecuted.
This PR adds no trusted probe dispatcher, observations, or customer health
evidence.

## Resources created

None.

## Commands executed

- `.venv/bin/python -m pytest tests/test_generated_deployment_contract.py tests/test_generated_plan_artifacts.py tests/test_nova_plan_codebuild.py tests/test_nova_plan_runs.py tests/test_terraform_generation.py tests/test_customer_plan_review.py -q` — 191 passed.
- `make verify` — 1,086 passed; Ruff, OpenAPI snapshot, Actions configuration, and Docker Compose configuration checks passed.
- `.venv/bin/python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.

## Observed result

Focused and full test suites, documentation conventions, and diff checks
passed. One existing Starlette/httpx test-client deprecation warning remains.
Hosted CI and independent review are pending.

## Teardown

No external resources were created, so no teardown was required.

## Final boundary

No live Nova call, AWS API call, health probe, customer plan, apply, recovery,
or destroy was performed. The typed requirements are not workload health
evidence and are not yet executed by the hosted deployment flow.
