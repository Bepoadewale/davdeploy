# ticket262 — Real Bedrock Knowledge Base retrieval certification

PR: [#262](https://github.com/Bepoadewale/davdeploy/pull/262)

Branch: `test/real-bedrock-knowledge-base`

## Problem / goal

Certify an AWS Bedrock Knowledge Base using an owned OpenSearch Serverless
vector collection, a synthetic document, real ingestion and a real retrieval
query, followed by verified teardown.

## Current repo state

The repository has a Knowledge Base Terraform resource but no vector collection
module, index creation workflow, data source ingestion or retrieval evidence.

## Research / references used

- AWS Bedrock Knowledge Base vector-store prerequisites and field mappings.
- AWS OpenSearch Serverless data-access and network-policy documentation.

## Work planned for the PR

- Add a policy-scoped OpenSearch Serverless vector collection module.
- Add an opt-in disposable root and signed index/data-source/retrieval runner.
- Execute the real lifecycle and record all evidence and absence checks.

## Acceptance criteria

- [ ] Collection, index, Knowledge Base and S3 data source are created with least-privilege roles.
- [ ] A synthetic document is ingested and retrievable through Bedrock.
- [ ] Temporary resources are destroyed and checked absent.

## Acceptance status

In progress.

## Tests / validation performed

Bootstrap only.

## Evidence files produced

Pending `docs/test/test262.md`.

## Boundaries

The collection must be temporary, tagged and accessible only under explicit
disposable-certification opt-in. No customer data, credentials or collection is
used.

## Follow-up work

Private networking, customer data sources and non-default embedding dimensions
need module-specific certification beyond this isolated baseline.
