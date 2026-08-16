#!/usr/bin/env python3
"""Voz local do JARVIS com Pocket-TTS + referência fixa de voz.

Mantém o contrato existente em ``POST /speech``.

Ordem local:
    Pocket-TTS (voz clonada) -> Piper -> falha explícita

O áudio de referência e o voice-state ficam fora do Git.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import wave


VOICE_PROFILE = (
    "asetrate={rate}*{pitch},aresample={rate},atempo={tempo},"
    "highpass=f=70,"
    "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=200,"
    "volume=1.15"
)
MAX_TEXT = 2_200
LAUNCH_LABEL = "ai.theopadilha.jarvis-voice"
LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_LABEL}.plist"
LOG_DIR = Path(__file__).resolve().parents[1] / "09_LOGS"


class VoiceEngine:
    name = "unknown"
    model_name = "unknown"
    sample_rate = 24_000
    device = "cpu"
    natural_audio = True

    def synthesize(self, text: str, options: dict) -> bytes:
        raise NotImplementedError


class PocketTTSEngine(VoiceEngine):
    name = "pocket-tts"
    device = "cpu"
    natural_audio = True

    def __init__(
        self,
        reference: Path,
        language: str = "portuguese",
        temperature: float = 0.7,
        lsd_decode_steps: int = 1,
        quantize: bool = False,
    ):
        try:
            from pocket_tts import TTSModel
        except ImportError as error:
            raise RuntimeError(
                "Pocket-TTS ausente; instale em Python 3.11 com `pip install pocket-tts==2.1.0`."
            ) from error

        if not reference.is_file():
            raise RuntimeError(f"referência Pocket-TTS não encontrada em {reference}")

        self._lock = threading.Lock()
        self._model = TTSModel.load_model(
            language=language,
            temp=temperature,
            lsd_decode_steps=lsd_decode_steps,
            quantize=quantize,
        )
        self._voice_state = self._model.get_state_for_audio_prompt(str(reference))
        self.reference = reference
        self.language = language
        self.temperature = temperature
        self.lsd_decode_steps = lsd_decode_steps
        self.quantize = quantize
        self.sample_rate = int(getattr(self._model, "sample_rate", 24_000))
        self.model_name = f"Pocket-TTS-{language}"

    def synthesize(self, text: str, options: dict) -> bytes:
        with self._lock:
            audio = self._model.generate_audio(
                self._voice_state,
                text,
                copy_state=True,
            )
        return _tensor_to_wav(audio, self.sample_rate)


class PiperEngine(VoiceEngine):
    name = "piper"
    natural_audio = False

    def __init__(self, model_path: Path):
        try:
            from piper import PiperVoice
        except ImportError as error:
            raise RuntimeError("Piper ausente; instale com `pip install piper-tts`.") from error
        if not model_path.is_file():
            raise RuntimeError(f"modelo Piper não encontrado em {model_path}")
        self._voice = PiperVoice.load(str(model_path))
        self.model_name = model_path.name
        self.sample_rate = getattr(getattr(self._voice, "config", None), "sample_rate", 22_050)

    def synthesize(self, text: str, options: dict) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            self._voice.synthesize_wav(text, handle)
        return buffer.getvalue()


class FallbackEngine(VoiceEngine):
    def __init__(self, engines: list[VoiceEngine]):
        if not engines:
            raise RuntimeError("nenhum motor de voz local disponível")
        self.engines = engines
        self._sync_public_state()

    def _sync_public_state(self) -> None:
        current = self.engines[0]
        self.name = current.name
        self.model_name = current.model_name
        self.sample_rate = current.sample_rate
        self.device = current.device
        self.natural_audio = current.natural_audio

    def synthesize(self, text: str, options: dict) -> bytes:
        errors: list[str] = []
        for index, engine in enumerate(list(self.engines)):
            try:
                audio = engine.synthesize(text, options)
            except Exception as error:
                errors.append(f"{engine.name}: {type(error).__name__}")
                continue
            if index:
                self.engines.insert(0, self.engines.pop(index))
            self._sync_public_state()
            return audio
        raise RuntimeError("todos os motores falharam (" + ", ".join(errors) + ")")


def _tensor_to_wav(tensor, sample_rate: int) -> bytes:
    import torch

    pcm = tensor.detach().to("cpu").float()
    while pcm.ndim > 1:
        pcm = pcm[0]
    pcm = pcm.clamp(-1.0, 1.0)
    pcm = (pcm * 32767.0).to(dtype=torch.int16).contiguous()

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.numpy().tobytes())
    return buffer.getvalue()


def _bounded(payload: dict, name: str, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(float(payload.get(name, default)), high))
    except (TypeError, ValueError):
        return default


def apply_profile(audio: bytes, rate: int, pitch: float, tempo: float) -> tuple[bytes, str]:
    if not shutil.which("ffmpeg"):
        return audio, "audio/wav"
    chain = VOICE_PROFILE.format(rate=rate, pitch=pitch, tempo=tempo)
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-i", "pipe:0",
                "-af", chain, "-f", "mp3", "-b:a", "128k", "pipe:1",
            ],
            input=audio,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return audio, "audio/wav"
    if result.returncode != 0 or not result.stdout:
        return audio, "audio/wav"
    return result.stdout, "audio/mpeg"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JARVIS local neural voice")
    parser.add_argument(
        "--engine",
        choices=("auto", "pocket", "piper"),
        default=os.environ.get("JARVIS_TTS_ENGINE", "auto"),
        help="auto prefere Pocket-TTS e preserva Piper como fallback",
    )
    parser.add_argument(
        "--reference",
        default=os.environ.get("JARVIS_TTS_REFERENCE", ""),
        help="WAV ou .safetensors da identidade vocal do Pocket-TTS",
    )
    parser.add_argument(
        "--language",
        default=os.environ.get("JARVIS_TTS_LANGUAGE", "portuguese"),
        help="modelo Pocket-TTS; use portuguese ou portuguese_24l",
    )
    parser.add_argument(
        "--voice",
        default=os.environ.get("JARVIS_PIPER_VOICE", ""),
        help="modelo .onnx do Piper usado como fallback",
    )
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--lsd-decode-steps", type=int, default=1)
    parser.add_argument("--quantize", action="store_true")
    parser.add_argument("--install-agent", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--token", default="")
    parser.add_argument("--pitch", type=float, default=0.94)
    parser.add_argument("--tempo", type=float, default=1.02)
    parser.add_argument(
        "--profile",
        choices=("auto", "raw", "cockpit"),
        default="auto",
        help="auto preserva Pocket-TTS cru e só processa Piper",
    )
    parser.add_argument("--raw", action="store_true")
    return parser


def build_engine(args) -> FallbackEngine:
    engines: list[VoiceEngine] = []
    failures: list[str] = []
    reference = Path(args.reference).expanduser() if args.reference else None
    piper_voice = Path(args.voice).expanduser() if args.voice else None

    if args.engine in {"auto", "pocket"} and reference is not None:
        try:
            engines.append(
                PocketTTSEngine(
                    reference=reference,
                    language=args.language,
                    temperature=args.temperature,
                    lsd_decode_steps=args.lsd_decode_steps,
                    quantize=args.quantize,
                )
            )
        except Exception as error:
            failures.append(f"Pocket-TTS: {error}")
            if args.engine == "pocket":
                raise RuntimeError(failures[-1]) from error
    elif args.engine == "pocket":
        raise RuntimeError("Pocket-TTS exige --reference com WAV ou .safetensors")

    if args.engine in {"auto", "piper"} and piper_voice is not None:
        try:
            engines.append(PiperEngine(piper_voice))
        except Exception as error:
            failures.append(f"Piper: {error}")
            if args.engine == "piper":
                raise RuntimeError(failures[-1]) from error

    if not engines:
        detail = "; ".join(failures) or "informe --reference para Pocket-TTS ou --voice para Piper"
        raise RuntimeError(f"nenhum motor local pôde iniciar: {detail}")
    return FallbackEngine(engines)


def install_agent(args) -> Path:
    import plistlib

    program = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--engine", args.engine,
        "--host", args.host,
        "--port", str(args.port),
        "--language", args.language,
        "--temperature", str(args.temperature),
        "--lsd-decode-steps", str(args.lsd_decode_steps),
        "--profile", "raw" if args.raw else args.profile,
        "--pitch", str(args.pitch),
        "--tempo", str(args.tempo),
    ]
    if args.quantize:
        program.append("--quantize")
    if args.voice:
        program.extend(["--voice", str(Path(args.voice).expanduser().resolve())])
    if args.reference:
        program.extend(["--reference", str(Path(args.reference).expanduser().resolve())])

    payload = {
        "Label": LAUNCH_LABEL,
        "ProgramArguments": program,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "PATH": (
                f"{Path.home() / '.local' / 'bin'}:"
                "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            ),
        },
        "StandardOutPath": str(LOG_DIR / "voice-server.log"),
        "StandardErrorPath": str(LOG_DIR / "voice-server-error.log"),
    }
    LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENT.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True))

    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", f"{domain}/{LAUNCH_LABEL}"],
        capture_output=True,
        check=False,
    )
    for _ in range(20):
        gone = subprocess.run(
            ["launchctl", "print", f"{domain}/{LAUNCH_LABEL}"],
            capture_output=True,
            check=False,
        )
        if gone.returncode != 0:
            break
        time.sleep(0.25)
    subprocess.run(
        ["launchctl", "bootstrap", domain, str(LAUNCH_AGENT)],
        capture_output=True,
        check=False,
    )
    for _ in range(20):
        alive = subprocess.run(
            ["launchctl", "print", f"{domain}/{LAUNCH_LABEL}"],
            capture_output=True,
            check=False,
        )
        if alive.returncode == 0:
            return LAUNCH_AGENT
        time.sleep(0.25)
    raise RuntimeError(f"launchd não aceitou {LAUNCH_LABEL}; verifique {LAUNCH_AGENT}")


def make_handler(engine: FallbackEngine, args):
    class VoiceHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            return

        def _send(self, status: int, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Jarvis-Voice-Token")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict):
            self._send(
                status,
                json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def do_OPTIONS(self):
            self._send(204, b"", "text/plain")

        def do_GET(self):
            if self.path.rstrip("/") in {"", "/health"}:
                return self._json(
                    200,
                    {
                        "ok": True,
                        "status_real": "local_voice_ready",
                        "engine": engine.name,
                        "model": engine.model_name,
                        "sample_rate": engine.sample_rate,
                        "device": engine.device,
                        "language": args.language,
                        "reference": Path(args.reference).name if args.reference else None,
                        "fallbacks": [item.name for item in engine.engines[1:]],
                        "profile": (
                            "raw"
                            if args.raw
                            or args.profile == "raw"
                            or (args.profile == "auto" and engine.natural_audio)
                            else "cockpit"
                        ),
                    },
                )
            return self._json(404, {"ok": False, "error": "rota desconhecida"})

        def do_POST(self):
            if self.path.rstrip("/") != "/speech":
                return self._json(404, {"ok": False, "error": "rota desconhecida"})
            if args.token and self.headers.get("X-Jarvis-Voice-Token", "") != args.token:
                return self._json(401, {"ok": False, "error": "token da voz inválido"})
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 100_000)
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._json(400, {"ok": False, "error": "corpo inválido"})
            text = str(body.get("text") or body.get("message") or "").strip()[:MAX_TEXT]
            if not text:
                return self._json(400, {"ok": False, "error": "texto vazio"})

            try:
                audio = engine.synthesize(text, body)
            except Exception as error:
                return self._json(
                    500,
                    {"ok": False, "error": f"falha na síntese: {type(error).__name__}: {error}"},
                )

            use_profile = (
                not args.raw
                and args.profile != "raw"
                and (
                    args.profile == "cockpit"
                    or (args.profile == "auto" and not engine.natural_audio)
                )
            )
            if not use_profile:
                return self._send(200, audio, "audio/wav")

            pitch = _bounded(body, "pitch", args.pitch, 0.70, 1.10)
            tempo = _bounded(body, "tempo", args.tempo, 0.80, 1.40)
            processed, content_type = apply_profile(audio, engine.sample_rate, pitch, tempo)
            return self._send(200, processed, content_type)

    return VoiceHandler


def main() -> int:
    args = build_parser().parse_args()
    if args.raw:
        args.profile = "raw"

    if args.install_agent:
        try:
            agent = install_agent(args)
        except RuntimeError as error:
            print(f"FALHA: {error}")
            return 1
        print(f"Voz registrada no boot: {agent}")
        print(f"Status real: configuração registrada; o motor será carregado pelo {LAUNCH_LABEL}.")
        return 0

    try:
        engine = build_engine(args)
    except RuntimeError as error:
        print(f"FALHA: {error}")
        return 1

    server = ThreadingHTTPServer((args.host, args.port), make_handler(engine, args))
    print("JARVIS — voz local")
    print(f"Status real: {engine.name}/{engine.model_name} em http://{args.host}:{args.port}/speech")
    print("Custo de API: zero; síntese local. Referência e pesos ficam fora do Git.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
