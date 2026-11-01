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

PR #218 merged and its CI plus Terraform deployment completed on 2026-11-01.
It was subsequently superseded by PR #219 after the product decision to authorize
all verified `@davdeploy.tech` identities rather than an individual subject allowlist.

## Tests / validation performed

See `docs/test/test218.md`.

## Evidence files produced

`docs/test/test218.md`

## Boundaries

This does not designate an author, create a user, or weaken comment ownership.
It creates only the secure configuration path for a separately verified Cognito subject.

## Follow-up work

None for the retired subject-allowlist path. PR #219 owns the verified-team-email
authorization path.
