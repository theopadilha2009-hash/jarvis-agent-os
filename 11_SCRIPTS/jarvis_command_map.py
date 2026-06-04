from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "197_COMMAND_MAP"
OUT.mkdir(parents=True, exist_ok=True)

COMMANDS = [
    {"command": "home-dashboard home", "use": "visão rápida do estado geral", "when": "começo e fim de sessão"},
    {"command": "fast-status status", "use": "status ultra rápido", "when": "checagem leve"},
    {"command": "command-profiler profile", "use": "mede comandos lentos", "when": "depois de crescimento grande"},
    {"command": "deep-sweep sweep", "use": "qualidade local e compile/cache", "when": "antes de ship"},
    {"command": "marathon-consolidator", "use": "consolida escala, domínios e warnings", "when": "depois de marathon"},
    {"command": "smart-marathon plan", "use": "ver pool/restante/readiness", "when": "antes de gerar features"},
    {"command": "autoship status", "use": "ver se pode commitar com guard", "when": "antes de autoship"},
    {"command": "ship-guard preflight", "use": "pré-checagem de envio", "when": "antes de commit/push sensível"},
    {"command": "operator-brief brief", "use": "resumo de operação", "when": "passar contexto rápido"},
    {"command": "start-here start", "use": "ponto de entrada humano", "when": "quando se perder"},
]

payload = {
    "created_at": datetime.now().isoformat(timespec="seconds"),
    "verdict": "pass",
    "total": len(COMMANDS),
    "commands": COMMANDS,
}

(OUT / "COMMAND_MAP.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

lines = ["# JARVIS Command Map", "", f"Created at: `{payload['created_at']}`", "", "## Core commands", ""]
for item in COMMANDS:
    lines.append(f"- `py -3 11_SCRIPTS/jarvis_ops.py {item['command']}`")
    lines.append(f"  - Use: {item['use']}")
    lines.append(f"  - When: {item['when']}")
lines.append("")
lines.append("Status real: command map generated locally.")
(OUT / "COMMAND_MAP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

print("COMMAND_MAP_DONE")
print(OUT / "COMMAND_MAP.md")
print(json.dumps({"verdict": "pass", "total": len(COMMANDS)}, indent=2))
