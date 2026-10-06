"""Melody extraction: pitch-track each melody-capable stem, follow whichever stem carries
the tune frame by frame, then cut the pitch curve into notes."""

from dataclasses import dataclass, asdict
from pathlib import Path

import librosa
import numpy as np
import scipy.ndimage
import torch
import torchcrepe

from .audio import load

CREPE_SR = 16000
HOP_S = 0.01  # 10 ms frames
FMIN, FMAX = 65.0, 2000.0  # C2 .. B6: any sung or played melody

# Melody-following knobs.
SILENCE_DB = -45.0     # stem frames quieter than this (relative to the stem's peak) can't be melody
UNVOICED_SCORE = 0.35  # a stem must beat this salience to be called the melody
SWITCH_COST = 1.5      # salience given up to change melody stem (avoids flicker)

# Note-segmentation knobs.
MIN_NOTE_S = 0.06
PITCH_JUMP = 0.6       # semitones away from the current note that start a new note...
JUMP_FRAMES = 3        # ...if they last this many frames
GAP_FRAMES = 3         # unvoiced frames that end a note


@dataclass
class Note:
    start: float       # seconds
    end: float
    midi: int          # as heard, tuning-corrected
    stem: str
    periodicity: float  # mean pitch-tracker confidence over the note (0..1)
    stability: float    # fraction of frames within half a semitone of `midi`


@dataclass
class Track:
    """The melody as a frame-level curve: which stem carries it and at what pitch."""
    times: np.ndarray        # (T,) seconds
    midi: np.ndarray         # (T,) float midi, nan where there's no melody
    periodicity: np.ndarray  # (T,) of the chosen stem, 0 where there's no melody
    stem: np.ndarray         # (T,) index into `stems`, -1 where there's no melody
    margin: np.ndarray       # (T,) salience of chosen stem minus the runner-up
    stems: list[str]
    tuning: float            # cents/100 the recording sits off A440


def pitch_track(stem_path: Path, cache: Path, model: str, device: str) -> dict:
    """CREPE pitch, periodicity and loudness for one stem, every 10 ms. Cached as .npz."""
    if cache.exists():
        return dict(np.load(cache))
    y, sr = load(stem_path, mono=True)
    y16 = librosa.resample(y, orig_sr=sr, target_sr=CREPE_SR)
    hop = int(CREPE_SR * HOP_S)
    audio = torch.from_numpy(y16)[None]
    pitch, periodicity = torchcrepe.predict(
        audio, CREPE_SR, hop, FMIN, FMAX, model=model, decoder=torchcrepe.decode.viterbi,
        return_periodicity=True, batch_size=1024, device=device, pad=True)
    pitch, periodicity = pitch[0].cpu().numpy(), periodicity[0].cpu().numpy()
    # Periodicity is noisy frame to frame; torchcrepe recommends a short median filter.
    periodicity = scipy.ndimage.median_filter(periodicity, size=3)
    rms = librosa.feature.rms(y=y16, frame_length=4 * hop, hop_length=hop, center=True)[0]
    n = min(len(pitch), len(rms))
    data = {"pitch": pitch[:n], "periodicity": periodicity[:n], "rms": rms[:n]}
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, **data)
    return data


def salience(track: dict) -> np.ndarray:
    """How strongly a stem presents a clear pitch in each frame (0..1)."""
    db = 20 * np.log10(track["rms"] + 1e-9)
    db -= np.percentile(db, 99)  # relative to the stem's own loud parts
    loud = np.clip((db - SILENCE_DB) / -SILENCE_DB, 0, 1)
    return track["periodicity"] * np.sqrt(loud)


def follow(tracks: dict[str, dict]) -> Track:
    """Pick, frame by frame, the stem carrying the melody (or none), with a Viterbi pass
    that charges SWITCH_COST per change so the choice doesn't flicker."""
    names = list(tracks)
    T = min(len(t["pitch"]) for t in tracks.values())
    sal = np.stack([salience(tracks[n])[:T] for n in names])     # (S, T)
    score = np.vstack([np.full((1, T), UNVOICED_SCORE), sal])  # state 0 = no melody
    S = score.shape[0]
    switch = SWITCH_COST * (1 - np.eye(S))
    # Leaving or entering silence is cheaper than swapping instruments mid-phrase.
    switch[0, :] *= 0.3
    switch[:, 0] *= 0.3
    best = score[:, 0].copy()
    back = np.zeros((S, T), dtype=np.int16)
    for t in range(1, T):
        cand = best[:, None] - switch  # from state i (rows) to j (cols)
        back[:, t] = cand.argmax(0)
        best = cand.max(0) + score[:, t]
    path = np.empty(T, dtype=np.int16)
    path[-1] = best.argmax()
    for t in range(T - 1, 0, -1):
        path[t - 1] = back[path[t], t]
    stem = path.astype(int) - 1

    midi = np.full(T, np.nan)
    per = np.zeros(T)
    for i, n in enumerate(names):
        on = stem == i
        midi[on] = librosa.hz_to_midi(tracks[n]["pitch"][:T][on])
        per[on] = tracks[n]["periodicity"][:T][on]
    srt = np.sort(sal, axis=0)
    margin = np.where(stem >= 0, srt[-1] - (srt[-2] if len(names) > 1 else 0), 0.0)

    voiced = stem >= 0
    tuning = 0.0
    if voiced.any():
        # Circular mean of the fractional part: how far the recording sits off A440.
        frac = midi[voiced] - np.round(midi[voiced])
        w = per[voiced]
        ang = np.angle(np.sum(w * np.exp(2j * np.pi * frac)))
        tuning = float(ang / (2 * np.pi))
    return Track(times=np.arange(T) * HOP_S, midi=midi, periodicity=per, stem=stem,
                 margin=margin, stems=names, tuning=tuning)


def onsets(stem_path: Path, cache: Path) -> np.ndarray:
    """Onset times (s) in a stem: needed to split repeated notes of the same pitch."""
    if cache.exists():
        return np.load(cache)
    y, sr = load(stem_path, mono=True)
    hop = int(sr * HOP_S)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop,
                                        backtrack=False, units="frames")
    t = frames * HOP_S
    np.save(cache, t)
    return t


def segment(track: Track, stem_onsets: dict[str, np.ndarray]) -> list[Note]:
    """Cut the melody curve into notes: at pitch changes, gaps, stem changes, and onsets
    that re-strike the same pitch."""
    midi = track.midi - track.tuning
    voiced = track.stem >= 0
    # Smooth vibrato and tracker jitter inside each voiced run.
    smooth = midi.copy()
    for a, b in _runs(voiced):
        if b - a >= 5:
            smooth[a:b] = scipy.ndimage.median_filter(midi[a:b], size=5, mode="nearest")

    spans = []  # (start_frame, end_frame) of candidate notes
    for a, b in _runs(voiced):
        # Split voiced runs where the stem changes.
        cuts = [a] + [t for t in range(a + 1, b) if track.stem[t] != track.stem[t - 1]] + [b]
        for s, e in zip(cuts, cuts[1:]):
            spans.extend(_split_on_pitch(smooth, s, e))

    notes = []
    min_frames = int(round(MIN_NOTE_S / HOP_S))
    for s, e in spans:
        stem = track.stems[track.stem[s]]
        for s2, e2 in _split_on_onsets(s, e, stem_onsets.get(stem), min_frames):
            if e2 - s2 < min_frames:
                continue
            seg = midi[s2:e2]
            pitch = int(np.round(np.median(seg)))
            notes.append(Note(
                start=float(track.times[s2]), end=float(track.times[e2 - 1] + HOP_S),
                midi=pitch, stem=stem,
                periodicity=float(np.mean(track.periodicity[s2:e2])),
                stability=float(np.mean(np.abs(seg - pitch) < 0.5))))
    return _merge_ties(notes)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) of each run of True, plus closing gaps shorter than GAP_FRAMES."""
    m = mask.copy()
    # Close short gaps: a dropout of a couple of frames isn't a new note.
    for a, b in _true_runs(~m):
        if b - a < GAP_FRAMES and a > 0 and b < len(m):
            m[a:b] = True
    return _true_runs(m)


def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def _split_on_pitch(midi: np.ndarray, a: int, b: int) -> list[tuple[int, int]]:
    out = []
    start = a
    ref = None
    t = a
    while t < b:
        if np.isnan(midi[t]):
            t += 1
            continue
        if ref is None:
            ref = midi[t]
        if abs(midi[t] - ref) > PITCH_JUMP:
            end = min(t + JUMP_FRAMES, b)
            window = midi[t:end]
            if len(window) == JUMP_FRAMES and np.all(np.abs(window - ref) > PITCH_JUMP):
                out.append((start, t))
                start, ref = t, np.nanmedian(window)
                t = end
                continue
        else:
            # Track the note's pitch as it settles (attack transients sit off-pitch).
            ref = np.nanmedian(midi[start:t + 1])
        t += 1
    out.append((start, b))
    return out


def _split_on_onsets(s: int, e: int, onset_times, min_frames: int):
    if onset_times is None or e - s < 2 * min_frames:
        return [(s, e)]
    frames = np.round(onset_times / HOP_S).astype(int)
    inner = frames[(frames >= s + min_frames) & (frames <= e - min_frames)]
    cuts = [s]
    for f in inner:
        if f - cuts[-1] >= min_frames:
            cuts.append(int(f))
    cuts.append(e)
    return list(zip(cuts, cuts[1:]))


def _merge_ties(notes: list[Note]) -> list[Note]:
    """Fold a too-short sliver into the same-pitch note right before it."""
    out: list[Note] = []
    for n in notes:
        if out and out[-1].midi == n.midi and out[-1].stem == n.stem \
                and n.start - out[-1].end < 0.015 and (n.end - n.start) < MIN_NOTE_S * 1.5:
            out[-1].end = n.end
            continue
        out.append(n)
    return out


def to_json(notes: list[Note]) -> list[dict]:
    return [asdict(n) for n in notes]
