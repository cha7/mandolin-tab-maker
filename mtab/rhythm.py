"""Beats, meter and quantization: turning note times in seconds into note values."""

from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

from .audio import load
from .melody import Note

# Gaps shorter than this many beats between notes are articulation, not rests: the
# earlier note is held to the next one, the way a tab writes it.
FILL_GAP_BEATS = 0.5


@dataclass
class Grid:
    beats: np.ndarray       # beat times (s)
    beats_per_bar: int
    first_downbeat: int     # index into `beats`
    subdivision: int        # grid steps per beat: 4 (sixteenths) or 3 (triplets / compound)

    @property
    def compound(self) -> bool:
        return self.subdivision == 3

    @property
    def beat_ql(self) -> float:
        """A beat in quarter notes: a dotted quarter in compound time."""
        return 1.5 if self.compound else 1.0

    @property
    def time_signature(self) -> str:
        if self.compound:
            return f"{self.beats_per_bar * 3}/8"
        return f"{self.beats_per_bar}/4"

    def beat_pos(self, t):
        """Seconds to fractional beat index, extrapolating past either end."""
        b = self.beats
        idx = np.arange(len(b), dtype=float)
        t = np.asarray(t, dtype=float)
        pos = np.interp(t, b, idx)
        head = (b[1] - b[0]) if len(b) > 1 else 0.5
        tail = (b[-1] - b[-2]) if len(b) > 1 else 0.5
        pos = np.where(t < b[0], (t - b[0]) / head, pos)
        pos = np.where(t > b[-1], len(b) - 1 + (t - b[-1]) / tail, pos)
        return pos

    def time_at(self, pos):
        """Fractional beat index to seconds (inverse of beat_pos)."""
        b = self.beats
        idx = np.arange(len(b), dtype=float)
        pos = np.asarray(pos, dtype=float)
        t = np.interp(pos, idx, b)
        head = (b[1] - b[0]) if len(b) > 1 else 0.5
        tail = (b[-1] - b[-2]) if len(b) > 1 else 0.5
        t = np.where(pos < 0, b[0] + pos * head, t)
        t = np.where(pos > len(b) - 1, b[-1] + (pos - len(b) + 1) * tail, t)
        return t


@dataclass
class QNote:
    """A quantized note. Positions are in beats from the start of the first bar."""
    onset: float
    duration: float
    midi: int             # as heard
    residual: float       # how far off the grid the onset was, in grid steps (0..0.5)
    periodicity: float
    stability: float
    stem: str
    written: int = 0      # pitch on the mandolin, after transposition
    string: int = 0       # 1 = E (highest) .. 4 = G (lowest), as tabs number them
    fret: int = 0


def track_beats(mix_path: Path, cache: Path, device: str) -> tuple[np.ndarray, np.ndarray]:
    """Beat and downbeat times (s) with beat_this. Cached."""
    if cache.exists():
        d = np.load(cache)
        return d["beats"], d["downbeats"]
    from beat_this.inference import Audio2Beats

    y, sr = load(mix_path)
    beats, downbeats = Audio2Beats(checkpoint_path="final0", device=device, dbn=False)(y, sr)
    np.savez(cache, beats=beats, downbeats=downbeats)
    return np.asarray(beats), np.asarray(downbeats)


def make_grid(beats: np.ndarray, downbeats: np.ndarray, notes: list[Note],
              subdivision: int | None = None, beats_per_bar: int | None = None) -> Grid:
    if len(beats) < 4:
        raise ValueError("found fewer than 4 beats; pass --bpm to set the tempo by hand")
    bidx = [int(np.argmin(np.abs(beats - d))) for d in downbeats]
    bidx = sorted(set(i for i, d in zip(bidx, downbeats) if abs(beats[i] - d) < 0.07))
    if beats_per_bar is None:
        gaps = np.diff(bidx)
        gaps = gaps[(gaps >= 2) & (gaps <= 7)]
        beats_per_bar = int(np.bincount(gaps).argmax()) if len(gaps) else 4
    # The bar phase most downbeats agree on.
    if bidx:
        phase = int(np.bincount(np.array(bidx) % beats_per_bar).argmax())
    else:
        phase = 0
    grid = Grid(beats=beats, beats_per_bar=beats_per_bar, first_downbeat=phase,
                subdivision=subdivision or 4)
    if subdivision is None:
        grid.subdivision = _pick_subdivision(grid, notes)
    return grid


def fixed_grid(bpm: float, beats_per_bar: int, start: float, end: float,
               subdivision: int = 4) -> Grid:
    """A steady grid from a given tempo, for when the beat tracker can't be trusted."""
    step = 60.0 / bpm
    beats = np.arange(start, end + step, step)
    return Grid(beats=beats, beats_per_bar=beats_per_bar, first_downbeat=0,
                subdivision=subdivision)


def _pick_subdivision(grid: Grid, notes: list[Note]) -> int:
    """Sixteenths unless the onsets sit clearly better on a triplet grid."""
    if not notes:
        return 4
    pos = grid.beat_pos([n.start for n in notes])

    def err(sub):  # mean distance to the grid, in beats
        return float(np.mean(np.abs(pos * sub - np.round(pos * sub)) / sub))

    # A finer grid always fits a little better; only switch on a clear win.
    return 3 if err(3) < 0.75 * err(4) else 4


def quantize(notes: list[Note], grid: Grid) -> list[QNote]:
    sub = grid.subdivision
    bar1 = origin(grid, notes)
    starts = grid.beat_pos([n.start for n in notes]) - bar1
    ends = grid.beat_pos([n.end for n in notes]) - bar1
    q: list[QNote] = []
    for n, s, e in zip(notes, starts, ends):
        qs = np.round(s * sub) / sub
        qe = max(np.round(e * sub) / sub, qs + 1 / sub)
        q.append(QNote(onset=float(qs), duration=float(qe - qs), midi=n.midi,
                       residual=float(abs(s * sub - np.round(s * sub))),
                       periodicity=n.periodicity, stability=n.stability, stem=n.stem))
    # Two notes landing on one grid step: keep the stronger.
    by_onset: dict[float, QNote] = {}
    for n in q:
        k = n.onset
        if k not in by_onset or _strength(n) > _strength(by_onset[k]):
            by_onset[k] = n
    out = sorted(by_onset.values(), key=lambda n: n.onset)
    for a, b in zip(out, out[1:]):
        gap = b.onset - (a.onset + a.duration)
        if gap < 0 or gap < FILL_GAP_BEATS:
            a.duration = b.onset - a.onset
    return out


def _strength(n: QNote) -> float:
    return n.duration * n.periodicity


def origin(grid: Grid, notes: list[Note]) -> int:
    """Beat index where bar 1 starts: the downbeat at or before the first note."""
    first = grid.first_downbeat
    if notes:
        p = float(grid.beat_pos(notes[0].start))
        while first > p + 1e-6:
            first -= grid.beats_per_bar
        while first + grid.beats_per_bar <= p:
            first += grid.beats_per_bar
    return first


def to_json(qnotes: list[QNote]) -> list[dict]:
    return [asdict(n) for n in qnotes]
