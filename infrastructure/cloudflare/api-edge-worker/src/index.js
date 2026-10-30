/**
 * DavDeploy's intentionally small Cloudflare API edge.
 *
 * The Worker has no customer state. It forwards to the API Gateway origin and
 * overwrites the edge header so browsers cannot forge direct-origin access.
 */
export default {
  async fetch(request, env) {
    const inbound = new URL(request.url);
    const upstream = new URL(env.UPSTREAM_API_ORIGIN);
    upstream.pathname = inbound.pathname;
    upstream.search = inbound.search;

    const headers = new Headers(request.headers);
    headers.delete('x-davdeploy-edge');
    headers.set('x-davdeploy-edge', env.DAVDEPLOY_EDGE_ORIGIN_TOKEN);
    headers.set('x-forwarded-host', inbound.host);

    const init = { method: request.method, headers, redirect: 'manual' };
    if (!['GET', 'HEAD'].includes(request.method)) init.body = request.body;
    return fetch(new Request(upstream.toString(), init));
  },
};
