# ticket218 - configure the team blog author allowlist through Terraform

PR: [#218](https://github.com/Bepoadewale/davdeploy/pull/218)

Branch: `chore/blog-author-deployment-config`

## Problem / goal

Make team blog publishing configuration reproducible and protected instead of
requiring a direct, untracked Lambda environment edit.

## Current repo state

The blog API safely denies publishing unless a Cognito subject is allowlisted.
The first deployment intentionally had no configured author because no subject
was supplied as Terraform input.

## Research / references used

- Existing Terraform plan workflow environment-variable pattern.
- Blog API author boundary in PR #216.

## Work planned for the PR

- Add a list-valued Terraform input for approved blog author subjects.
- Pass GitHub's protected environment variable into Terraform.
- Pass only the comma-separated subject list into the API Lambda runtime.

## Acceptance criteria

- [x] No subject is committed in source or Terraform state as a literal default.
- [x] An empty allowlist remains fail-closed.
- [x] A protected GitHub environment variable is the production configuration path.
- [x] Full local verification passes; required CI is pending.

## Acceptance status

Implementation and local validation are complete. Required CI and deployment are pending.

## Tests / validation performed

See `docs/test/test218.md`.

## Evidence files produced

`docs/test/test218.md`

## Boundaries

This does not designate an author, create a user, or weaken comment ownership.
It creates only the secure configuration path for a separately verified Cognito subject.

## Follow-up work

Set `DAVDEPLOY_BLOG_AUTHOR_SUBJECTS` in the protected `terraform-plan` GitHub
environment after retrieving the founder's subject from the signed-in workspace profile.
