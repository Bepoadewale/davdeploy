# Private Batch endpoint validation

This root validates one Linux/x86 AWS Batch Fargate job with public-IP
assignment disabled. It creates a fresh two-AZ VPC from the shared VPC module,
which includes one NAT gateway and one public IPv4 address, then adds ECR API,
ECR Docker, CloudWatch Logs, and S3 endpoints. The task security group permits
HTTPS only to the interface endpoint group and S3's endpoint prefix list. The
endpoint group allows TCP/443 only from the Batch task group.

The test image is built locally from `image/Dockerfile`, pushed to the test
repository, then referenced by immutable SHA256 digest. Use two saved plans:
first, a targeted plan that creates only the ECR repository; after review and
explicit cleanup authorization, apply that exact one-resource plan through the
Terraform run monitor, push the image, and record its registry digest. Then
create and inspect the full saved plan, which contains the rest of the VPC,
endpoints, IAM roles, Batch resources, and the exact image digest. Apply only
after the full resource inventory and cleanup scope are approved.

Before applying, verify the caller account is `654654474502`, the region is
`us-east-1`, current prices and quotas, and every resource in the exact saved
plan. The experiment bound is one hour and USD $1.00 estimated spend. The
estimated fixed charges are approximately $0.122/hour: six interface-endpoint
AZ-hours ($0.06), one NAT gateway hour ($0.045), one in-use IPv4 hour ($0.005),
and one 0.25 vCPU/0.5 GiB Fargate job hour ($0.0124). The $1.00 ceiling also
allows bounded data processing, logging, and transfer. It is an estimate, not a
hard AWS spending cap. AWS rounds partial endpoint and NAT hours up.

Do not apply until the exact plan, maximum runtime, cost assumptions, and exact
cleanup authorization are recorded in `docs/test/test517.md`. Use the PID-based
Terraform run monitor for each apply/destroy. On teardown, delete only the
single tagged test image from the exact test repository, then destroy the
reviewed Terraform state. Independently verify the VPC, endpoints, NAT gateway,
public IP, ECR repo, Batch queue/environment, roles, security groups, and log
group are absent. Record AWS-retained inactive job-definition history
separately. Never touch the hosted control plane or its state/lock resources.
