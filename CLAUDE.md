@AGENTS.md

# mandolin-tab-maker

A local-only app: a Python engine and server (`mtab app`) with a Next.js 16 page exported to static files, styled with the Feather Heavy design system: paste a YouTube link, get a mandolin tab with a confidence rating per section. It runs on people's own computers, installed by one pasted line (`install.sh` / `install.ps1`, which need no Node.js), and is never deployed. The page explaining it and how to install it (cha7j.com/mandolin-tab-maker) is a separate repo, `mandolin-tab-maker-info`. README.md explains every part and lists every command; read the relevant section before changing one. Read `AGENTS.md` before writing Next code (this Next version has breaking changes).

## Layout

- `src/app/` the page (`page.js`, `TabMaker.jsx`, `page.module.css`, `Mandolin.jsx`) and layout; `src/lib/tab.js` (reading tab.txt). No server code: `next build` is a static export into `mtab/web/` (**committed**; rebuild and commit it after any `src/` change), `next dev` forwards `/api` to the Python app (`next.config.mjs`, `scripts/dev.mjs`).
- `mtab/app.py` `mtab app`: serves `mtab/web/` and the JSON API (`/api/jobs`, `/api/jobs/<id>`, `/api/history`, `/api/files/<id>/<file>`), the job queue and every history and output-file read; it imports no PyTorch.
- `mtab/` the Python engine (audio, separation, melody, rhythm, harmony, mandolin, report, render) and its CLI `mtab run|eval|app`; `tests/` its pytest suite. Python deps in `pyproject.toml`, run through uv (`scripts/uv.cjs`).
- `install.sh` (Mac, Linux) / `install.ps1` (Windows): download `main` into `~/MandolinTabMaker`, uv, `uv sync --no-dev`, a Desktop launcher (`assets/mandolin.ico`), then start the app. Re-running updates and must keep `out/`, `work/`, `.venv/`.
- Styles: `@cha7/feather-heavy-design-system`, **vendored** in `src/vendor/feather-heavy/` (tokens `--fh-*`, classes `.fh-*`, `ThemeScript`/`ThemeToggle`); the mark is our own `src/app/Mandolin.jsx` (same API as `Feather`; `icon.svg` is the same drawing), imported as `@/vendor/feather-heavy/...` in `src/app/layout.js`. Never edit the copy; `npm run ui:update` refreshes it (`scripts/ui-vendor.mjs`).
- `scripts/` - `dev.mjs` (`npm run dev`), `setup-python.cjs` (uv + Python env), `uv.cjs`, `ui-vendor.mjs`, `check-node.cjs`.
- `work/<song>/` caches the slow steps; `out/<song>/` holds tab.txt, tab.musicxml, preview.wav, report.json, notes.json. Both gitignored.

## Rules

- **Running it needs no Node.js:** only uv and Python. Node 22 (`.nvmrc`) is for working on the page; every npm script that starts Node checks it first (`scripts/check-node.cjs`). Python 3.11 via uv.
- **The engine is the CLI.** `mtab app` runs `python -m mtab.cli run <url> <flags>` as a child process, one job at a time (the GPU can't share), and reads its timestamped `[HH:MM:SS]` stdout lines as the job log and `out/<song>/` as the result. Keep that contract: a new engine option gets a CLI flag, then a check in `option_args()` (`mtab/app.py`) and a control in `TabMaker.jsx`. The song id is the YouTube video id (`video_id()` matches `mtab/audio.py`'s pattern).
- **Local only, never deployed:** no Terraform, Lambda or hosting code here. The run-it steps exist twice, in README.md: Run it on your computer and in `mandolin-tab-maker-info`'s `src/app/page.js` - change both together (including the install lines), and keep them for non-technical readers (no git, no tokens, no Python, no Node), for both Mac and Windows. `install.ps1` stays ASCII and pauses on errors.
- **No token to run it:** anyone can `npm install` without GitHub Packages access, so the design system stays vendored. Never add a `@cha7/*` dependency.
- **Cross-platform:** it must install on Windows, Apple-chip Macs and Linux: PyTorch comes from the CUDA index except on macOS (`pyproject.toml` markers), and no dependency may need git (`beat-this` is a commit archive).
- **YouTube links only** on the page. The app downloads whatever it's given, so it listens on 127.0.0.1 and every API request passes `refused()` first (Host and Origin checks). POSTs take JSON only.
- **Output files:** the API serves only the names in `FILES` (`mtab/app.py`) from a validated song id; static files never leave `mtab/web/`.
- **Styles:** colors only from `--fh-*` role tokens (never hex, never `--fh-green-*`/`--fh-gray-*` palette, never a dark-mode media query - tokens switch themselves). Reuse `.fh-*` classes before writing new CSS; page-specific CSS goes in a module next to the page. The theme lives in `localStorage`.
- **Secrets** stay out of the repo (`.env.local` is gitignored); the app needs none.
- **Copyright:** tabs and reference scores of copyrighted songs are for personal study; never commit `out/`, `work/` or `eval/refs/`.

## Commands

`npm run dev` (page at http://localhost:3000, API on :8765), `npm run build` (export into `mtab/web/`; commit it), `npm run app` (`mtab app`, as people run it: http://localhost:8765), `npm test` (Vitest, then pytest), `npm run test:fast` (skips the slow end-to-end test), `npm run tab -- <url or file>`, `npm run eval`, `npm run setup:python` (uv + Python env), `npm run ui:update` (needs a GitHub Packages token, then commit `src/vendor/`). npm only.
