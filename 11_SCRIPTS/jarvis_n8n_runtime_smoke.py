from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "05_EXECUCAO" / "216_N8N_RUNTIME_SMOKE"


def latest_file(pattern: str) -> Path | None:
    files = [p for p in REPO.glob(pattern) if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def slug(value: str, fallback: str = "runtime-smoke") -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip().lower()).strip("-")
    return s[:90] or fallback


def find_latest_workflow() -> Path | None:
    candidates = [
        latest_file("05_EXECUCAO/207_N8N_EXPORT_PACKAGER/**/IMPORT_THIS_IN_N8N.json"),
        latest_file("05_EXECUCAO/204_N8N_WORKFLOW_BUILDER/**/workflow_skeleton.importable.json"),
    ]
    return next((p for p in candidates if p and p.exists()), None)


def node_names(workflow: dict[str, Any]) -> list[str]:
    return [str(n.get("name", "")) for n in workflow.get("nodes", []) if isinstance(n, dict)]


def node_types(workflow: dict[str, Any]) -> list[str]:
    return [str(n.get("type", "")) for n in workflow.get("nodes", []) if isinstance(n, dict)]


def connections(workflow: dict[str, Any]) -> dict[str, Any]:
    c = workflow.get("connections", {})
    return c if isinstance(c, dict) else {}


def has_any(names: list[str], terms: list[str]) -> bool:
    hay = "\n".join(names).lower()
    return any(t.lower() in hay for t in terms)


def simulate_case(case: dict[str, Any], names: list[str], types: list[str], conns: dict[str, Any]) -> dict[str, Any]:
    message = str(case.get("message", ""))
    from_me = bool(case.get("fromMe", False))
    text_ok = bool(message.strip())

    route = "normal"
    blocked = []
    warnings = []

    if from_me:
        route = "blocked_anti_loop"
    elif not text_ok:
        route = "fallback_empty_message"
    elif any(x in message.lower() for x in ["humano", "atendente", "pessoa", "suporte"]):
        route = "human_transfer"
    elif len(message) < 3:
        route = "fallback_low_context"

    required_signals = {
        "trigger": any("webhook" in t.lower() or "manual" in t.lower() for t in types),
        "normalization": has_any(names, ["normaliza", "normalize", "payload"]),
        "guard": has_any(names, ["guard", "fallback", "anti", "safety", "confidence"]),
        "logs": has_any(names, ["log", "audit", "registro"]),
        "human_transfer": has_any(names, ["human", "handoff", "transfer", "chatwoot"]),
        "dry_run": has_any(names, ["dry", "safety", "preview"]),
        "response": any("respond" in t.lower() or "http" in t.lower() for t in types),
    }

    for k, ok in required_signals.items():
        if not ok:
            blocked.append(f"missing runtime signal: {k}")

    if not conns:
        blocked.append("workflow has no connections")

    if route in {"fallback_empty_message", "fallback_low_context"} and not required_signals["guard"]:
        blocked.append("fallback route needed but guard signal missing")

    if route == "human_transfer" and not required_signals["human_transfer"]:
        blocked.append("human transfer route needed but human transfer signal missing")

    if route == "blocked_anti_loop" and not required_signals["guard"]:
        blocked.append("anti-loop route needed but guard signal missing")

    if route == "normal" and len(message) < 8:
        warnings.append("normal route with short message")

    return {
        "case": case.get("name", "case"),
        "route": route,
        "message": message,
        "fromMe": from_me,
        "signals": required_signals,
        "blockers": blocked,
        "warnings": warnings,
        "verdict": "pass" if not blocked else "block",
    }


def run(client: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    workflow_path = find_latest_workflow()
    workflow = read_json(workflow_path)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT / f"{ts}_{slug(client)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    names = node_names(workflow)
    types = node_types(workflow)
    conns = connections(workflow)

    cases = [
        {"name": "normal_lead", "message": "Oi, quero saber mais sobre atendimento", "fromMe": False},
        {"name": "human_transfer", "message": "Quero falar com um humano", "fromMe": False},
        {"name": "empty_message", "message": "", "fromMe": False},
        {"name": "anti_loop_from_me", "message": "Mensagem enviada pelo proprio bot", "fromMe": True},
        {"name": "low_context", "message": "oi", "fromMe": False},
    ]

    blockers = []
    warnings = []

    if not workflow_path:
        blockers.append("no latest n8n workflow/export found")
    if workflow.get("active") is not False:
        blockers.append("workflow active must be false for safe runtime smoke")
    if not workflow.get("nodes"):
        blockers.append("workflow has no nodes")
    if len(names) < 5:
        blockers.append("workflow has too few nodes for professional smoke")

    results = [simulate_case(c, names, types, conns) for c in cases] if workflow else []

    for r in results:
        blockers.extend([f"{r['case']}: {b}" for b in r.get("blockers", [])])
        warnings.extend([f"{r['case']}: {w}" for w in r.get("warnings", [])])

    verdict = "pass" if not blockers else "block"

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "client": client,
        "workflow_path": str(workflow_path.relative_to(REPO)) if workflow_path else None,
        "workflow_name": workflow.get("name"),
        "active": workflow.get("active"),
        "nodes": len(names),
        "connection_sources": len(conns),
        "cases": results,
        "blockers": blockers,
        "warnings": warnings,
        "status_real": "local_static_runtime_simulation_only",
        "not_validated": [
            "not imported in n8n UI",
            "not executed in n8n runtime",
            "no real credentials",
            "no real webhook",
            "no production",
        ],
    }

    (out_dir / "N8N_RUNTIME_SMOKE.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# JARVIS n8n Runtime Smoke",
        "",
        f"- verdict: `{verdict}`",
        f"- client: `{client}`",
        f"- workflow: `{payload['workflow_path']}`",
        f"- workflow_name: `{payload['workflow_name']}`",
        f"- active: `{payload['active']}`",
        f"- nodes: `{payload['nodes']}`",
        f"- connection_sources: `{payload['connection_sources']}`",
        "",
        "## Cases",
        "",
    ]

    for r in results:
        md.append(f"- `{r['case']}` route=`{r['route']}` verdict=`{r['verdict']}`")

    md += ["", "## Blockers", ""]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]

    md += ["", "## Warnings", ""]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]

    md += [
        "",
        "## Status real",
        "",
        "Local static runtime simulation only. Still requires n8n UI import and real runtime test.",
        "",
    ]

    (out_dir / "N8N_RUNTIME_SMOKE.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_RUNTIME_SMOKE_DONE")
    print(out_dir / "N8N_RUNTIME_SMOKE.md")
    print(json.dumps({
        "verdict": verdict,
        "workflow_path": payload["workflow_path"],
        "nodes": payload["nodes"],
        "cases": len(results),
        "blockers": blockers,
        "warnings": warnings,
    }, indent=2))

    return 0 if verdict == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="runtime-smoke")
    args = parser.parse_args()
    return run(args.client)


if __name__ == "__main__":
    raise SystemExit(main())
