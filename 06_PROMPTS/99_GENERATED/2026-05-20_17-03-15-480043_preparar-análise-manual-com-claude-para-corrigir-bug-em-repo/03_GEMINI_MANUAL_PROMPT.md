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


# Tarefa para Gemini

Use como segundo cérebro de baixo custo/manual.
Entregue:
- análise alternativa
- riscos que podem ter passado batido
- opções free/baixo custo
- plano simplificado
- pontos para validar antes de executar

Não assumir acesso a arquivos locais.
Não usar dados sensíveis.
