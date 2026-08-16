# Voz própria do JARVIS

## Estado atual

A voz local agora foi preparada para sair do teto do Piper sem mudar a API usada pelo restante do JARVIS.

Ordem local:

```text
Chatterbox Multilingual V3 -> Piper -> macOS `say`
```

O servidor continua ouvindo em:

```text
POST http://127.0.0.1:8123/speech
```

Portanto `device_worker.py` e o restante do cockpit não precisam conhecer o motor interno.

## Por que Chatterbox

O Piper continua útil como fallback leve, mas o modelo pt-BR disponível é `medium` e soa sintético. O Chatterbox Multilingual V3 é um TTS neural aberto de 500M parâmetros, suporta português, MPS/CPU/CUDA e clonagem zero-shot por áudio de referência.

O objetivo não é imitar uma pessoa identificável. A referência deve ser uma voz própria, licenciada ou criada para o projeto.

## Custo

A síntese local não cobra por caractere, minuto ou chamada de API.

O código do Chatterbox é open-source (MIT) e os pesos são baixados localmente na primeira carga. Isso não torna hardware/VPS/energia gratuitos: o custo é apenas de infraestrutura já utilizada, não de TTS por uso.

## Instalação recomendada no Mac

Chatterbox foi desenvolvido/testado em Python 3.11. Instale em ambiente isolado:

```bash
cd ~/CAMINHO/jarvis-agent-os
python3.11 -m venv .venv-voice
source .venv-voice/bin/activate
python -m pip install --upgrade pip
pip install chatterbox-tts piper-tts
```

O primeiro start baixa os pesos do Chatterbox:

```bash
python 11_SCRIPTS/local_tts_server.py --engine chatterbox
```

Health check:

```bash
curl -s http://127.0.0.1:8123/health
```

Teste de fala:

```bash
curl -s -X POST http://127.0.0.1:8123/speech \
  -H 'Content-Type: application/json' \
  -d '{"text":"Bem-vindo, Theo. Sistemas no ar."}' \
  -o /tmp/jarvis-chatterbox.wav

afplay /tmp/jarvis-chatterbox.wav
```

## Voz de referência

Para aproximar a identidade vocal desejada, use um trecho limpo de aproximadamente 5–15 segundos de uma voz que o projeto tenha direito de utilizar:

```text
~/Library/Application Support/JARVIS/voices/jarvis-reference.wav
```

Subir:

```bash
python 11_SCRIPTS/local_tts_server.py \
  --engine chatterbox \
  --reference ~/Library/Application\ Support/JARVIS/voices/jarvis-reference.wav
```

Controles por requisição:

```json
{
  "text": "Senhor, todos os sistemas estão operacionais.",
  "cfg_weight": 0.35,
  "exaggeration": 0.5
}
```

`cfg_weight` menor tende a preservar uma cadência mais deliberada. O perfil de pitch/FFmpeg usado no Piper não é aplicado ao Chatterbox por padrão porque pode degradar a naturalidade.

## Fallback Piper

O Piper não foi removido. Para forçar:

```bash
python 11_SCRIPTS/local_tts_server.py \
  --engine piper \
  --voice ~/Library/Application\ Support/JARVIS/voices/cadu.onnx
```

Para modo automático com Chatterbox primeiro e Piper de reserva:

```bash
python 11_SCRIPTS/local_tts_server.py \
  --engine auto \
  --voice ~/Library/Application\ Support/JARVIS/voices/cadu.onnx \
  --reference ~/Library/Application\ Support/JARVIS/voices/jarvis-reference.wav
```

Se Chatterbox não estiver instalado ou falhar na síntese, o mesmo processo tenta o Piper.

## Iniciar junto com o Mac

Depois que o teste de voz estiver aprovado:

```bash
python 11_SCRIPTS/local_tts_server.py \
  --engine auto \
  --voice ~/Library/Application\ Support/JARVIS/voices/cadu.onnx \
  --reference ~/Library/Application\ Support/JARVIS/voices/jarvis-reference.wav \
  --install-agent
```

O LaunchAgent continua sendo:

```text
ai.theopadilha.jarvis-voice
```

Logs:

```text
09_LOGS/voice-server.log
09_LOGS/voice-server-error.log
```

## O que ainda precisa de validação real

O código está preparado, mas não chamar de concluído até verificar no Mac:

1. `pip install chatterbox-tts` em Python 3.11.
2. carregamento do modelo em MPS no MacBook.
3. `/health` retornando `engine=chatterbox-v3`.
4. WAV gerado e reproduzido pelo `afplay`.
5. comparação A/B com ElevenLabs e Piper.
6. reinício do LaunchAgent e saudação real no boot.

Até esses testes acontecerem, o status correto é **integração preparada em branch; runtime Chatterbox ainda não validado no Mac**.
