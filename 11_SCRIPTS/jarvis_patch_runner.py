from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "114_PATCH_RUNNER"
REPORT = OUT / "PATCH_RUNNER_REPORT.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py(script: str, *args: str) -> tuple[int, str]:
    return run([sys.executable, script, *args])


def git_status() -> str:
    _, out = run(["git", "status", "-sb"])
    return out


def git_diff() -> str:
    _, out = run(["git", "diff", "--stat"])
    return out


def list_patches() -> dict:
    code, out = py("11_SCRIPTS/jarvis_self_patch.py", "list")
    if code != 0:
        return {"ok": False, "raw": out}

    try:
        return json.loads(out)
    except Exception:
        return {"ok": False, "raw": out}


def next_patch_name() -> str | None:
    data = list_patches()
    nxt = data.get("next")
    return nxt if nxt and nxt != "none" else None


def validate() -> tuple[int, str]:
    files = [
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


def apply_next(limit: int = 1) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    applied: list[str] = []

    for _ in range(max(1, limit)):
        nxt = next_patch_name()
        if not nxt:
            outputs.append("NO_PENDING_PATCH")
            break

        outputs.append(f"NEXT_PATCH: {nxt}")

        code_plan, out_plan = py("11_SCRIPTS/jarvis_self_patch.py", "plan", nxt)
        outputs.append("PLAN\n" + (out_plan or "-"))
        if code_plan != 0:
            break

        code_apply, out_apply = py("11_SCRIPTS/jarvis_self_patch.py", "apply", nxt)
        outputs.append("APPLY\n" + (out_apply or "-"))
        if code_apply != 0:
            break

        applied.append(nxt)

    code_val, out_val = validate()
    outputs.append("VALIDATE\n" + (out_val or "OK"))

    code_close, out_close = py("11_SCRIPTS/jarvis_ops.py", "closeout")
    outputs.append("CLOSEOUT\n" + (out_close or "-"))

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "applied": applied,
        "status": git_status(),
        "diff": git_diff(),
        "validation_code": code_val,
        "closeout_code": code_close,
        "outputs": outputs,
    }

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("PATCH_RUNNER_DONE")
    print(REPORT)
    print(git_status())

    return max(code_val, code_close)


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 114 Patch Runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("next")

    p_apply = sub.add_parser("apply-next")
    p_apply.add_argument("--limit", type=int, default=1)

    args = parser.parse_args()

    if args.cmd == "next":
        data = list_patches()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data.get("ok") else 1

    if args.cmd == "apply-next":
        return apply_next(limit=args.limit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
