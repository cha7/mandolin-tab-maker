import { describe, expect, it } from "vitest";
import { movedText, parseTab, stage, visibleSections } from "./tab";

const TAB = `Old tune  (D major, 4/4)
G|---|

bars 1-4  [confidence: high, medium]
A|-0-2-|

bars 5-8  [confidence: low]
A|-5-|

bars 9-12  [confidence: rest]
A|---|

bars 13-16  [confidence: low, low]
A|-7-|

bars 17-20  [confidence: medium]
A|-2-|`;

describe("tab", () => {
  it("splits tab.txt into its header and rated sections", () => {
    const { head, sections } = parseTab(TAB);
    expect(head).toBe("Old tune  (D major, 4/4)\nG|---|");
    expect(sections.map((s) => [s.first, s.last, s.label])).toEqual([
      [1, 4, "high"], [5, 8, "low"], [9, 12, "rest"], [13, 16, "low"], [17, 20, "medium"],
    ]);
    expect(sections[0].body).toBe("A|-0-2-|");
  });

  it("hides sections that aren't confident, counting the low ones", () => {
    const { sections } = parseTab(TAB);
    const rows = visibleSections(sections, "confident");
    expect(rows.map((r) => r.hidden ?? r.first)).toEqual([1, 2, 17]);
    expect(visibleSections(sections, "all")).toHaveLength(5);
  });

  it("says how the tab moved and which step is running", () => {
    expect(movedText(0, "D")).toBe("as recorded");
    expect(movedText(12, "D")).toBe("up 1 octave");
    expect(movedText(-24, "D")).toBe("down 2 octaves");
    expect(movedText(-3, "F")).toBe("from F (-3)");
    expect(stage(["[1] audio: x", "[2] separating stems"])).toBe("Separating instruments (the slow step)");
    expect(stage([])).toBe("Working");
  });
});
