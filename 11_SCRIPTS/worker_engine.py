"""
worker_engine.py — JARVIS Sprint 8 real worker engine.

`./jarvis do "pedido"` é a interface principal do worker.

O que faz:
  1. classifica o pedido (ask_router, regex local — sem LLM, sem API)
  2. resolve projeto (PROJECT_REGISTRY)
  3. classifica risco e escolhe rota segura
  4. roda um pequeno loop observe-act executando apenas comandos do
     ALLOWLIST. Tudo que estiver fora vira "bloqueado" e é só impresso.
  5. registra um worker run em 05_EXECUCAO/42_WORKER_RUNS/<ts>_<slug>/
     (gitignored). Suprimível com --dry-run ou JARVIS_NO_REPORT=1.

Hard rules:
  - nunca executa Claude
  - nunca chama API paga
  - nunca toca produção / VPS / n8n real
  - nunca edita projetos-alvo
  - nunca lê .env
  - nunca usa --apply em sub-comandos a menos que explicitamente seguro
  - nunca faz push / PR / merge / deploy / migrations
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "05_EXECUCAO" / "42_WORKER_RUNS"

# Reuse ask_router + secret_scan (stdlib-style internal modules).
sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
try:
    from ask_router import (  # type: ignore
        detect_intent as _di,
        detect_project_alias as _dp,
        _detect_capability_hint as _dc,
        INTENT_NEXT_ACTION,
        INTENT_SELF_EVOLVE,
        INTENT_PROJECT_FIX,
        INTENT_PROJECT_QA,
        INTENT_BROWSER_QA,
        INTENT_FINAL_GATE,
        INTENT_N8N_BLUEPRINT,
        INTENT_APP_BLUEPRINT,
        INTENT_AUTOMATION_BLUEPRINT,
        INTENT_RESEARCH_PLAN,
        INTENT_AGENDA_NOTE,
        INTENT_CAPTURE_NOTE,
        INTENT_OPEN_PROJECT,
        INTENT_CAPABILITY_CHECK,
        INTENT_LIMITS,
        INTENT_TASK_ADD,
        INTENT_TASK_LIST,
        INTENT_UNCLEAR,
    )
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []
    INTENT_NEXT_ACTION = "next_action"
    INTENT_SELF_EVOLVE = "self_evolve"
    INTENT_PROJECT_FIX = "project_fix"
    INTENT_PROJECT_QA = "project_qa"
    INTENT_BROWSER_QA = "browser_qa"
    INTENT_FINAL_GATE = "final_gate"
    INTENT_N8N_BLUEPRINT = "n8n_blueprint"
    INTENT_APP_BLUEPRINT = "app_blueprint"
    INTENT_AUTOMATION_BLUEPRINT = "automation_blueprint"
    INTENT_RESEARCH_PLAN = "research_plan"
    INTENT_AGENDA_NOTE = "agenda_note"
    INTENT_CAPTURE_NOTE = "capture_note"
    INTENT_OPEN_PROJECT = "open_project"
    INTENT_CAPABILITY_CHECK = "capability_check"
    INTENT_LIMITS = "limits"
    INTENT_TASK_ADD = "task_add"
    INTENT_TASK_LIST = "task_list"
    INTENT_UNCLEAR = "unclear"

    def _di(text): return INTENT_UNCLEAR
    def _dp(text, override=None): return override
    def _dc(text): return None


# ── Safety: allowlist ─────────────────────────────────────────────────────────

# A command is allowed if its (cmd[0:2]) matches one of these prefixes AND no
# blocked token appears anywhere in cmd[1:]. The allowlist is intentionally
# narrow: read-only or dry-run / non-destructive write to gitignored runtime.
ALLOWED_PREFIXES = [
    ("./jarvis", "daily"),
    ("./jarvis", "now"),
    ("./jarvis", "state-status"),
    ("./jarvis", "task-add"),
    ("./jarvis", "task-list"),
    ("./jarvis", "task-next"),
    ("./jarvis", "no-claude"),
    ("./jarvis", "blueprint"),
    ("./jarvis", "project-intel"),
    ("./jarvis", "project-memory"),
    ("./jarvis", "capability-check"),
    ("./jarvis", "capability-plan"),
    ("./jarvis", "capabilities"),
    ("./jarvis", "recipe-show"),
    ("./jarvis", "recipe-run"),
    ("./jarvis", "recipe-list"),
    ("./jarvis", "handoff-self"),
    ("./jarvis", "rc-status"),
    ("./jarvis", "health"),
    ("./jarvis", "doctor-agent"),
    ("./jarvis", "ask"),
    ("./jarvis", "plan"),
    ("./jarvis", "limits"),
]

# Tokens that, if found anywhere in a candidate command, immediately mark it as
# blocked — even if the prefix is allowed.
BLOCKED_TOKENS = {
    "--apply",          # never auto-apply anything (reports, debriefs, freezes)
    "--force",
    "--force-weak",
    "--live",           # recipe-run --live actually executes sub-commands
    "report-apply",
    "rc-freeze",
    "state-reset",
    "state-archive",
    "run-prune",
    "self-debrief",
    "project-memory-update",
    "gate-run",
    "gates",
    "push",
    "deploy",
    "merge",
    "tag",
    "pull-request",
    "pr-create",
    "claude",           # do not exec the claude CLI
}


def _is_allowed(cmd):
    """Return True iff cmd matches an allowed prefix AND has no blocked token."""
    if not cmd or len(cmd) < 2:
        return False
    prefix = (cmd[0], cmd[1])
    if prefix not in ALLOWED_PREFIXES:
        return False
    for token in cmd[1:]:
        if token in BLOCKED_TOKENS:
            return False
    return True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _looks_secret_like(text: str) -> bool:
    for _name, pattern in SECRET_PATTERNS:
        if pattern.search(text or ""):
            return True
    return False


def _slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "worker-run"


def _run(cmd, timeout=60):
    """Run cmd in ROOT, capture combined output. Returns (rc, out, summary)."""
    try:
        out = subprocess.check_output(
            cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=timeout
        )
        rc = 0
    except subprocess.CalledProcessError as e:
        out = e.output or ""
        rc = e.returncode
    except subprocess.TimeoutExpired:
        return (124, "<timeout>", "timeout")
    except Exception as e:
        return (1, f"<erro: {e}>", f"erro: {e}")
    summary = _one_line_summary(out)
    return (rc, out, summary)


def _one_line_summary(out: str) -> str:
    """Extract a representative single line from a sub-command output."""
    if not out:
        return "(sem saída)"
    interesting = []
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("##"):
            continue
        interesting.append(line)
    if not interesting:
        return "(sem linha legível)"
    # Prefer a "Resultado:" / "PASSOU" / "DRY-RUN" line if present.
    for line in interesting:
        if line.startswith("Resultado:") or "PASSOU" in line or "DRY-RUN" in line:
            return line[:160]
    # Otherwise return the last non-trivial line (usually the conclusion).
    for line in reversed(interesting):
        if "Produção:" in line:
            continue
        return line[:160]
    return interesting[-1][:160]


# ── Arg parsing ───────────────────────────────────────────────────────────────

def parse_args(argv):
    text_parts = []
    project_override = None
    dry_run = False
    mode = "safe"
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project" and i + 1 < len(argv):
            project_override = argv[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--project="):
            project_override = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1].strip().lower()
            i += 2
            continue
        if a.startswith("--mode="):
            mode = a.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if a == "--dry-run":
            dry_run = True
            i += 1
            continue
        text_parts.append(a)
        i += 1
    text = " ".join(text_parts).strip()
    if mode not in ("safe", "no-claude"):
        mode = "safe"
    return text, project_override, dry_run, mode


# ── Route selection ───────────────────────────────────────────────────────────

ROUTE_RESUME = "resume"
ROUTE_N8N = "n8n_blueprint"
ROUTE_PROJECT = "project_fix_or_inspect"
ROUTE_SELF_EVOLVE = "self_evolve"
ROUTE_NO_CLAUDE = "no_claude"
ROUTE_CAPABILITY = "capability_check"
ROUTE_HANDOFF = "handoff"
ROUTE_UNCLEAR = "unclear"

# Risk classification of the route (informational; not a gate).
RISK_READ_ONLY = "read_only"
RISK_JARVIS_WRITE = "jarvis_write"
RISK_RUNTIME_WRITE = "runtime_write"
RISK_NEEDS_CLAUDE = "needs_claude"
RISK_BLOCKED = "blocked"

_NO_CLAUDE_HINT = re.compile(r"(?i)\b(sem claude|acabou (?:o )?claude|claude (?:fora|indisponível|indisponivel|caiu)|offline)\b")
_HANDOFF_HINT = re.compile(r"(?i)\b(handoff|hand[- ]off|passar (?:para|pra) chatgpt|cole no chatgpt)\b")


def choose_route(text, intent, project, capability_hint, mode):
    """Return (route, risk)."""
    # Explicit --mode no-claude overrides everything except secret-like inputs.
    if mode == "no-claude":
        return (ROUTE_NO_CLAUDE, RISK_RUNTIME_WRITE)

    if _NO_CLAUDE_HINT.search(text or ""):
        return (ROUTE_NO_CLAUDE, RISK_RUNTIME_WRITE)

    if _HANDOFF_HINT.search(text or ""):
        return (ROUTE_HANDOFF, RISK_RUNTIME_WRITE)

    if capability_hint:
        return (ROUTE_CAPABILITY, RISK_READ_ONLY)

    if intent == INTENT_NEXT_ACTION:
        return (ROUTE_RESUME, RISK_READ_ONLY)

    if intent == INTENT_SELF_EVOLVE:
        return (ROUTE_SELF_EVOLVE, RISK_NEEDS_CLAUDE)

    if intent == INTENT_N8N_BLUEPRINT:
        return (ROUTE_N8N, RISK_RUNTIME_WRITE)

    if intent == INTENT_CAPABILITY_CHECK:
        return (ROUTE_CAPABILITY, RISK_READ_ONLY)

    if intent in (
        INTENT_PROJECT_FIX,
        INTENT_PROJECT_QA,
        INTENT_BROWSER_QA,
        INTENT_FINAL_GATE,
        INTENT_OPEN_PROJECT,
    ):
        return (ROUTE_PROJECT, RISK_READ_ONLY if not project else RISK_NEEDS_CLAUDE)

    return (ROUTE_UNCLEAR, RISK_READ_ONLY)


# ── Route action plans ────────────────────────────────────────────────────────
# Each entry: (label, command_list, blocked_reason_or_None)
# blocked_reason_or_None — if non-None, this step is printed but NOT executed.

def plan_resume(text, project):
    return [
        ("Dashboard de uma tela", ["./jarvis", "daily"], None),
        ("Estado runtime", ["./jarvis", "state-status"], None),
    ], './jarvis next', None


def plan_n8n(text, project, mode):
    actions = [
        ("Recipe dry-run n8n-workflow",
         ["./jarvis", "recipe-run", "n8n-workflow", "--goal", text, "--dry-run"],
         None),
    ]
    if mode == "no-claude":
        actions.append((
            "Pacote no-claude (n8n)",
            ["./jarvis", "no-claude", f"workflow n8n: {text}"],
            None,
        ))
    return actions, f'./jarvis start "criar workflow n8n: {text}"', None


def plan_project(text, project):
    if not project:
        return [], None, "Sem project alias detectado — peça com --project ALIAS."
    actions = [
        ("Inspeção read-only", ["./jarvis", "project-intel", "--project", project], None),
        ("Plano local (texto-only, sem --save)",
         ["./jarvis", "plan", f"{text} no projeto {project} sem produção"],
         None),
    ]
    return actions, f'./jarvis start "{project}: {text}"', None


def plan_self_evolve(text, project):
    actions = [
        ("Health do JARVIS", ["./jarvis", "health"], None),
        ("Recipe dry-run self-evolve",
         ["./jarvis", "recipe-run", "self-evolve", "--goal", text, "--dry-run"],
         None),
    ]
    return actions, f'./jarvis start "evoluir o JARVIS: {text}"', None


def plan_no_claude(text, project, dry_run):
    no_claude_cmd = ["./jarvis", "no-claude", text]
    task_cmd = ["./jarvis", "task-add", f"no-claude: {text}"]
    if dry_run:
        no_claude_cmd.append("--dry-run")
        task_cmd.append("--dry-run")
    actions = [
        ("Pacote no-claude", no_claude_cmd, None),
        ("Enfileirar task local", task_cmd, None),
    ]
    return actions, './jarvis state-status', None


def plan_capability(text, project, capability_hint):
    name = capability_hint or "google_calendar"
    actions = [
        ("Detalhe da capability", ["./jarvis", "capability-check", name], None),
    ]
    return actions, f'./jarvis capability-plan {name}', None


def plan_handoff(text, project):
    actions = [
        ("Snapshot do JARVIS (terminal-only)", ["./jarvis", "handoff-self"], None),
    ]
    return actions, './jarvis handoff-self --save', None


def plan_unclear(text, project, dry_run):
    ask_cmd = ["./jarvis", "ask", text, "--dry-run"]
    task_cmd = ["./jarvis", "task-add", f"revisar request unclear: {text}", "--dry-run"]
    actions = [
        ("Router local em modo explicação", ask_cmd, None),
        ("Marcar revisão (dry-run)", task_cmd, None),
    ]
    return actions, f'./jarvis no-claude "{text}" --dry-run', None


def build_plan(route, text, project, mode, dry_run, capability_hint):
    """Return (actions, next_cmd, error). error != None => abort with message."""
    if route == ROUTE_RESUME:
        return plan_resume(text, project)
    if route == ROUTE_N8N:
        return plan_n8n(text, project, mode)
    if route == ROUTE_PROJECT:
        return plan_project(text, project)
    if route == ROUTE_SELF_EVOLVE:
        return plan_self_evolve(text, project)
    if route == ROUTE_NO_CLAUDE:
        return plan_no_claude(text, project, dry_run)
    if route == ROUTE_CAPABILITY:
        return plan_capability(text, project, capability_hint)
    if route == ROUTE_HANDOFF:
        return plan_handoff(text, project)
    return plan_unclear(text, project, dry_run)


# ── Worker log ────────────────────────────────────────────────────────────────

def _write_worker_log(text, route, risk, mode, project, intent, actions_recorded,
                      next_cmd, capability_hint):
    """Write 6 markdown files to 42_WORKER_RUNS/<ts>_<slug>/."""
    ts_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    slug = _slugify(text)
    pkg = WORKER_DIR / f"{ts_dir}_{slug}"
    try:
        pkg.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return None, f"FALHA criando pacote: {e}"

    ts = datetime.now().isoformat(timespec="seconds")

    (pkg / "01_REQUEST.md").write_text(
        f"# Worker Request\n\n## Timestamp\n{ts}\n\n## Texto original\n{text}\n",
        encoding="utf-8",
    )
    (pkg / "02_ROUTE.md").write_text(
        "# Worker Route\n\n"
        f"- route: `{route}`\n"
        f"- risk: `{risk}`\n"
        f"- mode: `{mode}`\n"
        f"- intent: `{intent}`\n"
        f"- project: `{project or '(nenhum)'}`\n"
        f"- capability: `{capability_hint or '(n/a)'}`\n",
        encoding="utf-8",
    )
    actions_md = ["# Actions\n"]
    for i, (label, cmd, status, _summary) in enumerate(actions_recorded, 1):
        actions_md.append(f"\n## {i}. {label}\n")
        actions_md.append(f"- command: `{' '.join(cmd)}`\n")
        actions_md.append(f"- status: {status}\n")
    (pkg / "03_ACTIONS.md").write_text("".join(actions_md), encoding="utf-8")

    obs_md = ["# Observations (one-line summary por step)\n"]
    for i, (label, cmd, status, summary) in enumerate(actions_recorded, 1):
        obs_md.append(f"\n## {i}. {label}\n")
        obs_md.append(f"- summary: {summary}\n")
    (pkg / "04_OBSERVATIONS.md").write_text("".join(obs_md), encoding="utf-8")

    (pkg / "05_NEXT_COMMAND.md").write_text(
        f"# Próximo comando sugerido\n\n```\n{next_cmd or '(nenhum)'}\n```\n",
        encoding="utf-8",
    )

    (pkg / "06_STATUS_REAL.md").write_text(
        "# Status real\n\n"
        "## O que JARVIS fez (loop observe-act)\n"
        f"- {len([a for a in actions_recorded if a[2] == 'EXECUTADO'])} comando(s) seguros do allowlist\n\n"
        "## O que JARVIS NÃO fez\n"
        "- não executou Claude\n"
        "- não chamou API paga (Anthropic/OpenAI)\n"
        "- não tocou produção / VPS / n8n real\n"
        "- não editou projetos-alvo\n"
        "- não leu .env nem imprimiu segredos\n"
        "- não fez push / PR / merge / deploy / migrations\n",
        encoding="utf-8",
    )
    return pkg, None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    text, project_override, dry_run, mode = parse_args(sys.argv[1:])
    if not text:
        print('Uso: ./jarvis do "pedido" [--project ALIAS] [--mode safe|no-claude] [--dry-run]')
        sys.exit(1)
    if _looks_secret_like(text):
        print("FALHA: pedido parece conter segredo. JARVIS recusa registrar.")
        sys.exit(1)

    intent = _di(text)
    project = _dp(text, project_override)
    capability_hint = _dc(text) if intent == INTENT_CAPABILITY_CHECK or not intent else _dc(text)
    route, risk = choose_route(text, intent, project, capability_hint, mode)

    print("JARVIS — Worker Engine")
    print("Status real: loop observe-act local. Sem Claude. Sem API. Sem produção.")
    print("")
    print("## Pedido")
    print(f'  "{text}"')
    print("")
    print("## Interpretação")
    print(f"  route:   {route}")
    print(f"  intent:  {intent}")
    print(f"  project: {project or '(não detectado)'}")
    print(f"  risk:    {risk}")
    print(f"  mode:    {mode}")
    if capability_hint:
        print(f"  capability: {capability_hint}")
    print("")

    actions, next_cmd, error = build_plan(
        route, text, project, mode, dry_run, capability_hint
    )

    if error:
        print("## Erro de plano")
        print(f"  {error}")
        print("")
        print("## Próximo comando sugerido")
        print('  ./jarvis ask "{text}" --dry-run')
        print("Produção: nada alterado.")
        sys.exit(1)

    print("## Ações planejadas")
    if not actions:
        print("  (nenhuma — fluxo apenas informativo)")
    for i, (label, cmd, blocked_reason) in enumerate(actions, 1):
        cmd_str = " ".join(cmd) if cmd else ""
        if blocked_reason:
            print(f"  {i}. [BLOQUEADO] {label}")
            print(f"     $ {cmd_str}")
            print(f"     motivo: {blocked_reason}")
        else:
            print(f"  {i}. {label}")
            print(f"     $ {cmd_str}")
    print("")

    # Execute the actions that are allowed; dry-run skips execution.
    actions_recorded = []
    if dry_run:
        print("## Loop observe-act")
        print("  --dry-run: nenhum comando foi executado.")
        for label, cmd, blocked_reason in actions:
            if blocked_reason:
                actions_recorded.append((label, cmd, "BLOQUEADO", blocked_reason))
            else:
                actions_recorded.append((label, cmd, "PULADO (dry-run)", "—"))
    else:
        print("## Loop observe-act")
        for i, (label, cmd, blocked_reason) in enumerate(actions, 1):
            if blocked_reason:
                print(f"  {i}. [BLOQUEADO] {label} — {blocked_reason}")
                actions_recorded.append((label, cmd, "BLOQUEADO", blocked_reason))
                continue
            if not _is_allowed(cmd):
                msg = "fora do allowlist do worker"
                print(f"  {i}. [BLOQUEADO] {label} — {msg}")
                print(f"     $ {' '.join(cmd)}")
                actions_recorded.append((label, cmd, "BLOQUEADO", msg))
                continue
            print(f"  {i}. {label}")
            print(f"     $ {' '.join(cmd)}")
            rc, _out, summary = _run(cmd, timeout=90)
            tag = "PASS" if rc == 0 else f"FAIL(rc={rc})"
            print(f"     → {tag}  {summary}")
            actions_recorded.append((label, cmd, "EXECUTADO", f"{tag}: {summary}"))
    print("")

    # Always print what JARVIS did NOT do.
    print("## Bloqueado / não executado")
    print("  - Claude não executado")
    print("  - produção / VPS / n8n real / Supabase prod não tocados")
    print("  - projeto-alvo não editado")
    print("  - APIs pagas (Anthropic/OpenAI) não chamadas")
    print("  - .env não lido; segredos não impressos")
    print("  - sem push / PR / merge / deploy / migrations")
    print("")

    pkg_rel = None
    log_skipped_reason = None
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"
    if dry_run:
        log_skipped_reason = "--dry-run"
    elif no_report:
        log_skipped_reason = "JARVIS_NO_REPORT=1"
    else:
        pkg, err = _write_worker_log(
            text, route, risk, mode, project, intent,
            actions_recorded, next_cmd, capability_hint,
        )
        if err:
            log_skipped_reason = err
        elif pkg:
            pkg_rel = pkg.relative_to(ROOT)

    print("## Resultado")
    if pkg_rel:
        print(f"  worker run: {pkg_rel}/")
    elif log_skipped_reason:
        print(f"  worker run: pulado ({log_skipped_reason})")
    print("")

    print("## Próximo comando")
    print(f"  {next_cmd or '(nenhum)'}")
    print("")
    print("Produção: nada alterado. Claude não executado.")


if __name__ == "__main__":
    main()
