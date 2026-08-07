"""
worker_engine.py — JARVIS worker engine (Sprint 8 + Sprint 8.1 reinforced).

`./jarvis do "pedido"` é a interface principal. Sem argumento, faz smart
resume baseado no estado real (work session / gates / top task).

O que mudou em 8.1 vs 8.0:
  - sem argumento → smart resume (decide via state, não mais erro).
  - allowlist inclui geradores de mission pack (goal-sprint, qa-sprint,
    self-evolve, blueprint, claude-launch --print-only) — todos
    escrevem em pastas gitignored.
  - rotas produzem ARTEFATOS REAIS, não previews:
      project_fix       → project-intel + goal-sprint (mission pack pronto)
      self_evolve       → health + self-evolve (mission pack pronto)
      n8n_blueprint     → blueprint --type n8n (pacote local pronto)
      no_claude         → pacote no-claude + task local
      capability_check  → capability-check + capability-plan (se aplicável)
      handoff           → handoff-self --save (arquivo persistido)
      resume / unclear  → orientação estado-aware
  - --copy joga o prompt principal do último artefato no clipboard.
  - worker log inclui trecho da mission e o path exato para `cat | pbcopy`.

Mantém todas as garantias de segurança:
  - nunca executa Claude
  - nunca chama API paga
  - nunca toca produção / VPS / n8n real / Supabase prod
  - nunca edita projetos-alvo
  - nunca lê .env nem imprime segredos
  - nunca usa --apply / --live / --force em sub-comandos
  - nunca push / PR / merge / deploy / migrations / tag
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "05_EXECUCAO" / "42_WORKER_RUNS"
CURRENT_SESSION = ROOT / "05_EXECUCAO" / "36_WORK_SESSIONS" / "current.json"
GATES_LATEST = ROOT / "05_EXECUCAO" / "37_GATES" / "latest.json"
TASKS_JSONL = ROOT / "05_EXECUCAO" / "34_TASKS" / "tasks.jsonl"
ASK_UNCLEAR = ROOT / "05_EXECUCAO" / "32_ASK_LEARNING" / "UNCLEAR_REQUESTS.md"
MISSIONS_DIR = ROOT / "05_EXECUCAO" / "21_CLAUDE_MISSIONS"
BLUEPRINTS_DIR = ROOT / "05_EXECUCAO" / "40_BLUEPRINTS"
PERSONAL_DIR = ROOT / "05_EXECUCAO" / "64_PERSONAL_TOOLS"

# Reuse intents + secret detection from existing internal modules.
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
        INTENT_SCREEN_CAPTURE,
        INTENT_IMAGE_TO_PDF,
        INTENT_IMAGE_CONVERT,
        INTENT_SPEAK,
        INTENT_MESSAGE_DRAFT,
        INTENT_MESSAGE_SEND,
        INTENT_MEMORY_SAVE,
        INTENT_STORAGE_SCAN,
        INTENT_FILES_TRIAGE,
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
    INTENT_SCREEN_CAPTURE = "screen_capture"
    INTENT_IMAGE_TO_PDF = "image_to_pdf"
    INTENT_IMAGE_CONVERT = "image_convert"
    INTENT_SPEAK = "speak"
    INTENT_MESSAGE_DRAFT = "message_draft"
    INTENT_MESSAGE_SEND = "message_send"
    INTENT_MEMORY_SAVE = "memory_save"
    INTENT_STORAGE_SCAN = "storage_scan"
    INTENT_FILES_TRIAGE = "files_triage"
    INTENT_UNCLEAR = "unclear"

    def _di(text): return INTENT_UNCLEAR
    def _dp(text, override=None): return override
    def _dc(text): return None

# Project deep intel (Sprint 8.3) — optional, soft import.
try:
    import project_deep_intel as _pdi  # type: ignore
except Exception:
    _pdi = None


# ── Safety: allowlist ─────────────────────────────────────────────────────────
# `do` may auto-execute only these prefixes. Each ALSO must contain no blocked
# token anywhere in argv. The allowlist now includes mission-pack generators
# because they write to gitignored runtime — they are the "real artifact" path.
ALLOWED_PREFIXES = {
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
    ("./jarvis", "project-cockpit"),
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
    ("./jarvis", "screen-capture"),
    ("./jarvis", "image-to-pdf"),
    ("./jarvis", "image-convert"),
    ("./jarvis", "speak"),
    ("./jarvis", "message-draft"),
    ("./jarvis", "message-send"),
    ("./jarvis", "memory-save"),
    ("./jarvis", "storage-scan"),
    ("./jarvis", "files-triage"),
    # Sprint 8.1 — mission pack generators (write to gitignored 21_CLAUDE_MISSIONS).
    ("./jarvis", "goal-sprint"),
    ("./jarvis", "qa-sprint"),
    ("./jarvis", "browser-qa"),
    ("./jarvis", "self-evolve"),
    ("./jarvis", "claude-launch"),
}

# Tokens that, if found anywhere in candidate command, immediately mark it as
# blocked — even if the prefix is allowed. Conservative on purpose.
BLOCKED_TOKENS = {
    "--apply",
    "--force",
    "--force-weak",
    "--live",
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
    "claude",        # never exec the claude CLI
}


def _is_allowed(cmd):
    if not cmd or len(cmd) < 2:
        return False
    if (cmd[0], cmd[1]) not in ALLOWED_PREFIXES:
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


def _safe_load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _has_cmd(name: str) -> bool:
    return shutil.which(name) is not None


def _pbcopy(text: str) -> bool:
    """Copy text to clipboard via pbcopy. Returns True on success."""
    if not _has_cmd("pbcopy"):
        return False
    try:
        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(text.encode("utf-8"))
        return p.returncode == 0
    except Exception:
        return False


def _run(cmd, timeout=120):
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
    return (rc, out, _one_line_summary(out))


def _one_line_summary(out: str) -> str:
    if not out:
        return "(sem saída)"
    interesting = []
    for raw in out.splitlines():
        line = raw.strip()
        if not line or line.startswith("##"):
            continue
        interesting.append(line)
    if not interesting:
        return "(sem linha legível)"
    for line in interesting:
        if (
            line.startswith("Resultado:")
            or "PASSOU" in line
            or "DRY-RUN" in line
            or line.startswith("Mission pack:")
            or line.startswith("Prompt:")
            or line.startswith("Próximo:")
        ):
            return line[:160]
    for line in reversed(interesting):
        if "Produção:" in line:
            continue
        return line[:160]
    return interesting[-1][:160]


def _latest_dir(parent: Path, prefix: str | None = None) -> Path | None:
    if not parent.exists():
        return None
    cands = [
        p for p in parent.iterdir()
        if p.is_dir() and not p.name.startswith(".")
        and (prefix is None or p.name.startswith(prefix) or prefix in p.name)
    ]
    return sorted(cands, key=lambda p: p.name, reverse=True)[0] if cands else None


def _latest_subtree_after(parent: Path, since: float) -> Path | None:
    """Most recent immediate subdir created after `since` (epoch seconds)."""
    if not parent.exists():
        return None
    cands = [
        p for p in parent.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.stat().st_mtime >= since
    ]
    return sorted(cands, key=lambda p: p.stat().st_mtime, reverse=True)[0] if cands else None


def _read_text_capped(path: Path, max_chars: int = 4000) -> str:
    try:
        t = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"<erro lendo {path}: {e}>"
    if len(t) <= max_chars:
        return t
    return t[:max_chars] + f"\n\n…(truncado em {max_chars} chars)…"


# ── State inspection (smart resume) ──────────────────────────────────────────

def _top_pending_task():
    if not TASKS_JSONL.exists():
        return None
    try:
        seen = {}
        with TASKS_JSONL.open(encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except Exception:
                    continue
                tid = ev.get("task_id") or ev.get("id")
                if not tid:
                    continue
                if tid not in seen:
                    seen[tid] = ev
                else:
                    seen[tid].update(ev)
        for _tid, ev in seen.items():
            if ev.get("status") in ("pending", None):
                return ev
        return None
    except Exception:
        return None


def _git_dirty_files():
    """Return list of dirty files via `git status --short`, or None on error."""
    try:
        out = subprocess.check_output(
            ["git", "status", "--short"], cwd=ROOT, text=True,
            stderr=subprocess.STDOUT, timeout=5,
        )
    except Exception:
        return None
    return [l for l in out.splitlines() if l.strip()]


def _smart_resume_decision():
    """Look at JARVIS state, return (next_command, reason, dirty_files)."""
    dirty = _git_dirty_files()
    if dirty:
        # Dirty tree dominates — Theo needs to commit / stash / revert first.
        return (
            "git status --short   # depois: git add -p && git commit -m '...' OU git restore .",
            f"ATENÇÃO: árvore suja ({len(dirty)} arquivo(s)). Resolva antes de gates ou release.",
            dirty,
        )

    session = _safe_load_json(CURRENT_SESSION)
    gates = _safe_load_json(GATES_LATEST)
    top = _top_pending_task()

    if session:
        st = session.get("status")
        nc = session.get("next_command")
        if st == "blocked":
            return ("./jarvis state-status",
                    "sessão atual está blocked — revise antes de continuar",
                    None)
        if nc:
            return (nc, f"sessão ativa diz next_command={nc!r} (status={st})", None)
        if st in ("started", "mission_generated"):
            return ("./jarvis next",
                    "sessão ativa aguarda colar missão no Claude",
                    None)
        if st == "report_pending":
            return ("./jarvis report-template",
                    "sessão aguarda relatório do Claude — gere o template `cat > /tmp/...`",
                    None)
        if st in ("report_checked", "debrief_applied"):
            return ("./jarvis gates",
                    "debrief aplicado — rode os gates para fechar a sessão",
                    None)
        if st == "gates_passed":
            return ("./jarvis finish",
                    "gates passaram — feche a sessão",
                    None)
        return ("./jarvis work-status",
                f"sessão ativa com status={st!r} — inspecione antes de agir",
                None)

    if gates and gates.get("all_ok") is False:
        return ("./jarvis gates",
                "último gate-run não está all_ok — investigue / re-rode",
                None)

    if top:
        text = (top.get("text") or top.get("request") or "").strip()
        snippet = text.replace('"', "'")[:80]
        return (f'./jarvis do "{snippet}"',
                f"top task pendente: {snippet}",
                None)

    return ('./jarvis do "o que você quer fazer agora"',
            "nenhuma sessão / nenhum gate falho / nenhuma task — descreva o pedido",
            None)


# ── Arg parsing ───────────────────────────────────────────────────────────────

_REUSE_HINT = re.compile(
    r"(?i)\b(melhor[ae]?(?: a)?(?: última| ultima)? miss[ãa]o|"
    r"regenera|faz (?:de )?(?:novo|dnv)|repete|reuse)\b"
)


def parse_args(argv):
    text_parts = []
    project_override = None
    dry_run = False
    mode = "safe"
    copy_flag = False
    reuse_last = False
    report_path = None
    auto_finish = False
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
        if a == "--copy":
            copy_flag = True
            i += 1
            continue
        if a == "--no-copy":
            copy_flag = False
            i += 1
            continue
        if a == "--reuse-last":
            reuse_last = True
            i += 1
            continue
        if a == "--report" and i + 1 < len(argv):
            report_path = argv[i + 1]
            i += 2
            continue
        if a.startswith("--report="):
            report_path = a.split("=", 1)[1]
            i += 1
            continue
        if a == "--auto-finish":
            auto_finish = True
            i += 1
            continue
        text_parts.append(a)
        i += 1
    text = " ".join(text_parts).strip()
    if mode not in ("safe", "no-claude"):
        mode = "safe"
    if text and _REUSE_HINT.search(text):
        reuse_last = True
    return {
        "text": text,
        "project_override": project_override,
        "dry_run": dry_run,
        "mode": mode,
        "copy_flag": copy_flag,
        "reuse_last": reuse_last,
        "report_path": report_path,
        "auto_finish": auto_finish,
    }


# ── Reuse-last helpers ────────────────────────────────────────────────────────

def _latest_project_worker_run() -> dict | None:
    """Find the most recent worker run that targeted a project route."""
    if not WORKER_DIR.exists():
        return None
    runs = sorted(
        [p for p in WORKER_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")],
        reverse=True,
    )
    for run in runs:
        plan = run / "02_PLAN.md"
        if not plan.exists():
            continue
        try:
            t = plan.read_text(encoding="utf-8")
        except Exception:
            continue
        if "route: `project_fix_or_inspect`" in t or "route: `self_evolve`" in t:
            req_file = run / "01_REQUEST.md"
            request_text = ""
            if req_file.exists():
                try:
                    rt = req_file.read_text(encoding="utf-8")
                    inblock = False
                    for line in rt.splitlines():
                        if line.strip() == "## Texto original":
                            inblock = True
                            continue
                        if inblock:
                            if line.startswith("## "):
                                break
                            request_text += line + "\n"
                except Exception:
                    pass
            # extract project from plan
            proj = None
            for line in t.splitlines():
                if line.strip().startswith("- project:"):
                    proj = line.split(":", 1)[1].strip().strip("`")
                    if proj == "(nenhum)":
                        proj = None
                    break
            return {
                "run": run,
                "request": (request_text or "").strip(),
                "project": proj,
                "route": ("self_evolve"
                          if "route: `self_evolve`" in t
                          else "project_fix_or_inspect"),
            }
    return None


# ── Route names ───────────────────────────────────────────────────────────────

ROUTE_RESUME = "resume"
ROUTE_N8N = "n8n_blueprint"
ROUTE_RESEARCH = "research_plan"
ROUTE_PROJECT = "project_fix_or_inspect"
ROUTE_SELF_EVOLVE = "self_evolve"
ROUTE_NO_CLAUDE = "no_claude"
ROUTE_CAPABILITY = "capability_check"
ROUTE_HANDOFF = "handoff"
ROUTE_PERSONAL = "personal_tool"
ROUTE_UNCLEAR = "unclear"

RISK_READ_ONLY = "read_only"
RISK_JARVIS_WRITE = "jarvis_write"
RISK_RUNTIME_WRITE = "runtime_write"
RISK_NEEDS_CLAUDE = "needs_claude"
RISK_BLOCKED = "blocked"

_NO_CLAUDE_HINT = re.compile(
    r"(?i)\b(sem claude|acabou (?:o )?claude|claude (?:fora|indispon[íi]vel|caiu)|offline)\b"
)
_HANDOFF_HINT = re.compile(
    r"(?i)\b(handoff|hand[- ]off|passar (?:para|pra) chatgpt|cole no chatgpt)\b"
)


def choose_route(text, intent, project, capability_hint, mode, project_override=False):
    if not text.strip():
        return (ROUTE_RESUME, RISK_READ_ONLY)
    if mode == "no-claude":
        return (ROUTE_NO_CLAUDE, RISK_RUNTIME_WRITE)
    if _NO_CLAUDE_HINT.search(text):
        return (ROUTE_NO_CLAUDE, RISK_RUNTIME_WRITE)
    if _HANDOFF_HINT.search(text):
        return (ROUTE_HANDOFF, RISK_RUNTIME_WRITE)
    if capability_hint:
        return (ROUTE_CAPABILITY, RISK_READ_ONLY)
    if intent == INTENT_RESEARCH_PLAN:
        return (ROUTE_RESEARCH, RISK_RUNTIME_WRITE)
    if intent == INTENT_NEXT_ACTION:
        return (ROUTE_RESUME, RISK_READ_ONLY)
    if intent == INTENT_SELF_EVOLVE:
        return (ROUTE_SELF_EVOLVE, RISK_NEEDS_CLAUDE)
    if intent == INTENT_N8N_BLUEPRINT:
        return (ROUTE_N8N, RISK_RUNTIME_WRITE)
    if intent == INTENT_CAPABILITY_CHECK:
        return (ROUTE_CAPABILITY, RISK_READ_ONLY)
    if intent in (
        INTENT_SCREEN_CAPTURE,
        INTENT_IMAGE_TO_PDF,
        INTENT_IMAGE_CONVERT,
        INTENT_SPEAK,
        INTENT_MESSAGE_DRAFT,
        INTENT_MESSAGE_SEND,
        INTENT_MEMORY_SAVE,
        INTENT_STORAGE_SCAN,
        INTENT_FILES_TRIAGE,
    ):
        risk = RISK_READ_ONLY if intent in (INTENT_IMAGE_TO_PDF, INTENT_STORAGE_SCAN, INTENT_FILES_TRIAGE) else RISK_RUNTIME_WRITE
        return (ROUTE_PERSONAL, risk)
    if intent in (INTENT_PROJECT_FIX, INTENT_PROJECT_QA,
                  INTENT_BROWSER_QA, INTENT_FINAL_GATE, INTENT_OPEN_PROJECT):
        return (ROUTE_PROJECT, RISK_NEEDS_CLAUDE if project else RISK_READ_ONLY)
    # Strong bias: if user supplied --project ALIAS explicitly, treat as project route
    # even if the intent classifier was confused. This is the common "do something
    # in <project>" flow.
    if project_override and project:
        return (ROUTE_PROJECT, RISK_NEEDS_CLAUDE)
    # Weaker bias: project alias detected from text plus action-y verb → project route.
    if project and _ACTION_HINT.search(text):
        return (ROUTE_PROJECT, RISK_NEEDS_CLAUDE)
    return (ROUTE_UNCLEAR, RISK_READ_ONLY)


# Action-y verbs that, combined with a detected project alias, justify routing
# to project_fix_or_inspect even if the intent classifier returned something else.
_ACTION_HINT = re.compile(
    r"(?i)\b(bug|fix|consert|corrig|arrum|resolv|implement|"
    r"feature|funcionalidade|atualiz|update|melhor|tunin|"
    r"qa|test|valid|revisar|review|"
    r"refator|refact|limpar|cleanup|organiz|"
    r"docum|docs|readme)\b"
)


# ── Plan builders ─────────────────────────────────────────────────────────────
# Each plan returns (actions, next_cmd, error). Each action is
# (label, cmd_list, blocked_reason_or_None).

def plan_resume(text, project, dry_run):
    next_cmd, reason, dirty_files = _smart_resume_decision()
    extras = {"reason": reason}
    if dirty_files:
        # Dirty tree: skip running `daily` (it will report dirty anyway) and
        # surface the file list prominently. The user needs to see what's
        # dirty, not a 200-line dashboard.
        extras["dirty_files"] = dirty_files
        actions = []  # no auto-actions; Theo decides commit vs revert
    else:
        actions = [
            ("Dashboard (read-only)", ["./jarvis", "daily"], None),
        ]
    return actions, next_cmd, None, extras


def plan_research(text, project, dry_run):
    goal = text or "research plan"
    cmd = ["./jarvis", "blueprint", "--type", "research", "--goal", goal]
    if dry_run:
        cmd.append("--dry-run")
    actions = [
        ("Blueprint local (research)", cmd, None),
    ]
    next_cmd = f'./jarvis blueprint --type research --goal "{goal}"'
    extras = {"artifact_dir": BLUEPRINTS_DIR, "artifact_hint": "research"}
    return actions, next_cmd, None, extras


def plan_n8n(text, project, mode, dry_run):
    goal = text or "workflow n8n"
    actions = [
        ("Blueprint local (n8n)",
         ["./jarvis", "blueprint", "--type", "n8n", "--goal", goal] +
         (["--dry-run"] if dry_run else []),
         None),
    ]
    if mode == "no-claude":
        actions.append((
            "Pacote no-claude (n8n)",
            ["./jarvis", "no-claude", f"workflow n8n: {goal}"] +
            (["--dry-run"] if dry_run else []),
            None,
        ))
    next_cmd = f'./jarvis start "criar workflow n8n: {goal}"'
    extras = {"artifact_dir": BLUEPRINTS_DIR, "artifact_hint": "n8n"}
    return actions, next_cmd, None, extras


def plan_project(text, project, dry_run):
    if not project:
        return ([], None,
                "Sem project alias detectado — peça com --project ALIAS "
                "(ex.: oficina, jarvis-core, ls, gc).", {})
    actions = [
        ("Inspeção read-only do projeto",
         ["./jarvis", "project-intel", "--project", project], None),
        ("Mission pack Claude (goal-sprint)",
         ["./jarvis", "goal-sprint", "--project", project, "--goal", text] +
         (["--dry-run"] if dry_run else []),
         None),
        ("Bloco para abrir Claude (print-only)",
         ["./jarvis", "claude-launch", "--project", project, "--print-only"],
         None),
    ]
    next_cmd = (f'./jarvis start "{project}: {text}"  '
                "# ou cole o prompt da mission no Claude já aberto")
    extras = {"artifact_dir": MISSIONS_DIR, "artifact_hint": f"project-{project}_goal-sprint"}
    return actions, next_cmd, None, extras


def plan_self_evolve(text, project, dry_run):
    goal = text or "reduzir trabalho manual"
    actions = [
        ("Health quick", ["./jarvis", "health"], None),
        ("Mission pack self-evolve",
         ["./jarvis", "self-evolve", "--goal", goal] +
         (["--dry-run"] if dry_run else []),
         None),
        ("Bloco para abrir Claude (jarvis-core)",
         ["./jarvis", "claude-launch", "--project", "jarvis-core", "--print-only"],
         None),
    ]
    next_cmd = f'./jarvis start "evoluir o JARVIS: {goal}"'
    extras = {"artifact_dir": MISSIONS_DIR, "artifact_hint": "jarvis-core_self-evolve"}
    return actions, next_cmd, None, extras


def plan_no_claude(text, project, dry_run):
    base = text or "pedido sem texto"
    no_claude_cmd = ["./jarvis", "no-claude", base]
    task_cmd = ["./jarvis", "task-add", f"no-claude: {base}"]
    if dry_run:
        no_claude_cmd.append("--dry-run")
        task_cmd.append("--dry-run")
    actions = [
        ("Pacote no-claude completo", no_claude_cmd, None),
        ("Enfileirar task local", task_cmd, None),
    ]
    next_cmd = './jarvis state-status   # ver pacote + task gerados'
    extras = {"artifact_dir": ROOT / "05_EXECUCAO" / "38_NO_CLAUDE",
              "artifact_hint": _slugify(base)}
    return actions, next_cmd, None, extras


def plan_capability(text, project, capability_hint, dry_run):
    name = capability_hint or "google_calendar"
    actions = [
        ("Detalhe da capability", ["./jarvis", "capability-check", name], None),
        ("Plano local (future_adapter)", ["./jarvis", "capability-plan", name], None),
    ]
    next_cmd = './jarvis limits   # ver fronteira completa do robô'
    return actions, next_cmd, None, {}


def plan_handoff(text, project, dry_run):
    cmd = ["./jarvis", "handoff-self"]
    if not dry_run:
        cmd.append("--save")
    actions = [
        ("Snapshot do JARVIS (persistido em 39_HANDOFFS/)", cmd, None),
    ]
    next_cmd = 'open 05_EXECUCAO/39_HANDOFFS/   # último handoff'
    extras = {"artifact_dir": ROOT / "05_EXECUCAO" / "39_HANDOFFS",
              "artifact_hint": "jarvis_handoff"}
    return actions, next_cmd, None, extras


def plan_personal(text, intent, dry_run):
    if intent == INTENT_SCREEN_CAPTURE:
        cmd = ["./jarvis", "screen-capture", "--interactive"]
        if dry_run:
            cmd.append("--dry-run")
        return [("Captura interativa local", cmd, None)], "./jarvis screen-capture --interactive", None, {}

    if intent == INTENT_IMAGE_TO_PDF:
        match = re.search(r"(?i)([^\s\"']+\.(?:png|jpe?g|heic|tiff?|webp|svg))", text)
        if not match:
            return [], None, "Informe o caminho da imagem. PDF permanece bloqueado; só existe preview.", {}
        source = match.group(1)
        cmd = ["./jarvis", "image-to-pdf", source, "--dry-run"]
        return [("Planejar imagem para PDF (bloqueado)", cmd, None)], "PDF bloqueado pelo AGENTS.md", None, {}

    if intent == INTENT_IMAGE_CONVERT:
        image_match = re.search(r"(?i)([^\s\"']+\.(?:png|jpe?g|heic|tiff?|webp|svg))", text)
        format_match = re.search(r"(?i)\b(?:para|em)\s+(png|jpe?g|tiff?)\b", text)
        if not image_match or not format_match:
            return [], None, "Informe uma imagem e o formato png, jpg ou tiff.", {}
        source = image_match.group(1)
        output_format = format_match.group(1).lower()
        extension = "jpg" if output_format in ("jpg", "jpeg") else "tiff" if output_format in ("tif", "tiff") else "png"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = PERSONAL_DIR / "converted" / f"{_slugify(Path(source).stem, 36)}-{stamp}.{extension}"
        cmd = ["./jarvis", "image-convert", source, "--to", output_format, "--output", str(output)]
        if dry_run:
            cmd.append("--dry-run")
        return [("Converter imagem em runtime seguro", cmd, None)], f"open {output}", None, {}

    if intent == INTENT_SPEAK:
        quoted = re.search(r'["“](.+?)["”]', text)
        speech = quoted.group(1) if quoted else re.sub(
            r"(?i)^\s*(?:ler?|leia|diga|falar)\s+em\s+voz\s+alta\s*[:,-]?\s*", "", text
        ).strip()
        cmd = ["./jarvis", "speak", speech]
        if dry_run:
            cmd.append("--dry-run")
        return [("Fala local", cmd, None)], f'./jarvis speak "{speech}"', None, {}

    if intent == INTENT_MESSAGE_DRAFT:
        phone_match = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", text)
        if not phone_match:
            return [], None, "Informe DDI + DDD + número. JARVIS nunca envia automaticamente.", {}
        phone = "".join(char for char in phone_match.group(0) if char.isdigit())
        quoted = re.search(r'["“](.+?)["”]', text)
        body = quoted.group(1) if quoted else re.sub(re.escape(phone_match.group(0)), "", text).strip(" :-")
        if not quoted:
            body = re.sub(
                r"(?i)^\s*(?:mandar?|enviar?)\s+mensagem(?:\s+(?:no|pelo)\s+whatsapp)?\s*(?:para)?\s*",
                "",
                body,
            ).strip()
        if not body:
            return [], None, "Informe também o texto da mensagem. Nada foi enviado.", {}
        cmd = ["./jarvis", "message-draft", "--phone", phone, body]
        if dry_run:
            cmd.append("--dry-run")
        return [("Rascunho de WhatsApp (sem envio)", cmd, None)], "revise o link e envie manualmente", None, {}

    if intent == INTENT_MESSAGE_SEND:
        phone_match = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", text)
        if not phone_match:
            return [], None, "Informe DDI + DDD + número para enviar pelo app Mensagens.", {}
        phone = "".join(char for char in phone_match.group(0) if char.isdigit())
        quoted = re.search(r'["“](.+?)["”]', text)
        body = quoted.group(1) if quoted else re.sub(re.escape(phone_match.group(0)), "", text).strip(" :-")
        if not quoted:
            body = re.sub(
                r"(?i)^\s*(?:mandar?|enviar?|manda|envia)\s+(?:uma\s+)?(?:mensagem|msg)\s*(?:para)?\s*",
                "",
                body,
            ).strip()
        if not body:
            return [], None, "Informe também o texto exato da mensagem.", {}
        cmd = ["./jarvis", "message-send", "--phone", phone, body]
        if dry_run:
            cmd.append("--dry-run")
        return [("Enviar pelo app Mensagens", cmd, None)], "mensagem enviada pelo Mac", None, {}

    if intent == INTENT_MEMORY_SAVE:
        body = re.sub(
            r"(?i)^\s*(?:guard(?:a|e|ar)|salv(?:a|e|ar)|registr(?:a|e|ar)|grav(?:a|e|ar)|lembr(?:a|e|ar)(?:-se)?)\s*",
            "",
            text,
        ).strip(" :-")
        body = re.sub(
            r"(?i)^(?:isso\s+)?na\s+mem[oó]ria(?:\s+como\s+(?:prefer[eê]ncia|aprendizado|decis[aã]o))?\s*",
            "",
            body,
        ).strip(" :-")
        body = re.sub(r"(?i)^que\s+", "", body).strip()
        body = re.sub(r"(?i)\s+(?:na|como)\s+(?:mem[oó]ria|aprendizado|decis[aã]o|prefer[eê]ncia)\s*$", "", body).strip()
        if not body:
            return [], None, "Diga o conteúdo que deve entrar na memória.", {}
        kind = "preference" if re.search(r"(?i)prefer[eê]ncia", text) else "decision" if re.search(r"(?i)decis[aã]o", text) else "learning"
        cmd = ["./jarvis", "memory-save", body, "--kind", kind]
        if dry_run:
            cmd.append("--dry-run")
        return [("Gravar memória operacional", cmd, None)], "memória disponível na constelação local", None, {"memory_kind": kind}

    scan_path = str(Path.home() / "Downloads") if "download" in text.lower() else "."
    if intent == INTENT_STORAGE_SCAN:
        cmd = ["./jarvis", "storage-scan", scan_path, "--top", "20"]
        return [("Análise read-only de armazenamento", cmd, None)], f"./jarvis files-triage {scan_path}", None, {}
    if intent == INTENT_FILES_TRIAGE:
        cmd = ["./jarvis", "files-triage", scan_path, "--limit", "100"]
        return [("Plano read-only de organização", cmd, None)], "revise o plano; nenhum arquivo foi movido", None, {}
    return [], None, "Ferramenta pessoal não reconhecida.", {}


_UNCLEAR_PATTERN_HINTS = [
    (re.compile(r"(?i)\b(deploy|push|merge|tag|prod(?:u(?:ção|cao))?)\b"),
     "parece pedido de ação restrita — JARVIS bloqueia. Veja ./jarvis limits."),
    (re.compile(r"(?i)\b(test|teste|qa|quality)\b"),
     'soa como QA — tente: ./jarvis do "qa sprint no projeto <alias>"'),
    (re.compile(r"(?i)\b(refator|refact|limpar|cleanup|organizar)\b"),
     'soa como refator — tente: ./jarvis do "refator no projeto <alias>: <objetivo>"'),
    (re.compile(r"(?i)\b(criar|montar|build|scaffold|novo)\b"),
     'parece scaffold — tente: ./jarvis blueprint --type app --goal "..."'),
    (re.compile(r"(?i)\b(documenta(?:r|ção|cao)|docs|readme)\b"),
     'parece docs — tente: ./jarvis do "docs do projeto <alias>: <o que documentar>"'),
]


def plan_unclear(text, project, dry_run):
    actions = [
        ("Router local em modo explicação",
         ["./jarvis", "ask", text, "--dry-run"], None),
        ("Marcar revisão (dry-run)",
         ["./jarvis", "task-add", f"revisar request unclear: {text}", "--dry-run"], None),
    ]
    hints = []
    for pat, msg in _UNCLEAR_PATTERN_HINTS:
        if pat.search(text or ""):
            hints.append(msg)
    next_cmd = f'./jarvis no-claude "{text}" --dry-run   # ver plano manual + comandos seguros'
    extras = {"hints": hints}
    return actions, next_cmd, None, extras


def build_plan(route, text, project, mode, dry_run, capability_hint, intent):
    if route == ROUTE_RESUME:
        return plan_resume(text, project, dry_run)
    if route == ROUTE_RESEARCH:
        return plan_research(text, project, dry_run)
    if route == ROUTE_N8N:
        return plan_n8n(text, project, mode, dry_run)
    if route == ROUTE_PROJECT:
        return plan_project(text, project, dry_run)
    if route == ROUTE_SELF_EVOLVE:
        return plan_self_evolve(text, project, dry_run)
    if route == ROUTE_NO_CLAUDE:
        return plan_no_claude(text, project, dry_run)
    if route == ROUTE_CAPABILITY:
        return plan_capability(text, project, capability_hint, dry_run)
    if route == ROUTE_HANDOFF:
        return plan_handoff(text, project, dry_run)
    if route == ROUTE_PERSONAL:
        return plan_personal(text, intent, dry_run)
    return plan_unclear(text, project, dry_run)


# ── Artifact detection (after live execution) ────────────────────────────────

def _find_recent_artifact(extras, started_at) -> Path | None:
    """If the route produced a real artifact (mission pack, blueprint, etc.),
    return its directory path. Looks under extras['artifact_dir'] for the most
    recent subdir created after started_at, optionally matching artifact_hint."""
    art_dir = extras.get("artifact_dir") if extras else None
    if not art_dir:
        return None
    candidate = _latest_subtree_after(art_dir, started_at - 1)
    if not candidate:
        return None
    hint = (extras or {}).get("artifact_hint")
    if hint and hint not in candidate.name:
        # take it anyway — most recent matters
        pass
    return candidate


def _prompt_file_in(artifact: Path) -> Path | None:
    """Return the most likely prompt file inside an artifact dir."""
    if not artifact or not artifact.exists():
        return None
    # mission pack format
    candidates = [
        "01_CLAUDE_PROMPT.md",
        "01_REQUEST.md",
        "PROMPT.md",
        "01_SPEC.md",
    ]
    for name in candidates:
        p = artifact / name
        if p.exists():
            return p
    mds = sorted(artifact.glob("*.md"))
    return mds[0] if mds else None


# ── FULL_MISSION assembler ────────────────────────────────────────────────────

_FULL_MISSION_HEADER = """\
# JARVIS — Mission para Claude Code (assembled by ./jarvis do)

**Status real**: Esta missão foi montada por JARVIS local. JARVIS NÃO executou
Claude. Você (Claude) deve executar as ações dentro do projeto-alvo, mas
respeitando todas as regras abaixo.

## Regras invariáveis (não negociar)
- NUNCA faça push, PR, merge, deploy, tag, migrações ou tocar produção.
- NUNCA leia conteúdo de `.env`, NUNCA imprima tokens / cookies / API keys
  / QR codes / segredos / senhas.
- NUNCA chame API paga (Anthropic, OpenAI, etc.) — você é o LLM, não chame
  outro LLM.
- NUNCA execute Claude em background.
- Se o projeto-alvo estiver em main/master, PARE e reporte.
- Edite só o necessário para cumprir o objetivo. Sem refactor agressivo.

## Comportamento esperado
- NÃO pergunte ao Theo. Faça best-effort dentro das regras e reporte.
- Se faltar info, marque RISCO em STATUS REAL e siga com a melhor hipótese.
- Prefira mudanças pequenas, testáveis, reversíveis.
- Sempre rode os checks locais (typecheck/tests/lint) que o projeto já tem.
- Termine com o bloco STATUS REAL completo no final do output.

"""

_FULL_MISSION_RETURN_FORMAT = """

## Formato de retorno obrigatório (no fim do output)

```
## STATUS REAL
- branch: <nome>
- arquivos tocados: <lista>
- typecheck: <PASS/FAIL/NOT_RUN>
- tests:     <PASS/FAIL/NOT_RUN>
- lint:      <PASS/FAIL/NOT_RUN>

## WHAT CHANGED
<bullets curtos>

## WHAT IMPROVED
<bullets curtos>

## RISKS
<bullets — ou "nenhum identificado">

## SAFE TO COMMIT
<yes/no + motivo curto>
```

Status real: este pacote foi montado por JARVIS local sem chamar API paga
e sem executar Claude. Produção: nada alterado por JARVIS.
"""


def _assemble_full_mission(worker_pkg: Path, intel_summary: str,
                           goal_sprint_prompt: str, project: str, goal: str,
                           reused_from_dir: Path | None = None,
                           deep_intel_md: str = "") -> Path:
    """Write FULL_MISSION.md inside the worker run package and return path."""
    lines = [_FULL_MISSION_HEADER]
    lines.append(f"## Projeto\n- alias: `{project}`\n- objetivo: {goal}\n\n")
    if reused_from_dir:
        rel = reused_from_dir.relative_to(ROOT) if reused_from_dir.is_absolute() else reused_from_dir
        lines.append(f"## Reuso\n- base anterior: `{rel}`\n\n")
    if deep_intel_md:
        lines.append("## Project deep context (read-only — git + grep + ls-files)\n\n")
        lines.append(deep_intel_md.rstrip())
        lines.append("\n\n")
    if intel_summary:
        lines.append("## Contexto do projeto (project-intel, read-only)\n")
        lines.append("```\n")
        lines.append(intel_summary.rstrip())
        lines.append("\n```\n\n")
    if goal_sprint_prompt:
        lines.append("## Missão detalhada (goal-sprint)\n")
        lines.append(goal_sprint_prompt.rstrip())
        lines.append("\n\n")
    lines.append(_FULL_MISSION_RETURN_FORMAT)
    target = worker_pkg / "07_FULL_MISSION.md"
    try:
        target.write_text("".join(lines), encoding="utf-8")
    except Exception:
        return None
    return target


# ── Worker log ────────────────────────────────────────────────────────────────

def _write_worker_log(text, route, risk, mode, project, intent, actions_recorded,
                      next_cmd, capability_hint, extras, artifact_dir, prompt_file,
                      reason):
    ts_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    slug = _slugify(text or route)
    pkg = WORKER_DIR / f"{ts_dir}_{slug}"
    try:
        pkg.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return None, f"FALHA criando pacote: {e}"

    ts = datetime.now().isoformat(timespec="seconds")

    (pkg / "01_REQUEST.md").write_text(
        f"# Worker Request\n\n## Timestamp\n{ts}\n\n## Texto original\n{text or '(vazio — smart resume)'}\n",
        encoding="utf-8",
    )

    plan_md = [
        "# Worker Plan\n\n",
        f"- route: `{route}`\n",
        f"- risk: `{risk}`\n",
        f"- mode: `{mode}`\n",
        f"- intent: `{intent}`\n",
        f"- project: `{project or '(nenhum)'}`\n",
        f"- capability: `{capability_hint or '(n/a)'}`\n",
    ]
    if reason:
        plan_md.append(f"\n## Reasoning\n{reason}\n")
    if extras and extras.get("hints"):
        plan_md.append("\n## Heurísticas para pedido unclear\n")
        for h in extras["hints"]:
            plan_md.append(f"- {h}\n")
    (pkg / "02_PLAN.md").write_text("".join(plan_md), encoding="utf-8")

    actions_md = ["# Actions\n"]
    for i, (label, cmd, status, summary) in enumerate(actions_recorded, 1):
        actions_md.append(f"\n## {i}. {label}\n")
        actions_md.append(f"- command: `{' '.join(cmd)}`\n")
        actions_md.append(f"- status: {status}\n")
        actions_md.append(f"- summary: {summary}\n")
    (pkg / "03_ACTIONS.md").write_text("".join(actions_md), encoding="utf-8")

    next_md = [
        "# Próximo comando\n\n",
        "```\n",
        f"{next_cmd or '(nenhum)'}\n",
        "```\n",
    ]
    if artifact_dir:
        next_md.append(f"\n## Artefato gerado\n- pasta: `{artifact_dir.relative_to(ROOT)}`\n")
        if prompt_file:
            rel = prompt_file.relative_to(ROOT)
            next_md.append(f"- prompt: `{rel}`\n")
            next_md.append("\n## Copiar para o clipboard\n")
            next_md.append("```\n")
            next_md.append(f"cat {rel} | pbcopy\n")
            next_md.append("```\n")
    (pkg / "04_NEXT.md").write_text("".join(next_md), encoding="utf-8")

    mission_md = ["# Mission excerpt\n\n"]
    if prompt_file and prompt_file.exists():
        excerpt = _read_text_capped(prompt_file, max_chars=3500)
        mission_md.append(f"_File: `{prompt_file.relative_to(ROOT)}`_\n\n")
        mission_md.append("```\n")
        mission_md.append(excerpt)
        if not excerpt.endswith("\n"):
            mission_md.append("\n")
        mission_md.append("```\n")
    else:
        mission_md.append("(sem mission pack para esta rota)\n")
    (pkg / "05_MISSION.md").write_text("".join(mission_md), encoding="utf-8")

    n_exec = len([a for a in actions_recorded if a[2] == "EXECUTADO"])
    (pkg / "06_STATUS_REAL.md").write_text(
        "# Status real\n\n"
        "## O que JARVIS fez (loop observe-act)\n"
        f"- {n_exec} comando(s) seguros do allowlist executados\n"
        f"- worker run gravado em `{pkg.relative_to(ROOT)}/`\n\n"
        "## O que JARVIS NÃO fez\n"
        "- não executou Claude\n"
        "- não chamou API paga (Anthropic/OpenAI)\n"
        "- não tocou produção / VPS / n8n real / Supabase prod\n"
        "- não editou projetos-alvo\n"
        "- não leu .env nem imprimiu segredos\n"
        "- não fez push / PR / merge / deploy / migrations / tag\n",
        encoding="utf-8",
    )
    return pkg, None


# ── Main ──────────────────────────────────────────────────────────────────────

def _session_project() -> str | None:
    """Get project alias from active work session, if any."""
    s = _safe_load_json(CURRENT_SESSION)
    if not s:
        return None
    p = s.get("project")
    if p and p not in ("(nenhum)", "null", "None"):
        return p
    return None


def _run_report_close(report_path: str, project_override: str | None,
                      dry_run: bool, auto_finish: bool) -> int:
    """The "close the Claude loop" flow: report-check + report-apply + gate-run
    [+ work-close]. Bypasses the worker's allowlist because the user explicitly
    asked for this via --report PATH. Each sub-command is invoked via the same
    ./jarvis dispatcher Theo would otherwise run by hand."""
    print("JARVIS — Worker Engine: Close the Loop (--report)")
    print("Status real: roda report-check + report-apply + gate-run em sequência.")
    print("")

    path = Path(report_path).expanduser()
    print("## Pedido")
    print(f"  --report {report_path}")
    print(f"  --auto-finish: {'sim' if auto_finish else 'não'}")
    print(f"  --dry-run:     {'sim' if dry_run else 'não'}")
    print("")

    if not path.exists():
        if dry_run:
            print(f"AVISO (--dry-run): arquivo não existe: {path}")
            print("  Live: report-template gera o `cat > PATH` antes desta etapa.")
            print("  Próximo: ./jarvis report-template   # gerar `cat > /tmp/...`")
            return 0
        print(f"FALHA: arquivo não existe: {path}")
        print("Próximo: ./jarvis report-template   # gerar `cat > /tmp/...`")
        return 2

    project = project_override or _session_project()
    print("## Projeto")
    if project:
        print(f"  {project}")
    else:
        print("  (não detectado — vai usar fallback do report_intake)")
    print("")

    steps = [
        ("Validar (report-check)",
         ["./jarvis", "report-check", "--file", str(path)]
         + (["--project", project] if project else [])),
        ("Aplicar (report-apply)",
         ["./jarvis", "report-apply", "--file", str(path)]
         + (["--project", project] if project else [])),
        ("Rodar gates (safety+smoke+doctrine)",
         ["./jarvis", "gate-run"]),
    ]
    if auto_finish:
        steps.append(("Fechar sessão (work-close)",
                      ["./jarvis", "work-close"]))

    print("## Sequência")
    for i, (label, cmd) in enumerate(steps, 1):
        print(f"  {i}. {label}")
        print(f"     $ {' '.join(cmd)}")
    print("")

    if dry_run:
        print("--dry-run: nenhuma das ações foi executada.")
        print("## Garantias")
        print("  Claude não executado · sem push/PR/merge/deploy/migrations/tag")
        return 0

    print("## Execução")
    summaries = []
    failed_at = None
    for i, (label, cmd) in enumerate(steps, 1):
        print(f"\n  → Step {i}/{len(steps)}: {label}")
        print(f"     $ {' '.join(cmd)}")
        rc, out, summary = _run(cmd, timeout=600)
        tag = "PASS" if rc == 0 else f"FAIL(rc={rc})"
        print(f"     {tag}  {summary}")
        summaries.append((label, rc, summary, out))
        if rc != 0:
            failed_at = (i, label, summary, out)
            break

    print("")
    print("## Garantias")
    print("  Claude não executado · projeto-alvo intacto · sem push/PR/merge/deploy/migrations/tag")
    print("")

    if failed_at:
        i, label, summary, out = failed_at
        print(f"## Resultado")
        print(f"  PARADO no step {i}: {label}")
        print(f"  motivo: {summary}")
        # Tail of failing command's output for context.
        tail = (out or "").strip().splitlines()[-15:]
        if tail:
            print("  últimas linhas:")
            for line in tail:
                print(f"    {line}")
        print("")
        print("## Próximo")
        if "report-check" in label.lower():
            print(f"  ./jarvis report-template   # revisar o template e re-colar")
        elif "report-apply" in label.lower():
            print(f"  ./jarvis report-status     # ver porque apply falhou")
        elif "gate" in label.lower():
            print(f"  ./jarvis gate-status       # detalhar gates que falharam")
        else:
            print(f"  ./jarvis state-status")
        return 1

    print("## Resultado")
    print(f"  LOOP FECHADO: {len(steps)} step(s) PASS")
    print("")
    print("## Próximo")
    if auto_finish:
        print("  ./jarvis daily       # sessão fechada — começar nova")
    else:
        print("  ./jarvis finish      # fecha a sessão (gates já passaram)")
    return 0


def main():
    opts = parse_args(sys.argv[1:])
    text = opts["text"]
    project_override = opts["project_override"]
    dry_run = opts["dry_run"]
    mode = opts["mode"]
    copy_flag = opts["copy_flag"]
    reuse_last = opts["reuse_last"]
    report_path = opts["report_path"]
    auto_finish = opts["auto_finish"]

    if report_path:
        # Special path: close the Claude loop. Doesn't go through worker routing.
        sys.exit(_run_report_close(report_path, project_override, dry_run, auto_finish))

    if text and _looks_secret_like(text):
        print("FALHA: pedido parece conter segredo. JARVIS recusa registrar.")
        sys.exit(1)

    reused_from = None
    if reuse_last:
        last = _latest_project_worker_run()
        if not last:
            print("AVISO: --reuse-last sem worker run de projeto/self-evolve encontrado.")
            print("       Continuando com o pedido cru.")
        else:
            reused_from = last
            extra_instruction = text.strip()
            base_request = last["request"].strip()
            # Build a combined request that keeps the original objective and
            # appends the new tweak/improvement.
            if extra_instruction:
                combined = (
                    f"{base_request}\n\n"
                    f"## Ajuste para esta tentativa\n{extra_instruction}"
                )
            else:
                combined = f"{base_request}\n\n## Ajuste para esta tentativa\nregenerar com mesmas regras"
            text = combined
            if not project_override and last.get("project"):
                project_override = last["project"]

    intent = _di(text) if text else INTENT_NEXT_ACTION
    project = _dp(text, project_override) if text else (project_override or None)
    capability_hint = _dc(text) if text else None
    route, risk = choose_route(
        text, intent, project, capability_hint, mode,
        project_override=bool(project_override),
    )

    print("JARVIS — Worker Engine")
    print("Status real: loop observe-act local. Sem Claude. Sem API. Sem produção.")
    print("")

    if reused_from:
        print("## Reuso")
        prev = reused_from["run"].relative_to(ROOT)
        print(f"  base:  {prev}/")
        print(f"  rota:  {reused_from['route']}  project: {reused_from.get('project') or '(nenhum)'}")
        print("")

    print("## Pedido")
    if text:
        first_line = text.splitlines()[0]
        if len(text.splitlines()) == 1:
            print(f'  "{first_line}"')
        else:
            print(f'  "{first_line}" (+ ajuste)')
    else:
        print("  (vazio — smart resume)")
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

    actions, next_cmd, error, extras = build_plan(
        route, text, project, mode, dry_run, capability_hint, intent
    )
    extras = extras or {}

    if error:
        print("## Erro de plano")
        print(f"  {error}")
        print("")
        print("## Próximo comando sugerido")
        print(f'  ./jarvis ask "{text or "?"}" --dry-run')
        print("Produção: nada alterado.")
        sys.exit(1)

    if extras.get("reason"):
        print("## Smart resume reasoning")
        print(f"  {extras['reason']}")
        if extras.get("dirty_files"):
            print("")
            print("## ⚠ Árvore suja — STOP")
            for line in extras["dirty_files"][:20]:
                print(f"    {line}")
            if len(extras["dirty_files"]) > 20:
                print(f"    …(+{len(extras['dirty_files']) - 20} mais)")
            print("")
            print("  Sugestões seguras (escolha uma):")
            print("    git status --short            # ver detalhe")
            print("    git diff                      # ver mudanças")
            print("    git add -p && git commit      # commitar parcial")
            print("    git restore .                 # descartar mudanças (CUIDADO)")
            print("    ./jarvis state-status         # ver runtime travado")
        print("")

    if extras.get("hints"):
        print("## Heurísticas — talvez você quis dizer")
        for h in extras["hints"]:
            print(f"  - {h}")
        print("")

    def _display_cmd(cmd):
        # Collapse newlines and excess whitespace to keep planning view tidy.
        return " ".join((c.replace("\n", " ⏎ ")) for c in cmd) if cmd else ""

    print("## Ações planejadas")
    if not actions:
        print("  (nenhuma — fluxo apenas informativo)")
    for i, (label, cmd, blocked_reason) in enumerate(actions, 1):
        cmd_str = _display_cmd(cmd)
        if len(cmd_str) > 160:
            cmd_str = cmd_str[:157] + "..."
        if blocked_reason:
            print(f"  {i}. [BLOQUEADO] {label}")
            print(f"     $ {cmd_str}")
            print(f"     motivo: {blocked_reason}")
        else:
            print(f"  {i}. {label}")
            print(f"     $ {cmd_str}")
    print("")

    actions_recorded = []
    captured_outputs = {}  # label → full stdout, kept in memory for FULL_MISSION
    started_at = datetime.now().timestamp()
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
                cmd_disp = _display_cmd(cmd)
                if len(cmd_disp) > 160:
                    cmd_disp = cmd_disp[:157] + "..."
                print(f"  {i}. [BLOQUEADO] {label} — {msg}")
                print(f"     $ {cmd_disp}")
                actions_recorded.append((label, cmd, "BLOQUEADO", msg))
                continue
            cmd_disp = _display_cmd(cmd)
            if len(cmd_disp) > 160:
                cmd_disp = cmd_disp[:157] + "..."
            print(f"  {i}. {label}")
            print(f"     $ {cmd_disp}")
            rc, out, summary = _run(cmd, timeout=120)
            tag = "PASS" if rc == 0 else f"FAIL(rc={rc})"
            print(f"     → {tag}  {summary}")
            actions_recorded.append((label, cmd, "EXECUTADO", f"{tag}: {summary}"))
            captured_outputs[label] = out
    print("")

    # Artifact detection (post-execution).
    artifact_dir = None
    prompt_file = None
    if not dry_run and extras.get("artifact_dir"):
        artifact_dir = _find_recent_artifact(extras, started_at)
        if artifact_dir:
            prompt_file = _prompt_file_in(artifact_dir)

    if artifact_dir:
        print("## Artefato gerado")
        print(f"  pasta:  {artifact_dir.relative_to(ROOT)}/")
        if prompt_file:
            rel = prompt_file.relative_to(ROOT)
            print(f"  prompt: {rel}")
            print(f"  copiar: cat {rel} | pbcopy")
            if copy_flag and prompt_file.exists():
                ok = _pbcopy(prompt_file.read_text(encoding="utf-8", errors="ignore"))
                print(f"  --copy: {'clipboard OK' if ok else 'pbcopy indisponível'}")
        print("")

    print("## Garantias")
    print("  Claude não executado · projeto-alvo intacto · sem push/PR/merge/deploy/migrations/tag · sem APIs pagas · .env não lido")
    print("")

    pkg_rel = None
    log_skipped_reason = None
    full_mission_path = None
    worker_pkg = None
    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"
    if dry_run:
        log_skipped_reason = "--dry-run"
    elif no_report:
        log_skipped_reason = "JARVIS_NO_REPORT=1"
    else:
        worker_pkg, err = _write_worker_log(
            text, route, risk, mode, project, intent,
            actions_recorded, next_cmd, capability_hint,
            extras, artifact_dir, prompt_file,
            extras.get("reason"),
        )
        if err:
            log_skipped_reason = err
        elif worker_pkg:
            pkg_rel = worker_pkg.relative_to(ROOT)
            # For project routes, assemble a FULL_MISSION combining project-intel
            # output, the goal-sprint prompt, and a return-format footer. This
            # is what Theo actually pastes into Claude — strictly stronger than
            # raw goal-sprint output.
            if route == ROUTE_PROJECT and prompt_file and project:
                intel_summary = captured_outputs.get("Inspeção read-only do projeto", "")
                goal_sprint_prompt = ""
                try:
                    goal_sprint_prompt = prompt_file.read_text(encoding="utf-8")
                except Exception:
                    pass
                # Sprint 8.3: deep project intel — git history, candidate files,
                # hot files, likely tests. Injected into FULL_MISSION so Claude
                # gets concrete file pointers without Theo typing them.
                deep_md = ""
                if _pdi is not None:
                    try:
                        deep_data = _pdi.gather(project, text)
                        deep_md = _pdi.render_markdown(deep_data)
                    except Exception as e:
                        deep_md = f"_(deep intel falhou: {e})_\n"
                full_mission_path = _assemble_full_mission(
                    worker_pkg, intel_summary, goal_sprint_prompt,
                    project, text,
                    reused_from.get("run") if reused_from else None,
                    deep_intel_md=deep_md,
                )

    if full_mission_path:
        rel = full_mission_path.relative_to(ROOT)
        print("## Full mission (assembled by do)")
        print(f"  arquivo: {rel}")
        print(f"  copiar:  cat {rel} | pbcopy")
        if copy_flag:
            try:
                ok = _pbcopy(full_mission_path.read_text(encoding="utf-8", errors="ignore"))
                print(f"  --copy:  {'clipboard OK (full mission)' if ok else 'pbcopy indisponível'}")
            except Exception:
                pass
        print("")

    print("## Resultado")
    if pkg_rel:
        print(f"  worker run: {pkg_rel}/")
    elif log_skipped_reason:
        print(f"  worker run: pulado ({log_skipped_reason})")
    print("")

    print("## Próximo")
    print(f"  {next_cmd or '(nenhum)'}")
    print("")
    print("Produção: nada alterado. Claude não executado.")


if __name__ == "__main__":
    main()
