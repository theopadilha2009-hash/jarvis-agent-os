from __future__ import annotations

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OPS = REPO / "11_SCRIPTS" / "jarvis_ops.py"


def read_ops() -> str:
    return OPS.read_text(encoding="utf-8", errors="replace")


def write_ops(text: str) -> None:
    OPS.write_text(text, encoding="utf-8")


def insert_before_main(text: str, block: str) -> str:
    marker = "\ndef main() -> int:"
    if marker not in text:
        raise RuntimeError("main insertion point not found")
    return text.replace(marker, "\n" + block + marker, 1)


def insert_parser(text: str, block: str) -> str:
    for marker in [
        '    p_backlog = sub.add_parser("backlog")',
        '    p_grow = sub.add_parser("grow")',
        '    p_patch_run = sub.add_parser("patch-run")',
        '    p_auto_cycle = sub.add_parser("auto-cycle")',
    ]:
        if marker in text:
            return text.replace(marker, block + marker, 1)
    raise RuntimeError("parser insertion point not found")


def insert_route(text: str, block: str) -> str:
    for marker in [
        '    if args.cmd == "backlog":',
        '    if args.cmd == "grow":',
        '    if args.cmd == "patch-run":',
        '    if args.cmd == "auto-cycle":',
    ]:
        if marker in text:
            return text.replace(marker, block + marker, 1)
    raise RuntimeError("route insertion point not found")


def apply() -> bool:
    text = read_ops()
    changed = False

    if "def snapshot(" not in text:
        text = insert_before_main(text, """
def snapshot(label: str = "manual") -> int:
    from datetime import datetime
    import json

    out_dir = REPO / "05_EXECUCAO" / "118_OPERATOR_EXPANSION"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / "SNAPSHOT_REPORT.md"

    _, status_out = run(["git", "status", "-sb"])
    _, porcelain_out = run(["git", "status", "--porcelain"])
    _, diff_out = run(["git", "diff", "--stat"])
    _, commits_out = run(["git", "log", "--oneline", "--decorate", "-12"])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "git_clean": not bool(porcelain_out.strip()),
        "status": status_out,
        "diff": diff_out or "clean",
        "commits": commits_out,
    }

    lines = [
        "# JARVIS Snapshot — Block 118",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Label: **{label}**",
        f"Git clean: `{'yes' if payload['git_clean'] else 'no'}`",
        "",
        "## Status",
        "",
        "```text",
        status_out or "-",
        "```",
        "",
        "## Diff",
        "",
        "```text",
        diff_out or "clean",
        "```",
        "",
        "## Last Commits",
        "",
        "```text",
        commits_out or "-",
        "```",
        "",
        "## Payload",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ]

    report.write_text("\\n".join(lines), encoding="utf-8")

    print("SNAPSHOT_SAVED")
    print(report)
    print(status_out)
    return 0


""")
        changed = True

    if "def review(" not in text:
        text = insert_before_main(text, """
def review() -> int:
    print("JARVIS REVIEW — STATUS")
    code1 = status()

    print("")
    print("JARVIS REVIEW — PROGRESS")
    code2 = progress(save=True) if "progress" in globals() else 0

    print("")
    print("JARVIS REVIEW — CLOSEOUT")
    code3 = closeout(print_full=False)

    return max(code1, code2, code3)


""")
        changed = True

    if "def launch(" not in text:
        text = insert_before_main(text, """
def launch(goal: str, limit: int = 2) -> int:
    print("JARVIS LAUNCH — SNAPSHOT")
    code1 = snapshot("launch-start")

    print("")
    print("JARVIS LAUNCH — GROW")
    code2 = grow(limit=limit) if "grow" in globals() else 0

    print("")
    print("JARVIS LAUNCH — AUTOPILOT")
    code3 = autopilot(goal, limit=limit) if "autopilot" in globals() else work(goal)

    print("")
    print("JARVIS LAUNCH — FINAL SNAPSHOT")
    code4 = snapshot("launch-end")

    return max(code1, code2, code3, code4)


""")
        changed = True

    if 'p_snapshot = sub.add_parser("snapshot")' not in text:
        text = insert_parser(text, """
    p_snapshot = sub.add_parser("snapshot")
    p_snapshot.add_argument("label", nargs="*", default=["manual"])

    sub.add_parser("review")

    p_launch = sub.add_parser("launch")
    p_launch.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_launch.add_argument("--limit", type=int, default=2)

""")
        changed = True

    if 'if args.cmd == "snapshot":' not in text:
        text = insert_route(text, """
    if args.cmd == "snapshot":
        return snapshot(" ".join(args.label).strip() or "manual")

    if args.cmd == "review":
        return review()

    if args.cmd == "launch":
        return launch(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            limit=args.limit,
        )

""")
        changed = True

    write_ops(text)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 118 Operator Expander")
    parser.add_argument("cmd", choices=["apply"])
    args = parser.parse_args()

    if args.cmd == "apply":
        changed = apply()
        print(f"OPERATOR_EXPANDER_APPLIED changed={changed}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
