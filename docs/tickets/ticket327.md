# ticket327

PR: #327 (draft)
Branch: `test/public-blog-anonymous-read`

## Problem / goal

Lock down the public blog API boundary with request-level regression tests. Visitors
should be able to read published posts and comments without signing in. Comment
creation/editing and team authoring routes must continue to require authentication.

## Current repo state

- `GET /api/v1/blog/posts`, `GET /api/v1/blog/posts/{slug}`, and
  `GET /api/v1/blog/posts/{slug}/comments` do not declare the token dependency.
- Comment writes, team post listing, and team post writes declare
  `Depends(verify_token)`.
- Existing service tests cover author eligibility and comment/post ownership, but do
  not exercise anonymous HTTP requests against the public read routes.
- API Gateway configuration has explicit unauthenticated routes for only those three
  GET paths; the application routes remain responsible for auth on writes.
- The test avoids entering the application lifespan, guards the global migration and
  session factories, and stubs the edge-origin and Aurora readiness checks. It also
  rejects all `boto3.client` creation, so no configured cloud or database dependency
  can be reached by the HTTP requests.

## Research / references used

- `apps/api/src/davdeploy/main.py` public and team blog routes.
- `tests/test_public_blog.py` existing author and ownership service tests.
- `tests/test_public_blog_edge.py` API Gateway route-boundary assertions.

## Work planned for the PR

Add one request-level regression test that exercises the public and protected HTTP
routes without an authorization header. Keep production behavior unchanged.

## Acceptance criteria

- [x] Anonymous HTTP GET succeeds for published post list, detail, and comments.
- [x] Anonymous comment creation and comment editing are rejected.
- [x] Anonymous team post listing, creation, and editing are rejected.
- [x] Existing route behavior is unchanged.
- [x] Focused local tests pass; CI is rerunning after the final isolation guards.
- [x] No AWS resources or external services are used.

## Acceptance status

Implementation complete. Focused local verification passed. The most recent CI run
passed, but cloud guard stubs were added afterward, so CI is pending for the updated
head.

## Tests / validation performed

- `uv run pytest -q tests/test_public_blog_api_access.py tests/test_public_blog.py tests/test_public_blog_edge.py` — 5 passed.
- `uv run ruff check tests/test_public_blog_api_access.py` — passed.
- Missing required `Authorization` headers currently return HTTP 422 from FastAPI's header validation; they do not reach protected handlers. The test records this current behavior without changing it.
- TestClient does not enter the application lifespan; patched global migration/session factories fail the test if called. The edge-origin and Aurora readiness checks are deterministic local stubs, and `boto3.client` is patched to fail if any cloud call is attempted. The test restores any previous dependency override and closes its temporary session and engine.
- GitHub CI run `41936237791` — all seven checks passed before the final cloud-boundary stubs; current-head CI is pending.

## Evidence files produced

- `docs/test/test327.md`

## Boundaries

This PR adds test coverage only. It does not change blog visibility, authentication,
authorization, content, or infrastructure behavior.

## Follow-up work

No production behavior change was needed. The PR remains open and unmerged. Current-head
CI is pending.
