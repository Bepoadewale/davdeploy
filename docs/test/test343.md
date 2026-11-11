# test343 — retain the current customer CloudFormation template

Date: 2026-11-11

Execution type: Read-only AWS object metadata check and local Terraform source
validation. No AWS writes or customer role/resource changes.

Customer repository: Not applicable; this PR changes the DavDeploy Terraform
template-host root.

Commit: Implementation commit pending.

AWS account: `654654474502` (read-only object metadata check only).

AWS region: `us-east-1`.

## Resources created

None. The existing immutable template object was only inspected with
`HeadObject`; no object, bucket, stack, or customer role was created or changed.

## Commands executed

`.venv/bin/python -m pytest -q tests/test_customer_aws_connection_contract.py`
passed (9 tests).

`make terraform-validate` passed for all Terraform roots.

`.venv/bin/python scripts/check_doc_conventions.py` passed.

`git diff --check` passed.

The system `pytest` executable was unavailable; the repository virtualenv
runner was used. Full clean-room verification and final-head CI remain pending.

## Observed result

The live template URL resolves to versioned key
`cloudformation/customer-discovery-role-7e03683a397f0d4e2a5f68b9559d2790ff127e5513540457b47e9c4779b2b793.yaml`.
Read-only metadata reports a 5,401-byte `application/x-yaml` object encrypted
with AES256 and version ID `n2TcoAoYYbzagk4VM5E8ermoFgV5kZsw`. The Terraform
configuration now declares that exact object as retained and moves its
existing current-object state address into the retained map.

## Teardown

None. The existing published object is deliberately retained for customer
stacks and saved setup links.

## Final boundary

This PR prepares a safe state transition only. It does not publish a new
template or update an existing customer role. Any later public-template write
and control-plane URL rollout must be separately planned, reviewed, and
recorded.
