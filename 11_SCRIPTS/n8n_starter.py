#!/usr/bin/env python3
import json, re, sys, uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "05_EXECUCAO" / "46_N8N_STARTERS"

def slug(s):
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9áàâãéèêíóôõúçñ]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")[:80] or "workflow"

def node(name, type_name, pos, parameters=None, type_version=1):
    return {
        "parameters": parameters or {},
        "id": str(uuid.uuid4()),
        "name": name,
        "type": type_name,
        "typeVersion": type_version,
        "position": pos
    }

def main():
    goal = " ".join(sys.argv[1:]).strip()
    if not goal:
        print("uso: ./jarvis-n8n ideia")
        return 2

    folder = OUT / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_" + slug(goal))
    folder.mkdir(parents=True, exist_ok=True)

    n1 = node("Manual Trigger", "n8n-nodes-base.manualTrigger", [0, 0])
    n2 = node("Set - Entrada", "n8n-nodes-base.set", [260, 0], {
        "values": {
            "string": [
                {"name": "goal", "value": goal},
                {"name": "status_real", "value": "rascunho_local"},
                {"name": "source", "value": "jarvis-n8n"}
            ]
        },
        "options": {}
    })
    n3 = node("Code - Processar", "n8n-nodes-base.code", [520, 0], {
        "jsCode": "return items.map(item => ({ json: { ...item.json, ok: true, message: 'starter gerado pelo JARVIS', processed_at: new Date().toISOString() } }));"
    }, 2)
    n4 = node("Set - Resultado", "n8n-nodes-base.set", [780, 0], {
        "values": {
            "string": [
                {"name": "resultado", "value": "starter_ok"},
                {"name": "proximo_passo", "value": "adaptar nodes reais no n8n"}
            ]
        },
        "options": {}
    })

    workflow = {
        "name": "JARVIS Starter - " + goal[:60],
        "nodes": [n1, n2, n3, n4],
        "connections": {
            "Manual Trigger": {"main": [[{"node": "Set - Entrada", "type": "main", "index": 0}]]},
            "Set - Entrada": {"main": [[{"node": "Code - Processar", "type": "main", "index": 0}]]},
            "Code - Processar": {"main": [[{"node": "Set - Resultado", "type": "main", "index": 0}]]}
        },
        "active": False,
        "settings": {},
        "versionId": str(uuid.uuid4()),
        "meta": {"generated_by": "JARVIS local"}
    }

    wf = folder / "workflow.json"
    wf.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "README.md").write_text(
        "# n8n Starter\n\nIdeia: " + goal + "\n\nImportar workflow.json no n8n com active=false.\n",
        encoding="utf-8"
    )

    print("N8N_STARTER_OK")
    print("pasta:", folder.relative_to(ROOT))
    print("json:", wf.relative_to(ROOT))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
