// Tabs: the job queue, the songs made before, and their output files. Each job
// runs the Python engine's CLI (`mtab run`, via scripts/uv.cjs) as a child
// process, one at a time (the GPU can't share), and its timestamped progress
// lines become the job's log. Routes call these, never the engine directly.
import { spawn } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

// The engine's melody stems (mtab/separate.py MELODY_STEMS).
export const STEMS = ["vocals", "guitar", "piano", "other"];

// The only files the page may fetch from a song's output folder.
export const FILES = {
  "tab.txt": "text/plain; charset=utf-8",
  "tab.musicxml": "application/vnd.recordare.musicxml+xml",
  "preview.wav": "audio/wav",
  "report.json": "application/json",
};

export const SONG_ID = /^[A-Za-z0-9_-]{1,64}$/;
const YOUTUBE = /^https?:\/\/(www\.|m\.|music\.)?(youtube\.com|youtu\.be)\//;
// Same pattern as mtab/audio.py, so the song id here is the engine's folder name.
const YOUTUBE_ID = /(?:v=|youtu\.be\/|shorts\/|embed\/)([A-Za-z0-9_-]{11})/;
const LOG_LINE = /^\[\d\d:\d\d:\d\d\] /;

export class InputError extends Error {}

// A YouTube video link -> its video id, or throws InputError.
export function videoId(url) {
  const u = String(url ?? "").trim();
  if (!YOUTUBE.test(u)) throw new InputError("paste a youtube.com or youtu.be link");
  const m = u.match(YOUTUBE_ID);
  if (!m) throw new InputError("that YouTube link doesn't point at a video");
  return m[1];
}

// The page's options -> `mtab run` flags, or throws InputError. Separation and
// the pitch model aren't offered.
export function optionArgs(raw = {}) {
  const args = [];
  const stem = raw.stem || "auto";
  if (stem !== "auto" && !STEMS.includes(stem)) throw new InputError("bad stem");
  if (stem !== "auto") args.push("--stem", stem);
  if (raw.key_change) args.push("--key-change");
  const num = (key, flag, ok) => {
    const v = raw[key];
    if (v === "" || v === null || v === undefined) return;
    const n = Number(v);
    if (!Number.isFinite(n) || !ok(n)) throw new InputError(`bad ${key}`);
    args.push(flag, String(n));
  };
  num("bpm", "--bpm", (v) => v >= 30 && v <= 300);
  num("beats_per_bar", "--beats-per-bar", (v) => Number.isInteger(v) && v >= 2 && v <= 7);
  num("subdivision", "--grid", (v) => v === 3 || v === 4);
  return args;
}

const time = () => new Date().toTimeString().slice(0, 8);

export function createJobs({ root = process.cwd(), run = spawn } = {}) {
  const out = path.join(root, "out");
  const state = new Map(); // id -> { status, log, error }
  const queue = []; // [{ id, url, args }]
  let running = null;

  const reportPath = (id) => path.join(out, id, "report.json");

  function next() {
    if (running || !queue.length) return;
    const job = (running = queue.shift());
    const st = state.get(job.id);
    st.status = "running";
    const log = (line) => {
      console.log(line);
      st.log.push(line);
    };
    if (existsSync(reportPath(job.id))) log(`[${time()}] re-running (cached steps are reused)`);

    let stderr = "";
    const proc = run(process.execPath, [path.join(root, "scripts", "uv.cjs"), "run", "mtab", "run", job.url, ...job.args], {
      cwd: root,
      // Unbuffered, so progress shows as it happens; UTF-8, so Windows'
      // console encoding can't break a log line.
      env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
    });
    let partial = "";
    proc.stdout.on("data", (chunk) => {
      const lines = (partial + chunk).split("\n");
      partial = lines.pop();
      for (const line of lines) if (LOG_LINE.test(line)) log(line);
    });
    proc.stderr.on("data", (chunk) => {
      process.stderr.write(chunk);
      stderr = (stderr + chunk).slice(-4000);
    });
    const finish = (error) => {
      if (running !== job) return;
      Object.assign(st, error ? { status: "error", error } : { status: "done" });
      running = null;
      next();
    };
    proc.on("error", (e) => finish(e.message));
    proc.on("close", (code) => {
      if (code === 0) return finish(null);
      // The traceback's last line, e.g. "RuntimeError: no melody found".
      const last = stderr.trim().split("\n").filter(Boolean).pop();
      finish(last || `the engine stopped (exit ${code})`);
    });
  }

  return {
    // Queues a tab for a YouTube link. Returns the song id; a song already
    // made (or in progress) isn't queued again unless rerun is set.
    submit({ url, options, rerun = false }) {
      const id = videoId(url);
      const args = optionArgs(options ?? {});
      const cur = state.get(id);
      if (cur && (cur.status === "queued" || cur.status === "running")) return id;
      if (!rerun && !cur && existsSync(reportPath(id))) return id; // the page loads it
      state.set(id, { status: "queued", log: [], error: null });
      queue.push({ id, url: `https://www.youtube.com/watch?v=${id}`, args });
      next();
      return id;
    },

    status(id) {
      const st = { ...(state.get(id) ?? {}) };
      const report = reportPath(id);
      if (!st.status) Object.assign(st, { status: existsSync(report) ? "done" : "unknown", log: [] });
      if (st.status === "done" && existsSync(report)) {
        st.report = JSON.parse(readFileSync(report, "utf8"));
        st.tab = readFileSync(path.join(out, id, "tab.txt"), "utf8");
      }
      st.position = st.status === "queued" ? queue.findIndex((j) => j.id === id) + 1 : 0;
      return st;
    },

    history() {
      if (!existsSync(out)) return [];
      return readdirSync(out)
        .filter((id) => SONG_ID.test(id) && existsSync(reportPath(id)))
        .map((id) => {
          const s = JSON.parse(readFileSync(reportPath(id), "utf8")).summary;
          return { song_id: s.song_id, title: s.title, overall: s.overall, sections: s.sections, made: statSync(reportPath(id)).mtimeMs };
        })
        .sort((a, b) => b.made - a.made);
    },

    // One of FILES from a song's output folder, or null.
    file(id, name) {
      if (!SONG_ID.test(id) || !Object.hasOwn(FILES, name)) return null;
      const f = path.join(out, id, name);
      return existsSync(f) ? { body: readFileSync(f), type: FILES[name] } : null;
    },
  };
}

// One queue for the server process, kept across dev reloads.
export const jobs = (globalThis.__mtabJobs ??= createJobs());
