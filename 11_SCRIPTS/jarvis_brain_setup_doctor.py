from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "134_BRAIN_SETUP_DOCTOR"
REPORT = OUT / "BRAIN_SETUP_DOCTOR.md"
STATE = OUT / "BRAIN_SETUP_DOCTOR.json"


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
        return result.returncode, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return 127, f"COMMAND_NOT_FOUND: {cmd[0]}"


def has_cli(name: str) -> bool:
    return shutil.which(name) is not None


def has_env(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def ollama_http() -> dict:
    url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        return {
            "ok": True,
            "url": url,
            "models": [m.get("name", "") for m in data.get("models", []) if m.get("name")],
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "models": [],
            "error": str(exc),
        }


def doctor() -> dict:
    code, winget = run(["winget", "--version"])
    code_npm, npm = run(["npm", "--version"])

    ollama = ollama_http()

    checks = {
        "python": {
            "ok": True,
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
        "git": {
            "ok": has_cli("git"),
        },
        "winget": {
            "ok": code == 0,
            "version": winget,
        },
        "npm": {
            "ok": code_npm == 0,
            "version": npm,
        },
        "ollama": {
            "cli": has_cli("ollama"),
            "http": ollama["ok"],
            "models": ollama["models"],
            "error": ollama["error"],
        },
        "claude_code": {
            "cli": has_cli("claude"),
        },
        "api_keys_present": {
            "groq": has_env("GROQ_API_KEY"),
            "openai": has_env("OPENAI_API_KEY"),
            "anthropic": has_env("ANTHROPIC_API_KEY"),
            "tavily": has_env("TAVILY_API_KEY"),
            "brave": has_env("BRAVE_API_KEY"),
        },
    }

    recommended_next = []

    if not checks["ollama"]["http"]:
        recommended_next.append("Install/start Ollama for free local model routing.")

    if checks["ollama"]["http"] and not checks["ollama"]["models"]:
        recommended_next.append("Pull a small local model in Ollama, for example llama3.2 or qwen2.5-coder if available.")

    if not checks["claude_code"]["cli"]:
        recommended_next.append("Install Claude Code later if you want the strongest coding adapter.")

    if not any(checks["api_keys_present"].values()):
        recommended_next.append("Optional: add Groq/OpenAI/Anthropic/Tavily/Brave keys as environment variables only, never inside Git.")

    if checks["ollama"]["http"] or any(checks["api_keys_present"].values()) or checks["claude_code"]["cli"]:
        recommended_next.append("Run: py -3 11_SCRIPTS\\jarvis_ops.py brain status")

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "checks": checks,
        "recommended_next": recommended_next,
        "safe_commands": {
            "check_brain": "py -3 11_SCRIPTS\\jarvis_ops.py brain status",
            "route_code": 'py -3 11_SCRIPTS\\jarvis_ops.py brain route "criar scripts sozinho" --task code',
            "jarvis_think": '.\\jarvis.bat think "melhorar autonomia do Jarvis"',
            "jarvis_build": '.\\jarvis.bat build "melhorar autonomia do Jarvis"',
        },
        "install_notes": {
            "ollama_windows": [
                "Option A: install Ollama manually from the official website.",
                "Option B: use winget search Ollama, then install the matching official package.",
                "After install, open Ollama once or restart terminal, then run ollama list.",
            ],
            "groq_free_first": [
                "Create a Groq API key only if you want a free/cheap cloud model.",
                "Set it only as an environment variable: setx GROQ_API_KEY \"your_key_here\"",
                "Restart terminal after setx.",
            ],
            "no_secrets_rule": [
                "Never paste keys into repo files.",
                "Never commit .env.",
                "Never send API keys into chat logs.",
            ],
        },
    }


def write(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Brain Setup Doctor — Block 134",
        "",
        f"Generated at: `{payload['created_at']}`",
        "",
        "## Current checks",
        "",
        "```json",
        json.dumps(payload["checks"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Recommended next",
        "",
    ]

    for item in payload["recommended_next"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Safe commands",
        "",
        "```powershell",
    ]

    for cmd in payload["safe_commands"].values():
        lines.append(cmd)

    lines += [
        "```",
        "",
        "## Install notes",
        "",
        "```json",
        json.dumps(payload["install_notes"], ensure_ascii=False, indent=2),
        "```",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 134 Brain Setup Doctor")
    parser.add_argument("action", choices=["doctor"], nargs="?", default="doctor")
    args = parser.parse_args()

    payload = doctor()
    write(payload)

    print("BRAIN_SETUP_DOCTOR_DONE")
    print(REPORT)
    print(json.dumps({
        "ollama_http": payload["checks"]["ollama"]["http"],
        "ollama_models": payload["checks"]["ollama"]["models"],
        "claude_code": payload["checks"]["claude_code"]["cli"],
        "api_keys_present": payload["checks"]["api_keys_present"],
        "recommended_next": payload["recommended_next"],
    }, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
