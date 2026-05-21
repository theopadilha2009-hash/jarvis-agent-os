from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "01_SISTEMA" / "00_REGRAS" / "REGRAS_EXECUCAO_FORTE_CREDENCIAIS.md"

def main():
    print("JARVIS — Theo Padilha AI Worker Execution Modes")
    print("")
    print("Status real: modos de execução documentados. Nada executado.")
    print("")
    print("PREPARE")
    print("- Planeja, cria briefing, handoff, prompts, checklist e relatórios.")
    print("- Não altera projeto real.")
    print("")
    print("READONLY")
    print("- Inspeciona arquivos, Git, logs, Docker, n8n, VPS ou projeto.")
    print("- Não altera nada.")
    print("")
    print("LOCAL_EXEC")
    print("- Pode editar projeto local, criar branch, rodar build/teste e preparar commit.")
    print("- Sem push/deploy sem autorização.")
    print("")
    print("INFRA_EXEC")
    print("- Pode operar VPS, Docker, Portainer, Traefik, n8n e serviços reais.")
    print("- Exige escopo explícito e backup/checkpoint antes de ação sensível.")
    print("")
    print("PRODUCTION_ARMED")
    print("- Modo para deploy, push, merge, ativar workflow, enviar mensagem real, alterar banco real, trocar DNS ou rodar migration.")
    print("- Exige autorização explícita.")
    print("")
    print("Regra de credenciais:")
    print("- Credenciais podem ser usadas localmente quando autorizado.")
    print("- Nunca salvar segredo em Git, relatório, prompt externo ou log permanente.")
    print("")
    if RULES.exists():
        print(f"Arquivo de regra: {RULES.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
