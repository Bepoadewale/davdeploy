# Current State Audit

Audit date: 2026-10-28. Branch reviewed: `main` after hosted Lambda/Aurora/Cognito/Resend deployment and the customer-workflow hardening work.

## Current deployment addendum — 2026-11-03

The latest protected Terraform release is plan run [41729846651](https://github.com/Bepoadewale/davdeploy/actions/runs/41729846651)
and apply run [41730396958](https://github.com/Bepoadewale/davdeploy/actions/runs/41730396958)
for commit `2e39e4a45fee9bd69b5827a48431c052e5f772e2`. It changed six Lambda
packages in place, with zero creates and zero destroys. Migration verification
passed, and `https://api.davdeploy.tech/healthz` returned HTTP 200. The hosted
serverless certification control is deployed but remains disabled: its flag is
`false` and its workspace allowlist is empty.

PRs #283–#285 add a persisted certification mode, typed single-module Lambda/API
lifecycle requests, exact artifact and saved-plan chaining, and protected
Terraform inputs. These changes do not enable general customer execution. The
App Runner renderer remains the only generally enabled hosted renderer;
multi-module CodeBuild requests remain rejected. There is no hosted AWS
customer-workload lifecycle evidence for the Lambda/API renderer. The product
cannot yet safely deploy arbitrary compositions from natural language. See
`EXECUTION_READINESS_MATRIX.md` and `COMPOSED_EXECUTION_GOAL.md` for current
capability and remaining work.

## What works today

- A local FastAPI, PostgreSQL, OPA, worker, Prometheus, Grafana and Tempo stack runs with Docker Compose for deterministic development evidence.
- The hosted API runs as AWS Lambda, uses Cognito OIDC/JWKS verification, and persists tenant-scoped records in private encrypted Aurora PostgreSQL through the RDS Data API. Local signed fixture users remain development-only.
- The planner turns a request into typed AWS-oriented candidates, cost ranges, complexity scores and a selected recommendation. It does not default to EKS.
- The product stores projects, intents, cloud connections, plans, approvals, audit events and local execution results.
- A GitHub App reads repository metadata through short-lived installation tokens. Desired-state writes are separately guarded and disabled in ordinary customer operation.
- A customer AWS discovery role has been proven with short-lived STS access. It is read-only and has not deployed a workload.
- The static UI is maintained separately in `davdeploy-frontend` and served at `https://davdeploy.tech`. Exact-origin API CORS, Cognito password-plus-authenticator access, Resend invitation delivery, hosted policy enforcement, and Aurora persistence are live. The hosted service does not accept local fixture sign-in or use SQLite.
- The customer-facing plan flow supports draft, submitted, approved and rejected revisions; administrator rejection reasons; administrator self-approval; editable draft/rejected constraints; review diffs; and a clear approved-not-deployed boundary.
- The local UI has separate developer and administrator fixture sessions, role-aware dashboards, integration selectors, one-plan review, approval queues, audit evidence, local dry-run execution, governed destroy, fixture desired-state PR state, App Runner Terraform contract preview, cloud-readiness preflight and plan-only review records.
- Every customer AWS plan includes mandatory Prometheus-compatible metrics and Amazon Managed Grafana review components with cost assumptions and coverage limitations.

## What is simulated or partial

- Natural-language understanding, pricing and normal inventory are deterministic fixtures.
- Local browser login is a fixture; hosted customers use Cognito password-plus-authenticator access and server-side workspace membership.
- Fixture desired-state PR/check state does not write GitHub, publish checks, or merge code.
- App Runner Terraform rendering and plan-only review records are local governance evidence; they do not run authenticated Terraform or create AWS resources.
- Cloud-readiness preflight is administrator-only local guardrail evidence. The hosted runtime identity is proven for read-only discovery only; it does not prove live reviewed PR/checks, Terraform workload plan/apply, GitOps sync or workload readiness.

## Missing for the developer and administrator journey

1. Hosted customer identity and invitation delivery are connected. Enterprise federation, SSO and broader account lifecycle operations remain follow-up work.
2. Live GitHub public OAuth/install callback and public webhook delivery are not executed; fixture webhooks and read-only installation-token discovery are implemented.
3. Live GitHub desired-state PR writes/checks are not enabled; publication remains fixture-only.
4. The public CloudFormation template host and hosted Lambda control plane are deployed and verified for read-only customer-account discovery. Production identity, policy and durable hosted persistence are present; customer-workload execution is separately disabled.
5. Authenticated Terraform plan-only review has not been executed; apply remains out of scope until separately authorized.
6. Real workload monitoring, actual AWS cost evidence for deployed workloads, GitOps/Argo reconciliation and customer-cloud destroy evidence are not implemented.

## Reuse plan

Reuse the existing organisation checks, signed principal boundary, OPA client, canonical SHA-256 hashing, audit event store, PostgreSQL Compose service, GitHub read-only adapter, AWS STS discovery adapter and planner. Do not reuse the legacy execution-plan self-approval prohibition for customer plan decisions.

## Risks and shortest credible path

Real GitHub writes and real AWS workload execution need customer-controlled external setup and explicit authorisation. The hosted product is stable enough for planning/review and can verify read-only customer discovery. The shortest next path is a recorded human browser journey, recovery evidence, authenticated Terraform plan-only mode, then a separately authorised create → validate → destroy cloud pilot. Approval remains separate from deployment throughout.
