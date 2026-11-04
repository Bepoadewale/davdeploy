# Ticket 327: Cover anonymous public blog reads

PR: #327 (draft)
Branch: `test/public-blog-anonymous-read`

## Goal

Lock down the public blog API boundary with request-level regression tests. Visitors
should be able to read published posts and comments without signing in. Comment
creation/editing and team authoring routes must continue to require authentication.

## Current repository state

- `GET /api/v1/blog/posts`, `GET /api/v1/blog/posts/{slug}`, and
  `GET /api/v1/blog/posts/{slug}/comments` do not declare the token dependency.
- Comment writes, team post listing, and team post writes declare
  `Depends(verify_token)`.
- Existing service tests cover author eligibility and comment/post ownership, but do
  not exercise anonymous HTTP requests against the public read routes.
- API Gateway configuration has explicit unauthenticated routes for only those three
  GET paths; the application routes remain responsible for auth on writes.

## Research / references

- `apps/api/src/davdeploy/main.py` public and team blog routes.
- `tests/test_public_blog.py` existing author and ownership service tests.
- `tests/test_public_blog_edge.py` API Gateway route-boundary assertions.

## Work and acceptance criteria

- [ ] Anonymous HTTP GET succeeds for published post list, detail, and comments.
- [ ] Anonymous comment creation and comment editing return unauthorized.
- [ ] Anonymous team post listing, creation, and editing return unauthorized.
- [ ] Existing route behavior is unchanged unless a regression test proves otherwise.
- [ ] Focused local tests and required CI pass.
- [ ] No AWS resources or external services are used.

## Validation performed

Pending implementation.

## Evidence

- `docs/test/test327.md`

## Boundaries

This PR adds test coverage only. It does not change blog visibility, authentication,
authorization, content, or infrastructure behavior.

## Follow-up

None unless a regression test reveals that the documented public/private route split
is not implemented.
