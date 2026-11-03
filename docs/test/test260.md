# test260 — Public multi-region DNS failover certification

Date: 2026-11-03

Execution type: Controlled disposable AWS and DNS validation.

Customer repository: None.

Commit: `bc84e9b` plus evidence update in progress.

AWS account: `654654474502`.

AWS region: `us-east-1` and `us-west-2`.

## Resources created

A temporary delegated Route 53 child zone, primary us-east-1 and secondary
us-west-2 S3 website health endpoints, health check and failover CNAME records.

## Commands executed

Terraform run monitor applied and destroyed the public-failover root. Cloudflare
API temporarily delegated the child zone. `dig @1.1.1.1` observed public DNS;
Route 53 health-check status and direct S3 endpoint probes verified health.

## Observed result

The delegated hostname initially resolved to the primary S3 website and Route
53 reported HTTP 200. After deletion of only the temporary primary health
object, Route 53 reported HTTP 404 and public DNS switched to the secondary
us-west-2 website, which served `secondary-healthy`.

## Teardown

Terraform recorded `Destroy complete! Resources: 13 destroyed.` The temporary
Cloudflare NS delegation was deleted and its absence was verified.

## Final boundary

This uses public S3 website origins solely for test health endpoints; customer
delivery should use private origins and an appropriate edge layer.
