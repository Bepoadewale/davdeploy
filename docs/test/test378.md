# test378 — deploy Nova intent scope guard

- Date: 2026-11-12
- Execution type: Protected control-plane Terraform saved-plan apply and read-only post-release verification
- Customer repository: N/A; no customer repository or workload was used
- Backend source: `40439ab6b493a40c522102fa88de1c48043b4177` (PR #377 merge)
- Commit: `40439ab6b493a40c522102fa88de1c48043b4177`
- Terraform root: `infrastructure/terraform/serverless-control-plane`
- AWS account: `654654474502`
- AWS region: `us-east-1`

## Purpose

Deploy PR #377's typed Nova intent scope classification. The deployed API
rejects unrelated requests with a fixed HTTP 422 explanation before creating a
workload intent. This keeps DavDeploy focused on software infrastructure; it
does not make Nova a general question-answering assistant. Deploying a
financial-domain application remains in scope.

## Protected plan and apply

- Merged-main CI [43190545115](https://github.com/Bepoadewale/davdeploy/actions/runs/43190545115)
  passed all seven jobs for source commit `40439ab6b493a40c522102fa88de1c48043b4177`.
- Documentation/status reconciliation PR #378 passed all seven required checks
  in run [43200068425](https://github.com/Bepoadewale/davdeploy/actions/runs/43200068425)
  on evidence head `d9ab36d`.
- Final PR head `642dc18c0f2722ed6decc8339d58465287ee812c` passed all seven
  required checks in run
  [43200776989](https://github.com/Bepoadewale/davdeploy/actions/runs/43200776989).
- The final documentation reconciliation head
  `1d3a8e3c6d210424f1dd2c1a6764bba28df6d3dd` passed all seven required checks
  in run [43201578281](https://github.com/Bepoadewale/davdeploy/actions/runs/43201578281).
- Protected plan [43191437865](https://github.com/Bepoadewale/davdeploy/actions/runs/43191437865)
  completed successfully for that exact source and AWS account.
- The sanitized plan summary was complete/applyable with no errors: 0
  additions, 6 in-place Lambda package updates, 0 destroys/replacements, 0
  drift, and 8 output changes. The six Lambda functions were the only changed
  resources.
- Exact saved-plan apply [43192601048](https://github.com/Bepoadewale/davdeploy/actions/runs/43192601048)
  completed successfully as GitHub deployment `7733504560`. It verified the
  saved-plan manifest and digest; Terraform reported 0 added, 6 changed, and 0
  destroyed. Database migrations completed successfully.

## Commands executed

- `gh run watch 43190545115 --interval 120 --exit-status --compact` — all
  seven merged-main CI jobs passed.
- `gh run watch 43191437865 --interval 300 --exit-status --compact` — protected
  Terraform plan passed for the exact merged source.
- `gh run watch 43192601048 --interval 300 --exit-status --compact` — exact
  saved-plan apply passed after the standing user authorization was used to
  approve the GitHub `terraform-apply` environment gate.
- Read-only AWS account identity, Lambda configuration/package state, selected
  runtime feature flags, and API health checks.
- No raw Terraform plan/state values were printed or stored locally.

## Post-release observations

- AWS caller identity: `654654474502`.
- All six control-plane Lambdas are `Active` with `LastUpdateStatus=Successful`
  and common `CodeSha256=/q4CbzB47savx6EUbTIWj4ASIao3eCdNDKSbfbkkBEg=`.
- `https://api.davdeploy.tech/healthz` returned HTTP 200 with
  `{"status":"ok","product":"davdeploy"}`.
- The deployed API reports plan runner, credential broker, plan reviews,
  Terraform state API, and hosted certification disabled; only plan-role
  trust/account verification is enabled.
- Synthetic model-classification evidence for stock advice and a
  stockbroking-app deployment is recorded in `docs/test/test377.md`. This
  release did not make an authenticated customer intent request, so it does
  not establish the full customer UI/API experience or classification quality.

## Resources created

Terraform created no AWS resources. It updated six existing control-plane
Lambda packages in place. No customer role, plan, workload, or customer
infrastructure was created or changed.

## Observed result

The protected release completed successfully, all six Lambda package updates
are active, database migrations passed, and the API health endpoint returned
HTTP 200. PR #377's scope guard is in the deployed API source. The plan worker,
credential broker, plan reviews, Terraform state API, and hosted certification
remain disabled.

## Teardown

No teardown applies. This control-plane release created no disposable or
customer workload resources.

## Final boundary

An out-of-scope result is a typed model classification, not authorization or a
security approval. It can be wrong; infrastructure requests still require the
separate deterministic schema, plan policy, pricing, approval, and execution
gates. No Nova-generated customer plan has been applied, operated,
health-checked, recovered, or destroyed.
