from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "116_GROWTH_LOOP"
REPORT = OUT / "GROWTH_LOOP_REPORT.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py(script: str, *args: str) -> tuple[int, str]:
    return run([sys.executable, script, *args])


def parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        return {"ok": False, "raw": text}


def list_patches() -> dict:
    code, out = py("11_SCRIPTS/jarvis_self_patch.py", "list")
    data = parse_json(out)
    data["code"] = code
    return data


def pending_patches() -> list[str]:
    data = list_patches()
    patches = data.get("patches", [])
    return [p["name"] for p in patches if not p.get("applied")]


def validate() -> tuple[int, str]:
    files = [
        "11_SCRIPTS/jarvis_growth_loop.py",
        "11_SCRIPTS/jarvis_patch_runner.py",
        "11_SCRIPTS/jarvis_self_patch.py",
        "11_SCRIPTS/jarvis_auto_cycle.py",
        "11_SCRIPTS/jarvis_ops.py",
        "11_SCRIPTS/jarvis_local_cleaner.py",
        "11_SCRIPTS/jarvis_auto_improve.py",
        "11_SCRIPTS/jarvis_autoship.py",
        "11_SCRIPTS/jarvis_cli.py",
        "11_SCRIPTS/jarvis_api.py",
        "11_SCRIPTS/jarvis_core.py",
    ]
    files = [f for f in files if (REPO / f).exists()]
    return run([sys.executable, "-m", "py_compile", *files])


def apply(limit: int = 2) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    applied: list[str] = []

    before = list_patches()
    outputs.append("PATCHES_BEFORE\n" + json.dumps(before, ensure_ascii=False, indent=2))

    for name in pending_patches()[: max(1, limit)]:
        code_plan, out_plan = py("11_SCRIPTS/jarvis_self_patch.py", "plan", name)
        outputs.append(f"PLAN {name}\n{out_plan or '-'}")

        if code_plan != 0:
            break

        code_apply, out_apply = py("11_SCRIPTS/jarvis_self_patch.py", "apply", name)
        outputs.append(f"APPLY {name}\n{out_apply or '-'}")

        if code_apply != 0:
            break

        applied.append(name)

    code_val, out_val = validate()
    outputs.append("VALIDATE\n" + (out_val or "OK"))

    code_close, out_close = py("11_SCRIPTS/jarvis_ops.py", "closeout")
    outputs.append("CLOSEOUT\n" + (out_close or "-"))

    after = list_patches()
    outputs.append("PATCHES_AFTER\n" + json.dumps(after, ensure_ascii=False, indent=2))

    _, status = run(["git", "status", "-sb"])
    _, diff = run(["git", "diff", "--stat"])

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "applied": applied,
        "pending_after": pending_patches(),
        "validation_code": code_val,
        "closeout_code": code_close,
        "status": status,
        "diff": diff,
        "outputs": outputs,
    }

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("GROWTH_LOOP_DONE")
    print(REPORT)
    print(status)

    return max(code_val, code_close)


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 116 Growth Loop")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--limit", type=int, default=2)

    args = parser.parse_args()

    if args.cmd == "list":
        print(json.dumps(list_patches(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "apply":
        return apply(limit=args.limit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
