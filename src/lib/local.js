// The app downloads whatever link it's given and runs the engine on this
// machine, so it serves this machine only: `npm run dev` / `start` listen on
// 127.0.0.1, and every route calls localOnly() first. The Host check blocks
// DNS rebinding; the Origin check blocks other websites' pages posting to
// localhost.
const LOCAL_HOST = /^(localhost|127\.0\.0\.1)(:\d+)?$/;

// null when the request is allowed, else a Response to return.
export function localOnly(request) {
  const host = request.headers.get("host") ?? "";
  const origin = request.headers.get("origin");
  const ok =
    LOCAL_HOST.test(host) &&
    (request.method === "GET" || request.method === "HEAD" || origin === null || origin === `http://${host}`);
  return ok ? null : Response.json({ error: "forbidden" }, { status: 403 });
}
