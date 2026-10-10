#!/usr/bin/env node
// npm run dev: the page with hot reload on http://localhost:3000 (next dev), and the
// Python app on :8765 for its API (mtab app --dev, which accepts the dev page's
// requests). next.config.mjs forwards /api from one to the other. Ctrl+C stops both.
import { spawn } from "node:child_process";
import path from "node:path";

const ROOT = path.join(import.meta.dirname, "..");
const procs = [
  spawn(process.execPath, [path.join(ROOT, "scripts", "uv.cjs"), "run", "mtab", "app", "--no-browser", "--dev"], { cwd: ROOT, stdio: "inherit" }),
  spawn(process.execPath, [path.join(ROOT, "node_modules", "next", "dist", "bin", "next"), "dev", "--hostname", "127.0.0.1", "--port", "3000"], {
    cwd: ROOT,
    stdio: "inherit",
  }),
];
const stop = (code) => {
  for (const p of procs) if (p.exitCode === null) p.kill();
  process.exit(code ?? 0);
};
for (const p of procs) p.on("exit", (code) => stop(code));
process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));
