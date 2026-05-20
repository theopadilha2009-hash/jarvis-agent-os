# Task

## ID
TASK-20260520-001

## Projeto
JARVIS — Theo Padilha AI Worker

## Pedido original
Fazer o Jarvis evoluir para executar ações no terminal quando necessário, com segurança, logs e aprovação humana para risco.

## Objetivo final
Criar uma camada local de comandos seguros para o Jarvis executar tarefas como status, check, criação de task, criação de logs, processamento de memória e futuramente execução controlada com Claude/Gemini/n8n.

## Tipo
- [x] automação local
- [x] terminal
- [x] Jarvis core
- [ ] VPS/produção

## Status real
Criado localmente.

## Risco
- [x] baixo agora
- [ ] médio
- [ ] alto

## Ferramenta sugerida
Bash local primeiro. n8n e agentes só depois.

## Contexto usado
- Teste 01 LS Clínica Memory Pack concluído.
- Comando `./jarvis check` funcionando.
- Comando `./jarvis status` funcionando.
- Estrutura do laboratório validada.

## Plano seguro
1. Manter comandos apenas locais.
2. Criar comandos simples: status, check, new-task, log.
3. Adicionar depois comandos de processar inbox e gerar relatório.
4. Só depois conectar Claude/Gemini.
5. Nunca permitir deploy, main, VPS, produção ou API paga sem aprovação.

## Aprovação humana necessária antes de
- executar comando em VPS real;
- alterar projeto de cliente real;
- publicar/deployar;
- instalar ferramenta nova;
- usar credenciais;
- rodar API paga;
- enviar mensagem real.

## Resultado esperado
Jarvis começa a virar uma CLI local segura, com tarefas e logs.

## Resultado obtido
Primeira versão do comando `./jarvis` criada e testada com `check` e `status`.

## Próximo passo
Criar comando `./jarvis process-memory` para transformar entradas em notas organizadas.
