# Contexto JARVIS

Sistema: JARVIS — Theo Padilha AI Worker
Creator / Owner: Theo Padilha
Status real: laboratório local. Não é produção.

Pedido:
projeto da empresa no VS Code com executor externo autorizado: investigar bug no projeto GC sem alterar produção | projeto selecionado: gc-gestao-de-cristo | caminho: /Users/usuario1/VAMOO_PROJETOS/gc-gestao-de-cristo | sem produção, sem credenciais, sem deploy

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
