import { EventEmitter } from "node:events";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { InputError, createJobs, optionArgs, videoId } from "./jobs";

// A stand-in for the engine's process: records its arguments, finishes when told.
function fakeRun() {
  const calls = [];
  const run = (cmd, args, opts) => {
    const proc = new EventEmitter();
    proc.stdout = new EventEmitter();
    proc.stderr = new EventEmitter();
    calls.push({ cmd, args, opts, proc });
    return proc;
  };
  return { run, calls };
}

function setup() {
  const root = mkdtempSync(path.join(tmpdir(), "mtab-"));
  const song = path.join(root, "out", "abc123def45");
  mkdirSync(song, { recursive: true });
  const summary = { song_id: "abc123def45", title: "Old tune", overall: 0.7, sections: { high: 2, medium: 1, low: 1 } };
  writeFileSync(path.join(song, "report.json"), JSON.stringify({ summary, sections: [] }));
  writeFileSync(path.join(song, "tab.txt"), "tab");
  writeFileSync(path.join(song, "secret.wav"), "not served");
  const { run, calls } = fakeRun();
  return { root, calls, jobs: createJobs({ root, run }) };
}

const YT = "https://www.youtube.com/watch?v=Xpkc-NU1KA0";

describe("videoId", () => {
  it("takes YouTube video links only", () => {
    expect(videoId(YT)).toBe("Xpkc-NU1KA0");
    expect(videoId("https://youtu.be/Xpkc-NU1KA0?t=3")).toBe("Xpkc-NU1KA0");
    expect(videoId(" https://m.youtube.com/shorts/Xpkc-NU1KA0 ")).toBe("Xpkc-NU1KA0");
    for (const bad of ["https://example.com/a.mp3", "file:///etc/passwd", "https://photos.google.com/photo/AF1Qip", "https://www.youtube.com/@channel", undefined]) {
      expect(() => videoId(bad)).toThrow(InputError);
    }
  });
});

describe("optionArgs", () => {
  it("turns the page's options into mtab run flags", () => {
    expect(optionArgs({})).toEqual([]);
    expect(optionArgs({ stem: "vocals", key_change: true, bpm: "120", beats_per_bar: "", subdivision: "3" })).toEqual([
      "--stem", "vocals", "--key-change", "--bpm", "120", "--grid", "3",
    ]);
  });
  it("refuses values the engine wouldn't take", () => {
    for (const bad of [{ bpm: 9000 }, { bpm: "abc" }, { stem: "drums" }, { subdivision: 5 }, { beats_per_bar: 2.5 }]) {
      expect(() => optionArgs(bad)).toThrow(InputError);
    }
  });
});

describe("jobs", () => {
  it("runs the engine for a link and follows its progress", () => {
    const { jobs, calls, root } = setup();
    expect(jobs.submit({ url: "https://youtu.be/Xpkc-NU1KA0", options: { stem: "guitar" } })).toBe("Xpkc-NU1KA0");
    expect(calls).toHaveLength(1);
    const { cmd, args, opts, proc } = calls[0];
    expect(cmd).toBe(process.execPath);
    expect(args).toEqual([path.join(root, "scripts", "uv.cjs"), "run", "mtab", "run", YT, "--stem", "guitar"]);
    expect(opts.cwd).toBe(root);
    expect(jobs.status("Xpkc-NU1KA0").status).toBe("running");

    // Only the timestamped lines are the log (not the summary JSON or the tab printed at the end).
    proc.stdout.emit("data", "[12:00:01] audio: x\n[12:00:0");
    proc.stdout.emit("data", "2] separating stems\n{\n");
    expect(jobs.status("Xpkc-NU1KA0").log).toEqual(["[12:00:01] audio: x", "[12:00:02] separating stems"]);
    proc.emit("close", 0);
    expect(jobs.status("Xpkc-NU1KA0").status).toBe("done");
  });

  it("runs one song at a time and reports the queue", () => {
    const { jobs, calls } = setup();
    jobs.submit({ url: YT });
    jobs.submit({ url: "https://youtu.be/aaaaaaaaaaa" });
    jobs.submit({ url: YT }); // already running: not queued twice
    expect(calls).toHaveLength(1);
    expect(jobs.status("aaaaaaaaaaa")).toMatchObject({ status: "queued", position: 1 });
    calls[0].proc.stderr.emit("data", "Traceback...\nRuntimeError: no melody found\n");
    calls[0].proc.emit("close", 1);
    expect(jobs.status("Xpkc-NU1KA0")).toMatchObject({ status: "error", error: "RuntimeError: no melody found" });
    expect(calls).toHaveLength(2);
    expect(jobs.status("aaaaaaaaaaa").status).toBe("running");
  });

  it("loads a song made before instead of re-making it, unless asked", () => {
    const { jobs, calls } = setup();
    expect(jobs.submit({ url: "https://youtu.be/abc123def45" })).toBe("abc123def45");
    expect(calls).toHaveLength(0);
    expect(jobs.status("abc123def45")).toMatchObject({ status: "done", tab: "tab" });
    jobs.submit({ url: "https://youtu.be/abc123def45", rerun: true });
    expect(calls).toHaveLength(1);
    expect(jobs.status("abc123def45").log[0]).toMatch(/re-running/);
  });

  it("lists songs made before and serves only their listed files", () => {
    const { jobs } = setup();
    expect(jobs.history()).toMatchObject([{ song_id: "abc123def45", title: "Old tune" }]);
    expect(jobs.file("abc123def45", "tab.txt").body.toString()).toBe("tab");
    expect(jobs.file("abc123def45", "secret.wav")).toBeNull();
    expect(jobs.file("..", "tab.txt")).toBeNull();
    expect(jobs.file("abc123def45", "constructor")).toBeNull();
    expect(jobs.status("nothing-here").status).toBe("unknown");
  });
});
