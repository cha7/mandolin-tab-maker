import numpy as np

from mtab.melody import Note
from mtab.rhythm import fixed_grid, make_grid, origin, quantize


def note(start, end, midi=60):
    return Note(start=start, end=end, midi=midi, stem="x", periodicity=0.9, stability=1.0)


def test_quantize_snaps_and_fills_short_gaps():
    grid = fixed_grid(bpm=120, beats_per_bar=4, start=0.0, end=4.0)  # 0.5 s per beat
    notes = [note(0.01, 0.2, 60), note(0.27, 0.45, 62), note(0.52, 0.9, 64)]
    q = quantize(notes, grid)
    assert [n.onset for n in q] == [0.0, 0.5, 1.0]
    assert [n.duration for n in q] == [0.5, 0.5, 0.75]
    assert all(n.residual < 0.2 for n in q)


def test_downbeat_phase_and_pickup():
    beats = np.arange(0, 20, 0.5)
    downbeats = beats[1::4]  # bars start on beat index 1, 5, 9...
    notes = [note(0.0, 0.4)]  # pickup on beat 0
    grid = make_grid(beats, downbeats, notes)
    assert grid.beats_per_bar == 4
    # Bar 1 starts one bar before the downbeat at index 1, so the pickup is in bar 1.
    assert origin(grid, notes) == -3


def test_triplet_grid_detected():
    beats = np.arange(0, 20, 0.6)
    downbeats = beats[::2]
    notes = [note(t, t + 0.15) for t in np.arange(0, 12, 0.2)]  # three per beat
    grid = make_grid(beats, downbeats, notes)
    assert grid.subdivision == 3
    assert grid.time_signature == "6/8"
