"""Synthesize a known tune, run the real pitch tracking -> tab steps, and score it."""

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from mtab import pipeline
from mtab.evaluate import compare, load_estimate, load_reference
from mtab.render import _pluck

FIXTURE = Path(__file__).parent / "fixtures" / "test-tune.abc"
BPM = 100


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    ref = load_reference(FIXTURE)
    sr = 44100
    lead_in = 1.3  # seconds of silence: bar 1 shouldn't have to start at t=0
    beat = 60 / BPM
    y = np.zeros(int((lead_in + ref[-1, 1] * beat + 1) * sr))
    rng = np.random.default_rng(0)
    for on, end, midi in ref:
        n = _pluck(int(midi), (end - on) * beat * 0.95, sr, rng)
        i = int((lead_in + on * beat) * sr)
        y[i:i + len(n)] += n
    wav = tmp / "tune.wav"
    sf.write(wav, np.stack([y, y], 1).astype(np.float32), sr)
    opts = pipeline.Options(separate=False, bpm=BPM, beats_per_bar=4)
    summary = pipeline.run(str(wav), opts, tmp / "work", tmp / "out")
    return ref, tmp / "out" / summary["song_id"], summary


def test_melody_round_trips(run):
    ref, out, _ = run
    r = compare(load_estimate(out), ref)
    assert r["f1"] >= 0.9, r


def test_outputs_written(run):
    _, out, summary = run
    for f in ("tab.txt", "tab.musicxml", "preview.wav", "report.json", "notes.json"):
        assert (out / f).exists()
    assert summary["written_key"] == "D"
    assert summary["shift"] == 0
    report = json.loads((out / "report.json").read_text())
    assert report["sections"][0]["label"] == "high"
