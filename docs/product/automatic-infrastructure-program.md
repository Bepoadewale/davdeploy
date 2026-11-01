# Automatic infrastructure programme

DavDeploy's customer experience is simple: describe the product, inspect a
plain-English plan and price, then deploy. Customers do not select AWS
services, deployment patterns or internal modules.

The programme below turns the present single-profile AWS planner into a
composed-architecture product. Each PR is deliberately broad, but preserves
the rule that AI proposes while typed policy, bounded modules and approved
execution authorise cloud changes.

| PR | Delivery | Main outcome | Depends on |
| --- | --- | --- | --- |
| #224 | Composed-plan foundation | Typed capability/module graph and dependency-ordered architecture plans | Existing planner |
| #225 | Intent intelligence | Bedrock-backed structured capability extraction, repository signals and reuse of workspace constraints | #224 |
| #226 | Universal application modules | Edge, web, API, identity, secrets, storage and baseline operations modules | #224 |
| #227 | Data and asynchronous modules | Relational/NoSQL data, queues, events, schedules, email and webhook patterns | #224, #226 |
| #228 | Compute execution modules | Lambda, App Runner, ECS and EC2 implementation, outputs, observation, rollback and destroy contracts | #224–#227 |
| #229 | Advanced application modules | AI/RAG, search, real-time, analytics, media and payment/webhook compositions | #224–#227 |
| #230 | Specialised scale modules | Kubernetes, GPU/ML, streaming, hybrid connectivity and multi-region design contracts | #224–#229 |
| #231 | Cost, reliability and operations | Live pricing/quota inputs, health evidence, incident/recovery and cost forecasts | #224–#230 |
| #232 | Commercial launch readiness | Billing provider, entitlements, onboarding, support/status, legal references and launch evidence | #224–#231 |

## Delivery rule

Every module has an explicit lifecycle stage. A module can appear in an
architecture recommendation before it is executable, but it becomes an
automatic deployment option only after its versioned implementation passes
policy, security, cost, observation, rollback/destroy and real-AWS evidence.
This is internal implementation detail: the customer still receives one
complete plan rather than a cloud-service decision tree.

## Customer flow

```text
Describe product → DavDeploy understands requirements → DavDeploy composes
the cheapest viable architecture → customer sees plan, cost and trade-offs
→ customer deploys → DavDeploy observes health and cost
```

Existing workspace facts, including account, budget, region, environment,
availability and data classification, are inputs to this flow. DavDeploy asks
only for a missing business constraint it cannot safely infer; it never asks a
customer to choose an AWS service.

## Programme boundary

No finite catalogue can honestly guarantee every bespoke AWS topology on day
one. The programme targets broad common-product coverage through composable
modules, then adds demand-led modules without changing the customer workflow
or granting arbitrary model-directed cloud access.
