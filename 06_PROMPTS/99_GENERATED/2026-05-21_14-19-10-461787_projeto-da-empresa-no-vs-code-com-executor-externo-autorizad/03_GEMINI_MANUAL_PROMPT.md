# Contexto JARVIS

Sistema: JARVIS — Theo Padilha AI Worker
Creator / Owner: Theo Padilha
Status real: laboratório local. Não é produção.

Pedido:
projeto da empresa no VS Code com executor externo autorizado: corrigir bug de visitantes do GC sem produção | projeto selecionado: gc-gestao-de-cristo | caminho: /Users/usuario1/VAMOO_PROJETOS/gc-gestao-de-cristo | sem produção, sem credenciais, sem deploy

Tipo detectado:
bug/código

Risco detectado:
médio

Perfil sugerido:
COMPANY_WORKSPACE

Ferramenta sugerida:
CHATGPT_COCKPIT + CLAUDE_MANUAL/CLAUDE_CODE_FUTURO se autorizado

Modo:
workspace empresa / branch / read-only primeiro

Motivo:
Pedido menciona contexto de empresa; usar workspace separado, VS Code/Git seguro e Claude apenas como executor autorizado.

Primeira ação segura:
Confirmar pasta, git status, branch, escopo e autorização antes de executar.

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
