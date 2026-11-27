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

Secure session persistence currently requires macOS Keychain and Swift. On
other platforms, use an externally provisioned `DAVDEPLOY_TOKEN`; this CLI does
not store credentials in a plain-text file.
