## What changed

## Evidence

- [ ] Tests/lint pass.
- [ ] Claims are labelled executed, simulated or planned.
- [ ] No secret, customer or private strategy data was added.
- [ ] Focused validation is recorded; GitHub Actions provides the fresh-runner integration proof.

## Cloud evidence (only if a cloud pilot was authorised)

- [ ] Terraform plan, apply, smoke, security/failure proof, observability, Cost Explorer query, destroy and absence evidence are linked.
- [ ] The AWS account, region, tags and exact Terraform state scope are recorded.
- [ ] This PR does not call planned/static cloud work “executed.”

## Security review

- [ ] No raw LLM output gains execution authority.
- [ ] Tenant, policy, approval and audit effects were considered.
