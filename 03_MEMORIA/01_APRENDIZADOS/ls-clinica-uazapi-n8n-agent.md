# Aprendizado — LS Clínica UAZAPI + n8n + IA

## Título
Webhook de entrada não é endpoint de envio.

## Projeto relacionado
LS Clínica.

## O que aconteceu
O agente LS conseguiu responder automaticamente no WhatsApp em teste controlado usando UAZAPI → n8n → IA → UAZAPI.

## Principal aprendizado
Antes de prompt perfeito, o mais importante é validar o fluxo real:
entrada chega, payload é normalizado, anti-loop funciona, IA responde, envio usa endpoint correto e log mostra o caminho.

## Causas de erro encontradas
- Teste em número/instância errada.
- Payload UAZAPI lido por caminhos incorretos.
- Telefone do remetente não extraído corretamente.
- Node de envio usando URL do próprio webhook n8n.
- Risco de token em JSON de referência.

## Como diagnosticar
Verificar:
- `lead.numero`
- `mensagem.texto`
- `mensagem.tipo`
- `fromMe = false`
- `trackSource != n8n`
- `envio_real_liberado = true`
- node de envio chamando `/send/text`
- execução passando por Normaliza, Anti-Loop, IA, Build Payload e Send Text.

## Solução aplicada
- Separar webhook de entrada e endpoint de envio.
- Usar endpoint UAZAPI `/send/text` para saída.
- Normalizar payload real UAZAPI.
- Adicionar anti-loop com `fromMe` / `track_source`.
- Manter allowlist no teste.
- Guardar token apenas na UI/credencial do n8n.

## Como evitar no futuro
- Começar sempre pelo fluxo real antes de melhorar prompt.
- Não copiar segredos de workflow de referência.
- Testar número/instância correta.
- Manter logs antes de achismo.
- Separar teste controlado de produção plena.

## Template reutilizável
Webhook → Normaliza → Anti-loop → Dedup/buffer → Pausa IA → Contexto/memória → Classificador → Agente/especialista → Parser/guardrail → Envio → Log → Handoff/erro.

## Status da lição
Documentada e reutilizável.
