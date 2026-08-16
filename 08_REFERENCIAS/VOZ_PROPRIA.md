# Voz própria do JARVIS

## Voz escolhida

A referência aprovada pelo Theo é `bill_boerst.wav`.

Ela fica fora do Git em:

```text
~/Library/Application Support/JARVIS/voices/bill_boerst.wav
```

Depois da validação, a identidade deve ser exportada para:

```text
~/Library/Application Support/JARVIS/voices/bill_boerst.safetensors
```

O `.safetensors` é o formato preferido no uso diário porque evita reprocessar o WAV a cada boot.

## Motor local

O motor preparado é **Pocket-TTS**.

Ordem local:

```text
Pocket-TTS (Bill) -> Piper -> macOS say
```

O contrato usado pelo restante do JARVIS continua igual:

```text
POST http://127.0.0.1:8123/speech
```

O Pocket-TTS roda localmente, aceita WAV ou voice-state `.safetensors` como referência e possui modelos em português. O perfil de pitch/FFmpeg do Piper não é aplicado ao Pocket-TTS por padrão para não deformar a identidade aprovada.

## Instalação isolada no Mac

Não reutilizar o ambiente do Chatterbox. Criar ambiente próprio:

```bash
python3.11 -m venv ~/.venv-pocket
source ~/.venv-pocket/bin/activate
python -m pip install --upgrade pip
python -m pip install "pocket-tts==2.1.0" piper-tts
```

Os pesos do Pocket-TTS são baixados localmente na primeira carga. Se o Hugging Face solicitar aceite/login para o modelo, isso é uma ação humana única antes do primeiro download.

## Preparar a voz Bill

Copiar a referência aprovada para o diretório permanente:

```bash
mkdir -p ~/Library/Application\ Support/JARVIS/voices
cp ~/Desktop/jarvis-vozes-humanas/bill_boerst.wav \
  ~/Library/Application\ Support/JARVIS/voices/bill_boerst.wav
```

Primeiro teste, sem alterar o JARVIS ativo:

```bash
source ~/.venv-pocket/bin/activate

python 11_SCRIPTS/local_tts_server.py \
  --engine pocket \
  --reference ~/Library/Application\ Support/JARVIS/voices/bill_boerst.wav \
  --language portuguese \
  --port 8124
```

`portuguese` é o modelo menor para resposta rápida. Se a dicção/qualidade não for suficiente, comparar com `portuguese_24l`, que é maior e mais lento.

Health check:

```bash
curl -s http://127.0.0.1:8124/health
```

Teste de fala:

```bash
curl -s \
  -H 'Content-Type: application/json' \
  -d '{"text":"Theo, todos os sistemas estão operacionais. Estou pronto."}' \
  http://127.0.0.1:8124/speech \
  -o ~/Desktop/jarvis-bill-teste.wav

open -a 'QuickTime Player' ~/Desktop/jarvis-bill-teste.wav
```

## Congelar a identidade para carregar rápido

Depois que a voz em português for aprovada:

```bash
source ~/.venv-pocket/bin/activate

pocket-tts export-voice \
  ~/Library/Application\ Support/JARVIS/voices/bill_boerst.wav \
  ~/Library/Application\ Support/JARVIS/voices/bill_boerst.safetensors \
  --language portuguese
```

Depois o servidor usa o `.safetensors`:

```bash
python 11_SCRIPTS/local_tts_server.py \
  --engine pocket \
  --reference ~/Library/Application\ Support/JARVIS/voices/bill_boerst.safetensors \
  --language portuguese
```

## Iniciar junto com o Mac

Só depois do teste real aprovado em `8124`:

```bash
python 11_SCRIPTS/local_tts_server.py \
  --engine pocket \
  --reference ~/Library/Application\ Support/JARVIS/voices/bill_boerst.safetensors \
  --language portuguese \
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

## Fallback Piper

O Piper não foi removido. Para manter reserva no mesmo processo:

```bash
python 11_SCRIPTS/local_tts_server.py \
  --engine auto \
  --reference ~/Library/Application\ Support/JARVIS/voices/bill_boerst.safetensors \
  --language portuguese \
  --voice ~/Library/Application\ Support/JARVIS/voices/cadu.onnx
```

## Estado real

Confirmado:
- `bill_boerst.wav` foi escolhido pelo Theo como identidade desejada;
- o servidor foi preparado em branch isolada para Pocket-TTS;
- o endpoint `/speech` foi preservado;
- áudio/modelos não são commitados no Git;
- `main` e produção não foram alteradas.

Ainda precisa de validação no Mac:
1. instalar Pocket-TTS no ambiente `~/.venv-pocket`;
2. carregar `portuguese` com `bill_boerst.wav`;
3. gerar e ouvir uma frase real;
4. medir latência;
5. exportar `bill_boerst.safetensors`;
6. só então trocar o serviço da porta `8123` e instalar o LaunchAgent.

Sem esses passos, o status é **integração preparada; voz Bill ainda não ativa no JARVIS real**.
