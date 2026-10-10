// Reading the engine's tab.txt and report for the page (mtab/render.py writes
// the tab: a header, then one block per 4-bar section, blank-line separated).

const SECTION = /^bars (\d+)-(\d+)\s+\[confidence: ([^\]]+)\]/;

// tab.txt -> { head, sections: [{ first, last, label, body }] }; label is the
// section's best rating: high, medium, low, or rest (no melody).
export function parseTab(text) {
  const parts = String(text).split("\n\n");
  const head = parts.shift() ?? "";
  const sections = [];
  for (const p of parts) {
    const lines = p.split("\n").filter((l) => l.length);
    const m = lines[0]?.match(SECTION);
    if (!m) continue;
    const labels = m[3].split(", ");
    const label = ["high", "medium", "low"].find((l) => labels.includes(l)) ?? "rest";
    sections.push({ first: Number(m[1]), last: Number(m[2]), label, body: lines.slice(1).join("\n") });
  }
  return { head, sections };
}

export const confident = (label) => label === "high" || label === "medium";

// The sections to draw, with a { hidden: n } marker where n not-confident
// sections were left out (rests aren't counted).
export function visibleSections(sections, show) {
  const rows = [];
  let hidden = 0;
  for (const s of sections) {
    if (show === "confident" && !confident(s.label)) {
      if (s.label !== "rest") hidden++;
      continue;
    }
    if (hidden) rows.push({ hidden });
    hidden = 0;
    rows.push(s);
  }
  if (hidden) rows.push({ hidden });
  return rows;
}

// How the tab was moved from the recording, in words.
export function movedText(shift, key) {
  if (shift === 0) return "as recorded";
  const octaves = Math.abs(shift / 12);
  if (shift % 12 === 0) return `${shift > 0 ? "up" : "down"} ${octaves} octave${octaves > 1 ? "s" : ""}`;
  return `from ${key} (${shift > 0 ? "+" : ""}${shift})`;
}

// The job log's latest step, in words.
const STAGES = [
  [/audio:/, "Downloading"],
  [/separating/, "Separating instruments (the slow step)"],
  [/pitch tracking/, "Following the melody"],
  [/notes; tuning/, "Finding the beat"],
  [/tracking beats/, "Finding the beat"],
  [/bpm, .* bars/, "Writing the tab"],
];
export function stage(log) {
  let name = "Working";
  for (const line of log ?? []) for (const [re, n] of STAGES) if (re.test(line)) name = n;
  return name;
}
