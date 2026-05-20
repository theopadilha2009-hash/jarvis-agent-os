# Executor Profiles — JARVIS Theo Padilha AI Worker

## Status real
Perfis documentados localmente. Nenhum acesso externo, Claude, Gemini, n8n, API ou credencial foi conectado.

## Regra principal
Perfil define permissões e ferramentas possíveis. Perfil não libera produção automaticamente.

## Perfis

### THEO_OWNER
Dono: Theo Padilha
Uso: desenvolvimento principal do JARVIS.
Ferramentas atuais: ChatGPT manual, terminal local, Git, Markdown, Mac.
Ferramentas futuras: Gemini CLI, Ollama, Groq, n8n local, Claude se disponível.
Permissão: máxima no laboratório local.
Bloqueios: produção, VPS real, deploy, credenciais, API paga e envio real precisam aprovação explícita.
Status: ativo.

### CHEFE_CLAUDE
Dono da conta/ferramenta: chefe/equipe.
Uso: execução premium futura quando houver Claude disponível.
Ferramentas atuais: não conectado.
Ferramentas futuras: Claude manual, Claude Code, análise de repo, revisão técnica.
Permissão: limitada ao contexto autorizado.
Bloqueios: nunca usar conta/ferramenta do chefe para projeto pessoal sensível sem autorização.
Status: futuro.

### CLIENT_SAFE
Dono/usuário: cliente ou usuário externo.
Uso: versão segura e limitada do JARVIS.
Ferramentas atuais: não conectado.
Ferramentas futuras: dashboard, relatórios, tarefas simples, consulta de status.
Permissão: baixa.
Bloqueios: sem terminal livre, sem produção, sem credenciais, sem acesso a projetos internos.
Status: futuro.

### LAB_FREE
Dono/usuário: Theo Padilha.
Uso: testes com ferramentas grátis/local.
Ferramentas atuais: manual.
Ferramentas futuras: Ollama, Gemini free/manual, Groq free/baixo custo, DeepSeek laboratório.
Permissão: laboratório/sandbox.
Bloqueios: não usar dados sensíveis, não usar produção, não usar cliente real.
Status: futuro/laboratório.

### PRODUCTION_LOCKED
Dono/usuário: qualquer operação sensível.
Uso: modo de segurança para produção.
Ferramentas atuais: nenhuma execução automática.
Ferramentas futuras: read-only, checklist, aprovação humana.
Permissão: leitura/diagnóstico primeiro.
Bloqueios: deploy, main, banco real, VPS real, envio real e credenciais sem autorização explícita.
Status: regra de segurança permanente.
