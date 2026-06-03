from __future__ import annotations

from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "146_SAFE_PATCH_CYCLE" / "operator_notes"


def write_note(title: str = "Jarvis operator note", body: str = "") -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_title = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in title).strip("_")
    if not safe_title:
        safe_title = "note"

    path = OUT / f"{stamp}_{safe_title}.md"
    lines = [
        f"# {title}",
        "",
        f"Created at: `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        "## Note",
        "",
        body.strip() or "- No body provided.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    path = write_note(
        "Jarvis safe patch cycle",
        "This helper confirms the safe patch cycle can create useful local notes.",
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
