# Project Status — LS Clínica

## Projeto
LS Clínica — agente de atendimento WhatsApp com UAZAPI, n8n e IA.

## Status real atual
Testado em fluxo automático controlado.

## Criado
- Workflow LS v1.3 com arquitetura real UAZAPI.
- Entrada por webhook isolado no n8n.
- Normalização de payload UAZAPI.
- Anti-loop com `fromMe` / `track_source`.
- Gate de horário BR.
- Allowlist de teste.
- Classificador LLM.
- Especialista dinâmico LLM baseado no prompt da Dra. Larissa.
- Payload de envio UAZAPI `/send/text`.
- Log estruturado.

## Importado
- Workflow importado no n8n para teste controlado.

## Configurado
- Credenciais/URL/token foram configurados na UI do n8n.
- Segredos não devem ser exportados no JSON nem salvos no Jarvis.

## Conectado
- Webhook UAZAPI apontado para endpoint isolado da LS.
- Entrada UAZAPI chegou no n8n.
- Saída UAZAPI respondeu via WhatsApp no teste controlado.

## Testado
- Mensagem “oi” enviada no WhatsApp chegou no n8n.
- IA gerou resposta.
- Resposta chegou no WhatsApp via UAZAPI.

## Validado
- Validado apenas como fluxo automático controlado: UAZAPI → n8n → IA → UAZAPI.

## Não é produção plena
Ainda falta decisão operacional antes de pacientes reais:
- número/instância definitiva;
- escopo de uso;
- regras de horário;
- pausa por humano;
- handoff;
- monitoramento;
- validação com mais casos reais.

## Riscos
- Usar número/instância errada.
- Misturar webhook de entrada com endpoint de envio.
- Payload UAZAPI mal normalizado.
- Loop por `track_source` / `fromMe`.
- Exportar workflow configurado com token.
- Chamar teste controlado de produção plena.

## Próximo passo seguro
Validar mais mensagens em teste controlado e decidir regra de liberação controlada com humano acompanhando.
