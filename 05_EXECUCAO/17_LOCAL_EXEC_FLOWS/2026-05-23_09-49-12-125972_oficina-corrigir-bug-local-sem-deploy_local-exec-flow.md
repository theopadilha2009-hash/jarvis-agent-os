# LOCAL_EXEC Flow — JARVIS Theo Padilha AI Worker

## Data
2026-05-23T09:49:12

## Tarefa
oficina corrigir bug local sem deploy

## Status real
Guia operacional local criado. Nenhum projeto foi alterado.

## Fluxo seguro
1. PREPARE — classificar modo e preparar contexto.
2. READONLY — inspecionar projeto sem alterar.
3. LOCAL_EXEC PLAN — planejar edição local.
4. LOCAL_EXEC READY — checar blockers antes de editar.
5. LOCAL_EXEC HANDOFF — gerar pacote curto para Claude/VS Code.
6. LOCAL_EXEC REVIEW — revisar saída do executor antes de aceitar patch.

## Comandos recomendados
```bash
./jarvis mode-plan "oficina corrigir bug local sem deploy"
./jarvis readonly-run "oficina corrigir bug local sem deploy"
./jarvis local-exec-plan "oficina corrigir bug local sem deploy"
./jarvis local-exec-ready "oficina corrigir bug local sem deploy"
./jarvis local-exec-handoff "oficina corrigir bug local sem deploy"
# depois de rodar Claude/VS Code e salvar a resposta em arquivo:
./jarvis local-exec-review caminho/da/resposta.md
```

## Travamentos obrigatórios
- não editar main/master sem branch segura;
- não abrir/copiar `.env`; usar apenas variáveis locais existentes;
- não fazer push;
- não fazer merge;
- não fazer deploy;
- não alterar VPS, n8n, banco real ou produção;
- se a revisão bloquear, parar e revisar com humano.

## Critério para avançar
- `local-exec-ready` sem blocker crítico;
- Claude/VS Code respondeu com arquivos alterados e validações;
- `local-exec-review` não classificou como `PARAR E REVISAR COM HUMANO`; 
- build/test reportado ou justificativa clara.

## Ainda não executa
- patch automático;
- commit automático;
- push/PR automático;
- deploy;
- VPS/n8n/produção.

## Produção
Nada alterado.
