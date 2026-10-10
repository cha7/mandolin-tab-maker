# mandolin-tab-maker

Paste a YouTube link; it finds the melody and arranges it as a mandolin tab, with chord
names, a MusicXML file for MuseScore, a play-along preview, and a confidence rating for each
section.

It runs on your own computer: separating the instruments takes too much computing for a
website. [cha7j.com/mandolin-tab-maker](https://cha7j.com/mandolin-tab-maker) explains it and
has the same instructions as below (that page is its own repo, `mandolin-tab-maker-info`).

## Run it on your computer

**Mac** (needs an Apple chip, M1 or newer. To check: Apple menu → About This Mac → *Chip*):
1. **Install Node.js.** Go to [nodejs.org](https://nodejs.org), download the version marked
   **LTS**, open it and click through the installer.
2. **Download the app:** [mandolin-tab-maker.zip](https://github.com/cha7/mandolin-tab-maker/archive/refs/heads/main.zip).
   Double-click it in Downloads to unzip it.
3. Open **Terminal**: press ⌘ Space, type *Terminal*, press Enter. Type `cd` and a space, drag
   the **mandolin-tab-maker-main** folder onto the Terminal window, and press Enter.
4. Type `npm install` and press Enter. The first time takes 10 to 30 minutes while it
   downloads the music tools. It's done when you can type again.
5. Type `npm run dev` and press Enter, then open [localhost:8765](http://localhost:8765) in
   your web browser. Keep the window open while you use it.

**Windows PC** (Windows 10 or 11):
1. **Install Node.js.** Go to [nodejs.org](https://nodejs.org), download the version marked
   **LTS**, open it and click through the installer.
2. **Download the app:** [mandolin-tab-maker.zip](https://github.com/cha7/mandolin-tab-maker/archive/refs/heads/main.zip).
   In Downloads, right-click it, choose **Extract All**, then **Extract**.
3. Open the extracted **mandolin-tab-maker-main** folder (the one with *README.md* in it).
   Click the address bar at the top, type `cmd`, and press Enter. A black Command Prompt
   window opens.
4. Type `npm install` and press Enter. The first time takes 10 to 30 minutes while it
   downloads the music tools. It's done when you can type again.
5. Type `npm run dev` and press Enter, then open [localhost:8765](http://localhost:8765) in
   your web browser. Keep the window open while you use it.

**Next time:** open Terminal (Mac) or Command Prompt (PC) in the folder the same way, type
`npm run dev`, and go to [localhost:8765](http://localhost:8765). To stop it, close the
window. Your tabs are saved in the **out** folder inside the app's folder.

A tab takes a minute or two on a computer with an NVIDIA graphics card, and 10 to 20 minutes
on others. Tabs of copyrighted songs are for your own practice, not for sharing.

(The same steps are on cha7j.com/mandolin-tab-maker, in the `mandolin-tab-maker-info` repo's
`src/app/page.js`: keep the two in step.)

---

The rest is for working on the app.

**Status: Phase 0.** The point of this phase is to measure how often the output is right.
It's local only: nothing here is deployed.

```
Browser ─► Next.js app (127.0.0.1:8765) ─► mtab run <url>  (Python engine, one job at a time)
              src/app, src/data/jobs.js        └─ work/<song>/ cache, out/<song>/ tab + report
```

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
npm run dev       # http://localhost:8765
npm test
```

`npm install` installs the app's packages, then [uv](https://docs.astral.sh/uv/) into your
user folder if it's missing, then the Python environment into `.venv`: Python 3.11, PyTorch
(the CUDA build on Windows and Linux, PyPI's on Macs), Demucs, CREPE and a bundled ffmpeg
(`pyproject.toml`). It needs no git or Python of your own. The first time downloads several GB.
Set `MTAB_SKIP_SETUP=1` to skip the Python part; `npm run setup:python` runs it again.

| command | does |
|---|---|
| `npm run dev` | the app at http://localhost:8765 |
| `npm run build` / `npm start` | a production build, then serve it at http://localhost:8765 |
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
| `src/app/` | The page (`page.js`, `TabMaker.jsx`, `page.module.css`), the layout, and JSON routes in `api/`: `jobs` (start), `jobs/[id]` (progress, then the tab), `history`, `files/[id]/[file]` |
| `src/data/jobs.js` | The job queue, songs made before and their files. Routes call these, never the engine |
| `src/lib/local.js` | `localOnly(request)`: every route calls it first (Host and Origin checks) |
| `src/lib/tab.js` | Reading the engine's tab.txt and report for the page |
| `mtab/` | The Python engine and its CLI (below); `tests/` is its pytest suite |

**The engine is the CLI.** A job runs `mtab run <youtube url> <flags>` as a child process
(through `scripts/uv.cjs`), one at a time since the GPU can't share. Its timestamped
`[HH:MM:SS]` lines become the job's log, and `out/<song>/` its result; the song id is the
YouTube video id. To offer a new engine option on the page: add the CLI flag, then its check
in `optionArgs()` and a control in `TabMaker.jsx`.

### Design

Styles come from [`@cha7/feather-heavy-design-system`](https://github.com/cha7/feather-heavy-design-system):
forest-green tokens, light and dark mode, and a few components. Its README
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
