from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "146_SAFE_PATCH_CYCLE"
REPORT = OUT / "SAFE_PATCH_CYCLE.md"
STATE = OUT / "SAFE_PATCH_CYCLE.json"

PATCHES = [
    {
        "id": "operator_notes_v1",
        "title": "Add operator notes helper",
        "path": "11_SCRIPTS/jarvis_operator_notes.py",
        "kind": "create_file",
    },
]


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def git_status() -> str:
    _, out = run(["git", "status", "-sb"])
    return out


def operator_notes_content() -> str:
    return '''from __future__ import annotations

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
    path.write_text("\\n".join(lines), encoding="utf-8")
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
'''


def patch_target(patch: dict) -> Path:
    return REPO / patch["path"]


def inspect() -> dict:
    items = []
    for patch in PATCHES:
        target = patch_target(patch)
        items.append({
            "id": patch["id"],
            "title": patch["title"],
            "path": patch["path"],
            "exists": target.exists(),
            "pending": not target.exists(),
        })

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "patches": items,
        "pending_count": sum(1 for item in items if item["pending"]),
        "git_status": git_status(),
    }


def write_report(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Safe Patch Cycle — Block 146",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Pending patches: `{payload.get('pending_count', 0)}`",
        "",
        "## Patches",
        "",
    ]

    for item in payload.get("patches", []):
        lines.append(
            f"- `{item['id']}` — pending=`{item['pending']}` — `{item['path']}`"
        )

    lines += [
        "",
        "## Git status",
        "",
        "```text",
        payload.get("git_status", "-") or "-",
        "```",
        "",
    ]

    if "applied" in payload:
        lines += [
            "## Applied",
            "",
            f"- `{payload['applied']}`",
            "",
        ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def status() -> int:
    payload = inspect()
    write_report(payload)

    print("SAFE_PATCH_CYCLE_STATUS_DONE")
    print(REPORT)
    print(json.dumps({
        "pending_count": payload["pending_count"],
        "patches": payload["patches"],
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))
    return 0


def apply_next() -> int:
    payload = inspect()

    pending = [item for item in payload["patches"] if item["pending"]]
    if not pending:
        payload["applied"] = "none"
        write_report(payload)
        print("SAFE_PATCH_CYCLE_NOTHING_TO_APPLY")
        print(REPORT)
        return 0

    chosen = pending[0]
    target = REPO / chosen["path"]
    target.parent.mkdir(parents=True, exist_ok=True)

    if chosen["id"] == "operator_notes_v1":
        target.write_text(operator_notes_content(), encoding="utf-8")
    else:
        print(f"Unknown patch: {chosen['id']}")
        return 1

    code, out = run(["py", "-3", "-m", "py_compile", str(target.relative_to(REPO))])

    payload = inspect()
    payload["applied"] = chosen["id"]
    payload["compile_exit"] = code
    payload["compile_output"] = out[-1000:]
    write_report(payload)

    print("SAFE_PATCH_CYCLE_APPLY_DONE")
    print(REPORT)
    print(json.dumps({
        "applied": chosen["id"],
        "compile_exit": code,
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 146 Safe Patch Cycle")
    parser.add_argument("action", choices=["status", "apply-next"])
    args = parser.parse_args()

    if args.action == "status":
        return status()

    if args.action == "apply-next":
        return apply_next()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
