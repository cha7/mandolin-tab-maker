"""The whole run: source -> stems -> melody -> notes -> bars -> mandolin tab.

Slow steps (download, separation, pitch tracking, beats) are cached under work/<song>/,
so re-running after a tweak to the later steps takes seconds."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import audio, harmony, mandolin, melody, render, report, rhythm, separate


@dataclass
class Options:
    stem: str = "auto"            # or one of separate.MELODY_STEMS
    key_change: bool = False      # allow moving to a mandolin-friendly key, not just octaves
    bpm: float | None = None      # skip beat tracking and use a steady tempo
    beats_per_bar: int | None = None
    subdivision: int | None = None  # 4 or 3; None = detect
    crepe: str | None = None      # "full" or "tiny"; None = full on GPU, tiny on CPU
    separate: bool = True         # False: treat the input as an isolated melody


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(source: str, opts: Options, work_root=Path("work"), out_root=Path("out"),
        log=_log, song_id: str | None = None) -> dict:
    sid = song_id or audio.song_id(source)
    work, out = work_root / sid, out_root / sid
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    dev = separate.device()
    model = opts.crepe or ("full" if dev == "cuda" else "tiny")

    log(f"audio: {source}")
    mix_path = audio.fetch(source, work)
    title_file = work / "title.txt"
    title = title_file.read_text() if title_file.exists() else Path(source).stem

    if opts.separate:
        log(f"separating stems ({separate.MODEL} on {dev})")
        stems = separate.separate(mix_path, work)
        names = separate.MELODY_STEMS if opts.stem == "auto" else (opts.stem,)
        harmony_paths = [stems[s] for s in separate.HARMONY_STEMS]
    else:
        stems = {"mix": mix_path}
        names = ("mix",)
        harmony_paths = [mix_path]

    log(f"pitch tracking {', '.join(names)} (crepe {model})")
    tracks = {n: melody.pitch_track(stems[n], work / f"pitch-{n}-{model}.npz", model, dev)
              for n in names}
    track = melody.follow(tracks)
    stem_onsets = {n: melody.onsets(stems[n], work / f"onsets-{n}.npy") for n in names}
    notes = melody.segment(track, stem_onsets)
    if not notes:
        raise RuntimeError("no melody found")
    log(f"{len(notes)} notes; tuning {track.tuning * 100:+.0f} cents")

    if opts.bpm:
        grid = rhythm.fixed_grid(opts.bpm, opts.beats_per_bar or 4, notes[0].start,
                                 notes[-1].end, opts.subdivision or 4)
    else:
        log("tracking beats")
        beats, downbeats = rhythm.track_beats(mix_path, work / "beats.npz", dev)
        grid = rhythm.make_grid(beats, downbeats, notes, opts.subdivision, opts.beats_per_bar)
    bar1 = rhythm.origin(grid, notes)
    qnotes = rhythm.quantize(notes, grid)
    bpb = grid.beats_per_bar
    n_bars = int(np.ceil(max(n.onset + n.duration for n in qnotes) / bpb))
    bpm = 60 / float(np.median(np.diff(grid.beats)))
    log(f"{grid.time_signature}, {bpm:.0f} bpm, {n_bars} bars, grid 1/{grid.subdivision}")

    chroma = harmony.beat_chroma(harmony_paths, grid, work / "chroma.npy") \
        if not opts.bpm else np.zeros((len(grid.beats), 12))
    chords = harmony.chords(chroma, grid, bar1, n_bars) if chroma.any() else []
    tonic, mode = harmony.key(qnotes, chroma)

    shift = mandolin.choose_shift([n.midi for n in qnotes], tonic, mode, opts.key_change)
    folded = mandolin.fit_range(qnotes, shift)
    mandolin.assign_frets(qnotes)
    w_tonic = (tonic + shift) % 12
    w_chords = [(p, render.transpose_chord(c, shift)) for p, c in chords]

    bars = report.score_bars(track, qnotes, grid, bar1, n_bars)
    secs = report.sections(bars)

    move = (f"{shift:+d} semitones" if shift % 12 else
            f"{shift // 12:+d} octave(s)" if shift else "none")
    header = [
        f"{title}",
        f"Mandolin (GDAE)   key: {harmony.key_name(w_tonic, mode)}   "
        f"time: {grid.time_signature}   tempo: ~{bpm:.0f} bpm",
        f"transposed from {harmony.key_name(tonic, mode)}: {move}"
        + (f"   ({folded} notes folded into range)" if folded else ""),
        "Tab strings top to bottom: E A D G. Numbers are frets; rhythm is in tab.musicxml.",
    ]
    (out / "tab.txt").write_text(render.ascii_tab(qnotes, grid, w_chords, secs, n_bars, header))
    render.musicxml(qnotes, grid, w_chords, w_tonic, mode, bpm, title, out / "tab.musicxml")
    mix, sr = audio.load(mix_path)
    render.preview(qnotes, grid, bar1, mix, sr, with_mix=shift % 12 == 0,
                   path=out / "preview.wav")

    played = [s for s in secs if s.label != "rest"]
    summary = {
        "source": source, "title": title, "song_id": sid,
        "key": harmony.key_name(tonic, mode), "written_key": harmony.key_name(w_tonic, mode),
        "shift": shift, "folded_notes": folded, "time_signature": grid.time_signature,
        "bpm": round(bpm, 1), "bars": n_bars, "notes": len(qnotes),
        "tuning_cents": round(track.tuning * 100),
        "stem_share": {n: round(float(np.mean(track.stem == i)), 3)
                       for i, n in enumerate(track.stems)},
        "sections": {lab: sum(s.label == lab for s in played) for lab in ("high", "medium", "low")},
        "overall": round(float(np.mean([s.score for s in played])), 3) if played else 0.0,
    }
    (out / "notes.json").write_text(json.dumps({
        "beat_ql": grid.beat_ql, "notes": rhythm.to_json(qnotes), "chords": w_chords}, indent=1))
    (out / "report.json").write_text(json.dumps(
        {"summary": summary, **report.to_json(bars, secs)}, indent=1))
    log(f"wrote {out}/tab.txt, tab.musicxml, preview.wav, report.json")
    return summary
