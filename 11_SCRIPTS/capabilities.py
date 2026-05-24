"""
capabilities.py — JARVIS capability registry reader.

Reads 01_SISTEMA/06_CAPABILITIES/CAPABILITY_REGISTRY.json and prints:
  list                      summary by group (default)
  check NAME                detail + safe behavior + setup needed (if any)
  plan NAME                 local plan for a future_adapter capability

Read-only. No API calls. No installs. Stdlib only.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "01_SISTEMA" / "06_CAPABILITIES" / "CAPABILITY_REGISTRY.json"


def _load():
    if not REGISTRY.exists():
        print(f"FALHA: registry ausente: {REGISTRY.relative_to(ROOT)}")
        sys.exit(1)
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"FALHA: registry JSON inválido: {e}")
        sys.exit(1)


def _find_capability(data, name):
    name = (name or "").strip().lower()
    for group, payload in data.get("groups", {}).items():
        for cap in payload.get("capabilities", []):
            if cap.get("name", "").lower() == name:
                return group, cap
    return None, None


# ── list ──────────────────────────────────────────────────────────────────────

def cmd_list(argv):
    data = _load()
    print("JARVIS — Capabilities")
    print(f"Status real: {data.get('status_real', 'leitura local')}")
    print("")
    print(f"registry: {REGISTRY.relative_to(ROOT)}")
    print(f"updated:  {data.get('updated_at', '?')}")
    print("")
    for group, payload in data.get("groups", {}).items():
        caps = payload.get("capabilities", [])
        print(f"## {group}  ({len(caps)})")
        print(f"  {payload.get('summary', '')}")
        for c in caps:
            print(f"  - {c.get('name')}: {c.get('what', '')}")
        print("")
    print("Use:")
    print("  ./jarvis capability-check <NAME>")
    print("  ./jarvis capability-plan  <NAME>   (apenas para grupo future_adapter)")
    print("Produção: nada alterado.")


# ── check ─────────────────────────────────────────────────────────────────────

def cmd_check(argv):
    if not argv:
        print("Uso: ./jarvis capability-check <NAME>")
        sys.exit(1)
    name = argv[0]
    data = _load()
    group, cap = _find_capability(data, name)
    print("JARVIS — Capability Check")
    print("Status real: leitura local. Nada foi editado.")
    print("")
    if not cap:
        print(f"FALHA: capability desconhecida: {name}")
        print("Liste todas com: ./jarvis capabilities")
        sys.exit(1)
    print(f"name: {cap.get('name')}")
    print(f"group: {group}")
    print(f"what: {cap.get('what', '')}")
    print("")
    if group == "available":
        print(f"status: DISPONÍVEL — JARVIS pode executar local agora")
        print(f"safe_now: {cap.get('safe_now', '')}")
        if cap.get("notes"):
            print(f"notes: {cap['notes']}")
    elif group == "manual":
        print(f"status: MANUAL — JARVIS prepara, Theo executa")
        print(f"safe_now: {cap.get('safe_now', '')}")
        if cap.get("notes"):
            print(f"notes: {cap['notes']}")
    elif group == "blocked":
        print(f"status: BLOQUEADO (hard rule) — JARVIS NUNCA faz isto")
        print(f"why_blocked: {cap.get('why_blocked', '')}")
    elif group == "future_adapter":
        print(f"status: FUTURE_ADAPTER — possível um dia; hoje só alternativa local")
        if cap.get("local_alternative"):
            print(f"local_alternative: {cap['local_alternative']}")
        print(f"setup_needed:")
        for s in cap.get("setup_needed", []):
            print(f"  - {s}")
        print(f"comportamento seguro atual: usar a alternativa local; NÃO há adapter ativo.")
        print(f"plano detalhado: ./jarvis capability-plan {cap.get('name')}")
    print("")
    print("Produção: nada alterado.")


# ── plan ──────────────────────────────────────────────────────────────────────

def cmd_plan(argv):
    if not argv:
        print("Uso: ./jarvis capability-plan <NAME>")
        sys.exit(1)
    name = argv[0]
    data = _load()
    group, cap = _find_capability(data, name)
    print("JARVIS — Capability Plan")
    print("Status real: plano local APENAS. Nenhum adapter criado, nenhuma API chamada.")
    print("")
    if not cap:
        print(f"FALHA: capability desconhecida: {name}")
        sys.exit(1)
    if group != "future_adapter":
        print(f"AVISO: '{name}' está no grupo '{group}', não 'future_adapter'.")
        print("Capability-plan só faz sentido para itens do grupo future_adapter.")
        print(f"Use: ./jarvis capability-check {name}")
        sys.exit(2)
    print(f"name: {cap.get('name')}")
    print(f"what: {cap.get('what')}")
    print(f"local_alternative: {cap.get('local_alternative', '(?)')}")
    print("")
    print("## Aprovação humana necessária")
    print("- Theo precisa autorizar explicitamente cada passo.")
    print("- Sem aprovação por escrito, JARVIS NÃO executa nada.")
    print("")
    print("## Credenciais necessárias")
    for s in cap.get("setup_needed", []):
        print(f"- {s}")
    print("")
    print("## Testes de segurança antes de habilitar")
    print("- adapter em modo dry-run primeiro (sem efeitos reais)")
    print("- escopo mínimo (read-only quando possível)")
    print("- timeout curto e rate-limit local")
    print("- nenhum segredo em arquivo versionado")
    print("- nenhum payload com PII sem mascaramento")
    print("")
    print("## Níveis de status (subir um por vez)")
    print("1. drafted — plano escrito; nada de código")
    print("2. adapter local — implementado mas SEM credencial real")
    print("3. dry-run validado — adapter responde sem efeito externo")
    print("4. read-only sandbox — credencial em ambiente de teste; só leitura")
    print("5. read-only prod — credencial prod com escopo mínimo de leitura")
    print("6. write sandbox — efeitos só em ambiente de teste, com ack humano")
    print("7. write prod — apenas após Theo dar OK por escrito; cada call audita.")
    print("")
    print("## O que JARVIS NÃO fará")
    print("- não chamar API paga sem flag explícita")
    print("- não armazenar segredo em texto claro")
    print("- não fazer efeito externo sem dry-run + ack humano")
    print("- não criar adapter sem entrada em CAPABILITY_REGISTRY.json")
    print("")
    print("Produção: nada alterado. Apenas plano local.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if not argv:
        cmd_list([])
        return
    sub = argv[0]
    rest = argv[1:]
    if sub == "list":
        cmd_list(rest)
    elif sub == "check":
        cmd_check(rest)
    elif sub == "plan":
        cmd_plan(rest)
    else:
        # Allow direct usage: capabilities.py NAME -> treat as 'list'.
        cmd_list([])


if __name__ == "__main__":
    main()
