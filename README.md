# mandolin-tab-maker

Give it a recording (a YouTube URL or an audio file); it finds the melody and arranges it as
a mandolin tab, with chord names and a confidence rating for each section.

**Status: Phase 0, a local experiment.** The point of this phase is to measure how often the
output is right before building anything to host. Nothing here is deployed.

## Setup

Needs Node 18+ and npm. Then:

```sh
npm install
```

That installs [uv](https://docs.astral.sh/uv/) into your user folder if it's missing, then
the Python environment into `.venv`: Python 3.11, PyTorch, Demucs, CREPE and a bundled
ffmpeg (defined in `pyproject.toml`; there are no npm packages). The first time downloads
several GB. Set `MTAB_SKIP_SETUP=1` to skip it; `npm run setup` runs it again.

An NVIDIA GPU is used if present (separation and pitch tracking are about 10x faster);
CPU works, using CREPE's small model.

| command | does |
|---|---|
| `npm start` (or `npm run ui`) | the web page at http://localhost:8765 |
| `npm run tab -- <url or file> [options]` | one tab from the command line (`npm run tab -- --help`) |
| `npm run eval` | score `eval/songs.yaml` against reference melodies |
| `npm test` / `npm run test:fast` | all tests / skip the slower end-to-end test |
| `npm run setup` | install or update uv and the Python environment |
| `npm run uv -- <args>` | run uv directly (e.g. `npm run uv -- add librosa`) |

## Use

**Web page:**

```sh
npm start             # then open http://localhost:8765
```

Paste a YouTube link and click Make tab, or upload (or drag in) any video or audio
file, or pick a video from Google Photos (below). The page shows progress and then the tab, a
playback preview and MusicXML/text downloads. It shows only confident sections
unless you switch to Everything. Songs made before are listed at the bottom and reopen
instantly; tick "Re-make" under Options to run one again with different settings. It
handles one song at a time (others queue) and only listens on localhost, since it
downloads whatever link it's given.

**Google Photos:** a `photos.google.com/photo/...` link can't be used directly: it only
opens when you're signed in, and Google's API no longer lets apps fetch library items by
link or ID. Instead the page signs you in to Google (read-only access to what you pick)
and opens Google's own Photos picker, where you choose the video. One-time setup:

1. In Google Cloud Console, use an OAuth client of type "Web application" in a project
   with the **Photos Picker API** enabled (the photos-picker sample app's client works).
2. Add `http://localhost:8765/auth/google/callback` to its **Authorized redirect URIs**.
3. Copy `.env.example` to `.env.local` (gitignored) and fill in `GOOGLE_CLIENT_ID` and
   `GOOGLE_CLIENT_SECRET`, then restart `npm start`.

The sign-in is held in memory only, so you sign in again after a restart. Uploads and
picked videos are saved in `work/uploads/`.

**Command line:**

```sh
npm run tab -- "https://www.youtube.com/watch?v=..."   # or a local .mp3/.wav
```

Writes `out/<song>/`:

| file | what |
|---|---|
| `tab.txt` | ASCII tab with chord names and each 4-bar section's confidence |
| `tab.musicxml` | notation with rhythm, key, chords and string/fret marks; open in MuseScore (Add → linked staff → Tablature for a tab staff) |
| `preview.wav` | the tab played back over the recording: the fastest way to hear what's wrong |
| `report.json` | per-bar confidence evidence and a summary |
| `notes.json` | the quantized notes, for `mtab eval` |

Useful options: `--stem vocals|guitar|piano|other` (force the melody source),
`--key-change` (move to a mandolin-friendly key, not just octaves), `--bpm 120
--beats-per-bar 4` (skip beat tracking), `--grid 3` (triplets/compound time),
`--no-separate` (input is already a solo melody).

Slow steps are cached in `work/<song>/`, so re-running after changing later steps takes
seconds. Delete a song's `work/` folder to start over.

## How it works

1. **Audio**: yt-dlp download, decoded with a bundled ffmpeg (`mtab/audio.py`).
2. **Separation**: Demucs `htdemucs_6s` into vocals, guitar, piano, other, bass, drums
   (`separate.py`).
3. **Melody**: CREPE pitch tracking on each melody-capable stem; a Viterbi pass picks, frame
   by frame, which stem carries the tune (so a melody handed from whistle to banjo is
   followed); the pitch curve is cut into notes at pitch changes and re-strikes
   (`melody.py`).
4. **Rhythm**: beat_this beats and downbeats; notes are snapped to a 16th or triplet grid,
   recording how far off-grid each was (`rhythm.py`).
5. **Harmony**: chords per half-bar by chroma template matching on the accompaniment
   stems; key by Krumhansl profiles (`harmony.py`).
6. **Mandolin**: octave (or key) shift into range, then string and fret for each note by
   dynamic programming favoring first position and open strings (`mandolin.py`).
7. **Confidence**: per bar, the pitch tracker's confidence × how clearly one stem leads ×
   how well the written notes match the heard pitch × how close onsets sat to the grid
   (`report.py`). The high/medium/low thresholds are placeholders until calibrated.

## Phase 0: measuring efficacy

```sh
cp eval/songs.example.yaml eval/songs.yaml   # add 10-20 songs with reference melodies
npm run eval
```

For each song, prints note F1/precision/recall against the reference, plus the
tool's own confidence. Scoring is in beats, ignores octave and key (the tab may be
transposed), searches for where the reference starts in the recording, and counts a note
right if its pitch class matches and its onset is within a 16th (`evaluate.py`).

What to look for:
- **Is F1 high when the melody is clear?** Solo or lead-instrument recordings should reach
  about 0.8 or higher. If not, the approach has a problem; stop here.
- **Does confidence track F1?** The gate only works if high-confidence sections are
  actually right. Plot section confidence against correctness and set `HIGH`/`MEDIUM` in
  `report.py` from that.

Tests (`npm test`) include an end-to-end round trip: a synthesized test tune goes
through the real pitch tracker, quantizer and fret choice and must score F1 ≥ 0.9.

## Findings so far

**Outer Wilds theme** (`Xpkc-NU1KA0`, 2.5 min, 1.5 min to process on a GTX 1070):
- About a third of the song comes out as rest. In those passages the tune is played on
  plucked or strummed instruments that Demucs leaves inside a *polyphonic* stem (the
  "other" stem shows the chord tones of A major at once). CREPE tracks one line at a time,
  so it correctly reports no confidence there, and its pitch output means nothing.
- Where a single line does stand out, notes come through, but repeated pedal and
  rhythm notes from the accompaniment get mistaken for melody. Bars rated "high" there
  still need checking against `preview.wav`.

**Next experiment** suggested by this: a polyphonic note transcriber (e.g. Basic Pitch) on
the stems, then pick the melody line from the notes (highest voice with continuity
and a penalty for repeated pedal notes), instead of a single-line pitch tracker. Compare
both modes with `mtab eval`.

## Notes

- Downloading from YouTube is against its terms of service; this is for personal, local
  experiments. Tabs of copyrighted songs are for the requester's own study, not to publish.
