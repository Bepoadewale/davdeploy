# Email operations

## Purpose and current state

DavDeploy uses two distinct services:

- **Resend** sends transactional product email. The hosted API currently sends workspace
  invitations as `DavDeploy <notify@davdeploy.tech>` and sets Reply-To to
  `support@davdeploy.tech`.
- **Cloudflare Email Routing** receives mail for `davdeploy.tech` and forwards approved aliases to
  external inboxes. It is not an outbound-email provider and does not host a mailbox.

The Resend domain is verified through Cloudflare DNS. The hosted Lambda is configured with
`DAVDEPLOY_EMAIL_PROVIDER=resend`; it retrieves the sending-only key from the Standard SSM
SecureString `/davdeploy/runtime/resend-invitation-api-key`. The key is never committed, passed as
a Terraform value, or placed in a Lambda environment variable.

## Active alias registry

| Alias | Purpose | Cloudflare forwarding destination | Outbound use |
| --- | --- | --- | --- |
| `bepoadewale@davdeploy.tech` | founder correspondence | `bepoadewale1@gmail.com` | founder correspondence through Resend |
| `support@davdeploy.tech` | customer support and public contact | `bepoadewale1@gmail.com` | Reply-To for product messages |
| `notify@davdeploy.tech` | invitations, plan notices and security notices | `bepoadewale1@gmail.com` | active hosted invitation sender |
| `eniolaonipede@davdeploy.tech` | Eniola correspondence | `onipedeeniola126@gmail.com` | Eniola correspondence through Resend |

The Cloudflare catch-all rule is disabled. New aliases must be explicitly added and tested.

## Add an alias safely

1. Decide the alias, receiving inbox, owner, purpose, and reply behavior. Do not use a catch-all.
2. In Cloudflare **Email → Email Routing → Destination addresses**, add the receiving inbox.
   The receiving mailbox owner must click Cloudflare's verification email before it can be used.
3. In **Email → Email Routing → Routing rules**, create an enabled literal `To` rule for the exact
   alias and forward it to the verified destination. Confirm Email Routing reports `ready` and
   `synced`.
4. Send an independent inbound test from a different email account to the alias. Gmail can hide a
   message that it sent to itself and then received through a forward, so do not use the final
   destination inbox as the test sender.
5. Send a direct Resend test from the new `@davdeploy.tech` address to the intended inbox. On the
   verified `davdeploy.tech` domain, Resend can send from an approved local part; do not create a
   new DNS identity for every alias.
6. If replies should return to the alias, make it the Resend `reply_to` address and repeat the
   independent inbound test. Record the result in a PR ticket/test file when product behavior is
   affected.

## Product invitation sender

The deployed invitation path is intentionally narrower than ordinary correspondence:

- Terraform chooses Resend when `resend_invitation_parameter_name` is non-empty; otherwise it can
  use the existing optional SES adapter or remain disabled.
- The protected `terraform-plan` environment supplies only
  `RESEND_INVITATION_PARAMETER_NAME=/davdeploy/runtime/resend-invitation-api-key`.
- The Lambda API role has `ssm:GetParameter` for that exact ARN and no wildcard Parameter Store
  permission.
- Change the product From/Reply-To values only through a reviewed Terraform change, protected
  plan, and saved-plan apply. Do not alter product mail by editing Lambda configuration manually.

Before a new beta cohort, create a controlled workspace invitation, accept it in a browser, and
record the full journey. Delivery confirmation alone does not prove workspace onboarding.

## Rotate or change provider

### Rotate the Resend key

1. Create a replacement sending-only key in Resend.
2. Update the existing SSM parameter value with `aws ssm put-parameter --overwrite`; never place
   the key in GitHub variables, Terraform variables, source, tickets, or logs.
3. Revoke the old Resend key only after a direct send and a hosted invitation test succeed.
4. Record the rotation date and affected operator in the private operations record; do not record
   the key value.

### Use another outbound provider

Keep Cloudflare Email Routing unchanged unless inbound routing is also changing. Add a bounded
backend adapter, tests, provider validation, least-privilege runtime secret access, and a reviewed
Terraform selector. The existing SES adapter is an example, but it is not active. A provider change
requires a protected plan/apply and a controlled direct-send, inbound-reply, and product-invitation
test before production use.

## Troubleshooting

- Confirm the Resend domain is verified and its DNS records remain DNS-only.
- Confirm Cloudflare Email Routing is `enabled`, `ready`, and `synced`; check the exact rule and
  verified destination rather than enabling a catch-all.
- Check both Inbox and Spam. A direct message to the destination distinguishes outbound sender
  delivery from Cloudflare forwarding.
- Test forwarding from a different external account. Gmail deduplicates same-account send/forward
  loops and Cloudflare may display a warning instead of placing a duplicate in the inbox.
- Do not expose the Resend key while diagnosing delivery. The sending-only key cannot query account
  or delivery history; use the Resend dashboard for provider logs when needed.
