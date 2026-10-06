"""Source separation with Demucs' 6-stem model (drums, bass, other, vocals, guitar, piano)."""

from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from .audio import SAMPLE_RATE, load

MODEL = "htdemucs_6s"
# Stems that can carry a melody. Bass and drums never do (for our purposes).
MELODY_STEMS = ("vocals", "guitar", "piano", "other")
# Stems that carry the harmony, for chord detection.
HARMONY_STEMS = ("bass", "guitar", "piano", "other")


def device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def separate(mix_path: Path, work: Path) -> dict[str, Path]:
    """Writes work/stems/<name>.wav for every stem and returns their paths. Cached."""
    stem_dir = work / "stems"
    from demucs.pretrained import get_model

    model = get_model(MODEL)
    paths = {name: stem_dir / f"{name}.wav" for name in model.sources}
    if all(p.exists() for p in paths.values()):
        return paths

    from demucs.apply import apply_model

    y, sr = load(mix_path)
    assert sr == SAMPLE_RATE == model.samplerate
    wav = torch.from_numpy(y.T.copy())  # (channels, samples)
    # Demucs normalizes its input this way in its own CLI.
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    wav = (wav - mean) / std
    with torch.no_grad():
        out = apply_model(model, wav[None], device=device(), shifts=1, split=True,
                          overlap=0.25, progress=True)[0]
    out = out * std + mean
    stem_dir.mkdir(parents=True, exist_ok=True)
    for name, source in zip(model.sources, out):
        sf.write(str(paths[name]), source.cpu().numpy().T.astype(np.float32), sr)
    return paths
