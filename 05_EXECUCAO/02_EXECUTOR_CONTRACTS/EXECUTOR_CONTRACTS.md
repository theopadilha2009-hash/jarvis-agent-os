# Executor Contracts — JARVIS

## Objetivo
Definir como cada executor pode ser usado sem bagunçar autoria, segurança, custo ou produção.

## Regra
Executor externo recebe tarefa limitada. JARVIS continua sendo o dono do processo.

## Contrato base
Todo executor precisa receber:
- objetivo
- contexto mínimo
- limites
- arquivos permitidos
- ações proibidas
- formato de saída
- status real
- próximos passos

## Proibido por padrão
- pedir segredo
- expor token
- usar produção
- fazer deploy
- mexer na main
- enviar mensagem real
- usar API paga sem aprovação
