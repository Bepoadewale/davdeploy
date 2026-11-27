# Append-only CloudFormation template publishing

**State: source design validated by a lock-free protected-state plan. The first attempt failed on an ambiguous move graph; the corrected plan showed four address moves and zero adds, changes, or destroys. No lock or AWS resource/state was changed, and no apply ran. See [test438](../test/test438.md).**

DavDeploy hosts its public, non-secret customer connection template in a versioned S3 bucket. Setup links and customer CloudFormation stacks can keep using a published URL after a newer template is released, so every published key must remain available and unchanged.

## Publishing model

- Name each object `cloudformation/customer-<template-name>-<sha256>.yaml`, where the digest is computed from the source template bytes. Current examples are `customer-discovery-role` and the default-off `customer-nova-apply-role` template.
- Manage every published key through one `aws_s3_object.published_customer_templates` resource using the object key as the `for_each` key. Terraform therefore gives each object a stable address such as `aws_s3_object.published_customer_templates["cloudformation/customer-nova-apply-role-<digest>.yaml"]`.
- Include each current key from its source map and keep previous keys in the append-only `retained_template_keys` manifest. Before publishing a changed template, add its formerly current key to that manifest in the same source change.
- Set `prevent_destroy = true` on the shared resource so the protection applies at the first creation of every current object as well as to every retained object. Ignore later provider-side object drift; a changed template has a different SHA-256 key and becomes a new instance.
- Keep each output URL pointed at its respective current content-hash key. The S3 bucket name, old keys, and their URLs remain unchanged.

This is Terraform-level deletion protection. It does not protect against an administrator deleting objects outside Terraform, losing Terraform state, or deliberately removing lifecycle protection from source. S3 versioning remains an additional recovery mechanism, not a substitute for the append-only manifest.

## State migration

The existing discovery-template state uses a separate current-object address and a retained-object map. Use static `moved` blocks to move historical `customer_discovery_role`, `active_customer_discovery_role`, and `published_customer_discovery_role` addresses to their original retained-map addresses. Then move each retained-map instance, plus the current `8c5d…` object, to the new key-derived resource addresses. Each `from` address must appear exactly once. These moves change Terraform state addresses only; they must not change S3 keys or object contents. The corrected lock-free template-host plan showed the current discovery object and three retained objects moving addresses, with zero adds, changes, or destroys. The newly introduced Nova apply-role template has no prior managed state address and joins the collection at its content-hash key on first publication. The earlier attempt failed with an ambiguous move graph before Terraform produced a plan. Any apply remains separate and requires explicit approval. Do not apply a plan that proposes replacing an existing key.

After this migration, each release adds the prior current key to the manifest and introduces the new content-hash instance. No move is required for newly published objects because they are created directly at their permanent address. Keep all historical keys in the manifest indefinitely while customer URLs or stacks may depend on them; removal requires a separate explicit retention decision and must not be part of routine publishing.

## Plan review and apply

The template-host root is operated with `scripts/customer-aws-template-host.sh`, separately from the control-plane GitHub Actions workflows. Run `make customer-aws-template-host-plan` to initialize the configured remote state and create a saved plan under `.local/template-host-plans/`. The directory is mode `0700`; the saved plan and manifest are mode `0600`. Review the displayed plan and retain its printed directory and SHA-256 digest.

Apply requires the same exact plan file and the digest recorded at review time:

```sh
CONFIRM_TEMPLATE_HOST_APPLY=APPLY_DAVDEPLOY_TEMPLATE_HOST \
  make customer-aws-template-host-apply \
  PLAN_DIRECTORY=/absolute/path/to/.local/template-host-plans/plan.<id> \
  PLAN_SHA256=<reviewed-plan-sha256>
```

The helper checks the reviewed digest, manifest digest, AWS account, region, state bucket/key/lock table, template bucket, Terraform version, Git commit, and current Terraform/template source fingerprint before initializing the backend. It then applies only that saved plan; it does not regenerate a plan or use `-auto-approve`. Terraform's saved-plan state check rejects a plan if the remote state changed after review. Create and review a new plan after any source, target, or state change. Local saved plans are sensitive artifacts: keep them in the ignored `.local/` directory, use an encrypted local disk, and do not copy them into Git or GitHub artifacts. File permissions restrict access but do not encrypt a plan.

The confirmation variable is an accidental-invocation guard. It does not replace inspection of the displayed plan and supplying the exact printed digest. This local operator path has no GitHub workflow or environment approval; a future remote workflow would need its own isolated plan storage, role, state binding, and approval design.

## Trade-offs

| Choice | Benefit | Cost or limit |
| --- | --- | --- |
| Content-addressed S3 keys | URL and bytes identify one template revision; prior URLs remain stable | Identical template bytes share one key; any edit publishes a new URL |
| Key-derived Terraform `for_each` addresses | New objects are protected from first creation and do not churn addresses on each release | Existing state needs one-time `moved` blocks |
| Append-only manifest plus `prevent_destroy` | Terraform rejects accidental deletion while the resource remains managed | The manifest grows; no automated garbage collection |
| `ignore_changes = all` on immutable objects | Later plans do not rewrite published bytes in place | Correctness depends on the source hash determining the key and on publishing only through this Terraform root |
| S3 versioning | Helps recover an overwritten or deleted object version | The public unversioned URL can still be affected by a delete marker; versioning alone is not retention lock |

## Acceptance criteria

1. Regression tests prove each current template uses its content-hash key in the shared stable-address collection and receives `prevent_destroy` on first creation.
2. Migration blocks cover the existing discovery object and every already-managed retained key without changing any key string; a new template with no prior state is created at its permanent address.
3. Each output URL resolves to its respective current keyed instance; no existing public URL is renamed or redirected.
4. For the one-time migration, a reviewed plan against the protected template-host state shows only the expected address moves and no object create, update, replacement, or deletion. The current migration plan met this criterion with four moves and zero resource changes.
5. Before a later template release, review a separate plan for a changed source file: it must add the new content-hash object, retain every prior key, and propose no prior-object update, replacement, or deletion. This future-publication plan has not been exercised by this change.
6. Any live apply is a separate, explicitly approved operation. Source changes and CI do not constitute deployment evidence.
