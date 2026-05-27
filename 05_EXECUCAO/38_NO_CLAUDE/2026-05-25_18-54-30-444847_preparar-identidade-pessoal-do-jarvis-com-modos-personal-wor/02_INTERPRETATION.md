# Interpretação local (sem LLM)
## O que JARVIS entendeu
- intent: `unclear`
- projeto: `jarvis-core`

## Como JARVIS chegou aqui
JARVIS classificou via `ask_router.detect_intent` (regex, sem LLM).
Se o intent estiver errado, o pedido pode ser ambíguo. Use `./jarvis ask-log`
para revisar requests que cairam em `unclear` e ajustar `INTENT_PATTERNS`.

## O que JARVIS NÃO pode fazer sem Claude
- escrever o código real
- aplicar fix no projeto-alvo
- escrever o workflow n8n real
- abrir Claude Code ou rodar agente em background
- chamar API Anthropic / OpenAI

## O que JARVIS pode fazer agora
- gerar plano manual (próximo arquivo)
- imprimir comandos seguros que VOCÊ executa
- gerar blueprint local (se aplicável)
- enfileirar task local (`task-add`) para retomar quando Claude voltar
