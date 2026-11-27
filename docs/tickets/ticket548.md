# ticket548 — bind template-host apply to its reviewed saved plan

PR: [#548](https://github.com/Bepoadewale/davdeploy/pull/548) (draft)
Branch: `fix/template-host-saved-plan-20261127`

## Problem / goal

The template-host helper displayed a plan and then accepted `apply`, which ran a
new `terraform apply -auto-approve` from current configuration. The displayed
plan was not bound to the mutation. Require a saved plan and the exact digest
the operator reviewed, and validate its deployment context before Terraform
initializes the backend or applies it.

## Current repo state

- PR #438 merged append-only object addresses and `prevent_destroy`; its
  protected-state plan was taken at commit `5ec154f6…` before PR #399 added the
  Nova apply-role template source.
- The template-host Terraform state remains separate from the serverless
  control-plane root. The existing Terraform plan/apply GitHub Actions workflows
  are hard-coded to the serverless root and are not a template-host entrypoint.
- The local script is the template-host operator entrypoint. This PR changes
  only its saved-plan workflow and documentation/tests. It does not run a plan
  against protected AWS state or apply infrastructure.

## Research / references used

- `AGENTS.md` — PR ticket/evidence rules and required clean-room sequence for
  Terraform execution behavior.
- `docs/architecture/append-only-template-publishing.md` — immutable
  content-addressed object and state-migration design.
- `docs/TERRAFORM_GITHUB_OPERATIONS.md` and
  `.github/workflows/terraform-{plan,apply}.yml` — existing exact saved-plan
  workflow for the separate serverless control-plane root.
- Terraform saved plans retain the planned operations and fail when the state
  snapshot is stale; this PR relies on Terraform's normal saved-plan apply
  behavior after checking a separately reviewed SHA-256 digest.

## Work planned for the PR

- The plan command writes `tfplan` and a manifest below ignored
  `.local/template-host-plans/`, using directory mode `0700` and file mode
  `0600`.
- The manifest binds the saved-plan digest, timestamp, AWS account, region,
  backend bucket/key/lock table, template bucket, Terraform version, Git commit,
  and a fingerprint of Terraform configuration, CloudFormation templates, the
  shell entrypoint, and the manifest verifier itself.
- The apply command requires `apply-saved-plan <directory> <reviewed-sha256>`
  and the existing explicit confirmation variable. It rejects tampering,
  changed context/source, symlinks, incorrect artifact paths, and the old
  unbound `apply` operation before applying the exact saved-plan file.
- Local docs explain how to review and apply that plan. Tests use fake AWS and
  Terraform commands; they do not contact AWS.

## Acceptance criteria

- [x] Apply accepts only a saved plan and a valid reviewed digest.
- [x] Manifest verification binds plan bytes and target/account/backend/source
      context; mismatches fail before Terraform apply.
- [x] Changes to either helper used during apply or manifest verification
      invalidate the reviewed plan.
- [x] Apply passes the exact verified plan file to Terraform and does not
      recompute a plan or use `-auto-approve`.
- [x] Plan artifacts are stored under ignored local storage with restrictive
      permissions and are documented as sensitive; the operator must use an
      encrypted local disk because permissions alone do not encrypt them.
- [x] Mocked runner/manifest tests, focused lint, shell syntax, Terraform
      formatting/validation, and required isolated local clean-room checks pass.
- [ ] Required PR CI and final review pass.
- [x] No AWS plan/apply, Terraform state write, S3 write, or infrastructure
      change was performed.

## Acceptance status

The implementation and local validations are complete on commit
`d2b879811e1dd143597a060154ebae0916d5e058`. Required PR CI and final review
remain open. No AWS plan or apply is claimed.

## Tests / validation performed

See `docs/test/test548.md` for exact commands and outcomes. Full local
clean-room validation ran in a separate uniquely named worktree and Compose
project, then stopped the stack and removed only that test's generated local
environment.

## Evidence files produced

- `docs/tickets/ticket548.md`
- `docs/test/test548.md`
- `docs/architecture/append-only-template-publishing.md`

## Boundaries

- No AWS operations or infrastructure changes were made.
- The PR does not claim that a current protected-state plan or apply has passed.
- The plan artifact remains local and requires encrypted disk storage. This PR
  does not create remote plan storage or a GitHub Actions workflow for this
  separate root.
- The existing destroy operation remains outside this focused change.

## Follow-up work

After this source change is merged, create and review a fresh plan against
current main. Verify the four address moves and the new Nova apply-role object
creation, with no update or delete actions, before any separately authorized
apply. Confirm the published object and resulting Terraform addresses afterward.
