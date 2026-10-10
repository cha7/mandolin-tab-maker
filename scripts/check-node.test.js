import { describe, it, expect } from "vitest";
import { createRequire } from "node:module";

const { check } = createRequire(import.meta.url)("./check-node.cjs");

describe("check-node", () => {
  it("passes the required major or newer, and explains anything older", () => {
    expect(check("v22.21.1", 22)).toBeNull();
    expect(check("v24.0.0", 22)).toBeNull();
    expect(check("v18.17.1", 22)).toMatch(/needs Node 22 or newer; this terminal has v18\.17\.1[\s\S]*nvm use/);
  });
});
