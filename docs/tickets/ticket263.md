# ticket263 — Real site-to-site VPN traffic certification

PR: [#263](https://github.com/Bepoadewale/davdeploy/pull/263)

Branch: `test/real-vpn-traffic`

## Problem / goal

Replace the existing documentation-range VPN lifecycle evidence with a real
temporary peer, established tunnel and routed traffic probe.

## Current repo state

The current root uses TEST-NET-2 and cannot prove encryption or routing.

## Research / references used

AWS Site-to-Site VPN static-route and customer-gateway configuration guidance.

## Work planned for the PR

Create a disposable EC2 StrongSwan peer, AWS VPN gateway, scoped routes and
two probe instances; exchange real traffic through the tunnel and destroy all
temporary resources.

## Acceptance criteria

- [x] Both tunnel and routed probe evidence is recorded.
- [ ] All created resources are tagged and destroyed.

## Acceptance status

Traffic evidence is complete; cleanup is in progress.

## Tests / validation performed

Real IKEv2 establishment and a four-packet routed ICMP probe succeeded.

## Evidence files produced

`docs/test/test263.md`.

## Boundaries

No customer network, account or traffic is used. This is a temporary dedicated
test topology only.

## Follow-up work

Customer BGP, Transit Gateway and private-network variants need separate
certification.
