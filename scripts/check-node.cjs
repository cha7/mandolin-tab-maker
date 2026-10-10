#!/usr/bin/env node
// Runs before the npm scripts that start Node (package.json "pre..." hooks):
// stops with a clear message when the terminal's Node is older than
// .nvmrc's, instead of an error like "node: bad option: --disable-warning"
// or a syntax error deep in a dependency. Plain CommonJS with no newer
// syntax, so even an old Node can run it.
"use strict";
const fs = require("fs");
const path = require("path");

function requiredMajor(root) {
  try {
    const m = fs.readFileSync(path.join(root, ".nvmrc"), "utf8").match(/(\d+)/);
    if (m) return Number(m[1]);
  } catch (err) {
    // no .nvmrc: fall through
  }
  return 22;
}

function check(version, required) {
  const major = Number(String(version).replace(/^v/, "").split(".")[0]);
  if (major >= required) return null;
  return (
    "This project needs Node " + required + " or newer; this terminal has " + version + ".\n" +
    "  Switch:  nvm use            (reads .nvmrc; nvm install " + required + " if it's missing)\n" +
    "  Always:  nvm alias default " + required
  );
}

module.exports = { check, requiredMajor };

if (require.main === module) {
  const problem = check(process.version, requiredMajor(path.join(__dirname, "..")));
  if (problem) {
    console.error(problem);
    process.exit(1);
  }
}
