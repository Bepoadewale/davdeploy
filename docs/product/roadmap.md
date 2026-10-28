# Product Roadmap

1. **V1 foundation:** local intent → plan → policy → approval → bounded execution → observation → destruction.
2. **BYOC execution:** scoped AWS role assumption, live inventory and pricing, profile-specific Terraform rendering, GitHub App, desired-state publication and GitOps observation.
3. **AI runtime controls:** metering, release governance, model quality evidence and cost intelligence.
4. **Business controls:** enterprise identity, policy packs, support and commercial packaging.
5. **Provider-by-provider expansion:** only after the AWS path is proven, add a separately
   validated connection, discovery, pricing, policy, planner, rendering, execution, observation,
   recovery, and support path for each additional provider. See the [provider enablement
   gate](../architecture/provider-model.md#provider-enablement-gate).

The local V1, cloud-pilot contracts and future cloud operator workflow are now implemented and statically validated. The next phase is a separately authorised cloud pilot; it must preserve the same evidence boundary.

Not V1: multi-cloud execution, physical GPU fleets, edge fleets, model training, Kafka platform, SCIM or full autonomous remediation.

## Transactional email and onboarding

The verified Resend domain and runtime-only SSM key now enable workspace invitation delivery. The
remaining release evidence is a controlled browser journey covering invitation creation, external
delivery, acceptance, Cognito sign-in, workspace resolution, plan creation, approval, and sign-out.
See [email operations](../EMAIL_OPERATIONS.md) for the active configuration, rotation process and
provider-change requirements. Cognito OTP delivery is a separate Resend custom-sender path with
its own KMS and Lambda boundary; it is not the workspace-invitation sender. A controlled OTP
browser journey remains release evidence. SES remains a fallback configuration, not the active
customer-code delivery path.
