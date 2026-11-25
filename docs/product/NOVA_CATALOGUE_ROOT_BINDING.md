# Nova catalogue-to-root crosswalk validation

Status: implemented in draft PR #506; final CI and merge are pending.

The Nova evidence matrix lists 26 architecture modules and 30 Terraform
implementations. Today, those cross-references are descriptive prose and can
drift from the Python catalogues, certification scenarios, or checked-in
Terraform roots.

This package will make the existing crosswalk machine-checkable. It will
validate catalogue and scenario identifiers against their Python sources,
verify every listed Terraform root resolves to a checked-in root, and check
that architecture-to-root and root-to-architecture candidate references agree.
The 30 implementation IDs are the workload-root registry; four additional
Terraform module directories are shared or plan-only components and are
classified below instead of being silently omitted.

These are evidence and compatibility references only. A passing crosswalk
does not make a root executable, certify a workload, authorize a plan, or
change Nova's dispatch behavior. Unsupported and ambiguous relationships must
remain explicitly unassigned or partial; the validator must not infer them
from matching service names.

## Terraform module directories outside the workload registry

These directories are checked separately because they are consumed as shared
components or represent plan-only contracts rather than standalone workload
roots.

| Module path | Reason for exclusion from the 30 workload roots |
|---|---|
| `modules/app-runner-plan-contract` | Plan-only typed App Runner contract used by the renderer; it does not create AWS resources. |
| `modules/iam` | Shared pilot IAM component used by `infrastructure/terraform/pilot`. |
| `modules/opensearch-serverless-vector` | Reusable vector collection component used by the knowledge-base validation stack, not a standalone workload root. |
| `modules/rds` | Shared pilot PostgreSQL component; the workload registry separately tracks `modules/aurora-postgres`. |

## Acceptance

- The matrix has exactly the source-defined architecture catalogue and
  certification scenario identifiers.
- Every implementation registry row resolves to one unique existing Terraform
  root and all documented candidate references point to known identifiers.
- Candidate relationships are symmetric across both matrix sections, with
  ambiguous/partial cases labeled and no runtime dispatch implied.
- AppConfig reflects PR #495's merged lifecycle evidence and verified cleanup.
- Focused tests and current required CI checks pass.
