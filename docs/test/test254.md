# test254 — Real ACM and SES DNS validation certification

Date: 2026-11-02

Execution type: Controlled disposable AWS DNS validation.

Customer repository: None.

Commit: `21a9aeb` plus evidence update in progress.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

An ACM certificate and SES domain identity for
`certemaildns20261102a.cert.davdeploy.tech`.

## Commands executed

Terraform monitor apply/destroy commands were run against
`infrastructure/terraform/module-validation/email-dns`; Cloudflare DNS API
created and then removed the ACM, SES, DKIM and MAIL FROM records.

## Observed result

ACM reached `ISSUED`; SES identity and DKIM both reached `Success`.

## Teardown

Terraform recorded `Destroy complete! Resources: 4 destroyed.` Cloudflare DNS
record absence was checked after deletion.

## Final boundary

This validates DNS ownership only; it does not send customer email.
