"""Fitting the melody to a mandolin: choosing the octave (or key), then a string and fret
for every note."""

import numpy as np

from .rhythm import QNote

# Open strings, as tabs list them top to bottom: E5, A4, D4, G3 (GDAE tuning).
OPEN = {1: 76, 2: 69, 3: 62, 4: 55}
MAX_FRET = 15
LOWEST, HIGHEST = OPEN[4], OPEN[1] + MAX_FRET   # G3 .. G6
COMFORT_TOP = OPEN[1] + 7                        # B5: the top of first position

# Keys that sit well on a mandolin (lots of open strings), by tonic pitch class.
FRIENDLY_MAJOR = {7, 2, 9, 0, 5}   # G D A C F
FRIENDLY_MINOR = {4, 11, 9, 2}     # Em Bm Am Dm


def choose_shift(midi: list[int], tonic: int, mode: str, key_change: bool) -> int:
    """Semitones to move the melody by. Octaves only, unless key_change allows moving
    it to a mandolin-friendly key."""
    if not midi:
        return 0
    m = np.array(midi)
    shifts = range(-36, 37) if key_change else range(-36, 37, 12)
    best, best_cost = 0, float("inf")
    for s in shifts:
        p = m + s
        out = np.mean((p < LOWEST) | (p > HIGHEST))
        high = np.mean(p > COMFORT_TOP)
        center = abs(np.median(p) - 69) / 12
        cost = 10 * out + 2 * high + 0.5 * center
        if key_change:
            friendly = FRIENDLY_MAJOR if mode == "major" else FRIENDLY_MINOR
            cost += 0 if (tonic + s) % 12 in friendly else 1.5
            cost += 0.02 * min(s % 12, 12 - s % 12)  # prefer small moves
        if cost < best_cost:
            best, best_cost = s, cost
    return best


def fit_range(notes: list[QNote], shift: int) -> int:
    """Applies the shift; folds any note still out of range by octaves. Returns how many
    notes had to be folded (they no longer match the original contour)."""
    folded = 0
    for n in notes:
        w = n.midi + shift
        if w < LOWEST or w > HIGHEST:
            folded += 1
            while w < LOWEST:
                w += 12
            while w > HIGHEST:
                w -= 12
        n.written = w
    return folded


def _unary(fret: int) -> float:
    if fret == 0:
        return 0.0
    # Fretted notes cost a little, and more beyond first position (fret 7, the pinky).
    return 0.2 + 0.05 * fret + 0.5 * max(0, fret - 7)


def _transition(a: tuple[int, int], b: tuple[int, int]) -> float:
    (sa, fa), (sb, fb) = a, b
    cost = 0.05 * abs(sa - sb)
    if fa and fb:
        d = abs(fa - fb)
        cost += 0.15 * max(0, d - 2) + 0.5 * max(0, d - 4)  # stretches, then shifts
    return cost


def assign_frets(notes: list[QNote]) -> None:
    """Chooses (string, fret) for each note by dynamic programming: cheap frets, open
    strings when they fit, and few position shifts."""
    if not notes:
        return
    cands = []
    for n in notes:
        c = [(s, n.written - o) for s, o in OPEN.items() if 0 <= n.written - o <= MAX_FRET]
        cands.append(c)
    cost = [np.array([_unary(f) for _, f in cands[0]])]
    back = []
    for i in range(1, len(notes)):
        prev, cur = cands[i - 1], cands[i]
        trans = np.array([[_transition(p, c) for c in cur] for p in prev])
        tot = cost[-1][:, None] + trans
        back.append(tot.argmin(0))
        cost.append(tot.min(0) + np.array([_unary(f) for _, f in cur]))
    j = int(cost[-1].argmin())
    for i in range(len(notes) - 1, -1, -1):
        notes[i].string, notes[i].fret = cands[i][j]
        if i:
            j = int(back[i - 1][j])
