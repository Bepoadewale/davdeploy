/**
 * DavDeploy's intentionally small Cloudflare API edge.
 *
 * The Worker has no customer state. It forwards to the API Gateway origin and
 * overwrites the edge header so browsers cannot forge direct-origin access.
 */
addEventListener('fetch', (event) => event.respondWith(handle(event.request)));

async function handle(request) {
    const inbound = new URL(request.url);
    const upstream = new URL(UPSTREAM_API_ORIGIN);
    upstream.pathname = inbound.pathname;
    upstream.search = inbound.search;

    const headers = new Headers(request.headers);
    headers.delete('x-davdeploy-edge');
    headers.set('x-davdeploy-edge', DAVDEPLOY_EDGE_ORIGIN_TOKEN);
    headers.set('x-forwarded-host', inbound.host);

    const init = { method: request.method, headers, redirect: 'manual' };
    if (!['GET', 'HEAD'].includes(request.method)) init.body = request.body;
    return fetch(new Request(upstream.toString(), init));
}
