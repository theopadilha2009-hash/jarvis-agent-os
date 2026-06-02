from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PATCH_ORDER = [
    "cycle-command",
    "fast-command",
    "health-command",
]

SAFE_PATCHES = {
    "cycle-command": {
        "title": "Add Jarvis cycle command",
        "risk": "low",
        "target": "11_SCRIPTS/jarvis_ops.py",
        "description": "Adds cycle command: improve + closeout.",
    },
    "fast-command": {
        "title": "Add Jarvis fast command",
        "risk": "low",
        "target": "11_SCRIPTS/jarvis_ops.py",
        "description": "Adds fast command: auto-cycle + status in one command.",
    },
    "health-command": {
        "title": "Add Jarvis health command",
        "risk": "low",
        "target": "11_SCRIPTS/jarvis_ops.py",
        "description": "Adds health command: status + progress in one command.",
    },
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


def ops_text() -> str:
    return (REPO / "11_SCRIPTS" / "jarvis_ops.py").read_text(encoding="utf-8", errors="replace")


def write_ops(text: str) -> None:
    (REPO / "11_SCRIPTS" / "jarvis_ops.py").write_text(text, encoding="utf-8")


def insert_before_main(text: str, block: str) -> str:
    marker = "\ndef main() -> int:"
    if marker not in text:
        raise RuntimeError("Could not find main() insertion point")
    return text.replace(marker, "\n" + block + marker, 1)


def insert_parser(text: str, block: str) -> str:
    markers = [
        '    p_auto_cycle = sub.add_parser("auto-cycle")',
        '    p_self_patch = sub.add_parser("self-patch")',
        '    p_improve = sub.add_parser("improve")',
        '    p_ship = sub.add_parser("ship")',
        '    sub.add_parser("status")',
    ]
    for marker in markers:
        if marker in text:
            return text.replace(marker, block + marker, 1)
    raise RuntimeError("Could not find parser insertion point")


def insert_route(text: str, block: str) -> str:
    markers = [
        '    if args.cmd == "auto-cycle":',
        '    if args.cmd == "self-patch":',
        '    if args.cmd == "improve":',
        '    if args.cmd == "ship":',
        '    if args.cmd == "status":',
    ]
    for marker in markers:
        if marker in text:
            return text.replace(marker, block + marker, 1)
    raise RuntimeError("Could not find route insertion point")


def is_applied(patch_name: str) -> bool:
    text = ops_text()
    if patch_name == "cycle-command":
        return "def cycle(" in text and 'p_cycle = sub.add_parser("cycle")' in text
    if patch_name == "fast-command":
        return "def fast(" in text and 'p_fast = sub.add_parser("fast")' in text
    if patch_name == "health-command":
        return "def health(" in text and 'sub.add_parser("health")' in text
    return False


def next_patch_name() -> str | None:
    for name in PATCH_ORDER:
        if not is_applied(name):
            return name
    return None


def plan(patch_name: str) -> dict:
    if patch_name == "next":
        patch_name = next_patch_name() or "none"

    if patch_name == "none":
        return {
            "ok": True,
            "patch": "none",
            "message": "No pending safe patch.",
            "available": PATCH_ORDER,
        }

    patch = SAFE_PATCHES.get(patch_name)
    if not patch:
        return {"ok": False, "error": f"Unknown patch: {patch_name}", "available": PATCH_ORDER}

    return {
        "ok": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "patch": patch_name,
        "applied": is_applied(patch_name),
        **patch,
    }


def apply_cycle_command() -> dict:
    text = ops_text()
    changed = False

    if "def cycle(" not in text:
        func = '''
def cycle(goal: str, print_full: bool = False) -> int:
    print("JARVIS CYCLE — IMPROVE")
    code1 = improve(goal, print_full=print_full)

    print("")
    print("JARVIS CYCLE — CLOSEOUT")
    code2 = closeout(print_full=False)

    return max(code1, code2)


'''
        text = insert_before_main(text, func)
        changed = True

    if 'p_cycle = sub.add_parser("cycle")' not in text:
        parser = '''
    p_cycle = sub.add_parser("cycle")
    p_cycle.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_cycle.add_argument("--print", action="store_true")

'''
        text = insert_parser(text, parser)
        changed = True

    if 'if args.cmd == "cycle":' not in text:
        route = '''
    if args.cmd == "cycle":
        return cycle(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            print_full=args.print,
        )

'''
        text = insert_route(text, route)
        changed = True

    write_ops(text)
    return {"ok": True, "patch": "cycle-command", "changed": changed}


def apply_fast_command() -> dict:
    text = ops_text()
    changed = False

    if "def fast(" not in text:
        func = '''
def fast(goal: str, no_apply: bool = False) -> int:
    print("JARVIS FAST — AUTO CYCLE")
    code1 = auto_cycle(goal, no_apply=no_apply)

    print("")
    print("JARVIS FAST — STATUS")
    code2 = status()

    return max(code1, code2)


'''
        text = insert_before_main(text, func)
        changed = True

    if 'p_fast = sub.add_parser("fast")' not in text:
        parser = '''
    p_fast = sub.add_parser("fast")
    p_fast.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_fast.add_argument("--no-apply", action="store_true")

'''
        text = insert_parser(text, parser)
        changed = True

    if 'if args.cmd == "fast":' not in text:
        route = '''
    if args.cmd == "fast":
        return fast(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            no_apply=args.no_apply,
        )

'''
        text = insert_route(text, route)
        changed = True

    write_ops(text)
    return {"ok": True, "patch": "fast-command", "changed": changed}


def apply_health_command() -> dict:
    text = ops_text()
    changed = False

    if "def health(" not in text:
        func = '''
def health() -> int:
    print("JARVIS HEALTH — STATUS")
    code1 = status()

    print("")
    print("JARVIS HEALTH — PROGRESS")
    code2 = progress(save=False)

    return max(code1, code2)


'''
        text = insert_before_main(text, func)
        changed = True

    if 'sub.add_parser("health")' not in text:
        parser = '''
    sub.add_parser("health")

'''
        text = insert_parser(text, parser)
        changed = True

    if 'if args.cmd == "health":' not in text:
        route = '''
    if args.cmd == "health":
        return health()

'''
        text = insert_route(text, route)
        changed = True

    write_ops(text)
    return {"ok": True, "patch": "health-command", "changed": changed}


def apply_patch(patch_name: str) -> dict:
    expected = [
        "11_SCRIPTS/jarvis_self_patch.py",
        "11_SCRIPTS/jarvis_ops.py",
        "11_SCRIPTS/jarvis_auto_cycle.py",
        "11_SCRIPTS/jarvis_local_cleaner.py",
    ]

    if not guard_expected(expected):
        return {
            "ok": False,
            "error": "Unexpected files in git status.",
            "current_paths": current_paths(),
            "expected": expected,
        }

    if patch_name == "next":
        patch_name = next_patch_name()
        if not patch_name:
            return {"ok": True, "patch": "none", "changed": False, "message": "No pending safe patch."}

    if patch_name == "cycle-command":
        return apply_cycle_command()
    if patch_name == "fast-command":
        return apply_fast_command()
    if patch_name == "health-command":
        return apply_health_command()

    return {"ok": False, "error": f"Unknown patch: {patch_name}", "available": PATCH_ORDER}


def list_patches() -> dict:
    return {
        "ok": True,
        "patches": [
            {
                "name": name,
                "applied": is_applied(name),
                **SAFE_PATCHES[name],
            }
            for name in PATCH_ORDER
        ],
        "next": next_patch_name(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 113 Self Patch Catalog")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("patch", nargs="?", default="next")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("patch", nargs="?", default="next")

    args = parser.parse_args()

    if args.cmd == "list":
        print(json.dumps(list_patches(), ensure_ascii=False, indent=2))
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
