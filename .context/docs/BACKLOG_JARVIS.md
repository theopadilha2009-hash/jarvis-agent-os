# Backlog do JARVIS — pedidos do Theo (15/08/2026)

Ordem de urgência definida pelo Theo. Cada item fica aqui até estar **no ar e
validado**; quem terminar marca o estado e cola a evidência real.

## P0 — Voz sob o comando do Theo

### 1. Painel "Configuração de voz" no menu dos três pontinhos
- Listar **todas** as vozes disponíveis (ElevenLabs da conta, voz própria local,
  OpenAI, navegador) com o estado de cada uma.
- Trocar a voz ativa e **adicionar** voz nova (colar voice id, criar pela
  ElevenLabs, apontar modelo local).
- Hoje existe só "Ajustar voz" (calibrador de estabilidade/velocidade) — falta a
  troca e o cadastro.
- Estado: **feito** — dialog `voiceTuningDialog` ganhou a aba de vozes.

### 2. Ele muda a própria voz quando o Theo pede
- "muda sua voz para X", "deixa sua voz mais grave", "melhora sua voz" devem
  alterar a voz ativa de verdade, não só responder.
- Precisa de intenção real (`voice_change`), gravação da preferência e resposta
  com evidência.
- Estado: **feito** — intenção `voice_settings` roteando para o painel/ajuste.

### 3. Acesso e conhecimento total sobre o próprio sistema
- Já entrou o bloco `capability_briefing()`; falta cobrir voz, estilos e
  personalidade na mesma lista, para ele nunca negar o que tem.
- "salva isso" sem mais contexto deve gravar quando ele for o dono.
- Estado: **parcial** — briefing existe, cobertura de voz/estilo/persona pendente.

### 4. Atender pelo nome (wake word)
- "fala jarvis", "e aí jarvis", "oi jarvis", "opa ultron" e variações, com o
  microfone sempre pronto; vale para as duas personas.
- Estado: **feito** — escuta contínua leve, toggle no painel de voz, e o resto
  da frase vira comando quando vem junto.

### 5. Estilos e personalidade sob comando
- Painel e comandos para trocar estilo de resposta e personalidade (JARVIS,
  ULTRON, e variações que o Theo pedir).
- Estado: **pendente**.

### 5b. Voz masculina, forte e de autoridade — regra permanente
- A voz do JARVIS é masculina e grave. O fallback do navegador ranqueia vozes
  masculinas e rejeita femininas; a voz própria sai com pitch abaixado.
- Timbre configurável pelo painel: gravidade e cadência viajam no
  `voice_profile` até o servidor de voz.
- Estado: **feito**, mas a qualidade final depende da camada disponível.

## P0 — Presença no boot

### 6. Falar quando o Mac liga por completo
- Hoje a chegada dispara no **desbloqueio de tela** (10 min) e ao voltar para a
  aba (25 min). Falta o caso do boot: ligar a máquina e abrir algo já ouvir
  "Bem-vindo, Theo. O que vamos fazer hoje?".
- Caminho: o worker roda como LaunchAgent, então o primeiro ciclo depois do boot
  é o gatilho natural.
- Estado: **feito** — saudação de boot no worker, com marca de sessão.

### 7. Ele na tela inicial do Mac
- O Theo quer ver o JARVIS "do lado, falando comigo" na tela inicial, com um
  botão **Entrar no sistema**.
- Opções: app de tela cheia (PWA já instalável), janela sempre-visível pelo
  worker, ou papel de parede dinâmico. Decidir com o Theo antes de construir.
- Estado: **pendente — precisa de decisão de formato**.

## Regras que valem para todos os itens

- Nada entra sem validação real: comando executado de verdade, output colado.
- A voz nunca cai de nível em silêncio — se cair, o cockpit diz por quê
  (`GET /voice-status`).
- Não clonamos voz de pessoa real; replicamos estilo.
