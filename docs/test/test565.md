# test565 — Nova plan-runner failure-code baseline

## Test type

Real hosted AWS **plan-only** run; no workload apply was attempted.

## Environment

- Repository: `Bepoadewale/davdeploy`
- Source/deployed control-plane commit: `a5d38166bbc30942ac4ea82622712221446e1343`
- AWS account: `654654474502`
- Region: `us-east-1`
- Architecture plan: `539f558d-16cf-4359-921a-9205a7e81bfe`
- Review-only revision: `f017ecba-22c2-4a01-9074-8632b505839c`
- Generated plan run: `5a917d8b-93ba-4a85-8d7e-258e0b753ebe`
- CodeBuild build: `davdeploy-nova-plan-only:68cd98fd-633a-4e8d-9bda-750a6ab6dd7f`

## Commands and observations

- Protected Terraform plan `46124569024` for the exact merge commit succeeded;
  exact saved-plan apply `46125147226` succeeded and migrations completed.
- The deployed release package hash matched all six control-plane Lambda
  hashes. Public `/healthz` returned HTTP 200. The selected administrator CLI
  session remained valid without a new authenticator challenge.
- Authenticated read-only checks confirmed the test connection's verified
  setup, the unapproved source plan, and the previous terminal v25 run.
- A new review-only revision was created and submitted with the same content
  digest; its decision remained null and its execution boundary remained
  `UNEXECUTED_APPROVAL_ONLY`.
- One authenticated `POST /api/v1/customer-plan-revisions/<revision>/generated-plan-runs`
  request returned HTTP 202. The run reached CodeBuild and ended
  `FAILED` / `CODEBUILD_FAILED`.
- The CodeBuild `BUILD` phase failed with `COMMAND_EXECUTION_ERROR`; the runner
  emitted only its generic fail-closed message. The API returned no artifact
  and the generic fixed error summary. No raw model proposal or plan was
  retrieved.

## Result and resource boundary

No saved-plan artifact was recorded, and the plan-only run cannot apply or
destroy resources. No workload resource creation was observed; no teardown was
needed. The architecture plan remains unapproved. Preserve the failed run as
audit evidence and do not retry it.

This baseline does not prove that the v26 proposal was plan-valid, that a
customer workload was deployed, or that any create/invoke/update/recovery/
destroy lifecycle succeeded. The next run must use a fresh review-only
revision after the diagnostic PR is merged and deployed.
