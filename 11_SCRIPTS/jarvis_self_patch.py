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
    "work-command",
    "sync-check-command",
    "done-command",
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
        "description": "Adds fast command: auto-cycle + status.",
    },
    "health-command": {
        "title": "Add Jarvis health command",
        "risk": "low",
        "target": "11_SCRIPTS/jarvis_ops.py",
        "description": "Adds health command: status + progress.",
    },
    "work-command": {
        "title": "Add Jarvis work command",
        "risk": "low",
        "target": "11_SCRIPTS/jarvis_ops.py",
        "description": "Adds work command: health + improve + patch-run next.",
    },
    "sync-check-command": {
        "title": "Add Jarvis sync-check command",
        "risk": "low",
        "target": "11_SCRIPTS/jarvis_ops.py",
        "description": "Adds sync-check command: fetch + local/remote comparison + status.",
    },
    "done-command": {
        "title": "Add Jarvis done command",
        "risk": "low",
        "target": "11_SCRIPTS/jarvis_ops.py",
        "description": "Adds done command: closeout + status.",
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
    return all(p in expected for p in current_paths())


def ops_text() -> str:
    return (REPO / "11_SCRIPTS" / "jarvis_ops.py").read_text(encoding="utf-8", errors="replace")


def write_ops(text: str) -> None:
    (REPO / "11_SCRIPTS" / "jarvis_ops.py").write_text(text, encoding="utf-8")


def insert_before_main(text: str, block: str) -> str:
    marker = "\ndef main() -> int:"
    if marker not in text:
        raise RuntimeError("Could not find main insertion point")
    return text.replace(marker, "\n" + block + marker, 1)


def insert_parser(text: str, block: str) -> str:
    markers = [
        '    p_patch_run = sub.add_parser("patch-run")',
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
        '    if args.cmd == "patch-run":',
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
    checks = {
        "cycle-command": "def cycle(",
        "fast-command": "def fast(",
        "health-command": "def health(",
        "work-command": "def work(",
        "sync-check-command": "def sync_check(",
        "done-command": "def done(",
    }
    return checks.get(patch_name, "__missing__") in text


def next_patch_name() -> str | None:
    for name in PATCH_ORDER:
        if not is_applied(name):
            return name
    return None


def add_simple_command(name: str, func_code: str, parser_code: str, route_code: str) -> dict:
    text = ops_text()
    changed = False

    if f"def {name}(" not in text:
        text = insert_before_main(text, func_code)
        changed = True

    parser_signature = parser_code.strip().splitlines()[0].strip()
    if parser_signature and parser_signature not in text:
        text = insert_parser(text, parser_code)
        changed = True

    route_signature = f'if args.cmd == "{name.replace("_", "-")}":'
    if route_signature not in text:
        text = insert_route(text, route_code)
        changed = True

    write_ops(text)
    return {"ok": True, "patch": f"{name}-command", "changed": changed}


def apply_cycle_command() -> dict:
    return add_simple_command(
        "cycle",
        '''
def cycle(goal: str, print_full: bool = False) -> int:
    print("JARVIS CYCLE — IMPROVE")
    code1 = improve(goal, print_full=print_full)

    print("")
    print("JARVIS CYCLE — CLOSEOUT")
    code2 = closeout(print_full=False)

    return max(code1, code2)


''',
        '''
    p_cycle = sub.add_parser("cycle")
    p_cycle.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_cycle.add_argument("--print", action="store_true")

''',
        '''
    if args.cmd == "cycle":
        return cycle(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            print_full=args.print,
        )

''',
    )


def apply_fast_command() -> dict:
    return add_simple_command(
        "fast",
        '''
def fast(goal: str, no_apply: bool = False) -> int:
    print("JARVIS FAST — AUTO CYCLE")
    code1 = auto_cycle(goal, no_apply=no_apply)

    print("")
    print("JARVIS FAST — STATUS")
    code2 = status()

    return max(code1, code2)


''',
        '''
    p_fast = sub.add_parser("fast")
    p_fast.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])
    p_fast.add_argument("--no-apply", action="store_true")

''',
        '''
    if args.cmd == "fast":
        return fast(
            " ".join(args.goal).strip() or "melhorar Jarvis",
            no_apply=args.no_apply,
        )

''',
    )


def apply_health_command() -> dict:
    return add_simple_command(
        "health",
        '''
def health() -> int:
    print("JARVIS HEALTH — STATUS")
    code1 = status()

    print("")
    print("JARVIS HEALTH — PROGRESS")
    code2 = progress(save=False)

    return max(code1, code2)


''',
        '''
    sub.add_parser("health")

''',
        '''
    if args.cmd == "health":
        return health()

''',
    )


def apply_work_command() -> dict:
    return add_simple_command(
        "work",
        '''
def work(goal: str) -> int:
    print("JARVIS WORK — HEALTH")
    code1 = health() if "health" in globals() else status()

    print("")
    print("JARVIS WORK — IMPROVE")
    code2 = improve(goal, print_full=False)

    print("")
    print("JARVIS WORK — PATCH NEXT")
    code3 = patch_run("next", limit=1) if "patch_run" in globals() else 0

    return max(code1, code2, code3)


''',
        '''
    p_work = sub.add_parser("work")
    p_work.add_argument("goal", nargs="*", default=["melhorar", "Jarvis"])

''',
        '''
    if args.cmd == "work":
        return work(" ".join(args.goal).strip() or "melhorar Jarvis")

''',
    )


def apply_sync_check_command() -> dict:
    return add_simple_command(
        "sync_check",
        '''
def sync_check() -> int:
    print("JARVIS SYNC CHECK — FETCH")
    code_fetch, out_fetch = run(["git", "fetch", "origin"])
    print(out_fetch or "fetch ok")

    print("")
    print("JARVIS SYNC CHECK — LOCAL")
    _, local = run(["git", "rev-parse", "--short", "HEAD"])
    print(local)

    print("")
    print("JARVIS SYNC CHECK — REMOTE")
    _, remote = run(["git", "rev-parse", "--short", "origin/main"])
    print(remote)

    print("")
    print("JARVIS SYNC CHECK — STATUS")
    code_status = status()

    return max(code_fetch, code_status)


''',
        '''
    sub.add_parser("sync-check")

''',
        '''
    if args.cmd == "sync-check":
        return sync_check()

''',
    )


def apply_done_command() -> dict:
    return add_simple_command(
        "done",
        '''
def done() -> int:
    print("JARVIS DONE — CLOSEOUT")
    code1 = closeout(print_full=False)

    print("")
    print("JARVIS DONE — STATUS")
    code2 = status()

    return max(code1, code2)


''',
        '''
    sub.add_parser("done")

''',
        '''
    if args.cmd == "done":
        return done()

''',
    )


def plan(patch_name: str) -> dict:
    if patch_name == "next":
        patch_name = next_patch_name() or "none"

    if patch_name == "none":
        return {"ok": True, "patch": "none", "message": "No pending safe patch.", "available": PATCH_ORDER}

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

    handlers = {
        "cycle-command": apply_cycle_command,
        "fast-command": apply_fast_command,
        "health-command": apply_health_command,
        "work-command": apply_work_command,
        "sync-check-command": apply_sync_check_command,
        "done-command": apply_done_command,
    }

    handler = handlers.get(patch_name)
    if not handler:
        return {"ok": False, "error": f"Unknown patch: {patch_name}", "available": PATCH_ORDER}

    return handler()


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
    parser = argparse.ArgumentParser(description="JARVIS Block 115 Expanded Self Patch Catalog")
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
