# Documentation map

The [frontend separation audit](MIGRATION_AUDIT.md) records the ownership and
security boundary with the private `davdeploy-frontend` repository. The
strategic review and scale goal are in
[`docs/strategy/10-scale-and-multi-tenancy.md`](strategy/10-scale-and-multi-tenancy.md).
It describes the long-term millions-customer target without claiming that
current infrastructure already operates at that scale.

Start with the [current-state audit](product/CURRENT_STATE_AUDIT.md), [frontend/API boundary](architecture/frontend-api-boundary.md), [product flow](product/PRODUCT_FLOW.md), [user stories](product/USER_STORIES.md), [plan approval architecture](architecture/PLAN_APPROVAL_ARCHITECTURE.md), [plan lifecycle](architecture/PLAN_LIFECYCLE.md), [approval RBAC](security/APPROVAL_RBAC.md), [minimum-necessary infrastructure](product/minimum-necessary-infrastructure.md), [the planner](architecture/planner.md), [Nova 2 Lite model boundary](architecture/nova-2-lite.md), [same-account pilot boundary](architecture/same-account-pilot.md), [platform runtime readiness](architecture/platform-runtime-readiness.md), [AWS and observability](architecture/AWS_AND_OBSERVABILITY.md), [Day-2 operations](architecture/day2.md), [agent client strategy](product/agent-client-strategy.md), [customer AWS connection](architecture/customer-aws-connection.md), [cloud-pilot design](architecture/cloud-pilot.md), [validation evidence](VALIDATION.md), numbered [customer workload test evidence](test/README.md), and PR-numbered [PR tickets](tickets/README.md).

The active Resend/Cloudflare setup, aliases, secret boundary, testing and provider-change process
are in [email operations](EMAIL_OPERATIONS.md).

The current hosted-control-plane DLQ assessment, incident procedure, recovery-drill boundary, and
customer support handoff are in [operations readiness](OPERATIONS_READINESS.md).

- `product/`: current customer, product, packaging and roadmap material.
- `architecture/`, `security/`, cloud/reliability/GitOps pages: current technical contracts.
- `strategy/`: preserved historical strategy and commercial thinking. It is private and not public-repository material.
- `decisions/`: active architectural decisions, including [provider and private-beta boundaries](decisions/ADR-011-provider-and-private-beta-boundaries.md) and the [separated static frontend](decisions/ADR-012-separated-static-frontend.md).

Every document must clearly say whether a capability is executed locally, simulated, statically validated, planned for a cloud pilot or executed in cloud evidence.

Every PR that performs customer workload testing must also create `docs/test/testN.md`, where `N` is the GitHub PR number. Do not store customer workload run evidence only in `docs/VALIDATION.md`.

Every PR must create a matching `docs/tickets/ticketN.md` file, where `N` is the GitHub PR number. The ticket records the PR goal, current repo state, research, planned work, acceptance criteria, acceptance status, validation, evidence, boundaries, and follow-up work.
