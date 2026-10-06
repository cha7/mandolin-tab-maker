"""Getting audio in: a YouTube URL or a local file, decoded to a 44.1 kHz stereo WAV."""

import hashlib
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf

SAMPLE_RATE = 44100  # what Demucs expects

_YOUTUBE_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})")


def is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def song_id(source: str) -> str:
    """A stable folder name for a song, so re-runs reuse the slow steps."""
    if is_url(source):
        m = _YOUTUBE_ID.search(source)
        if m:
            return m.group(1)
        return "url-" + hashlib.sha1(source.encode()).hexdigest()[:10]
    p = Path(source)
    return re.sub(r"[^A-Za-z0-9_-]+", "-", p.stem)[:40] + "-" + hashlib.sha1(
        str(p.resolve()).encode()).hexdigest()[:6]


def fetch(source: str, work: Path) -> Path:
    """Returns work/mix.wav, downloading and/or decoding the source if needed."""
    out = work / "mix.wav"
    if out.exists():
        return out
    work.mkdir(parents=True, exist_ok=True)
    if is_url(source):
        src = _download(source, work)
    else:
        src = Path(source)
        if not src.exists():
            raise FileNotFoundError(source)
    _decode(src, out)
    return out


def _download(url: str, work: Path) -> Path:
    import yt_dlp

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(work / "download.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        (work / "title.txt").write_text(info.get("title", ""))
        return Path(ydl.prepare_filename(info))


def _decode(src: Path, out: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(src),
         "-vn", "-ac", "2", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(out)],
        check=True,
    )


def load(path: Path, mono: bool = False) -> tuple[np.ndarray, int]:
    """Audio as float32, shape (samples, channels), or (samples,) when mono."""
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if mono:
        y = y.mean(axis=1)
    return y, sr
