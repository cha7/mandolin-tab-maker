# mandolin-tab-maker

Paste a YouTube link; it finds the melody and arranges it as a mandolin tab, with chord
names, a MusicXML file for MuseScore, a play-along preview, and a confidence rating for each
section.

It runs on your own computer: separating the instruments takes too much computing for a
website. [cha7j.com/mandolin-tab-maker](https://cha7j.com/mandolin-tab-maker) explains it and
has the same instructions as below (that page is its own repo, `mandolin-tab-maker-info`).

## Run it on your computer

You copy one line, paste it, and wait. It downloads the app and the music tools (about
2 GB on a Mac, about 6 GB on a PC; 10 to 30 minutes), puts **Mandolin Tab Maker** on your
Desktop, and opens it in your web browser.

**Mac** (needs an Apple chip, M1 or newer. To check: Apple menu → About This Mac → *Chip*):
1. Open **Terminal**: press ⌘ Space, type *Terminal*, press Enter.
2. Paste this line and press Enter:
   ```sh
   curl -fsSL https://raw.githubusercontent.com/cha7/mandolin-tab-maker/main/install.sh | sh
   ```
   If your Mac asks whether Terminal may use your Desktop folder, click **Allow**.
3. When it's done, the app opens in your web browser. Keep the Terminal window open while
   you use it.

**Windows PC** (Windows 10 or 11):
1. Press **Windows key + R**. A small *Run* box opens.
2. Paste this line and press Enter:
   ```
   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/cha7/mandolin-tab-maker/main/install.ps1 | iex"
   ```
3. When it's done, the app opens in your web browser. Keep the black window open while you
   use it.

**Next time:** double-click **Mandolin Tab Maker** on your Desktop. To stop it, close its
window. Your tabs are saved in the **out** folder inside the **MandolinTabMaker** folder in
your home folder. To update the app, paste the same line again (your tabs are kept).

A tab takes a minute or two on a computer with an NVIDIA graphics card, and 10 to 20 minutes
on others. Tabs of copyrighted songs are for your own practice, not for sharing.

(The same steps are on cha7j.com/mandolin-tab-maker, in the `mandolin-tab-maker-info` repo's
`src/app/page.js`: keep the two in step. Both link to `install.sh` / `install.ps1` below.)

---

The rest is for working on the app.

**Status: Phase 0.** The point of this phase is to measure how often the output is right.
It's local only: nothing here is deployed.

```
Browser ─► mtab app (Python, 127.0.0.1:8765) ─► mtab run <url>  (child process, one job at a time)
           page from mtab/web/, JSON API          └─ work/<song>/ cache, out/<song>/ tab + report
```

Running the app needs only Python, set up by [uv](https://docs.astral.sh/uv/): `mtab app`
serves the page and its API. The page is a Next.js static export, built by `npm run build`
into `mtab/web/` and **committed**, so people who install the app never need Node.js. Node is
only for working on the page.

## Install scripts

`install.sh` (Mac, Linux) and `install.ps1` (Windows) are what the steps above run, straight
from this repo's `main` branch (so the repo must be public). Each one:
1. downloads `main` as an archive into `~/MandolinTabMaker` (`MTAB_DIR` to change it),
   merging over what's there, so `out/`, `work/` and `.venv/` survive an update;
2. installs uv into the user folder if it's missing;
3. runs `uv sync --no-dev`: Python 3.11, PyTorch (the CUDA build on Windows and Linux, PyPI's
   on Macs), Demucs, CREPE, yt-dlp and a bundled ffmpeg (`pyproject.toml`);
4. writes a launcher (`Mandolin Tab Maker.command` / `.bat`, running `uv run --no-dev mtab app`)
   and puts it (Mac) or a shortcut to it with `assets/mandolin.ico` (Windows) on the Desktop;
5. starts the app, which opens the browser.

They need no git, Node.js or Python of your own. `install.ps1` must stay ASCII (it runs
through `irm | iex`) and pauses on an error so the window doesn't close before it's read.

## Quick start

**On your machine:**
- Node 22 or newer (`nvm use`; every npm script checks it first) and npm.
- An NVIDIA GPU if you have one (separation and pitch tracking are about 10x faster); CPU
  works, using CREPE's small model. Macs: Apple chip only (PyTorch has no Intel Mac builds).
- **No token to run it.** Only updating the design system needs GitHub Packages
  (`@cha7/feather-heavy-design-system`): a classic personal access token with
  `read:packages`, in your *user* `~/.npmrc` (never the project's):
  ```bash
  echo "//npm.pkg.github.com/:_authToken=ghp_YOUR_TOKEN" >> ~/.npmrc
  ```

**Then:**

```bash
npm install
npm run dev       # the page at http://localhost:3000, the Python app on :8765
npm test
```

`npm install` installs the page's packages, then uv into your user folder if it's missing,
then the Python environment into `.venv` (the same as the install scripts, plus pytest). Set
`MTAB_SKIP_SETUP=1` to skip the Python part; `npm run setup:python` runs it again.

| command | does |
|---|---|
| `npm run dev` | the page with hot reload at http://localhost:3000, forwarding `/api` to `mtab app --dev` on :8765 (`scripts/dev.mjs` starts both) |
| `npm run build` | export the page into `mtab/web/`. **Commit it** after any change to `src/`: it's what everyone else runs |
| `npm run app` | `mtab app`: the app as people run it, at http://localhost:8765 (opens the browser; `-- --no-browser`, `-- --port <n>`) |
| `npm run tab -- <url or file> [options]` | one tab from the command line (`npm run tab -- --help`) |
| `npm run eval` | score `eval/songs.yaml` against reference melodies |
| `npm test` / `npm run test:fast` | Vitest, then pytest / the same without the slow end-to-end test |
| `npm run setup:python` | install or update uv and the Python environment |
| `npm run uv -- <args>` | run uv directly (e.g. `npm run uv -- add librosa`) |
| `npm run ui:update` | the latest Feather Heavy design system, copied into `src/vendor/` (then look at the page in both themes and commit it) |

## Use

**The app:** paste a YouTube link and click Make tab; it takes YouTube links only. It shows
progress and then the tab, a playback preview and MusicXML/text downloads. It shows only
confident sections unless you switch to Everything. Songs made before are listed at the
bottom and reopen instantly; tick "Re-make" under Options to run one again with different
settings. It handles one song at a time (others queue) and only listens on 127.0.0.1, since
it downloads whatever link it's given.

**Command line:**

```sh
npm run tab -- "https://www.youtube.com/watch?v=..."   # or a local .mp3/.wav (for eval)
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

## Building the app

| Where | What |
|---|---|
| `src/app/` | The page (`page.js`, `TabMaker.jsx`, `page.module.css`, `Mandolin.jsx` the mark), the layout |
| `src/lib/tab.js` | Reading the engine's tab.txt and report for the page |
| `next.config.mjs` | `next build`: a static export into `mtab/web/` (not Next's default `out/`, where the tabs are). `next dev`: a normal dev server forwarding `/api` to :8765 (static exports don't allow rewrites) |
| `mtab/app.py` | `mtab app`: serves `mtab/web/` and the JSON API (`POST /api/jobs` start, `GET /api/jobs/<id>` progress then the tab, `/api/history`, `/api/files/<id>/<file>`); the job queue, songs made before and their files |
| `mtab/` | The Python engine and its CLI (below); `tests/` is its pytest suite (`test_app.py` for the server) |
| `install.sh`, `install.ps1` | The install scripts (above) |

**The engine is the CLI.** A job runs `python -m mtab.cli run <youtube url> <flags>` as a
child process, one at a time since the GPU can't share. Its timestamped `[HH:MM:SS]` lines
become the job's log, and `out/<song>/` its result; the song id is the YouTube video id. To
offer a new engine option on the page: add the CLI flag, then its check in `option_args()`
(`mtab/app.py`) and a control in `TabMaker.jsx`, then `npm run build`.

**Local only.** The app downloads whatever link it's given, so it listens on 127.0.0.1, and
every API request passes `refused()` first: the Host must be localhost (blocks DNS
rebinding), and a POST's Origin must be the app's own page (blocks other websites). POSTs
take JSON only, and files are served only from `FILES` for a validated song id. The server
imports no PyTorch, so it starts in a moment.

### Design

Styles come from [`@cha7/feather-heavy-design-system`](https://github.com/cha7/feather-heavy-design-system):
forest-green tokens (one setting recolors them), light and dark mode, and a few components. Its README
(`src/vendor/feather-heavy/README.md`) has the full token and class list.

**It's vendored**, unlike the other cha7 apps: a copy lives in `src/vendor/feather-heavy/`
and the app imports from there (`@/vendor/feather-heavy/...`), because installing from
GitHub Packages always needs a token, and people downloading this app don't have one.
`npm run ui:update` installs the latest (with your token) and refreshes the copy
(`scripts/ui-vendor.mjs`). Don't edit the copy: change the design system and update.

- **Colors come from tokens, never hex:** `var(--fh-surface)`, `var(--fh-text-muted)`,
  `var(--fh-accent)`, `var(--fh-danger)`, ... Each one switches with the theme by itself, so
  the app needs no dark-mode CSS. Confidence: `--fh-success` (high), `--fh-warning`
  (medium), `--fh-danger` (low), `--fh-line-strong` (no melody).
- **Components are classes** on plain HTML: `fh-card`, `fh-button fh-button--primary`,
  `fh-alert fh-alert--danger`, `fh-label`, `fh-field` with `fh-input`/`fh-select`. Page
  layout goes in `src/app/page.module.css`.
- **The app's color:** `FH_HUE` in `.env` (committed, like `mtab/web/`), 0–359 around the
  color wheel: `156` forest (the default), `200` teal, `245` Puget Sound blue, `285` dusk,
  `330` heather, `30` terracotta, `75` ochre. The accent and the tinted grays follow it in
  both themes; the confidence colors don't. `next.config.mjs` reads it at build time and
  `layout.js` sets it on `<html>`: `npm run build` and commit after changing it.
- **Theme:** `src/app/layout.js` has `<ThemeScript />` in `<head>` and `<ThemeToggle />` in
  the masthead, with `<Mandolin />` (`src/app/Mandolin.jsx`, the same drawing as `icon.svg`) as
  the mark in place of the design system's Feather; the choice is kept in `localStorage`.
- **Updating:** `npm run ui:update`, then look at the page in both themes and commit
  `src/vendor/feather-heavy/`.

## How the engine works

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
- Hosting the engine would be a separate piece of work: a GPU worker, plus access control,
  since tabs of copyrighted songs aren't for publishing. YouTube also often refuses
  datacenter IPs.
