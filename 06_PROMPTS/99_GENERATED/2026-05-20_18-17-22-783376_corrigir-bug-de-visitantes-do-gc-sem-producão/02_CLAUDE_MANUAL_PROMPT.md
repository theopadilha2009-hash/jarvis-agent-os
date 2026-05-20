# Contexto JARVIS

Sistema: JARVIS — Theo Padilha AI Worker
Creator / Owner: Theo Padilha
Status real: laboratório local. Não é produção.

Pedido:
corrigir bug de visitantes do GC sem produção

Tipo detectado:
bug/código

Risco detectado:
baixo

Perfil sugerido:
THEO_OWNER

Ferramenta sugerida:
CHATGPT_COCKPIT agora; CLAUDE_CODE_FUTURO depois

Modo:
branch/sandbox

Motivo:
Código precisa de branch, git status, patch mínimo, build/teste e sem deploy.

Primeira ação segura:
Confirmar git status, branch e escopo antes de editar.

Bloqueios:
- não pedir ou expor credenciais
- não usar produção
- não fazer deploy
- não mexer em main/push/merge
- não usar banco real
- não enviar mensagem real
- não usar API paga sem aprovação


# Tarefa para Claude / Claude Code

Modo inicial: read-only.
Antes de editar:
- confirmar pasta/projeto
- rodar git status
- identificar branch
- localizar arquivos relevantes
- propor patch mínimo

Se for autorizado editar:
- não mexer na main
- não refatorar fora do escopo
- não commitar/push/deployar
- rodar build/teste possível
- resumir arquivos alterados

Saída obrigatória:
- arquivos lidos
- diagnóstico
- plano
- alterações sugeridas ou feitas
- testes rodados
- riscos restantes
