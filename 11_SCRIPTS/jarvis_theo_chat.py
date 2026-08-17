#!/usr/bin/env python3
"""JARVIS-THEO — interface de terminal da inteligência JARVIS.

Usa o mesmo cérebro do cockpit web (`command_payload` em api/index.py):
OpenRouter para entender, transcrever e conversar. Não abre Claude, Codex,
Grok nem OpenCode.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import jarvis_theo_ui as theo_ui  # noqa: E402
import jarvis_theo_brain as theo_brain  # noqa: E402

ROOT = Path(os.environ.get("JARVIS_HOME") or Path(__file__).resolve().parents[1])
SUPPORT = Path.home() / "Library" / "Application Support" / "JARVIS"
SECRETS_CANDIDATES = (
    Path(os.environ.get("JARVIS_SECRETS_FILE") or "") if os.environ.get("JARVIS_SECRETS_FILE") else None,
    SUPPORT / "secrets.env",
    ROOT / ".env.local",
    ROOT / ".env",
)
LOADABLE_KEYS = {
    "OPENROUTER_API_KEY",
    "OPENROUTER_FALLBACK_API_KEY",
    "OPENROUTER_API_KEYS",
    "OPENROUTER_MODEL",
    "OPENROUTER_MODEL_POOL",
    "OPENROUTER_DEEP_MODEL_POOL",
    "OPENROUTER_ATTACHMENT_MODEL",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_FALLBACK_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "JARVIS_OWNER_TOKEN",
    "JARVIS_ADMIN_USERNAME",
    "JARVIS_ADMIN_PASSWORD_HASH",
}
WEB_INTENT = re.compile(
    r"\b(?:pesquis|busca|procur(?:a|e)|not[ií]cia|pre[cç]o|documenta|"
    r"o\s+que\s+(?:saiu|aconteceu)|como\s+(?:funciona|fazer)|site\s+oficial)\b",
    re.I,
)
SELF_INTENT = re.compile(
    r"\b(?:quem\s+(?:[eé]|voc[eê])|o\s+que\s+voc[eê]\s+[eé]|sobre\s+voc[eê]|"
    r"sua\s+voz|voz\s+local|pocket|o\s+que\s+voc[eê]\s+consegue)\b",
    re.I,
)
LOCAL_TTS_URL = os.environ.get("JARVIS_LOCAL_TTS_URL", "http://127.0.0.1:8123/speech")
MAX_TRANSCRIPT_CHARS = 20_000
MAX_HISTORY = 12
TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".json", ".log"}
INSTALLABLE_KEYS = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_FALLBACK_API_KEY",
    "OPENROUTER_API_KEYS",
    "OPENROUTER_MODEL",
    "OPENROUTER_MODEL_POOL",
    "OPENROUTER_DEEP_MODEL_POOL",
    "OPENROUTER_ATTACHMENT_MODEL",
)
SECRETS_PATH = SUPPORT / "secrets.env"


def load_gateway():
    spec = importlib.util.spec_from_file_location("jarvis_web_gateway", ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def secret_files() -> list[Path]:
    files = []
    for path in SECRETS_CANDIDATES:
        if path and path.is_file():
            files.append(path)
    return files


def load_secrets(environ: dict | None = None) -> list[str]:
    """Load known keys into env. Returns file paths used. Never prints values."""
    env = environ if environ is not None else os.environ
    loaded = []
    for path in secret_files():
        used = False
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            if key not in LOADABLE_KEYS:
                continue
            value = value.strip().strip("'").strip('"')
            if not value or env.get(key, "").strip():
                continue
            env[key] = value
            used = True
        if used:
            loaded.append(str(path))
    return loaded


def openrouter_ready(environ: dict | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return any(str(env.get(name) or "").strip() for name in ("OPENROUTER_API_KEY", "OPENROUTER_FALLBACK_API_KEY"))


def parse_args(argv: list[str] | None = None) -> dict:
    raw = list(argv if argv is not None else sys.argv[1:])
    dry_run = os.environ.get("JARVIS_NO_REPORT") == "1"
    install_keys = False
    setup = False
    parts: list[str] = []
    for token in raw:
        if token in ("--dry-run",):
            dry_run = True
        elif token in ("--install-keys",):
            install_keys = True
        elif token in ("--install-from-env",):
            install_keys = True
        elif token in ("--setup",):
            setup = True
        elif token.startswith("-") and token not in (
            "--dry-run",
            "--install-keys",
            "--install-from-env",
            "--setup",
            "-h",
            "--help",
        ):
            raise SystemExit(f"flag desconhecida: {token}")
        elif token in ("-h", "--help"):
            return {
                "help": True,
                "dry_run": True,
                "install_keys": False,
                "setup": False,
                "prompt": "",
                "source": "",
            }
        else:
            parts.append(token)
    prompt = " ".join(parts).strip()
    source = ""
    if len(parts) == 1:
        candidate = Path(parts[0]).expanduser()
        if candidate.is_file() and candidate.suffix.lower() in TEXT_SUFFIXES:
            if candidate.name.startswith(".env") or candidate.suffix.lower() == ".env":
                raise SystemExit("Recusei ler um arquivo de ambiente.")
            text = candidate.read_text(encoding="utf-8", errors="replace")[:MAX_TRANSCRIPT_CHARS].strip()
            source = str(candidate)
            prompt = (
                "Transcreva com clareza e explique o que isso significa. "
                "Corrija cortes, identifique o assunto e resume o recado.\n\n"
                f"{text}"
            )
    return {
        "help": False,
        "dry_run": dry_run,
        "install_keys": install_keys,
        "setup": setup,
        "prompt": prompt,
        "source": source,
    }


def rotating_slots(environ: dict | None = None) -> int:
    env = environ if environ is not None else os.environ
    count = 0
    if str(env.get("OPENROUTER_API_KEY") or "").strip():
        count += 1
    if str(env.get("OPENROUTER_FALLBACK_API_KEY") or "").strip():
        count += 1
    count += len([item for item in str(env.get("OPENROUTER_API_KEYS") or "").split(",") if item.strip()])
    return count


def print_help() -> None:
    secrets = SUPPORT / "secrets.env"
    print(theo_ui.banner(openrouter_ready(), rotating_slots()))
    print(theo_ui.status_line("Status real: ajuda da interface local. Nada foi enviado ao OpenRouter."))
    print("")
    print("Uso:")
    print("  jarvis-theo                         # conversa")
    print('  jarvis-theo "explica isso pra mim"')
    print("  jarvis-theo recado.txt              # transcreve e entende o arquivo")
    print("  jarvis-theo --dry-run               # preview, sem chamar OpenRouter")
    print("")
    print("No chat: /sair  /limpar  /ajuda")
    print("Se um modelo ou chave acabar, o JARVIS troca sozinho (pool + reserva).")
    print("Pesquisa web entra quando o pedido pede fonte, preço ou notícia.")
    print("Voz: Pocket TTS local (não acaba). /sair  /limpar  /ajuda")
    print("Melhoria de verdade: ele vai com calma e não mexe no disco.")
    print(f"Chaves: {secrets}  |  instalar: jarvis-theo --install-keys")
    print("Outro computador: jarvis-theo --setup")
    print("Produção: nada alterado.")


def print_setup() -> int:
    repo = ROOT
    dest = SECRETS_PATH
    print("JARVIS-THEO — setup noutro computador")
    print("Status real: login = chaves OpenRouter no cofre local. Sem usuário/senha.")
    print("")
    print("1. Copie o repo (git clone) para o outro Mac.")
    print(f"   origem deste: {repo}")
    print("2. Ligar o comando no PATH:")
    print(f'   ln -sfn "{repo}/jarvis-theo" "$HOME/.local/bin/jarvis-theo"')
    print("   e tenha ~/.local/bin no PATH (zshrc).")
    print("3. Cofre (não vai no git, não manda no WhatsApp):")
    print(f"   mkdir -p \"{dest.parent}\"")
    print(f"   nano \"{dest}\"")
    print("   OPENROUTER_API_KEY=sk-or-v1-...")
    print("   OPENROUTER_FALLBACK_API_KEY=sk-or-v1-...")
    print(f"   chmod 600 \"{dest}\"")
    print("4. Conferir: jarvis-theo --dry-run")
    print("5. Usar: jarvis-theo")
    print("")
    print("As mesmas chaves do OpenRouter servem nos dois Macs.")
    print("Produção: nada alterado.")
    return 0


def env_key_names(environ: dict | None = None) -> list[str]:
    env = environ if environ is not None else os.environ
    names = []
    for name in INSTALLABLE_KEYS:
        if str(env.get(name) or "").strip():
            names.append(name)
    return names


def extract_openrouter_lines(text: str) -> dict[str, str]:
    found = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        if key not in INSTALLABLE_KEYS:
            continue
        value = value.strip().strip("'").strip('"')
        if value:
            found[key] = value
    return found


def _kv(path: Path, key: str) -> str:
    if not path.is_file():
        return ""
    prefix = key + "="
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith(prefix):
            return raw.split("=", 1)[1].strip().strip("'").strip('"')
    return ""


def looks_like_openrouter_key(value: str) -> bool:
    text = (value or "").strip()
    return text.startswith("sk-or-") and len(text) >= 24


def pull_openrouter_from_vercel_api() -> dict[str, str]:
    tokens = Path.home() / ".claude" / ".env.tokens"
    project_file = ROOT / ".vercel" / "project.json"
    if not project_file.is_file():
        raise RuntimeError("projeto Vercel não está linkado (.vercel/project.json)")
    project = json.loads(project_file.read_text(encoding="utf-8"))
    token = _kv(tokens, "VERCEL_TOKEN")
    if not token:
        raise RuntimeError("VERCEL_TOKEN ausente em ~/.claude/.env.tokens")
    team = _kv(tokens, "VERCEL_ORG_ID") or str(project.get("orgId") or "")
    project_id = str(project.get("projectId") or "")
    if not project_id:
        raise RuntimeError("projectId ausente no link da Vercel")
    url = f"https://api.vercel.com/v9/projects/{project_id}/env?decrypt=true"
    if team:
        url += f"&teamId={team}"
    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    incoming: dict[str, str] = {}
    for item in data.get("envs") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        if key not in INSTALLABLE_KEYS:
            continue
        targets = item.get("target") or []
        if isinstance(targets, str):
            targets = [targets]
        if "production" not in targets:
            continue
        value = str(item.get("value") or "").strip()
        if value:
            incoming[key] = value
    return incoming


def merge_secret_lines(existing: str, incoming: dict[str, str]) -> str:
    kept = []
    seen = set()
    for raw in existing.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in incoming:
                kept.append(f"{key}={incoming[key]}")
                seen.add(key)
                continue
        if line.strip():
            kept.append(line)
    for key, value in incoming.items():
        if key not in seen:
            kept.append(f"{key}={value}")
    return "\n".join(kept).rstrip() + "\n"


def install_keys_from_vercel(dry_run: bool = False, runner=None) -> int:
    dest = SECRETS_PATH
    print("JARVIS-THEO")
    if dry_run:
        print("Status real: preview da instalação das chaves OpenRouter da Vercel.")
        print(f"Destino: {dest}")
        print("Vai copiar só OPENROUTER_* (principal + reserva + pool).")
        print("Produção: nada alterado.")
        return 0
    if not shutil.which("vercel"):
        print("Status real: `vercel` CLI ausente; não instalei chave.")
        print("Produção: nada alterado.")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    incoming: dict[str, str] = {}
    api_error = ""
    from_env = {
        name: str(os.environ.get(name) or "").strip()
        for name in INSTALLABLE_KEYS
        if str(os.environ.get(name) or "").strip()
    }
    if any(looks_like_openrouter_key(from_env.get(name, "")) for name in ("OPENROUTER_API_KEY", "OPENROUTER_FALLBACK_API_KEY")):
        incoming = from_env
    if not incoming:
        try:
            incoming = pull_openrouter_from_vercel_api()
        except Exception as exc:
            api_error = exc.__class__.__name__
    if not incoming:
        handle = tempfile.NamedTemporaryFile(
            prefix="jarvis-openrouter-",
            suffix=".env",
            delete=False,
        )
        tmp = Path(handle.name)
        handle.close()
        run = runner or subprocess.run
        try:
            result = run(
                ["vercel", "env", "pull", str(tmp), "--environment", "production", "--yes"],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                print("Status real: Vercel recusou o pull das chaves.")
                if api_error:
                    print(f"API: {api_error}")
                err = (result.stderr or result.stdout or "").strip().splitlines()
                if err:
                    print(err[-1][:200])
                print("Produção: nada alterado.")
                return 1
            incoming = extract_openrouter_lines(tmp.read_text(encoding="utf-8", errors="replace"))
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    if "OPENROUTER_API_KEY" not in incoming and "OPENROUTER_FALLBACK_API_KEY" not in incoming:
        print("Status real: o pull não trouxe chave OpenRouter.")
        print("Produção: nada alterado.")
        return 1
    key_ok = any(
        looks_like_openrouter_key(incoming.get(name, ""))
        for name in ("OPENROUTER_API_KEY", "OPENROUTER_FALLBACK_API_KEY")
    )
    if not key_ok:
        print("Status real: o valor puxado não parece uma chave OpenRouter.")
        print("Não gravei o cofre para não sobrescrever com lixo.")
        print("Produção: nada alterado.")
        return 1
    previous = dest.read_text(encoding="utf-8", errors="replace") if dest.is_file() else ""
    dest.write_text(merge_secret_lines(previous, incoming), encoding="utf-8")
    dest.chmod(0o600)
    print("Status real: chaves OpenRouter gravadas no cofre local.")
    print(f"Arquivo: {dest}")
    print("Nomes: " + ", ".join(sorted(incoming)))
    print("Se uma acabar, o JARVIS usa a reserva e o pool de modelos.")
    print("Produção: nada alterado.")
    return 0


def route_note(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    bits = []
    if payload.get("openrouter_key_failover"):
        bits.append("chave anterior esgotou; usei a reserva")
    routing = payload.get("model_routing") if isinstance(payload.get("model_routing"), dict) else {}
    attempts = routing.get("compatibility_attempts") or []
    if routing.get("compatibility_fallback") or len(attempts) > 1:
        bits.append("troquei de modelo no pool")
        selected = str(routing.get("selected") or payload.get("model") or "").strip()
        if selected:
            bits.append(f"agora: {selected}")
    return "; ".join(bits)


def format_reply(payload: dict, status: int) -> str:
    if not isinstance(payload, dict):
        return "O JARVIS não devolveu uma resposta utilizável."
    text = (
        payload.get("message")
        or payload.get("error")
        or payload.get("summary")
        or ""
    )
    text = str(text).strip()
    if text:
        return text
    if status >= 400:
        return "Essa rota falhou; na próxima eu troco de modelo/chave e tento de novo."
    return "Recebi o pedido, mas a resposta veio vazia."


def wants_web(prompt: str) -> bool:
    return bool(WEB_INTENT.search(prompt or ""))


def local_reply(prompt: str) -> dict:
    text = (prompt or "").strip()
    lowered = text.casefold()
    if "voz" in lowered or "pocket" in lowered or "falar" in lowered:
        message = (
            "Minha voz principal neste Mac é Pocket TTS local: portuguese + bill_boerst. "
            "Sem cota, sem chave, sem OpenRouter. Se o servidor da 8123 cair, o alto-falante usa o say."
        )
    elif SELF_INTENT.search(text) or "o que você consegue" in lowered:
        message = (
            "Sou o JARVIS do Theo Padilha — lab local, um operador. "
            "No terminal eu penso, pesquiso a web e falo. "
            "Não mexo em disco, .env, deploy nem produção neste chat. "
            "Voz: Pocket TTS. Login do Theo é o mesmo do Ultron. "
            "Amigos aprovados usam JARVIS + modo code, sem Mac."
        )
    else:
        message = (
            "As rotas rápidas da nuvem falharam agora. Continuo aqui: peça de novo, "
            "pergunte quem eu sou, ou peça uma pesquisa que eu tento pelas fontes livres."
        )
    return {
        "ok": True,
        "status": 200,
        "message": message,
        "provider": "local_fallback",
        "model": "jarvis-local",
    }


def speak_local(text: str) -> None:
    """Fala pelo Pocket local. Falhou? o chat segue sem travar."""
    clean = (text or "").strip()[:2_200]
    if not clean or os.environ.get("JARVIS_LOCAL_VOICE") == "0":
        return
    if not shutil.which("afplay"):
        return

    def _run() -> None:
        path = ""
        try:
            request = Request(
                LOCAL_TTS_URL,
                data=json.dumps({"text": clean}, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=25) as response:
                audio = response.read()
            if not audio:
                return
            suffix = ".wav" if audio[:4] == b"RIFF" else ".mp3"
            handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            handle.write(audio)
            handle.close()
            path = handle.name
            subprocess.run(["/usr/bin/afplay", path], capture_output=True, timeout=90, check=False)
        except (URLError, OSError, subprocess.TimeoutExpired, ValueError):
            return
        finally:
            if path:
                Path(path).unlink(missing_ok=True)

    threading.Thread(target=_run, daemon=True).start()


def ask_web(prompt: str) -> tuple[dict, int] | None:
    if not wants_web(prompt):
        return None
    try:
        gateway = load_gateway()
        payload, status = gateway.assistant_response({"command": prompt, "prompt": prompt})
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    text = payload.get("message") or payload.get("summary") or ""
    if not text:
        return None
    payload = dict(payload)
    payload.setdefault("ok", status < 400)
    payload.setdefault("status", status)
    payload.setdefault("provider", payload.get("provider") or "web")
    return payload, status


def ask(prompt: str, history: list[dict], chat_fn=None) -> tuple[dict, int]:
    web = None if chat_fn is not None else ask_web(prompt)
    if web:
        return web
    runner = chat_fn or theo_brain.chat
    payload = runner(prompt, history)
    status = int(payload.get("status") or (200 if payload.get("ok") else 502))
    if status >= 400 or not payload.get("ok", True):
        fallback = local_reply(prompt)
        return fallback, 200
    return payload, status


def preview(opts: dict, ready: bool) -> int:
    names = env_key_names()
    print(theo_ui.banner(ready, rotating_slots()))
    print(theo_ui.status_line("Status real: preview da interface. OpenRouter não foi chamado."))
    print(theo_ui.muted("Cérebro: OpenRouter + pesquisa web. Voz: Pocket TTS local."))
    print(theo_ui.muted("Se uma rota da nuvem bloquear, eu troco de chave/modelo; se todas caírem, respondo local."))
    print(theo_ui.muted(f"Chaves locais: {len(names)} ({', '.join(names) or 'nenhuma'})"))
    if not ready:
        print(f"Instalar: jarvis-theo --install-keys  →  {SECRETS_PATH}")
    if opts.get("source"):
        print(f"Arquivo: {opts['source']}")
    if opts.get("prompt"):
        print(f"Pedido: {opts['prompt'][:240]}")
    else:
        print("Modo: conversa interativa")
    print("Produção: nada alterado.")
    return 0


def print_turn(payload: dict, status: int) -> None:
    note = route_note(payload)
    if note:
        print(theo_ui.route_line(note))
    reply = format_reply(payload, status)
    print(theo_ui.jarvis_prefix() + reply)
    print("")
    speak_local(reply)


def one_shot(prompt: str, chat_fn=None) -> int:
    theo_ui.apply_room()
    try:
        print(theo_ui.banner(True, rotating_slots()))
        print(theo_ui.status_line("Status real: um pedido ao cérebro OpenRouter."))
        payload, status = ask(prompt, [], chat_fn=chat_fn)
        print("")
        print_turn(payload, status)
        print(theo_ui.muted("Produção: nada alterado."))
    finally:
        theo_ui.restore_room()
    return 0 if payload.get("ok", status < 400) and status < 400 else 1


def repl(chat_fn=None) -> int:
    history: list[dict] = []
    theo_ui.apply_room()
    try:
        theo_ui.play_intro(True, rotating_slots())
        print(theo_ui.status_line("Status real: conversa local com o cérebro OpenRouter."))
        print(theo_ui.muted("Se uma rota acabar, troco de modelo/chave e sigo."))
        print(theo_ui.muted("Não escrevo código no disco. Produção: nada alterado."))
        print("")
        while True:
            try:
                line = input(theo_ui.user_prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print("")
                print(theo_ui.muted("JARVIS-THEO encerrado."))
                return 0
            if not line:
                continue
            lowered = line.lower()
            if lowered in {"/sair", "/exit", "/quit", "sair"}:
                print(theo_ui.muted("Até já."))
                return 0
            if lowered in {"/limpar", "/clear"}:
                history.clear()
                print(theo_ui.muted("Conversa limpa. Memórias confirmadas continuam guardadas."))
                continue
            if lowered in {"/ajuda", "/help"}:
                print_help()
                continue
            if lowered in {"/aplicar", "/apply"}:
                print(theo_ui.muted("Sem rascunho pendente. Eu não mexo no disco sozinho."))
                continue
            try:
                payload, status = ask(line, history, chat_fn=chat_fn)
            except Exception as exc:
                print(theo_ui.jarvis_prefix() + f"essa rota caiu ({exc.__class__.__name__}). Manda de novo que eu troco.")
                continue
            print_turn(payload, status)
            if status < 400 and isinstance(payload, dict) and payload.get("ok", True):
                history.append({"role": "user", "content": line})
                history.append({"role": "assistant", "content": format_reply(payload, status)})
                if len(history) > MAX_HISTORY:
                    history = history[-MAX_HISTORY:]
        return 0
    finally:
        theo_ui.restore_room()


def execute(argv: list[str] | None = None, gateway=None, chat_fn=None) -> int:
    try:
        opts = parse_args(argv)
    except SystemExit as exc:
        print("JARVIS-THEO")
        print(f"Status real: {exc}.")
        print("Produção: nada alterado.")
        return 1
    if opts.get("help"):
        print_help()
        return 0
    if opts.get("setup"):
        return print_setup()
    if opts.get("install_keys"):
        return install_keys_from_vercel(dry_run=opts["dry_run"])

    loaded = load_secrets()
    ready = openrouter_ready()
    if opts["dry_run"]:
        return preview(opts, ready)

    if not ready:
        print("JARVIS-THEO")
        print("Status real: OpenRouter não está configurado neste Mac.")
        print(f"Rode: jarvis-theo --install-keys")
        print(f"Ou crie {SECRETS_PATH} com OPENROUTER_API_KEY=...")
        if loaded:
            print("Li um arquivo de segredos, mas a chave do OpenRouter não estava lá.")
        print("Produção: nada alterado.")
        return 1

    runner = chat_fn
    if runner is None and gateway is not None and hasattr(gateway, "chat"):
        runner = gateway.chat
    if opts["prompt"]:
        return one_shot(opts["prompt"], chat_fn=runner)
    return repl(chat_fn=runner)


def main() -> int:
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
