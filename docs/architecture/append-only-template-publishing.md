# Append-only CloudFormation template publishing

**State: source design validated by a lock-free protected-state plan. The first attempt failed on an ambiguous move graph; the corrected plan showed four address moves and zero adds, changes, or destroys. No lock or AWS resource/state was changed, and no apply ran. See [test438](../test/test438.md).**

DavDeploy hosts its public, non-secret customer connection template in a versioned S3 bucket. Setup links and customer CloudFormation stacks can keep using a published URL after a newer template is released, so every published key must remain available and unchanged.

## Publishing model

- Name each object `cloudformation/customer-discovery-role-<sha256>.yaml`, where the digest is computed from the source template bytes.
- Manage every published key through one `aws_s3_object.published_customer_templates` resource using the object key as the `for_each` key. Terraform therefore gives that object a stable address such as `aws_s3_object.published_customer_templates["cloudformation/customer-discovery-role-<digest>.yaml"]`.
- Include the current key automatically and keep previous keys in the append-only `retained_template_keys` manifest. Before publishing a changed template, add the formerly current key to that manifest in the same source change.
- Set `prevent_destroy = true` on the shared resource so the protection applies at the first creation of each current object as well as to every retained object. Ignore later provider-side object drift; a changed template has a different SHA-256 key and becomes a new instance.
- Keep the output URL pointed at the current content hash. The S3 bucket name, old keys, and their URLs remain unchanged.

This is Terraform-level deletion protection. It does not protect against an administrator deleting objects outside Terraform, losing Terraform state, or deliberately removing lifecycle protection from source. S3 versioning remains an additional recovery mechanism, not a substitute for the append-only manifest.

## State migration

The existing state uses a separate current-object address and a retained-object map. Use static `moved` blocks to move historical `customer_discovery_role`, `active_customer_discovery_role`, and `published_customer_discovery_role` addresses to their original retained-map addresses. Then move each retained-map instance, plus the current `8c5d…` object, to the new key-derived resource addresses. Each `from` address must appear exactly once. These moves change Terraform state addresses only; they must not change S3 keys or object contents. The corrected lock-free template-host plan showed the current object and three retained objects moving addresses, with zero adds, changes, or destroys. The earlier attempt failed with an ambiguous move graph before Terraform produced a plan. Any apply remains separate and requires explicit approval. Do not apply a plan that proposes replacing an existing key.

After this migration, each release adds the prior current key to the manifest and introduces the new content-hash instance. No move is required for newly published objects because they are created directly at their permanent address. Keep all historical keys in the manifest indefinitely while customer URLs or stacks may depend on them; removal requires a separate explicit retention decision and must not be part of routine publishing.

## Trade-offs

| Choice | Benefit | Cost or limit |
| --- | --- | --- |
| Content-addressed S3 keys | URL and bytes identify one template revision; prior URLs remain stable | Identical template bytes share one key; any edit publishes a new URL |
| Key-derived Terraform `for_each` addresses | New objects are protected from first creation and do not churn addresses on each release | Existing state needs one-time `moved` blocks |
| Append-only manifest plus `prevent_destroy` | Terraform rejects accidental deletion while the resource remains managed | The manifest grows; no automated garbage collection |
| `ignore_changes = all` on immutable objects | Later plans do not rewrite published bytes in place | Correctness depends on the source hash determining the key and on publishing only through this Terraform root |
| S3 versioning | Helps recover an overwritten or deleted object version | The public unversioned URL can still be affected by a delete marker; versioning alone is not retention lock |

## Acceptance criteria

1. A regression test proves the content-hash key, stable key-derived address, append-only manifest, and `prevent_destroy` are present on the resource that creates new objects.
2. Migration blocks cover the current object and every already-managed retained key without changing any key string.
3. The output URL resolves to the current keyed instance; no existing public URL is renamed or redirected.
4. Terraform format and validation pass, and a reviewed plan against the protected template-host state shows state moves plus only the expected new object, with no existing-object update, replacement, or deletion.
5. Any live apply is a separate, explicitly approved operation. Source changes and CI do not constitute deployment evidence.
