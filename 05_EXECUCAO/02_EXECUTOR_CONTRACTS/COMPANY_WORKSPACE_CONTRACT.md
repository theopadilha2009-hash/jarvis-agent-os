# Contract — Company Workspace Mode

## Status real
Documentado. Nada conectado. Nada executado em projeto de empresa.

## Objetivo
Permitir que o JARVIS seja usado em projetos da empresa sem misturar autoria, credenciais, produção, conta do chefe ou projetos pessoais.

## Regra de autoria
JARVIS — Theo Padilha AI Worker continua sendo criado e pertencente a Theo Padilha.

## Uso em empresa
Quando usado em projeto da empresa, o JARVIS atua como cockpit local de organização, decisão, prompt, plano, revisão, memória e status.

## Claude do chefe/equipe
Claude pode ser usado como executor externo autorizado quando disponível, mas:
- não vira dono do JARVIS;
- não recebe segredos;
- não recebe contexto pessoal sensível;
- não faz deploy/main/produção sem autorização;
- deve seguir contrato de executor.

## VS Code
VS Code é workspace de execução local. Antes de qualquer uso:
- confirmar pasta certa;
- rodar git status;
- confirmar branch;
- evitar main;
- não abrir/envazar .env;
- não commitar segredo;
- não fazer push/deploy sem autorização.

## Separação obrigatória
- Projeto pessoal: THEO_OWNER / LAB_FREE
- Projeto empresa: COMPANY_WORKSPACE
- Conta/ferramenta do chefe: CHEFE_CLAUDE
- Produção: PRODUCTION_LOCKED

## Produção
Nada automático. Sempre aprovação humana.
