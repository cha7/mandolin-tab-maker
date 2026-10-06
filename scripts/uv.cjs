#!/usr/bin/env node
// Runs uv (the Python package manager this project uses) with the given arguments, from
// the repo root. Finds uv on PATH or where its installer puts it, so npm scripts work
// even when ~/.local/bin isn't on PATH yet. `npm install` installs uv if it's missing.
"use strict";
const { spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const EXE = process.platform === "win32" ? "uv.exe" : "uv";

function findUv() {
  const candidates = [
    process.env.UV,
    EXE, // on PATH
    path.join(os.homedir(), ".local", "bin", EXE),
    path.join(os.homedir(), ".cargo", "bin", EXE),
  ].filter(Boolean);
  for (const c of candidates) {
    if (c !== EXE && !fs.existsSync(c)) continue;
    const r = spawnSync(c, ["--version"], { stdio: "ignore" });
    if (r.status === 0) return c;
  }
  return null;
}

function runUv(args) {
  const uv = findUv();
  if (!uv) {
    console.error("uv isn't installed. Run `npm install` (or `npm run setup`) first.");
    return 1;
  }
  const r = spawnSync(uv, args, { cwd: ROOT, stdio: "inherit" });
  if (r.error) {
    console.error(r.error.message);
    return 1;
  }
  return r.status === null ? 1 : r.status;
}

module.exports = { findUv, runUv, ROOT };

if (require.main === module) {
  process.exit(runUv(process.argv.slice(2)));
}
