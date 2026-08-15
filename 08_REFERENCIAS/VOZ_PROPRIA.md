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

O modelo não vem no repositório. Baixe uma voz pt-BR do Piper e aponte:

```bash
pip3 install piper-tts

mkdir -p 05_EXECUCAO/voices && cd 05_EXECUCAO/voices
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx.json
cd -

python3 11_SCRIPTS/local_tts_server.py --voice 05_EXECUCAO/voices/pt_BR-cadu-medium.onnx
```

Ajustes úteis: `--pitch 0.90` deixa mais grave, `--tempo 1.06` compensa a
duração, `--raw` devolve o Piper puro para comparar, `--token` exige
`X-Jarvis-Voice-Token` em cada chamada.

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

## O que esta voz não é

Ela não imita o Paul Bettany nem nenhuma pessoa real — clonar a voz de alguém
identificável sem consentimento não entra aqui. O que replicamos é o *estilo*:
as características que fazem a voz soar como um mordomo competente. Para clonar
uma voz, use uma que seja sua ou que você tenha direito de usar.
