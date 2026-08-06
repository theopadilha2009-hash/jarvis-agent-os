"""
ask_router.py — natural-language router for JARVIS.

Theo types something like:
  ./jarvis ask "abre oficina e corrige bug da agenda"
  ./jarvis ask "evolui o jarvis para reduzir trabalho manual"
  ./jarvis ask "coloca amanhã revisar LS na agenda"

This script classifies the request **locally** (no LLM, no paid API,
stdlib only) and prints the next safe command Theo should run. It can
also delegate to JARVIS sub-commands (self-evolve, goal-sprint,
blueprint, agenda-add, ...) when --copy or non-dry-run is requested.

Output format follows the JARVIS doctrine:
  Status real: ...
  ... interpretation ...
  Próximo comando: ...
  Produção: nada alterado.

Hard rules:
  - never calls Anthropic / OpenAI / paid APIs
  - never executes Claude
  - never touches production
  - never edits the target project
  - never reads .env
"""
from pathlib import Path
from datetime import datetime, timedelta
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "05_PROJECT_REGISTRY" / "PROJECT_REGISTRY.json"
ASK_LEARNING_DIR = ROOT / "05_EXECUCAO" / "32_ASK_LEARNING"
UNCLEAR_FILE = ASK_LEARNING_DIR / "UNCLEAR_REQUESTS.md"

# Reuse SECRET_PATTERNS so we never log a secret-shaped request.
try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []


def _looks_secret_like(text: str) -> bool:
    for _name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False

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

SAFETY_READONLY = "readonly"
SAFETY_LOCAL_PREP = "local-prep"
SAFETY_LOCAL_WRITE = "local-write"


def _load_registry():
    if not REGISTRY.exists():
        return {"projects": []}
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {"projects": []}


def _project_aliases():
    return [p["alias"].lower() for p in _load_registry().get("projects", [])]


def parse_args(argv):
    text_parts = []
    alias = None
    dry_run = False
    copy_flag = None  # tri-state: None=default, True=force, False=skip
    explain = False
    force = False
    log_mode = False
    no_log = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            if i + 1 < len(argv):
                alias = argv[i + 1].strip().lower()
                i += 2
                continue
        if a.startswith("--project="):
            alias = a.split("=", 1)[1].strip().lower()
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
        if a == "--explain":
            explain = True
            i += 1
            continue
        if a == "--force":
            force = True
            i += 1
            continue
        if a == "--log":
            log_mode = True
            i += 1
            continue
        if a == "--no-log":
            no_log = True
            i += 1
            continue
        text_parts.append(a)
        i += 1
    text = " ".join(text_parts).strip()
    return text, alias, dry_run, copy_flag, explain, force, log_mode, no_log


def _log_unclear(text: str, project: str):
    """Append an unclear request to UNCLEAR_REQUESTS.md (secret-safe).

    No-op if the request looks secret-like (token/api_key/etc). Append-only;
    never edits past entries. This is JARVIS's way of building a pattern-tuning
    backlog without calling an LLM."""
    if not text.strip():
        return
    if _looks_secret_like(text):
        return
    ASK_LEARNING_DIR.mkdir(parents=True, exist_ok=True)
    if not UNCLEAR_FILE.exists():
        UNCLEAR_FILE.write_text(
            "# JARVIS — unclear ask requests (append-only)\n"
            "\n"
            "Cada linha = request que `ask_router.detect_intent` não classificou.\n"
            "Use para tunar os patterns em `INTENT_PATTERNS` (ask_router.py).\n"
            "Sem segredos: requests secret-shaped são recusados antes de gravar.\n"
            "\n",
            encoding="utf-8",
        )
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"- [{ts}] project={project or '(?)'} request={text!r}  # needs pattern tuning"
    with UNCLEAR_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _show_unclear_log():
    """Read UNCLEAR_REQUESTS.md and print the last entries."""
    print("JARVIS — Ask Log (unclear requests)")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    if not UNCLEAR_FILE.exists():
        print(f"(arquivo ausente — nada ainda classificado como unclear)")
        print(f"alvo: {UNCLEAR_FILE.relative_to(ROOT)}")
        print("Produção: nada alterado.")
        return
    body = UNCLEAR_FILE.read_text(encoding="utf-8", errors="ignore")
    items = [l for l in body.splitlines() if l.startswith("- [")]
    print(f"arquivo: {UNCLEAR_FILE.relative_to(ROOT)} ({len(body)} bytes)")
    print(f"unclear acumulados: {len(items)}")
    print("")
    for line in items[-30:]:
        print(line)
    if len(items) > 30:
        print(f"... (+{len(items) - 30} entradas anteriores)")
    print("")
    print("Próximo passo de manutenção:")
    print("  - leia as entradas e ajuste INTENT_PATTERNS em 11_SCRIPTS/ask_router.py")
    print("Produção: nada alterado.")


# ── intent detection ──────────────────────────────────────────────────────────

# Order matters: earlier patterns win when ambiguous.
# Strategy: very-specific intents first (next_action, self_evolve, project_fix
# with explicit action verbs), then blueprints (which have distinctive nouns
# like n8n / workflow), then agenda (which is tightened so the bare word
# "agenda" inside "bug da agenda" does NOT trigger calendar intent), then
# generic fallbacks (open_project, unclear).
INTENT_PATTERNS = [
    # Personal tools are deterministic and more specific than project work.
    (INTENT_IMAGE_TO_PDF, re.compile(
        r"(?i)\b(imagem|foto|png|jpe?g|heic|tiff?|webp|svg)\b.*\b(para|em|virar|converter|transformar)\b.*\bpdf\b|"
        r"\b(converter|transformar)\b.*\b(imagem|foto|[^\s]+\.(?:png|jpe?g|heic|tiff?|webp|svg))\b.*\bpdf\b"
    )),
    (INTENT_IMAGE_CONVERT, re.compile(
        r"(?i)\b(converter|transformar)\b.*\b(?:imagem|foto|[^\s]+\.(?:png|jpe?g|heic|tiff?|webp|svg))\b"
        r".*\b(?:para|em)\b.*\b(png|jpe?g|tiff?)\b"
    )),
    (INTENT_SCREEN_CAPTURE, re.compile(
        r"(?i)\b(screenshot|captura de tela|tirar? (?:um )?print|print da tela)\b"
    )),
    (INTENT_SPEAK, re.compile(
        r"(?i)\b(ler? em voz alta|leia em voz alta|diga em voz alta|falar em voz alta|"
        r"sintetizar voz|text[-\s]?to[-\s]?speech|tts)\b"
    )),
    (INTENT_MESSAGE_DRAFT, re.compile(
        r"(?i)\b(mensagem (?:no|pelo) whatsapp|whatsapp para|rascunho de mensagem)\b"
    )),
    (INTENT_MESSAGE_SEND, re.compile(
        r"(?i)\b(mandar? mensagem|enviar? mensagem|manda(?:r)? (?:uma )?msg|envia(?:r)? (?:uma )?msg)\b"
    )),
    (INTENT_MEMORY_SAVE, re.compile(
        r"(?i)\b(?:guarda(?:r)?|salva(?:r)?|registre?|grava(?:r)?|lembre(?:-se)?)\b.{0,90}\b(?:mem[oó]ria|prefer[eê]ncia|aprendizado|decis[aã]o)\b|"
        r"\b(?:mem[oó]ria|prefer[eê]ncia|aprendizado|decis[aã]o)\b.{0,40}\b(?:guarda(?:r)?|salva(?:r)?|registre?|grava(?:r)?)\b"
    )),
    (INTENT_STORAGE_SCAN, re.compile(
        r"(?i)\b(limpar? armazenamento|analisar? armazenamento|arquivos? grandes?|"
        r"espaço em disco|espaco em disco|o que est[aá] ocupando)\b"
    )),
    (INTENT_FILES_TRIAGE, re.compile(
        r"(?i)\b(organizar? arquivos?|arrumar? (?:a pasta|os arquivos|downloads)|"
        r"organizar? downloads|triagem de arquivos|separar? arquivos? por tipo)\b"
    )),
    # JARVIS foundation/docs/research routing.
    # Keeps requests about identity, modes, sources and architecture out of unclear.
    (INTENT_RESEARCH_PLAN, re.compile(
        r"(?i)\b("
        r"identidade(?: pessoal)? do jarvis|"
        r"modos? (?:personal|work assist|future company)|"
        r"personal[_\s-]?mode|work[_\s-]?assist[_\s-]?mode|future[_\s-]?company[_\s-]?mode|"
        r"jarvis foundation|foundation docs?|"
        r"research lessons?|deep research|sources?|fontes?|"
        r"documenta(?:r|ção)|docs?|readme|"
        r"arquitetura do jarvis|base do jarvis"
        r")\b"
    )),
    # limits / what JARVIS can do — checked very early so phrases like
    # "quais limites" / "o que pode fazer" don't get mis-routed.
    (INTENT_LIMITS, re.compile(
        r"(?i)\b(limit(?:e|es)|o que (?:você|voce|jarvis|pode|consegue) faz(?:er)?|"
        r"quais limites|fronteira do robô|fronteira do robo)\b"
    )),
    # capability check — "capacidade X" / "consigo usar X" / "agenda real" /
    # "pesquisa web" / etc. We route to capability-check with a name hint
    # detected later in _next_command_for.
    (INTENT_CAPABILITY_CHECK, re.compile(
        r"(?i)\b(capacidade|capability|consigo (?:usar|chamar)|posso (?:usar|chamar)|"
        r"agenda real|google calendar|pesquisa(?:r)? web|web research|"
        r"gmail real|github api|chatwoot|uazapi|supabase prod|deploy vercel)\b"
    )),
    # task add / list — phrases like "cria tarefa" / "adiciona tarefa" /
    # "lista tarefas" / "minhas pendências"
    (INTENT_TASK_LIST, re.compile(
        r"(?i)\b(lista(?:r)? tarefas?|minhas pendências?|minhas tarefas?|task list|"
        r"o que est(?:á|a) na (?:fila|lista|backlog))\b"
    )),
    (INTENT_TASK_ADD, re.compile(
        r"(?i)\b(cria(?:r)? tarefa|adiciona(?:r)? tarefa|nova tarefa|"
        r"adiciona(?:r)? pendência|registra(?:r)? tarefa|task add|"
        r"anota(?:r)? como tarefa|coloca(?:r)? na fila)\b"
    )),
    # next action / what should I do now
    (INTENT_NEXT_ACTION, re.compile(
        r"(?i)\b(o que faço agora|o que fazer agora|próx(?:imo|imo passo|imo)|"
        r"next step|what now|next action|status agora|cockpit)\b"
    )),
    # self-evolve (jarvis itself)
    (INTENT_SELF_EVOLVE, re.compile(
        r"(?i)\b(auto[-\s]?evolu(?:i|ir|ção)|self[-\s]?evolve|evolui(?:r)? o jarvis|"
        r"melhora(?:r)? o jarvis|melhorar (?:o )?jarvis|evolu(?:i|ir)(?: o)? jarvis|"
        r"fortalec(?:er|e) (?:o )?jarvis|virar minha ferramenta principal)\b"
    )),
    # project fix / improve / build something inside a project — checked
    # before agenda_note so "corrige bug da agenda" routes to a sprint
    # mission instead of a calendar entry.
    (INTENT_PROJECT_FIX, re.compile(
        r"(?i)\b(corrig(?:e|ir|indo)|conserta(?:r)?|arruma(?:r)?|melhora(?:r)?|reescreve(?:r)?|"
        r"refator(?:a|ar)|implementa(?:r)?|adiciona(?:r)?|cria(?:r)?\s+(?:código|feature|tela)|"
        r"resolve(?:r)? bug|gera(?:r)? código|prepara(?:r)? missão)\b"
    )),
    # browser/UI QA
    (INTENT_BROWSER_QA, re.compile(
        r"(?i)\b(browser[-\s]?qa|teste(?:r)? (?:de )?ui|smoke (?:de )?ui|qa visual)\b"
    )),
    # final gate / pré-deploy
    (INTENT_FINAL_GATE, re.compile(
        r"(?i)\b(final[-\s]?gate|pré[-\s]?deploy|pre[-\s]?deploy|antes de subir|gate final)\b"
    )),
    # project QA sprint
    (INTENT_PROJECT_QA, re.compile(
        r"(?i)\b(qa[-\s]?sprint|sprint de qa|rod(?:a|ar) qa|qa do projeto)\b"
    )),
    # n8n workflow blueprint (distinctive nouns)
    (INTENT_N8N_BLUEPRINT, re.compile(
        r"(?i)\b(n8n|workflow|fluxo de automação|webhook|trigger node)\b"
    )),
    # research / plan
    (INTENT_RESEARCH_PLAN, re.compile(
        r"(?i)\b(pesquisa(?:r)?|investiga(?:r)?|estuda(?:r)?|research|me d(?:á|a)\s+(?:um\s+)?plano|"
        r"gera(?:r)? plano|levanta(?:r)? opções)\b"
    )),
    # automation blueprint
    (INTENT_AUTOMATION_BLUEPRINT, re.compile(
        r"(?i)\b(automaç(?:ã|a)o|automatiz(?:ar|ado)|cron|scheduler|integração entre)\b"
    )),
    # app blueprint (e.g. "novo app", "criar projeto")
    (INTENT_APP_BLUEPRINT, re.compile(
        r"(?i)\b(novo (?:app|projeto)|criar (?:projeto|app)|scaffold|boilerplate|inicia(?:r)? projeto)\b"
    )),
    # agenda — tight: requires "na/à/para agenda", or "agenda" as a verb at
    # start, or "lembrete", or weekday/time word + scheduling verb. Bare word
    # "agenda" (as in "bug da agenda") MUST NOT trigger.
    (INTENT_AGENDA_NOTE, re.compile(
        r"(?i)("
        r"\bcoloca(?:r)?\s+.*\b(?:na|à)\s+agenda\b"
        r"|\badiciona(?:r)?\s+(?:à|na)\s+agenda\b"
        r"|\b(?:na|à|para a?)\s+agenda\b"
        r"|^\s*agenda(?:r)?\s+(?:hoje|amanh(?:ã|a)|segunda|terça|terca|quarta|quinta|sexta|sábado|sabado|domingo|\d)"
        r"|\blembrete\b"
        r"|\blembrar?\s+(?:de\s+|que\s+)"
        r"|\bmarcar?\s+(?:reuni(?:ão|ao)|consulta|call|meeting|compromisso)\b"
        r")"
    )),
    # capture / inbox idea
    (INTENT_CAPTURE_NOTE, re.compile(
        r"(?i)\b(captur(?:a|ar)|inbox|anota(?:r|ção)|ideia[:\s]|salva(?:r)? ideia|"
        r"grava(?:r)? ideia|registra(?:r)? ideia)\b"
    )),
    # open project (without an explicit action verb)
    (INTENT_OPEN_PROJECT, re.compile(
        r"(?i)\b(abre|abrir|abra)\s+(?:o\s+)?(?:projeto\s+)?[a-z0-9_-]+"
    )),
]


def detect_intent(text: str):
    for intent, pattern in INTENT_PATTERNS:
        if pattern.search(text):
            return intent
    if not text.strip():
        return INTENT_UNCLEAR
    return INTENT_UNCLEAR


def detect_project_alias(text: str, override: str = None):
    if override:
        return override
    lower = text.lower()
    # match word-boundary alias names
    for alias in _project_aliases():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            return alias
    # synonyms / fragments
    for needle, alias in (
        ("jarvis", "jarvis-core"),
        ("self-evolve", "jarvis-core"),
        ("self evolve", "jarvis-core"),
    ):
        if needle in lower:
            return alias
    return None


# ── action planning ───────────────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "request"


# Map common request fragments to a capability name in CAPABILITY_REGISTRY.json.
# Conservative: only the obvious aliases. Anything ambiguous falls through.
_CAPABILITY_HINT_MAP = [
    (re.compile(r"(?i)\b(google calendar|agenda real|calendario real|calendário real)\b"), "google_calendar"),
    (re.compile(r"(?i)\b(pesquisa(?:r)? web|web research|busca(?:r)? na web)\b"), "web_research"),
    (re.compile(r"(?i)\bgmail\b"), "gmail"),
    (re.compile(r"(?i)\bgithub api\b"), "github_api"),
    (re.compile(r"(?i)\bchatwoot\b"), "chatwoot"),
    (re.compile(r"(?i)\buazapi\b"), "uazapi"),
    (re.compile(r"(?i)\bsupabase prod\b"), "supabase_prod"),
    (re.compile(r"(?i)\bdeploy (?:vercel|na vercel)\b"), "vercel_deploy"),
    (re.compile(r"(?i)\bbackground claude|claude (?:em )?background\b"), "background_claude_execution"),
    (re.compile(r"(?i)\b(api paga|llm paga|anthropic api|openai api)\b"), "paid_llm_api"),
    (re.compile(r"(?i)\b(push (?:no|para o) remote|git push)\b"), "push_to_remote"),
    (re.compile(r"(?i)\b(production deploy|deploy em produ(?:ção|cao))\b"), "production_deploy"),
]


def _detect_capability_hint(text: str):
    for pattern, name in _CAPABILITY_HINT_MAP:
        if pattern.search(text):
            return name
    return None


def _next_command_for(intent: str, project: str, text: str, copy_flag):
    """Return (command_list, human_string, safety, dry_run_safe)."""
    want_copy = " --copy" if copy_flag else ""
    if intent == INTENT_SCREEN_CAPTURE:
        return (
            ["./jarvis", "screen-capture", "--interactive", "--dry-run"],
            "./jarvis screen-capture --interactive --dry-run",
            SAFETY_LOCAL_PREP,
            True,
        )
    if intent == INTENT_IMAGE_TO_PDF:
        match = re.search(r"(?i)([^\s\"']+\.(?:png|jpe?g|heic|tiff?|webp|svg))", text)
        image = match.group(1) if match else "<IMAGEM>"
        return (
            ["./jarvis", "image-to-pdf", image, "--dry-run"],
            f'./jarvis image-to-pdf "{image}" --dry-run',
            SAFETY_LOCAL_PREP,
            bool(match),
        )
    if intent == INTENT_IMAGE_CONVERT:
        image_match = re.search(r"(?i)([^\s\"']+\.(?:png|jpe?g|heic|tiff?|webp|svg))", text)
        format_match = re.search(r"(?i)\b(?:para|em)\s+(png|jpe?g|tiff?)\b", text)
        image = image_match.group(1) if image_match else "<IMAGEM>"
        output_format = format_match.group(1).lower() if format_match else "<FORMATO>"
        return (
            ["./jarvis", "image-convert", image, "--to", output_format, "--dry-run"],
            f'./jarvis image-convert "{image}" --to {output_format} --dry-run',
            SAFETY_LOCAL_PREP,
            bool(image_match and format_match),
        )
    if intent == INTENT_SPEAK:
        quoted = re.search(r'["“](.+?)["”]', text)
        speech = quoted.group(1) if quoted else text
        return (
            ["./jarvis", "speak", speech, "--dry-run"],
            f'./jarvis speak "{speech}" --dry-run',
            SAFETY_LOCAL_PREP,
            True,
        )
    if intent == INTENT_MESSAGE_DRAFT:
        phone_match = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", text)
        phone = "".join(c for c in phone_match.group(0) if c.isdigit()) if phone_match else "<DDI_DDD_NUMERO>"
        return (
            ["./jarvis", "message-draft", "--phone", phone, "<TEXTO>", "--dry-run"],
            f'./jarvis message-draft --phone {phone} "<TEXTO>" --dry-run',
            SAFETY_LOCAL_PREP,
            bool(phone_match),
        )
    if intent == INTENT_MESSAGE_SEND:
        phone_match = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", text)
        phone = "".join(c for c in phone_match.group(0) if c.isdigit()) if phone_match else "<DDI_DDD_NUMERO>"
        return (
            ["./jarvis", "message-send", "--phone", phone, "<TEXTO>", "--dry-run"],
            f'./jarvis message-send --phone {phone} "<TEXTO>" --dry-run',
            SAFETY_LOCAL_WRITE,
            bool(phone_match),
        )
    if intent == INTENT_MEMORY_SAVE:
        return (
            ["./jarvis", "memory-save", text, "--dry-run"],
            f'./jarvis memory-save "{text}" --dry-run',
            SAFETY_LOCAL_WRITE,
            True,
        )
    if intent == INTENT_STORAGE_SCAN:
        return (
            ["./jarvis", "storage-scan", ".", "--top", "20"],
            "./jarvis storage-scan . --top 20",
            SAFETY_READONLY,
            True,
        )
    if intent == INTENT_FILES_TRIAGE:
        return (
            ["./jarvis", "files-triage", ".", "--limit", "100"],
            "./jarvis files-triage . --limit 100",
            SAFETY_READONLY,
            True,
        )
    if intent == INTENT_SELF_EVOLVE:
        return (
            ["./jarvis", "self-evolve", "--goal", text] + (["--copy"] if copy_flag else []),
            f'./jarvis self-evolve --goal "{text}"{want_copy}',
            SAFETY_LOCAL_PREP,
            True,
        )
    if intent == INTENT_PROJECT_FIX:
        proj = project or "<ALIAS>"
        return (
            ["./jarvis", "goal-sprint", "--project", proj, "--goal", text],
            f'./jarvis goal-sprint --project {proj} --goal "{text}"',
            SAFETY_LOCAL_PREP,
            bool(project),
        )
    if intent == INTENT_PROJECT_QA:
        proj = project or "<ALIAS>"
        return (
            ["./jarvis", "qa-sprint", "--project", proj],
            f"./jarvis qa-sprint --project {proj}",
            SAFETY_LOCAL_PREP,
            bool(project),
        )
    if intent == INTENT_BROWSER_QA:
        proj = project or "<ALIAS>"
        return (
            ["./jarvis", "browser-qa", "--project", proj],
            f"./jarvis browser-qa --project {proj}",
            SAFETY_LOCAL_PREP,
            bool(project),
        )
    if intent == INTENT_FINAL_GATE:
        proj = project or "<ALIAS>"
        return (
            ["./jarvis", "final-gate", "--project", proj],
            f"./jarvis final-gate --project {proj}",
            SAFETY_LOCAL_PREP,
            bool(project),
        )
    if intent == INTENT_N8N_BLUEPRINT:
        return (
            ["./jarvis", "blueprint", "--type", "n8n", "--goal", text],
            f'./jarvis blueprint --type n8n --goal "{text}"',
            SAFETY_LOCAL_WRITE,
            True,
        )
    if intent == INTENT_APP_BLUEPRINT:
        return (
            ["./jarvis", "blueprint", "--type", "app", "--goal", text],
            f'./jarvis blueprint --type app --goal "{text}"',
            SAFETY_LOCAL_WRITE,
            True,
        )
    if intent == INTENT_AUTOMATION_BLUEPRINT:
        return (
            ["./jarvis", "blueprint", "--type", "automation", "--goal", text],
            f'./jarvis blueprint --type automation --goal "{text}"',
            SAFETY_LOCAL_WRITE,
            True,
        )
    if intent == INTENT_RESEARCH_PLAN:
        return (
            ["./jarvis", "blueprint", "--type", "research", "--goal", text],
            f'./jarvis blueprint --type research --goal "{text}"',
            SAFETY_LOCAL_WRITE,
            True,
        )
    if intent == INTENT_AGENDA_NOTE:
        return (
            ["./jarvis", "agenda-add", text],
            f'./jarvis agenda-add "{text}"',
            SAFETY_LOCAL_WRITE,
            True,
        )
    if intent == INTENT_CAPTURE_NOTE:
        return (
            ["./jarvis", "capture", text],
            f'./jarvis capture "{text}"',
            SAFETY_LOCAL_WRITE,
            True,
        )
    if intent == INTENT_OPEN_PROJECT:
        proj = project or "<ALIAS>"
        return (
            ["./jarvis", "project-open", "--project", proj, "--print-only"],
            f"./jarvis project-open --project {proj} --print-only",
            SAFETY_READONLY,
            bool(project),
        )
    if intent == INTENT_NEXT_ACTION:
        return (
            ["./jarvis", "self-cockpit"],
            "./jarvis self-cockpit",
            SAFETY_READONLY,
            True,
        )
    if intent == INTENT_LIMITS:
        return (
            ["./jarvis", "limits"],
            "./jarvis limits",
            SAFETY_READONLY,
            True,
        )
    if intent == INTENT_CAPABILITY_CHECK:
        cap = _detect_capability_hint(text)
        if cap:
            return (
                ["./jarvis", "capability-check", cap],
                f"./jarvis capability-check {cap}",
                SAFETY_READONLY,
                True,
            )
        return (
            ["./jarvis", "capabilities"],
            "./jarvis capabilities",
            SAFETY_READONLY,
            True,
        )
    if intent == INTENT_TASK_ADD:
        return (
            ["./jarvis", "task-add", text],
            f'./jarvis task-add "{text}"',
            SAFETY_LOCAL_WRITE,
            True,
        )
    if intent == INTENT_TASK_LIST:
        return (
            ["./jarvis", "task-list"],
            "./jarvis task-list",
            SAFETY_READONLY,
            True,
        )
    # unclear
    return (
        ["./jarvis", "self-cockpit"],
        "./jarvis self-cockpit",
        SAFETY_READONLY,
        True,
    )


# ── output ────────────────────────────────────────────────────────────────────

def _print_header(text):
    print("JARVIS — Ask Router")
    print("Status real: interpretação local. Nada em produção foi alterado.")
    print("")
    print("Pedido:")
    print(f'"{text}"')
    print("")


def _explain_intent(intent: str) -> str:
    return {
        INTENT_NEXT_ACTION: "perguntar status / próximo passo — roda self-cockpit",
        INTENT_SELF_EVOLVE: "evoluir o próprio JARVIS — gera missão self-evolve",
        INTENT_PROJECT_FIX: "trabalho em projeto-alvo — gera missão goal-sprint",
        INTENT_PROJECT_QA: "QA sprint de projeto — gera missão qa-sprint",
        INTENT_BROWSER_QA: "QA de UI/browser — gera missão browser-qa",
        INTENT_FINAL_GATE: "validação final pré-deploy — gera missão final-gate",
        INTENT_N8N_BLUEPRINT: "blueprint n8n (somente spec/prompt local; sem webhook real)",
        INTENT_APP_BLUEPRINT: "blueprint de app/projeto novo (somente plano local)",
        INTENT_AUTOMATION_BLUEPRINT: "blueprint de automação (somente plano local)",
        INTENT_RESEARCH_PLAN: "pesquisa + plano (blueprint research)",
        INTENT_AGENDA_NOTE: "item de agenda local (append-only em 05_EXECUCAO/31_AGENDA)",
        INTENT_CAPTURE_NOTE: "captura no inbox local (append-only em 05_EXECUCAO/30_INBOX)",
        INTENT_OPEN_PROJECT: "abrir projeto — roda project-open --print-only",
        INTENT_CAPABILITY_CHECK: "checar capability no CAPABILITY_REGISTRY (rota para capability-check / capabilities)",
        INTENT_LIMITS: "explicar fronteira do robô — roda limits",
        INTENT_TASK_ADD: "adicionar tarefa à fila local — roda task-add",
        INTENT_TASK_LIST: "listar tarefas locais — roda task-list",
        INTENT_SCREEN_CAPTURE: "captura de tela local — sugere preview interativo",
        INTENT_IMAGE_TO_PDF: "conversão local de imagem para PDF — preserva o original",
        INTENT_IMAGE_CONVERT: "conversão local entre formatos de imagem permitidos",
        INTENT_SPEAK: "síntese de voz local — sugere preview antes de falar",
        INTENT_MESSAGE_DRAFT: "rascunho de WhatsApp — nunca envia automaticamente",
        INTENT_MESSAGE_SEND: "envio explícito pelo app Mensagens do macOS",
        INTENT_MEMORY_SAVE: "memória operacional local e versionável",
        INTENT_STORAGE_SCAN: "inventário read-only de arquivos grandes — nunca apaga",
        INTENT_FILES_TRIAGE: "plano read-only de organização por tipo — nunca move",
        INTENT_UNCLEAR: "intent não classificada — caindo em self-cockpit como fallback (auto-logged)",
    }.get(intent, intent)


def _print_interpretation(intent, project, safety, action_str, explain: bool):
    print("Interpretação:")
    print(f"- intent: {intent}")
    print(f"- project: {project or '(não detectado)'}")
    print(f"- safety: {safety}")
    print(f"- action: {action_str}")
    if explain:
        print(f"- explain: {_explain_intent(intent)}")
    print("")


def _print_next(command_str):
    print("Próximo comando:")
    print(f"  {command_str}")
    print("")


def _print_footer(did_lines, did_not_lines):
    print("O que JARVIS fez:")
    for l in did_lines or ["- nada (apenas interpretou e imprimiu sugestão)"]:
        print(l)
    print("")
    print("O que JARVIS NÃO fez:")
    for l in did_not_lines:
        print(l)
    print("")
    print("Produção: nada alterado.")


def _delegate(cmd_list):
    """Run a JARVIS sub-command from the same repo. Returns exit code.
    Never raises — keeps ask_router resilient."""
    try:
        return subprocess.call(cmd_list, cwd=ROOT)
    except Exception as e:
        print(f"AVISO: delegação falhou: {e}")
        return 1


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    text, alias_override, dry_run, copy_flag, explain, force, log_mode, no_log = parse_args(argv)

    if log_mode and not text:
        _show_unclear_log()
        return

    if not text:
        _print_header("")
        print("FALHA: pedido vazio. Uso: ./jarvis ask \"o que faço agora\"")
        print("Produção: nada alterado.")
        sys.exit(1)

    intent = detect_intent(text)
    project = detect_project_alias(text, alias_override)
    cmd_list, cmd_str, safety, dry_run_safe = _next_command_for(intent, project, text, copy_flag)

    # If the classifier punted to UNCLEAR, log the request so future pattern
    # tuning has real data to work from. Secret-shaped requests are skipped.
    # `--no-log` lets smoke/CI exercise the unclear path without growing the log.
    if intent == INTENT_UNCLEAR and not no_log:
        _log_unclear(text, project)

    _print_header(text)
    _print_interpretation(intent, project, safety, cmd_str, explain)
    _print_next(cmd_str)

    did = []
    did_not = [
        "- não abriu produção",
        "- não chamou API paga",
        "- não executou Claude",
        "- não mexeu em projeto alvo",
        "- não leu .env",
    ]

    if dry_run or copy_flag is None:
        # default: ask just interprets. go-mode would call with copy_flag=True.
        did = ["- interpretou o pedido localmente (regex + registry)"]
        if dry_run:
            print("Modo: --dry-run (apenas interpretação; nada delegado).")
        _print_footer(did, did_not)
        return

    # Non-dry-run: actually delegate. Only do this if the next command is safe
    # by design (does not push, deploy, edit target, run Claude).
    if intent in (INTENT_PROJECT_FIX, INTENT_PROJECT_QA, INTENT_BROWSER_QA, INTENT_FINAL_GATE, INTENT_OPEN_PROJECT) and not project:
        print("AVISO: intent envolve projeto-alvo, mas alias não foi detectado.")
        print("Use --project ALIAS para forçar, ou re-escreva incluindo o alias.")
        _print_footer(did, did_not)
        return

    print("Delegando para sub-comando JARVIS (sem executar Claude, sem tocar projeto-alvo).")
    rc = _delegate(cmd_list)
    did.append("- interpretou o pedido localmente")
    did.append(f"- delegou para: {cmd_str} (exit={rc})")
    _print_footer(did, did_not)


if __name__ == "__main__":
    main()
