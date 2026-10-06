"""Scoring a generated tab against a known-good melody (ABC, MusicXML or MIDI).

Both are compared in beats, not seconds (a score has no audio timing), and without regard
to octave or key, since the tab may be transposed. The alignment (key shift, tempo
doubling/halving, and where in the recording the reference starts) is searched for."""

import json
from pathlib import Path

import mir_eval
import numpy as np
import yaml

from . import pipeline

ONSET_TOLERANCE = 0.25  # quarter notes: one sixteenth either way


def load_reference(path: Path) -> np.ndarray:
    """(onset_ql, end_ql, midi) for the top line of the first tune, repeats expanded."""
    from music21 import chord, converter, note, stream

    s = converter.parse(str(path))
    if isinstance(s, stream.Opus):
        s = s.scores[0]
    try:
        s = s.expandRepeats()
    except Exception:  # noqa: BLE001 - malformed repeats: compare unexpanded
        pass
    part = s.parts[0] if hasattr(s, "parts") and s.parts else s
    rows = []
    for el in part.flatten().notes:
        if isinstance(el, chord.Chord):
            midi = max(p.midi for p in el.pitches)
        elif isinstance(el, note.Note):
            midi = el.pitch.midi
        else:
            continue
        on = float(el.getOffsetInHierarchy(part))
        rows.append((on, on + max(float(el.quarterLength), 0.125), midi))
    return np.array(sorted(rows))


def load_estimate(out_dir: Path) -> np.ndarray:
    d = json.loads((out_dir / "notes.json").read_text())
    q = d["beat_ql"]
    return np.array([(n["onset"] * q, (n["onset"] + n["duration"]) * q, n["written"])
                     for n in d["notes"]])


def _hz(pc):
    return 440 * 2 ** ((60 + pc - 69) / 12)


def compare(est: np.ndarray, ref: np.ndarray) -> dict:
    """Best-alignment note precision/recall/F1 by pitch class and onset."""
    best = {"f1": 0.0, "precision": 0.0, "recall": 0.0}
    ref_pc = ref[:, 2].astype(int) % 12
    for scale in (0.5, 1.0, 2.0):
        r_on = ref[:, 0] * scale
        r_iv = np.stack([r_on, ref[:, 1] * scale], 1)
        for t in range(12):
            e_pc = (est[:, 2].astype(int) + t) % 12
            # Candidate offsets: where same-pitch pairs say the reference starts.
            head = slice(0, min(len(ref), 24))
            diffs = (est[:, 0][:, None] - r_on[head][None, :])[e_pc[:, None] == ref_pc[head][None, :]]
            if not len(diffs):
                continue
            q = np.round(diffs / 0.25) * 0.25
            vals, counts = np.unique(q, return_counts=True)
            for off in vals[np.argsort(counts)[-8:]]:
                tol = ONSET_TOLERANCE * scale
                lo, hi = off + r_on[0] - tol, off + r_on[-1] + tol
                win = (est[:, 0] >= lo) & (est[:, 0] <= hi)
                if not win.any():
                    continue
                e_iv = est[win, :2] - off
                match = mir_eval.transcription.match_notes(
                    r_iv, _hz(ref_pc), e_iv, _hz(e_pc[win]),
                    onset_tolerance=tol, offset_ratio=None)
                p, r = len(match) / win.sum(), len(match) / len(ref)
                f1 = 2 * p * r / (p + r) if p + r else 0.0
                if f1 > best["f1"]:
                    best = {"f1": f1, "precision": p, "recall": r, "transpose": t,
                            "tempo_scale": scale, "offset_ql": float(off)}
    return {k: round(v, 3) if isinstance(v, float) else v for k, v in best.items()}


def run_set(config: Path, work_root=Path("work"), out_root=Path("out")) -> list[dict]:
    cfg = yaml.safe_load(config.read_text())
    rows = []
    for song in cfg["songs"]:
        opts = pipeline.Options(**song.get("options", {}))
        try:
            summary = pipeline.run(song["source"], opts, work_root, out_root)
        except Exception as e:  # noqa: BLE001 - one bad song shouldn't stop the set
            rows.append({"name": song["name"], "error": str(e)})
            continue
        row = {"name": song["name"], "overall_conf": summary["overall"],
               "sections": summary["sections"]}
        if song.get("reference"):
            ref = load_reference(config.parent / song["reference"]
                                 if not Path(song["reference"]).is_absolute()
                                 else Path(song["reference"]))
            est = load_estimate(out_root / summary["song_id"])
            row.update(compare(est, ref))
        rows.append(row)
    return rows
