"""
report_intake.py — validate + apply Claude final reports.

Sub-commands (positional argv[0]):
  template                            print the exact "cat > /tmp/..." block
  status                              status of the expected report file
  check  --file PATH                  validate the report (no write)
  apply  --file PATH [--force-weak]   delegate to self-debrief or
                                      project-memory-update --apply,
                                      picking the project from the
                                      current work session.

Hard rules:
  - never reads .env
  - never prints secrets
  - refuses apply on weak / secret-shaped reports
  - never touches the target project itself (delegates to existing safe paths)
"""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

# Reuse the weak-report classifier from project_memory_update so we have a
# single source of truth.
try:
    sys.path.insert(0, str(ROOT / "11_SCRIPTS"))
    from project_memory_update import report_quality, SECTION_HEADINGS  # type: ignore
    from secret_scan import SECRET_PATTERNS  # type: ignore
    from work_session import _load_current, update_status  # type: ignore
except Exception as e:
    SECRET_PATTERNS = []
    SECTION_HEADINGS = ("STATUS REAL", "FILES CHANGED", "VALIDATION RESULTS",
                        "COMMITS CREATED", "SAFE TO COMMIT", "WHAT IMPROVED",
                        "RISKS")

    def report_quality(_t):
        return "weak", 0, 1.0, "fallback"

    def _load_current():
        return None

    def update_status(*a, **k):
        return False


DEFAULT_REPORT_PATHS = {
    "jarvis-core": "/tmp/jarvis-claude-out.md",
    "*": "/tmp/claude-out.md",
}


def _looks_secret_like(text: str) -> bool:
    for _name, pattern in SECRET_PATTERNS:
        if pattern.search(text or ""):
            return True
    return False


def _parse_common(argv):
    file_path = None
    force_weak = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--file":
            if i + 1 < len(argv):
                file_path = argv[i + 1]
                i += 2
                continue
        if a.startswith("--file="):
            file_path = a.split("=", 1)[1]
            i += 1
            continue
        if a == "--force-weak":
            force_weak = True
            i += 1
            continue
        i += 1
    return file_path, force_weak


def _detected_headings(text: str):
    found = []
    for h in SECTION_HEADINGS:
        # Cheap heuristic — we don't need the full extract_section logic here.
        if re.search(rf"(?im)^\s*(?:#+\s*)?(?:\d+[\.\)]\s*)?\**\s*{re.escape(h)}\b", text):
            found.append(h)
    return found


def _resolve_project(default_from_arg: str = None) -> str:
    """Project precedence: --project arg > current work session > jarvis-core."""
    if default_from_arg:
        return default_from_arg
    state = _load_current()
    if state and state.get("project"):
        return state["project"]
    return "jarvis-core"


def _expected_path_for(project: str) -> str:
    if project == "jarvis-core" or not project:
        return DEFAULT_REPORT_PATHS["jarvis-core"]
    return DEFAULT_REPORT_PATHS["*"]


# ── template ──────────────────────────────────────────────────────────────────

def cmd_template(argv):
    state = _load_current()
    project = (state or {}).get("project") or "jarvis-core"
    expected = _expected_path_for(project)
    debrief_dry = (
        f"./jarvis self-debrief --from-file {expected} --dry-run"
        if project == "jarvis-core"
        else f"./jarvis project-memory-update --project {project} --from-file {expected} --dry-run"
    )
    debrief_apply = debrief_dry.replace("--dry-run", "--apply")
    print("JARVIS — Report Template")
    print("Status real: apenas template. Nada gravado.")
    print("")
    print(f"current work session: {(state or {}).get('work_id', '(nenhuma)')}")
    print(f"project alvo: {project}")
    print(f"caminho esperado: {expected}")
    print("")
    print("```bash")
    print(f"cat > {expected}")
    print("# (cole o RELATÓRIO FINAL do Claude; Ctrl+D para fechar)")
    print(f"./jarvis report-check --file {expected}")
    print(f"./jarvis report-apply --file {expected}")
    print("# equivalente (manual):")
    print(debrief_dry)
    print(debrief_apply)
    print("```")
    print("")
    print("Produção: nada alterado.")


# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(argv):
    state = _load_current()
    project = (state or {}).get("project") or "jarvis-core"
    expected = (state or {}).get("expected_report_path") or _expected_path_for(project)
    print("JARVIS — Report Status")
    print("Status real: leitura local. Nada editado.")
    print("")
    print(f"work session: {(state or {}).get('work_id', '(nenhuma)')}")
    print(f"project alvo: {project}")
    print(f"caminho esperado: {expected}")
    p = Path(expected)
    if not p.exists():
        print("status: AUSENTE — relatório ainda não salvo")
        print(f"sugestão: ./jarvis report-template  (mostra o cat exato)")
        print("")
        print("Produção: nada alterado.")
        return
    raw = p.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        print("status: VAZIO — arquivo existe mas sem conteúdo")
        print("")
        print("Produção: nada alterado.")
        return
    label, hits, ratio, hint = report_quality(raw)
    print(f"status: {'PRESENTE+PRONTO' if label == 'strong' else 'PRESENTE+FRACO'}")
    print(f"diagnóstico: {hint}")
    print(f"tamanho: {len(raw)} bytes")
    print("")
    if label == "strong":
        print(f"Próximo: ./jarvis report-apply --file {expected}")
    else:
        print(f"Próximo: ./jarvis report-check --file {expected}")
        print(f"        (e/ou refaça o cat com o RELATÓRIO correto)")
    print("")
    print("Produção: nada alterado.")


# ── check ─────────────────────────────────────────────────────────────────────

def cmd_check(argv):
    file_path, _fw = _parse_common(argv)
    print("JARVIS — Report Check")
    print("Status real: leitura local. Nada gravado.")
    print("")
    if not file_path:
        print("FALHA: --file obrigatório.")
        sys.exit(1)
    p = Path(file_path)
    if not p.exists():
        print(f"FALHA: arquivo não encontrado: {file_path}")
        sys.exit(1)
    raw = p.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        print(f"FALHA: arquivo vazio: {file_path}")
        sys.exit(2)
    if _looks_secret_like(raw):
        print(f"FALHA: o arquivo contém padrão secret-like — APLICAR seria perigoso.")
        print("Ação segura: NÃO checamos detalhes. Limpe segredos antes.")
        sys.exit(3)

    label, hits, ratio, hint = report_quality(raw)
    headings = _detected_headings(raw)
    project = _resolve_project()
    apply_cmd = (
        f"./jarvis report-apply --file {file_path}"
    )
    direct_apply = (
        f"./jarvis self-debrief --from-file {file_path} --apply"
        if project == "jarvis-core"
        else f"./jarvis project-memory-update --project {project} --from-file {file_path} --apply"
    )

    print(f"file: {file_path}")
    print(f"size: {len(raw)} bytes")
    print(f"detected headings: {', '.join(headings) if headings else '(nenhuma)'}")
    print(f"quality: {label}  ({hint})")
    print(f"guessed project alvo: {project}")
    print("")
    if label == "strong":
        print("Resultado: READY — pode aplicar.")
        print(f"Aplicar agora:")
        print(f"  {apply_cmd}")
        print(f"Equivalente direto:")
        print(f"  {direct_apply}")
        print("")
        print("Produção: nada alterado (ainda).")
        return
    print("Resultado: WEAK — não aplicar como está.")
    print('Esse arquivo parece conter comandos ou está sem seções (STATUS REAL / VALIDATION RESULTS / FILES CHANGED / SAFE TO COMMIT / ...).')
    print("Causa provável: você salvou os COMANDOS do template no /tmp em vez do RELATÓRIO final.")
    print("Override (perigoso): ./jarvis report-apply --file ... --force-weak")
    print("")
    print("Produção: nada alterado.")
    # NOTE: exit 0 here. The warning IS the value — `report-apply` enforces
    # the refusal with non-zero exit. Keeping check exit=0 lets smoke assert
    # on the warning text without needing expect-nonzero plumbing.


# ── apply ─────────────────────────────────────────────────────────────────────

def cmd_apply(argv):
    file_path, force_weak = _parse_common(argv)
    print("JARVIS — Report Apply")
    print("Status real: roteia para self-debrief / project-memory-update.")
    print("")
    if not file_path:
        print("FALHA: --file obrigatório.")
        sys.exit(1)
    p = Path(file_path)
    if not p.exists():
        print(f"FALHA: arquivo não encontrado: {file_path}")
        sys.exit(1)
    raw = p.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        print(f"FALHA: arquivo vazio: {file_path}")
        sys.exit(2)
    if _looks_secret_like(raw):
        print("FALHA: arquivo parece conter segredo. NÃO aplicamos.")
        sys.exit(3)
    label, hits, ratio, hint = report_quality(raw)
    project = _resolve_project()

    print(f"file: {file_path}")
    print(f"quality: {label}  ({hint})")
    print(f"project alvo: {project}")
    print("")
    if label != "strong" and not force_weak:
        print("FALHA: relatório fraco/comandos-only. Recuso aplicar.")
        print(f"Use --force-weak se for intencional (perigoso).")
        sys.exit(4)

    # Delegate to the existing safe writer.
    if project == "jarvis-core":
        delegate = ["python3", "11_SCRIPTS/project_memory_update.py",
                    "--project", "jarvis-core",
                    "--from-file", str(p), "--apply"]
        if force_weak:
            delegate.append("--force-weak-report")
        # self-debrief is a wrapper over project-memory-update; calling
        # project-memory-update directly avoids an extra subprocess hop.
    else:
        delegate = ["python3", "11_SCRIPTS/project_memory_update.py",
                    "--project", project,
                    "--from-file", str(p), "--apply"]
        if force_weak:
            delegate.append("--force-weak-report")

    print("Delegando para writer seguro:")
    print("  " + " ".join(delegate[1:]))
    print("")
    result = subprocess.run(delegate, cwd=ROOT)
    if result.returncode != 0:
        print("")
        print(f"FALHA: writer retornou {result.returncode}. Memória NÃO atualizada.")
        sys.exit(result.returncode)

    # Advance the work session lifecycle if there is one.
    updated = update_status("debrief_applied", debrief_at=None)
    print("")
    if updated:
        print("OK — work session avançou para status=debrief_applied.")
    print("Próximos gates (Theo executa):")
    print("  env JARVIS_NO_REPORT=1 ./jarvis safety-gate")
    print("  env JARVIS_NO_REPORT=1 ./jarvis smoke-test")
    print("  ./jarvis doctrine-check")
    print("Depois: ./jarvis work-close")
    print("")
    print("Produção: nada alterado em VPS / n8n / produção.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if not argv:
        print("Uso: report_intake.py <template|status|check|apply> [args]")
        sys.exit(1)
    sub = argv[0]
    rest = argv[1:]
    if sub == "template":
        cmd_template(rest)
    elif sub == "status":
        cmd_status(rest)
    elif sub == "check":
        cmd_check(rest)
    elif sub == "apply":
        cmd_apply(rest)
    else:
        print(f"FALHA: subcomando desconhecido: {sub}")
        sys.exit(1)


if __name__ == "__main__":
    main()
