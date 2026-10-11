import { describe, expect, it } from "vitest";
import { readHue } from "./next.config.mjs";

describe("readHue (next.config.mjs)", () => {
  it("passes a hue through, and none for unset or empty", () => {
    expect(readHue({ FH_HUE: " 245 " })).toBe("245");
    expect(readHue({ FH_HUE: "0" })).toBe("0");
    expect(readHue({ FH_HUE: "" })).toBe("");
    expect(readHue({})).toBe("");
  });

  it("refuses anything but 0-359, so a typo fails the build", () => {
    for (const bad of ["360", "-10", "blue", "12.5"]) expect(() => readHue({ FH_HUE: bad })).toThrow(/FH_HUE/);
  });
});
