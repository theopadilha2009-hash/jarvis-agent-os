#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "05_EXECUCAO" / "205_N8N_WORKFLOW_VALIDATOR"
OUT.mkdir(parents=True, exist_ok=True)

SECRET_KEY_PATTERNS = [
    "token", "api_key", "apikey", "authorization", "bearer", "client_secret",
    "password", "passwd", "secret", "service_role", "private_key", "access_key",
    "refresh_token", "instance_token", "cookie", "session",
]

SECRET_VALUE_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{12,}", re.I),
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}", re.I),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{12,}", re.I),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}", re.I),
    re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}", re.I),
]

PROFESSIONAL_SIGNALS = {
    "trigger": ["webhook", "manualtrigger", "scheduletrigger", "formtrigger", "trigger"],
    "normalization": ["set", "code", "function", "editfields"],
    "branching": ["if", "switch", "filter"],
    "logs": ["log", "postgres", "supabase", "sheet", "database", "data table", "datatable"],
    "fallback": ["fallback", "error", "fail", "retry", "catch"],
    "human_transfer": ["human", "handoff", "transfer", "chatwoot", "atendente", "pausa"],
    "dry_run_or_safety": ["dry", "mock", "test", "approval", "approve", "gate", "safe"],
    "memory_or_state": ["redis", "memory", "postgres", "supabase", "buffer", "state"],
    "ai_agent": ["ai agent", "openai", "anthropic", "gemini", "llm", "agent"],
}

def now_slug() -> str:
    return time.strftime("%Y%m%d_%H%M%S")

def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))

def walk(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k, v
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")

def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)

def node_text(node: dict[str, Any]) -> str:
    parts = [
        node.get("name", ""),
        node.get("type", ""),
        json.dumps(node.get("parameters", {}), ensure_ascii=False),
    ]
    return " ".join(str(x).lower() for x in parts)

def detect_secrets(data: dict[str, Any]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []

    for p, k, v in walk(data):
        key = str(k).lower()
        text = as_text(v)

        if any(pattern in key for pattern in SECRET_KEY_PATTERNS):
            safe_key = any(x in key for x in ["credentials_included", "requires_human_validation", "status_real"])
            safe_value = text.strip().lower() in {"", "false", "true", "none", "null", "not_production", "skeleton_only_not_production"}
            expression_value = text.strip().startswith("={{")
            if text and not safe_key and not safe_value and not expression_value and "credential" not in key:
                safe_preview = text[:8] + "..." if len(text) > 8 else "***"
                hits.append({
                    "path": p,
                    "kind": "sensitive_key",
                    "preview": safe_preview,
                })

        if isinstance(v, str):
            low = v.lower()
            if ".env" in low or "service_role" in low:
                hits.append({
                    "path": p,
                    "kind": "sensitive_reference",
                    "preview": v[:40] + ("..." if len(v) > 40 else ""),
                })
            for rx in SECRET_VALUE_PATTERNS:
                if rx.search(v) and not v.strip().startswith("={{"):
                    hits.append({
                        "path": p,
                        "kind": "secret_like_value",
                        "preview": v[:8] + "...",
                    })
                    break

    return hits[:40]

def validate_shape(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []

    if not isinstance(data, dict):
        return ["workflow root is not an object"]

    if "name" not in data:
        blockers.append("missing workflow name")

    if "nodes" not in data or not isinstance(data.get("nodes"), list):
        blockers.append("missing nodes[]")

    if "connections" not in data or not isinstance(data.get("connections"), dict):
        blockers.append("missing connections{}")

    if data.get("active") is not False:
        blockers.append("workflow active must be false for safe import QA")

    nodes = data.get("nodes") or []
    if isinstance(nodes, list):
        ids = set()
        names = set()
        for i, n in enumerate(nodes):
            if not isinstance(n, dict):
                blockers.append(f"node[{i}] is not object")
                continue
            if not n.get("name"):
                blockers.append(f"node[{i}] missing name")
            if not n.get("type"):
                blockers.append(f"node[{i}] missing type")
            if "position" not in n:
                blockers.append(f"node[{i}] missing position")
            node_id = n.get("id")
            if node_id:
                if node_id in ids:
                    blockers.append(f"duplicate node id: {node_id}")
                ids.add(node_id)
            name = n.get("name")
            if name:
                if name in names:
                    blockers.append(f"duplicate node name: {name}")
                names.add(name)

    return blockers

def detect_professional_signals(data: dict[str, Any]) -> dict[str, bool]:
    nodes = data.get("nodes") or []
    all_text = "\n".join(node_text(n) for n in nodes if isinstance(n, dict))

    signals: dict[str, bool] = {}
    for name, words in PROFESSIONAL_SIGNALS.items():
        signals[name] = any(w in all_text for w in words)

    return signals

def connection_stats(data: dict[str, Any]) -> dict[str, Any]:
    connections = data.get("connections") or {}
    nodes = data.get("nodes") or []

    connected_from = set(connections.keys())
    connected_to = set()

    for src, payload in connections.items():
        if not isinstance(payload, dict):
            continue
        for channel_payload in payload.values():
            if not isinstance(channel_payload, list):
                continue
            for group in channel_payload:
                if not isinstance(group, list):
                    continue
                for item in group:
                    if isinstance(item, dict) and item.get("node"):
                        connected_to.add(item["node"])

    node_names = {n.get("name") for n in nodes if isinstance(n, dict) and n.get("name")}
    isolated = sorted(n for n in node_names if n not in connected_from and n not in connected_to)

    return {
        "node_count": len(nodes),
        "connection_source_count": len(connected_from),
        "connection_target_count": len(connected_to),
        "isolated_nodes": isolated,
    }

def score_workflow(blockers: list[str], secret_hits: list[dict[str, str]], signals: dict[str, bool], stats: dict[str, Any]) -> tuple[str, list[str]]:
    warnings: list[str] = []

    if secret_hits:
        blockers.append("secret-like values detected")

    missing_signals = [k for k, v in signals.items() if not v]
    important_missing = [x for x in missing_signals if x in {"logs", "fallback", "human_transfer", "dry_run_or_safety"}]

    for x in important_missing:
        warnings.append(f"missing professional signal: {x}")

    isolated = stats.get("isolated_nodes") or []
    if isolated:
        warnings.append(f"isolated nodes detected: {', '.join(isolated[:8])}")

    if blockers:
        return "block", warnings

    if important_missing or isolated:
        return "warn", warnings

    return "pass", warnings

def validate(path: Path) -> dict[str, Any]:
    data = load_json(path)

    blockers = validate_shape(data)
    secret_hits = detect_secrets(data)
    signals = detect_professional_signals(data)
    stats = connection_stats(data)
    verdict, warnings = score_workflow(blockers, secret_hits, signals, stats)

    return {
        "verdict": verdict,
        "workflow_path": str(path),
        "workflow_name": data.get("name"),
        "active": data.get("active"),
        "blockers": blockers,
        "warnings": warnings,
        "secret_hits": secret_hits,
        "professional_signals": signals,
        "stats": stats,
        "status_real": "json_import_qa_only_not_n8n_runtime_validated",
    }

def write_report(result: dict[str, Any]) -> Path:
    stamp = now_slug()
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(result.get("workflow_name") or "workflow").lower()).strip("-")[:80]
    folder = OUT / f"{stamp}_{name}"
    folder.mkdir(parents=True, exist_ok=True)

    json_path = folder / "N8N_VALIDATION.json"
    md_path = folder / "N8N_VALIDATION.md"

    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# JARVIS n8n Workflow Validation",
        "",
        f"- verdict: `{result['verdict']}`",
        f"- workflow: `{result.get('workflow_name')}`",
        f"- active: `{result.get('active')}`",
        f"- status_real: `{result.get('status_real')}`",
        "",
        "## Blockers",
    ]

    if result["blockers"]:
        lines += [f"- {x}" for x in result["blockers"]]
    else:
        lines.append("- none")

    lines += ["", "## Warnings"]
    if result["warnings"]:
        lines += [f"- {x}" for x in result["warnings"]]
    else:
        lines.append("- none")

    lines += ["", "## Professional signals"]
    for k, v in result["professional_signals"].items():
        lines.append(f"- {k}: `{v}`")

    lines += ["", "## Stats"]
    for k, v in result["stats"].items():
        lines.append(f"- {k}: `{v}`")

    lines += ["", "## Secret hits"]
    if result["secret_hits"]:
        for hit in result["secret_hits"]:
            lines.append(f"- {hit['kind']} at `{hit['path']}` preview `{hit['preview']}`")
    else:
        lines.append("- none")

    lines += [
        "",
        "Status real: this validates exported JSON shape and safety signals only. It does not prove credentials, webhook, external APIs, n8n import UI, or production runtime.",
        "",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path

def find_latest_builder_workflow() -> Path | None:
    base = ROOT / "05_EXECUCAO" / "204_N8N_WORKFLOW_BUILDER"
    if not base.exists():
        return None
    candidates = sorted(base.rglob("workflow_skeleton.importable.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow", nargs="?", help="Path to n8n workflow JSON. If omitted, validates latest builder skeleton.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    path = Path(args.workflow).expanduser() if args.workflow else find_latest_builder_workflow()
    if path is None:
        print("N8N_VALIDATOR_BLOCKED")
        print(json.dumps({"verdict": "block", "blockers": ["no workflow path provided and no builder skeleton found"]}, indent=2))
        return 1

    if not path.is_absolute():
        path = ROOT / path

    if not path.exists():
        print("N8N_VALIDATOR_BLOCKED")
        print(json.dumps({"verdict": "block", "blockers": [f"workflow file not found: {path}"]}, indent=2))
        return 1

    result = validate(path)
    report = write_report(result)

    print("N8N_VALIDATOR_DONE")
    print(report.relative_to(ROOT))
    print(json.dumps({
        "verdict": result["verdict"],
        "workflow": result.get("workflow_name"),
        "blockers": len(result["blockers"]),
        "warnings": len(result["warnings"]),
        "secret_hits": len(result["secret_hits"]),
        "nodes": result["stats"].get("node_count"),
    }, indent=2))

    return 0 if result["verdict"] in {"pass", "warn"} else 2

if __name__ == "__main__":
    raise SystemExit(main())
