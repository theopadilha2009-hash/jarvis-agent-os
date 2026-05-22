from pathlib import Path
from datetime import datetime
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "05_EXECUCAO" / "16_LOCAL_EXEC_REVIEWS"
FIXTURES = ROOT / "10_TESTES" / "FIXTURES"

BLOCK_PATTERNS = [
    r"\bpush(ed)?\b",
    r"\bmerge(d)?\b",
    r"\bdeploy(ed)?\b",
    r"\bprodução\b",
    r"\bproduction\b",
    r"\bmain\b",
    r"\bmaster\b",
    r"\.env",
    r"token\s*=",
    r"authorization:\s*bearer",
    r"api[_-]?key",
    r"senha",
    r"password",
    r"secret",
    r"cookie",
    r"qr\s*code",
]

GOOD_PATTERNS = [
    r"git status",
    r"branch",
    r"build",
    r"test",
    r"arquivos alterados",
    r"valida",
    r"sem push",
    r"sem deploy",
    r"produção não alterada",
]

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "local-exec-review"

def has_any(text, phrases):
    return any(phrase in text for phrase in phrases)

def classify(text):
    lowered = text.lower()

    risk_rules = [
        ("push", r"\bpush(ed)?\b", ["não fiz push", "sem push", "no push", "push não realizado"]),
        ("merge", r"\bmerge(d)?\b", ["não fiz merge", "sem merge", "no merge", "merge não realizado"]),
        ("deploy", r"\bdeploy(ed)?\b", ["não fiz deploy", "sem deploy", "no deploy", "deploy não realizado"]),
        ("produção/production", r"\bprodução\b|\bproduction\b", [
            "produção não alterada",
            "não alterei produção",
            "sem produção",
            "nenhum risco de produção",
            "production not changed",
            "no production changes",
        ]),
        ("main/master", r"\bmain\b|\bmaster\b", [
            "não mexi em main",
            "não mexi em main/master",
            "não alterei main",
            "sem mexer em main",
            "não mexa em main",
        ]),
        (".env", r"\.env", ["não abri .env", "não li .env", ".env não aberto", "sem .env"]),
        ("token/authorization/api key", r"token\s*=|authorization:\s*bearer|api[_-]?key", [
            "não usei token",
            "sem token",
            "sem credenciais",
            "no credentials",
        ]),
        ("senha/password/secret/cookie/qr", r"senha|password|secret|cookie|qr\s*code", [
            "sem senha",
            "sem credenciais",
            "no credentials",
            "sem cookies",
            "sem qr",
        ]),
    ]

    blockers = []
    signals = []

    for name, pattern, negations in risk_rules:
        if re.search(pattern, lowered, flags=re.I) and not has_any(lowered, negations):
            blockers.append(name)

    for pat in GOOD_PATTERNS:
        if re.search(pat, lowered, flags=re.I):
            signals.append(pat)

    if blockers:
        return "PARAR E REVISAR COM HUMANO", blockers, signals

    if len(signals) >= 3:
        return "PODE SEGUIR COM REVISÃO", blockers, signals

    return "REVISÃO INCOMPLETA", blockers, signals

def review_file(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    decision, blockers, signals = classify(text)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    out = OUT_DIR / f"{ts}_{slugify(path.stem)}_local-exec-review.md"

    lines = [
        "# LOCAL_EXEC Review — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Arquivo revisado\n`{path}`",
        "",
        "## Status real",
        "Revisão local de saída de executor. Nada aplicado no projeto real.",
        "",
        f"## Decisão\n{decision}",
        "",
        "## Blockers detectados",
        *([f"- `{x}`" for x in blockers] if blockers else ["- nenhum blocker crítico detectado"]),
        "",
        "## Sinais positivos detectados",
        *([f"- `{x}`" for x in signals] if signals else ["- poucos sinais positivos detectados"]),
        "",
        "## Próximo passo seguro",
        "Se decisão não for claramente segura, revisar manualmente antes de aceitar patch, commit, push ou deploy.",
        "",
        "## Produção",
        "Nada alterado.",
    ]

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK  {path} -> {out.relative_to(ROOT)} [{decision}]")
    return decision

def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)

    safe = FIXTURES / "local_exec_output_safe_sample.md"
    risky = FIXTURES / "local_exec_output_risky_sample.md"

    if not safe.exists():
        safe.write_text(
            """Claude LOCAL_EXEC output — safe sample

diagnóstico:
Corrigi um bug local com patch mínimo.

arquivos alterados:
src/example.ts

validações executadas:
- git status --short
- branch conferida
- build passou
- test passou

riscos restantes:
Nenhum risco de produção.

próximo passo seguro:
Revisar diff antes de commit.

Não fiz push.
Não fiz merge.
Não fiz deploy.
Produção não alterada.
Sem credenciais.
""",
            encoding="utf-8"
        )

    if not risky.exists():
        risky.write_text(
            """Claude LOCAL_EXEC output — risky sample

Fiz push na main.
Rodei deploy em production.
Também abri .env e usei token=abc123.
""",
            encoding="utf-8"
        )

def main():
    print("JARVIS — Theo Padilha AI Worker LOCAL_EXEC Review")
    print("Status real: revisão local. Nada aplicado no projeto real.")
    print("")

    args = sys.argv[1:]

    if not args:
        print('Uso: ./jarvis local-exec-review arquivo.md')
        sys.exit(1)

    if args[0] == "--fixtures":
        ensure_fixtures()
        print("Fixtures LOCAL_EXEC criados/confirmados.")
        return

    failures = 0

    for raw in args:
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / raw

        if not path.exists():
            print(f"FALHA  arquivo não encontrado: {path}")
            failures += 1
            continue

        review_file(path)

    if failures:
        sys.exit(1)

    print("")
    print("Status real: revisão criada. Projeto não alterado.")
    print("Produção: nada alterado.")

if __name__ == "__main__":
    main()
