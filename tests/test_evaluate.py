import numpy as np

from mtab.evaluate import compare


def test_finds_alignment_through_key_octave_and_offset():
    rng = np.random.default_rng(1)
    on = np.cumsum(rng.choice([0.5, 1.0], 40)) - 0.5
    ref = np.stack([on, on + 0.5, rng.integers(60, 72, 40)], 1)
    # Estimate: 5 semitones + an octave up, 7 bars of intro, played twice through.
    est1 = ref.copy()
    est1[:, :2] += 28
    est1[:, 2] += 17
    est2 = est1.copy()
    est2[:, :2] += on[-1] + 1
    est = np.vstack([est1, est2])
    r = compare(est, ref)
    assert r["f1"] == 1.0
    assert r["offset_ql"] == 28


def test_wrong_notes_lower_the_score():
    on = np.arange(32, dtype=float)
    ref = np.stack([on, on + 1, 60 + (np.arange(32) % 7)], 1)
    est = ref.copy()
    est[::4, 2] += 1
    assert 0.6 < compare(est, ref)["f1"] < 0.9
