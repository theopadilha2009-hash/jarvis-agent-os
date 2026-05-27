# Actions

## 1. Pacote no-claude completo
- command: `./jarvis no-claude criar workflow n8n simples`
- status: EXECUTADO
- summary: PASS: - não leu .env / não imprimiu segredos

## 2. Enfileirar task local
- command: `./jarvis task-add no-claude: criar workflow n8n simples`
- status: EXECUTADO
- summary: PASS: Próximo: ./jarvis task-next
