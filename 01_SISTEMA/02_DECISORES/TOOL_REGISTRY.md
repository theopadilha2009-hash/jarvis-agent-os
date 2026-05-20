# Tool Registry — JARVIS Theo Padilha

## Status real
Registro criado localmente. Nenhuma ferramenta externa foi instalada, conectada ou validada por este arquivo.

## Regra principal
Ferramenta registrada não significa ferramenta ativa. Primeiro documentar, depois testar em laboratório, depois conectar com segurança.

## Tools

### CHATGPT_COCKPIT
Status: disponível manualmente.
Uso: decisão, resumo, prompts, planejamento, status real, documentação.
Risco: baixo.
Observação: cockpit principal atual.

### CLAUDE_MANUAL
Status: disponível manualmente se o usuário abrir Claude.
Uso: análise, revisão, código, prompts, raciocínio técnico.
Risco: médio se usar projeto real.
Regra: não colar segredos, não usar produção.

### CLAUDE_CODE_FUTURO
Status: futuro / não conectado.
Uso: executor premium de código local.
Risco: alto se tiver permissão ampla.
Regra: somente branch/sandbox, sem main, sem deploy, sem credenciais.

### GEMINI_MANUAL
Status: disponível manualmente se o usuário abrir Gemini.
Uso: pesquisa, comparação, análise alternativa.
Risco: médio em conteúdo sensível.
Regra: não usar conta escolar para projeto comercial sensível.

### GEMINI_CLI_FUTURO
Status: futuro / não conectado.
Uso: terminal agent, pesquisa, execução barata/free-first.
Risco: médio.
Regra: testar em sandbox.

### OLLAMA_LOCAL_FUTURO
Status: futuro / não conectado.
Uso: resumo local, classificação, limpeza de texto, privacidade.
Risco: baixo/médio.
Regra: não confiar para tarefa complexa sem revisão.

### GROQ_API_FUTURO
Status: futuro / não conectado.
Uso: classificação barata, resumo rápido, roteamento.
Risco: custo/API/privacidade.
Regra: só com chave segura e limite.

### DEEPSEEK_FUTURO
Status: futuro / não conectado.
Uso: alternativa de modelo para código/raciocínio.
Risco: privacidade/custo/qualidade variável.
Regra: laboratório primeiro.

### FLOW_SPEC
Status: radar/laboratório.
Uso: transformar ideia grande em spec, plano, tarefas e critérios.
Risco: baixo.
Regra: usar para projetos grandes, não para bug pequeno.

### N8N_FUTURO
Status: futuro / não conectado.
Uso: orquestração, fila, logs, aprovações, agendamentos.
Risco: alto se ativar produção/envio real.
Regra: active=false até teste controlado.

### PLAYWRIGHT_FUTURO
Status: futuro / não conectado.
Uso: testes web, screenshots, browser automation.
Risco: médio.
Regra: usar primeiro em site local/sandbox.

### RUFLO_FUTURO
Status: futuro / sandbox only.
Uso: multiagente/autopilot.
Risco: alto se usado cedo.
Regra: só depois do core local estar maduro.
