# Two-User Local Demonstration

The local product demo has separate signed `founder` developer and `administrator` workspace-administrator sign-in choices, dashboard views, a server-side administrator-only pending-approval queue, and persisted customer-plan decisions. This is a local fixture identity flow, not enterprise sign-in.

1. In Browser A, sign in as **developer**, select fixture or authorised read-only GitHub/AWS connections, create one plan, and select **Submit for approval**.
2. In Browser B, sign in as **administrator**, use the review queue filters for pending, approved, rejected or self-approved revisions, open the submitted plan, then approve or reject the exact submitted digest. Rejection requires a reason.
3. Return to Browser A, refresh the dashboard or reopen the revision, and see the persisted result. A draft or rejected plan can create a new immutable draft revision from edited budget, region, environment, data, availability, workload, access and assumption controls.
4. In Browser B, create, submit and approve an administrator-owned plan. Its audit event and decision record identify `is_self_approval: true`.
5. On an approved App Runner revision, select **Create desired-state PR publication**, then sign in as administrator and select **Mark PR checks passed**. In local mode this records the human-review/check state only; with explicit live GitHub write configuration it can open a reviewed GitHub PR. davdeploy still cannot merge GitHub changes.
6. As administrator, select **Generate plan-only Terraform contract**, run **cloud-readiness preflight** with runtime identity enabled for the local fixture, then select **Run plan-only review**. Developer sessions do not see these operator controls. The app records the allowed `terraform init`/`terraform plan` command shape and keeps apply unavailable.
7. On an approved revision, select **Execute local dry run**. The local worker observes READY, FAILED or DEGRADED evidence and displays health, cost and execution state. This does not create AWS resources.
8. For a local dry-run production environment, select **Request/execute local destroy** as an administrator. The app creates a destroy plan, records approval where required, executes the fixture cleanup and observes DESTROYED.

This demo never creates AWS infrastructure. Real GitHub/AWS modes remain explicit opt-in integrations.

The administrator detail view shows requester, repository/branch, AWS target, policy result, Prometheus/Grafana evidence, estimated cost/risk context, exact digest and a clear **approved, not deployed** boundary. After approval, the local dry-run panel shows observed environment health and destroy state. The audit tab shows actor, role, action, digest and rejection reason in an export-ready structure.

To pre-populate a fresh local workspace for a fast walkthrough, run:

```bash
make seed-demo-data
```

It creates a demo AWS fixture connection plus draft, submitted, approved, rejected, administrator self-approved, fixture PR/check-state, App Runner Terraform render, ready preflight, Terraform plan-only review and locally dry-run plan records. It uses only the local API and fixture executor.

## Optional local deterministic proof

GitHub Actions exercises the two-session workflow on a fresh runner as part of
the required `local-e2e` PR check. A separate local Compose stack is not needed
for PR validation. For optional local troubleshooting, the workflow can be
run manually with:

```bash
make local-proof
```

For the individual proof steps after the stack is already running, run:

```bash
make customer-plan-e2e
make seed-demo-data
docker compose restart api
make smoke
make customer-plan-persistence
```

It proves developer submission, developer decision denial, stale-digest rejection, administrator approval, rejection with a reason, immutable revision creation, cross-tenant denial, administrator self-approval, fixture PR publication and reviewed-check recording, App Runner Terraform contract rendering, ready cloud-readiness preflight, Terraform plan-only review, approved-plan local dry-run execution, observed readiness failure, governed local destroy, audit evidence and persistence after the API restarts. The local demo never calls AWS, Terraform apply/destroy, Kubernetes or GitHub writes.

## Connection flow available now

After local sign-in, select the fixture GitHub App installation, an authorized repository, and a branch. The local fixture does not call GitHub; a configured GitHub App runs the same list/inspect calls with a short-lived installation token. A separate reviewed-write flag can create a desired-state PR but never merges it. For AWS, choose an existing tenant-owned target or use **Connect AWS account** to open the customer-owned read-only role setup. The UI shows account, role, region, verification and capability information when available. It never asks for AWS access keys and does not grant deployment permission.
