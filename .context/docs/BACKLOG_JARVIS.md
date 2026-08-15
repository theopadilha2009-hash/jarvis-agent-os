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
- "salva isso" sem mais contexto deve gravar quando ele for o dono.
- Estado: **feito** — o briefing cobre voz, escuta pelo nome, personalidade e a
  fala no boot; ele não pode mais dizer que o jeito dele é fixo.

### 4. Atender pelo nome (wake word)
- "fala jarvis", "e aí jarvis", "oi jarvis", "opa ultron" e variações, com o
  microfone sempre pronto; vale para as duas personas.
- Estado: **feito e corrigido (15/08)** — a primeira negativa do microfone
  gravava "0" no localStorage e matava o recurso para sempre; a chave virou
  `jarvis-wake-word-v2`, a negativa só pede um clique, o timer sempre reagenda
  e um indicador ao lado do microfone mostra se está armado. Gatilhos novos:
  "bom dia jarvis", "psiu jarvis", "eae jarvis", nome no início da frase.

### 5. Estilos e personalidade sob comando
- Painel e comandos para trocar estilo de resposta e personalidade.
- Estado: **feito** — seis estilos (Padrão, Direto, Mordomo, Afiado, Técnico,
  Parceiro) no painel dos três pontinhos e por comando ("muda sua
  personalidade", "responde mais direto"). O estilo viaja no pedido e vira
  diretiva no prompt, validado contra o catálogo.

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
- Estado: **feito e corrigido (15/08)** — quem falava era a aba, e o navegador
  silencia áudio que ninguém pediu com um clique. Agora o worker fala pelo
  alto-falante do Mac (voz própria primeiro, `say` como reserva). O clone de
  runtime estava parado no PR #131, sem o código: atualizar o runtime faz
  parte do deploy.

### 7. Ele na tela inicial do Mac
- O Theo quer ver o JARVIS "do lado, falando comigo" na tela inicial, com um
  botão **Entrar no sistema**.
- Estado: **feito em parte** — `python3 11_SCRIPTS/install_mac_app.py` cria um
  bundle `.app` real em `~/Applications`, com ícone próprio, que abre o cockpit
  numa janela dedicada. Aparece no Launchpad e no Spotlight, e pode ser fixado
  no Dock.
- Falta o "ele do lado falando comigo" na área de trabalho: isso é uma janela
  flutuante sempre visível, e precisa de decisão de formato com o Theo.

## Bloqueio aberto — qualidade da voz

O Piper local é masculino e ilimitado, mas é um modelo `medium`: o pt-BR do
Piper não tem versão `high`, e o Mac só tem vozes compactas instaladas. Nenhum
ajuste de timbre transforma isso em voz humana. Sair desse patamar depende de
uma credencial: `OPENAI_API_KEY` (a cadeia `gpt-4o-mini-tts` já está pronta e
custa centavos por dia) ou ElevenLabs Starter, US$ 5/mês — a cota grátis atual
zerou e só volta em 07/09/2026.

## Regras que valem para todos os itens

- Nada entra sem validação real: comando executado de verdade, output colado.
- A voz nunca cai de nível em silêncio — se cair, o cockpit diz por quê
  (`GET /voice-status`).
- Não clonamos voz de pessoa real; replicamos estilo.
