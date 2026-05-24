"""
mission_open_latest.py — print the absolute path of the most recent mission's
prompt file on a SINGLE LINE so it can be piped:

    cat "$(./jarvis mission-open-latest)" | pbcopy
    cat "$(./jarvis mission-open-latest)"

With --project ALIAS, narrows to missions for that project alias.
With --print, also prints the full prompt content to stdout (after the path
line on stderr).
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MISSIONS_DIR = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"


def parse_args(argv):
    alias = None
    do_print = False
    path_only = True  # default: print only the path
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            if i + 1 < len(argv):
                alias = argv[i + 1].strip().lower()
                i += 2
                continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--print":
            do_print = True
            path_only = False
            i += 1
            continue
        i += 1
    return alias, do_print, path_only


def main():
    alias, do_print, path_only = parse_args(sys.argv[1:])

    if not MISSIONS_DIR.exists():
        print("FALHA: nenhuma missão registrada (pasta ausente).", file=sys.stderr)
        sys.exit(1)

    candidates = [d for d in MISSIONS_DIR.iterdir() if d.is_dir()]
    if alias:
        candidates = [d for d in candidates if f"project-{alias}_" in d.name]
    if not candidates:
        msg = f"FALHA: nenhuma missão encontrada{' para alias=' + alias if alias else ''}."
        print(msg, file=sys.stderr)
        sys.exit(1)

    latest = max(candidates, key=lambda d: d.stat().st_mtime)
    prompt = latest / "01_CLAUDE_PROMPT.md"
    if not prompt.exists():
        print(f"FALHA: 01_CLAUDE_PROMPT.md ausente em {latest}", file=sys.stderr)
        sys.exit(1)

    # Path goes to stdout — easy to capture with $(...)
    print(prompt)

    if do_print:
        # Full content also goes to stdout, after the path line.
        # If the caller wants pure-content piping, they should redirect
        # the path line: `./jarvis mission-open-latest --print | tail -n +2`
        # or use the default mode + cat "$(...)".
        sys.stdout.write(prompt.read_text(encoding="utf-8", errors="ignore"))


if __name__ == "__main__":
    main()
