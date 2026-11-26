# ECS Express plan-pricing contract

## Objective

Price the exact ECS Express pilot from its actual Terraform plan and a
digest-bound trusted usage profile. ECS Express has no separate orchestration
fee, but the plan hides many supporting resources behind one service resource.
Pricing must account for those resources or keep the plan incomplete.

## Supported shape

The first price profile is limited to the one-service pilot in
`infrastructure/terraform/customer-workload-ecs-express-pilot`: one
256-millicore, 512-MiB Fargate task target; one private, same-region ECR image;
one three-day Standard log group; a new two-AZ public VPC; and one ECS Express
service. A fresh VPC means one Application Load Balancer is not shared with
another service. Any second service, shared VPC/load balancer, unsupported
resource, or unknown price-bearing value keeps pricing incomplete.

## Billable coverage

| Driver | Usage quantity bound to the persisted customer revision | Price source |
| --- | --- | --- |
| Fargate CPU and memory | Task starts and average billed seconds per task, including image-pull time and the one-minute minimum | AWS Price List, Linux/x86 Fargate vCPU-hour and GB-hour |
| Application Load Balancer | Billed ALB hours, rounded up, and monthly LCU-hours | AWS Price List, `AWSELB` Application Load Balancer hour and LCU-hour products |
| Public IPv4 | Separate task and load-balancer address-seconds, including the 60-second minimum | AWS Price List, in-use public IPv4 address-hour product |
| CloudWatch Logs | Ingested GB and retained GB-month for the exact log group | AWS Price List, Standard log ingestion and storage products |
| Deployment alarm | One standard-resolution metric alarm created by Express Mode | AWS Price List, standard alarm metric-month product |
| ECR storage | Stored GB-month for the exact private ECR repository | Existing ECR storage assumptions and price line, counted once |
| Internet egress | Total bounded outbound GB from the service VPC | Existing AWS outbound data-transfer product |
| Cross-AZ transfer | Bounded bytes transferred between ALB nodes and Fargate tasks across AZs | Existing regional data-transfer product |

The exact pilot creates a VPC, subnets, an internet gateway, routes,
associations, IAM roles and service-linked roles, an ACM certificate, and ECS
orchestration resources. These have no direct hourly charge under the cited
AWS pricing guidance; their billable companions above remain separately
priced. AWS native ECR basic scanning is included at no additional charge.
Enhanced scanning,
other ECR features, NAT gateways, endpoints, extra load balancers, or other
unmodeled services are unsupported and must prevent complete pricing.

## Trusted assumptions and limits

Usage assumptions must come from the integrity-checked persisted customer
revision, not from Nova output or plan text. They are included in the pricing
context digest and evidence manifest. Each quantity has a minimum and maximum;
prices, SKUs, and rate values always come from the regional AWS Price List.

Task runtime and start counts include canary deployments and replacement tasks.
Task public-IPv4 duration must cover the full billed task runtime, including the
one-minute minimum; load-balancer public IPv4 bounds must cover both subnet AZs
for every bounded ALB hour.
The load balancer's public IPv4 and LCU usage can vary with traffic and AWS
scaling, so those quantities require explicit upper bounds. Missing or stale
assumptions keep pricing `INCOMPLETE`. A usage estimate is not an AWS-enforced
spending limit; approval must not present it as a guaranteed maximum bill.

The ALB's processed-byte LCU charge and AWS data transfer charges can apply to
the same requests. Both are included because they represent different billable
services. ECR storage and log usage are priced only once through their existing
resource-address mappings.

## Evidence and rejection behavior

Each accepted line records the exact planned address, quantity range, USD
unit-rate range, catalog SKU, catalog product digest, effective date, and
publication time. Evidence also binds to the exact plan digest and trusted
pricing-context digest. Unsupported sharing, extra services, resource/address
mismatch, unknown prices, expired catalog evidence, invalid assumptions, or
any material unpriced usage produces `INCOMPLETE` or `UNAVAILABLE` pricing.

The model does not approve or execute plans and does not change the hosted
control plane. The renderer remains default-off. Exact-plan policy review and
pricing remain separate approval gates.

## Sources

- [ECS Express resources and sharing](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html)
- [ECS Express pricing overview](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)
- [Amazon ECS pricing](https://aws.amazon.com/ecs/pricing/)
- [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/)
- [Application Load Balancer pricing](https://aws.amazon.com/elasticloadbalancing/pricing/)
- [Public IPv4 pricing](https://aws.amazon.com/vpc/pricing/)
- [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)
- [ECR basic scanning pricing](https://aws.amazon.com/about-aws/whats-new/2024/08/new-version-amazon-ecr-basic-scanning/)
- [ECR data transfer pricing](https://aws.amazon.com/ecr/pricing/)
- [AWS data-transfer billing categories](https://docs.aws.amazon.com/cur/latest/userguide/cur-data-transfers-charges.html)
