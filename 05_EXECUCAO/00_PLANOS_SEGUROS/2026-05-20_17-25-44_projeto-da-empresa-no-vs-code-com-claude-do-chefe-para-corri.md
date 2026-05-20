# Plano Seguro — JARVIS Theo Padilha AI Worker

## Pedido
projeto da empresa no VS Code com Claude do chefe para corrigir bug sem produção

## Tipo detectado
bug/código

## Risco detectado
médio

## Perfil sugerido
COMPANY_WORKSPACE

## Ferramenta sugerida
CHATGPT_COCKPIT + CLAUDE_MANUAL/CLAUDE_CODE_FUTURO se autorizado

## Modo de execução
workspace empresa / branch / read-only primeiro

## Motivo do roteamento
Pedido menciona contexto de empresa; usar workspace separado, VS Code/Git seguro e Claude apenas como executor autorizado.

## Status real
Plano criado localmente. Nada executado.

## Primeira ação segura
Confirmar pasta, git status, branch, escopo e autorização antes de executar.

## Etapas recomendadas
1. Confirmar projeto, pasta e contexto.
2. Rodar `git status` quando houver repo.
3. Confirmar branch e escopo.
4. Separar leitura, plano, execução e validação.
5. Executar só em laboratório/branch/sandbox quando permitido.
6. Rodar validação possível.
7. Salvar logs, memória e relatório.
8. Pedir aprovação humana antes de qualquer ação sensível.

## Bloqueios sem aprovação humana
- produção
- VPS real
- deploy
- main/push/merge
- credenciais
- banco real
- envio real para cliente/paciente/lead
- API paga relevante
- instalação de ferramenta nova
- autoalteração de arquitetura

## Produção
Nada alterado.

## Criador / dono
Theo Padilha.
