import argparse
import json
import sys
from pathlib import Path

from . import evaluate, pipeline
from .separate import MELODY_STEMS


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mtab", description="Melody -> mandolin tab (Phase 0)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="make a tab from a YouTube URL or audio file")
    r.add_argument("source")
    r.add_argument("--stem", default="auto", choices=("auto",) + MELODY_STEMS,
                   help="force the melody stem instead of following the loudest clear line")
    r.add_argument("--key-change", action="store_true",
                   help="allow moving to a mandolin-friendly key (default: octaves only)")
    r.add_argument("--bpm", type=float, help="skip beat tracking; use this steady tempo")
    r.add_argument("--beats-per-bar", type=int)
    r.add_argument("--grid", type=int, choices=(3, 4),
                   help="steps per beat: 4 = sixteenths, 3 = triplets/compound (default: detect)")
    r.add_argument("--crepe", choices=("full", "tiny"))
    r.add_argument("--no-separate", action="store_true",
                   help="input is already a solo melody; skip stem separation")
    r.add_argument("--work", type=Path, default=Path("work"))
    r.add_argument("--out", type=Path, default=Path("out"))

    e = sub.add_parser("eval", help="run a song list and score against reference melodies")
    e.add_argument("config", type=Path)
    e.add_argument("--work", type=Path, default=Path("work"))
    e.add_argument("--out", type=Path, default=Path("out"))

    a = ap.parse_args(argv)
    if a.cmd == "run":
        opts = pipeline.Options(stem=a.stem, key_change=a.key_change, bpm=a.bpm,
                                beats_per_bar=a.beats_per_bar, subdivision=a.grid,
                                crepe=a.crepe, separate=not a.no_separate)
        summary = pipeline.run(a.source, opts, a.work, a.out)
        print(json.dumps(summary, indent=1))
        print((a.out / summary["song_id"] / "tab.txt").read_text())
    else:
        rows = evaluate.run_set(a.config, a.work, a.out)
        print(f"\n{'song':30} {'conf':>5} {'F1':>5} {'prec':>5} {'recall':>6}  sections")
        for row in rows:
            if "error" in row:
                print(f"{row['name'][:30]:30} ERROR {row['error']}")
                continue
            print(f"{row['name'][:30]:30} {row['overall_conf']:5.2f} "
                  f"{row.get('f1', float('nan')):5.2f} {row.get('precision', float('nan')):5.2f} "
                  f"{row.get('recall', float('nan')):6.2f}  {row['sections']}")
        (a.out / "eval.json").write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
