# test262 — Real Bedrock Knowledge Base retrieval certification

Date: 2026-11-03

Execution type: Controlled disposable AWS execution with real ingestion, retrieval and teardown.

Customer repository: None.

Commit: `d706f41` plus evidence update in progress.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

Tagged OpenSearch Serverless vector collection `3fmg4zw2vl9ba0gc72aj`, vector
index `bedrock-kb-index`, private S3 source bucket, scoped Bedrock role,
Knowledge Base `YG5EQAYWXR`, and S3 data source `HNZNJDBNAY`.

## Commands executed

The Terraform PID monitor created and destroyed the isolated root. AWS CLI
created the FAISS 1024-dimension index, started ingestion job `OUFEYYKA7V`,
waited for its COMPLETE status, and called `bedrock-agent-runtime retrieve`.

## Observed result

The ingestion job indexed one synthetic document with zero failures. A real
retrieve call returned the exact text `DavDeploy certification document:
retrieval evidence confirms this exact synthetic phrase.` with its S3 source
URI and score `0.761705`.

## Teardown

Run `cert-knowledge-base-destroy-20261103a` completed with `11 destroyed`.

## Final boundary

`get-knowledge-base` returned not found after destroy and
`batch-get-collection` returned an empty collection list. The public network
policy was limited to this disposable certification collection only; production
private-network collection validation remains separate work.
