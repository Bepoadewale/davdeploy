# Definition of Done

A change is done only when it is useful, testable, documented in plain English and truthful about evidence.

- [ ] Typed inputs and outputs are validated.
- [ ] Tenant, role, policy and approval boundaries are tested where relevant.
- [ ] No privileged action comes from raw LLM output.
- [ ] Status is observed independently, not assumed from a command response.
- [ ] Failure and destroy paths are designed and tested where relevant.
- [ ] Tests, lint and applicable smoke checks pass in GitHub Actions or the relevant hosted
      environment.
- [ ] Documentation distinguishes executed, simulated and planned behavior.
- [ ] No secrets or customer data are committed.
- [ ] Required GitHub Actions checks, including fresh-runner `local-e2e` for runnable milestones,
      pass.
