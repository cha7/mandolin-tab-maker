"""Confidence: per-bar evidence that the tab matches the recording, rolled up into sections.

Phase 0 only reports these numbers; the thresholds below are placeholders until the
evaluation set tells us where "right" and "wrong" tabs actually fall."""

from dataclasses import dataclass, asdict

import numpy as np

from .melody import Track
from .rhythm import Grid, QNote

BARS_PER_SECTION = 4
HIGH, MEDIUM = 0.6, 0.4  # provisional; calibrate with `mtab eval`
MARGIN_FULL = 0.3        # salience lead over the runner-up stem that counts as unambiguous


@dataclass
class BarScore:
    bar: int            # 1-based
    notes: int
    coverage: float     # share of the bar where some stem carries a melody
    clarity: float      # pitch-tracker confidence on those frames
    dominance: float    # how clearly one stem leads (vs. two stems competing)
    pitch_fit: float    # frames whose pitch matches the written note
    rhythm: float       # 1 = every onset sat on the grid, 0 = halfway between
    score: float


@dataclass
class Section:
    first_bar: int
    last_bar: int
    score: float
    label: str          # high / medium / low / rest


def score_bars(track: Track, notes: list[QNote], grid: Grid, bar1: int,
               n_bars: int) -> list[BarScore]:
    bpb = grid.beats_per_bar
    pos = grid.beat_pos(track.times) - bar1  # every frame's beat position from bar 1
    onsets = np.array([n.onset for n in notes])
    ends = onsets + np.array([n.duration for n in notes])
    heard = np.array([n.midi for n in notes])
    midi = track.midi - track.tuning
    out = []
    for b in range(n_bars):
        lo, hi = b * bpb, (b + 1) * bpb
        frames = (pos >= lo) & (pos < hi)
        in_bar = [n for n in notes if lo <= n.onset < hi]
        voiced = frames & (track.stem >= 0)
        cov = float(voiced.sum() / max(frames.sum(), 1))
        if not in_bar or not voiced.any():
            out.append(BarScore(b + 1, len(in_bar), cov, 0, 0, 0, 0, 0))
            continue
        clarity = float(track.periodicity[voiced].mean())
        dominance = float(np.clip(track.margin[voiced] / MARGIN_FULL, 0, 1).mean())
        # Which written note is sounding at each voiced frame?
        idx = np.flatnonzero(voiced)
        k = np.searchsorted(onsets, pos[idx], side="right") - 1
        ok = (k >= 0) & (pos[idx] < ends[np.clip(k, 0, None)])
        fit = np.abs(midi[idx[ok]] - heard[k[ok]]) < 0.5
        pitch_fit = float(fit.sum() / len(idx))
        rhythm = float(1 - 2 * np.mean([n.residual for n in in_bar]))
        score = clarity * np.sqrt(dominance) * pitch_fit * rhythm
        out.append(BarScore(b + 1, len(in_bar), cov, clarity, dominance, pitch_fit,
                            rhythm, float(score)))
    return out


def sections(bars: list[BarScore]) -> list[Section]:
    out = []
    for i in range(0, len(bars), BARS_PER_SECTION):
        group = [b for b in bars[i:i + BARS_PER_SECTION]]
        played = [b for b in group if b.notes]
        if not played:
            out.append(Section(group[0].bar, group[-1].bar, 0.0, "rest"))
            continue
        w = np.array([b.notes for b in played], dtype=float)
        s = float(np.average([b.score for b in played], weights=w))
        label = "high" if s >= HIGH else "medium" if s >= MEDIUM else "low"
        out.append(Section(group[0].bar, group[-1].bar, s, label))
    return out


def to_json(bars: list[BarScore], secs: list[Section]) -> dict:
    return {"bars": [asdict(b) for b in bars], "sections": [asdict(s) for s in secs]}
