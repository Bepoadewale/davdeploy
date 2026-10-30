# DavDeploy API edge Worker

This Free-plan Worker is the public API endpoint at `https://api.davdeploy.tech`.
It forwards only to the fixed API Gateway origin and injects a secret header.
The Lambda verifies the same value from a SecureString SSM parameter, so a
direct API Gateway request cannot access the application once the guard is on.

## Safe rollout

1. Generate a random value locally; never commit or echo it.
2. Create or update `/davdeploy/runtime/edge-origin-token` as an SSM
   `SecureString` and set the protected GitHub environment variable
   `DAVDEPLOY_EDGE_ORIGIN_TOKEN_PARAMETER_NAME` to that parameter name.
3. Deploy this Worker, then upload the same value with `wrangler secret put
   DAVDEPLOY_EDGE_ORIGIN_TOKEN`.
4. Deploy the backend Terraform change, then deploy the frontend with
   `VITE_API_BASE_URL=https://api.davdeploy.tech`.
5. Verify an authenticated request through `api.davdeploy.tech` works and the
   direct `execute-api` endpoint returns 403. Do not log either secret.

The Worker preserves browser `Origin` and API authorization headers. API CORS
continues to allow only the configured DavDeploy frontend origin.

## Free edge rules

The zone has three narrow Free-plan protections, managed outside this repository:

- block common probe paths (`/.env`, `/.git/config`, `/wp-login.php`, `/xmlrpc.php`);
- block methods other than GET, POST, PUT, PATCH, DELETE, and OPTIONS on
  `api.davdeploy.tech`;
- block an IP after more than 20 API requests in 10 seconds at a Cloudflare
  colocation, for 10 seconds.

The application and API Gateway limits remain stricter controls for sensitive
operations. Cloudflare's Free rate limiter only supports the short 10-second
period above, so this is a burst guard rather than the authoritative limiter.
