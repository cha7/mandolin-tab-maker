"""Output: an ASCII tab, MusicXML (notation + chords + string/fret marks) and a preview."""

from pathlib import Path

import numpy as np
import scipy.signal
import soundfile as sf

from .harmony import NAMES
from .mandolin import OPEN
from .report import Section
from .rhythm import Grid, QNote

BARS_PER_LINE = 4
STRING_NAMES = {1: "E", 2: "A", 3: "D", 4: "G"}


def transpose_chord(name: str, shift: int) -> str:
    minor = name.endswith("m")
    root = name[:-1] if minor else name
    pc = (NAMES.index(root) + shift) % 12
    return NAMES[pc] + ("m" if minor else "")


def ascii_tab(notes: list[QNote], grid: Grid, chords: list[tuple[float, str]],
              secs: list[Section], n_bars: int, header: list[str]) -> str:
    bpb, sub = grid.beats_per_bar, grid.subdivision
    steps = bpb * sub
    cell = 2 if sub == 4 else 3  # characters per grid step
    width = steps * cell
    label = {}
    for s in secs:
        for b in range(s.first_bar, s.last_bar + 1):
            label[b] = s.label
    lines = list(header) + [""]
    for first in range(0, n_bars, BARS_PER_LINE):
        bars = range(first, min(first + BARS_PER_LINE, n_bars))
        chord_row = [" "] * (len(bars) * (width + 1) + 1)
        rows = {s: ["|"] for s in STRING_NAMES}
        for j, b in enumerate(bars):
            cells = {s: ["-"] * width for s in STRING_NAMES}
            for n in notes:
                if b * bpb <= n.onset < (b + 1) * bpb:
                    col = int(round((n.onset - b * bpb) * sub)) * cell
                    txt = str(n.fret)
                    for k, ch in enumerate(txt):
                        if col + k < width:
                            cells[n.string][col + k] = ch
            for s in STRING_NAMES:
                rows[s].extend(cells[s] + ["|"])
            for pos, name in chords:
                if b * bpb <= pos < (b + 1) * bpb:
                    col = 1 + j * (width + 1) + int(round((pos - b * bpb) * sub)) * cell
                    for k, ch in enumerate(name):
                        if col + k < len(chord_row):
                            chord_row[col + k] = ch
        conf = ", ".join(sorted({label.get(b + 1, "rest") for b in bars}))
        lines.append(f"bars {first + 1}-{bars[-1] + 1}  [confidence: {conf}]")
        if "".join(chord_row).strip():
            lines.append("  " + "".join(chord_row).rstrip())
        for s in STRING_NAMES:
            lines.append(STRING_NAMES[s] + " " + "".join(rows[s]))
        lines.append("")
    return "\n".join(lines)


def _m21_name(pc: int) -> str:
    return NAMES[pc].replace("b", "-")


def musicxml(notes: list[QNote], grid: Grid, chords: list[tuple[float, str]],
             tonic: int, mode: str, bpm: float, title: str, path: Path) -> None:
    from music21 import (articulations, duration, harmony, instrument, key, metadata,
                         meter, note, stream, tempo)

    q = grid.beat_ql
    part = stream.Part()
    part.insert(0, instrument.Mandolin())
    part.insert(0, meter.TimeSignature(grid.time_signature))
    part.insert(0, key.Key(_m21_name(tonic) if mode == "major" else _m21_name(tonic).lower()))
    part.insert(0, tempo.MetronomeMark(number=round(bpm), referent=duration.Duration(q)))
    for n in notes:
        m = note.Note(n.written)
        m.quarterLength = n.duration * q
        m.articulations.append(articulations.StringIndication(n.string))
        m.articulations.append(articulations.FretIndication(n.fret))
        part.insert(n.onset * q, m)
    for pos, name in chords:
        minor = name.endswith("m")
        root = _m21_name(NAMES.index(name[:-1] if minor else name))
        part.insert(pos * q, harmony.ChordSymbol(root + ("m" if minor else "")))
    score = stream.Score([part])
    score.metadata = metadata.Metadata(title=title)
    score.write("musicxml", fp=str(path))


def _pluck(midi: int, seconds: float, sr: int, rng) -> np.ndarray:
    """Karplus-Strong string; two slightly detuned strings, like a mandolin course."""
    out = np.zeros(int(seconds * sr))
    for detune in (-0.04, 0.04):
        f = 440 * 2 ** ((midi + detune - 69) / 12)
        N = max(2, int(round(sr / f)))
        x = np.zeros_like(out)
        x[:N] = rng.uniform(-1, 1, N)
        a = np.zeros(N + 2)
        a[0], a[N], a[N + 1] = 1, -0.497, -0.497
        out += scipy.signal.lfilter([1], a, x)
    fade = min(len(out), int(0.02 * sr))
    out[-fade:] *= np.linspace(1, 0, fade)
    return out * 0.15


def preview(notes: list[QNote], grid: Grid, bar1: int, mix: np.ndarray, mix_sr: int,
            with_mix: bool, path: Path) -> None:
    """The tab played back (as written, at the recording's timing), over the recording
    when the tab is in the same key, so you can hear where it goes wrong."""
    sr = 22050
    rng = np.random.default_rng(0)
    total = len(mix) / mix_sr
    out = np.zeros(int(total * sr) + sr)
    for n in notes:
        t0 = float(grid.time_at(bar1 + n.onset))
        t1 = float(grid.time_at(bar1 + n.onset + n.duration))
        if t0 < 0 or t0 >= total:
            continue
        y = _pluck(n.written, max(t1 - t0, 0.08) + 0.15, sr, rng)
        i = int(t0 * sr)
        y = y[: len(out) - i]
        out[i:i + len(y)] += y
    if with_mix:
        import librosa
        m = librosa.resample(mix.mean(axis=1) if mix.ndim == 2 else mix,
                             orig_sr=mix_sr, target_sr=sr)
        k = min(len(m), len(out))
        out[:k] += 0.35 * m[:k]
    out /= max(1.0, np.abs(out).max() / 0.95)
    sf.write(str(path), out.astype(np.float32), sr)
