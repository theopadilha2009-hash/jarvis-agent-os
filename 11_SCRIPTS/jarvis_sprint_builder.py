from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

BLOCKED = [
    "no automatic commit",
    "no automatic push",
    "no deploy",
    "no .env/secrets",
    "no free shell from cockpit",
    "no external production action",
]

SPRINT_TEMPLATES = [
    {
        "id": "S100-01",
        "title": "Fast Stability Sweep",
        "reason": "Confirms the repo/API is healthy before adding more features.",
        "commands": [
            "python 11_SCRIPTS\\jarvis_cli.py doctor",
            "python 11_SCRIPTS\\jarvis_cli.py diff-review",
            "git diff --stat",
            "git status -sb",
        ],
        "done_when": "Doctor is 7/7 or warnings are clearly explained.",
    },
    {
        "id": "S100-02",
        "title": "Next Feature Pack",
        "reason": "Turns the goal into a focused feature pack instead of random changes.",
        "commands": [
            'python 11_SCRIPTS\\jarvis_cli.py feature-pack "{goal}"',
            "python 11_SCRIPTS\\jarvis_cli.py open-latest",
        ],
        "done_when": "A feature pack exists with objective, files, validation, and blocked actions.",
    },
    {
        "id": "S100-03",
        "title": "Ultra Planning Pass",
        "reason": "Creates a stronger execution plan for the best feature idea.",
        "commands": [
            'python 11_SCRIPTS\\jarvis_cli.py ultra "{goal}"',
            "python 11_SCRIPTS\\jarvis_cli.py open-latest",
        ],
        "done_when": "The plan has a clear implementation path and no unsafe automation.",
    },
    {
        "id": "S100-04",
        "title": "Visual Cockpit Improvement",
        "reason": "Improves the cockpit so work becomes faster and less terminal-heavy.",
        "commands": [
            'python 11_SCRIPTS\\jarvis_cli.py feature-pack "improve Jarvis cockpit for: {goal}"',
            "python 11_SCRIPTS\\jarvis_cli.py diff-review",
        ],
        "done_when": "The visual change is useful, readable, and does not break API routes.",
    },
    {
        "id": "S100-05",
        "title": "Close Sprint Safely",
        "reason": "Ends the sprint with validation before any commit/push decision.",
        "commands": [
            "python -m py_compile 11_SCRIPTS\\jarvis_cli.py 11_SCRIPTS\\jarvis_api.py 11_SCRIPTS\\jarvis_core.py",
            "python 11_SCRIPTS\\jarvis_cli.py doctor",
            "python 11_SCRIPTS\\jarvis_cli.py diff-review",
            "git diff --stat",
            "git status -sb",
        ],
        "done_when": "Only expected files changed and validation passed.",
    },
]


def render_commands(commands: list[str], goal: str) -> list[str]:
    clean_goal = goal.replace('"', "'")
    return [cmd.format(goal=clean_goal) for cmd in commands]


def build_sprint(goal: str) -> dict:
    goal = (goal or "melhorar o Jarvis com pequenos upgrades seguros").strip()
    now = datetime.now().isoformat(timespec="seconds")

    upgrades = []
    for item in SPRINT_TEMPLATES:
        upgrades.append({
            "id": item["id"],
            "title": item["title"],
            "reason": item["reason"],
            "commands": render_commands(item["commands"], goal),
            "done_when": item["done_when"],
        })

    return {
        "ok": True,
        "block": "100",
        "name": "JARVIS Sprint Builder",
        "created_at": now,
        "goal": goal,
        "upgrades": upgrades,
        "blocked_actions": BLOCKED,
        "final_validation": [
            "python -m py_compile 11_SCRIPTS\\jarvis_cli.py 11_SCRIPTS\\jarvis_api.py 11_SCRIPTS\\jarvis_core.py",
            "python 11_SCRIPTS\\jarvis_cli.py doctor",
            "python 11_SCRIPTS\\jarvis_cli.py diff-review",
            "git diff --stat",
            "git status -sb",
        ],
    }


def to_markdown(data: dict) -> str:
    lines = [
        "# JARVIS Sprint Builder ? Block 100",
        "",
        f"Created at: `{data['created_at']}`",
        f"Goal: **{data['goal']}**",
        "",
        "## Safety",
    ]

    for b in data["blocked_actions"]:
        lines.append(f"- {b}")

    lines += ["", "## Sprint Upgrades"]

    for idx, up in enumerate(data["upgrades"], 1):
        lines += [
            "",
            f"### {idx}. {up['title']} ({up['id']})",
            "",
            f"Why: {up['reason']}",
            "",
            "Commands:",
            "",
            "```powershell",
            *up["commands"],
            "```",
            "",
            f"Done when: {up['done_when']}",
        ]

    lines += [
        "",
        "## Final Validation",
        "",
        "```powershell",
        *data["final_validation"],
        "```",
        "",
    ]

    return "\n".join(lines)


def save_sprint(data: dict) -> tuple[Path, Path]:
    out = REPO / "05_EXECUCAO" / "100_JARVIS_SPRINT_BUILDER" / "sprints"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    json_path = out / f"sprint_{stamp}.json"
    md_path = out / f"sprint_{stamp}.md"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(data), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 100 Sprint Builder")
    parser.add_argument("goal", nargs="*", help="Sprint goal")
    parser.add_argument("--save", action="store_true", help="Save sprint plan under 05_EXECUCAO")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip()
    data = build_sprint(goal)

    if args.save:
        json_path, md_path = save_sprint(data)
        print("SPRINT_SAVED")
        print(f"json: {json_path}")
        print(f"md:   {md_path}")
    else:
        print(to_markdown(data))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
