from pathlib import Path
from datetime import datetime
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "07_RELATORIOS" / "02_TECNICOS"
REPORT_FILE = REPORT_DIR / "ULTIMO_VISUAL_COCKPIT.md"

MUST_NOT = [
    "push, merge ou deploy",
    "tocar VPS, n8n ou produção",
    "abrir/ler .env ou imprimir secrets/tokens/API keys",
    "rodar rm -rf, git reset --hard, force-push, drop table, chmod 0777",
    "alterar projetos sem LOCAL_EXEC handoff aprovado",
]

SAFE_NOW = [
    "ler código em modo read-only (./jarvis readonly-run \"tarefa\")",
    "planejar edição local sem aplicar (./jarvis local-exec-plan \"tarefa\")",
    "preparar pacote LOCAL_EXEC (./jarvis local-exec-handoff \"tarefa\")",
    "revisar saída de executor (./jarvis local-exec-review arquivo.md)",
]


def run(cmd):
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
        return 0, out.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or "").strip()
    except Exception as e:
        return 1, f"ERRO: {e}"


def latest_file(folder, pattern="*.md"):
    p = ROOT / folder
    if not p.exists():
        return None
    files = [x for x in p.glob(pattern) if x.is_file()]
    return max(files, key=lambda x: x.stat().st_mtime) if files else None


def latest_dir(folder):
    p = ROOT / folder
    if not p.exists():
        return None
    dirs = [x for x in p.iterdir() if x.is_dir()]
    return max(dirs, key=lambda x: x.stat().st_mtime) if dirs else None


def rel(path):
    if not path:
        return "—"
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def age_str(path):
    if not path or not path.exists():
        return "—"
    secs = int((datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds())
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


def parse_gate_label(path):
    if not path or not path.exists():
        return "SEM RELATÓRIO"
    text = path.read_text(encoding="utf-8", errors="ignore")
    for label in ("PASSOU", "COM PENDÊNCIAS", "FALHOU"):
        if label in text:
            return label
    return "DESCONHECIDO"


def quality_gate_status():
    _, out = run(["./jarvis", "quality-gate"])
    for label in ("PASSOU", "COM PENDÊNCIAS", "FALHOU"):
        if label in out:
            return label
    return "DESCONHECIDO"


def review_decision(path):
    if not path or not path.exists():
        return "—"
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"##\s+Decisão\s*\n([^\n]+)", text)
    return m.group(1).strip() if m else "—"


def project_lock_from(path):
    if not path:
        return "—"
    m = re.search(r"project-([a-z0-9]+(?:-[a-z0-9]+)*?)-", path.name)
    return m.group(1) if m else "—"


def git_info():
    _, commit = run(["git", "rev-parse", "--short", "HEAD"])
    _, branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    _, status = run(["git", "status", "--short"])
    return commit, branch, bool(status)


def build_text():
    commit, branch, dirty = git_info()

    qg = quality_gate_status()
    smoke_p = latest_file("10_TESTES/SMOKE_TESTS")
    release_p = latest_file("10_TESTES/RELEASE_CHECKS")
    safety_p = latest_file("10_TESTES/SAFETY_GATES")
    smoke = parse_gate_label(smoke_p)
    release = parse_gate_label(release_p)
    safety = parse_gate_label(safety_p)

    session_p = latest_file("05_EXECUCAO/18_LOCAL_EXEC_SESSIONS")
    handoff_p = latest_dir("05_EXECUCAO/15_LOCAL_EXEC_HANDOFFS")
    review_p = latest_file("05_EXECUCAO/16_LOCAL_EXEC_REVIEWS")

    project_lock = project_lock_from(session_p)
    review = review_decision(review_p)

    blocked = []
    if dirty:
        blocked.append("git status sujo — pendências locais para commit/limpar")
    for name, label in (
        ("quality-gate", qg),
        ("smoke-test", smoke),
        ("release-check", release),
        ("safety-gate", safety),
    ):
        if label != "PASSOU":
            blocked.append(f"{name}: {label}")
    if review.startswith("PARAR"):
        blocked.append(f"última review LOCAL_EXEC: {review}")

    next_action = []
    if dirty:
        next_action.append("rever `git status --short` e commitar/limpar antes de seguir")
    if any(l != "PASSOU" for l in (qg, smoke, release, safety)):
        next_action.append("rodar `./jarvis safety-gate` e resolver gate em FALHA/PENDÊNCIA")
    if review.startswith("PARAR"):
        next_action.append("revisar manualmente última saída LOCAL_EXEC antes de aceitar patch")
    if not next_action:
        if project_lock != "—":
            next_action.append(
                f"continuar projeto travado: `./jarvis local-exec-session --project {project_lock} \"tarefa\"`"
            )
        else:
            next_action.append("escolher projeto: `./jarvis project-menu`")

    lines = [
        "# Visual Cockpit — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Status real",
        "Painel local. Nada aplicado em projeto real. Produção não alterada.",
        "",
        "## Header",
        f"- Commit: {commit}",
        f"- Branch: {branch}",
        f"- Git: {'sujo' if dirty else 'limpo'}",
        "",
        "## Gate status (last run)",
        "| Gate          | Result          | Age  | Artifact |",
        "|---------------|-----------------|------|----------|",
        f"| quality-gate  | {qg:<15} | live | (inline) |",
        f"| smoke-test    | {smoke:<15} | {age_str(smoke_p):<4} | {rel(smoke_p)} |",
        f"| release-check | {release:<15} | {age_str(release_p):<4} | {rel(release_p)} |",
        f"| safety-gate   | {safety:<15} | {age_str(safety_p):<4} | {rel(safety_p)} |",
        "",
        "## Latest project lock",
        f"- Projeto: {project_lock}",
        f"- Sessão: {rel(session_p)}",
        f"- Idade: {age_str(session_p)}",
        "",
        "## Latest handoff",
        f"- Pacote: {rel(handoff_p)}",
        f"- Idade: {age_str(handoff_p)}",
        "",
        "## Latest LOCAL_EXEC review decision",
        f"- Decisão: **{review}**",
        f"- Arquivo: {rel(review_p)}",
        f"- Idade: {age_str(review_p)}",
        "",
        "## Next recommended action",
        *[f"- {x}" for x in next_action],
        "",
        "## Blocked / pending",
        *([f"- {x}" for x in blocked] if blocked else ["- nada bloqueando"]),
        "",
        "## Safe to do now",
        *[f"- {x}" for x in SAFE_NOW],
        "",
        "## Must NOT do",
        *[f"- {x}" for x in MUST_NOT],
        "",
        "## Produção",
        "Nada alterado.",
    ]
    return "\n".join(lines) + "\n"


def main():
    print("JARVIS — Theo Padilha AI Worker Visual Cockpit")
    print("Status real: painel local. Nada executado em projeto real.")
    print("")

    text = build_text()
    print(text)

    if os.environ.get("JARVIS_NO_REPORT") == "1":
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
        return

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(text, encoding="utf-8")
    print(f"Relatório: {REPORT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
