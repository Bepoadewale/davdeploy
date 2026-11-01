# ticket219 - authorize blog publishing by verified team email

PR: [#219](https://github.com/Bepoadewale/davdeploy/pull/219)

Branch: `feat/blog-team-email-authors`

## Problem / goal

Allow every authenticated DavDeploy team member with a verified
`@davdeploy.tech` email address to create and edit public blog posts. Customer
workspace roles and non-DavDeploy email domains must not grant publishing access.

## Current repo state

PR #218 supplied a protected Cognito-subject allowlist. The product decision now
uses a verified team email domain instead, so no operator-maintained author list
is required.

## Research / references used

- Cognito ID-token verification already validates the signed `email` and
  `email_verified` claims before a hosted request reaches the product service.
- Existing server-side workspace membership resolution and blog post/comment
  ownership checks.

## Work planned for the PR

- Authorize publishing only from verified `@davdeploy.tech` ID-token claims.
- Remove the retired individual-subject deployment configuration.
- Add authorization, ownership, runtime-claim, Terraform, and documentation
  coverage.

## Work completed

- Carry verified email claims from Cognito's signed ID token into the
  server-resolved request principal.
- Replace the subject allowlist check with a case-insensitive verified
  `@davdeploy.tech` email-domain check.
- Remove the retired Terraform and GitHub Actions author-allowlist configuration.
- Preserve post ownership and comment ownership checks.

## Acceptance criteria

- [x] A verified `@davdeploy.tech` identity can publish.
- [x] A verified external/customer email cannot publish.
- [x] An unverified `@davdeploy.tech` email cannot publish.
- [x] A team member cannot edit another team member's post.
- [x] No individual author subject is required in Terraform or GitHub Actions.
- [x] Full local verification passes: `make verify` reported 316 tests passing.
- [ ] Required CI and hosted deployment pass.

## Acceptance status

Implementation and local verification are complete. CI and the normal saved-plan
deployment remain pending.

## Tests / validation performed

See `docs/test/test219.md`. Focused tests and `make verify` passed locally.

## Evidence files produced

`docs/test/test219.md`

## Boundaries

This changes only blog-author authorization. It does not make workspace roles
publishers, expose customer data, change comment ownership, or modify Cognito
authentication.

## Follow-up work

After deployment, verify the flow in `/blog/manage` with a fresh authenticated
DavDeploy team session.
