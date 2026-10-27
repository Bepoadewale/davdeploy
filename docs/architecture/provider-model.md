# Provider Model

davdeploy plans in capabilities first and maps them to a cloud provider second. The current executable catalogue is AWS-only. Other clouds are future adapters, not supported execution targets.

The provider boundary covers:

- identity and short-lived access;
- inventory discovery and approved regions;
- compute, serverless, containers, Kubernetes, and accelerators;
- databases, storage, queues, secrets, networking, and load balancing;
- pricing, execution, observation, and destroy.

The local `CloudDiscovery` interface is deliberately narrow. Its AWS fixture returns approved regions and reusable-resource names without credentials or network access. A future AWS adapter must assume a customer-scoped role with short-lived credentials. Azure, GCP, OCI, DigitalOcean, and Huawei adapters are roadmap-only.

Single-provider designs are the default. Multi-cloud is a future capability only when a real requirement outweighs extra networking, identity, egress, observability, and recovery complexity.

## Provider enablement gate

A provider is not enabled by adding it to a browser selector. Before DavDeploy marks Azure, Google
Cloud, OCI, DigitalOcean, or another provider as available, that provider must have all of the
following:

1. A tenant-scoped connection contract and provider-native short-lived identity method. The browser
   must never receive or store provider credentials.
2. Read-only discovery, account/project/subscription validation, approved-region or zone discovery,
   and a durable, provenance-marked inventory snapshot.
3. Timestamped pricing evidence, quota and availability checks, plus provider-specific policy
   controls.
4. Capability mappings from the provider-neutral workload model to validated provider resources;
   no AWS architecture name or cost estimate may be relabelled as another provider.
5. Provider-specific Terraform/OpenTofu rendering, plan review, exact approval binding, bounded
   apply/destroy, and trusted observed-output ingestion.
6. Provider-aware audit events, support runbooks, alerting, recovery evidence, data-deletion
   handling, and customer-facing status copy.

The current APIs, schema, planner, pricing/discovery adapters, plan-review kind, Terraform
renderer, and execution workflow are AWS-specific. The visible Azure, Google Cloud, and other
provider choices in the browser are intentionally informational until this gate is complete for
each provider.
