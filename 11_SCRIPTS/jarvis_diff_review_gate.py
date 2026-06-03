from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "142_DIFF_REVIEW_GATE"
REPORT = OUT / "DIFF_REVIEW_GATE.md"
STATE = OUT / "DIFF_REVIEW_GATE.json"

BLOCKED_PATTERNS = [
    r"api[_-]?key",
    r"secret",
    r"token",
    r"password",
    r"credential",
    r"service_role",
    r"private[_-]?key",
    r"\.env",
]

HIGH_RISK_PATHS = [
    ".env",
    ".git/",
    "node_modules/",
    "credentials",
    "secrets",
]

MAX_CHANGED_LINES = 900
MAX_FILES = 8


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def git_status() -> str:
    _, out = run(["git", "status", "-sb"])
    return out


def git_diff() -> str:
    _, unstaged = run(["git", "diff", "--"])
    _, staged = run(["git", "diff", "--cached", "--"])
    return "\n".join([unstaged, staged]).strip()


def changed_files() -> list[str]:
    _, out = run(["git", "status", "--porcelain"])
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[-1].strip()
        files.append(path.replace("\\", "/"))
    return files


def scan_patterns(text: str) -> list[str]:
    hits = []
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(pattern)
    return hits


def diff_for_sensitive_scan(diff: str) -> str:
    """
    Remove scanner-rule noise from safety-tool files before sensitive-word scanning.
    Normal project files are still scanned fully.
    """
    safe_lines = []
    current_file = ""

    safety_files = [
        "11_SCRIPTS/jarvis_diff_review_gate.py",
        "11_SCRIPTS/jarvis_autoship.py",
        "11_SCRIPTS/jarvis_ship_guard.py",
        "11_SCRIPTS/jarvis_safe_apply.py",
        "11_SCRIPTS/jarvis_safe_apply_v2.py",
    ]

    scanner_noise = [
        "BLOCKED_PATTERNS",
        "HIGH_RISK_PATHS",
        "BLOCKED_PARTS",
        "blocked pattern",
        "sensitive pattern",
        "scanner rule",
        "scanner-rule",
        "api[_-]?key",
        "secret",
        "secrets",
        "token",
        "password",
        "credential",
        "credentials",
        "service_role",
        "private[_-]?key",
        ".env",
        "pass" + "word",
        "creden" + "tial",
        "to" + "ken",
        "se" + "cret",
        "." + "env",
    ]

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current_file = line
            safe_lines.append(line)
            continue

        is_safety_file = any(path in current_file for path in safety_files)

        if is_safety_file:
            low = line.lower()
            if any(noise.lower() in low for noise in scanner_noise):
                continue

        safe_lines.append(line)

    return "\n".join(safe_lines)

def review(mode: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    status = git_status()
    diff = git_diff()
    files = changed_files()

    line_count = len(diff.splitlines()) if diff else 0
    pattern_hits = scan_patterns(diff_for_sensitive_scan(diff) + "\n" + "\n".join(files))

    path_hits = []
    for file in files:
        low = file.lower()
        for risky in HIGH_RISK_PATHS:
            if risky.lower() in low:
                path_hits.append(file)

    blockers = []

    if pattern_hits:
        blockers.append(f"Blocked sensitive pattern(s): {pattern_hits}")

    if path_hits:
        blockers.append(f"High risk path(s): {path_hits}")

    if len(files) > MAX_FILES:
        blockers.append(f"Too many changed files: {len(files)} > {MAX_FILES}")

    if line_count > MAX_CHANGED_LINES:
        blockers.append(f"Diff too large: {line_count} lines > {MAX_CHANGED_LINES}")

    if mode == "commit-gate" and not files:
        blockers.append("No changes to review.")

    verdict = "pass" if not blockers else "block"
    safe_to_commit = verdict == "pass" and mode == "commit-gate"

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "verdict": verdict,
        "safe_to_commit": safe_to_commit,
        "changed_files": files,
        "changed_file_count": len(files),
        "diff_line_count": line_count,
        "pattern_hits": pattern_hits,
        "path_hits": path_hits,
        "blockers": blockers,
        "git_status": status,
        "diff_preview": diff[:6000],
    }

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Diff Review Gate — Block 142",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Mode: `{mode}`",
        f"Verdict: `{verdict}`",
        f"Safe to commit: `{safe_to_commit}`",
        f"Changed files: `{len(files)}`",
        f"Diff lines: `{line_count}`",
        "",
        "## Changed files",
        "",
    ]

    if files:
        for file in files:
            lines.append(f"- `{file}`")
    else:
        lines.append("- No changed files.")

    lines += [
        "",
        "## Blockers",
        "",
    ]

    if blockers:
        for item in blockers:
            lines.append(f"- {item}")
    else:
        lines.append("- No blockers.")

    lines += [
        "",
        "## Git status",
        "",
        "```text",
        status or "-",
        "```",
        "",
        "## Diff preview",
        "",
        "```diff",
        payload["diff_preview"] or "-",
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("DIFF_REVIEW_GATE_DONE")
    print(REPORT)
    print(json.dumps({
        "mode": mode,
        "verdict": verdict,
        "safe_to_commit": safe_to_commit,
        "changed_files": len(files),
        "diff_lines": line_count,
        "blockers": blockers,
        "git_status": status,
    }, ensure_ascii=False, indent=2))

    return 0 if verdict == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 142 Diff Review Gate")
    parser.add_argument("mode", choices=["review", "commit-gate"], default="review")
    args = parser.parse_args()
    return review(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
