"""
local_capture.py — JARVIS local inbox / agenda (no external APIs).

Sub-commands (selected via positional argv[0]):
  capture "text"            append to 05_EXECUCAO/30_INBOX/INBOX.md
  inbox                     read INBOX.md
  agenda-add "text"         append to 05_EXECUCAO/31_AGENDA/AGENDA.md
  agenda                    lê a agenda do app (Supabase) ou AGENDA.md

Flags (where applicable):
  --dry-run                 preview only, no file write
  --date YYYY-MM-DD         override date stamp on agenda items

Hard rules:
  - append-only, timestamped
  - refuses input that looks secret-like (reuses SECRET_PATTERNS)
  - agenda lê/grava no Supabase do app quando o worker.env tem credencial;
    sem credencial, cai no arquivo local (comportamento antigo)
  - sem Google Calendar, sem reminders, sem Slack
  - never prints secrets
"""
from pathlib import Path
from datetime import datetime, date, timezone
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
INBOX_DIR = ROOT / "05_EXECUCAO" / "30_INBOX"
AGENDA_DIR = ROOT / "05_EXECUCAO" / "31_AGENDA"
INBOX_FILE = INBOX_DIR / "INBOX.md"
AGENDA_FILE = AGENDA_DIR / "AGENDA.md"

# Reuse SECRET_PATTERNS from secret_scan.py so we keep a single source of truth.
try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from secret_scan import SECRET_PATTERNS  # type: ignore
except Exception:
    SECRET_PATTERNS = []

try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from jarvis_supabase import credentials as _supabase_credentials  # type: ignore
    from jarvis_supabase import rest as _supabase_rest  # type: ignore
except Exception:
    def _supabase_credentials():
        return "", ""

    def _supabase_rest(*_args, **_kwargs):
        raise OSError("Supabase indisponível")

AGENDA_TABLE = "jarvis_agenda_items"

try:
    from zoneinfo import ZoneInfo

    LOCAL_TZ = ZoneInfo(os.environ.get("JARVIS_TIMEZONE", "America/Sao_Paulo"))
except Exception:  # sem tzdata: cai no fuso do processo
    LOCAL_TZ = None


def _local_iso(value: str) -> str:
    """Relógio de parede local → ISO em UTC. "" quando a data é inválida."""
    try:
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        return ""
    if LOCAL_TZ is None:
        return naive.astimezone().astimezone(timezone.utc).isoformat()
    return naive.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc).isoformat()


def _utc_to_local(value: str) -> str:
    """ISO em UTC do banco → "YYYY-MM-DD HH:MM" no relógio do dono."""
    raw = str(value or "")
    if not raw:
        return ""
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[:16].replace("T", " ")
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if LOCAL_TZ is not None:
        when = when.astimezone(LOCAL_TZ)
    return when.strftime("%Y-%m-%d %H:%M")


def _looks_secret_like(text: str) -> bool:
    for _name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _parse_common(argv):
    text_parts = []
    dry_run = False
    date_override = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            dry_run = True
            i += 1
            continue
        if a == "--date":
            if i + 1 < len(argv):
                date_override = argv[i + 1].strip()
                i += 2
                continue
        if a.startswith("--date="):
            date_override = a.split("=", 1)[1].strip()
            i += 1
            continue
        text_parts.append(a)
        i += 1
    return " ".join(text_parts).strip(), dry_run, date_override


def _ensure_file(path: Path, header: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(header, encoding="utf-8")


# ── capture ───────────────────────────────────────────────────────────────────

def cmd_capture(argv):
    text, dry_run, _date = _parse_common(argv)
    print("JARVIS — Local Capture")
    print("Status real: append-only local. Nada em produção foi alterado.")
    print("")
    if not text:
        print('FALHA: texto vazio. Uso: ./jarvis capture "ideia ..."')
        sys.exit(1)
    if _looks_secret_like(text):
        print("FALHA: o texto parece conter segredo (token/api_key/etc).")
        print("Ação segura: NÃO gravamos nada. Remova o segredo e tente de novo.")
        sys.exit(2)
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"- [{ts}] {text}"
    print(f"alvo: {INBOX_FILE.relative_to(ROOT)}")
    print(f"linha: {line}")
    print("")
    if dry_run:
        print("Modo: --dry-run (nada gravado).")
        print("Produção: nada alterado.")
        return
    _ensure_file(INBOX_FILE, "# JARVIS local inbox (append-only)\n\n")
    with INBOX_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"OK — anexado em {INBOX_FILE.relative_to(ROOT)}")
    print("Produção: nada alterado.")


def cmd_inbox(argv):
    _text, _dry, _d = _parse_common(argv)
    print("JARVIS — Local Inbox")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    if not INBOX_FILE.exists():
        print(f"(arquivo ausente — registre algo com `./jarvis capture \"...\"`)")
        print(f"alvo: {INBOX_FILE.relative_to(ROOT)}")
        print("Produção: nada alterado.")
        return
    body = INBOX_FILE.read_text(encoding="utf-8", errors="ignore")
    print(f"arquivo: {INBOX_FILE.relative_to(ROOT)} ({len(body)} bytes)")
    items = [l for l in body.splitlines() if l.startswith("- [")]
    print(f"itens: {len(items)}")
    print("")
    for line in items[-30:]:
        print(line)
    if len(items) > 30:
        print(f"... (+{len(items) - 30} itens anteriores)")
    print("")
    print("Produção: nada alterado.")


# ── agenda ────────────────────────────────────────────────────────────────────

_WEEKDAY_PT = {
    "segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3,
    "sexta": 4, "sábado": 5, "sabado": 5, "domingo": 6,
}


_TIME_PATTERNS = (
    re.compile(r"(?i)\b(?:[àa]s)\s+([01]?\d|2[0-3])(?:(?::|h)([0-5]\d))?\b"),
    re.compile(r"\b([01]?\d|2[0-3])h([0-5]\d)?\b"),
    re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b"),
)

# Verbos de anotação que não fazem parte do conteúdo do item.
_NOTE_VERB = re.compile(
    r"(?i)^\s*(?:jarvis[,\s]+)?(?:anota(?:r)?|anote|lembra(?:r)?|lembre|"
    r"me\s+lembra(?:r)?|me\s+lembre)\s+(?:que\s+|de\s+|a[ií]\s*[:,-]?\s*|:\s*)?"
)


def _infer_date(text: str, override: str, today=None):
    """Best-effort date parse without external libs.

    Priority: explicit override > YYYY-MM-DD in text > 'hoje'/'amanhã' >
    weekday hint > None. Returns a string (YYYY-MM-DD) or None."""
    if override:
        try:
            datetime.strptime(override, "%Y-%m-%d")
            return override
        except Exception:
            return override  # let user be explicit even if odd format
    today = today or date.today()
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        return m.group(1)
    lower = text.lower()
    if re.search(r"\bhoje\b", lower):
        return today.isoformat()
    if re.search(r"\bamanh(?:ã|a)\b", lower):
        return date.fromordinal(today.toordinal() + 1).isoformat()
    for word, target in _WEEKDAY_PT.items():
        if re.search(rf"\b{word}\b", lower):
            delta = (target - today.weekday()) % 7
            if delta == 0:
                delta = 7
            return date.fromordinal(today.toordinal() + delta).isoformat()
    return None


def _infer_time(text: str):
    """(hora, minuto) ou None. Exige 'às 14h', '14h30' ou '14:30'.

    "a" solto não conta: "a 14 de novembro" viraria 14:00.
    """
    for pattern in _TIME_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    return None


def _infer_when(text: str, override: str, today=None):
    """Data + hora. 'YYYY-MM-DD HH:MM', 'YYYY-MM-DD' ou None."""
    base = _infer_date(text, override, today=today)
    if not base or len(base) > 10:
        return base
    clock = _infer_time(text)
    if clock:
        return f"{base} {clock[0]:02d}:{clock[1]:02d}"
    return base


def _strip_note_verb(text: str) -> str:
    stripped = _NOTE_VERB.sub("", text or "").strip()
    return stripped or text


_AGENDA_LINE = re.compile(r"^- \[(?P<when>[^\]]+)\]\s+\(criado (?P<created>[^)]+)\)\s+(?P<text>.*)$")
_INBOX_LINE = re.compile(r"^- \[(?P<ts>[^\]]+)\]\s+(?P<text>.*)$")


def parse_agenda_line(line: str):
    match = _AGENDA_LINE.match(line.strip())
    return match.groupdict() if match else None


def parse_inbox_line(line: str):
    match = _INBOX_LINE.match(line.strip())
    return match.groupdict() if match else None


def _supabase_agenda_items(base, key):
    """Agenda do app no formato do arquivo local. None quando não respondeu."""
    try:
        rows = _supabase_rest(
            base, key, AGENDA_TABLE,
            query=(
                "select=id,title,status,scheduled_for,created_at&owner_id=eq.theo"
                "&status=eq.pending&order=scheduled_for.asc.nullslast&limit=200"
            ),
        )
    except (OSError, ValueError):
        return None
    items = []
    for row in rows if isinstance(rows, list) else []:
        scheduled = str(row.get("scheduled_for") or "")
        items.append({
            "when": _utc_to_local(scheduled) or "sem-data",
            "text": str(row.get("title") or ""),
            "created": str(row.get("created_at") or "")[:19],
        })
    return items


def read_agenda_items(path=None):
    """Itens da agenda: a do app quando há credencial, senão o arquivo local.

    Quem lê (week, agenda) enxerga a mesma agenda que o JARVIS fala — antes o
    relatório da semana contava uma agenda e a voz outra.
    """
    if path is None:
        base, key = _supabase_credentials()
        if base and key:
            items = _supabase_agenda_items(base, key)
            if items is not None:
                return items
    target = Path(path) if path else AGENDA_FILE
    if not target.exists():
        return []
    body = target.read_text(encoding="utf-8", errors="ignore")
    items = [parse_agenda_line(line) for line in body.splitlines() if line.startswith("- [")]
    return [item for item in items if item]


def read_inbox_items(path=None):
    target = Path(path) if path else INBOX_FILE
    if not target.exists():
        return []
    body = target.read_text(encoding="utf-8", errors="ignore")
    items = [parse_inbox_line(line) for line in body.splitlines() if line.startswith("- [")]
    return [item for item in items if item]


def cmd_agenda_add(argv):
    text, dry_run, date_override = _parse_common(argv)
    base, key = _supabase_credentials()
    print("JARVIS — Agenda Add")
    print("Status real: grava na agenda do app quando há credencial; senão, no arquivo local.")
    print("")
    if not text:
        print('FALHA: texto vazio. Uso: ./jarvis agenda-add "tarefa"')
        sys.exit(1)
    if _looks_secret_like(text):
        print("FALHA: o texto parece conter segredo (token/api_key/etc).")
        print("Ação segura: NÃO gravamos nada.")
        sys.exit(2)
    when = _infer_when(text, date_override) or "sem-data"
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"- [{when}] (criado {ts}) {_strip_note_verb(text)}"
    print(f"data inferida: {when}")
    print(f"linha: {line}")
    print("")
    if dry_run:
        print("Modo: --dry-run (nada gravado).")
        print("Produção: nada alterado.")
        return
    if base and key:
        # _infer_when devolve "YYYY-MM-DD" ou "YYYY-MM-DD HH:MM".
        if when == "sem-data":
            scheduled = None
        else:
            # `when` é relógio local; gravar como UTC fazia o item aparecer
            # 3h diferente no app. Converte de verdade.
            scheduled = _local_iso(when if " " in when else when + " 12:00") or None
        try:
            saved = _supabase_rest(
                base, key, AGENDA_TABLE, "POST",
                body={
                    "owner_id": "theo",
                    "title": _strip_note_verb(text),
                    "scheduled_for": scheduled,
                    "source": "jarvis-cli",
                },
            )
            item = saved[0] if isinstance(saved, list) and saved else {}
            print(f"OK — anotado na agenda do app (id {item.get('id', '?')}).")
            print("Produção: nada alterado.")
            return
        except (OSError, ValueError):
            print("AVISO: a agenda do app não respondeu; gravando no arquivo local.")
            print("")
    print(f"alvo: {AGENDA_FILE.relative_to(ROOT)}")
    _ensure_file(AGENDA_FILE, "# JARVIS local agenda (append-only)\n\n")
    with AGENDA_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"OK — anexado em {AGENDA_FILE.relative_to(ROOT)}")
    print("Produção: nada alterado.")


def _print_supabase_agenda(base, key):
    """Agenda do app, que é a mesma que a voz lê. True quando conseguiu."""
    try:
        rows = _supabase_rest(
            base, key, AGENDA_TABLE,
            query=(
                "select=id,title,status,scheduled_for&owner_id=eq.theo&status=eq.pending"
                "&order=scheduled_for.asc.nullslast,created_at.desc&limit=50"
            ),
        )
    except (OSError, ValueError):
        return False
    print("JARVIS — Agenda")
    print("Status real: leitura da agenda do app. Nada foi editado.")
    print("fonte: Supabase (a mesma que o JARVIS fala)")
    print(f"itens: {len(rows)}")
    print("")
    if not rows:
        print("(vazia — anote com `./jarvis agenda-add \"...\"`)")
        print("Produção: nada alterado.")
        return True
    for row in rows:
        due = str(row.get("scheduled_for") or "")[:16].replace("T", " ") or "sem-data"
        print(f"- [{due}] {row.get('title', '')}")
    print("")
    print("Produção: nada alterado.")
    return True


def cmd_agenda(argv):
    _text, _dry, _d = _parse_common(argv)
    base, key = _supabase_credentials()
    if base and key and _print_supabase_agenda(base, key):
        return
    if base and key:
        print("AVISO: a agenda do app não respondeu; mostrando o arquivo local.")
        print("")
    print("JARVIS — Agenda (local)")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    if not AGENDA_FILE.exists():
        print(f"(arquivo ausente — registre algo com `./jarvis agenda-add \"...\"`)")
        print(f"alvo: {AGENDA_FILE.relative_to(ROOT)}")
        print("Produção: nada alterado.")
        return
    body = AGENDA_FILE.read_text(encoding="utf-8", errors="ignore")
    print(f"arquivo: {AGENDA_FILE.relative_to(ROOT)} ({len(body)} bytes)")
    items = [l for l in body.splitlines() if l.startswith("- [")]
    print(f"itens: {len(items)}")
    print("")
    today_iso = date.today().isoformat()
    upcoming = [l for l in items if "[sem-data]" not in l and "[" in l and l[3:13] >= today_iso]
    upcoming.sort(key=lambda l: l[3:23])
    past = [l for l in items if l not in upcoming]
    print(f"futuras: {len(upcoming)}")
    for line in upcoming[:30]:
        print(line)
    print("")
    if past:
        print(f"passadas/sem-data (últimas 10): {len(past)}")
        for line in past[-10:]:
            print(line)
        print("")
    print("Produção: nada alterado.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: local_capture.py <capture|inbox|agenda-add|agenda> [flags] [texto]")
        sys.exit(1)
    sub = argv[0]
    rest = argv[1:]
    if sub == "capture":
        cmd_capture(rest)
    elif sub == "inbox":
        cmd_inbox(rest)
    elif sub == "agenda-add":
        cmd_agenda_add(rest)
    elif sub == "agenda":
        cmd_agenda(rest)
    else:
        print(f"FALHA: subcomando desconhecido: {sub}")
        sys.exit(1)


if __name__ == "__main__":
    main()
