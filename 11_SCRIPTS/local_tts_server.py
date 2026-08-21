#!/usr/bin/env python3
"""Voz própria do JARVIS: síntese neural local, sem cota e sem chave.

Motor principal: Pocket TTS (portuguese + rafael no JARVIS, javert no Ultron).
rafael é a voz masculina de catálogo em português; bill_boerst é inglês e
soa torto em pt-BR. Se edge-tts estiver instalado, a camada neural gratuita
da Microsoft (Antonio / Humberto) entra primeiro — melhor pronúncia.
O modelo Pocket fica em memória; cada /speech gera a frase inteira.

Piper continua como fallback se Pocket falhar. O gateway web chama este
servidor quando a voz paga não está disponível.

    # Pocket (padrão; usa ~/.venv-pocket se o python atual não tiver o pacote)
    python3 11_SCRIPTS/local_tts_server.py

    # Piper só, se quiser o motor antigo
    python3 11_SCRIPTS/local_tts_server.py --engine piper --voice ~/.…/cadu.onnx
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
import wave


# Perfil sonoro do cockpit: só no fallback Piper.
VOICE_PROFILE = (
    "asetrate={rate}*{pitch},aresample={rate},atempo={tempo},"
    "highpass=f=70,"
    "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=200,"
    "volume=1.15"
)
# Pocket: um semitom mais grave. Se o ffmpeg atrasar, devolve o WAV cru.
POCKET_ADULT = "asetrate={rate}*0.96,aresample={rate},atempo=1.035,highpass=f=85,volume=1.06"
MAX_TEXT = 2_200
DEFAULT_ENGINE = "auto"
DEFAULT_LANGUAGE = "portuguese"
DEFAULT_VOICE = "rafael"
DEFAULT_ULTRON_VOICE = "javert"
DEFAULT_EDGE_JARVIS = "pt-BR-AntonioNeural"
DEFAULT_EDGE_ULTRON = "pt-BR-AntonioNeural"
EDGE_STYLE = {
    "jarvis": {"rate": "-5%", "pitch": "-8Hz"},
    "ultron": {"rate": "-12%", "pitch": "-22Hz"},
}
DEFAULT_POCKET_PYTHON = Path(".venv-pocket") / "bin" / "python"
CATALOG_VOICES = {
    "rafael", "javert", "jean", "marius", "bill_boerst", "alba", "giovanni",
    "lola", "juergen", "estelle", "anna", "azelma", "caro_davy", "charles",
    "cosette", "eponine", "eve", "fantine", "george", "jane", "mary",
    "michael", "paul", "peter_yearsley", "stuart_bell", "vera",
}

LAUNCH_LABEL = "ai.theopadilha.jarvis-voice"
LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_LABEL}.plist"
LOG_DIR = Path(__file__).resolve().parents[1] / "09_LOGS"
SPEECH_CACHE_MAX = 24
SPEECH_CACHE_CHARS = 72
_SPEECH_CACHE = {}
_SPEECH_CACHE_LOCK = threading.Lock()


def voice_lock_dir(home=None, environ=None) -> Path:
    env = environ if environ is not None else os.environ
    override = (env.get("JARVIS_VOICE_LOCK_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    root = Path(home) if home else Path(env.get("HOME") or Path.home())
    return root / "Library" / "Application Support" / "JARVIS" / "voice-lock"


def parse_voice_lock(text: str) -> dict:
    parsed = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().casefold().replace(" ", "_").replace("-", "_")
        value = value.strip()
        if key in {"language", "voice", "engine", "ultron_voice", "edge_jarvis", "edge_ultron"} and value:
            parsed[key] = value
    return parsed


def normalize_engine(value: str) -> str:
    engine = (value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if engine in {"pocket", "pockettts"}:
        return "pocket_tts"
    if engine in {"edge", "edgetts", "microsoft"}:
        return "edge"
    if engine in {"auto", "quality"}:
        return "auto"
    return engine or DEFAULT_ENGINE


def resolve_voice_config(environ=None, home=None) -> dict:
    """engine/language/voice: env > VOICE_CONFIG do HOME > defaults aprovados."""
    env = environ if environ is not None else os.environ
    lock_path = voice_lock_dir(home=home, environ=env) / "VOICE_CONFIG.txt"
    lock = {}
    try:
        lock = parse_voice_lock(lock_path.read_text(encoding="utf-8"))
    except OSError:
        lock = {}
    engine = normalize_engine(env.get("JARVIS_TTS_ENGINE") or lock.get("engine") or DEFAULT_ENGINE)
    language = (env.get("JARVIS_TTS_LANGUAGE") or lock.get("language") or DEFAULT_LANGUAGE).strip()
    voice = (env.get("JARVIS_TTS_VOICE") or lock.get("voice") or DEFAULT_VOICE).strip()
    ultron_voice = (env.get("JARVIS_TTS_ULTRON_VOICE") or lock.get("ultron_voice") or DEFAULT_ULTRON_VOICE).strip()
    return {
        "engine": engine,
        "language": language or DEFAULT_LANGUAGE,
        "voice": voice or DEFAULT_VOICE,
        "ultron_voice": ultron_voice or DEFAULT_ULTRON_VOICE,
        "edge_jarvis": (env.get("JARVIS_TTS_EDGE_JARVIS") or lock.get("edge_jarvis") or DEFAULT_EDGE_JARVIS).strip(),
        "edge_ultron": (env.get("JARVIS_TTS_EDGE_ULTRON") or lock.get("edge_ultron") or DEFAULT_EDGE_ULTRON).strip(),
        "lock_path": str(lock_path),
    }


def catalog_voice(value: str, fallback: str) -> str:
    name = (value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if name in CATALOG_VOICES:
        return name
    return fallback


def persona_is_ultron(value: str) -> bool:
    return (value or "").strip().casefold() in {"ultron", "ultron_private"}


def resolve_request_voices(body: dict, config: dict) -> dict:
    persona = str((body or {}).get("persona") or "jarvis")
    ultron = persona_is_ultron(persona)
    requested = catalog_voice(str((body or {}).get("voice") or ""), "")
    pocket = requested or (config.get("ultron_voice") if ultron else config.get("voice")) or DEFAULT_VOICE
    edge = (config.get("edge_ultron") if ultron else config.get("edge_jarvis")) or DEFAULT_EDGE_JARVIS
    persona_id = "ultron" if ultron else "jarvis"
    style = EDGE_STYLE[persona_id]
    return {
        "persona": persona_id,
        "pocket": catalog_voice(pocket, DEFAULT_VOICE),
        "edge": edge,
        "edge_rate": style["rate"],
        "edge_pitch": style["pitch"],
    }


def pocket_python(home=None) -> Path:
    root = Path(home) if home else Path.home()
    return root / DEFAULT_POCKET_PYTHON


def default_piper_voice(home=None) -> Path | None:
    root = Path(home) if home else Path.home()
    candidates = (
        root / "Library" / "Application Support" / "JARVIS" / "voices" / "cadu.onnx",
        Path(__file__).resolve().parents[1] / "05_EXECUCAO" / "voices" / "pt_BR-cadu-medium.onnx",
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def maybe_reexec_pocket_python(engine: str) -> None:
    """Pocket vive no venv aprovado; sem isso o processo longo não carrega o modelo."""
    if engine not in {"pocket_tts", "auto", "edge"}:
        return
    if os.environ.get("JARVIS_TTS_NO_REEXEC") == "1":
        return
    try:
        import pocket_tts  # noqa: F401
        return
    except ImportError:
        pass
    candidate = pocket_python()
    if not candidate.is_file():
        return
    current = Path(sys.executable).resolve()
    if current == candidate.resolve():
        return
    os.execv(str(candidate), [str(candidate), *sys.argv])


def pcm16_wav(frames: bytes, sample_rate: int, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate) or 24_000)
        handle.writeframes(frames)
    return buffer.getvalue()


def tensor_to_wav(audio, sample_rate: int) -> bytes:
    """Converte o tensor do Pocket (ou WAV já pronto) em WAV PCM16, sem ffmpeg."""
    if isinstance(audio, (bytes, bytearray)) and audio[:4] == b"RIFF":
        return bytes(audio)
    if hasattr(audio, "detach"):
        audio = audio.detach()
    if hasattr(audio, "cpu"):
        audio = audio.cpu()
    if hasattr(audio, "clamp"):
        audio = audio.clamp(-1, 1)
        if int(getattr(audio, "ndim", 1) or 1) > 1:
            audio = audio.reshape(-1)
        pcm = (audio * 32767).short() if hasattr(audio, "short") else audio
        frames = pcm.numpy().tobytes() if hasattr(pcm, "numpy") else bytes(pcm)
        return pcm16_wav(frames, sample_rate)
    if isinstance(audio, (bytes, bytearray)):
        return pcm16_wav(bytes(audio), sample_rate)
    samples = list(audio)
    packed = b"".join(
        struct.pack("<h", max(-32768, min(32767, int(float(sample) * 32767))))
        for sample in samples
    )
    return pcm16_wav(packed, sample_rate)


def default_load_model(language: str):
    from pocket_tts import TTSModel

    return TTSModel.load_model(language=language)


def default_load_voice_state(model, voice: str):
    return model.get_state_for_audio_prompt(voice)


class PocketRuntime:
    """Um load do modelo + voice states; generate_audio reutiliza os dois."""

    def __init__(self, language: str, voice: str, loader=None, state_loader=None, extra_voices=None):
        self.language = language
        self.voice = voice
        self.voices = []
        for name in (voice, *(extra_voices or ())):
            clean = catalog_voice(name, "")
            if clean and clean not in self.voices:
                self.voices.append(clean)
        if not self.voices:
            self.voices = [DEFAULT_VOICE]
        self._loader = loader or default_load_model
        self._state_loader = state_loader or default_load_voice_state
        self.model = None
        self.voice_state = None
        self.voice_states = {}
        self.sample_rate = 24_000
        self.load_calls = 0
        self.state_load_calls = 0
        self._lock = threading.Lock()

    def load(self):
        pending = [name for name in self.voices if name not in self.voice_states]
        if self.model is not None and not pending:
            return self
        with self._lock:
            if self.model is None:
                self.model = self._loader(self.language)
                self.load_calls += 1
                self.sample_rate = int(getattr(self.model, "sample_rate", 24_000) or 24_000)
            for name in self.voices:
                if name in self.voice_states:
                    continue
                self.voice_states[name] = self._state_loader(self.model, name)
                self.state_load_calls += 1
            self.voice_state = self.voice_states.get(self.voice) or next(iter(self.voice_states.values()), None)
        return self

    def generate(self, text: str, voice: str | None = None) -> bytes:
        self.load()
        chosen = catalog_voice(voice or "", self.voice) if voice else self.voice
        with self._lock:
            if chosen not in self.voice_states:
                self.voice_states[chosen] = self._state_loader(self.model, chosen)
                self.state_load_calls += 1
            state = self.voice_states[chosen]
            self.voice_state = state
            audio = self.model.generate_audio(state, text, copy_state=True)
        return tensor_to_wav(audio, self.sample_rate)


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


def apply_pocket_adult(audio: bytes, rate: int) -> bytes:
    """Abaixa o timbre um pouco. Falhou ou atrasou → áudio original."""
    if not audio or audio[:4] != b"RIFF" or not shutil.which("ffmpeg"):
        return audio
    chain = POCKET_ADULT.format(rate=int(rate or 24_000))
    try:
        result = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-af", chain, "-f", "wav", "pipe:1"],
            input=audio,
            capture_output=True,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return audio
    if result.returncode != 0 or not result.stdout or result.stdout[:4] != b"RIFF":
        return audio
    return result.stdout


def synthesize_edge(text: str, voice: str, rate: str = "-5%", pitch: str = "-8Hz") -> dict:
    """Neural gratuita da Microsoft (Edge Read Aloud). Sem chave; precisa de rede."""
    try:
        import asyncio
        import edge_tts
    except ImportError:
        return {"ok": False, "error": "edge-tts não instalado", "engine": "edge"}
    voice = (voice or DEFAULT_EDGE_JARVIS).strip() or DEFAULT_EDGE_JARVIS

    async def collect():
        chunks = []
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        async for item in communicate.stream():
            if item.get("type") == "audio" and item.get("data"):
                chunks.append(item["data"])
        return b"".join(chunks)

    try:
        loop = asyncio.new_event_loop()
        try:
            audio = loop.run_until_complete(collect())
        finally:
            loop.close()
    except Exception as error:
        return {"ok": False, "error": f"falha na síntese edge: {error}", "engine": "edge"}
    if not audio:
        return {"ok": False, "error": "edge-tts devolveu áudio vazio", "engine": "edge"}
    return {"ok": True, "audio": audio, "content_type": "audio/mpeg", "engine": "edge", "voice": voice}


def synthesize_speech(text: str, pocket=None, piper=None, piper_opts=None, voice=None, edge_voice=None, prefer_edge=False, edge_rate="-5%", edge_pitch="-8Hz") -> dict:
    """Gera áudio sem derrubar o processo. Edge neural (se pedido) → Pocket → Piper."""
    opts = piper_opts or {}
    if prefer_edge and edge_voice:
        edge = synthesize_edge(text, edge_voice, rate=edge_rate, pitch=edge_pitch)
        if edge.get("ok"):
            return edge
    if pocket is not None:
        try:
            try:
                audio = pocket.generate(text, voice=voice)
            except TypeError:
                audio = pocket.generate(text)
            if audio:
                rate = int(getattr(pocket, "sample_rate", 24_000) or 24_000)
                return {
                    "ok": True,
                    "audio": apply_pocket_adult(audio, rate),
                    "content_type": "audio/wav",
                    "engine": "pocket_tts",
                    "voice": voice or getattr(pocket, "voice", ""),
                }
        except Exception as error:
            if piper is None and not (prefer_edge and edge_voice):
                return {"ok": False, "error": f"falha na síntese: {error}", "engine": "pocket_tts"}
    if piper is not None:
        try:
            audio = synthesize_wav(piper, text)
            if opts.get("raw"):
                return {"ok": True, "audio": audio, "content_type": "audio/wav", "engine": "piper"}
            processed, content_type = apply_profile(
                audio,
                int(opts.get("sample_rate") or 22_050),
                float(opts.get("pitch") or 0.94),
                float(opts.get("tempo") or 1.02),
            )
            return {"ok": True, "audio": processed, "content_type": content_type, "engine": "piper"}
        except Exception as error:
            return {"ok": False, "error": f"falha na síntese: {error}", "engine": "piper"}
    return {"ok": False, "error": "nenhum motor de voz disponível", "engine": "none"}


def speech_cache_get(key):
    if not key or len(str(key[0] if key else "")) > SPEECH_CACHE_CHARS:
        return None
    with _SPEECH_CACHE_LOCK:
        return _SPEECH_CACHE.get(key)


def speech_cache_put(key, result: dict) -> None:
    if not key or not result.get("ok") or not result.get("audio"):
        return
    if len(str(key[0])) > SPEECH_CACHE_CHARS:
        return
    with _SPEECH_CACHE_LOCK:
        if len(_SPEECH_CACHE) >= SPEECH_CACHE_MAX:
            _SPEECH_CACHE.pop(next(iter(_SPEECH_CACHE)), None)
        _SPEECH_CACHE[key] = {
            "audio": result["audio"],
            "content_type": result.get("content_type") or "audio/wav",
            "engine": result.get("engine") or "",
        }


def voice_ready(host="127.0.0.1", port=8123, timeout=0.5) -> bool:
    try:
        request = Request(f"http://{host}:{port}/health", method="GET")
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(4_000).decode("utf-8"))
            return int(response.status) == 200 and bool(payload.get("ok"))
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return False


def pids_on_port(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [int(token) for token in result.stdout.split() if token.isdigit()]


def stop_listeners(port: int) -> None:
    mine = os.getpid()
    for pid in pids_on_port(port):
        if pid == mine:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    time.sleep(0.25)
    for pid in pids_on_port(port):
        if pid == mine:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def free_stale_port(host: str, port: int) -> None:
    if voice_ready(host, port):
        return
    stop_listeners(port)


def voice_lock_path() -> Path:
    path = Path.home() / "Library" / "Application Support" / "JARVIS" / "voice-server.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def acquire_voice_lock():
    import fcntl

    handle = voice_lock_path().open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def warmup_runtime(pocket, voice: str) -> None:
    if pocket is None:
        return
    try:
        if hasattr(pocket, "generate"):
            pocket.generate("ok", voice=voice)
    except TypeError:
        try:
            pocket.generate("ok")
        except Exception:
            return
    except Exception:
        return


class ExclusiveHTTPServer(ThreadingHTTPServer):
    # SO_REUSEADDR precisa ficar ligado: no macOS a porta fica em TIME_WAIT
    # depois do kill. A exclusão real é o flock + /health.
    allow_reuse_address = True


def agent_program_args(args, config: dict) -> list[str]:
    python = sys.executable
    if config.get("engine") == "pocket_tts":
        candidate = pocket_python()
        if candidate.is_file():
            python = str(candidate)
    command = [
        python,
        str(Path(__file__).resolve()),
        "--host", args.host,
        "--port", str(args.port),
        "--engine", config["engine"],
        "--language", config["language"],
        "--tts-voice", config["voice"],
        "--ultron-voice", config.get("ultron_voice") or DEFAULT_ULTRON_VOICE,
        "--pitch", str(args.pitch),
        "--tempo", str(args.tempo),
    ]
    if getattr(args, "voice", ""):
        command.extend(["--voice", str(Path(args.voice).expanduser().resolve())])
    if getattr(args, "raw", False):
        command.append("--raw")
    return command


def agent_payload(args, config: dict) -> dict:
    return {
        "Label": LAUNCH_LABEL,
        "ProgramArguments": agent_program_args(args, config),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 15,
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "PATH": (
                f"{Path.home() / '.local' / 'bin'}:"
                f"{Path.home() / '.venv-pocket' / 'bin'}:"
                "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            ),
            "HOME": str(Path.home()),
        },
        "StandardOutPath": str(LOG_DIR / "voice-server.log"),
        "StandardErrorPath": str(LOG_DIR / "voice-server-error.log"),
    }


def install_agent(args, config=None) -> Path:
    """Deixa a voz de pé desde o boot: um processo só, reinicia só se cair."""
    import plistlib

    config = config or resolve_voice_config()
    stop_listeners(int(getattr(args, "port", 8123) or 8123))
    payload = agent_payload(args, config)
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
    parser.add_argument("--voice", default="", help="caminho do modelo .onnx do Piper (fallback)")
    parser.add_argument("--engine", default="", help="pocket_tts (padrão) ou piper")
    parser.add_argument("--language", default="", help="idioma Pocket (padrão: portuguese)")
    parser.add_argument("--tts-voice", default="", dest="tts_voice", help="voz Pocket do JARVIS (padrão: rafael)")
    parser.add_argument("--ultron-voice", default="", dest="ultron_voice", help="voz Pocket do Ultron (padrão: javert)")
    parser.add_argument("--install-agent", action="store_true", help="sobe junto com o Mac, via LaunchAgent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--token", default="", help="exigido no header X-Jarvis-Voice-Token quando definido")
    parser.add_argument("--pitch", type=float, default=0.94, help="<1 deixa a voz mais grave (só Piper)")
    parser.add_argument("--tempo", type=float, default=1.02, help="compensa a duração após o pitch (só Piper)")
    parser.add_argument("--raw", action="store_true", help="devolve o Piper puro, sem o timbre do cockpit")
    return parser


def apply_cli_overrides(config: dict, args) -> dict:
    if args.engine:
        config["engine"] = normalize_engine(args.engine)
    if args.language:
        config["language"] = args.language.strip()
    if args.tts_voice:
        config["voice"] = args.tts_voice.strip()
    if getattr(args, "ultron_voice", ""):
        config["ultron_voice"] = args.ultron_voice.strip()
    return config


def make_handler(args, pocket, piper, sample_rate: int, config: dict):
    class VoiceHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):  # silêncio: quem fala é o JARVIS
            return

        def _send(self, status: int, body: bytes, content_type: str, engine: str = ""):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Jarvis-Voice-Token")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header(
                "X-Jarvis-Voice-Engine",
                engine or ("pocket_tts" if pocket is not None else "piper" if piper is not None else "none"),
            )
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_OPTIONS(self):  # noqa: N802
            self._send(204, b"", "text/plain")

        def do_GET(self):  # noqa: N802
            if self.path.rstrip("/") in {"", "/health"}:
                return self._json(200, {
                    "ok": True,
                    "status_real": "local_voice_ready",
                    "engine": config.get("engine"),
                    "language": config.get("language"),
                    "voice": config.get("voice"),
                    "ultron_voice": config.get("ultron_voice"),
                    "edge_jarvis": config.get("edge_jarvis"),
                    "edge_ultron": config.get("edge_ultron"),
                    "pocket_loaded": pocket is not None,
                    "piper_loaded": piper is not None,
                    "piper_voice": Path(args.voice).name if piper is not None and args.voice else "",
                    "sample_rate": sample_rate,
                    "profile": "raw" if pocket is not None or args.raw else "cockpit",
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

            chosen = resolve_request_voices(body if isinstance(body, dict) else {}, config)
            prefer_edge = config.get("engine") == "edge"
            cache_id = (text, chosen["pocket"], chosen["edge"], prefer_edge)
            cached = speech_cache_get(cache_id)
            if cached:
                return self._send(200, cached["audio"], cached["content_type"], cached.get("engine") or "")
            result = synthesize_speech(
                text,
                pocket=pocket,
                piper=piper,
                piper_opts={
                    "raw": args.raw,
                    "sample_rate": sample_rate,
                    "pitch": bounded("pitch", args.pitch, 0.70, 1.10),
                    "tempo": bounded("tempo", args.tempo, 0.80, 1.40),
                },
                voice=chosen["pocket"],
                edge_voice=chosen["edge"],
                prefer_edge=prefer_edge,
                edge_rate=chosen.get("edge_rate") or "-5%",
                edge_pitch=chosen.get("edge_pitch") or "-8Hz",
            )
            if not result.get("ok"):
                return self._json(500, {
                    "ok": False,
                    "error": result.get("error") or "falha na síntese",
                    "engine": result.get("engine"),
                })
            speech_cache_put(cache_id, result)
            return self._send(200, result["audio"], result["content_type"], result.get("engine") or "")

    return VoiceHandler


def load_piper(path: str):
    try:
        from piper import PiperVoice
    except ImportError:
        return None
    model = Path(path).expanduser()
    if not model.is_file():
        return None
    return PiperVoice.load(str(model))


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = apply_cli_overrides(resolve_voice_config(), args)
    if args.install_agent:
        try:
            agent = install_agent(args, config)
        except RuntimeError as error:
            print(f"FALHA: {error}")
            return 1
        print(f"Voz registrada no boot: {agent}")
        print(
            f"Status real: {LAUNCH_LABEL} ativo; engine={config['engine']} "
            f"language={config['language']} voice={config['voice']}."
        )
        return 0

    maybe_reexec_pocket_python(config["engine"])

    if voice_ready(args.host, args.port):
        print("JARVIS — voz local")
        print(f"Status real: já ativa em http://{args.host}:{args.port}/speech")
        print("Produção: nada alterado.")
        return 0

    free_stale_port(args.host, args.port)
    if voice_ready(args.host, args.port):
        print("JARVIS — voz local")
        print(f"Status real: já ativa em http://{args.host}:{args.port}/speech")
        print("Produção: nada alterado.")
        return 0

    lock = acquire_voice_lock()
    if lock is None:
        time.sleep(0.8)
        if voice_ready(args.host, args.port):
            print("JARVIS — voz local")
            print(f"Status real: já ativa em http://{args.host}:{args.port}/speech")
            print("Produção: nada alterado.")
            return 0
        print("FALHA: outra instância da voz está subindo.")
        return 1

    pocket = None
    pocket_error = ""
    if config["engine"] in {"pocket_tts", "auto", "edge"}:
        try:
            pocket = PocketRuntime(
                config["language"],
                config["voice"],
                extra_voices=[config.get("ultron_voice") or DEFAULT_ULTRON_VOICE],
            )
            pocket.load()
        except Exception as error:
            pocket = None
            pocket_error = str(error)
            print(f"AVISO: Pocket TTS indisponível ({error}); tentando fallback.")
        else:
            warmup_runtime(pocket, config["voice"])

    piper_path = (args.voice or "").strip()
    if not piper_path:
        found = default_piper_voice()
        piper_path = str(found) if found else ""
        args.voice = piper_path
    piper = None
    if piper_path:
        try:
            piper = load_piper(piper_path)
        except Exception as error:
            piper = None
            print(f"AVISO: Piper indisponível ({error}).")
        if piper is None and config["engine"] == "piper":
            print(f"FALHA: modelo Piper não encontrado em {piper_path}")
            return 1

    if pocket is None and piper is None and config["engine"] == "piper":
        print("FALHA: instale o Piper com `pip3 install piper-tts` ou use --engine pocket_tts.")
        return 1

    sample_rate = getattr(pocket, "sample_rate", None) or getattr(getattr(piper, "config", None), "sample_rate", 22_050)
    try:
        server = ExclusiveHTTPServer((args.host, args.port), make_handler(args, pocket, piper, int(sample_rate), config))
    except OSError as error:
        if voice_ready(args.host, args.port):
            print("JARVIS — voz local")
            print(f"Status real: já ativa em http://{args.host}:{args.port}/speech")
            print("Produção: nada alterado.")
            return 0
        print(f"FALHA: porta {args.port} ocupada ({error}).")
        return 1
    engine_label = config.get("engine") or ("pocket_tts" if pocket is not None else "piper" if piper is not None else "indisponível")
    print("JARVIS — voz local")
    print(
        f"Status real: engine={engine_label} language={config['language']} "
        f"voice={config['voice']} ultron={config.get('ultron_voice')} "
        f"em http://{args.host}:{args.port}/speech"
    )
    if pocket_error and piper is not None:
        print(f"Fallback: Piper em {Path(piper_path).name}")
    print("Produção: nada alterado; a síntese acontece nesta máquina.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
