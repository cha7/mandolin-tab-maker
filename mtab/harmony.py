"""Chord names above the staff and the key signature."""

from pathlib import Path

import librosa
import numpy as np

from .audio import load
from .rhythm import Grid, QNote

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
CHORD_SWITCH_COST = 0.12   # similarity given up to change chord between beats
MIN_CHROMA_ENERGY = 0.05   # beats quieter than this (relative) get no chord

# Krumhansl-Kessler key profiles.
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _templates():
    labels, temps = [], []
    for root in range(12):
        for quality, third in (("", 4), ("m", 3)):
            t = np.zeros(12)
            t[[root, (root + third) % 12, (root + 7) % 12]] = 1
            temps.append(t / np.linalg.norm(t))
            labels.append(NAMES[root] + quality)
    return labels, np.array(temps)


def beat_chroma(stem_paths: list[Path], grid: Grid, cache: Path) -> np.ndarray:
    """Chroma of the accompaniment, one 12-vector per beat. Cached."""
    if cache.exists():
        return np.load(cache)
    y = None
    for p in stem_paths:
        s, sr = load(p, mono=True)
        y = s if y is None else y[: len(s)] + s[: len(y)]
    y = librosa.resample(y, orig_sr=sr, target_sr=22050)
    hop = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=22050, hop_length=hop)
    frames = librosa.time_to_frames(grid.beats, sr=22050, hop_length=hop)
    frames = np.clip(frames, 0, chroma.shape[1] - 1)
    # One column per beat interval [beat i, beat i+1).
    out = np.zeros((len(grid.beats), 12))
    energy = np.zeros(len(grid.beats))
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    bounds = list(frames) + [chroma.shape[1]]
    for i in range(len(grid.beats)):
        a, b = bounds[i], max(bounds[i + 1], bounds[i] + 1)
        out[i] = np.median(chroma[:, a:b], axis=1)
        energy[i] = rms[a:b].mean() if b <= len(rms) else 0
    energy /= energy.max() + 1e-9
    out[energy < MIN_CHROMA_ENERGY] = 0
    np.save(cache, out)
    return out


def chords(chroma: np.ndarray, grid: Grid, bar1: int, n_bars: int) -> list[tuple[float, str]]:
    """(beat position from bar 1, chord name) at each chord change, at most two per bar."""
    labels, temps = _templates()
    norm = np.linalg.norm(chroma, axis=1, keepdims=True)
    sim = (chroma / np.maximum(norm, 1e-9)) @ temps.T  # (beats, chords)
    has = norm[:, 0] > 0
    # Viterbi over beats so the chord doesn't change on every passing note.
    B, C = sim.shape
    best = sim[0].copy()
    back = np.zeros((B, C), dtype=int)
    for i in range(1, B):
        stay = best
        move = best.max() - CHORD_SWITCH_COST
        back[i] = np.where(stay >= move, np.arange(C), best.argmax())
        best = np.maximum(stay, move) + sim[i]
    path = np.empty(B, dtype=int)
    path[-1] = best.argmax()
    for i in range(B - 1, 0, -1):
        path[i - 1] = back[i, path[i]]

    bpb = grid.beats_per_bar
    halves = (0, bpb // 2) if bpb % 2 == 0 and bpb >= 4 else (0,)
    out: list[tuple[float, str]] = []
    for bar in range(n_bars):
        for k, h in enumerate(halves):
            lo = bar1 + bar * bpb + h
            hi = bar1 + bar * bpb + (halves[k + 1] if k + 1 < len(halves) else bpb)
            idx = [i for i in range(lo, hi) if 0 <= i < B and has[i]]
            if not idx:
                continue
            votes = np.bincount(path[idx], weights=sim[idx, path[idx]], minlength=C)
            name = labels[int(votes.argmax())]
            pos = float(bar * bpb + h)
            if not out or out[-1][1] != name:
                out.append((pos, name))
    return out


def key(notes: list[QNote], chroma: np.ndarray) -> tuple[int, str]:
    """(tonic pitch class, 'major' or 'minor') from melody durations plus harmony."""
    hist = np.zeros(12)
    for n in notes:
        hist[n.midi % 12] += n.duration
    if hist.sum():
        hist /= hist.sum()
    if chroma.size and chroma.sum():
        h = chroma.sum(0)
        hist = hist + h / h.sum()
    best, best_r = (0, "major"), -2.0
    for tonic in range(12):
        for mode, prof in (("major", _MAJOR), ("minor", _MINOR)):
            r = np.corrcoef(hist, np.roll(prof, tonic))[0, 1]
            if r > best_r:
                best, best_r = (tonic, mode), r
    return best


def key_name(tonic: int, mode: str) -> str:
    return NAMES[tonic] + ("m" if mode == "minor" else "")
