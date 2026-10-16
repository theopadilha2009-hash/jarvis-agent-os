#!/usr/bin/env python3
"""Treino do wake word "Jarvis" (palavra solta) para o gate acustico do JARVIS.

O modelo pre-treinado hey_jarvis_v0.1 so reconhece "Hey Jarvis" (0.77-0.98);
"Jarvis" solto fica em ~0.13. Este script gera dataset sintetico com o TTS
local (POST 8123/speech: rafael, javert, Antonio/edge), aplica augmentacao
(ruido, pitch, velocidade, recorte), treina uma cabeca binaria sobre os
embeddings congelados do speech_embedding (melspectrogram.onnx +
embedding_model.onnx do openwakeword) com warm-start dos pesos oficiais e
exporta um ONNX plugavel no mesmo formato do hey_jarvis (input [1,16,96]
float32 -> score sigmoid [1,1]).

Pipeline oficial do openwakeword (openwakeword/train.py) exige tensorflow
(import na linha 579) e GPU/TPU do Colab; aqui segue a alternativa de
transfer learning prevista no escopo: embedding congelado + cabeca onnx.

Uso (venv pocket):

    ~/.venv-pocket/bin/python 11_SCRIPTS/train_wake_jarvis.py dataset
    ~/.venv-pocket/bin/python 11_SCRIPTS/train_wake_jarvis.py train
    ~/.venv-pocket/bin/python 11_SCRIPTS/train_wake_jarvis.py validate

Dataset em /tmp/jarvis-wake-dataset (volatil); modelo final em
~/Library/Application Support/JARVIS/models/jarvis_free.onnx.

Saida:
    Status real: ... / Producao: nada alterado. (dataset e train)
    Tabela de validacao via voice_gate.py CLI real (validate).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import shutil
import subprocess
import sys
import warnings

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from voice_gate import (  # noqa: E402  (mesmo loader do gate real)
    DEFAULT_MODELS_DIR,
    WAKE_CHUNK,
    load_audio_16k,
)

SR = 16000
CLIP_SAMPLES = 2 * SR            # 2.0 s por clip de treino/validacao
PAD_SAMPLES = 8000               # mesmo pad do voice_gate ao pontuar
FRAME_SAMPLES = WAKE_CHUNK       # 1280 = 80 ms = 1 frame de feature
N_FRAMES = 16                    # janela de frames que o modelo ve
FREE_FRAME_MS = 80

TTS_URL = os.environ.get("JARVIS_LOCAL_TTS_URL", "http://127.0.0.1:8123/speech")
DATA_DIR = pathlib.Path("/tmp/jarvis-wake-dataset")
FINAL_MODEL = pathlib.Path(DEFAULT_MODELS_DIR) / "jarvis_free.onnx"

POS_TEXTS = [
    "Jarvis", "Ei Jarvis", "Sim, Jarvis?", "Jarvis, esta aí?", "Jarvis? Tudo bem?",
    "Jarvis, pode vir", "Sr. Jarvis", "Ola Jarvis", "E ai, Jarvis", "Jarvis!!",
    "JARVIS!", "Jarvis...", "Claro, Jarvis", "Jarvis, me escuta",
]
# formas exclusivas de validacao (TTS deterministico: texto+voz repetidos = clip identico)
VAL_POS_TEXTS = ["Jarvis,", "Jarvis?", "Jarvis!", "Jarvis.", "Jarvis...", "jarvis",
                 "JARVIS", "Ola, Jarvis?", "Jarvis! Preciso de voce", "Pode ser, Jarvis?"]
# textos negativos: fala comum, near-miss (Jarbas/jardim/justica/Justin) e frases longas
NEG_TEXTS = [
    "bom dia", "boa tarde", "boa noite", "que horas sao", "que dia e hoje",
    "abre o spotify", "toca musica", "me lembra de ligar pro dentista amanha",
    "resume meus emails", "quanto esta o dolar", "agenda de hoje",
    "como esta o tempo", "desliga a luz da sala", "vou sair agora",
    "chama o Ruan no WhatsApp", "status do projeto", "oi", "ola",
    "tudo bem", "obrigado", "por favor", "sim", "nao", "chama o Jarvis no WhatsApp",
    "Hey Justin", "Ei Justin", "justin bieber", "jardim", "Jarbas",
    "justica", "jantar", "jarro de agua", "salva isso", "anota ai",
    "quanto tempo falta", "me conta uma piada", "clica ali", "fecha a aba",
    "estou ocupado", "modo foco", "prepare o meu dia",
    "quando eu chegar em casa quero que voce prepare uma lista com tudo que precisamos comprar no mercado esta semana",
    "lembra de revisar o pull request antes da reuniao de sexta com o time de desenvolvimento",
    "sera que vale a pena migrar esse servico antes do fim do mes ou deixamos para o proximo ciclo",
    "caderneta", "girassol", "jacaranda", "járvia",
]
NEG_NOISE_SECONDS = 8            # clips sinteticos de ruido/silencio
SEED = 1234


# ---------------------------------------------------------------- utils -----
def log(msg: str) -> None:
    print(msg, flush=True)


def status_real(created: list[str], tested: str, not_validated: str) -> None:
    print("\nSTATUS REAL")
    print(f"- Created: {', '.join(created) if created else '-'}")
    print(f"- Modified: nada")
    print(f"- Tested: {tested}")
    print(f"- Not validated: {not_validated}")
    print("- Production: nada alterado.")


def tts_speech(text: str, voice: str, out_path: pathlib.Path, prefer_edge: bool = False) -> bool:
    """POST 8123/speech -> wav em out_path. False se falhar."""
    import requests

    body = {"text": text, "voice": voice}
    if prefer_edge:
        body["prefer_edge"] = True
    try:
        r = requests.post(TTS_URL, json=body, timeout=40)
        audio = r.content
    except requests.RequestException as exc:
        log(f"  tts falhou ({text!r}, {voice}): {exc}")
        return False
    if not audio or audio[:4] != b"RIFF":
        log(f"  tts resposta invalida ({text!r}, {voice}): {audio[:80]!r}")
        return False
    out_path.write_bytes(audio)
    return True


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def make_noise(kind: str, n: int, rng: np.random.Generator) -> np.ndarray:
    if kind == "white":
        return rng.normal(0, 1, n).astype(np.float32)
    if kind == "pink":  # aproximacao por filtro 1/f simples
        white = rng.normal(0, 1, n).astype(np.float32)
        from scipy.signal import lfilter
        return lfilter([0.049922035, -0.095993537, 0.050612699, -0.004408786],
                       [1, -2.494956002, 2.017265875, -0.522189400], white).astype(np.float32)
    if kind == "brown":
        out = np.cumsum(rng.normal(0, 1, n)).astype(np.float32)
        return out / (np.abs(out).max() + 1e-9)
    if kind == "modulated":  # "chuveiro/vento": ruido com envelope lento
        white = rng.normal(0, 1, n).astype(np.float32)
        env = np.convolve(rng.normal(0, 1, n // 400 + 1), np.ones(3) / 3, mode="same")
        env = np.interp(np.linspace(0, len(env) - 1, n), np.arange(len(env)), env)
        env = 0.3 + 0.7 * np.abs(env) / (np.abs(env).max() + 1e-9)
        return (white * env).astype(np.float32)
    raise ValueError(kind)


def speed_change(audio: np.ndarray, factor: float, rng: np.random.Generator) -> np.ndarray:
    """Tape-speed: muda pitch e duracao juntos (fator >1 = mais rapido)."""
    from scipy.signal import resample_poly
    from math import gcd
    up, down = int(round(factor * 100)), 100
    g = gcd(up, down)
    return resample_poly(audio, up // g, down // g).astype(np.float32)


def pitch_change(audio: np.ndarray, factor: float) -> np.ndarray:
    """Pitch shift com duracao preservada (ressample + reinterpola)."""
    from scipy.signal import resample_poly
    from math import gcd
    up, down = int(round(factor * 100)), 100
    g = gcd(up, down)
    shifted = resample_poly(audio, up // g, down // g).astype(np.float32)
    idx = np.linspace(0, len(shifted) - 1, len(audio))
    return np.interp(idx, np.arange(len(shifted)), shifted).astype(np.float32)


def add_noise(audio: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    kinds = rng.choice(["white", "pink", "brown", "modulated"])
    noise = make_noise(kinds, len(audio), rng)
    sig_pow = float(np.mean(audio ** 2)) + 1e-12
    noise_pow = float(np.mean(noise ** 2)) + 1e-12
    noise *= np.sqrt(sig_pow / noise_pow / (10 ** (snr_db / 10)))
    return (audio + noise).astype(np.float32)


def augment(audio: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = audio.copy()
    if rng.random() < 0.6:
        out = speed_change(out, float(rng.uniform(0.90, 1.12)), rng)
    if rng.random() < 0.5:
        out = pitch_change(out, float(rng.uniform(0.94, 1.06)))
    if rng.random() < 0.8:
        out = add_noise(out, float(rng.uniform(5, 25)), rng)
    if rng.random() < 0.4:
        out = out * float(rng.uniform(0.5, 1.4))
    return np.clip(out, -1.0, 1.0)


def fit_clip(audio: np.ndarray, rng: np.random.Generator | None,
             pad_jitter: bool = False) -> np.ndarray:
    """Pad/trunca para CLIP_SAMPLES com silencio nas bordas (estilo voice_gate)."""
    pad_total = CLIP_SAMPLES - len(audio)
    if pad_total < 0:
        start = 0
        if pad_jitter and rng is not None:
            start = int(rng.integers(0, -pad_total + 1))
        return audio[start:start + CLIP_SAMPLES]
    if pad_jitter and rng is not None:
        left = int(rng.integers(0, max(pad_total, 1)))
    else:
        left = pad_total // 2
    right = pad_total - left
    return np.concatenate([np.zeros(left, np.float32), audio,
                           np.zeros(right, np.float32)])


# -------------------------------------------------------------- dataset -----
def cmd_dataset(args: argparse.Namespace) -> int:
    rng = np.random.default_rng(SEED)
    random.seed(SEED)
    data_dir = pathlib.Path(args.out)
    for sub in ("pos_raw", "neg_raw", "pos_aug", "neg_aug", "val_pos", "val_neg",
                "val_extra"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)
    voices = [("rafael", False), ("javert", False), ("Antonio", True)]

    def slug(text: str) -> str:
        keep = [c if c.isalnum() else "" for c in text.lower()][:20]
        return "".join(keep) or "clip"

    n_pos = n_neg = fail = 0
    manifest = {"pos_raw": [], "neg_raw": [], "val_pos": [], "val_neg": []}

    # ---- positivos: treino e held-out com TEXTOS diferentes (sem vazamento)
    log("== positivos treino (Jarvis solto) ==")
    for pi, text in enumerate(POS_TEXTS):
        for voice, edge in voices:
            name = f"pos_{pi:02d}_{slug(text)}_{voice}.wav"
            path = data_dir / "pos_raw" / name
            if tts_speech(text, voice, path, prefer_edge=edge):
                manifest["pos_raw"].append(name)
                n_pos += 1
            else:
                fail += 1

    log("== positivos held-out (formas novas) ==")
    for vi, text in enumerate(VAL_POS_TEXTS):
        for voice, edge in voices:
            name = f"val_pos_{vi:02d}_{slug(text)}_{voice}.wav"
            path = data_dir / "val_pos" / name
            if tts_speech(text, voice, path, prefer_edge=edge):
                manifest["val_pos"].append(name)
                n_pos += 1
            else:
                fail += 1

    # ---- extra informativo: "Hey Jarvis" (gatilho antigo) — fora dos alvos
    log("== extra: Hey Jarvis (gatilho antigo, informativo) ==")
    for voice, edge in voices[:2]:
        name = f"extra_hey_jarvis_{voice}.wav"
        if tts_speech("Hey Jarvis", voice, data_dir / "val_extra" / name, prefer_edge=edge):
            manifest.setdefault("val_extra", []).append(name)

    # ---- negativos: fala comum
    log("== negativos (fala comum + near-miss) ==")
    for j, text in enumerate(NEG_TEXTS):
        for voice, edge in voices:
            is_val = (j % 6 == 5)  # ~1/6 para held-out
            sub = "val_neg" if is_val else "neg_raw"
            name = f"neg_{j:02d}_{slug(text)}_{voice}.wav"
            path = data_dir / sub / name
            if tts_speech(text, voice, path, prefer_edge=edge):
                manifest[sub].append(name)
                n_neg += 1
            else:
                fail += 1

    # ---- negativos sinteticos: ruido/silencio puro
    log("== negativos sinteticos (ruido/silencio) ==")
    for k in range(NEG_NOISE_SECONDS):
        dur = float(rng.uniform(1.0, 2.5))
        n = int(dur * SR)
        kind = ["silence", "white", "pink", "brown", "modulated"][k % 5]
        if kind == "silence":
            clip = (rng.normal(0, 0.0005, n)).astype(np.float32)
        else:
            clip = make_noise(kind, n, rng)
            clip = (clip / (np.abs(clip).max() + 1e-9) * rng.uniform(0.02, 0.15)).astype(np.float32)
        name = f"neg_noise_{k:02d}_{kind}.wav"
        _write_wav(data_dir / "neg_raw" / name, clip, SR)
        manifest["neg_raw"].append(name)
        n_neg += 1

    # ---- augmentacao (apenas treino; held-out fica cru)
    log("== augment ==")
    from scipy.io import wavfile

    def augment_dir(sub_in: str, sub_out: str, variants: int) -> int:
        made = 0
        for name in manifest[sub_in]:
            audio = load_audio_16k(str(data_dir / sub_in / name))
            for v in range(variants):
                aug = augment(audio, np.random.default_rng(SEED + made * 17 + v))
                out_name = f"{pathlib.Path(name).stem}_aug{v}.wav"
                _write_wav(data_dir / sub_out / out_name, fit_clip(aug, np.random.default_rng(SEED + made), True), SR)
                made += 1
        return made

    n_pos_aug = augment_dir("pos_raw", "pos_aug", variants=16)
    n_neg_aug = augment_dir("neg_raw", "neg_aug", variants=3)

    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    log(f"Status real: dataset pronto em {data_dir} "
        f"(pos {n_pos}+{n_pos_aug}aug, neg {n_neg}+{n_neg_aug}aug, falhas {fail})")
    log("Produção: nada alterado.")
    return 0 if fail == 0 else 1


def _write_wav(path: pathlib.Path, audio: np.ndarray, sr: int) -> None:
    import wave

    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(pcm.tobytes())


# ----------------------------------------------------------------- train ----
def load_official_weights(models_dir: str) -> dict[str, np.ndarray]:
    """Le os initializers do hey_jarvis_v0.1.onnx (warm-start)."""
    import onnx

    model = onnx.load(os.path.join(models_dir, "hey_jarvis_v0.1.onnx"))
    return {init.name: onnx.numpy_helper.to_array(init) for init in model.graph.initializer}


def cmd_train(args: argparse.Namespace) -> int:
    import torch
    import torch.nn as nn
    from openwakeword.utils import AudioFeatures

    seed = SEED
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    data_dir = pathlib.Path(args.data)
    models_dir = args.models_dir

    # ---------------------------------------------------------- features ---
    log("== extraindo features (embeddings congelados) ==")
    af = AudioFeatures(
        melspec_model_path=os.path.join(models_dir, "melspectrogram.onnx"),
        embedding_model_path=os.path.join(models_dir, "embedding_model.onnx"),
        inference_framework="onnx",
    )

    def clip_features(audio: np.ndarray, positive: bool) -> list[tuple[np.ndarray, int]]:
        """Emula EXATAMENTE o WakeScorer.score do voice_gate: pad de 0.5 s,
        chunks de 1280 e UM score por chunk (get_features das ultimas 16
        frames). Cada chunk adiciona 2 frames ao buffer (hop de 40 ms), entao
        so as janelas alinhadas ao chunk existem em runtime e sao rotuladas."""
        pcm_full = np.concatenate([
            np.zeros(PAD_SAMPLES, np.float32),
            audio.astype(np.float32),
            np.zeros(PAD_SAMPLES, np.float32),
        ])
        pcm = (np.clip(pcm_full, -1.0, 1.0) * 32768).astype(np.int16)
        af.reset()
        rows: list[tuple[np.ndarray, int]] = []
        chunk_rms: list[float] = []
        for start in range(0, len(pcm) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
            af(pcm[start:start + FRAME_SAMPLES])
            feats = af.get_features(N_FRAMES)[0].astype(np.float32)  # [16, 96]
            chunk = pcm[start:start + FRAME_SAMPLES].astype(np.float32) / 32768.0
            chunk_rms.append(float(np.sqrt((chunk ** 2).mean() + 1e-12)))
            rows.append((feats, 0))  # rotulo definido abaixo
        if positive:
            thresh = max(0.008, 0.12 * max(chunk_rms))
            speech_chunks = [i for i, r in enumerate(chunk_rms) if r > thresh]
            for i in speech_chunks[-2:]:  # janelas de pico do runtime
                rows[i] = (rows[i][0], 1)
        return rows

    def collect(sub: str, positive: bool) -> tuple[list, int]:
        rows, clips = [], 0
        folder = data_dir / sub
        for path in sorted(folder.glob("*.wav")):
            audio = load_audio_16k(str(path))
            is_bg = "neg_noise_" in path.name
            rows.extend((f, lab, is_bg) for f, lab in clip_features(audio, positive))
            clips += 1
        return rows, clips

    pos_rows, pos_clips = collect("pos_raw", True)
    pos_rows += collect("pos_aug", True)[0]
    neg_rows, neg_clips = collect("neg_raw", False)
    neg_rows += collect("neg_aug", False)[0]
    log(f"janelas: pos={len(pos_rows)} ({pos_clips} clips), neg={len(neg_rows)} ({neg_clips} clips)")

    # fundo (silencio/ruido) entra SEMPRE, com repeticao; subamostra so a fala
    noise_rows = [r for r in neg_rows if r[2]]
    speech_neg = [r for r in neg_rows if not r[2]]
    target_speech_neg = int(len(pos_rows) * 2.0)
    if len(speech_neg) > target_speech_neg:
        idx = rng.choice(len(speech_neg), target_speech_neg, replace=False)
        speech_neg = [speech_neg[i] for i in idx]

    # silencio sintetico garantido (amplitudes variadas, incl. zeros exatos):
    # impede a cabeca de extrapolar alto em fundo sem fala
    bg_rows = []
    for amp in (0.0, 0.0003, 0.001, 0.003, 0.01):
        clip = (rng.normal(0, max(amp, 1e-6), CLIP_SAMPLES)).astype(np.float32)
        bg_rows.extend((f, 0, True) for f, _ in clip_features(clip, False))
    neg_rows = speech_neg + noise_rows * 3 + bg_rows * 3
    log(f"pos={len(pos_rows)}, neg={len(neg_rows)} "
        f"(fala {len(speech_neg)}, fundo {len(noise_rows) * 3 + len(bg_rows) * 3})")
    X = np.stack([f for f, _, _ in pos_rows] + [f for f, _, _ in neg_rows]).reshape(-1, N_FRAMES * 96)
    y = np.array([lab for _, lab, _ in pos_rows] + [lab for _, lab, _ in neg_rows], dtype=np.float32)
    perm = rng.permutation(len(y))
    X, y = X[perm], y[perm]
    n_val = max(1, int(len(y) * 0.1))
    Xt, yt = torch.tensor(X[n_val:], dtype=torch.float32), torch.tensor(y[n_val:])
    Xv, yv = torch.tensor(X[:n_val], dtype=torch.float32), torch.tensor(y[:n_val])
    log(f"treino={len(yt)} (pos={int(yt.sum())}), val={n_val} (pos={int(yv.sum())})")

    # ------------------------------------------------------------ modelo ---
    class WakeHead(nn.Module):
        """Mesma arquitetura do hey_jarvis.onnx: 1536->128-LN-ReLU->128-LN-ReLU->1."""

        def __init__(self) -> None:
            super().__init__()
            self.flat = nn.Flatten()
            self.fc1 = nn.Linear(1536, 128)
            self.ln1 = nn.LayerNorm(128)
            self.fc2 = nn.Linear(128, 128)
            self.ln2 = nn.LayerNorm(128)
            self.fc3 = nn.Linear(128, 1)
            self.act = nn.ReLU()
            self.sig = nn.Sigmoid()

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            h = self.act(self.ln1(self.fc1(self.flat(x))))
            h = self.act(self.ln2(self.fc2(h)))
            return self.sig(self.fc3(h))

    model = WakeHead()
    weights = load_official_weights(models_dir)
    with torch.no_grad():
        model.fc1.weight.copy_(torch.tensor(weights["model.1.weight"]))
        model.fc1.bias.copy_(torch.tensor(weights["model.1.bias"]))
        model.ln1.weight.copy_(torch.tensor(weights["model.2.weight"]))
        model.ln1.bias.copy_(torch.tensor(weights["model.2.bias"]))
        model.fc2.weight.copy_(torch.tensor(weights["model.4.weight"]))
        model.fc2.bias.copy_(torch.tensor(weights["model.4.bias"]))
        model.ln2.weight.copy_(torch.tensor(weights["model.5.weight"]))
        model.ln2.bias.copy_(torch.tensor(weights["model.5.bias"]))
        model.fc3.weight.copy_(torch.tensor(weights["model.7.weight"]))
        model.fc3.bias.copy_(torch.tensor(weights["model.7.bias"]))
    base_state = {k: v.clone() for k, v in model.state_dict().items()}

    # fine-tune completo (camadas base destravadas); os negativos de fundo
    # garantidos + LR baixo preservam a rejeicao do modelo original

    def score_max_janelas(net: nn.Module, Xb: torch.Tensor) -> np.ndarray:
        with torch.no_grad():
            return net(Xb).squeeze(1).numpy()

    from sklearn.metrics import roc_auc_score

    def evaluate(net: nn.Module, Xb: torch.Tensor, yb: torch.Tensor) -> dict:
        p = score_max_janelas(net, Xb)
        pos_p, neg_p = p[yb.numpy() == 1], p[yb.numpy() == 0]
        return {
            "auc": float(roc_auc_score(yb.numpy(), p)) if len(set(yb.numpy().tolist())) > 1 else 0.0,
            "pos_mean": float(pos_p.mean()) if len(pos_p) else 0.0,
            "neg_mean": float(neg_p.mean()) if len(neg_p) else 0.0,
            "neg_max": float(neg_p.max()) if len(neg_p) else 0.0,
        }

    log(f"baseline (pesos oficiais) janela-a-janela: {evaluate(model, Xv, yv)}")

    # ------------------------------------------------------------ treino ---
    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=0.0)
    pos_weight = 2.0

    def bce_weighted(out: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        eps = 1e-7
        p = out.clamp(eps, 1 - eps)
        loss = -(pos_weight * target * p.log() + (1 - target) * (1 - p).log())
        return loss.mean()
    best = {"auc": -1.0, "state": None, "epoch": -1}
    steps = max(1, (len(Xt) + args.batch - 1) // args.batch)
    for epoch in range(args.epochs):
        model.train()
        order = torch.randperm(len(Xt))
        total = 0.0
        for s in range(steps):
            idx = order[s * args.batch:(s + 1) * args.batch]
            opt.zero_grad()
            out = model(Xt[idx]).squeeze(1)
            loss = bce_weighted(out, yt[idx])
            loss.backward()
            opt.step()
            total += float(loss) * len(idx)
        model.eval()
        m = evaluate(model, Xv, yv)
        marker = ""
        if m["auc"] > best["auc"]:
            best = {"auc": m["auc"], "state": {k: v.clone() for k, v in model.state_dict().items()},
                    "epoch": epoch}
            marker = " *"
        if epoch % 5 == 0 or marker or epoch == args.epochs - 1:
            log(f"epoch {epoch:02d} loss={total / len(Xt):.4f} val_auc={m['auc']:.4f} "
                f"pos={m['pos_mean']:.3f} neg={m['neg_mean']:.3f}{marker}")
    model.load_state_dict(best["state"])
    log(f"melhor epoch: {best['epoch']} (val_auc={best['auc']:.4f})")
    log(f"final janela-a-janela: {evaluate(model, Xv, yv)}")

    # ------------------------------------------------------------ export ---
    model.eval()
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_onnx = out_path.with_suffix(".onnx.tmp")
    torch.onnx.export(
        model, torch.zeros(1, N_FRAMES, 96), str(tmp_onnx),
        input_names=["input"], output_names=["output"],
        dynamo=False, opset_version=13, do_constant_folding=True,
    )
    shutil.move(str(tmp_onnx), str(out_path))
    import onnxruntime as ort

    sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
    probe = sess.run(None, {sess.get_inputs()[0].name: np.zeros((1, N_FRAMES, 96), np.float32)})[0]
    log(f"exportado: {out_path} ({out_path.stat().st_size} bytes); "
        f"score silencio={float(probe.reshape(-1)[0]):.4f}")
    log("Status real: modelo treinado e exportado.")
    log("Produção: nada alterado (modelo novo em arquivo separado jarvis_free.onnx).")
    return 0


# -------------------------------------------------------------- validate ----
def cmd_validate(args: argparse.Namespace) -> int:
    data_dir = pathlib.Path(args.data)
    sandbox = data_dir / "models_sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)
    models_dir = pathlib.Path(args.models_dir)
    for base in ("silero_vad.onnx", "melspectrogram.onnx", "embedding_model.onnx"):
        os.symlink(models_dir / base, sandbox / base)
    new_model = pathlib.Path(args.model)
    if not new_model.exists():
        log(f"ERRO: modelo novo ausente: {new_model}")
        return 1
    os.symlink(new_model, sandbox / "hey_jarvis_v0.1.onnx")  # voice_gate espera esse nome

    gate = [sys.executable, str(HERE / "voice_gate.py")]

    def run_gate(wav: pathlib.Path, models: pathlib.Path) -> float:
        proc = subprocess.run(gate + [str(wav), "--models-dir", str(models)],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip()[:200])
        return float(json.loads(proc.stdout)["wake"])

    def table(title: str, folder: str, models: pathlib.Path, good: str) -> list[tuple[str, float]]:
        rows = []
        for wav in sorted((data_dir / folder).glob("*.wav")):
            rows.append((wav.name, run_gate(wav, models)))
        log(f"\n== {title} ({good}) ==")
        hits = 0
        for name, score in rows:
            log(f"  {score:6.3f}  {name}")
        return rows

    pos_new = table("POSITIVOS Jarvis solto — modelo NOVO", "val_pos", sandbox,
                    "alvo score>=0.55 em >=90%")
    neg_new = table("NEGATIVOS — modelo NOVO", "val_neg", sandbox,
                    "alvo score<=0.35 em >=95%")

    # baseline: mesmo protocolo com o modelo oficial
    official = data_dir / "models_sandbox_official"
    if official.exists():
        shutil.rmtree(official)
    official.mkdir(parents=True)
    for base in ("silero_vad.onnx", "melspectrogram.onnx", "embedding_model.onnx",
                 "hey_jarvis_v0.1.onnx"):
        os.symlink(models_dir / base, official / base)
    pos_off = [(n, run_gate(data_dir / "val_pos" / n, official)) for n, _ in pos_new]
    neg_off = [(n, run_gate(data_dir / "val_neg" / n, official)) for n, _ in neg_new]

    def summarize(label: str, rows: list[tuple[str, float]], crit) -> None:
        hits = sum(1 for _, s in rows if crit(s))
        pct = 100.0 * hits / len(rows) if rows else 0.0
        log(f"{label}: {hits}/{len(rows)} ({pct:.0f}%)")

    log("\n== RESUMO ==")
    summarize("NOVO   pos >=0.55", pos_new, lambda s: s >= 0.55)
    summarize("NOVO   neg <=0.35", neg_new, lambda s: s <= 0.35)
    summarize("OFICIAL pos >=0.55", pos_off, lambda s: s >= 0.55)
    summarize("OFICIAL neg <=0.35", neg_off, lambda s: s <= 0.35)

    sil = data_dir / "val_neg"  # silencio puro vive em neg_raw; roda 1 extra
    noise = sorted((data_dir / "neg_raw").glob("neg_noise_*.wav"))[:2]
    for wav in noise:
        log(f"extra ruido {wav.name}: NOVO={run_gate(wav, sandbox):.3f} "
            f"OFICIAL={run_gate(wav, official):.3f}")
    log("\nStatus real: validacao via voice_gate.py CLI real (sandbox de symlinks).")
    log("Produção: nada alterado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Treino do wake word Jarvis (palavra solta)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("dataset", help="gera dataset TTS + augment em /tmp")
    p.add_argument("--out", default=str(DATA_DIR))
    p.set_defaults(func=cmd_dataset)

    p = sub.add_parser("train", help="treina cabeca binaria e exporta ONNX")
    p.add_argument("--data", default=str(DATA_DIR))
    p.add_argument("--models-dir", default=DEFAULT_MODELS_DIR)
    p.add_argument("--out", default=str(FINAL_MODEL))
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch", type=int, default=128)
    p.add_argument("--lr", type=float, default=1e-3)
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("validate", help="valida via voice_gate CLI em sandbox")
    p.add_argument("--data", default=str(DATA_DIR))
    p.add_argument("--models-dir", default=DEFAULT_MODELS_DIR)
    p.add_argument("--model", default=str(FINAL_MODEL))
    p.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
