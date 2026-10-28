# Governed GitHub and customer-cloud integrations

GitHub and AWS are external systems. davdeploy keeps them behind narrow contracts so a web user, CLI, or AI agent never receives broad infrastructure authority.

## GitHub

The production design uses a GitHub App installation, not a personal access token. It can inspect a selected repository, validate signed webhook deliveries, and create a reviewed desired-state pull request with required checks. A protected merge and the runtime reconciler remain separate from the product request.

The local fixture returns repository metadata, validates only a fixture signature, and creates a `fixture-pr://` reference. It cannot contact or write to GitHub.

The local webhook receiver is now implemented as a product contract. It accepts signed fixture events, persists the installation state, records deduplicated delivery IDs, rejects invalid signatures, requires GitHub event/delivery metadata, bounds request bodies to 1 MiB, and exposes revoked, missing-permission, repository-access-change and branch-update states in the UI. This proves the state machine locally. It is not evidence that GitHub has delivered a public webhook to davdeploy.

Approved customer-plan revisions can also create a desired-state PR publication. The package records the approved digest, repository, branch, selected AWS profile, required checks, profile-specific delivery contract and the explicit rule that davdeploy never merges customer code or desired state.

By default this remains a local fixture record. When a GitHub App installation is configured and `DAVDEPLOY_GITHUB_APP_WRITES_ENABLED=true` is explicitly set, the live publisher creates a dedicated `davdeploy/desired-state-<digest>` branch, commits the desired-state package files, opens a pull request to the selected branch and posts an `davdeploy/desired-state-review` status. It does not merge the pull request and does not deploy infrastructure.

## Bring your own AWS account

The production design uses a customer-approved IAM role with OIDC and short-lived STS credentials. The role contract states its audience, maximum session length, and credential boundary. It is not an AWS administrator credential and it is never sent to a browser or agent client.

The local fixture returns an example role ARN and a simulated session reference. It returns no access key, secret key, session token, or live AWS session.

## Current evidence

**Executed locally:** tenant ownership is enforced before repository discovery or a cloud-role contract is shown. Fixture webhook validation, persisted desired-state pull-request publication, role-contract shape, and the no-credentials boundary are unit tested.

**Implemented / unexecuted:** guarded live GitHub desired-state PR publication is implemented and tested with mocked GitHub API calls. A real PR is created only when the GitHub App has write permissions and the explicit reviewed-write environment flag is enabled.

**Not executed:** live webhook delivery, production GitHub PR publication against a customer repository in this PR, AWS OIDC workload deployment, Terraform apply, GitOps publication, and Argo reconciliation.
