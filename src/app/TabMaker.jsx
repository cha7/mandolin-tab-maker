"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { confident, movedText, parseTab, stage, visibleSections } from "@/lib/tab";
import styles from "./page.module.css";

const NO_OPTIONS = { stem: "auto", bpm: "", beats_per_bar: "", subdivision: "", key_change: false };

async function getJSON(url) {
  const r = await fetch(url);
  return r.json();
}

// The link form, the running job, the finished tab and the songs made before.
// The song being shown is kept in the URL's hash (#<song id>).
export default function TabMaker() {
  const [url, setUrl] = useState("");
  const [options, setOptions] = useState(NO_OPTIONS);
  const [rerun, setRerun] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [current, setCurrent] = useState(null);
  const [job, setJob] = useState(null);
  const [history, setHistory] = useState([]);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await getJSON("/api/history"));
    } catch {
      setHistory([]);
    }
  }, []);

  const openSong = useCallback((id) => {
    window.history.replaceState(null, "", "#" + id);
    setJob(null);
    setCurrent(id);
  }, []);

  useEffect(() => {
    loadHistory();
    if (location.hash.length > 1) setCurrent(decodeURIComponent(location.hash.slice(1)));
  }, [loadHistory]);

  // Poll the current song until it's done or failed.
  useEffect(() => {
    if (!current) return;
    let stop = false;
    let timer;
    const poll = async () => {
      let st = null;
      try {
        st = await getJSON("/api/jobs/" + encodeURIComponent(current));
      } catch {}
      if (stop) return;
      setJob(st && { ...st, loadedAt: Date.now() });
      if (st?.status === "done") loadHistory();
      if (st?.status === "queued" || st?.status === "running") timer = setTimeout(poll, 1500);
    };
    poll();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [current, loadHistory]);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setSending(true);
    try {
      const r = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), options, rerun }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || "request failed");
      openSong(j.song_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  const set = (key) => (e) =>
    setOptions((o) => ({ ...o, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  return (
    <>
      <section className="fh-card">
        <form className="fh-card__body" onSubmit={submit}>
          <div className={styles.row}>
            <label className="fh-visually-hidden" htmlFor="url">
              YouTube link
            </label>
            <input
              id="url"
              className="fh-input"
              type="url"
              required
              placeholder="https://www.youtube.com/watch?v=..."
              autoComplete="off"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <button className="fh-button fh-button--primary" type="submit" disabled={sending}>
              Make tab
            </button>
          </div>
          <details className={styles.options}>
            <summary>Options</summary>
            <div className={styles.opts}>
              <div className="fh-field">
                <label htmlFor="stem">Melody comes from</label>
                <select id="stem" className="fh-select" value={options.stem} onChange={set("stem")}>
                  <option value="auto">Detect (follow the clearest line)</option>
                  <option value="vocals">Vocals / whistle</option>
                  <option value="guitar">Guitar / banjo</option>
                  <option value="piano">Piano</option>
                  <option value="other">Other instruments</option>
                </select>
              </div>
              <div className="fh-field">
                <label htmlFor="bpm">Tempo (bpm)</label>
                <input id="bpm" className="fh-input" type="number" min="30" max="300" placeholder="detect" value={options.bpm} onChange={set("bpm")} />
              </div>
              <div className="fh-field">
                <label htmlFor="bpb">Beats per bar</label>
                <input id="bpb" className="fh-input" type="number" min="2" max="7" placeholder="detect" value={options.beats_per_bar} onChange={set("beats_per_bar")} />
              </div>
              <div className="fh-field">
                <label htmlFor="grid">Rhythm grid</label>
                <select id="grid" className="fh-select" value={options.subdivision} onChange={set("subdivision")}>
                  <option value="">Detect</option>
                  <option value="4">Straight (16ths)</option>
                  <option value="3">Triplets / jig (6/8)</option>
                </select>
              </div>
              <label className={styles.check}>
                <input type="checkbox" checked={options.key_change} onChange={set("key_change")} />
                Move to a mandolin-friendly key
              </label>
              <label className={styles.check}>
                <input type="checkbox" checked={rerun} onChange={(e) => setRerun(e.target.checked)} />
                Re-make even if done before
              </label>
            </div>
          </details>
          {error && (
            <div className={`fh-alert fh-alert--danger ${styles.note}`} role="alert">
              {error}
            </div>
          )}
        </form>
      </section>

      {job && job.status !== "done" && job.status !== "unknown" && <Progress job={job} />}
      {job?.status === "done" && <Result id={current} job={job} />}

      {history.length > 0 && (
        <section className="fh-card">
          <div className="fh-card__header">
            <h2 className="fh-card__title">Made before</h2>
          </div>
          <div className="fh-card__body">
            <ul className={styles.history}>
              {history.map((r) => (
                <li key={r.song_id}>
                  <a
                    href={"#" + r.song_id}
                    onClick={(e) => {
                      e.preventDefault();
                      openSong(r.song_id);
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                  >
                    {r.title || r.song_id}
                  </a>
                  <span className={styles.meta}>
                    {r.sections.high + r.sections.medium} confident of {r.sections.high + r.sections.medium + r.sections.low}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </>
  );
}

function Progress({ job }) {
  const logRef = useRef(null);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [job.log?.length]);
  const busy = job.status === "queued" || job.status === "running";
  const text =
    job.status === "queued"
      ? job.position > 1
        ? `Queued (${job.position - 1} ahead)`
        : "Starting"
      : job.status === "running"
        ? stage(job.log) + "..."
        : "Failed: " + job.error;
  return (
    <section className="fh-card" aria-live="polite">
      <div className="fh-card__body">
        <div>
          {busy && <span className={styles.spinner} />}
          <span className={styles.stage}>{text}</span>
        </div>
        {job.log?.length > 0 && (
          <pre ref={logRef} className={styles.log}>
            {job.log.join("\n")}
          </pre>
        )}
      </div>
    </section>
  );
}

function Result({ id, job }) {
  const [show, setShow] = useState("confident");
  const [jump, setJump] = useState(null);
  const s = job.report.summary;
  const { head, sections } = parseTab(job.tab);

  // Scroll to a section clicked in the strip, once it's drawn.
  useEffect(() => {
    if (jump === null) return;
    document.querySelector(`[data-first="${jump}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setJump(null);
  }, [jump, show]);

  const goTo = (first) => {
    if (show === "confident" && !sections.some((x) => x.first === first && confident(x.label))) setShow("all");
    setJump(first);
  };

  const confidentCount = s.sections.high + s.sections.medium;
  const chips = [
    ["Key", s.written_key],
    ["Time", s.time_signature],
    ["Tempo", `~${Math.round(s.bpm)} bpm`],
    ["Moved", movedText(s.shift, s.key)],
    ["Bars", s.bars],
    ["Confident sections", `${confidentCount} of ${confidentCount + s.sections.low}`],
  ];
  if (s.folded_notes) chips.push(["Notes folded into range", s.folded_notes]);
  const files = `/api/files/${encodeURIComponent(id)}`;

  return (
    <section className="fh-card">
      <div className="fh-card__body">
        <h2 className={styles.title}>{s.title}</h2>
        <div className={`fh-cluster ${styles.chips}`}>
          {chips.map(([k, v]) => (
            <span key={k} className="fh-label">
              {k} <b>{v}</b>
            </span>
          ))}
        </div>
        <div className={styles.hint}>Confidence by section (click to jump)</div>
        <div className={styles.strip}>
          {job.report.sections.map((x) => (
            <button
              key={x.first_bar}
              type="button"
              className={styles[x.label]}
              title={`bars ${x.first_bar}-${x.last_bar}: ${x.label}${x.label === "rest" ? "" : ` (${x.score.toFixed(2)})`}`}
              aria-label={`Bars ${x.first_bar}-${x.last_bar}, ${x.label === "rest" ? "no melody" : x.label}`}
              onClick={() => goTo(x.first_bar)}
            />
          ))}
        </div>
        <div className={styles.legend}>
          {[["high", "high"], ["medium", "medium"], ["low", "low"], ["rest", "no melody"]].map(([k, name]) => (
            <span key={k}>
              <i className={styles[k]} />
              {name}
            </span>
          ))}
        </div>
        <div className={`fh-toolbar ${styles.toolbar}`}>
          <div className={styles.seg} role="group" aria-label="Sections shown">
            {[["confident", "Confident only"], ["all", "Everything"]].map(([v, name]) => (
              <button key={v} type="button" className={show === v ? styles.on : undefined} aria-pressed={show === v} onClick={() => setShow(v)}>
                {name}
              </button>
            ))}
          </div>
          <a href={`${files}/tab.musicxml`} download={`${s.title || id}.musicxml`}>
            MusicXML (MuseScore)
          </a>
          <a href={`${files}/tab.txt`} download={`${s.title || id}.txt`}>
            tab.txt
          </a>
        </div>
        <audio className={styles.audio} controls preload="none" src={`${files}/preview.wav?t=${job.loadedAt}`} />
        <div className={styles.hint}>
          {s.shift % 12 === 0
            ? "The tab played back over the recording: the quickest way to hear whether it's right."
            : "The tab played back on its own (it's in a different key from the recording)."}
        </div>
        <div className={styles.tab}>
          <pre className={styles.head}>{head}</pre>
          {visibleSections(sections, show).map((x, i) =>
            x.hidden ? (
              <p key={`hidden-${i}`} className={styles.hiddenNote}>
                {x.hidden} section{x.hidden > 1 ? "s" : ""} hidden (not confident)
              </p>
            ) : (
              <div key={x.first} className={`${styles.block} ${styles[x.label]}`} data-first={x.first}>
                <h3>
                  Bars {x.first}-{x.last} · {x.label === "rest" ? "no melody" : x.label}
                </h3>
                <pre>{x.body}</pre>
              </div>
            ),
          )}
        </div>
      </div>
    </section>
  );
}
