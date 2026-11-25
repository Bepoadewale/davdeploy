# Nova catalogue-to-root crosswalk validation

Status: draft implementation package.

The Nova evidence matrix lists 26 architecture modules and 30 Terraform
implementations. Today, those cross-references are descriptive prose and can
drift from the Python catalogues, certification scenarios, or checked-in
Terraform roots.

This package will make the existing crosswalk machine-checkable. It will
validate catalogue and scenario identifiers against their Python sources,
verify every listed Terraform root resolves to a checked-in root, and check
that architecture-to-root and root-to-architecture candidate references agree.

These are evidence and compatibility references only. A passing crosswalk
does not make a root executable, certify a workload, authorize a plan, or
change Nova's dispatch behavior. Unsupported and ambiguous relationships must
remain explicitly unassigned or partial; the validator must not infer them
from matching service names.

## Acceptance

- The matrix has exactly the source-defined architecture catalogue and
  certification scenario identifiers.
- Every implementation registry row resolves to one unique existing Terraform
  root and all documented candidate references point to known identifiers.
- Candidate relationships are symmetric across both matrix sections, with
  ambiguous/partial cases labeled and no runtime dispatch implied.
- AppConfig reflects PR #495's merged lifecycle evidence and verified cleanup.
- Focused tests and current required CI checks pass.
