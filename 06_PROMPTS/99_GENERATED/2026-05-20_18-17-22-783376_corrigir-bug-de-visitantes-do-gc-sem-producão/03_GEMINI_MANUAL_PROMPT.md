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
