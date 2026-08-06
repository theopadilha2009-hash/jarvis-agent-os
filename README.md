# JARVIS — Theo Padilha AI Worker

<!-- JARVIS_FOUNDATION_START -->
## JARVIS Foundation

JARVIS is Theo's personal local AI worker and terminal cockpit.

## Cockpit web (preparado para Vercel)

O repositório inclui um gateway Python serverless em `api/index.py`, um cockpit
web compacto em `web/index.html` e a configuração em `vercel.json`. Ele publica status, capacidades,
planejamento e chat opcional sem importar o backend local que escreve arquivos
ou inicia processos.

- Sem credencial, texto livre cai em uma resposta local explícita, sem fingir
  que executou integrações externas.
- Com `OPENROUTER_API_KEY` configurada no ambiente da hospedagem, texto livre
  usa `openrouter/free` (ou `OPENROUTER_MODEL`). Nunca coloque a chave no repo.
- Com `ELEVENLABS_API_KEY`, a rota `/speech` usa a voz
  `tS45q0QcrDHqHoaWdCDR`; sem ela, o navegador fala pela voz nativa.
- Com `N8N_WEBHOOK_URL` (e opcionalmente `N8N_WEBHOOK_TOKEN`), pedidos de
  agenda e tarefas são executados pelo webhook n8n.
- Print, conversão e organização de arquivos retornam um comando de
  handoff para `./jarvis do ...`, porque a Vercel não acessa o Mac.
- O runtime web é stateless: histórico persistente exigirá um adaptador de
  banco separado. Nenhuma migration faz parte deste gateway.

Preview local do mesmo contrato HTTP:

```bash
python3 api/index.py --port 8790
```

Main foundation docs:

- `00_IDENTITY/JARVIS_IDENTITY.md`
- `00_IDENTITY/MODES.md`
- `00_IDENTITY/JARVIS_RESEARCH_LESSONS.md`
- `02_SOURCES/DEEP_RESEARCH/README.md`

Operating modes:

- `PERSONAL_MODE`: Theo's own projects.
- `WORK_ASSIST_MODE`: sanitized support for VAMOO AI/company work.
- `FUTURE_COMPANY_MODE`: placeholder for a possible official company version later.

Private GitHub is sync, not a secret vault.
<!-- JARVIS_FOUNDATION_END -->


Creator / Owner: Theo Padilha  
Status real: cockpit local + runtime web em evolução  
Produção: Vercel pessoal do Theo  
Credenciais: não armazenar aqui  
Ações perigosas: sempre exigem aprovação humana

## O que é
JARVIS é um AI Operations Worker criado por Theo Padilha para transformar pedidos soltos em tarefas, contexto, planos seguros, execução controlada, memória, logs e relatórios.

## Como funciona agora
No estado atual, JARVIS já possui estrutura local de laboratório, inbox para entradas, CLI local, criação automática de tasks, scan/processamento de inbox, logs, arquivo morto para entradas processadas e memória inicial de projetos.

## Limites atuais
O runtime na Vercel não controla o Mac diretamente. Ações do computador usam o
worker local; ElevenLabs e n8n só ficam ativos quando suas variáveis de ambiente
estão configuradas no projeto Vercel.

## Regra principal
Nada de produção, token, senha, API key, QR Code, .env, deploy, push/main, envio real, banco real ou VPS real sem aprovação humana.

## Comandos atuais
- ./jarvis doctor
- ./jarvis report
- ./jarvis intake "pedido"
- ./jarvis scan-inbox
- ./jarvis process-inbox

## Visão
JARVIS deve evoluir para um cockpit operacional capaz de receber goals, entender contexto, escolher ferramentas, executar com segurança, se revisar, atualizar memória e chamar humano só quando houver risco.

## Autoria
Este sistema foi criado por Theo Padilha com apoio de IA. Toda versão futura deve preservar a autoria original.
