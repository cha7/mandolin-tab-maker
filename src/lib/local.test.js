import { describe, expect, it } from "vitest";
import { localOnly } from "./local";

const req = (method, headers) => new Request("http://127.0.0.1:8765/api/jobs", { method, headers });

describe("localOnly", () => {
  it("allows this machine's own page", () => {
    expect(localOnly(req("GET", { host: "localhost:8765" }))).toBeNull();
    expect(localOnly(req("POST", { host: "127.0.0.1:8765", origin: "http://127.0.0.1:8765" }))).toBeNull();
    expect(localOnly(req("POST", { host: "localhost:8765" }))).toBeNull(); // curl: no Origin
  });

  it("refuses other host names (DNS rebinding) and other sites' pages", () => {
    expect(localOnly(req("GET", { host: "evil.example" })).status).toBe(403);
    expect(localOnly(req("GET", { host: "localhost.evil.example:8765" })).status).toBe(403);
    expect(localOnly(req("POST", { host: "localhost:8765", origin: "https://evil.example" })).status).toBe(403);
    expect(localOnly(req("POST", { host: "localhost:8765", origin: "http://localhost:9999" })).status).toBe(403);
  });
});
