from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "109_AUTOSHIP_RUNNER"
REPORT = OUT / "AUTOSHIP_REPORT.md"

SAFE_PREFIXES = (
    "11_SCRIPTS/",
    "README",
    "docs/",
)

BLOCKED_NAMES = (
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
)

BLOCKED_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "senha",
    "credential",
    "credentials",
)


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def status_porcelain() -> str:
    _, out = run(["git", "status", "--porcelain"])
    return out


def changed_files() -> list[str]:
    files = []
    for line in status_porcelain().splitlines():
        if not line.strip():
            continue
        # Git porcelain status uses two status chars, then the path.
        # Using [2:] is safer for both ' M file' and '?? file'.
        path = line[2:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        files.append(path)
    return files


def is_blocked(path: str) -> bool:
    name = Path(path).name.lower()
    low = path.lower()
    if name in BLOCKED_NAMES:
        return True
    if any(fragment in low for fragment in BLOCKED_FRAGMENTS):
        return True
    return False


def is_safe_source(path: str) -> bool:
    return path.startswith(SAFE_PREFIXES) and not is_blocked(path)


def safe_files() -> list[str]:
    return [p for p in changed_files() if is_safe_source(p)]


def unsafe_files() -> list[str]:
    return [p for p in changed_files() if not is_safe_source(p)]


def py_compile() -> tuple[int, str]:
    files = [
        "11_SCRIPTS/jarvis_cli.py",
        "11_SCRIPTS/jarvis_api.py",
        "11_SCRIPTS/jarvis_core.py",
        "11_SCRIPTS/jarvis_ops.py",
        "11_SCRIPTS/jarvis_closeout.py",
        "11_SCRIPTS/jarvis_autoship.py",
    ]
    files = [f for f in files if (REPO / f).exists()]
    return run([sys.executable, "-m", "py_compile", *files])


def closeout() -> tuple[int, str]:
    script = REPO / "11_SCRIPTS" / "jarvis_closeout.py"
    if script.exists():
        return run([sys.executable, "11_SCRIPTS/jarvis_closeout.py"])
    return run([sys.executable, "11_SCRIPTS/jarvis_cli.py", "doctor"])


def build_report(message: str, dry_run: bool, pushed: bool, blocked: list[str], staged: list[str], outputs: list[str]) -> str:
    _, branch = run(["git", "status", "-sb"])
    _, diff = run(["git", "diff", "--stat"])
    _, staged_diff = run(["git", "diff", "--cached", "--stat"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-8"])

    lines = [
        "# JARVIS AutoShip Runner — Block 109",
        "",
        f"Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"Message: `{message}`",
        f"Dry run: `{dry_run}`",
        f"Pushed: `{pushed}`",
        "",
        "## Staged/Safe Files",
        "",
    ]

    lines += [f"- `{p}`" for p in staged] or ["- none"]

    lines += [
        "",
        "## Blocked/Unsafe Files",
        "",
    ]

    lines += [f"- `{p}`" for p in blocked] or ["- none"]

    lines += [
        "",
        "## Command Output",
        "",
        "```text",
        "\n\n".join(outputs).strip() or "-",
        "```",
        "",
        "## Branch",
        "",
        "```text",
        branch or "-",
        "```",
        "",
        "## Diff Stat",
        "",
        "```text",
        diff or "clean",
        "```",
        "",
        "## Staged Diff Stat",
        "",
        "```text",
        staged_diff or "clean",
        "```",
        "",
        "## Last Commits",
        "",
        "```text",
        commits,
        "```",
        "",
    ]

    return "\n".join(lines)


def autoship(message: str, dry_run: bool = False, no_push: bool = False) -> int:
    outputs: list[str] = []
    OUT.mkdir(parents=True, exist_ok=True)

    blocked = unsafe_files()
    staged = safe_files()

    if blocked:
        print("AUTOSHIP_BLOCKED_UNSAFE_FILES")
        for p in blocked:
            print(p)
        report = build_report(message, dry_run, False, blocked, staged, outputs)
        REPORT.write_text(report, encoding="utf-8")
        print(f"REPORT: {REPORT}")
        return 2

    if not staged:
        print("AUTOSHIP_NOTHING_TO_SHIP")
        _, status = run(["git", "status", "-sb"])
        print(status)
        return 0

    code, out = py_compile()
    outputs.append("PY_COMPILE\n" + (out or "OK"))
    if code != 0:
        print(out)
        return code

    code, out = closeout()
    outputs.append("CLOSEOUT\n" + (out or "OK"))
    if code != 0:
        print(out)
        return code

    for p in staged:
        code, out = run(["git", "add", p])
        outputs.append(f"GIT_ADD {p}\n{out or 'OK'}")
        if code != 0:
            print(out)
            return code

    _, cached = run(["git", "diff", "--cached", "--stat"])
    outputs.append("STAGED_DIFF\n" + (cached or "clean"))

    pushed = False

    if dry_run:
        print("AUTOSHIP_DRY_RUN_OK")
        print(cached or "clean")
    else:
        code, out = run(["git", "commit", "-m", message])
        outputs.append("GIT_COMMIT\n" + (out or "OK"))
        print(out)
        if code != 0:
            report = build_report(message, dry_run, False, blocked, staged, outputs)
            REPORT.write_text(report, encoding="utf-8")
            print(f"REPORT: {REPORT}")
            return code

        if not no_push:
            code, out = run(["git", "push", "origin", "main"])
            outputs.append("GIT_PUSH\n" + (out or "OK"))
            print(out)
            if code != 0:
                report = build_report(message, dry_run, False, blocked, staged, outputs)
                REPORT.write_text(report, encoding="utf-8")
                print(f"REPORT: {REPORT}")
                return code
            pushed = True

    report = build_report(message, dry_run, pushed, blocked, staged, outputs)
    REPORT.write_text(report, encoding="utf-8")

    print("AUTOSHIP_DONE")
    print(f"REPORT: {REPORT}")
    _, final_status = run(["git", "status", "-sb"])
    print(final_status)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 109 AutoShip Runner")
    parser.add_argument("message", nargs="*", default=["chore: autoship Jarvis update"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()

    message = " ".join(args.message).strip() or "chore: autoship Jarvis update"
    return autoship(message, dry_run=args.dry_run, no_push=args.no_push)


if __name__ == "__main__":
    raise SystemExit(main())
