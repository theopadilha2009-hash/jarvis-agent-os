from pathlib import Path
from datetime import datetime
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INBOX = ROOT / "00_COLE_AQUI" / "03_OUTPUTS_CLAUDE_CHATGPT"
OUT_DIR = ROOT / "05_EXECUCAO" / "10_EXECUTOR_OUTPUT_REVIEWS"
LOG_DIR = ROOT / "09_LOGS"

RISK_WORDS = [
    "deploy", "push", "merge", "main", "master", "production", "produção",
    "prod", "sudo", "rm -rf", "drop table", "delete from", "truncate",
    ".env", "token", "api key", "apikey", "password", "senha", "secret",
    "service_role", "authorization", "bearer", "cookie", "qr code",
]

VALIDATION_WORDS = [
    "build", "test", "lint", "smoke", "quality", "passed", "passou",
    "bun run build", "npm run build", "pytest", "vitest", "jest",
]

CHANGE_WORDS = [
    "alterei", "changed", "modified", "updated", "created", "criei",
    "deletei", "removi", "patch", "diff", "files changed", "arquivo",
]

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "executor-output"

def sanitize(text):
    patterns = [
        (r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s]+", r"\1[REDACTED]"),
        (r"(?i)(api[_-]?key\s*[:=]\s*)[^\s]+", r"\1[REDACTED]"),
        (r"(?i)(token\s*[:=]\s*)[^\s]+", r"\1[REDACTED]"),
        (r"(?i)(password\s*[:=]\s*)[^\s]+", r"\1[REDACTED]"),
        (r"(?i)(senha\s*[:=]\s*)[^\s]+", r"\1[REDACTED]"),
        (r"(?i)(secret\s*[:=]\s*)[^\s]+", r"\1[REDACTED]"),
        (r"(?i)(service_role\s*[:=]\s*)[^\s]+", r"\1[REDACTED]"),
    ]
    for pat, repl in patterns:
        text = re.sub(pat, repl, text)
    return text

def infer_executor(text, filename):
    t = (text + " " + filename).lower()
    if "claude" in t:
        return "CLAUDE"
    if "gemini" in t:
        return "GEMINI"
    if "chatgpt" in t or "openai" in t:
        return "CHATGPT"
    return "UNKNOWN"

def find_hits(text, words):
    low = text.lower()
    return sorted(set(w for w in words if w in low))

def extract_files(text):
    candidates = set()
    for m in re.findall(r"[\w./-]+\.(?:ts|tsx|js|jsx|py|json|md|yml|yaml|sql|css|html|txt)", text):
        if len(m) <= 140 and ".env" not in m.lower():
            candidates.add(m)
    return sorted(candidates)[:30]

def classify_status(text):
    low = text.lower()
    if any(x in low for x in ["não editei", "no changes", "read-only", "read only", "sem alterar"]):
        return "read-only / análise"
    if any(x in low for x in ["alterei", "modified", "updated", "patch", "files changed"]):
        return "alteração sugerida ou realizada pelo executor"
    return "não confirmado"

def review_file(path):
    raw = path.read_text(encoding="utf-8", errors="ignore")
    safe = sanitize(raw)
    executor = infer_executor(safe, path.name)
    risks = find_hits(safe, RISK_WORDS)
    validations = find_hits(safe, VALIDATION_WORDS)
    changes = find_hits(safe, CHANGE_WORDS)
    files = extract_files(safe)
    status = classify_status(safe)

    production_risk = any(x in risks for x in ["deploy", "production", "produção", "prod", "push", "merge", "main", "master"])
    secret_risk = any(x in risks for x in [".env", "token", "api key", "apikey", "password", "senha", "secret", "service_role", "authorization", "bearer", "cookie", "qr code"])

    if production_risk or secret_risk:
        decision = "PARAR E REVISAR COM HUMANO"
        next_step = "Não aplicar mudanças. Revisar riscos, diff e presença de segredo antes de continuar."
    elif validations:
        decision = "PODE SEGUIR COM REVISÃO"
        next_step = "Revisar arquivos/diff localmente e confirmar se build/teste realmente passou."
    else:
        decision = "PRECISA DE VALIDAÇÃO"
        next_step = "Pedir ao executor comandos rodados, arquivos alterados e resultado de build/teste."

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out = OUT_DIR / f"{ts}_{slugify(path.stem)}_review.md"
    log = LOG_DIR / f"{ts}_executor-output-review.md"

    excerpt = safe[-5000:]

    lines = [
        "# Executor Output Review — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Source\n{path}",
        "",
        "## Status real",
        "Revisão local de output de executor. Nada aplicado no projeto real.",
        "",
        f"## Executor inferido\n{executor}",
        "",
        f"## Status do output\n{status}",
        "",
        f"## Decisão\n{decision}",
        "",
        f"## Riscos detectados\n{', '.join(risks) if risks else 'nenhum risco textual forte detectado'}",
        "",
        f"## Sinais de validação\n{', '.join(validations) if validations else 'nenhum build/test/lint claro detectado'}",
        "",
        f"## Sinais de alteração\n{', '.join(changes) if changes else 'nenhum sinal forte de alteração detectado'}",
        "",
        f"## Arquivos mencionados\n" + ("\n".join(f"- `{x}`" for x in files) if files else "nenhum arquivo técnico detectado"),
        "",
        "## Próximo passo seguro",
        next_step,
        "",
        "## Produção",
        "Nada alterado por esta revisão.",
        "",
        "## Trecho sanitizado do output",
        "```text",
        excerpt,
        "```",
        "",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")
    log.write_text(f"# Executor output review\n\nSource: {path}\nReview: {out}\nDecision: {decision}\n", encoding="utf-8")

    return out, decision

def collect_targets(args):
    if args:
        return [Path(a).expanduser() for a in args]
    if not DEFAULT_INBOX.exists():
        DEFAULT_INBOX.mkdir(parents=True, exist_ok=True)
        return []
    return sorted(
        [p for p in DEFAULT_INBOX.glob("*") if p.is_file() and p.suffix.lower() in [".txt", ".md"]],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

def main():
    targets = collect_targets(sys.argv[1:])

    print("JARVIS — Theo Padilha AI Worker Review Output v2")
    print("")

    if not targets:
        print("Nenhum output encontrado.")
        print(f"Coloque arquivos .txt/.md em: {DEFAULT_INBOX.relative_to(ROOT)}")
        return

    created = []
    failed = []

    for target in targets:
        if not target.exists():
            failed.append((target, "arquivo não encontrado"))
            continue
        try:
            out, decision = review_file(target)
            created.append((target, out, decision))
            print(f"OK  {target} -> {out.relative_to(ROOT)} [{decision}]")
        except Exception as e:
            failed.append((target, str(e)))
            print(f"FALHA  {target}: {e}")

    print("")
    print(f"Reviews criados: {len(created)}")
    print(f"Falhas: {len(failed)}")
    print("Status real: revisão local. Nada aplicado no projeto real.")

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
