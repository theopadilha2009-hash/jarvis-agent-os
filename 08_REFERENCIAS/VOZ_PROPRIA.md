# Voz própria do JARVIS

A voz paga é a melhor, mas ela acaba: o free tier da ElevenLabs esgota e o
cockpit cai para a voz do navegador, que é a compacta do sistema. Este é o
caminho para ter uma voz neural **nossa**, sem cota, sem chave e sem prazo.

## Como o cockpit escolhe a voz

```
ElevenLabs (pool de chaves)  →  OpenAI TTS  →  voz própria  →  voz do navegador
```

Cada camada só entra quando a anterior falha por cota, autorização, rede ou
ausência de chave. `GET /voice-status` diz qual está no ar e quanto sobrou.

## O timbre

O alvo é o mordomo britânico falando português: barítono quente, ritmo medido,
dicção precisa, autoridade serena, humor seco só numa leve inflexão. Isso vive
em dois lugares — `VOICE_DIRECTION` (instrução enviada ao TTS da OpenAI) e
`VOICE_PROFILE` (cadeia de áudio aplicada à voz local: pitch para baixo, tempo
compensado, corte de graves sujos, compressão suave e um eco curto de sala).

## Subir a voz própria

O motor principal é o Pocket TTS no catálogo aprovado (`portuguese` +
`bill_boerst`), no venv `~/.venv-pocket`. Config: env `JARVIS_TTS_ENGINE` /
`JARVIS_TTS_LANGUAGE` / `JARVIS_TTS_VOICE` ou
`~/Library/Application Support/JARVIS/voice-lock/VOICE_CONFIG.txt`.

```bash
python3 11_SCRIPTS/local_tts_server.py
```

O processo carrega o modelo uma vez e atende `POST /speech` com WAV cru —
o mesmo comportamento da CLI `pocket-tts generate --language portuguese
--voice bill_boerst --text "…"`. Sem cloning, sem WAV como `--voice`.

Piper continua como fallback se Pocket falhar. Para forçar só o Piper:

```bash
pip3 install piper-tts

mkdir -p 05_EXECUCAO/voices && cd 05_EXECUCAO/voices
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx.json
cd -

python3 11_SCRIPTS/local_tts_server.py --engine piper --voice 05_EXECUCAO/voices/pt_BR-cadu-medium.onnx
```

Ajustes úteis no Piper: `--pitch 0.90` deixa mais grave, `--tempo 1.06`
compensa a duração, `--raw` devolve o Piper puro para comparar, `--token`
exige `X-Jarvis-Voice-Token` em cada chamada.

## Deixar a voz de pé desde o boot

A saudação de boas-vindas sai pelo alto-falante do Mac, e quem sintetiza é este
servidor. Se ele não estiver rodando, a fala cai para o `say` do sistema, que é
uma voz compacta. Registre como serviço:

```bash
python3 11_SCRIPTS/local_tts_server.py --install-agent
```

O timbre padrão (`--pitch 0.90 --tempo 1.06`, voz `cadu`) foi escolhido pelo Theo
numa comparação às cegas entre quatro combinações de voz e gravidade.

Guarde o modelo fora do repositório e fora de `/tmp` — um `.onnx` num diretório
temporário desaparece e leva a voz junto. `~/Library/Application Support/JARVIS/voices/`
é o lugar. Logs em `09_LOGS/voice-server.log`.

Medido num MacBook: 0,46 s para carregar o modelo e 0,55 s para sintetizar uma
frase — mais rápido que a chamada remunerada.

## Ligar no gateway

```bash
SELF_HOSTED_TTS_URL=http://127.0.0.1:8123/speech python3 api/index.py
```

Em produção a Vercel precisa alcançar o servidor, e o Mac de casa não é
alcançável. Duas saídas:

- **VPS** (o caminho estável): rode o mesmo script atrás do Traefik com HTTPS e
  um token, e configure `SELF_HOSTED_TTS_URL` e `SELF_HOSTED_TTS_TOKEN` no
  projeto da Vercel.
- **Túnel** (para testar): `cloudflared tunnel --url http://127.0.0.1:8123`
  devolve uma URL HTTPS temporária.

## O teto desta voz

O pt-BR do Piper só existe em `medium` (e um `low`): não há modelo `high` para
subir de nível, e o Mac tem apenas vozes compactas instaladas. Nenhum ajuste de
timbre transforma isso em voz humana — é o teto do que roda de graça nesta
máquina. Passar desse ponto depende de `OPENAI_API_KEY` (a cadeia
`gpt-4o-mini-tts` já está pronta) ou de um plano pago da ElevenLabs.

## O que esta voz não é

Ela não imita o Paul Bettany nem nenhuma pessoa real — clonar a voz de alguém
identificável sem consentimento não entra aqui. O que replicamos é o *estilo*:
as características que fazem a voz soar como um mordomo competente. Para clonar
uma voz, use uma que seja sua ou que você tenha direito de usar.
