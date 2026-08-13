# JARVIS — Theo Padilha AI Worker

<!-- JARVIS_FOUNDATION_START -->
## JARVIS Foundation

JARVIS is Theo's personal local AI worker and terminal cockpit.

## Cockpit web (preparado para Vercel)

O repositório inclui um gateway Python serverless em `api/index.py`, um cockpit
web compacto em `web/index.html` e a configuração em `vercel.json`. Ele publica status, capacidades,
planejamento e chat opcional sem importar o backend local que escreve arquivos
ou inicia processos.

### Runtime V10

- A presença visual é um núcleo cognitivo abstrato: cristal, campo e anéis
  orbitais, sem rosto, corpo ou asset humanoide. Em repouso renderiza a 2 FPS
  e não baixa GLB.
- O cockpit V10 trata a conversa como workspace principal e reduz o núcleo a
  uma presença lateral compacta. A Central Operacional (`⌘K`) pesquisa ações
  reais, o composer aceita múltiplas linhas e anexos também podem ser colados
  ou arrastados. Evidências ficam na resposta, falhas podem ser tentadas de
  novo e nenhum drawer, navegador ou helper abre sozinho.
- Respostas chegam progressivamente por NDJSON; histórico de runs, memória,
  fila de tarefas e arquivos reutilizáveis têm gerenciadores visuais. Pedidos
  offline ficam numa caixa de saída explícita, tarefas em segundo plano podem
  notificar com opt-in e a voz aceita interrupção imediata.
- O núcleo 3D é carregado depois da interface e somente em tela/hardware
  adequados. Em celular, economia de dados ou movimento reduzido, o cockpit usa
  um núcleo abstrato estático; fora da tela, a renderização pausa por completo.
  Testes estáticos protegem nomes acessíveis, diálogos, responsividade e o
  orçamento de assets críticos.
- `./jarvis web` apenas imprime o endereço. O navegador só abre com
  `./jarvis web --open`.
- Web e `./jarvis do` compartilham um registro tipado de ações, riscos,
  confirmações e executores em `11_SCRIPTS/action_registry.py`.
- Pedidos recebem um run persistente local com plano, eventos, resultado e
  evidências. Ações externas e autoedição param em confirmação explícita;
  endpoints de run permitem consultar, confirmar, cancelar e repetir.
- “Busque na memória por …” usa SQLite local para pesquisar os Markdown
  confirmados por conteúdo, tipo, origem e projeto. O banco é runtime
  gitignored; os Markdown continuam sendo a fonte de verdade.

O cockpit funciona como central pessoal, não como outro chatbot: `GET
/personal-overview` reúne o estado real de conversa, memória, agenda, worker do
Mac e atividade recente. Pedidos como “o que você consegue fazer?” e “resumo do
meu dia” usam esse estado determinístico em vez de pedir ao modelo para inventar
uma lista de capacidades.

- Sem credencial, texto livre cai em uma resposta local explícita, sem fingir
  que executou integrações externas.
- Com `OPENROUTER_API_KEY` configurada no ambiente da hospedagem, texto livre
  usa uma lista ordenada de modelos gratuitos e o fallback oficial do
  OpenRouter. `OPENROUTER_MODEL_POOL` pode definir a ordem sem criar contas ou
  contornar limites; `OPENROUTER_MODEL` continua sendo aceito. Nunca coloque a
  chave no repo.
- Pesquisa gratuita coleta fontes antes da síntese. Consultas de carros leem
  anúncios OLX com preço, km e local e cruzam referências FIPE/média da
  Webmotors por versão. Se o modelo estiver sem cota, os dados e links reais
  ainda são devolvidos sem uma conclusão inventada. O cache dura cinco minutos.
- Com `ELEVENLABS_API_KEY`, a rota `/speech` usa a voz definida por
  `ELEVENLABS_VOICE_ID`; sem cota disponível, a interface continua em texto e
  informa a falha real.
- Com `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY`, pedidos explícitos para
  guardar algo escrevem em `public.jarvis_memories`, `/memory-tree` lê a
  constelação persistente e o OpenRouter recebe as memórias recentes como
  contexto. A chave server-side nunca é enviada ao navegador.
- Com `JARVIS_OWNER_TOKEN`, memória, agenda e comandos do Mac exigem pareamento
  no painel Sistema. O valor fica somente no armazenamento local do navegador.
- `./jarvis computer-worker --install` mantém uma ponte leve entre a fila
  privada do Supabase e o Mac. O worker aceita apenas abrir/fechar aplicativo,
  capturar tela, abrir o gravador, analisar Downloads, diagnosticar memória,
  consultar GitHub e enviar mensagem com número/texto explícitos. Cada pedido
  recebe estado e evidência; o worker não aceita shell ou caminho arbitrário.
- Pedidos explicitamente encadeados, como “abra o Spotify e depois tire um
  print”, viram um run de duas a seis etapas. O worker respeita dependências,
  não executa uma etapa depois da falha anterior e a interface só chama o run
  de concluído quando todas as linhas persistidas confirmam sucesso.
- Com `N8N_WEBHOOK_URL` (e opcionalmente `N8N_WEBHOOK_TOKEN`), pedidos de
  agenda e tarefas são executados pelo webhook n8n.
- Print e análise de armazenamento usam a fila privada do worker. Conversões e
  organização de arquivos ainda retornam um handoff explícito para o Mac.
- Sem Supabase, o preview local continua lendo as memórias Markdown do Mac; na
  Vercel, a memória persistente depende das duas variáveis acima.

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
O runtime na Vercel não acessa o Mac diretamente: ele grava um pedido
allowlisted no Supabase, e o worker local pareado executa e devolve a evidência.
Aceitação da fila não é apresentada como conclusão; runs pendentes permanecem
visivelmente em andamento até o worker devolver estado terminal.
ElevenLabs e n8n só ficam ativos quando suas variáveis de ambiente estão
configuradas no projeto Vercel. A voz continua em texto quando a cota externa
acaba.

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
