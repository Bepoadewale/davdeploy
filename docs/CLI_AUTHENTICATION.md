# DavDeploy CLI authentication

The CLI authenticates a human workspace user with the configured Cognito
user-pool client, requires the user's authenticator-app code, verifies the
identity against the DavDeploy API, and stores the resulting session in macOS
Keychain. Passwords, authenticator codes and bearer tokens are never accepted
as command-line arguments or printed. AWS operator credentials remain separate
from DavDeploy workspace authorization.

## Sign in

Set the hosted API URL and run the login command from an interactive terminal:

```sh
export DAVDEPLOY_API_URL=https://api.davdeploy.tech
davdeploy auth login --username you@example.com
```

The CLI asks for the password and current authenticator-app code using hidden
prompts. It verifies the identity through `GET /api/v1/me` before storing the
session. The default Cognito region and public app-client ID target DavDeploy's
hosted control plane; `DAVDEPLOY_COGNITO_REGION` and
`DAVDEPLOY_COGNITO_CLIENT_ID` can override them.

After sign-in, normal governed CLI commands use the Keychain session
automatically when they target the same API URL used at sign-in. The CLI refuses
to send the saved token to a different API. It refreshes the short-lived
identity token before a request when needed. Cognito refresh tokens expire; run
`davdeploy auth login` again after the configured refresh period. The existing `--token` and
`DAVDEPLOY_TOKEN` overrides remain available for automation. Do not put tokens
in shell history, repository files, issue text or logs.

## Review and approve an exact generated plan

Use the artifact identifier to retrieve the safe review summary, then approve
only the manifest digest shown for that artifact:

```sh
davdeploy get-generated-plan-artifact --artifact-id ARTIFACT_ID
davdeploy approve-generated-plan \\
  --artifact-id ARTIFACT_ID \\
  --manifest-sha256 MANIFEST_SHA256
```

The review endpoint returns plan summaries and evidence, not saved-plan bytes
or sensitive state. Approval is bound to the immutable manifest digest. DavDeploy
rechecks the artifact's target, proposal, configuration, provider schema,
policy, saved-plan and regional pricing evidence; this command does not apply
infrastructure. Apply remains a separate authorized action with its own gates.

Secure session persistence currently requires macOS Keychain and Swift. On
other platforms, use an externally provisioned `DAVDEPLOY_TOKEN`; this CLI does
not store credentials in a plain-text file.
