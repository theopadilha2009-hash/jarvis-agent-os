from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SAFE_PATCHES = {
    "cycle-command": {
        "title": "Add Jarvis cycle command",
        "risk": "low",
        "target": "11_SCRIPTS/jarvis_ops.py",
        "description": "Adds `jarvis_ops.py cycle`, running improve + closeout in one command.",
    }
}


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def current_paths() -> list[str]:
    _, out = run(["git", "status", "--porcelain"])
    paths = []
    for line in out.splitlines():
        path = line[2:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            paths.append(path)
    return paths


def guard_expected(expected: list[str]) -> bool:
    paths = current_paths()
    return all(p in expected for p in paths)


def plan(patch_name: str) -> dict:
    patch = SAFE_PATCHES.get(patch_name)
    if not patch:
        return {"ok": False, "error": f"Unknown patch: {patch_name}", "available": sorted(SAFE_PATCHES)}

    return {
        "ok": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "patch": patch_name,
        **patch,
        "validation": [
            "python3 -m py_compile 11_SCRIPTS/jarvis_self_patch.py 11_SCRIPTS/jarvis_ops.py",
            "python3 11_SCRIPTS/jarvis_ops.py cycle \"melhorar Jarvis\"",
            "python3 11_SCRIPTS/jarvis_ops.py ship \"feat: add Jarvis self patch planner\"",
        ],
    }


def apply_cycle_command() -> dict:
    target = REPO / "11_SCRIPTS" / "jarvis_ops.py"
    text = target.read_text(encoding="utf-8", errors="replace")
    changed = False

    if "def cycle(" not in text:
        cycle_func = '''
def cycle(goal: str, print_full: bool = False) -> int:
    print("JARVIS CYCLE — IMPROVE")
    code1 = improve(goal, print_full=print_full)

    print("")
    print("JARVIS CYCLE — CLOSEOUT")
    code2 = closeout(print_full=False)

    return max(code1, code2)


'''
        text = text.replace("\ndef improve(", "\n" + cycle_func + "def improve(")
        changed = True

    if 'p_cycle = sub.add_parser("cycle")' not in text:
        parser_block = '''
    p_cycle = sub.add_parser("cycle")
    p_cycle.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_cycle.add_argument("--print", action="store_true")

'''
        text = text.replace('    p_improve = sub.add_parser("improve")', parser_block + '    p_improve = sub.add_parser("improve")')
        changed = True

    if 'if args.cmd == "cycle":' not in text:
        route_block = '''
    if args.cmd == "cycle":
        return cycle(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            print_full=args.print,
        )

'''
        text = text.replace('    if args.cmd == "improve":', route_block + '    if args.cmd == "improve":')
        changed = True

    target.write_text(text, encoding="utf-8")
    return {"ok": True, "patch": "cycle-command", "changed": changed}


def apply_patch(patch_name: str) -> dict:
    expected = [
        "11_SCRIPTS/jarvis_self_patch.py",
        "11_SCRIPTS/jarvis_ops.py",
        "11_SCRIPTS/jarvis_local_cleaner.py",
    ]

    if not guard_expected(expected):
        return {
            "ok": False,
            "error": "Unexpected files in git status.",
            "current_paths": current_paths(),
            "expected": expected,
        }

    if patch_name == "cycle-command":
        return apply_cycle_command()

    return {"ok": False, "error": f"Unknown patch: {patch_name}", "available": sorted(SAFE_PATCHES)}


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 111 Self Patch Planner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("patch", nargs="?")

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("patch", nargs="?", default="cycle-command")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("patch", nargs="?", default="cycle-command")

    args = parser.parse_args()

    if args.cmd == "list":
        print(json.dumps(SAFE_PATCHES, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "plan":
        print(json.dumps(plan(args.patch), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "apply":
        result = apply_patch(args.patch)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
