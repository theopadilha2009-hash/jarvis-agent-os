from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "133_BRAIN_ROUTER"
REPORT = OUT / "BRAIN_ROUTER_REPORT.md"
STATE = OUT / "BRAIN_ROUTER_STATE.json"

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_GOAL = "melhorar autonomia do Jarvis"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def cli_available(name: str) -> bool:
    return shutil.which(name) is not None


def ollama_tags() -> dict:
    url = f"{OLLAMA_URL}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            models = [item.get("name", "") for item in data.get("models", []) if item.get("name")]
            return {
                "ok": True,
                "url": url,
                "models": models,
                "error": "",
            }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "models": [],
            "error": str(exc),
        }


def provider_status() -> dict:
    ollama = ollama_tags()

    status = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "local": {
            "ollama_cli": cli_available("ollama"),
            "ollama_http": ollama["ok"],
            "ollama_url": ollama["url"],
            "ollama_models": ollama["models"][:20],
            "ollama_error": ollama["error"],
        },
        "cli": {
            "claude_code": cli_available("claude"),
            "git": cli_available("git"),
            "python": True,
        },
        "api_env": {
            "groq": env_present("GROQ_API_KEY"),
            "openai": env_present("OPENAI_API_KEY"),
            "anthropic": env_present("ANTHROPIC_API_KEY"),
            "tavily": env_present("TAVILY_API_KEY"),
            "brave": env_present("BRAVE_API_KEY"),
        },
        "safety": {
            "prints_secret_values": False,
            "auto_paid_calls_default": False,
            "allow_model_calls_env": env_present("JARVIS_ALLOW_MODEL_CALLS"),
        },
    }

    return status


def choose_provider(task: str, prefer: str = "auto") -> dict:
    status = provider_status()
    prefer = (prefer or "auto").lower().strip()
    task = (task or "general").lower().strip()

    available = {
        "ollama": status["local"]["ollama_http"],
        "claude_code": status["cli"]["claude_code"],
        "groq": status["api_env"]["groq"],
        "openai": status["api_env"]["openai"],
        "anthropic": status["api_env"]["anthropic"],
        "offline": True,
    }

    if prefer != "auto":
        selected = prefer if available.get(prefer, False) else "offline"
    elif task in {"code", "build", "fix", "repo"} and available["claude_code"]:
        selected = "claude_code"
    elif available["ollama"]:
        selected = "ollama"
    elif available["groq"]:
        selected = "groq"
    elif available["openai"]:
        selected = "openai"
    elif available["anthropic"]:
        selected = "anthropic"
    else:
        selected = "offline"

    if selected == "claude_code":
        mode = "manual_cli_adapter"
        cost_mode = "depends_on_claude_plan"
        next_action = "Use Claude Code manually from terminal or VS Code with the generated prompt pack."
    elif selected == "ollama":
        mode = "local_model"
        cost_mode = "free_local_compute"
        next_action = "Use local Ollama model for draft reasoning when allowed."
    elif selected == "groq":
        mode = "api_adapter_pending"
        cost_mode = "free_or_low_cost_api"
        next_action = "Use GROQ_API_KEY only if configured in environment."
    elif selected == "openai":
        mode = "api_adapter_pending"
        cost_mode = "paid_api_possible"
        next_action = "Use OPENAI_API_KEY only if configured and budget guard allows."
    elif selected == "anthropic":
        mode = "api_adapter_pending"
        cost_mode = "paid_api_possible"
        next_action = "Use ANTHROPIC_API_KEY only if configured and budget guard allows."
    else:
        mode = "offline_planner"
        cost_mode = "zero_cost"
        next_action = "Generate structured plan/prompt without external model call."

    return {
        "task": task,
        "prefer": prefer,
        "selected": selected,
        "mode": mode,
        "cost_mode": cost_mode,
        "available": available,
        "status": status,
        "next_action": next_action,
    }


def prompt_pack(goal: str, task: str, selected: str) -> dict:
    goal = goal.strip() or DEFAULT_GOAL
    task = task.strip() or "general"

    system = (
        "You are Jarvis Agent OS. Work safely inside the local repository. "
        "Do not expose secrets. Do not modify .env. Prefer small validated patches. "
        "Always inspect status, change only expected files, run tests, then summarize."
    )

    user = f"""
Goal: {goal}
Task type: {task}
Selected brain/provider: {selected}

Required behavior:
1. Read the current project state.
2. Propose the smallest useful improvement.
3. Create or modify files only when safe.
4. Run validation.
5. If validation fails, fix once.
6. Never push directly from worker folders.
7. Return changed files, validation result, and next step.
""".strip()

    return {
        "system": system,
        "user": user,
        "safe_shell_context": [
            "git status -sb",
            "py -3 -m py_compile 11_SCRIPTS/jarvis_ops.py",
            ".\\jarvis.bat think \"melhorar autonomia do Jarvis\"",
        ],
    }


def ollama_generate(prompt: str, model: str | None = None) -> dict:
    tags = ollama_tags()
    if not tags["ok"]:
        return {"ok": False, "error": tags["error"], "text": ""}

    selected_model = model or (tags["models"][0] if tags["models"] else "")
    if not selected_model:
        return {"ok": False, "error": "NO_OLLAMA_MODEL_FOUND", "text": ""}

    payload = {
        "model": selected_model,
        "prompt": prompt,
        "stream": False,
    }

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            return {
                "ok": True,
                "model": selected_model,
                "text": data.get("response", ""),
                "raw_keys": sorted(data.keys()),
            }
    except Exception as exc:
        return {"ok": False, "model": selected_model, "error": str(exc), "text": ""}


def execute(action: str, goal: str, task: str, prefer: str, allow_calls: bool) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    route = choose_provider(task, prefer)
    pack = prompt_pack(goal, task, route["selected"])

    model_response = None

    if action == "status":
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "status": provider_status(),
        }

    elif action == "route":
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "goal": goal,
            "task": task,
            "route": route,
            "prompt_pack": pack,
        }

    elif action == "prompt":
        if allow_calls and route["selected"] == "ollama":
            model_response = ollama_generate(pack["system"] + "\n\n" + pack["user"])

        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "goal": goal,
            "task": task,
            "route": route,
            "prompt_pack": pack,
            "allow_calls": allow_calls,
            "model_response": model_response,
        }

    else:
        raise ValueError(f"unknown action: {action}")

    write_outputs(payload)

    print("BRAIN_ROUTER_DONE")
    print(REPORT)

    compact = {
        "action": action,
        "selected": payload.get("route", {}).get("selected"),
        "mode": payload.get("route", {}).get("mode"),
        "cost_mode": payload.get("route", {}).get("cost_mode"),
        "allow_calls": allow_calls,
    }

    if model_response is not None:
        text = str(model_response.get("text") or "")
        compact["model_ok"] = model_response.get("ok")
        compact["model"] = model_response.get("model")
        compact["model_response_length"] = len(text)
        compact["model_response_preview"] = text[:700]

    if action == "status":
        compact = {
            "action": action,
            "ollama_http": payload["status"]["local"]["ollama_http"],
            "ollama_models": payload["status"]["local"]["ollama_models"],
            "claude_code": payload["status"]["cli"]["claude_code"],
            "api_env": payload["status"]["api_env"],
        }

    print(json.dumps(compact, ensure_ascii=False, indent=2))
    return 0


def write_outputs(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Brain Router — Block 133",
        "",
        f"Generated at: `{payload.get('created_at')}`",
        f"Action: `{payload.get('action')}`",
        "",
        "## Payload",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ]

    if payload.get("model_response") and payload["model_response"].get("text"):
        (OUT / "LAST_MODEL_RESPONSE.md").write_text(
            payload["model_response"]["text"],
            encoding="utf-8",
        )

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Block 133 Brain Router")
    parser.add_argument("action", choices=["status", "route", "prompt"])
    parser.add_argument("goal", nargs="*", default=[DEFAULT_GOAL])
    parser.add_argument("--task", default="general")
    parser.add_argument("--prefer", default="auto")
    parser.add_argument("--allow-calls", action="store_true")
    args = parser.parse_args()

    goal = " ".join(args.goal).strip() or DEFAULT_GOAL

    return execute(
        args.action,
        goal=goal,
        task=args.task,
        prefer=args.prefer,
        allow_calls=args.allow_calls,
    )


if __name__ == "__main__":
    raise SystemExit(main())
