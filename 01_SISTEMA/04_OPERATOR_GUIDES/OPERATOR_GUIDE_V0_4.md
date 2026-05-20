# Operator Guide v0.4 — JARVIS Theo Padilha AI Worker

## Data
2026-05-20T19:32:54

## Status real
Guia operacional local. Não é produção.

## Regra principal
JARVIS prepara, organiza, valida e gera handoff. Execução real em projeto, produção, deploy, VPS, envio real ou credenciais só com autorização.

## Fluxo padrão para tarefa real

1. Atualizar índice dos projetos:
`./jarvis project-index ~/VAMOO_PROJETOS`

2. Descobrir o projeto certo:
`./jarvis project-select "sua tarefa"`

3. Preparar a tarefa completa:
`./jarvis task-start "sua tarefa"`

4. Gerar pacote para Claude/VS Code:
`./jarvis executor-handoff "sua tarefa"`

5. Imprimir prompt para copiar:
`./jarvis handoff-print`

6. Depois de usar Claude/ChatGPT/Gemini, salvar o output em:
`00_COLE_AQUI/03_OUTPUTS_CLAUDE_CHATGPT/`

7. Processar saída:
`./jarvis review-outputs`

8. Validar tudo:
`./jarvis release-check`

## Quando usar cada comando

### Quero ver se o JARVIS está saudável
`./jarvis release-check`

### Quero saber quais projetos existem no Mac
`./jarvis workspace-scan ~/VAMOO_PROJETOS`

### Quero escolher o projeto certo para uma tarefa
`./jarvis project-select "tarefa"`

### Quero preparar tudo para começar uma tarefa
`./jarvis task-start "tarefa"`

### Quero mandar algo para Claude sem me perder
`./jarvis executor-handoff "tarefa"`
`./jarvis handoff-print`

### Quero registrar resposta de Claude/Gemini/ChatGPT
`./jarvis review-outputs`

### Quero ver lista de comandos
`./jarvis commands`

## Cuidados
- Não colar `.env`, tokens, senhas ou credenciais em executor externo.
- Não fazer deploy/push/merge/produção sem autorização.
- Não mexer em main/master sem autorização.
- Não considerar prompt/handoff como execução validada.
- Sempre separar criado, preparado, testado, validado e produção.

## Próximo marco técnico
Criar `task-status`, para listar a última tarefa preparada, último handoff, último release-check e próximo passo seguro.
