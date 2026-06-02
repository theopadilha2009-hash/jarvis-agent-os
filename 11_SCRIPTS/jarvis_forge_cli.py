from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "107_FEATURE_FORGE_CLI"

BLOCKED_ACTIONS = [
    "no automatic commit",
    "no automatic push",
    "no deploy",
    "no secrets",
    "no .env reading",
    "no free shell through cockpit",
    "no external production action",
]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return text[:60] or "new_feature"


def has_any(text: str, words: list[str]) -> bool:
    low = text.lower()
    return any(w in low for w in words)


def infer_targets(goal: str) -> list[str]:
    targets: list[str] = []
    g = goal.lower()

    if has_any(g, ["terminal", "ops", "hub", "comando", "command", "cli", "status"]):
        targets.append("11_SCRIPTS/jarvis_ops.py")

    if has_any(g, ["api", "endpoint", "route", "http", "server", "webhook"]):
        targets.append("11_SCRIPTS/jarvis_api.py")

    if has_any(g, ["visual", "cockpit", "ui", "interface", "botao", "button", "painel"]):
        targets.append("11_SCRIPTS/jarvis_ui_assets/cockpit.html")

    if has_any(g, ["limpar", "clean", "ignore", "execucao", "local", "noise", "ruido"]):
        targets.append("11_SCRIPTS/jarvis_local_cleaner.py")

    if has_any(g, ["resumo", "resume", "snapshot", "estado", "project"]):
        targets.append("11_SCRIPTS/jarvis_project_resume.py")

    if has_any(g, ["fechar", "closeout", "validar", "validation", "checklist"]):
        targets.append("11_SCRIPTS/jarvis_closeout.py")

    if has_any(g, ["sprint", "upgrades", "roadmap"]):
        targets.append("11_SCRIPTS/jarvis_sprint_builder.py")

    if has_any(g, ["fila", "queue", "polish", "prioridade"]):
        targets.append("11_SCRIPTS/jarvis_polish_queue.py")

    if not targets:
        targets.append(f"11_SCRIPTS/jarvis_{slugify(goal)}.py")

    deduped = []
    for target in targets:
        if target not in deduped:
            deduped.append(target)
    return deduped


def infer_risk(goal: str, targets: list[str]) -> str:
    g = goal.lower()
    high_terms = ["deploy", "production", "prod", "secret", "token", ".env", "password", "senha", "push automatico", "auto push"]
    medium_terms = ["api", "endpoint", "route", "cockpit", "ui", "apply", "write", "delete"]

    if has_any(g, high_terms):
        return "high"
    if len(targets) >= 3 or has_any(g, medium_terms):
        return "medium"
    return "low"


def commit_message(goal: str, targets: list[str]) -> str:
    g = goal.lower()
    short = slugify(goal).replace("_", " ")[:52].strip()

    if any("cockpit.html" in t for t in targets):
        return f"style: polish Jarvis cockpit for {short}"
    if any("jarvis_api.py" in t for t in targets):
        return f"feat: improve Jarvis API for {short}"
    if any("jarvis_ops.py" in t for t in targets):
        return f"feat: improve Jarvis terminal ops for {short}"
    if any("jarvis_local_cleaner.py" in t for t in targets):
        return f"feat: improve Jarvis local cleaner"
    if any("jarvis_closeout.py" in t for t in targets):
        return f"feat: improve Jarvis closeout workflow"
    if any("jarvis_project_resume.py" in t for t in targets):
        return f"feat: improve Jarvis project resume"
    if any("jarvis_sprint_builder.py" in t for t in targets):
        return f"feat: improve Jarvis sprint builder"
    if any("jarvis_polish_queue.py" in t for t in targets):
        return f"feat: improve Jarvis polish queue"
    return f"feat: add Jarvis {slugify(goal).replace('_', ' ')[:45].strip()}"


def build_pack(goal: str) -> dict:
    goal = (goal or "melhorar Jarvis").strip()
    targets = infer_targets(goal)
    risk = infer_risk(goal, targets)

    return {
        "ok": True,
        "block": "107",
        "name": "JARVIS Feature Forge CLI",
        "created_at": now(),
        "goal": goal,
        "slug": slugify(goal),
        "risk": risk,
        "target_files": targets,
        "blocked_actions": BLOCKED_ACTIONS,
        "implementation_shape": [
            "Make the smallest useful implementation first.",
            "Prefer terminal-first workflow unless visual UI is explicitly needed.",
            "Keep generated outputs under 05_EXECUCAO and do not commit them by default.",
            "Do not touch secrets, .env, deploy, or production behavior.",
            "Commit only expected source files after validation.",
        ],
        "validation_commands": [
            "python3 -m py_compile 11_SCRIPTS/jarvis_cli.py 11_SCRIPTS/jarvis_api.py 11_SCRIPTS/jarvis_core.py",
            "python3 11_SCRIPTS/jarvis_ops.py closeout",
            "git diff --stat",
            "git status -sb",
        ],
        "commit_message": commit_message(goal, targets),
        "next_action": "Implement the smallest source change, then run closeout and commit expected files only.",
    }


def to_markdown(pack: dict) -> str:
    lines = [
        "# JARVIS Feature Forge CLI — Block 107",
        "",
        f"Created at: `{pack['created_at']}`",
        f"Goal: **{pack['goal']}**",
        f"Risk: `{pack['risk']}`",
        f"Slug: `{pack['slug']}`",
        "",
        "## Target Files",
        "",
    ]

    for target in pack["target_files"]:
        lines.append(f"- `{target}`")

    lines += ["", "## Implementation Shape", ""]
    for item in pack["implementation_shape"]:
        lines.append(f"- {item}")

    lines += ["", "## Blocked Actions", ""]
    for item in pack["blocked_actions"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Validation",
        "",
        "```bash",
        *pack["validation_commands"],
        "```",
        "",
        "## Commit Suggestion",
        "",
        "```text",
        pack["commit_message"],
        "```",
        "",
        "## Next Action",
        "",
        pack["next_action"],
        "",
    ]

    return "\n".join(lines)


def save_pack(pack: dict) -> tuple[Path, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base = OUT / f"forge_{stamp}_{pack['slug']}"
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(pack), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 107 Feature Forge CLI")
    parser.add_argument("goal", nargs="*", help="Feature goal")
    parser.add_argument("--save", action="store_true", help="Save pack under 05_EXECUCAO")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or "melhorar Jarvis"
    pack = build_pack(goal)

    if args.save:
        json_path, md_path = save_pack(pack)
        print("FORGE_PACK_SAVED")
        print(f"json: {json_path}")
        print(f"md:   {md_path}")
        return 0

    if args.json:
        print(json.dumps(pack, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(pack))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
