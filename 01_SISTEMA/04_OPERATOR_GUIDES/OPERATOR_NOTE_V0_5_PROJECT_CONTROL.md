# Operator Note v0.5 — JARVIS Project Control

## Status real

JARVIS v0.5 está fechado como camada de controle por projeto.

Ele ajuda a escolher projeto, ver estado, validar alias, preparar sessão LOCAL_EXEC com project lock e gerar handoff seguro.

Ainda não executa patch automático, build real automático, commit/push/PR, deploy, VPS, n8n ou produção.

## Comandos humanos principais

Ver próximo passo geral:

./jarvis next-step

Ver opções de um projeto:

./jarvis next-step oficina

Ver menu dos projetos:

./jarvis project-menu

Validar projeto específico:

./jarvis project-resolve oficina

Preparar sessão segura travada no projeto:

./jarvis local-exec-session --project oficina "descrever tarefa sem deploy"

Ver handoff gerado:

./jarvis local-exec-handoff-latest

Revisar resposta de executor:

./jarvis local-exec-review caminho/da/resposta.md

Ver radar de ferramentas futuras:

./jarvis future-tools-radar

## Regra de uso

Para tarefa real, usar project lock explícito.

Correto:

./jarvis local-exec-session --project oficina "corrigir bug X sem deploy"

Evitar:

./jarvis local-exec-session "corrigir bug"

Motivo: tarefa genérica pode escolher projeto errado.

## Claude / executor externo

Claude é opcional.

Usar apenas quando:
- a tarefa real precisar de leitura/edição local;
- o handoff estiver claro;
- branch e Git status estiverem seguros;
- não houver risco de produção;
- você quiser explicitamente usar executor externo.

Depois de qualquer resposta do executor, salvar em `.md` e rodar:

./jarvis local-exec-review caminho/da/resposta.md

## Travas mantidas

- Sem push automático.
- Sem merge automático.
- Sem deploy automático.
- Sem VPS/n8n/produção.
- Sem abertura de `.env`.
- Sem segredo em chat/Git/source.
- Sem dizer validado se só foi criado/preparado.

## O que a v0.5 entrega

- Project Registry.
- Project Resolve.
- Project Lock em local-exec-session.
- Project Menu.
- Next Step humano.
- Future Tools Radar.
- Primeira sessão controlada com oficina.
- Snapshots de marco.

## Próximo rumo

v0.6 pode começar a criar um comando mais guiado, tipo `run-safe`, mas ainda sem aplicar patch sozinho.

## Produção

Nada em v0.5 altera produção.
