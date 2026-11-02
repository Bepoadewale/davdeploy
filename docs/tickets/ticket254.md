# ticket254 — Real ACM and SES DNS validation certification

PR: Pending creation.

Branch: `test/real-email-dns-workload`

## Problem / goal

Prove that ACM and SES DNS validation work under a temporary owned
`davdeploy.tech` subdomain, rather than treating resource creation as proof.

## Current repo state

The foundation validation root creates a certificate for an unresolvable
`.invalid` domain and does not exercise SES validation.

## Research / references used

AWS ACM DNS validation, Amazon SES domain identity/DKIM validation and
Cloudflare DNS API documentation.

## Work planned for the PR

Create disposable ACM and SES domain identities, publish their exact DNS
validation records through Cloudflare, observe verified AWS state, then remove
the AWS identities and temporary DNS records.

## Acceptance criteria

- [ ] ACM reaches `ISSUED`.
- [ ] SES identity and DKIM verification are confirmed.
- [ ] AWS resources and temporary DNS records are removed.

## Acceptance status

In progress.

## Tests / validation performed

Pending controlled AWS execution.

## Evidence files produced

`docs/test/test254.md`

## Boundaries

This validates domain ownership and provider DNS integration. It does not send
customer email or alter the production Resend mail configuration.

## Follow-up work

Run a disposable application email send and receipt test without using
production addresses.
