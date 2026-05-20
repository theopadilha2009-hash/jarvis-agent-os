# Contexto JARVIS

Sistema: JARVIS — Theo Padilha AI Worker
Creator / Owner: Theo Padilha
Status real: laboratório local. Não é produção.

Pedido:
preparar análise manual com Claude para corrigir bug em repo sem mexer em produção

Tipo detectado:
bug/código

Risco detectado:
alto

Perfil sugerido:
PRODUCTION_LOCKED

Ferramenta sugerida:
CHATGPT_COCKPIT + checklist read-only

Modo:
diagnóstico read-only

Motivo:
Pedido contém risco alto. Só diagnóstico/plano até aprovação humana.

Primeira ação segura:
Criar plano de diagnóstico. Não executar ação real.

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
