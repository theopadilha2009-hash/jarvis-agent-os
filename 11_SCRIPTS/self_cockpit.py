"""
self_cockpit.py — JARVIS-on-JARVIS read-only cockpit.

Wraps project_status / project_memory for project=jarvis-core and adds a
"next safest action" derivation. Three sub-modes via flags:

  --mode status     compact status of the JARVIS repo itself
  --mode cockpit    status + last mission + memory excerpt + next action
  --mode next       only the next recommended command (one-liner)

Defaults to 'cockpit'. Never edits anything.
"""
from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ALIAS = "jarvis-core"


def run(cmd, cwd=None, timeout=15):
    try:
        return 0, subprocess.check_output(cmd, cwd=cwd or ROOT, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"<erro: {e}>"


def parse_args(argv):
    mode = "cockpit"
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--mode":
            if i + 1 < len(argv):
                mode = argv[i + 1].strip().lower()
                i += 2
                continue
        if a.startswith("--mode="):
            mode = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        i += 1
    if mode not in ("status", "cockpit", "next"):
        print(f"FALHA: --mode inválido: {mode}. Use status|cockpit|next.")
        sys.exit(1)
    return mode


def _suggest_next(branch: str, dirty: bool, latest_mission_dir, memory_state: str):
    """Pure decision tree. Returns list[str] (1+ lines).

    Always recommends `./jarvis go "..."` as the primary entry point so
    Theo only needs to remember one verb. Lower-level commands are kept
    visible underneath for power use."""
    if branch in ("main", "master"):
        return [
            f"⚠ Branch {branch} — PARE. Crie branch dedicada.",
            "  git checkout -b feature/jarvis-<topic>",
        ]
    if dirty:
        return [
            "Tree suja — primeiro decidir o que está pendente.",
            "  git status --short",
            "  git diff --stat",
            "  (commitar com git add <paths> ou descartar)",
        ]
    # clean tree
    if latest_mission_dir is None:
        return [
            "Sem missão JARVIS registrada. Sugestão principal:",
            '  ./jarvis go "evoluir o JARVIS para reduzir trabalho manual"',
            "Power-user equivalente:",
            '  ./jarvis self-evolve --goal "..." --copy',
        ]
    if memory_state in ("missing", "blank"):
        return [
            "Missão existe, memória ausente — registre debrief:",
            "  ./jarvis self-debrief --from-git --dry-run",
            "  ./jarvis self-debrief --from-git --apply",
        ]
    return [
        "Tree limpa + memória registrada. Sugestão principal:",
        '  ./jarvis go "o que faço agora"',
        "Outras boas opções:",
        "  env JARVIS_NO_REPORT=1 ./jarvis safety-gate",
        "  env JARVIS_NO_REPORT=1 ./jarvis smoke-test",
        '  ./jarvis go "evoluir o JARVIS para reduzir trabalho manual"',
    ]


def _find_latest_jarvis_mission():
    missions_dir = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"
    if not missions_dir.exists():
        return None
    matches = [d for d in missions_dir.iterdir() if d.is_dir() and f"project-{ALIAS}_" in d.name]
    if not matches:
        return None
    return max(matches, key=lambda d: d.stat().st_mtime)


def _memory_state():
    """Returns ('missing'|'blank'|'entries'|'freeform', last_excerpt)."""
    md = ROOT / "04_PROJETOS" / "JARVIS_CORE" / "PROJECT_STATUS.md"
    if not md.exists():
        return "missing", None
    text = md.read_text(encoding="utf-8", errors="ignore")
    non_template = [l for l in text.splitlines() if l.strip() and not l.startswith("#") and l.strip() != "-"]
    if not non_template:
        return "blank", None
    marker = "<!-- jarvis-memory-entry -->"
    if marker in text:
        last = next((c for c in reversed(text.split(marker)) if c.strip()), "")
        excerpt = "\n".join([l for l in last.splitlines() if l.strip()][:8])
        return "entries", excerpt
    excerpt = "\n".join([l for l in text.splitlines() if l.strip()][:8])
    return "freeform", excerpt


def main():
    mode = parse_args(sys.argv[1:])

    # Common context
    _, branch = run(["git", "branch", "--show-current"])
    _, status_short = run(["git", "status", "--short"])
    dirty_lines = [l for l in status_short.splitlines() if l.strip()]
    dirty = bool(dirty_lines)
    _, log_lines = run(["git", "log", "--oneline", "-5"])
    latest_mission = _find_latest_jarvis_mission()
    mem_state, mem_excerpt = _memory_state()
    next_lines = _suggest_next(branch or "", dirty, latest_mission, mem_state)

    if mode == "next":
        # one-liner-ish: first hint plus the first command suggestion.
        print("JARVIS — Theo Padilha AI Worker Self Next")
        print("Status real: leitura local. Nada foi editado.")
        print("")
        for line in next_lines:
            print(line)
        print("")
        print("Produção: nada alterado.")
        return

    print("JARVIS — Theo Padilha AI Worker Self " + ("Cockpit" if mode == "cockpit" else "Status"))
    print("Status real: leitura local do JARVIS. Nada foi editado.")
    print("")
    print(f"repo: {ROOT}")
    print(f"branch: {branch or '<sem branch>'}" + (" ⚠ MAIN" if branch in ("main", "master") else ""))
    print(f"dirty: {'yes (' + str(len(dirty_lines)) + ' arquivo(s))' if dirty else 'no'}")
    if dirty and mode == "cockpit":
        for line in dirty_lines[:6]:
            print(f"  {line}")
        if len(dirty_lines) > 6:
            print(f"  ... (+{len(dirty_lines) - 6} linhas)")
    if log_lines:
        print("recent commits:")
        for line in log_lines.splitlines():
            print(f"  {line}")
    print("")

    # Mission
    if latest_mission is not None:
        info_name = latest_mission.name
        marker = "_project-"
        mode_str = "?"
        if marker in info_name:
            tail = info_name[info_name.find(marker) + 1:]
            parts = tail.split("_", 2)
            if len(parts) > 1:
                mode_str = parts[1]
        age_s = int((datetime.now() - datetime.fromtimestamp(latest_mission.stat().st_mtime)).total_seconds())
        age = f"{age_s // 60}m" if age_s < 3600 else (f"{age_s // 3600}h" if age_s < 86400 else f"{age_s // 86400}d")
        print("## Última missão JARVIS")
        print(f"  pack: {latest_mission.relative_to(ROOT)}")
        print(f"  modo: {mode_str}   idade: {age}")
        prompt = latest_mission / "01_CLAUDE_PROMPT.md"
        if prompt.exists():
            print(f"  prompt: {prompt.relative_to(ROOT)}")
            if mode == "cockpit":
                print(f"  copy:   cat \"{prompt}\" | pbcopy")
                print(f"  short:  ./jarvis claude-copy-latest --project {ALIAS}")
    else:
        print("## Última missão JARVIS")
        print('  (nenhuma — gere com `./jarvis self-evolve --goal "..." --copy`)')
    print("")

    if mode == "cockpit":
        # Memory excerpt
        print("## Memória registrada (04_PROJETOS/JARVIS_CORE/PROJECT_STATUS.md)")
        if mem_state == "missing":
            print("  (arquivo ausente — registre debrief com self-debrief)")
        elif mem_state == "blank":
            print("  (template vazio — JARVIS amnésico de si mesmo)")
        else:
            for line in (mem_excerpt or "").splitlines():
                print(f"  {line}")
        print("")

        # Gates suggestion
        print("## Gates sugeridos")
        print("  env JARVIS_NO_REPORT=1 ./jarvis safety-gate")
        print("  env JARVIS_NO_REPORT=1 ./jarvis smoke-test")
        print("  ./jarvis command-audit")
        print("")

    # Next action
    print("## Próximo passo seguro")
    for line in next_lines:
        print(f"  {line}")
    print("")
    print("Produção: nada alterado.")


if __name__ == "__main__":
    main()
