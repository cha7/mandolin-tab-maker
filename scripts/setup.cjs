#!/usr/bin/env node
// `npm install` / `npm run setup`: installs uv if it's missing, then the Python
// environment (Python 3.11, PyTorch, Demucs, CREPE, ...) into .venv with `uv sync`.
// The first run downloads several GB. Set MTAB_SKIP_SETUP=1 to skip it on `npm install`.
"use strict";
const { spawnSync } = require("child_process");
const { findUv, runUv } = require("./uv.cjs");

if (process.env.MTAB_SKIP_SETUP === "1") {
  console.log("MTAB_SKIP_SETUP=1: skipping the Python setup.");
  process.exit(0);
}

if (!findUv()) {
  console.log("Installing uv (Python package manager) into your user folder...");
  const r = process.platform === "win32"
    ? spawnSync("powershell", ["-ExecutionPolicy", "ByPass", "-c",
        "irm https://astral.sh/uv/install.ps1 | iex"], { stdio: "inherit" })
    : spawnSync("sh", ["-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
        { stdio: "inherit" });
  if (r.status !== 0 || !findUv()) {
    console.error("Couldn't install uv. Install it by hand: https://docs.astral.sh/uv/");
    process.exit(1);
  }
}

console.log("Installing the Python environment (first time: several GB, a few minutes)...");
process.exit(runUv(["sync"]));
