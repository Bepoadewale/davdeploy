# ticket317 Bind Nova plans to trusted resource ownership

PR: draft, assigned PR number 317
Branch: `feat/nova-ownership-tags-317`

## Goal

Bind each generated Terraform plan to server-owned organization, workspace,
project, environment and plan identity. Require supported AWS resources to carry
those immutable ownership markers, and fail closed when plan evidence is missing,
unknown or mismatched. Preserve safe typed references within one proposal.

## Current repository state

Backend main is `c2c6279` (PR #315). The Nova plan runner currently injects the
trusted AWS account guard and region. The generated-plan policy verifies the
resource inventory, region and account guard, but does not verify resource
ownership tags. Typed references are already constrained to declared resources,
acyclic dependencies and declared provider outputs with matching type and
sensitivity.

## Research / references

- Terraform AWS provider default tags: https://registry.terraform.io/providers/hashicorp/aws/latest/docs#default_tags-configuration-block
- AWS resource tagging overview: https://docs.aws.amazon.com/tag-editor/latest/userguide/tagging.html
- Local implementation: `generated_terraform_plan.py`,
  `generated_plan_policy.py`, `generated_provider_validation.py`, and
  `generated_deployment_contract.py`.

## Work planned

- Pass a validated immutable server-owned ownership scope to the plan runner;
  Nova cannot choose or override it.
- Inject fixed ownership tags into trusted AWS provider configuration.
- Use the pinned provider schema and actual plan values to require exact known
  ownership tags for supported managed resources; fail closed where support or
  resulting values cannot be proven.
- Keep safe same-plan typed references working and test external, undeclared,
  wrong-type, sensitive, and cyclic references remain rejected.
- Document any resource types that cannot yet establish ownership evidence.

## Acceptance criteria

- [ ] Trusted organization/workspace/project/environment/plan scope is validated
  and cannot be supplied or changed by Nova.
- [ ] The runner injects deterministic ownership tags from trusted scope only.
- [ ] Supported resources with absent, unknown, or mismatched ownership tags are
  denied; unsupported tagging is not silently accepted.
- [ ] Safe same-plan references continue to validate, while invalid references
  fail closed.
- [ ] Focused tests and documentation convention checks pass.
- [ ] No AWS resources are created or changed; no apply/destroy path is added.
- [ ] Required GitHub CI passes; PR is left ready for review, not merged.

## Validation

Not run yet. This initial ticket/test commit contains no application changes.

## Evidence

- `docs/test/test317.md` will record focused local test results and boundaries.

## Boundaries and follow-up

This PR strengthens source-only plan generation/review. It does not deploy the
Nova runner to the hosted worker, authorize apply, or prove AWS tagging behavior
through a live resource lifecycle. Hosted execution and service-specific
ownership behavior remain follow-up work.
