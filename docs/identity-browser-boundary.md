# Identity and browser boundary

Local V1 uses a signed development token. Production uses the `JwksIdentityVerifier` interface with a trusted issuer, exact issuer/audience checks and JWKS signature verification.

The static browser client is owned by the private
`Bepoadewale/davdeploy-frontend` repository. Its OIDC client lists only the
exact redirect and logout URLs for `https://davdeploy.tech`. The same exact
origin is in `DAVDEPLOY_ALLOWED_FRONTEND_ORIGINS`; the technical
`davdeploy-frontend.pages.dev` hostname is deliberately not an authenticated
API origin. Wildcards, URL paths and public HTTP origins fail closed;
localhost HTTP is accepted only for development.

The API uses bearer authorization and does not enable cross-origin credential
cookies. Preview origins are not automatically trusted; each must be explicitly
approved or it cannot read authenticated API responses.

The browser receives an identity token/session only. It does not receive AWS credentials, Kubernetes credentials, Terraform state, GitHub App credentials or secret values.
