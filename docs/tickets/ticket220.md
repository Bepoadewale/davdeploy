# ticket220 - allow the verified founder Gmail blog author

PR: [#220](https://github.com/Bepoadewale/davdeploy/pull/220)

Branch: `feat/blog-founder-gmail-author`

## Problem / goal

Allow the verified founder account `bepoadewale1@gmail.com` to publish public
DavDeploy blog posts alongside verified `@davdeploy.tech` team email accounts.

## Current repo state

PR #219 authorizes verified `@davdeploy.tech` Cognito ID-token email claims for
blog publishing. The founder signs in with a verified Gmail address instead.

## Research / references used

- Existing Cognito ID-token email and `email_verified` validation.
- The PR #219 team-email authorization and post-ownership tests.

## Work planned for the PR

- Add one exact founder Gmail exception to the verified-author predicate.
- Prove that another Gmail address remains denied.
- Reconcile the historical PR #219 deployment status.

## Work completed

- Added only `bepoadewale1@gmail.com` as an exact, case-normalized verified
  founder exception.
- Preserved the verified `@davdeploy.tech` rule and all ownership checks.
- Added denial coverage for another Gmail address.

## Acceptance criteria

- [x] Verified `bepoadewale1@gmail.com` can publish.
- [x] Other Gmail addresses cannot publish solely because they use Gmail.
- [x] Verified `@davdeploy.tech` identities retain access.
- [x] Unverified email addresses remain denied.
- [x] Full local verification passes: `make verify` reported 316 tests passing.
- [ ] Required CI and hosted deployment pass.

## Acceptance status

Implementation and local verification are complete. CI and the normal saved-plan
deployment remain pending.

## Tests / validation performed

See `docs/test/test220.md`.

## Evidence files produced

`docs/test/test220.md`

## Boundaries

This is one exact verified-email exception. It does not make Gmail accounts,
workspace administrators, or customers generally eligible to publish.

## Follow-up work

Verify `/blog/manage` with the founder Gmail after deployment.
