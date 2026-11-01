# ticket216 - add public blog and discussion API

PR: [#216](https://github.com/Bepoadewale/davdeploy/pull/216)

Branch: `feat/public-blog`

## Problem / goal

Provide a secure first-party API for public DavDeploy articles and signed-in
discussion without turning customer workspace administrators into public-site publishers.

## Current repo state

The control plane already has durable PostgreSQL models, authenticated actor
attribution, audit events, and role-bound tenant APIs. It had no public editorial
content or discussion domain.

## Research / references used

- Existing PostgreSQL migration, audit, identity, and tenant-authorization patterns.
- Existing public Cloudflare edge and frontend API boundary.

## Work planned for the PR

- Add durable posts and comments plus migration 22.
- Expose public read-only routes for published posts and their comments.
- Require an explicit `DAVDEPLOY_BLOG_AUTHOR_SUBJECTS` allowlist for post creation
  and editing.
- Let signed-in readers create comments and edit only their own comments.
- Record all write actions in the existing audit trail and update OpenAPI.

## Acceptance criteria

- [x] Published articles and comments can be read without a workspace account.
- [x] Drafts are not exposed by public routes.
- [x] A customer workspace administrator cannot publish unless explicitly allowlisted.
- [x] A commenter cannot edit someone else's comment.
- [x] A team author cannot edit another author's post.
- [x] Full local verification passes; required CI is pending.

## Acceptance status

The API and clean local verification are complete. Required GitHub CI and a
reviewed production Terraform apply remain pending.

## Tests / validation performed

See `docs/test/test216.md`.

## Evidence files produced

`docs/test/test216.md`

## Boundaries

No public anonymous writes, HTML rendering, file uploads, email notifications,
or moderation automation are introduced. The initial author allowlist is
deliberate configuration, not a customer workspace role.

## Follow-up work

Configure the verified team Cognito subjects in the protected deployment input,
then perform one controlled publication and comment journey.
