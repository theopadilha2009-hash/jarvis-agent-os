# Referências open source usadas no cockpit web

Pesquisa registrada em 2026-08-09. Nenhum componente foi copiado literalmente;
os padrões abaixo foram reimplementados em JavaScript e CSS próprios para o
runtime stdlib/Vercel do JARVIS.

## assistant-ui/assistant-ui — MIT

- Fonte: https://github.com/assistant-ui/assistant-ui
- Padrões adaptados: sugestões iniciais compactas, composer fixo e histórico de
  conversa restaurado dentro da mesma thread visual.

## assistant-ui/tool-ui — MIT

- Fonte: https://github.com/assistant-ui/tool-ui
- Padrões adaptados: progresso curto `pedido → núcleo/forja → resultado`, estado
  atual identificável e recibo final sem manter um painel grande aberto.

## ag-ui-protocol/ag-ui — MIT

- Fonte: https://github.com/ag-ui-protocol/ag-ui
- Padrões adaptados: eventos explícitos de início/fim, execução observável e
  separação entre estado do agente, chamada de ferramenta e resultado real.

## CopilotKit/CopilotKit — MIT

- Fonte: https://github.com/CopilotKit/CopilotKit
- Padrões adaptados: generative UI controlada. O modelo escolhe entre superfícies
  que o produto já conhece; não injeta HTML arbitrário no cockpit.

## Decisões para o JARVIS

- Preservar o cockpit sem dependências React ou build frontend adicional.
- Não importar código de projetos sem licença permissiva comprovada.
- Mostrar progresso apenas durante trabalho real e usar o `event_stream` do
  backend como recibo após a resposta.
- Evitar envio concorrente da mesma conversa e cancelar voz anterior antes de
  iniciar uma nova reprodução.
- Reduzir o custo ocioso do Three.js agendando apenas os frames necessários.
