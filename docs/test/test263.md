# test263 — Real site-to-site VPN traffic certification

Date: 2026-11-03

## Scope

Created an isolated Ubuntu StrongSwan customer gateway peer and a separate
workload VPC. The peer fetched its own AWS-generated configuration through a
temporary least-privilege role; no pre-shared key was recorded in this file.

## Evidence

- AWS VPN connection: `vpn-0b0e3b768be90cc05`.
- IKEv2 tunnel `Tunnel1` reached `ESTABLISHED`.
- Protected traffic selectors were `10.250.0.0/16 === 10.240.0.0/16`.
- A probe from `10.250.1.13` to workload `10.240.1.63` received 4 of 4 ICMP
  replies, 0% packet loss, with 1.285–1.885 ms round-trip time.
- StrongSwan recorded 336 encrypted bytes in each direction for the probe.

## Cleanup

The Terraform root is destroyed immediately after recording this evidence.
No customer network, customer credentials, or customer traffic was used.
