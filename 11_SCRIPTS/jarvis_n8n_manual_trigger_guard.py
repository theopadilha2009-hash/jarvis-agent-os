#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / "05_EXECUCAO" / "209_N8N_WORKFLOW_PIPELINE"
OUT = ROOT / "05_EXECUCAO" / "213_N8N_MANUAL_TRIGGER_GUARD"
OUT.mkdir(parents=True, exist_ok=True)

MANUAL_NODE = {
    "parameters": {},
    "id": "jarvis-manual-trigger-safety-smoke",
    "name": "Manual Trigger - Safety Smoke",
    "type": "n8n-nodes-base.manualTrigger",
    "typeVersion": 1,
    "position": [-900, -420],
    "notes": "JARVIS safety node: import and review manually before activating webhook/runtime.",
}

def load_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def latest_named(base: Path, name: str) -> Path | None:
    if not base.exists():
        return None
    files = sorted(base.rglob(name), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

def find_export_path(obj: Any) -> str | None:
    if isinstance(obj, dict):
        for value in obj.values():
            if isinstance(value, str) and value.endswith("IMPORT_THIS_IN_N8N.json"):
                return value
            found = find_export_path(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_export_path(item)
            if found:
                return found
    return None

def to_path(value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else ROOT / p

def has_manual_trigger(workflow: dict[str, Any]) -> bool:
    for node in workflow.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", "")).lower()
        node_name = str(node.get("name", "")).lower()
        if "manualtrigger" in node_type or "manual trigger" in node_name:
            return True
    return False

def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []

    pipeline_path = latest_named(PIPELINE_DIR, "N8N_PIPELINE.json")
    pipeline = load_json(pipeline_path) or {}

    export_raw = find_export_path(pipeline)
    export_path = to_path(export_raw)
    workflow = load_json(export_path)

    if not pipeline_path:
        blockers.append("missing latest N8N_PIPELINE.json")
    if not export_path or not export_path.exists():
        blockers.append("missing IMPORT_THIS_IN_N8N.json")
    if not isinstance(workflow, dict):
        blockers.append("export workflow JSON could not be parsed")
        workflow = {}

    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        blockers.append("workflow nodes is not a list")
        nodes = []
        workflow["nodes"] = nodes

    before_nodes = len(nodes)
    already_had_manual = has_manual_trigger(workflow)
    changed = False

    if not blockers and not already_had_manual:
        nodes.insert(0, dict(MANUAL_NODE))
        changed = True

    if workflow.get("active") is not False:
        workflow["active"] = False
        changed = True
        warnings.append("active flag was forced to false")

    after_nodes = len(nodes)

    if not blockers and export_path:
        export_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")

    if not blockers and pipeline_path:
        pipeline["manual_trigger_guard"] = {
            "applied": True,
            "already_had_manual": already_had_manual,
            "changed": changed,
            "before_nodes": before_nodes,
            "after_nodes": after_nodes,
            "export_path": str(export_path.relative_to(ROOT)) if export_path else export_raw,
            "status_real": "manual_trigger_added_to_latest_import_export_only",
        }
        if "nodes" in pipeline:
            pipeline["nodes"] = after_nodes
        pipeline_path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "pass" if not blockers else "block",
        "blockers": blockers,
        "warnings": warnings,
        "pipeline_json": str(pipeline_path.relative_to(ROOT)) if pipeline_path else None,
        "export_path": str(export_path.relative_to(ROOT)) if export_path and export_path.exists() else export_raw,
        "already_had_manual": already_had_manual,
        "changed": changed,
        "before_nodes": before_nodes,
        "after_nodes": after_nodes,
        "active": workflow.get("active"),
        "status_real": "local_export_safety_patch_only_not_runtime_or_production_validated",
    }

    (OUT / "N8N_MANUAL_TRIGGER_GUARD.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# JARVIS n8n Manual Trigger Safety Guard",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- changed: `{payload['changed']}`",
        f"- already_had_manual: `{payload['already_had_manual']}`",
        f"- before_nodes: `{payload['before_nodes']}`",
        f"- after_nodes: `{payload['after_nodes']}`",
        f"- active: `{payload['active']}`",
        f"- export_path: `{payload['export_path']}`",
        f"- status_real: `{payload['status_real']}`",
        "",
        "## Blockers",
    ]
    md += [f"- {b}" for b in blockers] if blockers else ["- none"]
    md += ["", "## Warnings"]
    md += [f"- {w}" for w in warnings] if warnings else ["- none"]

    (OUT / "N8N_MANUAL_TRIGGER_GUARD.md").write_text("\n".join(md), encoding="utf-8")

    print("N8N_MANUAL_TRIGGER_GUARD_DONE")
    print(OUT / "N8N_MANUAL_TRIGGER_GUARD.md")
    print(json.dumps({
        "verdict": payload["verdict"],
        "changed": payload["changed"],
        "already_had_manual": payload["already_had_manual"],
        "before_nodes": payload["before_nodes"],
        "after_nodes": payload["after_nodes"],
        "active": payload["active"],
        "blockers": blockers,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))

    return 0 if payload["verdict"] == "pass" else 1

if __name__ == "__main__":
    raise SystemExit(main())
