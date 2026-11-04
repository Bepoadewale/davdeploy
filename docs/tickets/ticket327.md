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
- [x] Focused local tests and required CI pass.
- [x] No AWS resources or external services are used.

## Acceptance status

Implementation complete. Focused local verification passed, and required GitHub CI
run `41933204103` passed all seven checks.

## Tests / validation performed

- `uv run pytest -q tests/test_public_blog_api_access.py tests/test_public_blog.py tests/test_public_blog_edge.py` — 5 passed.
- `uv run ruff check tests/test_public_blog_api_access.py` — passed.
- Missing required `Authorization` headers currently return HTTP 422 from FastAPI's header validation; they do not reach protected handlers. The test records this current behavior without changing it.
- GitHub CI run `41933204103` — all required checks passed.

## Evidence files produced

- `docs/test/test327.md`

## Boundaries

This PR adds test coverage only. It does not change blog visibility, authentication,
authorization, content, or infrastructure behavior.

## Follow-up work

No behavior change was needed. The PR is ready for review and remains a draft; it has
not been merged.
