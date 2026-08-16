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

O Piper continua útil como fallback leve, mas o modelo pt-BR disponível é `medium` e soa sintético. O Chatterbox Multilingual é um TTS neural aberto, suporta português, MPS/CPU/CUDA e clonagem zero-shot por áudio de referência.

O objetivo não é imitar uma pessoa identificável. A referência deve ser uma voz própria, licenciada ou criada para o projeto.

## Custo

A síntese local não cobra por caractere, minuto ou chamada de API.

O código do Chatterbox é open-source (MIT) e os pesos são baixados localmente na primeira carga. Isso não torna hardware/VPS/energia gratuitos: o custo é apenas de infraestrutura já utilizada, não de TTS por uso.

## Instalação recomendada no Mac

Chatterbox requer Python 3.10+; no JARVIS usamos Python 3.11 em ambiente isolado:

```bash
cd ~/CAMINHO/jarvis-agent-os
python3.11 -m venv .venv-voice
source .venv-voice/bin/activate
python -m pip install --upgrade pip
pip install piper-tts
```

### Importante: PyPI 0.1.7 x Multilingual V3

Em 16/08/2026 foi validado no Mac do Theo que `pip install chatterbox-tts` instala a versão 0.1.7 cuja API publicada ainda não aceita o argumento `t3_model`. O repositório oficial atual já aceita `t3_model="v3"` em `ChatterboxMultilingualTTS.from_pretrained()`.

O servidor do JARVIS é compatível com os dois casos: se a API antiga estiver instalada ele carrega o multilingual padrão e deixa isso explícito no `/health`; para testar V3 explicitamente, instale o código oficial atual:

```bash
python -m pip install --upgrade --force-reinstall \
  'chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git@master'
```

O primeiro start baixa os pesos do Chatterbox:

```bash
python 11_SCRIPTS/local_tts_server.py --engine chatterbox --device mps
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

## Validação real

Confirmado no Mac do Theo em 16/08/2026:

1. Python 3.11.16 instalado via Homebrew.
2. `.venv-voice` criado e ativado.
3. `chatterbox-tts 0.1.7`, PyTorch 2.6 e `piper-tts 1.7.0` instalados.
4. primeira tentativa com `--device mps` chegou ao carregador do Chatterbox, mas falhou porque a API PyPI 0.1.7 não reconhecia `t3_model`.
5. compatibilidade corrigida na branch para não derrubar o servidor em versões sem esse seletor.

Ainda falta validar:

1. carregar o motor após a correção.
2. `/health` confirmar engine/model/device real.
3. gerar e reproduzir WAV real no Mac.
4. comparar Chatterbox × ElevenLabs × Piper.
5. reinstalar LaunchAgent e testar saudação no boot.

Até esses testes acontecerem, o status correto é **integração preparada e dependências instaladas; áudio Chatterbox ainda não validado**.
