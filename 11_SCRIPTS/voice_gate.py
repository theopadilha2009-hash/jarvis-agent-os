#!/usr/bin/env python3
"""Gate acustico de wake word para o JARVIS (arquivo .wav -> JSON de decisao).

Substitui a dependencia do STT da Apple na deteccao de "Jarvis":
  1. Silero VAD (silero_vad.onnx, snakers4) carregado direto com onnxruntime
     decide se ha fala no audio.
  2. openWakeWord (modelo hey_jarvis_v0.1.onnx, backend onnx) pontua o
     wake word por janela de 80 ms; o score final e o maximo.

Sem rede em runtime (modelos baixados no install) e sem torch.
Rodar com o venv pocket (tem onnxruntime/scipy/openwakeword):

    ~/.venv-pocket/bin/python 11_SCRIPTS/voice_gate.py <arquivo.wav> [--threshold 0.5]

Instalacao one-shot (uma vez por maquina; /tmp e volatil, re-rodar apos reboot):

    ~/.venv-pocket/bin/pip install --no-deps openwakeword
    ~/.venv-pocket/bin/pip install onnxruntime scikit-learn
    mkdir -p /tmp/voicegate-models && cd /tmp/voicegate-models
    BASE=https://github.com/dscripka/openWakeWord/releases/download/v0.5.1
    for f in melspectrogram.onnx embedding_model.onnx hey_jarvis_v0.1.onnx; do
        curl -sL "$BASE/$f" -o "$f"
    done
    curl -sL https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx \\
        -o /tmp/voicegate-models/silero_vad.onnx

Saida:
    {"vad": true, "wake": 0.83, "wake_hit": true, ...}
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import warnings

import numpy as np

SR = 16000
VAD_WINDOW = 512          # janela do Silero VAD em 16 kHz
WAKE_CHUNK = 1280         # janela do openWakeWord (80 ms em 16 kHz)
PAD_SAMPLES = 8000        # 0.5 s de silencio antes/depois ao pontuar
VAD_PROB_THRESHOLD = 0.5  # probabilidade de fala que conta como "vad: true"
WAKE_LABEL = "hey_jarvis_v0.1"
DEFAULT_MODELS_DIR = os.environ.get(
    "VOICE_GATE_MODELS_DIR",
    str(pathlib.Path.home() / "Library" / "Application Support" / "JARVIS" / "models"),
)


def load_audio_16k(path: str) -> np.ndarray:
    """Le .wav (header tolerante, o TTS local grava tamanho estourado) e reamostra p/ 16 kHz."""
    from scipy.io import wavfile
    from scipy.signal import resample_poly

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sample_rate, raw = wavfile.read(path)
    if raw.ndim == 2:
        raw = raw.mean(axis=1)
    if raw.dtype == np.int16:
        audio = raw.astype(np.float32) / 32768.0
    elif np.issubdtype(raw.dtype, np.integer):
        audio = raw.astype(np.float32) / float(np.iinfo(raw.dtype).max)
    else:
        audio = raw.astype(np.float32)
    if sample_rate != SR:
        audio = resample_poly(audio, SR, int(sample_rate))
    return np.clip(audio, -1.0, 1.0)


class SileroVad:
    """Silero VAD onnx em streaming de janelas de 512 amostras."""

    def __init__(self, model_path: str):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self.session = ort.InferenceSession(model_path, sess_options=opts,
                                            providers=["CPUExecutionProvider"])
        state_inputs = [i.name for i in self.session.get_inputs() if i.name not in ("input", "sr")]
        state_outputs = [o.name for o in self.session.get_outputs() if o.name != "output"]
        # pareamento posicional: (h, c) -> (hn, cn) ou state -> stateN
        self.state_io = list(zip(state_inputs, state_outputs))
        self.shapes = {i.name: i.shape for i in self.session.get_inputs()
                       if i.name not in ("input", "sr")}

    def _zeros_state(self) -> dict:
        feed = {}
        for name, shape_spec in self.shapes.items():
            shape = []
            for dim in shape_spec:
                shape.append(1 if not isinstance(dim, int) or dim <= 0 else dim)
            feed[name] = np.zeros(shape, dtype=np.float32)
        return feed

    def reset(self) -> None:
        self.state = self._zeros_state()

    def probabilities(self, audio: np.ndarray) -> list[float]:
        self.reset()
        probs = []
        sr = np.array(SR, dtype=np.int64)
        for start in range(0, len(audio) - VAD_WINDOW + 1, VAD_WINDOW):
            window = audio[start:start + VAD_WINDOW][None, :].astype(np.float32)
            feed = {**self.state, "input": window, "sr": sr}
            out = self.session.run(None, feed)
            probs.append(float(out[0][0][0]))
            for (in_name, _out_name), value in zip(self.state_io, out[1:]):
                self.state[in_name] = value
        return probs


class WakeScorer:
    """openWakeWord hey_jarvis em streaming de chunks de 80 ms."""

    def __init__(self, models_dir: str):
        from openwakeword.model import Model

        self.model = Model(
            wakeword_models=[os.path.join(models_dir, f"{WAKE_LABEL}.onnx")],
            inference_framework="onnx",
            melspec_model_path=os.path.join(models_dir, "melspectrogram.onnx"),
            embedding_model_path=os.path.join(models_dir, "embedding_model.onnx"),
        )

    def score(self, audio_16k: np.ndarray) -> float:
        """Score final = maximo sobre as janelas; recebe float32 [-1,1] e realimenta o stream."""
        self.model.reset()
        pcm = (np.concatenate([
            np.zeros(PAD_SAMPLES, dtype=np.float32),
            audio_16k,
            np.zeros(PAD_SAMPLES, dtype=np.float32),
        ]) * 32768.0).astype(np.int16)
        scores = []
        for start in range(0, len(pcm) - WAKE_CHUNK + 1, WAKE_CHUNK):
            prediction = self.model.predict(pcm[start:start + WAKE_CHUNK])
            scores.append(max(float(v) for v in prediction.values()))
        return max(scores) if scores else 0.0


def evaluate(path: str, models_dir: str, threshold: float) -> dict:
    audio = load_audio_16k(path)
    vad = SileroVad(os.path.join(models_dir, "silero_vad.onnx"))
    vad_probs = vad.probabilities(audio)
    vad_score = max(vad_probs) if vad_probs else 0.0
    wake = WakeScorer(models_dir).score(audio)
    return {
        "file": path,
        "duration_s": round(len(audio) / SR, 2),
        "vad": bool(vad_score >= VAD_PROB_THRESHOLD),
        "vad_score": round(vad_score, 4),
        "wake": round(wake, 4),
        "wake_hit": bool(wake >= threshold),
        "threshold": threshold,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate acustico de wake word JARVIS (.wav -> JSON)")
    parser.add_argument("wav", help="arquivo .wav de entrada")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="score minimo de wake word (default: 0.5)")
    parser.add_argument("--models-dir", default=DEFAULT_MODELS_DIR,
                        help=f"diretorio dos modelos onnx (default: {DEFAULT_MODELS_DIR})")
    args = parser.parse_args(argv)

    missing = [f for f in ("silero_vad.onnx", "melspectrogram.onnx",
                           "embedding_model.onnx", f"{WAKE_LABEL}.onnx")
               if not os.path.exists(os.path.join(args.models_dir, f))]
    if missing:
        print(f"modelos ausentes em {args.models_dir}: {missing}; "
              f" rode o bloco de instalacao do docstring", file=sys.stderr)
        return 1
    if not os.path.exists(args.wav):
        print(f"arquivo nao encontrado: {args.wav}", file=sys.stderr)
        return 2

    result = evaluate(args.wav, args.models_dir, args.threshold)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
