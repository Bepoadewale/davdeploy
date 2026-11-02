# test241 — Events module batch reopen

Date: 2026-11-02

Execution type: Real AWS disposable lifecycle inherited from superseded #236.

Customer repository: None.

Commit: Final PR commit pending.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

Disposable SQS queue/DLQ, EventBridge bus and SNS topic.

## Commands executed

See `docs/test/test236.md`.

## Observed result

Terraform created and destroyed all four disposable resources.

## Teardown

Terraform state was empty after destroy.

## Final boundary

All event-service registry entries remain disabled.
