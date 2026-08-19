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
        "expect": ["interface principal", "./jarvis do", "./jarvis help --all"],
    },
    {
        "name": "agent-eval",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "agent-eval"],
        "expect": ["Agent Runtime Eval", "50/50", "Produção: nada alterado"],
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
        "expect": [],
        "expect_codes": [0, 1],
    },
    {
        "name": "mission-open-latest-jarvis-core",
        "cmd": ["./jarvis", "mission-open-latest", "--project", "jarvis-core"],
        "expect": [],
        "expect_codes": [0, 1],
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
        "name": "decision-add-dry-run",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "decision-add", "usar log append-only", "--project", "jarvis-core", "--reason", "manter contexto auditável", "--dry-run"],
        "expect": [
            "Decision Add",
            "63_DECISIONS/decisions.jsonl",
            "Modo: PREVIEW",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "decision-list",
        "cmd": ["./jarvis", "decision-list", "--limit", "3"],
        "expect": [
            "Decision Log",
            "decisões exibidas:",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "decision-show-latest-or-empty",
        "cmd": ["./jarvis", "decision-show", "latest"],
        "expect": [
            "Decision Show",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "assistant-doctor",
        "cmd": ["./jarvis", "assistant-doctor"],
        "expect": ["Assistant Doctor", "captura de tela", "somente message-send envia", "Produção: nada alterado"],
    },
    {
        "name": "web-check",
        "cmd": ["./jarvis", "web", "--check"],
        "expect": ["JARVIS Web Check", "componentes presentes", "Produção: nada alterado"],
    },
    {
        "name": "screen-capture-dry-run",
        "cmd": ["./jarvis", "screen-capture", "--dry-run"],
        "expect": ["Screen Capture", "Modo: --dry-run", "nenhuma captura realizada", "Produção: nada alterado"],
    },
    {
        "name": "screen-record-dry-run",
        "cmd": ["./jarvis", "screen-record", "--dry-run"],
        "expect": ["Screen Recorder", "Status real:", "--dry-run", "Produção: nada alterado"],
    },
    {
        "name": "github-overview-dry-run",
        "cmd": ["./jarvis", "github-overview", "--dry-run"],
        "expect": ["GitHub Overview", "Status real:", "--dry-run", "Produção: nada alterado"],
    },
    {
        "name": "image-to-pdf-dry-run",
        "cmd": ["./jarvis", "image-to-pdf", "10_TESTES/FIXTURES/personal-tools-sample.svg", "--dry-run"],
        "expect": ["Image to PDF", "geração de PDF bloqueada", "nenhum PDF criado", "Produção: nada alterado"],
    },
    {
        "name": "image-convert-dry-run",
        "cmd": ["./jarvis", "image-convert", "10_TESTES/FIXTURES/personal-tools-sample.svg", "--to", "png", "--dry-run"],
        "expect": ["Image Convert", "original preservado", "nenhuma imagem criada", "Produção: nada alterado"],
    },
    {
        "name": "speak-dry-run",
        "cmd": ["./jarvis", "speak", "teste de voz local", "--dry-run"],
        "expect": ["JARVIS — Speak", "síntese local", "nenhum áudio", "Produção: nada alterado"],
    },
    {
        "name": "message-draft-dry-run",
        "cmd": ["./jarvis", "message-draft", "--phone", "5511999999999", "mensagem de teste", "--dry-run"],
        "expect": ["Message Draft", "nunca envia", "nada aberto ou copiado", "Produção: nada alterado"],
    },
    {
        "name": "message-send-dry-run",
        "cmd": ["./jarvis", "message-send", "--phone", "5511999999999", "mensagem de teste", "--dry-run"],
        "expect": ["Message Send", "envio explícito", "nenhuma mensagem enviada", "Produção: nada alterado"],
    },
    {
        "name": "memory-save-dry-run",
        "cmd": ["./jarvis", "memory-save", "Theo prefere respostas diretas", "--kind", "preference", "--dry-run"],
        "expect": ["Memory Save", "memória operacional", "nenhuma memória gravada", "Produção: nada alterado"],
    },
    {
        "name": "storage-scan-read-only",
        "cmd": ["./jarvis", "storage-scan", ".", "--top", "3", "--min-mb", "999999"],
        "expect": ["Storage Scan", "somente metadados", "Nenhuma limpeza foi executada", "Produção: nada alterado"],
    },
    {
        "name": "system-memory-dry-run",
        "cmd": ["./jarvis", "system-memory", "--cleanup-jarvis", "--dry-run"],
        "expect": ["System Memory", "Temporários controláveis", "nenhum processo encerrado", "processos pessoais foram preservados", "Produção: nada alterado"],
    },
    {
        "name": "spotify-dry-run",
        "cmd": ["./jarvis", "spotify", "next", "--dry-run"],
        "expect": ["JARVIS — Spotify", "Status real:", "--dry-run", "Spotify não alterado", "Produção: nada alterado"],
    },
    {
        "name": "computer-worker-dry-run",
        "cmd": ["./jarvis", "computer-worker", "--once", "--dry-run"],
        "expect": ["Device Worker", "ponte local allowlisted", "nenhum heartbeat ou comando foi gravado", "Produção: nenhum deploy alterado"],
    },
    {
        "name": "self-edit-dry-run",
        "cmd": ["./jarvis", "self-edit", "melhorar os próprios scripts com evidência", "--dry-run"],
        "expect": [
            "JARVIS Self Edit",
            "Status real:",
            "Codex CLI:",
            "Modo preview",
            "Duração total:",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "self-edit-publish-dry-run",
        "cmd": [
            "./jarvis",
            "self-edit",
            "criar diagnóstico no jarvis e fazer deploy",
            "--publish",
            "--dry-run",
        ],
        "expect": [
            "JARVIS Self Edit",
            "GitHub main + Vercel production autorizados",
            "theopadilha2009-hash/jarvis-agent-os",
            "jarvis-theo.vercel.app",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "promote-production-dry-run",
        "cmd": ["env", "JARVIS_NO_REPORT=1", "./jarvis", "promote-production", "--dry-run"],
        "expect": [
            "Promote Production",
            "jarvis-theo.vercel.app",
            "jarvis-agent-os",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "files-triage-read-only",
        "cmd": ["./jarvis", "files-triage", "10_TESTES/FIXTURES", "--limit", "10"],
        "expect": ["Files Triage", "plano read-only", "não possui --apply", "Produção: nada alterado"],
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
        "name": "resume-no-session",
        "cmd": ["./jarvis", "resume"],
        "expect": [
            "JARVIS — Resume",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "work-status-no-session-or-summary",
        "cmd": ["./jarvis", "work-status"],
        "expect": [
            "Work Status",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "work-next-no-session-or-summary",
        "cmd": ["./jarvis", "work-next"],
        "expect": [
            "Work Next",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "work-start-self-evolve-dry-run",
        "cmd": ["./jarvis", "work-start", "evoluir o JARVIS para reduzir trabalho manual", "--dry-run"],
        "expect": [
            "Work Start",
            "intent:  self_evolve",
            "project: jarvis-core",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "work-start-project-fix-dry-run",
        "cmd": ["./jarvis", "work-start", "abre oficina e prepara missão segura", "--dry-run"],
        "expect": [
            "Work Start",
            "project: oficina",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "report-template-default",
        "cmd": ["./jarvis", "report-template"],
        "expect": [
            "Report Template",
            "/tmp/",
            "report-check --file",
            "report-apply --file",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "report-status-default",
        "cmd": ["./jarvis", "report-status"],
        "expect": [
            "Report Status",
            "caminho esperado:",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "report-check-good-fixture",
        "cmd": ["./jarvis", "report-check", "--file", "10_TESTES/FIXTURES/good_claude_report_agent_os.md"],
        "expect": [
            "Report Check",
            "quality: strong",
            "READY — pode aplicar",
            "report-apply --file",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "report-check-bad-fixture-warns",
        "cmd": ["./jarvis", "report-check", "--file", "10_TESTES/FIXTURES/bad_claude_report_commands_only.md"],
        "expect": [
            "Report Check",
            "quality: weak",
            "WEAK",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "work-close-no-session",
        "cmd": ["./jarvis", "work-close", "--dry-run"],
        "expect": [
            "Work Close",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "report-check-good-fixture-with-project-jarvis-core",
        "cmd": ["./jarvis", "report-check",
                "--file", "10_TESTES/FIXTURES/good_claude_report_agent_os.md",
                "--project", "jarvis-core"],
        "expect": [
            "Report Check",
            "quality: strong",
            "project alvo: jarvis-core",
            "project source: explicit --project",
            "READY",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "report-check-good-fixture-with-project-oficina",
        "cmd": ["./jarvis", "report-check",
                "--file", "10_TESTES/FIXTURES/good_claude_report_agent_os.md",
                "--project", "oficina"],
        "expect": [
            "Report Check",
            "quality: strong",
            "project alvo: oficina",
            "project source: explicit --project",
            "project-memory-update --project oficina",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "task-add-print-id-dry-run",
        "cmd": ["./jarvis", "task-add", "teste id real", "--dry-run", "--print-id"],
        "expect": [
            "Task Add",
            "task_id: t-",
            "Modo: --dry-run",
            "TASK_ID=t-",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "gate-status-no-run-or-summary",
        "cmd": ["./jarvis", "gate-status"],
        "expect": [
            "Gate Status",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "run-prune-dry-run",
        "cmd": ["./jarvis", "run-prune", "--keep", "20", "--dry-run"],
        "expect": [
            "Run Prune",
            "35_RUNS",
            "--keep: 20",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "doctor-agent",
        "cmd": ["./jarvis", "doctor-agent"],
        "expect": [
            "Agent Doctor",
            "Git",
            "Files",
            "Runtime State",
            "Registries",
            "Gates",
            "Commands",
            "Result",
            "AGENT DOCTOR",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "state-status",
        "cmd": ["./jarvis", "state-status"],
        "expect": [
            "State Status",
            "Work session",
            "Task queue",
            "Gates",
            "Runtime gitignore",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "state-reset-dry-run",
        "cmd": ["./jarvis", "state-reset", "--dry-run"],
        "expect": [
            "State Reset",
            "Modo:",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "state-archive-dry-run",
        "cmd": ["./jarvis", "state-archive", "--dry-run"],
        "expect": [
            "State Archive",
            "Modo:",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "no-claude-n8n-dry-run",
        "cmd": ["./jarvis", "no-claude", "workflow n8n de agendamento whatsapp", "--dry-run"],
        "expect": [
            "No-Claude Mode",
            "Claude não executado",
            "intent:",
            "blueprint:",
            "--dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "no-claude-open-project-dry-run",
        "cmd": ["./jarvis", "no-claude", "abre oficina e ve o que falta", "--dry-run"],
        "expect": [
            "No-Claude Mode",
            "project:",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "cheatsheet",
        "cmd": ["./jarvis", "cheatsheet"],
        "expect": [
            "Cheatsheet",
            "./jarvis now",
            "./jarvis start",
            "./jarvis next",
            "./jarvis finish",
            "./jarvis gates",
            "./jarvis health",
            "./jarvis no-claude",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "handoff-self",
        "cmd": ["./jarvis", "handoff-self"],
        "expect": [
            "Handoff Self",
            "JARVIS Handoff Snapshot",
            "Git",
            "Work session atual",
            "Latest gates",
            "Comandos importantes",
            "Hard rules",
            "Produção",
        ],
    },
    {
        "name": "alias-now",
        "cmd": ["./jarvis", "now"],
        "expect": [
            "JARVIS — Resume",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "alias-start-dry-run",
        "cmd": ["./jarvis", "start", "evoluir o JARVIS para reduzir trabalho manual", "--dry-run"],
        "expect": [
            "Work Start",
            "intent:  self_evolve",
            "Modo: --dry-run",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "alias-next",
        "cmd": ["./jarvis", "next"],
        "expect": [
            "Work Next",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "alias-finish-no-session",
        "cmd": ["./jarvis", "finish", "--dry-run"],
        "expect": [
            "Work Close",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "alias-health",
        "cmd": ["./jarvis", "health"],
        "expect": [
            "Agent Doctor",
            "Result",
            "AGENT DOCTOR",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "daily",
        "cmd": ["./jarvis", "daily"],
        "expect": [
            "Daily Dashboard",
            "Health",
            "Active Work",
            "Next",
            "Gates",
            "Top Task",
            "Useful Commands",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "first-run-check",
        "cmd": ["./jarvis", "first-run-check"],
        "expect": [
            "First-Run Check",
            "Sistema",
            "Repo",
            "Registries",
            "Runtime dirs",
            "Gitignore de runtime",
            "Result",
            "FIRST-RUN CHECK",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "recipe-list",
        "cmd": ["./jarvis", "recipe-list"],
        "expect": [
            "Recipe List",
            "n8n-workflow",
            "project-fix",
            "self-evolve",
            "no-claude-plan",
            "resume-stuck",
            "handoff",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "recipe-show-n8n-workflow",
        "cmd": ["./jarvis", "recipe-show", "n8n-workflow"],
        "expect": [
            "Recipe Show",
            "n8n-workflow",
            "Steps",
            "blueprint",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "recipe-show-project-fix",
        "cmd": ["./jarvis", "recipe-show", "project-fix"],
        "expect": [
            "Recipe Show",
            "project-fix",
            "project-intel",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "recipe-run-n8n-dry-run",
        "cmd": ["./jarvis", "recipe-run", "n8n-workflow", "--goal", "agendamento whatsapp", "--dry-run"],
        "expect": [
            "Recipe Run",
            "n8n-workflow",
            "--dry-run",
            "DRY-RUN",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "recipe-run-project-fix-dry-run",
        "cmd": ["./jarvis", "recipe-run", "project-fix", "--project", "oficina", "--goal", "bug agenda", "--dry-run"],
        "expect": [
            "Recipe Run",
            "project-fix",
            "oficina",
            "bug agenda",
            "DRY-RUN",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "recipe-run-self-evolve-dry-run",
        "cmd": ["./jarvis", "recipe-run", "self-evolve", "--goal", "reduzir comandos manuais", "--dry-run"],
        "expect": [
            "Recipe Run",
            "self-evolve",
            "DRY-RUN",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "recipe-run-no-claude-plan-dry-run",
        "cmd": ["./jarvis", "recipe-run", "no-claude-plan", "--goal", "criar app simples", "--dry-run"],
        "expect": [
            "Recipe Run",
            "no-claude-plan",
            "DRY-RUN",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "rc-status",
        "cmd": ["./jarvis", "rc-status"],
        "expect": [
            "RC Status",
            "Git",
            "Gates",
            "Readiness",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "rc-freeze-dry-run",
        "cmd": ["./jarvis", "rc-freeze", "--dry-run"],
        "expect_codes": [0, 1],
        "expect": [
            "RC Freeze",
            "Modo:",
            "Readiness:",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "acceptance-dry-run",
        "cmd": ["./jarvis", "acceptance", "--dry-run"],
        "expect": [
            "Acceptance",
            "Resultado",
            "ACCEPTANCE",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "do-now-dry-run",
        "cmd": ["./jarvis", "do", "o que faço agora", "--dry-run"],
        "expect": [
            "Worker Engine",
            "route:",
            "resume",
            "--dry-run: nenhum comando foi executado",
            "Claude não executado",
            "## Próximo",
        ],
    },
    {
        "name": "do-n8n-dry-run",
        "cmd": ["./jarvis", "do", "workflow n8n de agendamento whatsapp", "--dry-run"],
        "expect": [
            "Worker Engine",
            "n8n_blueprint",
            "blueprint --type n8n",
            "--dry-run: nenhum comando foi executado",
            "Claude não executado",
        ],
    },
    {
        "name": "do-project-dry-run",
        "cmd": ["./jarvis", "do", "abre oficina e vê bug agenda", "--dry-run"],
        "expect": [
            "Worker Engine",
            "project_fix_or_inspect",
            "project-intel",
            "goal-sprint",
            "--dry-run: nenhum comando foi executado",
        ],
    },
    {
        "name": "do-self-evolve-dry-run",
        "cmd": ["./jarvis", "do", "evolui o jarvis para reduzir comandos", "--dry-run"],
        "expect": [
            "Worker Engine",
            "self_evolve",
            "self-evolve --goal",
            "--dry-run: nenhum comando foi executado",
        ],
    },
    {
        "name": "do-no-arg-smart-resume",
        "cmd": ["./jarvis", "do", "--dry-run"],
        "expect": [
            "Worker Engine",
            "(vazio — smart resume)",
            "route:   resume",
            "Smart resume reasoning",
            "Claude não executado",
        ],
    },
    {
        "name": "do-project-override-bias",
        "cmd": ["./jarvis", "do", "bug na agenda", "--project", "oficina", "--dry-run"],
        "expect": [
            "Worker Engine",
            "project_fix_or_inspect",
            "project: oficina",
            "goal-sprint",
            "--dry-run: nenhum comando foi executado",
        ],
    },
    {
        "name": "do-screen-capture-dry-run",
        "cmd": ["./jarvis", "do", "tirar um print da tela", "--dry-run"],
        "expect": ["Worker Engine", "personal_tool", "screen_capture", "screen-capture --interactive", "nenhum comando foi executado"],
    },
    {
        "name": "do-image-to-pdf-blocked-preview",
        "cmd": ["./jarvis", "do", "converter 10_TESTES/FIXTURES/personal-tools-sample.svg para pdf", "--dry-run"],
        "expect": ["Worker Engine", "personal_tool", "image_to_pdf", "image-to-pdf", "--dry-run"],
    },
    {
        "name": "do-image-convert-dry-run",
        "cmd": ["./jarvis", "do", "converter 10_TESTES/FIXTURES/personal-tools-sample.svg para png", "--dry-run"],
        "expect": ["Worker Engine", "personal_tool", "image_convert", "image-convert", "nenhum comando foi executado"],
    },
    {
        "name": "do-speak-dry-run",
        "cmd": ["./jarvis", "do", "ler em voz alta", "teste de foco", "--dry-run"],
        "expect": ["Worker Engine", "personal_tool", "speak", "./jarvis speak", "nenhum comando foi executado"],
    },
    {
        "name": "do-message-draft-dry-run",
        "cmd": ["./jarvis", "do", "mensagem no whatsapp para 5511999999999", "teste local", "--dry-run"],
        "expect": ["Worker Engine", "personal_tool", "message_draft", "message-draft", "nenhum comando foi executado"],
    },
    {
        "name": "do-message-send-dry-run",
        "cmd": ["./jarvis", "do", "mandar mensagem para 5511999999999", "teste local", "--dry-run"],
        "expect": ["Worker Engine", "personal_tool", "message_send", "message-send", "nenhum comando foi executado"],
    },
    {
        "name": "do-memory-save-dry-run",
        "cmd": ["./jarvis", "do", "guarda Theo prefere respostas diretas na memória", "--dry-run"],
        "expect": ["Worker Engine", "personal_tool", "memory_save", "memory-save", "nenhum comando foi executado"],
    },
    {
        "name": "do-storage-scan-dry-run",
        "cmd": ["./jarvis", "do", "ver arquivos grandes em downloads", "--dry-run"],
        "expect": ["Worker Engine", "personal_tool", "storage_scan", "storage-scan", "nenhum comando foi executado"],
    },
    {
        "name": "do-files-triage-dry-run",
        "cmd": ["./jarvis", "do", "organizar arquivos de downloads", "--dry-run"],
        "expect": ["Worker Engine", "personal_tool", "files_triage", "files-triage", "nenhum comando foi executado"],
    },
    {
        "name": "do-history",
        "cmd": ["./jarvis", "do-history", "--limit", "5"],
        "expect": [
            "Do History",
            "Status real",
            "## Runs",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "do-show-latest",
        "cmd": ["./jarvis", "do-show", "latest"],
        "expect_codes": [0, 1],
        "expect": [
            "Do Show",
            "## Run",
            "## Pedido",
            "## Plano",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "do-learn-dry-run",
        "cmd": ["./jarvis", "do-learn", "--dry-run"],
        "expect": [
            "Do Learn",
            "Status real",
            "Fontes",
            "Produção: nada alterado",
        ],
    },
    {
        "name": "do-reuse-last-dry-run",
        "cmd": ["./jarvis", "do", "tweak: foco em testes locais", "--reuse-last", "--dry-run"],
        "expect": [
            "Worker Engine",
            "## Pedido",
            "Claude não executado",
        ],
    },
    {
        "name": "help-default-slim",
        "cmd": ["./jarvis", "help"],
        "expect": [
            "interface principal",
            "./jarvis do",
            "./jarvis help --all",
            "Memória de worker runs",
        ],
    },
    {
        "name": "help-all-full",
        "cmd": ["./jarvis", "help", "--all"],
        "expect": [
            "doctor",
            "scan-inbox",
            "do-history",
            "do-show",
            "do-learn",
        ],
    },
    {
        "name": "do-report-nonexistent-dry-run",
        "cmd": ["./jarvis", "do", "--report", "/tmp/jarvis-doesnotexist-xyz.md", "--dry-run"],
        "expect": [
            "Close the Loop",
            "AVISO (--dry-run): arquivo não existe",
            "report-template",
        ],
    },
    {
        "name": "project-deep-intel-cli",
        "cmd": ["python3", "11_SCRIPTS/project_deep_intel.py", "--project", "oficina", "bug agenda"],
        "expect": [
            "Project Deep Intel",
            "alias: `oficina`",
            "keywords inferidas",
            "Commits recentes",
        ],
    },
    {
        "name": "do-capability-dry-run",
        "cmd": ["./jarvis", "do", "agenda real google calendar", "--dry-run"],
        "expect": [
            "Worker Engine",
            "capability_check",
            "google_calendar",
            "--dry-run: nenhum comando foi executado",
        ],
    },
    {
        "name": "do-unclear-dry-run",
        "cmd": ["./jarvis", "do", "pedido estranho xyz", "--dry-run"],
        "expect": [
            "Worker Engine",
            "unclear",
            "--dry-run: nenhum comando foi executado",
            "Claude não executado",
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
        expected_codes = check.get("expect_codes", [0])
        ok = code in expected_codes and not missing

        results.append({
            "name": check["name"],
            "cmd": check["cmd"],
            "ok": ok,
            "code": code,
            "expected_codes": expected_codes,
            "missing": missing,
            "output": output,
        })

        if ok:
            print(f"OK  {' '.join(check['cmd'])}")
        else:
            print(f"FALHA  {' '.join(check['cmd'])}")
            if code not in expected_codes:
                print(f"  exit code: {code} (esperado: {expected_codes})")
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
