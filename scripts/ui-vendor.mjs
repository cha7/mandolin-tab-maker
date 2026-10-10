#!/usr/bin/env node
// npm run ui:update: copies the installed @cha7/feather-heavy-design-system
// into src/vendor/feather-heavy/, which the app imports from. Vendored so
// that installing this app needs no GitHub Packages token (README: Design);
// only updating it does (`npm run ui:update` installs the latest first).

import { cpSync, existsSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const FROM = path.join(ROOT, "node_modules", "@cha7", "feather-heavy-design-system");
const TO = path.join(ROOT, "src", "vendor", "feather-heavy");

if (!existsSync(FROM)) {
  console.error("@cha7/feather-heavy-design-system isn't installed: run `npm run ui:update` (needs a GitHub Packages token).");
  process.exit(1);
}
rmSync(TO, { recursive: true, force: true });
for (const part of ["css", "react", "browser", "assets", "package.json", "README.md"]) {
  cpSync(path.join(FROM, part), path.join(TO, part), { recursive: true });
}
const { version } = JSON.parse(readFileSync(path.join(FROM, "package.json"), "utf8"));
console.log(`Copied @cha7/feather-heavy-design-system ${version} to src/vendor/feather-heavy/. Look at the app in both themes, then commit it.`);
