#!/usr/bin/env python3
from pathlib import Path
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "11_SCRIPTS"

SKIP_PARTS = {
    "__pycache__",
    "_ARCHIVE",
    ".venv",
    "venv",
}

def should_skip(path):
    return any(part in SKIP_PARTS for part in path.parts)

def main():
    files = sorted(
        p for p in BASE.rglob("*.py")
        if p.is_file() and not should_skip(p)
    )

    failed = []

    for p in files:
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as e:
            failed.append((p, e))

    if failed:
        print("FAIL — Python syntax gate encontrou erro:")
        for p, e in failed:
            print(f"- {p.relative_to(ROOT)}")
            print(f"  {e}")
        return 1

    print(f"OK — Python syntax gate passou em {len(files)} arquivo(s).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
