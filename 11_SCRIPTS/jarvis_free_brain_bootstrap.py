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
OUT = REPO / "05_EXECUCAO" / "135_FREE_BRAIN_BOOTSTRAP"
REPORT = OUT / "FREE_BRAIN_BOOTSTRAP.md"
STATE = OUT / "FREE_BRAIN_BOOTSTRAP.json"


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


def ollama_status() -> dict:
    url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        return {
            "http": True,
            "url": url,
            "models": [m.get("name", "") for m in data.get("models", []) if m.get("name")],
            "error": "",
        }
    except Exception as exc:
        return {
            "http": False,
            "url": url,
            "models": [],
            "error": str(exc),
        }


def status_payload() -> dict:
    code_winget, winget_out = run(["winget", "--version"])
    code_ollama, ollama_version = run(["ollama", "--version"])
    ollama = ollama_status()

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "winget": {
            "ok": code_winget == 0,
            "output": winget_out,
        },
        "ollama": {
            "cli": code_ollama == 0,
            "version": ollama_version,
            "http": ollama["http"],
            "models": ollama["models"],
            "error": ollama["error"],
        },
        "env": {
            "groq": has_env("GROQ_API_KEY"),
            "openai": has_env("OPENAI_API_KEY"),
            "anthropic": has_env("ANTHROPIC_API_KEY"),
            "tavily": has_env("TAVILY_API_KEY"),
            "brave": has_env("BRAVE_API_KEY"),
        },
        "recommended_order": [
            "1. Ollama local/free first.",
            "2. Groq key only if you want cheap/free cloud speed.",
            "3. Claude Code only when you want stronger repo coding.",
            "4. OpenAI/Anthropic only behind budget guard.",
        ],
    }


def install_ollama_plan() -> dict:
    payload = status_payload()

    commands = []

    if not payload["winget"]["ok"]:
        commands.append({
            "title": "winget missing",
            "command": "Install Ollama manually from the official installer, then restart terminal.",
            "safe": True,
        })
    elif not payload["ollama"]["cli"]:
        commands.append({
            "title": "search Ollama package",
            "command": "winget search Ollama",
            "safe": True,
        })
        commands.append({
            "title": "install Ollama manually after confirming package id",
            "command": "winget install <OFFICIAL_OLLAMA_PACKAGE_ID>",
            "safe": True,
        })
    else:
        commands.append({
            "title": "Ollama already installed",
            "command": "ollama --version",
            "safe": True,
        })

    if payload["ollama"]["cli"] and not payload["ollama"]["models"]:
        commands += [
            {
                "title": "pull small local model",
                "command": "ollama pull llama3.2:1b",
                "safe": True,
            },
            {
                "title": "or pull coding model if your PC handles it",
                "command": "ollama pull qwen2.5-coder:1.5b",
                "safe": True,
            },
        ]

    commands += [
        {
            "title": "test brain after setup",
            "command": 'py -3 11_SCRIPTS/jarvis_ops.py brain status',
            "safe": True,
        },
        {
            "title": "test local model call only after model exists",
            "command": 'py -3 11_SCRIPTS/jarvis_ops.py brain prompt "melhorar autonomia do Jarvis" --task code --prefer ollama --allow-calls',
            "safe": True,
        },
    ]

    payload["install_plan"] = commands
    return payload


def groq_plan() -> dict:
    payload = status_payload()

    payload["groq_setup"] = {
        "current": payload["env"]["groq"],
        "rules": [
            "Never write API keys into repo files.",
            "Never commit .env.",
            "Set the key only in the terminal/user environment.",
            "Restart terminal after setx.",
        ],
        "commands": [
            'setx GROQ_API_KEY "PASTE_KEY_HERE"',
            'py -3 11_SCRIPTS/jarvis_ops.py brain status',
            'py -3 11_SCRIPTS/jarvis_ops.py brain route "criar scripts sozinho" --task code --prefer groq',
        ],
    }

    return payload


def write(payload: dict, mode: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Free Brain Bootstrap — Block 135",
        "",
        f"Generated at: `{payload['created_at']}`",
        f"Mode: `{mode}`",
        "",
        "## Compact status",
        "",
        "```json",
        json.dumps({
            "winget": payload["winget"],
            "ollama": payload["ollama"],
            "env": payload["env"],
        }, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Recommended order",
        "",
    ]

    for item in payload["recommended_order"]:
        lines.append(f"- {item}")

    if "install_plan" in payload:
        lines += ["", "## Ollama install plan", ""]
        for item in payload["install_plan"]:
            lines += [
                f"### {item['title']}",
                "",
                "```powershell",
                item["command"],
                "```",
                "",
            ]

    if "groq_setup" in payload:
        lines += [
            "",
            "## Groq setup",
            "",
            "```json",
            json.dumps(payload["groq_setup"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 135 Free Brain Bootstrap")
    parser.add_argument("mode", choices=["status", "ollama-plan", "groq-plan"], nargs="?", default="status")
    args = parser.parse_args()

    if args.mode == "status":
        payload = status_payload()
    elif args.mode == "ollama-plan":
        payload = install_ollama_plan()
    elif args.mode == "groq-plan":
        payload = groq_plan()
    else:
        raise ValueError(args.mode)

    write(payload, args.mode)

    print("FREE_BRAIN_BOOTSTRAP_DONE")
    print(REPORT)
    print(json.dumps({
        "mode": args.mode,
        "ollama_cli": payload["ollama"]["cli"],
        "ollama_http": payload["ollama"]["http"],
        "ollama_models": payload["ollama"]["models"],
        "groq_env": payload["env"]["groq"],
        "next": "open report and follow ollama-plan/groq-plan if needed",
    }, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
