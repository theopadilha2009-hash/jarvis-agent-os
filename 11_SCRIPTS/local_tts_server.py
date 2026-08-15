#!/usr/bin/env python3
"""Voz própria do JARVIS: síntese neural local, sem cota e sem chave.

Sobe um HTTP mínimo que fala português com o Piper e aplica o timbre do
cockpit — barítono calmo, cadência medida, sem pressa. O gateway web chama
este servidor quando a voz paga não está disponível.

    python3 11_SCRIPTS/local_tts_server.py --voice 05_EXECUCAO/voices/pt_BR-cadu-medium.onnx

O modelo não vem no repositório: baixe uma voz do Piper (rhasspy/piper-voices)
e aponte com --voice.
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
import time
import wave


# Perfil sonoro do cockpit: grave sem soar arrastado, com ar de sala.
VOICE_PROFILE = (
    "asetrate={rate}*{pitch},aresample={rate},atempo={tempo},"
    "highpass=f=75,lowpass=f=8800,"
    "acompressor=threshold=-18dB:ratio=3:attack=8:release=180,"
    "aecho=0.88:0.4:24:0.15,volume=1.2"
)
MAX_TEXT = 2_200


LAUNCH_LABEL = "ai.theopadilha.jarvis-voice"
LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_LABEL}.plist"
LOG_DIR = Path(__file__).resolve().parents[1] / "09_LOGS"


def install_agent(args) -> Path:
    """Deixa a voz de pé desde o boot: sem ela a saudação cai para o `say`."""
    import plistlib

    payload = {
        "Label": LAUNCH_LABEL,
        "ProgramArguments": [
            sys.executable,
            str(Path(__file__).resolve()),
            "--voice", str(Path(args.voice).expanduser().resolve()),
            "--host", args.host,
            "--port", str(args.port),
            "--pitch", str(args.pitch),
            "--tempo", str(args.tempo),
        ],
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
    subprocess.run(["launchctl", "bootout", f"{domain}/{LAUNCH_LABEL}"], capture_output=True, check=False)
    # bootout é assíncrono: sem esperar o serviço sumir, o bootstrap seguinte
    # falha em silêncio e a voz não sobe.
    for _ in range(20):
        gone = subprocess.run(
            ["launchctl", "print", f"{domain}/{LAUNCH_LABEL}"],
            capture_output=True,
            check=False,
        )
        if gone.returncode != 0:
            break
        time.sleep(0.25)
    subprocess.run(["launchctl", "bootstrap", domain, str(LAUNCH_AGENT)], capture_output=True, check=False)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JARVIS local neural voice")
    parser.add_argument("--voice", required=True, help="caminho do modelo .onnx do Piper")
    parser.add_argument("--install-agent", action="store_true", help="sobe junto com o Mac, via LaunchAgent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--token", default="", help="exigido no header X-Jarvis-Voice-Token quando definido")
    parser.add_argument("--pitch", type=float, default=0.90, help="<1 deixa a voz mais grave")
    parser.add_argument("--tempo", type=float, default=1.06, help="compensa a duração após o pitch")
    parser.add_argument("--raw", action="store_true", help="devolve o Piper puro, sem o timbre do cockpit")
    return parser


def synthesize_wav(voice, text: str) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        voice.synthesize_wav(text, handle)
    return buffer.getvalue()


def apply_profile(audio: bytes, rate: int, pitch: float, tempo: float) -> tuple[bytes, str]:
    """Aplica o timbre e entrega mp3; sem ffmpeg, devolve o wav como veio."""
    if not shutil.which("ffmpeg"):
        return audio, "audio/wav"
    chain = VOICE_PROFILE.format(rate=rate, pitch=pitch, tempo=tempo)
    try:
        result = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-af", chain, "-f", "mp3", "-b:a", "128k", "pipe:1"],
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


def make_handler(voice, args, sample_rate: int):
    class VoiceHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):  # silêncio: quem fala é o JARVIS
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
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_OPTIONS(self):  # noqa: N802
            self._send(204, b"", "text/plain")

        def do_GET(self):  # noqa: N802
            if self.path.rstrip("/") in {"", "/health"}:
                return self._json(200, {
                    "ok": True,
                    "status_real": "local_voice_ready",
                    "voice": Path(args.voice).name,
                    "sample_rate": sample_rate,
                    "profile": "raw" if args.raw else "cockpit",
                })
            return self._json(404, {"ok": False, "error": "rota desconhecida"})

        def do_POST(self):  # noqa: N802
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

            def bounded(name, default, low, high):
                try:
                    return max(low, min(float(body.get(name, default)), high))
                except (TypeError, ValueError):
                    return default

            pitch = bounded("pitch", args.pitch, 0.70, 1.10)
            tempo = bounded("tempo", args.tempo, 0.80, 1.40)
            try:
                audio = synthesize_wav(voice, text)
            except Exception as error:  # o servidor não pode morrer por uma frase
                return self._json(500, {"ok": False, "error": f"falha na síntese: {error}"})
            if args.raw:
                return self._send(200, audio, "audio/wav")
            processed, content_type = apply_profile(audio, sample_rate, pitch, tempo)
            return self._send(200, processed, content_type)

    return VoiceHandler


def main() -> int:
    args = build_parser().parse_args()
    model = Path(args.voice).expanduser()
    if not model.is_file():
        print(f"FALHA: modelo não encontrado em {model}")
        return 1
    if args.install_agent:
        try:
            agent = install_agent(args)
        except RuntimeError as error:
            print(f"FALHA: {error}")
            return 1
        print(f"Voz registrada no boot: {agent}")
        print(f"Status real: {LAUNCH_LABEL} ativo; a saudação de boas-vindas usa esta voz.")
        return 0
    try:
        from piper import PiperVoice
    except ImportError:
        print("FALHA: instale o Piper com `pip3 install piper-tts`.")
        return 1
    voice = PiperVoice.load(str(model))
    sample_rate = getattr(getattr(voice, "config", None), "sample_rate", 22_050)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(voice, args, sample_rate))
    print("JARVIS — voz local")
    print(f"Status real: {model.name} em http://{args.host}:{args.port}/speech")
    print("Produção: nada alterado; a síntese acontece nesta máquina.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
