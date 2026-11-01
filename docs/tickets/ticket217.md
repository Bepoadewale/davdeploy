# ticket217 - expose public blog reads through the API edge

PR: [#217](https://github.com/Bepoadewale/davdeploy/pull/217)

Branch: `fix/public-blog-api-routes`

## Problem / goal

Allow public visitors to read published blog posts and comments through the
protected API edge while retaining JWT authentication for every write.

## Current repo state

The merged blog API correctly permits public reads at the application layer,
but API Gateway's authenticated `$default` route rejected those reads before
they reached the Lambda.

## Research / references used

- Existing explicit health, sensitive, preflight, and authenticated API Gateway routes.
- Production `401` response from `GET /api/v1/blog/posts` through `api.davdeploy.tech`.

## Work planned for the PR

- Add only the three public GET blog routes as explicit unauthenticated API Gateway routes.
- Preserve the JWT-protected default route for comments and team publishing.
- Add route-boundary coverage.

## Acceptance criteria

- [x] Published posts and comments are publicly readable through the edge.
- [x] No post creation, comment creation/editing, or author route bypasses JWT.
- [x] Full local verification passes; required CI is pending.

## Acceptance status

Implementation and local verification are complete. Required CI and deployment are pending.

## Tests / validation performed

See `docs/test/test217.md`.

## Evidence files produced

`docs/test/test217.md`

## Boundaries

This changes API Gateway route matching only. It does not add public writes,
relax the Lambda origin guard, or change Cognito authorization.

## Follow-up work

Run the saved-plan deployment, then confirm public reads return an empty list
until a team author publishes the first article.
