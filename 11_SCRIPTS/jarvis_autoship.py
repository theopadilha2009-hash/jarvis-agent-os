from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "145_AUTOSHIP"
REPORT = OUT / "AUTOSHIP.md"
STATE = OUT / "AUTOSHIP.json"

ALLOWED_PREFIXES = [
    "11_SCRIPTS/",
]

BLOCKED_PARTS = [
    "." + "env",
    ".git/",
    "se" + "cret",
    "se" + "crets",
    "to" + "ken",
    "creden" + "tial",
    "creden" + "tials",
    "pass" + "word",
    "service" + "_role",
    "private" + "_key",
    "node_modules/",
    "__pycache__/",
]

DEFAULT_MESSAGE = "chore: autoship safe Jarvis changes"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def git_status() -> str:
    _, out = run(["git", "status", "-sb"])
    return out


def porcelain_lines() -> list[str]:
    _, out = run(["git", "status", "--porcelain"])
    return [line for line in out.splitlines() if line.strip()]


def extract_path(line: str) -> str:
    path = line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ")[-1].strip()
    return path.replace("\\", "/")


def is_allowed_path(path: str) -> bool:
    low = path.lower()

    if any(part.lower() in low for part in BLOCKED_PARTS):
        return False

    return any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def safe_message(message: str) -> str:
    msg = (message or DEFAULT_MESSAGE).strip()
    msg = re.sub(r"\s+", " ", msg)
    if len(msg) > 120:
        msg = msg[:120].rstrip()
    if not msg:
        msg = DEFAULT_MESSAGE
    return msg


def write(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Autoship v1 — Block 145",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Action: `{payload['action']}`",
        f"Verdict: `{payload['verdict']}`",
        f"Can commit: `{payload['can_commit']}`",
        f"Can push: `{payload['can_push']}`",
        "",
        "## Files",
        "",
    ]

    if payload["files"]:
        for item in payload["files"]:
            lines.append(f"- `{item['path']}` allowed=`{item['allowed']}` status=`{item['status']}`")
    else:
        lines.append("- No changed files.")

    lines += [
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload["checks"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Blockers",
        "",
    ]

    if payload["blockers"]:
        for item in payload["blockers"]:
            lines.append(f"- {item}")
    else:
        lines.append("- No blockers.")

    lines += [
        "",
        "## Git status",
        "",
        "```text",
        payload["git_status"] or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def inspect(action: str) -> dict:
    lines = porcelain_lines()
    files = []

    blockers = []
    for line in lines:
        path = extract_path(line)
        allowed = is_allowed_path(path)
        files.append({
            "status": line[:2],
            "path": path,
            "allowed": allowed,
        })
        if not allowed:
            blockers.append(f"Blocked path: {path}")

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "verdict": "pending",
        "can_commit": False,
        "can_push": False,
        "files": files,
        "checks": [],
        "blockers": blockers,
        "git_status": git_status(),
    }


def status() -> int:
    payload = inspect("status")

    if not payload["files"]:
        payload["verdict"] = "nothing_to_ship"
        payload["can_commit"] = False
    elif payload["blockers"]:
        payload["verdict"] = "block"
    else:
        payload["verdict"] = "ready_for_guarded_commit"
        payload["can_commit"] = True

    write(payload)

    print("AUTOSHIP_STATUS_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "can_commit": payload["can_commit"],
        "files": payload["files"],
        "blockers": payload["blockers"],
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return 0 if payload["verdict"] != "block" else 1


def commit(message: str, push: bool) -> int:
    payload = inspect("commit")

    if not payload["files"]:
        payload["verdict"] = "nothing_to_ship"
        write(payload)
        print("AUTOSHIP_NOTHING_TO_SHIP")
        print(REPORT)
        print(json.dumps({
            "verdict": payload["verdict"],
            "git_status": payload["git_status"],
        }, ensure_ascii=False, indent=2))
        return 0

    if payload["blockers"]:
        payload["verdict"] = "block"
        write(payload)
        print("AUTOSHIP_BLOCKED")
        print(REPORT)
        print(json.dumps({
            "verdict": payload["verdict"],
            "blockers": payload["blockers"],
            "git_status": payload["git_status"],
        }, ensure_ascii=False, indent=2))
        return 1

    for item in payload["files"]:
        code, out = run(["git", "add", "--", item["path"]])
        payload["checks"].append({
            "name": f"git add {item['path']}",
            "exit_code": code,
            "output_tail": out[-1000:],
        })
        if code != 0:
            payload["blockers"].append(f"git add failed: {item['path']}")

    if payload["blockers"]:
        payload["verdict"] = "block"
        write(payload)
        print("AUTOSHIP_BLOCKED")
        print(REPORT)
        return 1

    gate_code, gate_out = run(["py", "-3", "11_SCRIPTS\\jarvis_ops.py", "ship-guard", "preflight"])
    payload["checks"].append({
        "name": "ship-guard preflight",
        "exit_code": gate_code,
        "output_tail": gate_out[-2500:],
    })

    if gate_code != 0:
        payload["blockers"].append("ship-guard blocked commit")

    if payload["blockers"]:
        payload["verdict"] = "block"
        payload["git_status"] = git_status()
        write(payload)
        print("AUTOSHIP_BLOCKED")
        print(REPORT)
        print(json.dumps({
            "verdict": payload["verdict"],
            "blockers": payload["blockers"],
            "git_status": payload["git_status"],
        }, ensure_ascii=False, indent=2))
        return 1

    msg = safe_message(message)
    commit_code, commit_out = run(["git", "commit", "-m", msg])
    payload["checks"].append({
        "name": f"git commit -m {msg}",
        "exit_code": commit_code,
        "output_tail": commit_out[-2500:],
    })

    if commit_code != 0:
        payload["verdict"] = "block"
        payload["blockers"].append("git commit failed")
        payload["git_status"] = git_status()
        write(payload)
        print("AUTOSHIP_COMMIT_FAILED")
        print(REPORT)
        return 1

    payload["can_commit"] = True

    if push:
        push_code, push_out = run(["git", "push", "origin", "main"])
        payload["checks"].append({
            "name": "git push origin main",
            "exit_code": push_code,
            "output_tail": push_out[-2500:],
        })
        if push_code != 0:
            payload["verdict"] = "committed_push_failed"
            payload["blockers"].append("git push failed")
            payload["git_status"] = git_status()
            write(payload)
            print("AUTOSHIP_PUSH_FAILED")
            print(REPORT)
            return 1
        payload["can_push"] = True

    payload["verdict"] = "shipped" if push else "committed"
    payload["git_status"] = git_status()
    write(payload)

    print("AUTOSHIP_DONE")
    print(REPORT)
    print(json.dumps({
        "verdict": payload["verdict"],
        "message": msg,
        "pushed": push,
        "git_status": payload["git_status"],
    }, ensure_ascii=False, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 145 Autoship v1")
    parser.add_argument("action", choices=["status", "commit"])
    parser.add_argument("message", nargs="*", default=[])
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    if args.action == "status":
        return status()

    if args.action == "commit":
        return commit(" ".join(args.message).strip(), push=args.push)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
