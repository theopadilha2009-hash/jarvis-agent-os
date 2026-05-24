from pathlib import Path
from datetime import datetime
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[1]

CHECKS = [
    {
        "name": "help",
        "cmd": ["./jarvis", "help"],
        "expect": ["Comandos:", "./jarvis help"],
    },
    {
        "name": "safety-gate",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "safety-gate"],
        "expect": ["Safety Gate", "SAFETY GATE PASSOU", "Produção não alterada", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "command-audit",
        "cmd": ["./jarvis", "command-audit"],
        "expect": ["Command Audit", "COMMAND AUDIT PASSOU", "Produção não alterada"],
    },
    {
        "name": "secret-scan",
        "cmd": ["./jarvis", "secret-scan"],
        "expect": ["Secret Scan", "SECRET SCAN PASSOU", "Nenhum segredo foi impresso"],
    },
    {
        "name": "storage-health",
        "cmd": ["./jarvis", "storage-health"],
        "expect": ["Storage Health", "STORAGE HEALTH PASSOU", "Produção não alterada"],
    },
    {
        "name": "pending-artifacts",
        "cmd": ["./jarvis", "pending-artifacts"],
        "expect": ["Pending Artifacts", "Status real", "Git status"],
    },
    {
        "name": "report-policy",
        "cmd": ["./jarvis", "report-policy"],
        "expect": ["Report Policy", "ULTIMO_*.md", "Snapshot versionado"],
    },
    {
        "name": "cockpit",
        "cmd": ["./jarvis", "cockpit"],
        "expect": ["JARVIS — Theo Padilha AI Worker Cockpit", "Execution modes", "Próximo passo seguro", "Produção"],
    },
    {
        "name": "visual-cockpit",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "visual-cockpit"],
        "expect": [
            "Visual Cockpit",
            "Gate status (last run)",
            "Latest project lock",
            "Latest LOCAL_EXEC review decision",
            "Must NOT do",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "claude-mission-jarvis-core-audit-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "claude-mission", "--jarvis-core", "--type", "audit", "plan safe next improvement"],
        "expect": [
            "Claude Mission",
            "--jarvis-core",
            "audit",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "claude-mission-latest",
        "cmd": ["./jarvis", "claude-mission-latest"],
        "expect": [
            "Claude Mission Latest",
            "Status real",
        ],
    },
    {
        "name": "operator-workbench-general",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "operator-workbench"],
        "expect": [
            "Operator Workbench",
            "Action menu",
            "Exact commands",
            "When to use Claude",
            "Must NOT do",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "operator-workbench-jarvis-core",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "operator-workbench", "--jarvis-core"],
        "expect": [
            "Operator Workbench",
            "jarvis-core",
            "Claude mission",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "operator-workbench-project-oficina",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "operator-workbench", "--project", "oficina"],
        "expect": [
            "Operator Workbench",
            "oficina",
            "run-safe",
            "project-resolve",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "doctor-project-jarvis-core",
        "cmd": ["./jarvis", "doctor", "--project", "jarvis-core"],
        "expect": [
            "Project Doctor",
            "jarvis-core",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "qa-sprint-jarvis-core-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "qa-sprint", "--project", "jarvis-core"],
        "expect": [
            "Mission Pack",
            "qa-sprint",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "goal-sprint-jarvis-core-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "goal-sprint", "--project", "jarvis-core", "--goal", "plan next safe improvement"],
        "expect": [
            "Mission Pack",
            "goal-sprint",
            "Goal: plan next safe improvement",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "browser-qa-jarvis-core-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "browser-qa", "--project", "jarvis-core"],
        "expect": [
            "Mission Pack",
            "browser-qa",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "final-gate-jarvis-core-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "final-gate", "--project", "jarvis-core"],
        "expect": [
            "Mission Pack",
            "final-gate",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "project-status-jarvis-core",
        "cmd": ["./jarvis", "project-status", "--project", "jarvis-core"],
        "expect": [
            "Project Status",
            "jarvis-core",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "project-cockpit-jarvis-core",
        "cmd": ["./jarvis", "project-cockpit", "--project", "jarvis-core"],
        "expect": [
            "Project Status",
            "Próximo passo seguro",
            "Estado registrado",
            "Próximas ações",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "mission-open-latest-default",
        "cmd": ["./jarvis", "mission-open-latest"],
        "expect": [
            "05_EXECUCAO/21_CLAUDE_MISSIONS/",
            "01_CLAUDE_PROMPT.md",
        ],
    },
    {
        "name": "mission-open-latest-jarvis-core",
        "cmd": ["./jarvis", "mission-open-latest", "--project", "jarvis-core"],
        "expect": [
            "05_EXECUCAO/21_CLAUDE_MISSIONS/",
            "_project-jarvis-core_",
            "01_CLAUDE_PROMPT.md",
        ],
    },
    {
        "name": "project-memory-jarvis-core",
        "cmd": ["./jarvis", "project-memory", "--project", "jarvis-core"],
        "expect": [
            "Project Memory",
            "alias: jarvis-core",
            "Próxima ação sugerida",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "project-memory-oficina",
        "cmd": ["./jarvis", "project-memory", "--project", "oficina"],
        "expect": [
            "Project Memory",
            "alias: oficina",
            "Próxima ação sugerida",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "project-memory-update-jarvis-core-dry-run",
        "cmd": ["./jarvis", "project-memory-update", "--project", "jarvis-core", "--from-git", "--dry-run"],
        "expect": [
            "Project Memory Update",
            "PREVIEW DA ENTRADA",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "project-memory-update-from-file-fixture",
        "cmd": ["./jarvis", "project-memory-update", "--project", "jarvis-core",
                "--from-file", "10_TESTES/FIXTURES/claude_report_sample.md", "--dry-run"],
        "expect": [
            "Project Memory Update",
            "safe to commit (parsed): yes",
            "STATUS REAL",
            "FILES CHANGED",
            "VALIDATION RESULTS",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "self-status",
        "cmd": ["./jarvis", "self-status"],
        "expect": [
            "Self Status",
            "branch:",
            "Próximo passo seguro",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "self-cockpit",
        "cmd": ["./jarvis", "self-cockpit"],
        "expect": [
            "Self Cockpit",
            "Última missão JARVIS",
            "Memória registrada",
            "Gates sugeridos",
            "Próximo passo seguro",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "self-next",
        "cmd": ["./jarvis", "self-next"],
        "expect": [
            "Self Next",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "self-evolve-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "self-evolve",
                "--goal", "test self-evolution mission preview"],
        "expect": [
            "Mission Pack",
            "self-evolve",
            "JARVIS SELF-EVOLVE",
            "TRUE NORTH",
            "HARD RULES",
            "Relatório: desativado por JARVIS_NO_REPORT=1",
        ],
    },
    {
        "name": "claude-launch-print-only-jarvis-core",
        "cmd": ["./jarvis", "claude-launch", "--project", "jarvis-core", "--print-only"],
        "expect": [
            "Claude Launch",
            "cd /Users",
            "claude",
            "cat > /tmp/jarvis-claude-out.md",
            "self-debrief",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "claude-save-report-template-default",
        "cmd": ["./jarvis", "claude-save-report-template"],
        "expect": [
            "Save-Report Template",
            "cat > /tmp/jarvis-claude-out.md",
            "self-debrief",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "doctrine-check",
        "cmd": ["./jarvis", "doctrine-check"],
        "expect": [
            "Doctrine Check",
            "AGENTS.md: OK",
            "COMMAND_CATALOG.md: OK",
            "./jarvis help: OK",
            "PROJECT_REGISTRY.json: OK",
            "DOCTRINE CHECK PASSOU",
        ],
    },
    {
        "name": "ask-next-action",
        "cmd": ["./jarvis", "ask", "o que faço agora"],
        "expect": [
            "Ask Router",
            "intent: next_action",
            "Próximo comando:",
            "./jarvis self-cockpit",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "ask-self-evolve-dry-run",
        "cmd": ["./jarvis", "ask", "evolui o jarvis para reduzir trabalho manual", "--dry-run"],
        "expect": [
            "Ask Router",
            "intent: self_evolve",
            "project: jarvis-core",
            "./jarvis self-evolve --goal",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "ask-project-fix-dry-run",
        "cmd": ["./jarvis", "ask", "abre oficina e corrige bug da agenda", "--dry-run"],
        "expect": [
            "Ask Router",
            "intent: project_fix",
            "project: oficina",
            "./jarvis goal-sprint --project oficina",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "ask-n8n-blueprint-dry-run",
        "cmd": ["./jarvis", "ask", "quero criar workflow n8n de agendamento whatsapp", "--dry-run"],
        "expect": [
            "Ask Router",
            "intent: n8n_blueprint",
            "./jarvis blueprint --type n8n",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "ask-agenda-dry-run",
        "cmd": ["./jarvis", "ask", "coloca amanhã revisar LS na agenda", "--dry-run"],
        "expect": [
            "Ask Router",
            "intent: agenda_note",
            "./jarvis agenda-add",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "go-dry-run-banner",
        "cmd": ["./jarvis", "go", "evoluir o jarvis para virar minha ferramenta principal", "--dry-run"],
        "expect": [
            "Go (power-wrapper de ask)",
            "Ask Router",
            "intent: self_evolve",
            "Próximo passo manual",
            "self-debrief --from-file /tmp/jarvis-claude-out.md",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "capture-dry-run",
        "cmd": ["./jarvis", "capture", "ideia: criar workflow n8n para leads", "--dry-run"],
        "expect": [
            "Local Capture",
            "30_INBOX/INBOX.md",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "inbox-read",
        "cmd": ["./jarvis", "inbox"],
        "expect": [
            "Local Inbox",
            "30_INBOX/INBOX.md",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "agenda-add-dry-run",
        "cmd": ["./jarvis", "agenda-add", "amanhã revisar LS", "--dry-run"],
        "expect": [
            "Agenda Add",
            "31_AGENDA/AGENDA.md",
            "data inferida:",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "agenda-read",
        "cmd": ["./jarvis", "agenda"],
        "expect": [
            "Agenda (local)",
            "31_AGENDA/AGENDA.md",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "blueprint-n8n-dry-run",
        "cmd": ["./jarvis", "blueprint", "--type", "n8n", "--goal", "workflow de agendamento whatsapp", "--dry-run"],
        "expect": [
            "Blueprint",
            "Tipo: n8n",
            "40_BLUEPRINTS/",
            "01_REQUEST.md",
            "03_CLAUDE_PROMPT.md",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "blueprint-research-dry-run",
        "cmd": ["./jarvis", "blueprint", "--type", "research", "--goal", "comparar opções de inbox local", "--dry-run"],
        "expect": [
            "Blueprint",
            "Tipo: research",
            "40_BLUEPRINTS/",
            "04_VALIDATION_CHECKLIST.md",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "self-debrief-weak-report-dry-run-warns",
        "cmd": ["./jarvis", "self-debrief", "--from-file",
                "10_TESTES/FIXTURES/bad_claude_report_commands_only.md", "--dry-run"],
        "expect": [
            "Project Memory Update",
            "ALERTA",
            "NÃO ser um relatório final",
            "STATUS REAL",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "project-open-jarvis-core-print-only",
        "cmd": ["./jarvis", "project-open", "--project", "jarvis-core", "--print-only"],
        "expect": [
            "Project Open",
            "Project: jarvis-core",
            "cd /Users",
            "claude",
            "git status --short",
            "project-cockpit --project jarvis-core",
            "--print-only",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "project-open-oficina-print-only",
        "cmd": ["./jarvis", "project-open", "--project", "oficina", "--print-only"],
        "expect": [
            "Project Open",
            "Project: oficina",
            "cd /Users/usuario1/VAMOO_PROJETOS/oficina",
            "claude",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "plan-project-fix",
        "cmd": ["./jarvis", "plan", "arrumar bug da agenda no oficina sem produção"],
        "expect": [
            "Plan Request",
            "intent: project_fix",
            "project: oficina",
            "Próximo comando seguro",
            "./jarvis goal-sprint --project oficina",
            "Missão Claude sugerida",
            "tipo: goal-sprint",
            "Validação esperada",
            "O que JARVIS NÃO vai fazer",
            "preview (default)",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "plan-self-evolve",
        "cmd": ["./jarvis", "plan", "evoluir o jarvis para reduzir pergunta"],
        "expect": [
            "Plan Request",
            "intent: self_evolve",
            "project: jarvis-core",
            "tipo: self-evolve",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "limits",
        "cmd": ["./jarvis", "limits"],
        "expect": [
            "Robot Limits",
            "O que JARVIS PODE fazer agora",
            "O que JARVIS AINDA NÃO faz",
            "O que requer Claude",
            "O que requer aprovação humana",
            "O que é PROIBIDO",
            "AGENTS.md",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "ask-unclear-routes-to-self-cockpit",
        "cmd": ["./jarvis", "ask", "asdf tarefa estranha sem padrão", "--dry-run", "--no-log"],
        "expect": [
            "Ask Router",
            "intent: unclear",
            "./jarvis self-cockpit",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "ask-log",
        "cmd": ["./jarvis", "ask-log"],
        "expect": [
            "Ask Log",
            "32_ASK_LEARNING/UNCLEAR_REQUESTS.md",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "ask-abre-routes-to-project-open",
        "cmd": ["./jarvis", "ask", "abre oficina", "--dry-run"],
        "expect": [
            "Ask Router",
            "intent: open_project",
            "project: oficina",
            "./jarvis project-open --project oficina --print-only",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "ask-capacidade-routes-to-capability-check",
        "cmd": ["./jarvis", "ask", "capacidade google calendar", "--dry-run"],
        "expect": [
            "Ask Router",
            "intent: capability_check",
            "./jarvis capability-check google_calendar",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "ask-limits-routes-to-limits",
        "cmd": ["./jarvis", "ask", "quais limites", "--dry-run"],
        "expect": [
            "Ask Router",
            "intent: limits",
            "./jarvis limits",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "task-add-dry-run",
        "cmd": ["./jarvis", "task-add", "teste de tarefa local", "--dry-run"],
        "expect": [
            "Task Add",
            "34_TASKS/tasks.jsonl",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "task-list",
        "cmd": ["./jarvis", "task-list"],
        "expect": [
            "Task List",
            "34_TASKS/tasks.jsonl",
            "pending:",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "task-next",
        "cmd": ["./jarvis", "task-next"],
        "expect": [
            "Task Next",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "run-list",
        "cmd": ["./jarvis", "run-list"],
        "expect": [
            "Run List",
            "35_RUNS",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "run-latest-or-empty",
        "cmd": ["./jarvis", "run-list"],
        "expect": [
            "Run List",
            "runs:",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "capabilities-list",
        "cmd": ["./jarvis", "capabilities"],
        "expect": [
            "Capabilities",
            "## available",
            "## manual",
            "## blocked",
            "## future_adapter",
            "local_files_read",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "capability-check-google-calendar",
        "cmd": ["./jarvis", "capability-check", "google_calendar"],
        "expect": [
            "Capability Check",
            "name: google_calendar",
            "group: future_adapter",
            "FUTURE_ADAPTER",
            "local_alternative",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "capability-check-paid-llm-api-blocked",
        "cmd": ["./jarvis", "capability-check", "paid_llm_api"],
        "expect": [
            "Capability Check",
            "group: blocked",
            "BLOQUEADO",
            "why_blocked",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "capability-check-claude-code-manual",
        "cmd": ["./jarvis", "capability-check", "claude_code_manual"],
        "expect": [
            "Capability Check",
            "group: manual",
            "MANUAL",
            "Theo abre",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "capability-plan-google-calendar",
        "cmd": ["./jarvis", "capability-plan", "google_calendar"],
        "expect": [
            "Capability Plan",
            "google_calendar",
            "Aprovação humana necessária",
            "Credenciais necessárias",
            "Testes de segurança",
            "Níveis de status",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "project-intel-jarvis-core",
        "cmd": ["./jarvis", "project-intel", "--project", "jarvis-core"],
        "expect": [
            "Project Intel",
            "alias: jarvis-core",
            "## Package manager",
            "## Framework hints",
            ".env risk",
            "Comandos recomendados",
            "Próxima ação segura",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "project-intel-oficina",
        "cmd": ["./jarvis", "project-intel", "--project", "oficina"],
        "expect": [
            "Project Intel",
            "alias: oficina",
            "## Package manager",
            "bun",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "go-dry-run-banner-with-run-suppression",
        "cmd": ["./jarvis", "go", "abre oficina", "--dry-run"],
        "expect": [
            "Go (power-wrapper de ask)",
            "intent: open_project",
            "project: oficina",
            "Run package",
            "suprimido",
            "Project intel sugerido",
            "./jarvis project-intel --project oficina",
            "project-memory-update --project oficina",
            "Gates de saúde",
            "safety-gate",
            "smoke-test",
            "doctrine-check",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "go-capability-routes",
        "cmd": ["./jarvis", "go", "capacidade google calendar", "--dry-run"],
        "expect": [
            "Go (power-wrapper de ask)",
            "intent: capability_check",
            "./jarvis capability-check google_calendar",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "blueprint-app-dry-run",
        "cmd": ["./jarvis", "blueprint", "--type", "app", "--goal", "app simples para vender automações", "--dry-run"],
        "expect": [
            "Blueprint",
            "Tipo: app",
            "40_BLUEPRINTS/",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "blueprint-automation-dry-run",
        "cmd": ["./jarvis", "blueprint", "--type", "automation", "--goal", "capturar leads e gerar relatório", "--dry-run"],
        "expect": [
            "Blueprint",
            "Tipo: automation",
            "40_BLUEPRINTS/",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "commands",
        "cmd": ["./jarvis", "commands"],
        "expect": ["Command Catalog", "auto-task", "quality-gate"],
    },
    {
        "name": "execution-modes",
        "cmd": ["./jarvis", "execution-modes"],
        "expect": ["PREPARE", "READONLY", "LOCAL_EXEC", "INFRA_EXEC", "PRODUCTION_ARMED"],
    },
    {
        "name": "overview",
        "cmd": ["./jarvis", "overview"],
        "expect": ["System Overview", "Status real", "Produção"],
    },
    {
        "name": "task-status",
        "cmd": ["./jarvis", "task-status"],
        "expect": ["Task Status", "Git status", "Próximo passo seguro"],
    },
    {
        "name": "self-test",
        "cmd": ["./jarvis", "self-test"],
        "expect": ["SELF-TEST PASSOU", "Status real"],
    },
    {
        "name": "quality-gate",
        "cmd": ["./jarvis", "quality-gate"],
        "expect": ["QUALITY GATE", "Python compile", "Git status"],
    },
    {
        "name": "run-safe-project-lock-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "run-safe", "--project", "oficina", "revisar tarefa segura sem deploy"],
        "expect": ["RUN SAFE", "Project lock: oficina", "LOCAL EXEC SESSION", "Resultado: RUN SAFE PASSOU"],
    },
    {
        "name": "future-tools-radar",
        "cmd": ["./jarvis", "future-tools-radar"],
        "expect": ["Future Tools Radar", "Nada foi instalado", "Produção"],
    },
    {
        "name": "next-step",
        "cmd": ["./jarvis", "next-step"],
        "expect": ["Next Step", "Opções agora", "project-menu"],
    },
    {
        "name": "next-step-oficina",
        "cmd": ["./jarvis", "next-step", "oficina"],
        "expect": ["Next Step", "Projeto selecionado: oficina", "local-exec-session --project oficina"],
    },
    {
        "name": "project-menu-list",
        "cmd": ["./jarvis", "project-menu"],
        "expect": ["Project Menu", "Projetos disponíveis", "Opções"],
    },
    {
        "name": "project-menu-oficina",
        "cmd": ["./jarvis", "project-menu", "oficina"],
        "expect": ["Project Menu", "Ações recomendadas", "local-exec-session --project oficina"],
    },
    {
        "name": "project-resolve-list",
        "cmd": ["./jarvis", "project-resolve"],
        "expect": ["Project Resolve", "Projetos disponíveis", "oficina"],
    },
    {
        "name": "project-resolve-oficina",
        "cmd": ["./jarvis", "project-resolve", "oficina"],
        "expect": ["PROJECT RESOLVE PASSOU", "LOCAL_EXEC permitido", "local-exec-session --project oficina"],
    },
    {
        "name": "project-select",
        "cmd": ["./jarvis", "project-select", "corrigir bug de visitantes do GC"],
        "expect": ["Project Select", "Projeto sugerido", "Próximo passo seguro"],
    },
    {
        "name": "local-exec-handoff-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-handoff", "corrigir bug local no projeto oficina sem deploy"],
        "expect": ["LOCAL_EXEC Handoff", "Projeto selecionado", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-ready-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-ready", "corrigir bug local no projeto oficina sem deploy"],
        "expect": ["LOCAL_EXEC Ready Check", "Projeto selecionado", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-plan-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-plan", "corrigir bug local no projeto oficina sem deploy"],
        "expect": ["LOCAL_EXEC Plan", "Nenhum arquivo do projeto foi alterado", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "readonly-run-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "readonly-run", "investigar bug no projeto GC sem alterar produção"],
        "expect": ["READONLY RUN", "inspeção local read-only", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-flow-latest",
        "cmd": ["./jarvis", "local-exec-flow-latest"],
        "expect": ["Latest LOCAL_EXEC Flow", "LOCAL_EXEC Flow", "Fluxo seguro"],
    },
    {
        "name": "local-exec-session-latest",
        "cmd": ["./jarvis", "local-exec-session-latest"],
        "expect": ["Latest LOCAL_EXEC Session", "LOCAL_EXEC Session", "Artefatos gerados"],
    },
    {
        "name": "local-exec-session-project-lock-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-session", "--project", "oficina", "corrigir bug local sem deploy"],
        "expect": ["LOCAL_EXEC Session", "Project lock: oficina", "Projeto selecionado: oficina", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-session-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-session", "corrigir bug local no projeto oficina sem deploy"],
        "expect": ["LOCAL_EXEC Session", "sessão de preparação local", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-flow-no-report",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-flow", "corrigir bug local no projeto oficina sem deploy"],
        "expect": ["LOCAL_EXEC Flow", "Fluxo seguro", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-review-latest",
        "cmd": ["./jarvis", "local-exec-review-latest"],
        "expect": ["Latest LOCAL_EXEC Review", "LOCAL_EXEC Review", "Decisão"],
    },
    {
        "name": "local-exec-review-fixtures",
        "cmd": ["./jarvis", "local-exec-review", "--fixtures"],
        "expect": ["LOCAL_EXEC Review", "Fixtures LOCAL_EXEC"],
    },
    {
        "name": "local-exec-review-fixture-safe",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-review", "10_TESTES/FIXTURES/local_exec_output_safe_sample.md"],
        "expect": ["LOCAL_EXEC Review", "[PODE SEGUIR COM REVISÃO]", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-review-fixture-risky",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-review", "10_TESTES/FIXTURES/local_exec_output_risky_sample.md"],
        "expect": ["LOCAL_EXEC Review", "[PARAR E REVISAR COM HUMANO]", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-review-fixture-mixed",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-review", "10_TESTES/FIXTURES/local_exec_output_mixed_sample.md"],
        "expect": ["LOCAL_EXEC Review", "[PARAR E REVISAR COM HUMANO]", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-review-fixture-codefence",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-review", "10_TESTES/FIXTURES/local_exec_output_codefence_sample.md"],
        "expect": ["LOCAL_EXEC Review", "[PARAR E REVISAR COM HUMANO]", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-review-fixture-negated-only",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "local-exec-review", "10_TESTES/FIXTURES/local_exec_output_negated_only_sample.md"],
        "expect": ["LOCAL_EXEC Review", "[PODE SEGUIR COM REVISÃO]", "Relatório: desativado por JARVIS_NO_REPORT=1"],
    },
    {
        "name": "local-exec-handoff-latest",
        "cmd": ["./jarvis", "local-exec-handoff-latest"],
        "expect": ["Latest LOCAL_EXEC Handoff", "Arquivo principal", "LOCAL_EXEC"],
    },
    {
        "name": "local-exec-ready-latest",
        "cmd": ["./jarvis", "local-exec-ready-latest"],
        "expect": ["Latest LOCAL_EXEC Ready Check", "LOCAL_EXEC Ready Check", "Status real"],
    },
    {
        "name": "local-exec-plan-latest",
        "cmd": ["./jarvis", "local-exec-plan-latest"],
        "expect": ["Latest LOCAL_EXEC Plan", "LOCAL_EXEC Plan", "Status real"],
    },
    {
        "name": "readonly-run-latest",
        "cmd": ["./jarvis", "readonly-run-latest"],
        "expect": ["Latest READONLY RUN", "READONLY RUN", "Status real"],
    },
    {
        "name": "task-brief-latest",
        "cmd": ["./jarvis", "task-brief-latest"],
        "expect": ["Latest Task Brief", "Status real", "Próximo passo seguro"],
    },
    {
        "name": "auto-task-latest",
        "cmd": ["./jarvis", "auto-task-latest"],
        "expect": ["Latest Auto Task", "Auto Task Run", "Nada executado no projeto real"],
    },
    {
        "name": "review-output-index",
        "cmd": ["./jarvis", "review-output-index"],
        "expect": ["Executor Output Index", "Reviews indexados", "Relatório"],
    },
    {
        "name": "review-output-latest",
        "cmd": ["./jarvis", "review-output-latest"],
        "expect": ["Latest Executor Output Review", "Executor Output Review", "Status real"],
    },
    {
        "name": "handoff-latest",
        "cmd": ["./jarvis", "handoff-latest"],
        "expect": ["Latest Handoff", "Arquivo principal para Claude"],
    },
    {
        "name": "handoff-print",
        "cmd": ["./jarvis", "handoff-print"],
        "expect": ["Handoff Print", "Prompt para Claude", "Regras obrigatórias"],
    },
]

def run(cmd):
    try:
        output = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
        return 0, output.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output.strip()
    except Exception as e:
        return 1, f"ERRO: {e}"

def main():
    print("JARVIS — Theo Padilha AI Worker CLI Smoke Test")
    print("Modo: exit code + conteúdo esperado")
    print("")

    results = []

    for check in CHECKS:
        code, output = run(check["cmd"])
        missing = [x for x in check["expect"] if x not in output]
        ok = code == 0 and not missing

        results.append({
            "name": check["name"],
            "cmd": check["cmd"],
            "ok": ok,
            "code": code,
            "missing": missing,
            "output": output,
        })

        if ok:
            print(f"OK  {' '.join(check['cmd'])}")
        else:
            print(f"FALHA  {' '.join(check['cmd'])}")
            if code != 0:
                print(f"  exit code: {code}")
            if missing:
                print(f"  conteúdo ausente: {', '.join(missing)}")

    passed = all(r["ok"] for r in results)

    out_dir = ROOT / "10_TESTES" / "SMOKE_TESTS"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    report = out_dir / f"{ts}_cli-smoke-test.md"

    lines = [
        "# CLI Smoke Test — JARVIS Theo Padilha AI Worker",
        "",
        f"## Data\n{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Resultado\n{'PASSOU' if passed else 'FALHOU'}",
        "",
        "## Status real",
        "Teste local de CLI. Nada de produção.",
        "",
    ]

    for r in results:
        lines += [
            f"## {r['name']}",
            f"Comando: `{' '.join(r['cmd'])}`",
            f"Status: {'OK' if r['ok'] else 'FALHA'}",
            f"Exit code: {r['code']}",
            f"Conteúdo ausente: {', '.join(r['missing']) if r['missing'] else 'nenhum'}",
            "",
            "```text",
            r["output"][-4000:],
            "```",
            "",
        ]

    no_report = os.environ.get("JARVIS_NO_REPORT") == "1"

    print("")
    print(f"Resultado: {'CLI SMOKE TEST PASSOU' if passed else 'CLI SMOKE TEST FALHOU'}")

    if no_report:
        print("Relatório: desativado por JARVIS_NO_REPORT=1")
    else:
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Relatório: {report.relative_to(ROOT)}")

    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
