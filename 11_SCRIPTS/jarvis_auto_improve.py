from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "110_AUTO_IMPROVE_LOOP"
REPORT = OUT / "AUTO_IMPROVE_REPORT.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def py(script: str, *args: str) -> tuple[int, str]:
    return run([sys.executable, script, *args])


def git_clean() -> bool:
    _, out = run(["git", "status", "--porcelain"])
    return not out.strip()


def existing(path: str) -> bool:
    return (REPO / path).exists()


def next_improvements() -> list[dict]:
    items = []

    if existing("11_SCRIPTS/jarvis_ops.py"):
        items.append({
            "title": "Reduce terminal friction",
            "goal": "criar comandos cada vez mais únicos para status, forge, closeout e ship",
            "target_files": ["11_SCRIPTS/jarvis_ops.py"],
            "risk": "low",
        })

    if existing("11_SCRIPTS/jarvis_autoship.py"):
        items.append({
            "title": "Improve autoship safety",
            "goal": "melhorar ship automático com validação de arquivos esperados e relatório final",
            "target_files": ["11_SCRIPTS/jarvis_autoship.py"],
            "risk": "medium",
        })

    if existing("11_SCRIPTS/jarvis_progress_dashboard.py"):
        items.append({
            "title": "Improve progress dashboard",
            "goal": "mostrar progresso, risco, últimos blocos e próxima ação de forma mais limpa",
            "target_files": ["11_SCRIPTS/jarvis_progress_dashboard.py"],
            "risk": "low",
        })

    items.append({
        "title": "Create next safe feature block",
        "goal": "gerar próximo bloco grande seguro usando forge, validar e enviar com ship",
        "target_files": ["11_SCRIPTS/"],
        "risk": "low",
    })

    return items


def build_report(goal: str) -> str:
    _, branch = run(["git", "status", "-sb"])
    _, commits = run(["git", "log", "--oneline", "--decorate", "-10"])
    _, diff = run(["git", "diff", "--stat"])
    _, porcelain = run(["git", "status", "--porcelain"])

    code_forge, forge = py("11_SCRIPTS/jarvis_ops.py", "forge", goal, "--print")
    code_progress, progress = py("11_SCRIPTS/jarvis_ops.py", "progress")
    code_closeout, closeout = py("11_SCRIPTS/jarvis_ops.py", "closeout")

    clean = not porcelain.strip()
    improvements = next_improvements()

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "git_clean": clean,
        "branch": branch,
        "next_improvements": improvements,
        "recommended_next_command": f'python3 11_SCRIPTS/jarvis_ops.py forge "{improvements[0]["goal"]}"',
        "ship_command_after_changes": 'python3 11_SCRIPTS/jarvis_ops.py ship "feat: name"',
    }

    lines = [
        "# JARVIS Auto Improve Loop — Block 110",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Goal: **{goal}**",
        f"Git clean: `{'yes' if clean else 'no'}`",
        "",
        "## Branch",
        "",
        "```text",
        branch or "-",
        "```",
        "",
        "## Current Diff",
        "",
        "```text",
        diff or "clean",
        "```",
        "",
        "## Uncommitted Files",
        "",
        "```text",
        porcelain or "clean",
        "```",
        "",
        "## Last Commits",
        "",
        "```text",
        commits or "-",
        "```",
        "",
        "## Next Improvement Queue",
        "",
    ]

    for i, item in enumerate(improvements, 1):
        lines.append(f"{i}. **{item['title']}** — risk `{item['risk']}`")
        lines.append(f"   - goal: `{item['goal']}`")
        lines.append(f"   - files: `{', '.join(item['target_files'])}`")

    lines += [
        "",
        "## Forge Output",
        "",
        "```text",
        forge or "-",
        "```",
        "",
        "## Progress Output",
        "",
        "```text",
        progress or "-",
        "```",
        "",
        "## Closeout Output",
        "",
        "```text",
        closeout or "-",
        "```",
        "",
        "## Recommended Next Commands",
        "",
        "```bash",
        payload["recommended_next_command"],
        payload["ship_command_after_changes"],
        "```",
        "",
        "## Machine Payload",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ]

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 110 Auto Improve Loop")
    parser.add_argument("goal", nargs="*", default=["melhorar", "autonomia", "do", "Jarvis"])
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar autonomia do Jarvis"

    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report(goal)
    REPORT.write_text(report, encoding="utf-8")

    print("AUTO_IMPROVE_REPORT_SAVED")
    print(REPORT)

    if args.print:
        print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
