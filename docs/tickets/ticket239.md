# ticket239 — Delivery module batch reopen

PR: [#239](https://github.com/Bepoadewale/davdeploy/pull/239)

## Goal

Merge the delivery module batch after GitHub automatically closed dependent
draft #234 when its stacked base #233 merged.

## Acceptance criteria

- [x] S3, ECR, Lambda and HTTP API reusable modules are included.
- [x] Real disposable AWS evidence is retained in `docs/test/test239.md`.
- [x] CloudFront remains disabled pending origin-specific lifecycle validation.

## Boundaries

No customer workload is enabled by this PR.
