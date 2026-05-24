"""
local_capture.py — JARVIS local inbox / agenda (no external APIs).

Sub-commands (selected via positional argv[0]):
  capture "text"            append to 05_EXECUCAO/30_INBOX/INBOX.md
  inbox                     read INBOX.md
  agenda-add "text"         append to 05_EXECUCAO/31_AGENDA/AGENDA.md
  agenda                    read AGENDA.md

Flags (where applicable):
  --dry-run                 preview only, no file write
  --date YYYY-MM-DD         override date stamp on agenda items

Hard rules:
  - append-only, timestamped
  - refuses input that looks secret-like (reuses SECRET_PATTERNS)
  - no external APIs, no Google Calendar, no reminders, no Slack
  - never reads .env
  - never prints secrets
"""
from pathlib import Path
from datetime import datetime, date
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


def _infer_date(text: str, override: str):
    """Best-effort date parse without external libs.

    Priority: explicit override > YYYY-MM-DD in text > 'hoje'/'amanhã' >
    weekday hint > None. Returns a string (YYYY-MM-DD) or None."""
    if override:
        try:
            datetime.strptime(override, "%Y-%m-%d")
            return override
        except Exception:
            return override  # let user be explicit even if odd format
    today = date.today()
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        return m.group(1)
    lower = text.lower()
    if re.search(r"\bhoje\b", lower):
        return today.isoformat()
    if re.search(r"\bamanh(?:ã|a)\b", lower):
        return (today + (date.fromordinal(today.toordinal() + 1) - today)).isoformat()
    for word, target in _WEEKDAY_PT.items():
        if re.search(rf"\b{word}\b", lower):
            delta = (target - today.weekday()) % 7
            if delta == 0:
                delta = 7
            return date.fromordinal(today.toordinal() + delta).isoformat()
    return None


def cmd_agenda_add(argv):
    text, dry_run, date_override = _parse_common(argv)
    print("JARVIS — Agenda Add (local)")
    print("Status real: append-only local. Nada externo foi notificado.")
    print("")
    if not text:
        print('FALHA: texto vazio. Uso: ./jarvis agenda-add "tarefa"')
        sys.exit(1)
    if _looks_secret_like(text):
        print("FALHA: o texto parece conter segredo (token/api_key/etc).")
        print("Ação segura: NÃO gravamos nada.")
        sys.exit(2)
    when = _infer_date(text, date_override) or "sem-data"
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"- [{when}] (criado {ts}) {text}"
    print(f"alvo: {AGENDA_FILE.relative_to(ROOT)}")
    print(f"data inferida: {when}")
    print(f"linha: {line}")
    print("")
    if dry_run:
        print("Modo: --dry-run (nada gravado).")
        print("Produção: nada alterado.")
        return
    _ensure_file(AGENDA_FILE, "# JARVIS local agenda (append-only)\n\n")
    with AGENDA_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"OK — anexado em {AGENDA_FILE.relative_to(ROOT)}")
    print("Produção: nada alterado.")


def cmd_agenda(argv):
    _text, _dry, _d = _parse_common(argv)
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
