import { PHASE_DEVELOPMENT_SERVER } from "next/constants.js";

// The page is a static export that the Python app (mtab/app.py) serves along with its
// API, so running the app needs no Node.js:
// - `npm run build` exports it into mtab/web/ (committed, so people who download the app
//   never build it). Not Next's default out/: that's where the tabs are.
// - `npm run dev` serves it with hot reload on :3000 and forwards /api to the Python app
//   on :8765 (scripts/dev.mjs starts both). Static exports don't allow rewrites, so the
//   dev server isn't one.
// FH_HUE (README: Design): the app's color, 0-359 around the color wheel; empty means the
// design system's forest green. Set in .env (committed, since mtab/web/ is) and fixed at
// build time: npm run build after changing it.
export function readHue(env = process.env) {
  const raw = (env.FH_HUE ?? "").trim();
  if (raw === "") return "";
  if (!/^\d+$/.test(raw) || Number(raw) > 359) throw new Error(`FH_HUE must be a whole number from 0 to 359 (got "${raw}").`);
  return String(Number(raw));
}

export default function nextConfig(phase) {
  const config = {
    // Pin the project root: if a parent folder has a lockfile, Next would treat it as
    // the workspace root.
    turbopack: { root: import.meta.dirname },
    env: { FH_HUE: readHue() },
  };
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return { ...config, rewrites: async () => [{ source: "/api/:path*", destination: "http://127.0.0.1:8765/api/:path*" }] };
  }
  return { ...config, output: "export", distDir: "mtab/web" };
}
